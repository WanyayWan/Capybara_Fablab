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
    LAST_STEP_TEXT,
    NO_ANSWER,
    ON_THE_WAY_TEXT,
    REFUSAL_TEXT,
    WHAT_HELP_TEXT,
    VoicePipeline,
)
from core.sessions import SessionManager
from core.steps import ProcedurePointer
from services.knowledge import KnowledgeBase, knowledge_dirs, load_chunks
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
# Written as a model ignoring the prompt would: the pipeline strips the source naming and
# "Say next", then re-adds them itself (top chunk's spoken_source, pointer set).
LLM_REPLY = "According to the 3D printer guide, first heat the nozzle. Say next when you're ready."
# LLM_REPLY for a question whose top chunk is not a step (no pointer, no "Say next").
SD_ANSWER = "According to the 3D printer guide, first heat the nozzle."


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
    threshold: float = TEST_THRESHOLD,
) -> Rig:
    clock = FakeClock(1000.0)
    states = DeviceStateStore(clock.now)
    sessions = SessionManager(timeout_s=120, max_turns=6, clock=clock.now)
    embedder = FakeEmbedder()
    kb = KnowledgeBase(
        load_chunks(knowledge_dirs(KNOWLEDGE_ROOT)),
        embedder,
        top_k=3,
        threshold=threshold,
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
    assert answer.text == SD_ANSWER
    assert answer.sources
    origins = [s["origin"] for s in answer.sources]
    assert len(origins) == len(set(origins))
    printer_guide = {
        "spoken_source": "the 3D printer guide",
        "origin": 'Fab Lab posted sign "Hands-On" (3D printing area)',
    }
    assert printer_guide in answer.sources
    assert answer.best_score is not None and answer.best_score >= TEST_THRESHOLD
    assert rig.unanswered.entries == []


async def test_PL5c_llm_no_answer_refused() -> None:
    """PL5c: confident retrieval but the LLM replies NO_ANSWER -> normal refusal, refused,
    logged as unanswered, and NO_ANSWER is never spoken or stored."""
    rig = make_rig(transcript="what is the maximum SD card size", llm=FakeLLM(" NO_ANSWER\n"))
    await voice_turn(rig)
    assert rig.llm.calls == 1
    assert rig.tts.spoken == [REFUSAL_TEXT]
    assert [e["question"] for e in rig.unanswered.entries] == ["what is the maximum SD card size"]
    turn = rig.sessions.get(DEVICE).turns[-1]
    assert turn.assistant == REFUSAL_TEXT and NO_ANSWER not in turn.assistant
    answer = await rig.pipeline.handle_text(DEVICE, "what is the maximum SD card size", speak=False)
    assert answer.refused is True and answer.text == REFUSAL_TEXT and answer.sources == []
    assert answer.best_score is not None and answer.best_score >= TEST_THRESHOLD


async def test_PL5d_llm_no_answer_while_help_pending() -> None:
    """PL5d: NO_ANSWER while staff are called -> "not in the guides" + staff status."""
    rig = make_rig(llm=FakeLLM("NO_ANSWER"))
    await rig.pipeline.request_help(DEVICE, source="button", speak=False)
    answer = await rig.pipeline.handle_text(DEVICE, "what is the maximum SD card size", speak=False)
    assert answer.refused is True
    assert answer.text == (
        "Sorry, I don't have that in the Fab Lab guides. "
        "Staff were called at 14:05 and should be with you shortly."
    )
    assert NO_ANSWER not in answer.text
    assert len(rig.unanswered.entries) == 1


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
    """PL7: "next" without a step pointer -> LLM receives history with the previous step;
    never refused. NEXT retrieves with the last question alone and skips the gate."""
    rig = make_rig()
    first = await rig.pipeline.handle_text(DEVICE, "how do I load filament", speak=False)
    assert first.refused is False
    rig.sessions.get(DEVICE).procedure = None  # no pointer: the pre-step-mode behaviour
    answer = await rig.pipeline.handle_text(DEVICE, "Next.", speak=False)
    assert answer.refused is False
    assert answer.intent is Intent.NEXT
    assert answer.text == "First heat the nozzle."  # NEXT: no source prefix, no pointer
    assert answer.sources
    assert rig.embedder.calls[-1] == ["how do I load filament"]
    messages = rig.llm.last_messages
    assert messages is not None
    assert messages[1:] == [
        {"role": "user", "content": "how do I load filament"},
        {"role": "assistant", "content": LLM_REPLY},
        {"role": "user", "content": "Next."},
    ]
    assert "Step 2: How do I load filament?" in messages[0]["content"]
    assert [t.user for t in rig.sessions.get(DEVICE).turns] == ["how do I load filament", "next"]


async def test_PL7a_second_next_still_uses_the_question() -> None:
    """A second "next" retrieves with the original question, not with "next"."""
    rig = make_rig()
    await rig.pipeline.handle_text(DEVICE, "how do I load filament", speak=False)
    rig.sessions.get(DEVICE).procedure = None
    await rig.pipeline.handle_text(DEVICE, "next", speak=False)
    answer = await rig.pipeline.handle_text(DEVICE, "go on", speak=False)
    assert answer.refused is False and rig.llm.calls == 3
    assert rig.embedder.calls[-1] == ["how do I load filament"]
    assert rig.unanswered.entries == []


STEP_THRESHOLD = 0.3  # FakeEmbedder scores "How do I use the 3D printer?" at ~0.36


def context_of(rig: Rig) -> list[str]:
    """The CONTEXT lines of the last LLM call's system prompt."""
    assert rig.llm.last_messages is not None
    return rig.llm.last_messages[0]["content"].split("CONTEXT:\n", 1)[1].splitlines()


OVERVIEW_QUESTION = "How do I use the 3D printer full procedure"  # overview ranks top (fake)


async def test_PL7c_overview_then_next_walks_steps() -> None:
    """PL7c: overview question -> LLM answers from the overview with the step prompt;
    pointer at step 0 and no Step 1 chunk added. Each "next" then speaks the next step
    verbatim, with no retrieval and no LLM call."""
    rig = make_rig(threshold=STEP_THRESHOLD)
    session = rig.sessions.get(DEVICE)
    await rig.pipeline.handle_text(DEVICE, OVERVIEW_QUESTION, speak=False)
    assert session.procedure == ProcedurePointer("3d-printer", 0)
    context = context_of(rig)
    assert "(full procedure)" in context[0]
    assert not any("] Step 1:" in line for line in context)
    assert rig.llm.last_messages is not None
    assert "include every action in the step" in rig.llm.last_messages[0]["content"]
    embed_calls, llm_calls = len(rig.embedder.calls), rig.llm.calls

    answer = await rig.pipeline.handle_text(DEVICE, "next", speak=False)
    assert answer.intent is Intent.NEXT and answer.refused is False
    assert session.procedure == ProcedurePointer("3d-printer", 1)
    assert [s["spoken_source"] for s in answer.sources] == ["the 3D printer guide"]
    assert len(rig.embedder.calls) == embed_calls  # no retrieval in step mode
    assert rig.llm.calls == llm_calls  # no LLM in step mode


async def test_PL7g_overview_next_next_next_speaks_steps_1_2_3() -> None:
    """PL7g: overview -> next -> next -> next speaks steps 1, 2, 3 of 3d-printer.md in
    order, each verbatim."""
    rig = make_rig(threshold=STEP_THRESHOLD)
    await rig.pipeline.handle_text(DEVICE, OVERVIEW_QUESTION, speak=False)
    kb = rig.pipeline.kb
    for step in (1, 2, 3):
        chunk = kb.step_chunk("3d-printer", step)
        assert chunk is not None
        answer = await rig.pipeline.handle_text(DEVICE, "next", speak=False)
        assert answer.text == f"Step {step}. {chunk.text} Say next when you're ready."
    assert [t.assistant.split(".")[0] for t in rig.sessions.get(DEVICE).turns[1:]] == [
        "Step 1",
        "Step 2",
        "Step 3",
    ]
    assert rig.llm.calls == 1


async def test_PL7d_next_after_last_step() -> None:
    """PL7d: "next" after the last step -> "That was the last step. Anything else?",
    no LLM call; the pointer stays so another "next" says the same."""
    rig = make_rig(threshold=STEP_THRESHOLD)
    await rig.pipeline.handle_text(DEVICE, "How do I remove my print?", speak=False)
    session = rig.sessions.get(DEVICE)
    assert session.procedure == ProcedurePointer("3d-printer", 5)  # Step 5 ranks top
    step6 = await rig.pipeline.handle_text(DEVICE, "next", speak=False)
    assert step6.text.startswith("Step 6. Take the build plate off")
    answer = await rig.pipeline.handle_text(DEVICE, "next", speak=False)
    assert answer.text == LAST_STEP_TEXT and answer.refused is False
    assert rig.llm.calls == 1
    assert (await rig.pipeline.handle_text(DEVICE, "go on", speak=False)).text == LAST_STEP_TEXT
    assert session.turns[-1].user == "next" and session.turns[-1].assistant == LAST_STEP_TEXT


async def test_PL7e_new_question_clears_pointer() -> None:
    """PL7e: a new question clears the pointer; one whose top chunk isn't a step leaves
    it empty, and a refused one does too."""
    rig = make_rig(threshold=STEP_THRESHOLD)
    session = rig.sessions.get(DEVICE)
    await rig.pipeline.handle_text(DEVICE, OVERVIEW_QUESTION, speak=False)
    assert session.procedure is not None
    await rig.pipeline.handle_text(DEVICE, "Where is the Fab Lab?", speak=False)
    assert session.procedure is None

    rig = make_rig(threshold=STEP_THRESHOLD)  # fresh: follow-ups combine with the last question
    session = rig.sessions.get(DEVICE)
    await rig.pipeline.handle_text(DEVICE, OVERVIEW_QUESTION, speak=False)
    assert session.procedure is not None
    rig.llm.reply = NO_ANSWER  # merged with the overview question it passes the low filter
    refused = await rig.pipeline.handle_text(DEVICE, "best pizza", speak=False)
    assert refused.refused is True and session.procedure is None


async def test_PL7f_pointer_only_from_top_chunk() -> None:
    """PL7f: "max SD card size" also retrieves "Step 4: Where do I insert the SD card?"
    lower down, but the top chunk isn't a step: no pointer, normal-length prompt."""
    rig = make_rig()
    answer = await rig.pipeline.handle_text(DEVICE, "what is the maximum SD card size", speak=False)
    assert any("Step 4:" in line for line in context_of(rig))
    assert rig.sessions.get(DEVICE).procedure is None
    assert rig.llm.last_messages is not None
    system = rig.llm.last_messages[0]["content"]
    assert "1 to 3 short sentences" in system and "include every action" not in system
    assert answer.refused is False


async def test_PL6c_refused_question_not_merged() -> None:
    """PL6c: a follow-up after a refused question is retrieved on its own."""
    rig = make_rig()
    first = await rig.pipeline.handle_text(DEVICE, "best pizza", speak=False)
    assert first.refused is True
    await rig.pipeline.handle_text(DEVICE, "what is the maximum SD card size", speak=False)
    assert rig.embedder.calls[-1] == ["what is the maximum SD card size"]


async def test_PL6d_refused_by_llm_not_merged() -> None:
    """Same when the refusal came from the LLM's NO_ANSWER."""
    rig = make_rig(llm=FakeLLM(NO_ANSWER))
    await rig.pipeline.handle_text(DEVICE, "what is the maximum SD card size", speak=False)
    rig.llm.reply = LLM_REPLY
    await rig.pipeline.handle_text(DEVICE, "how do I load filament", speak=False)
    assert rig.embedder.calls[-1] == ["how do I load filament"]


async def test_PL7b_next_without_history() -> None:
    """PL7b: NEXT with no history -> "What would you like help with?", no LLM call."""
    rig = make_rig(transcript="next")
    await voice_turn(rig)
    assert rig.tts.spoken == [WHAT_HELP_TEXT]
    assert rig.llm.calls == 0
    assert rig.sessions.get(DEVICE).turns == []
    assert rig.unanswered.entries == []


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
    """PL15: "is someone coming" while pending, nothing in the guides -> deterministic
    "not in the guides" + staff status, spoken; logged as unanswered; no LLM call."""
    rig = make_rig(transcript="is someone coming")
    await rig.pipeline.request_help(DEVICE, source="button", speak=False)
    await voice_turn(rig)
    expected = (
        "Sorry, I don't have that in the Fab Lab guides. "
        "Staff were called at 14:05 and should be with you shortly."
    )
    assert rig.tts.spoken == [expected]
    assert rig.llm.calls == 0
    assert [e["question"] for e in rig.unanswered.entries] == ["is someone coming"]


async def test_PL15b_pending_unconfident_question_no_llm() -> None:
    """PL15b: while pending, "what power for acrylic" with no confident chunk -> LLM not called."""
    rig = make_rig()
    await rig.pipeline.request_help(DEVICE, source="button", speak=False)
    answer = await rig.pipeline.handle_text(DEVICE, "what power for acrylic", speak=False)
    assert rig.llm.calls == 0
    assert answer.refused is True
    assert answer.text.endswith("Staff were called at 14:05 and should be with you shortly.")
    assert rig.unanswered.entries[0]["question"] == "what power for acrylic"


async def test_PL15c_acknowledged_status_reply() -> None:
    rig = make_rig()
    await rig.pipeline.request_help(DEVICE, source="button", speak=False)
    await rig.pipeline.help_update(DEVICE, "ack")
    answer = await rig.pipeline.handle_text(DEVICE, "is someone coming", speak=False)
    await rig.pipeline.drain()
    assert answer.text == (
        "Sorry, I don't have that in the Fab Lab guides. "
        "Staff were called at 14:05 and are on the way."
    )
    assert rig.llm.calls == 0


async def test_PL15d_confident_question_while_pending_has_status() -> None:
    """A confident question while pending still reaches the LLM with the staff status."""
    rig = make_rig()
    await rig.pipeline.request_help(DEVICE, source="button", speak=False)
    await rig.pipeline.handle_text(DEVICE, "what is the maximum SD card size", speak=False)
    assert rig.llm.last_messages is not None
    assert "Staff status: called at 14:05, waiting." in rig.llm.last_messages[0]["content"]


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


async def test_stage_timings_logged(caplog) -> None:  # type: ignore[no-untyped-def]
    """Latency diagnosis: each answered question logs retrieval and LLM durations."""
    caplog.set_level("INFO", logger="core.pipeline")
    rig = make_rig()
    await rig.pipeline.handle_text(DEVICE, "what is the maximum SD card size", speak=False)
    messages = [r.getMessage() for r in caplog.records if r.name == "core.pipeline"]
    assert any("retrieval" in m and " s" in m for m in messages)
    assert any("LLM call" in m for m in messages)


async def test_PL19_llm_own_refusal_treated_as_no_answer() -> None:
    """PL19: a reply opening with "I don't have information" (no NO_ANSWER) is refused,
    logged and replaced by the normal refusal, like NO_ANSWER."""
    reply = "I don't have information about the cost of SLS printing. The lab has SLS printers."
    rig = make_rig(llm=FakeLLM(reply))
    answer = await rig.pipeline.handle_text(DEVICE, "what is the maximum SD card size", speak=False)
    assert answer.refused is True and answer.text == REFUSAL_TEXT and answer.sources == []
    assert [e["question"] for e in rig.unanswered.entries] == ["what is the maximum SD card size"]
    assert rig.sessions.get(DEVICE).turns[-1].assistant == REFUSAL_TEXT


async def test_PL20_source_prefix_from_top_chunk() -> None:
    """PL20: the model names the wrong guide; the answer is prefixed with the top chunk's
    spoken_source instead."""
    rig = make_rig(llm=FakeLLM("According to the 3D printer guide, no. PVC releases chlorine."), threshold=0.3)
    answer = await rig.pipeline.handle_text("fabai-02", "can I cut PVC", speak=False)
    assert context_of(rig)[0].startswith("[the laser cutter guide]")
    assert answer.text == "According to the laser cutter guide, no. PVC releases chlorine."


async def test_PL21_say_next_only_with_pointer() -> None:
    """PL21: "Say next" is appended when the answer sets the step pointer, even if the
    model left it out, and stripped when it doesn't (PL5b)."""
    rig = make_rig(llm=FakeLLM("First check you are trained."), threshold=STEP_THRESHOLD)
    answer = await rig.pipeline.handle_text(DEVICE, OVERVIEW_QUESTION, speak=False)
    assert rig.sessions.get(DEVICE).procedure is not None
    assert answer.text.endswith("first check you are trained. Say next when you're ready.")
    assert answer.text.startswith("According to ")
