"""Conversation sessions (test-plan: test_sessions.py)."""

import pytest


@pytest.mark.skip(reason="not implemented")
def test_S1_new_device_empty_history() -> None:
    """S1: new device -> empty history."""


@pytest.mark.skip(reason="not implemented")
def test_S2_two_turns_four_messages() -> None:
    """S2: add 2 turns -> history has 4 messages in order."""


@pytest.mark.skip(reason="not implemented")
def test_S3_max_turns_kept() -> None:
    """S3: add 8 turns with max 6 -> only last 6 kept."""


@pytest.mark.skip(reason="not implemented")
def test_S4_expires_after_timeout() -> None:
    """S4: advance clock 121 s -> get returns a fresh empty session."""


@pytest.mark.skip(reason="not implemented")
def test_S5_activity_refreshes_timeout() -> None:
    """S5: advance 60 s, add turn, advance 60 s -> still alive."""


@pytest.mark.skip(reason="not implemented")
def test_S6_devices_independent() -> None:
    """S6: two devices -> histories independent."""


@pytest.mark.skip(reason="not implemented")
def test_S7_last_user_messages() -> None:
    """S7: last_user_messages(3) -> last 3 user texts, newest last."""
