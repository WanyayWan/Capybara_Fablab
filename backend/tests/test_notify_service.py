"""Staff notifications (test-plan: test_notify_service.py)."""

import pytest


@pytest.mark.skip(reason="not implemented")
def test_N1_format_normal() -> None:
    """N1: contains device, machine, location, time, questions."""


@pytest.mark.skip(reason="not implemented")
def test_N2_format_emergency() -> None:
    """N2: message starts with EMERGENCY."""


@pytest.mark.skip(reason="not implemented")
def test_N3_format_no_questions() -> None:
    """N3: no recent questions -> "no questions yet"."""


@pytest.mark.skip(reason="not implemented")
def test_N4_parse_callback_ack() -> None:
    """N4: parse_callback("ack:fabai-01:abc") -> ("ack", "fabai-01", "abc")."""


@pytest.mark.skip(reason="not implemented")
def test_N5_parse_callback_garbage() -> None:
    """N5: parse_callback("garbage") -> None."""


@pytest.mark.skip(reason="not implemented")
def test_N6_console_without_token() -> None:
    """N6: create_notifier without token -> ConsoleNotifier."""


@pytest.mark.skip(reason="not implemented")
def test_N7_telegram_send_help() -> None:
    """N7: send_help posts sendMessage with chat_id and 2 inline buttons."""
