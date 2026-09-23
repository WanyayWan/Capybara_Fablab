"""HTTP API with aiohttp test client and fakes (test-plan: test_api.py)."""

import pytest


@pytest.mark.skip(reason="not implemented")
def test_API1_health() -> None:
    """API1: GET /health -> 200, status ok."""


@pytest.mark.skip(reason="not implemented")
def test_API2_register() -> None:
    """API2: POST /api/device/register fabai-01 -> machine 3d-printer."""


@pytest.mark.skip(reason="not implemented")
def test_API3_event_talk_pressed() -> None:
    """API3: POST /api/device/event talk_pressed -> 202, accepted."""


@pytest.mark.skip(reason="not implemented")
def test_API4_event_unknown() -> None:
    """API4: unknown event -> 400."""


@pytest.mark.skip(reason="not implemented")
def test_API5_event_invalid_json() -> None:
    """API5: invalid JSON -> 400."""


@pytest.mark.skip(reason="not implemented")
def test_API6_state() -> None:
    """API6: GET /api/device/state?device_id=fabai-01 -> activity, help, led."""


@pytest.mark.skip(reason="not implemented")
def test_API7_state_missing_device_id() -> None:
    """API7: GET /api/device/state without device_id -> 400."""


@pytest.mark.skip(reason="not implemented")
def test_API8_ask_valid() -> None:
    """API8: POST /api/ask -> 200 with text, intent, sources, refused."""


@pytest.mark.skip(reason="not implemented")
def test_API9_ask_invalid_length() -> None:
    """API9: empty or 2001 chars -> 400."""


@pytest.mark.skip(reason="not implemented")
def test_API10_help_ack() -> None:
    """API10: POST /api/help/ack ack -> acknowledged."""


@pytest.mark.skip(reason="not implemented")
def test_API11_unanswered_after_refusal() -> None:
    """API11: GET /api/unanswered after refusal -> 1 entry."""


@pytest.mark.skip(reason="not implemented")
def test_API12_help_event_then_state() -> None:
    """API12: help_requested then state -> red_pulse."""
