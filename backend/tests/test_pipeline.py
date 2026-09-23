"""Voice pipeline with fakes and FakeClock (test-plan: test_pipeline.py).

Threshold-dependent tests use their own RAG threshold (build-plan section 9.8)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np

from config import Settings, get_device
from core.device_state import Activity, DeviceStateStore, HelpStatus
from core.intents import EMERGENCY_RESPONSE, Intent
from core.pipeline import (
    ALREADY_CALLED_TEXT,
    DIDNT_CATCH_TEXT,
    ERROR_TEXT,
    HELP_CONFIRMATION_TEXT,
    HELP_FAILED_TEXT,
    ON_THE_WAY_TEXT,
    REFUSAL_TEXT,
    VoicePipeline,
)
from core.sessions import SessionManager
from services.knowledge import Chunk, KnowledgeBase, knowledge_dirs, load_chunks
from tests.fakes import (
    FakeClock,
    FakeEmbedder,
    FakeLLM,
    FakeNotifier,
    FakeRecorder,
    FakeSTT,
    FakeTTS,
    FakeUnansweredLog,
)

KNOWLEDGE_ROOT = Path(__file__).resolve().parent.parent / "knowledge"
TEST_THRESHOLD = 0.5
RATE = 16000
DEVICE = "fabai-01"
LLM_REPLY = "According to the 3D printer guide, first heat the nozzle. Say next when you're ready."


def seconds(s: float) -> np.ndarray:
    return np.zeros(int(s * RATE), dtype=np.float32)


class StateSpyTTS(FakeTTS):
    """Also records the device activity at the moment each string is spoken."""

    def __init__(self, states: DeviceStateStore) -> None:
        super().__init__()
        self.states = states
        self.activities: list[Activity] = []

    def speak(self, text: str) -> None:
        self.activities.append(self.states.get(DEVICE).activity)
        super().speak(text)


class FailingNotifier(FakeNotifier):
    async def send_help(self, request):  # type: ignore[no-untyped-def]
        await super().send_help(request)
        raise RuntimeError("telegram down")


@dataclass
class Rig:
    pipeline: VoicePipeline
    recorder: FakeRecorder
    stt: FakeSTT
    llm: FakeLLM
    tts: StateSpyTTS
    notifier: FakeNotifier
    states: DeviceStateStore
    sessions: SessionManager
    unanswered: FakeUnansweredLog
    embedder: FakeEmbedder
    clock: FakeClock

    def activity(self, device_id: str = DEVICE) -> Activity:
        return self.states.get(device_id).activity

    def help(self, device_id: str = DEVICE) -> HelpStatus:
        return self.states.get(device_id).help


def make_rig(
    transcript: str = "how do I load filament",
    samples: np.ndarray | None = None,
    llm: FakeLLM | None = None,
    notifier: FakeNotifier | None = None,
    chunks: list[Chunk] | None = None,
) -> Rig:
    clock = FakeClock(1000.0)
    states = DeviceStateStore(clock.now)
    sessions = SessionManager(timeout_s=120, max_turns=6, clock=clock.now)
    embedder = FakeEmbedder()
    kb = KnowledgeBase(
        load_chunks(knowledge_dirs(KNOWLEDGE_ROOT)) if chunks is None else chunks,
        embedder,
        top_k=3,
        threshold=TEST_THRESHOLD,
        machine_boost=0.05,
    )
    kb.build()
    recorder = FakeRecorder(seconds(2.0) if samples is None else samples, RATE)
    stt = FakeSTT(transcript)
    llm = llm or FakeLLM(LLM_REPLY)
    tts = StateSpyTTS(states)
    notifier = notifier or FakeNotifier()
    unanswered = FakeUnansweredLog()
    pipeline = VoicePipeline(
        settings=Settings(min_record_s=0.5),
        recorder=recorder,
        stt=stt,
        kb=kb,
        llm=llm,
        tts=tts,
        notifier=notifier,
        states=states,
        sessions=sessions,
        unanswered=unanswered,
        devices=get_device,
        now=lambda: datetime(2026, 9, 24, 14, 5),
    )
    return Rig(pipeline, recorder, stt, llm, tts, notifier, states, sessions, unanswered, embedder, clock)


async def voice_turn(rig: Rig, device_id: str = DEVICE, held_ms: int = 2000) -> dict[str, object]:
    await rig.pipeline.talk_pressed(device_id)
    result = await rig.pipeline.talk_released(device_id, held_ms)
    await rig.pipeline.drain()
    return result


async def test_PL1_full_turn() -> None:
    """PL1: press, release 2 s -> listening, thinking, speaking, idle; 1 session turn."""
    rig = make_rig()
    assert await rig.pipeline.talk_pressed(DEVICE) == {"accepted": True}
    assert rig.activity() is Activity.LISTENING
    assert rig.recorder.start_calls == 1

    assert await rig.pipeline.talk_released(DEVICE, 2000) == {"accepted": True}
    assert rig.activity() is Activity.THINKING
    await rig.pipeline.drain()

    assert rig.tts.activities == [Activity.SPEAKING]
    assert rig.tts.spoken == ["According to the 3D printer guide, first heat the nozzle. Say next when you're ready."]
    assert rig.activity() is Activity.IDLE
    assert len(rig.stt.calls) == 1
    turns = rig.sessions.get(DEVICE).turns
    assert [(t.user, t.assistant) for t in turns] == [("how do I load filament", LLM_REPLY)]


async def test_PL2_too_short() -> None:
    """PL2: release after 0.2 s -> too_short, idle, STT not called."""
    rig = make_rig(samples=seconds(0.2))
    await rig.pipeline.talk_pressed(DEVICE)
    result = await rig.pipeline.talk_released(DEVICE, 200)
    await rig.pipeline.drain()
    assert result == {"accepted": False, "reason": "too_short"}
    assert rig.activity() is Activity.IDLE
    assert rig.stt.calls == []


async def test_PL2b_too_short_excludes_pre_roll() -> None:
    """Decision 9.4: 0.8 s of samples of which 0.5 s is pre-roll -> 0.3 s recorded -> too short."""
    rig = make_rig(samples=seconds(0.8))
    rig.recorder.pre_roll_samples = int(0.5 * RATE)
    await rig.pipeline.talk_pressed(DEVICE)
    result = await rig.pipeline.talk_released(DEVICE, 300)
    assert result == {"accepted": False, "reason": "too_short"}
    assert rig.stt.calls == []


async def test_PL2c_no_audio_falls_back_to_held_ms() -> None:
    """Decision 9.4: no samples at all -> use held_ms (long enough here, so accepted)."""
    rig = make_rig(samples=seconds(0))
    await rig.pipeline.talk_pressed(DEVICE)
    assert await rig.pipeline.talk_released(DEVICE, 2000) == {"accepted": True}
    await rig.pipeline.drain()

    rig2 = make_rig(samples=seconds(0))
    await rig2.pipeline.talk_pressed(DEVICE)
    assert await rig2.pipeline.talk_released(DEVICE, 200) == {"accepted": False, "reason": "too_short"}


async def test_PL2d_release_without_press() -> None:
    """A release with no recording in progress (e.g. cancelled by help) is ignored."""
    rig = make_rig()
    result = await rig.pipeline.talk_released(DEVICE, 2000)
    assert result == {"accepted": False, "reason": "not_recording"}
    assert rig.activity() is Activity.IDLE
    assert rig.stt.calls == []


async def test_PL3_empty_transcript() -> None:
    """PL3: STT "" -> TTS "didn't catch that", no LLM call."""
    rig = make_rig(transcript="  ")
    await voice_turn(rig)
    assert rig.tts.spoken == [DIDNT_CATCH_TEXT]
    assert "didn't catch that" in DIDNT_CATCH_TEXT
    assert rig.llm.calls == 0
    assert rig.activity() is Activity.IDLE


async def test_PL4_busy_while_thinking() -> None:
    """PL4: press while thinking -> accepted False, reason busy."""
    rig = make_rig()
    await rig.pipeline.talk_pressed(DEVICE)
    await rig.pipeline.talk_released(DEVICE, 2000)
    assert rig.activity() is Activity.THINKING
    assert await rig.pipeline.talk_pressed(DEVICE) == {"accepted": False, "reason": "busy"}
    assert rig.recorder.start_calls == 1
    await rig.pipeline.drain()
    assert await rig.pipeline.talk_pressed(DEVICE) == {"accepted": True}


async def test_PL4b_other_device_busy_while_recording() -> None:
    """One laptop mic: a second device can't start while the first is recording."""
    rig = make_rig()
    await rig.pipeline.talk_pressed(DEVICE)
    assert await rig.pipeline.talk_pressed("fabai-02") == {"accepted": False, "reason": "busy"}
    assert await rig.pipeline.talk_released("fabai-02", 2000) == {
        "accepted": False,
        "reason": "not_recording",
    }


