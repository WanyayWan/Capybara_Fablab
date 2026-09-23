"""Voice pipeline: button events → recording → STT → intent → RAG/LLM → TTS, plus staff help.

Depends only on the small interfaces below, so tests drive it entirely with fakes.
Blocking calls (STT, retrieval, LLM, TTS) run via `asyncio.to_thread`. A per-device
`asyncio.Lock` stops a second press from starting a parallel run. Any processing
exception sets activity `error` and speaks a best-effort apology.

Speech triggered by events rather than a question (help confirmation, "on the way") runs
as a background task so HTTP handlers and the Telegram poller return straight away;
`drain()` waits for background work. One laptop mic is shared by all devices, so only
one device can record at a time.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import Awaitable, Callable, Coroutine, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

import numpy as np

from config import Settings
from core.device_state import Activity, DeviceStateStore, HelpStatus
from core.intents import EMERGENCY_RESPONSE, Intent, detect_intent
from core.prompts import ContextChunk, build_messages
from core.sessions import SessionManager
from core.speech_text import to_speakable
from core.steps import ProcedurePointer, pointer_for

log = logging.getLogger(__name__)

NOT_IN_GUIDES_TEXT = "Sorry, I don't have that in the Fab Lab guides."
REFUSAL_TEXT = (
    f"{NOT_IN_GUIDES_TEXT} "
    'To get a staff member, double-press the button or say "call staff".'
)
NO_ANSWER = "NO_ANSWER"  # the LLM's reply when CONTEXT doesn't answer; never spoken
WHAT_HELP_TEXT = "What would you like help with?"
LAST_STEP_TEXT = "That was the last step. Anything else?"
NEXT_TURN_USER_TEXT = "next"
DIDNT_CATCH_TEXT = "Sorry, I didn't catch that. Please hold the button and try again."
ERROR_TEXT = "Sorry, something went wrong. Please try again."
HELP_CONFIRMATION_TEXT = "I've called Fab Lab staff. Please stay by the machine."
ALREADY_CALLED_TEXT = "Staff have already been called. Please stay by the machine."
HELP_FAILED_TEXT = "Sorry, I couldn't reach Fab Lab staff. Please find a staff member in the lab."
ON_THE_WAY_TEXT = "A staff member is on the way."

HELP_ACTIONS = ("ack", "resolve")
RECENT_QUESTIONS = 3
STEP_HISTORY_TURNS = 2  # step mode sends only the last 2 turns with the next step


@dataclass
class Answer:
    text: str
    intent: Intent
    sources: list[dict[str, str]] = field(default_factory=list)  # spoken_source + origin
    refused: bool = False
    best_score: float | None = None


@dataclass
class HelpRequest:
    device_id: str
    machine: str
    location: str
    time: datetime
    recent_questions: list[str]
    emergency: bool
    help_id: str


class ScoredChunkLike(Protocol):
    chunk: ContextChunk
    score: float


class RecorderLike(Protocol):
    sample_rate: int
    last_pre_roll_samples: int

    @property
    def is_recording(self) -> bool: ...
    def start(self) -> None: ...
    def stop(self) -> np.ndarray: ...
    def cancel(self) -> None: ...


class STTLike(Protocol):
    def transcribe(self, samples: np.ndarray) -> str: ...


class KnowledgeBaseLike(Protocol):
    def retrieve(self, query: str, machine: str) -> Sequence[ScoredChunkLike]: ...
    def is_confident(self, results: Sequence[ScoredChunkLike]) -> bool: ...
    def step_chunk(self, file: str, step: int) -> ContextChunk | None: ...


class LLMLike(Protocol):
    def chat(self, messages: list[dict[str, str]]) -> str: ...


class TTSLike(Protocol):
    def speak(self, text: str) -> None: ...


class NotifierLike(Protocol):
    def send_help(self, request: HelpRequest) -> Awaitable[None]: ...


class UnansweredLogLike(Protocol):
    def log(self, device_id: str, machine: str, question: str, best_score: float | None) -> None: ...


DeviceLookup = Callable[[str], Mapping[str, str]]


def _local_now() -> datetime:
    return datetime.now().astimezone()


def _unique_sources(chunks: Sequence[ContextChunk]) -> list[dict[str, str]]:
    """One `{"spoken_source", "origin"}` entry per distinct origin, in rank order."""
    unique = dict.fromkeys((c.spoken_source, c.origin) for c in chunks)
    return [{"spoken_source": spoken, "origin": origin} for spoken, origin in unique]


def _turn_user_text(text: str, intent: Intent) -> str:
    """Session history stores every NEXT as plain "next"."""
    return NEXT_TURN_USER_TEXT if intent is Intent.NEXT else text


def _last_question(user_messages: list[str]) -> str | None:
    """The most recent user message that isn't a NEXT ("next", "go on"...)."""
    for message in reversed(user_messages):
        if detect_intent(message) is not Intent.NEXT:
            return message
    return None


