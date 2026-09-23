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

log = logging.getLogger(__name__)

REFUSAL_TEXT = (
    "Sorry, I don't have that in the Fab Lab guides. "
    'To get a staff member, double-press the button or say "call staff".'
)
DIDNT_CATCH_TEXT = "Sorry, I didn't catch that. Please hold the button and try again."
ERROR_TEXT = "Sorry, something went wrong. Please try again."
HELP_CONFIRMATION_TEXT = "I've called Fab Lab staff. Please stay by the machine."
ALREADY_CALLED_TEXT = "Staff have already been called. Please stay by the machine."
HELP_FAILED_TEXT = "Sorry, I couldn't reach Fab Lab staff. Please find a staff member in the lab."
ON_THE_WAY_TEXT = "A staff member is on the way."

HELP_ACTIONS = ("ack", "resolve")
RECENT_QUESTIONS = 3


@dataclass
class Answer:
    text: str
    intent: Intent
    sources: list[str] = field(default_factory=list)
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


class LLMLike(Protocol):
    def chat(self, messages: list[dict[str, str]]) -> str: ...


class TTSLike(Protocol):
    def speak(self, text: str) -> None: ...


class NotifierLike(Protocol):
    def send_help(self, request: HelpRequest) -> Awaitable[None]: ...


class UnansweredLogLike(Protocol):
    def log(self, device_id: str, machine: str, question: str, best_score: float) -> None: ...


DeviceLookup = Callable[[str], Mapping[str, str]]


def _local_now() -> datetime:
    return datetime.now().astimezone()


def _unique_sources(results: Sequence[ScoredChunkLike]) -> list[str]:
    return list(dict.fromkeys(r.chunk.source for r in results))


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
        """Route `text` by intent (emergency, help, question) and optionally speak the answer."""
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
            answer = await self._answer_question(device_id, text)
        if speak:
            await self._speak(device_id, answer.text)
        return answer

    async def _answer_question(self, device_id: str, text: str) -> Answer:
        device = self.devices(device_id)
        machine, location = device["machine"], device["location"]
        session = self.sessions.get(device_id)
        previous = session.last_user_messages(1)
        query = f"{previous[0]} {text}" if previous else text
        results = list(await asyncio.to_thread(self.kb.retrieve, query, machine))
        best_score = max((r.score for r in results), default=0.0)
        help_status = self.states.get(device_id).help
        if self.kb.is_confident(results):
            chunks, sources = [r.chunk for r in results], _unique_sources(results)
        elif help_status is not HelpStatus.NONE:
            # let the LLM answer "is someone coming?" from the staff status line
            chunks, sources = [], []
        else:
            self.unanswered.log(device_id, machine, text, best_score)
            session.add_turn(text, REFUSAL_TEXT)
            return Answer(REFUSAL_TEXT, Intent.QUESTION, refused=True, best_score=best_score)
        messages = build_messages(
            machine,
            location,
            chunks,
            session.history_messages(),
            text,
            help_status,
            self._help_called_at.get(device_id),
        )
        reply = (await asyncio.to_thread(self.llm.chat, messages)).strip()
        session.add_turn(text, reply)
        return Answer(reply, Intent.QUESTION, sources=sources, best_score=best_score)

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