async def test_PL5_refuse_no_confident_chunk() -> None:
    """PL5: no confident chunk -> refusal, refused, logged, no LLM."""
    rig = make_rig()
    answer = await rig.pipeline.handle_text(DEVICE, "best pizza", speak=False)
    assert answer.refused is True
    assert answer.text == REFUSAL_TEXT
    assert answer.intent is Intent.QUESTION
    assert answer.sources == []
    assert answer.best_score is not None and answer.best_score < TEST_THRESHOLD
    assert rig.llm.calls == 0
    assert rig.unanswered.entries == [
        {
            "device_id": DEVICE,
            "machine": "3d-printer",
            "question": "best pizza",
            "best_score": answer.best_score,
        }
    ]
    assert rig.tts.spoken == []


async def test_PL5b_confident_answer_has_sources() -> None:
    rig = make_rig()
    answer = await rig.pipeline.handle_text(DEVICE, "what is the maximum SD card size", speak=False)
    assert answer.refused is False
    assert answer.text == LLM_REPLY
    assert answer.sources and len(answer.sources) == len(set(answer.sources))
    assert answer.best_score is not None and answer.best_score >= TEST_THRESHOLD
    assert rig.unanswered.entries == []


async def test_PL6_follow_up_query_combined() -> None:
    """PL6: follow-up retrieval query contains both questions."""
    rig = make_rig()
    await rig.pipeline.handle_text(DEVICE, "what is the maximum SD card size", speak=False)
    await rig.pipeline.handle_text(DEVICE, "what about the X1E", speak=False)
    query = rig.embedder.calls[-1][0]
    assert "what is the maximum SD card size" in query
    assert "what about the X1E" in query