class VoicePipeline:
    def __init__(
        self,
        settings: Settings,
        recorder: RecorderLike,
        stt: STTLike,
        kb: KnowledgeBaseLike,
        llm: LLMLike,
        tts: TTSLike,
        notifier: NotifierLike,
        states: DeviceStateStore,
        sessions: SessionManager,
        unanswered: UnansweredLogLike,
        devices: DeviceLookup,
        now: Callable[[], datetime] = _local_now,
    ) -> None:
        self.settings = settings
        self.recorder = recorder
        self.stt = stt
        self.kb = kb
        self.llm = llm
        self.tts = tts
        self.notifier = notifier
        self.states = states
        self.sessions = sessions
        self.unanswered = unanswered
        self.devices = devices
        self._now = now
        self._locks: dict[str, asyncio.Lock] = {}
        self._speech_lock = asyncio.Lock()
        self._tasks: set[asyncio.Task[Any]] = set()
        self._recording_device: str | None = None
        self._help_called_at: dict[str, datetime] = {}

    # ---- button events -------------------------------------------------------------

    async def talk_pressed(self, device_id: str) -> dict[str, object]:
        """Start recording unless busy; returns `{"accepted": bool, ...}`."""
        activity = self.states.get(device_id).activity
        mic_taken = self.recorder.is_recording and self._recording_device != device_id
        if activity in (Activity.THINKING, Activity.SPEAKING) or self._lock(device_id).locked() or mic_taken:
            return {"accepted": False, "reason": "busy"}
        self.recorder.start()
        self._recording_device = device_id
        self.states.set_activity(device_id, Activity.LISTENING)
        return {"accepted": True}

    async def talk_released(self, device_id: str, held_ms: int) -> dict[str, object]:
        """Stop recording; reject if shorter than MIN_RECORD_S, else process in the background.

        The duration is the recorded audio minus pre-roll; with no audio at all it falls
        back to `held_ms` (build-plan section 9.4).
        """
        if not self.recorder.is_recording or self._recording_device != device_id:
            return {"accepted": False, "reason": "not_recording"}
        samples = self.recorder.stop()
        self._recording_device = None
        if self._recorded_seconds(samples, held_ms) < self.settings.min_record_s:
            self.states.set_activity(device_id, Activity.IDLE)
            return {"accepted": False, "reason": "too_short"}
        self.states.set_activity(device_id, Activity.THINKING)
        self._spawn(self._process_audio(device_id, samples))
        return {"accepted": True}

    def _recorded_seconds(self, samples: np.ndarray, held_ms: int) -> float:
        if samples.size == 0:
            return held_ms / 1000
        recorded = max(0, samples.size - self.recorder.last_pre_roll_samples)
        return recorded / self.recorder.sample_rate

    async def _process_audio(self, device_id: str, samples: np.ndarray) -> None:
        """Transcribe `samples` and hand the text to `handle_text` with speech on."""
        async with self._lock(device_id):
            try:
                text = (await asyncio.to_thread(self.stt.transcribe, samples)).strip()
                log.info("[%s] heard: %r", device_id, text)
                if not text:
                    await self._speak(device_id, DIDNT_CATCH_TEXT)
                    return
                await self.handle_text(device_id, text, speak=True)
            except Exception:
                log.exception("[%s] voice turn failed", device_id)
                await self._fail(device_id)

    # ---- text turns ----------------------------------------------------------------

    async def ask(self, device_id: str, text: str, speak: bool = False) -> Answer:
        """`handle_text` under the device lock (used by `/api/ask`)."""
        async with self._lock(device_id):
            try:
                return await self.handle_text(device_id, text, speak)
            except Exception:
                if speak:
                    self.states.set_activity(device_id, Activity.ERROR)
                raise

    async def handle_text(self, device_id: str, text: str, speak: bool) -> Answer:
        """Route `text` by intent (emergency, help, next, question) and optionally speak the answer."""
        intent = detect_intent(text)
        if intent is Intent.EMERGENCY:
            help_text = await self.request_help(device_id, "voice", emergency=True, speak=False)
            reply = EMERGENCY_RESPONSE
            if help_text == HELP_FAILED_TEXT:
                reply = f"{reply} {HELP_FAILED_TEXT}"
            answer = Answer(reply, intent)
        elif intent is Intent.HELP:
            answer = Answer(await self.request_help(device_id, "voice", speak=False), intent)
        else:
            answer = await self._answer_question(device_id, text, intent)
        if speak:
            await self._speak(device_id, answer.text)
        return answer

    async def _answer_question(self, device_id: str, text: str, intent: Intent) -> Answer:
        """Answer a QUESTION or a NEXT from the knowledge base.

        QUESTION: clears the step pointer; retrieval query is the last question + this
        one; below the threshold (a junk filter) it is refused and logged, with no LLM
        call. If the retrieved chunks include a procedure overview or a "Step N" chunk,
        the session's pointer is set to that file and step (overview -> step 1, and the
        Step 1 chunk joins the context).
        NEXT with a pointer: `_next_step`. NEXT without one: retrieval query is the last
        question alone and the threshold gate is skipped; with no earlier question it
        just asks what the user needs.
        Whenever the LLM replies NO_ANSWER (CONTEXT doesn't answer), the turn is refused
        and logged like a below-threshold question.
        """
        device = self.devices(device_id)
        machine = device["machine"]
        session = self.sessions.get(device_id)
        if intent is Intent.NEXT and session.procedure is not None:
            return await self._next_step(device_id, text, session.procedure)
        previous = _last_question(session.last_user_messages(len(session.turns)))
        if intent is Intent.NEXT:
            if previous is None:
                return Answer(WHAT_HELP_TEXT, intent)
            query = previous
        else:
            session.procedure = None
            query = f"{previous} {text}" if previous else text
        started = time.perf_counter()
        results = list(await asyncio.to_thread(self.kb.retrieve, query, machine))
        log.info("[%s] retrieval (query embed + search) %.2f s", device_id, time.perf_counter() - started)
        best_score = max((r.score for r in results), default=0.0)
        if intent is Intent.QUESTION and not self.kb.is_confident(results):
            return self._refuse(device_id, machine, text, intent, best_score)
        chunks = [r.chunk for r in results]
        pointer = pointer_for(chunks) if intent is Intent.QUESTION else None
        if pointer is not None and pointer.step == 1:
            first = self.kb.step_chunk(pointer.file, 1)
            if first is not None and first not in chunks:
                chunks.append(first)
        reply = await self._llm_reply(device_id, chunks, session.history_messages(), text)
        if reply is None:
            return self._refuse(device_id, machine, text, intent, best_score)
        session.procedure = pointer
        session.add_turn(_turn_user_text(text, intent), reply)
        return Answer(reply, intent, sources=_unique_sources(chunks), best_score=best_score)

    async def _next_step(self, device_id: str, text: str, pointer: ProcedurePointer) -> Answer:
        """Step mode: fetch "Step N+1" of the pointer's file directly (no retrieval) and
        send only that chunk plus a short history. After the last step, say so without
        calling the LLM."""
        session = self.sessions.get(device_id)
        chunk = self.kb.step_chunk(pointer.file, pointer.step + 1)
        if chunk is None:
            session.add_turn(NEXT_TURN_USER_TEXT, LAST_STEP_TEXT)
            return Answer(LAST_STEP_TEXT, Intent.NEXT)
        history = session.history_messages(last_turns=STEP_HISTORY_TURNS)
        reply = await self._llm_reply(device_id, [chunk], history, text)
        if reply is None:
            session.procedure = None
            return self._refuse(device_id, self.devices(device_id)["machine"], text, Intent.NEXT, None)
        session.procedure = ProcedurePointer(pointer.file, pointer.step + 1)
        session.add_turn(NEXT_TURN_USER_TEXT, reply)
        return Answer(reply, Intent.NEXT, sources=_unique_sources([chunk]))

    async def _llm_reply(
        self,
        device_id: str,
        chunks: Sequence[ContextChunk],
        history: list[dict[str, str]],
        text: str,
    ) -> str | None:
        """Ask the LLM with `chunks` as CONTEXT; None if it replied NO_ANSWER."""
        device = self.devices(device_id)
        messages = build_messages(
            device["machine"],
            device["location"],
            chunks,
            history,
            text,
            self.states.get(device_id).help,
            self._help_called_at.get(device_id),
        )
        started = time.perf_counter()
        reply = (await asyncio.to_thread(self.llm.chat, messages)).strip()
        log.info(
            "[%s] LLM call %.2f s (context: %s)",
            device_id,
            time.perf_counter() - started,
            "; ".join(c.heading for c in chunks),
        )
        if NO_ANSWER in reply:
            log.info("[%s] LLM found no answer in CONTEXT", device_id)
            return None
        return reply

    def _refuse(
        self, device_id: str, machine: str, text: str, intent: Intent, best_score: float | None
    ) -> Answer:
        """Log `text` as unanswered and reply with the refusal (or the staff-status version).

        The refusal is still stored in the session so staff see it in `recent_questions`."""
        self.unanswered.log(device_id, machine, text, best_score)
        reply = self._refusal(device_id)
        self.sessions.get(device_id).add_turn(_turn_user_text(text, intent), reply)
        return Answer(reply, intent, refused=True, best_score=best_score)

    def _refusal(self, device_id: str) -> str:
        """The refusal, or, if staff are already called, "not in the guides" + their status."""
        status = self.states.get(device_id).help
        if status is HelpStatus.NONE:
            return REFUSAL_TEXT
        called_at = self._help_called_at.get(device_id)
        called = f"Staff were called at {called_at:%H:%M}" if called_at else "Staff were called"
        if status is HelpStatus.ACKNOWLEDGED:
            return f"{NOT_IN_GUIDES_TEXT} {called} and are on the way."
        return f"{NOT_IN_GUIDES_TEXT} {called} and should be with you shortly."

    # ---- staff help ----------------------------------------------------------------

    async def request_help(
        self,
        device_id: str,
        source: str,
        emergency: bool = False,
        speak: bool = True,
    ) -> str:
        """Call staff (deduped while pending) and return the confirmation text.

        An emergency is sent even if a request is already pending. With `speak`, the
        confirmation is spoken in the background.
        """
        self._cancel_recording(device_id)
        if self.states.get(device_id).help is HelpStatus.PENDING and not emergency:
            text = ALREADY_CALLED_TEXT
        else:
            text = await self._send_help(device_id, source, emergency)
        if speak:
            self._spawn(self._say(device_id, text))
        return text

    async def _send_help(self, device_id: str, source: str, emergency: bool) -> str:
        device = self.devices(device_id)
        called_at = self._now()
        self.states.set_help(device_id, HelpStatus.PENDING)
        self._help_called_at[device_id] = called_at
        request = HelpRequest(
            device_id=device_id,
            machine=device["machine"],
            location=device["location"],
            time=called_at,
            recent_questions=self.sessions.get(device_id).last_user_messages(RECENT_QUESTIONS),
            emergency=emergency,
            help_id=uuid.uuid4().hex[:8],
        )
        log.info("[%s] help requested via %s (emergency=%s)", device_id, source, emergency)
        try:
            await self.notifier.send_help(request)
        except Exception:
            log.exception("[%s] could not notify staff", device_id)
            self.states.set_help(device_id, HelpStatus.NONE)
            self._help_called_at.pop(device_id, None)
            return HELP_FAILED_TEXT
        return HELP_CONFIRMATION_TEXT

    async def help_update(self, device_id: str, action: str) -> None:
        """Apply a staff action: `ack` → acknowledged, `resolve` → none.

        `ack` is ignored unless help is pending (stale or duplicate button presses).
        """
        if action not in HELP_ACTIONS:
            raise ValueError(f"unknown help action: {action!r}")
        if action == "resolve":
            self.states.set_help(device_id, HelpStatus.NONE)
            self._help_called_at.pop(device_id, None)
            return
        if self.states.get(device_id).help is not HelpStatus.PENDING:
            return
        self.states.set_help(device_id, HelpStatus.ACKNOWLEDGED)
        self._spawn(self._say(device_id, ON_THE_WAY_TEXT))

    def _cancel_recording(self, device_id: str) -> None:
        if self.recorder.is_recording and self._recording_device == device_id:
            self.recorder.cancel()
            self._recording_device = None
            self.states.set_activity(device_id, Activity.IDLE)

    # ---- speech and background tasks -----------------------------------------------

    async def _speak(self, device_id: str, text: str, show_activity: bool = True) -> None:
        """Speak `text` (one utterance at a time); LED green while speaking, then idle."""
        async with self._speech_lock:
            if show_activity:
                self.states.set_activity(device_id, Activity.SPEAKING)
            await asyncio.to_thread(self.tts.speak, to_speakable(text))
            if show_activity:
                self.states.set_activity(device_id, Activity.IDLE)

    async def _say(self, device_id: str, text: str) -> None:
        """Background speech for help updates. Leaves the activity alone, so the LED shows
        the help colour (red_pulse / purple) straight away instead of green."""
        try:
            await self._speak(device_id, text, show_activity=False)
        except Exception:
            log.exception("[%s] could not speak %r", device_id, text)

    async def _fail(self, device_id: str) -> None:
        self.states.set_activity(device_id, Activity.ERROR)
        try:
            async with self._speech_lock:
                await asyncio.to_thread(self.tts.speak, ERROR_TEXT)
        except Exception:
            log.exception("[%s] could not speak the error message", device_id)

    def _lock(self, device_id: str) -> asyncio.Lock:
        return self._locks.setdefault(device_id, asyncio.Lock())

    def _spawn(self, coro: Coroutine[Any, Any, None]) -> None:
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def drain(self) -> None:
        """Wait until all background work (voice turns, queued speech) has finished."""
        while self._tasks:
            await asyncio.gather(*list(self._tasks), return_exceptions=True)
