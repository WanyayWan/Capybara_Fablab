"""Device state and LED values (test-plan: test_device_state.py)."""

import pytest


@pytest.mark.skip(reason="not implemented")
def test_D1_new_device_off() -> None:
    """D1: new device -> off."""


@pytest.mark.skip(reason="not implemented")
def test_D2_activity_colours() -> None:
    """D2: listening/thinking/speaking -> blue/yellow/green."""


@pytest.mark.skip(reason="not implemented")
def test_D3_help_pending_idle_red_pulse() -> None:
    """D3: help pending, idle -> red_pulse."""


@pytest.mark.skip(reason="not implemented")
def test_D4_activity_beats_help() -> None:
    """D4: help pending, listening -> blue."""


@pytest.mark.skip(reason="not implemented")
def test_D5_acknowledged_purple() -> None:
    """D5: help acknowledged, idle -> purple."""


@pytest.mark.skip(reason="not implemented")
def test_D6_error_flash_then_off() -> None:
    """D6: activity error -> red_flash; after 3 s -> off."""


@pytest.mark.skip(reason="not implemented")
def test_D7_acknowledged_clears_after_timeout() -> None:
    """D7: acknowledged, advance 601 s -> help none, off."""


@pytest.mark.skip(reason="not implemented")
def test_D8_unknown_device_off() -> None:
    """D8: unknown device id -> off without error."""
