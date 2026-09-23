"""Voice pipeline with fakes and FakeClock (test-plan: test_pipeline.py)."""

import pytest


@pytest.mark.skip(reason="not implemented")
def test_PL1_full_turn() -> None:
    """PL1: press, release 2 s -> listening, thinking, speaking, idle; 1 session turn."""


@pytest.mark.skip(reason="not implemented")
def test_PL2_too_short() -> None:
    """PL2: release after 0.2 s -> too_short, idle, STT not called."""


@pytest.mark.skip(reason="not implemented")
def test_PL3_empty_transcript() -> None:
    """PL3: STT "" -> TTS "didn't catch that", no LLM call."""


@pytest.mark.skip(reason="not implemented")
def test_PL4_busy_while_thinking() -> None:
    """PL4: press while thinking -> accepted False, reason busy."""


@pytest.mark.skip(reason="not implemented")
def test_PL5_refuse_no_confident_chunk() -> None:
    """PL5: no confident chunk -> refusal, refused, logged, no LLM."""


@pytest.mark.skip(reason="not implemented")
def test_PL6_follow_up_query_combined() -> None:
    """PL6: follow-up retrieval query contains both questions."""


@pytest.mark.skip(reason="not implemented")
def test_PL7_next_uses_history() -> None:
    """PL7: "next" -> LLM receives history with the previous step."""


@pytest.mark.skip(reason="not implemented")
def test_PL8_help_event() -> None:
    """PL8: help_requested -> notifier once, pending, TTS confirmation, red_pulse."""


@pytest.mark.skip(reason="not implemented")
def test_PL9_help_cancels_recording() -> None:
    """PL9: help while recording -> recorder cancelled."""


@pytest.mark.skip(reason="not implemented")
def test_PL10_help_deduped() -> None:
    """PL10: second help while pending -> notifier once, "already been called"."""


@pytest.mark.skip(reason="not implemented")
def test_PL11_voice_call_staff() -> None:
    """PL11: voice "call staff" -> same as PL8, no LLM call."""


@pytest.mark.skip(reason="not implemented")
def test_PL12_voice_fire() -> None:
    """PL12: voice "there's a fire" -> EMERGENCY_RESPONSE, emergency=True, no LLM."""


@pytest.mark.skip(reason="not implemented")
def test_PL13_help_ack() -> None:
    """PL13: help_update(ack) -> acknowledged, TTS "on the way", purple."""


@pytest.mark.skip(reason="not implemented")
def test_PL14_help_resolve() -> None:
    """PL14: help_update(resolve) -> help none."""


@pytest.mark.skip(reason="not implemented")
def test_PL15_is_someone_coming() -> None:
    """PL15: ask while pending -> system prompt has waiting status."""


@pytest.mark.skip(reason="not implemented")
def test_PL16_llm_raises() -> None:
    """PL16: LLM raises -> error, TTS "something went wrong", no crash."""


@pytest.mark.skip(reason="not implemented")
def test_PL17_unknown_device() -> None:
    """PL17: unknown device -> machine all, still answers."""


@pytest.mark.skip(reason="not implemented")
def test_PL18_help_recent_questions() -> None:
    """PL18: HelpRequest.recent_questions is last 3 user questions."""