async def test_PL6b_first_question_query_alone() -> None:
    rig = make_rig()
    await rig.pipeline.handle_text(DEVICE, "what is the maximum SD card size", speak=False)
    assert rig.embedder.calls[-1] == ["what is the maximum SD card size"]


async def test_PL7_next_uses_history() -> None:
    """PL7: "next" -> LLM receives history with the previous step.

    Uses a one-chunk KB: with the real guides, FakeEmbedder's bag of words drops below
    the threshold when "next" is appended (retrieval quality is judged in Phase 5)."""
    procedure = Chunk("p#1", "3d-printer", "3D printer guide", "Load filament", "Load filament steps.")
    rig = make_rig(chunks=[procedure])
    await rig.pipeline.handle_text(DEVICE, "how do I load filament", speak=False)
    answer = await rig.pipeline.handle_text(DEVICE, "next", speak=False)
    assert answer.refused is False
    messages = rig.llm.last_messages
    assert messages is not None
    assert messages[1:] == [
        {"role": "user", "content": "how do I load filament"},
        {"role": "assistant", "content": LLM_REPLY},
        {"role": "user", "content": "next"},
    ]


async def test_PL8_help_event() -> None:
    """PL8: help_requested -> notifier once, pending, TTS confirmation, red_pulse."""
    rig = make_rig()
    text = await rig.pipeline.request_help(DEVICE, source="button")
    assert text == HELP_CONFIRMATION_TEXT
    assert rig.help() is HelpStatus.PENDING
    await rig.pipeline.drain()
    assert len(rig.notifier.requests) == 1
    request = rig.notifier.requests[0]
    assert (request.device_id, request.machine, request.location) == (DEVICE, "3d-printer", "3D Printing Lab")
    assert request.emergency is False and request.help_id
    assert rig.tts.spoken == [HELP_CONFIRMATION_TEXT]
    assert rig.states.led(DEVICE) == "red_pulse"


async def test_PL9_help_cancels_recording() -> None:
    """PL9: help while recording -> recorder cancelled."""
    rig = make_rig()
    await rig.pipeline.talk_pressed(DEVICE)
    await rig.pipeline.request_help(DEVICE, source="button")
    await rig.pipeline.drain()
    assert rig.recorder.cancel_calls == 1
    assert not rig.recorder.is_recording
    assert rig.activity() is Activity.IDLE
    assert await rig.pipeline.talk_released(DEVICE, 2000) == {"accepted": False, "reason": "not_recording"}
    assert rig.stt.calls == []


async def test_PL10_help_deduped() -> None:
    """PL10: second help while pending -> notifier once, "already been called"."""
    rig = make_rig()
    await rig.pipeline.request_help(DEVICE, source="button")
    text = await rig.pipeline.request_help(DEVICE, source="button")
    await rig.pipeline.drain()
    assert len(rig.notifier.requests) == 1
    assert text == ALREADY_CALLED_TEXT
    assert "already been called" in text
    assert rig.tts.spoken == [HELP_CONFIRMATION_TEXT, ALREADY_CALLED_TEXT]


async def test_PL10b_emergency_not_deduped() -> None:
    """An emergency escalates even while a normal request is pending."""
    rig = make_rig()
    await rig.pipeline.request_help(DEVICE, source="button")
    await rig.pipeline.request_help(DEVICE, source="voice", emergency=True, speak=False)
    assert [r.emergency for r in rig.notifier.requests] == [False, True]


async def test_PL10c_notifier_failure() -> None:
    """Notifier raises -> help back to none, user told staff couldn't be reached."""
    rig = make_rig(notifier=FailingNotifier())
    text = await rig.pipeline.request_help(DEVICE, source="button")
    await rig.pipeline.drain()
    assert text == HELP_FAILED_TEXT
    assert rig.help() is HelpStatus.NONE
    assert rig.tts.spoken == [HELP_FAILED_TEXT]


async def test_PL11_voice_call_staff() -> None:
    """PL11: voice "call staff" -> same as PL8, no LLM call."""
    rig = make_rig(transcript="call staff please")
    await voice_turn(rig)
    assert len(rig.notifier.requests) == 1
    assert rig.notifier.requests[0].emergency is False
    assert rig.help() is HelpStatus.PENDING
    assert rig.tts.spoken == [HELP_CONFIRMATION_TEXT]
    assert rig.llm.calls == 0
    assert rig.states.led(DEVICE) == "red_pulse"
    answer = await rig.pipeline.handle_text(DEVICE, "call staff", speak=False)
    assert answer.intent is Intent.HELP and answer.text == ALREADY_CALLED_TEXT


async def test_PL12_voice_fire() -> None:
    """PL12: voice "there's a fire" -> EMERGENCY_RESPONSE, emergency=True, no LLM."""
    rig = make_rig(transcript="there's a fire")
    await voice_turn(rig)
    assert rig.tts.spoken == [EMERGENCY_RESPONSE]
    assert len(rig.notifier.requests) == 1
    assert rig.notifier.requests[0].emergency is True
    assert rig.llm.calls == 0
    assert rig.help() is HelpStatus.PENDING


async def test_PL12b_emergency_when_notifier_fails() -> None:
    rig = make_rig(notifier=FailingNotifier())
    answer = await rig.pipeline.handle_text(DEVICE, "I'm hurt", speak=False)
    assert answer.intent is Intent.EMERGENCY
    assert answer.text == f"{EMERGENCY_RESPONSE} {HELP_FAILED_TEXT}"


async def test_PL13_help_ack() -> None:
    """PL13: help_update(ack) -> acknowledged, TTS "on the way", purple."""
    rig = make_rig()
    await rig.pipeline.request_help(DEVICE, source="button")
    await rig.pipeline.help_update(DEVICE, "ack")
    await rig.pipeline.drain()
    assert rig.help() is HelpStatus.ACKNOWLEDGED
    assert rig.tts.spoken[-1] == ON_THE_WAY_TEXT
    assert "on the way" in ON_THE_WAY_TEXT
    assert rig.states.led(DEVICE) == "purple"


async def test_PL13b_ack_without_pending_ignored() -> None:
    rig = make_rig()
    await rig.pipeline.help_update(DEVICE, "ack")
    await rig.pipeline.drain()
    assert rig.help() is HelpStatus.NONE
    assert rig.tts.spoken == []


async def test_PL14_help_resolve() -> None:
    """PL14: help_update(resolve) -> help none."""
    rig = make_rig()
    await rig.pipeline.request_help(DEVICE, source="button")
    await rig.pipeline.help_update(DEVICE, "ack")
    await rig.pipeline.help_update(DEVICE, "resolve")
    await rig.pipeline.drain()
    assert rig.help() is HelpStatus.NONE
    assert rig.states.led(DEVICE) == "off"
    await rig.pipeline.request_help(DEVICE, source="button")
    assert len(rig.notifier.requests) == 2


async def test_PL15_is_someone_coming() -> None:
    """PL15: ask while pending -> system prompt has waiting status."""
    rig = make_rig()
    await rig.pipeline.request_help(DEVICE, source="button")
    answer = await rig.pipeline.handle_text(DEVICE, "is someone coming", speak=False)
    assert answer.refused is False
    assert rig.llm.last_messages is not None
    system = rig.llm.last_messages[0]["content"]
    assert "Staff status: called at 14:05, waiting." in system


async def test_PL16_llm_raises() -> None:
    """PL16: LLM raises -> error, TTS "something went wrong", no crash."""
    rig = make_rig(llm=FakeLLM("", error=RuntimeError("ollama down")))
    await voice_turn(rig)
    assert rig.activity() is Activity.ERROR
    assert rig.tts.spoken == [ERROR_TEXT]
    assert "something went wrong" in ERROR_TEXT
    assert rig.sessions.get(DEVICE).turns == []
    rig.clock.advance(3.0)
    assert rig.activity() is Activity.IDLE
    assert await rig.pipeline.talk_pressed(DEVICE) == {"accepted": True}


async def test_PL17_unknown_device() -> None:
    """PL17: unknown device -> machine all, still answers."""
    rig = make_rig()
    answer = await rig.pipeline.handle_text("mystery-99", "what is the maximum SD card size", speak=False)
    assert answer.refused is False
    assert rig.llm.last_messages is not None
    assert "at the Fab Lab (all)" in rig.llm.last_messages[0]["content"]


async def test_PL18_help_recent_questions() -> None:
    """PL18: HelpRequest.recent_questions is last 3 user questions."""
    rig = make_rig()
    for question in ["q one filament", "q two nozzle", "q three SD card", "q four PLA"]:
        await rig.pipeline.handle_text(DEVICE, question, speak=False)
    await rig.pipeline.handle_text(DEVICE, "call staff", speak=False)
    assert rig.notifier.requests[0].recent_questions == ["q two nozzle", "q three SD card", "q four PLA"]


async def test_ask_holds_device_lock_and_speaks() -> None:
    """ask() with speak -> answer spoken, activity back to idle."""
    rig = make_rig()
    answer = await rig.pipeline.ask(DEVICE, "what is the maximum SD card size", speak=True)
    assert rig.tts.spoken == [answer.text]
    assert rig.tts.activities == [Activity.SPEAKING]
    assert rig.activity() is Activity.IDLE
