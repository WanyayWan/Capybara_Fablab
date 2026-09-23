"""Device state and LED values (test-plan: test_device_state.py)."""

import pytest

from core.device_state import Activity, DeviceStateStore, HelpStatus
from tests.fakes import FakeClock


def make_store(clock: FakeClock) -> DeviceStateStore:
    return DeviceStateStore(clock=clock.now, help_ack_clear_s=600.0)


def test_D1_new_device_off() -> None:
    """D1: new device -> off."""
    store = make_store(FakeClock())
    store.set_activity("fabai-01", Activity.IDLE)
    assert store.led("fabai-01") == "off"


@pytest.mark.parametrize(
    ("activity", "led"),
    [
        (Activity.LISTENING, "blue"),
        (Activity.THINKING, "yellow"),
        (Activity.SPEAKING, "green"),
    ],
)
def test_D2_activity_colours(activity: Activity, led: str) -> None:
    """D2: listening/thinking/speaking -> blue/yellow/green."""
    store = make_store(FakeClock())
    store.set_activity("fabai-01", activity)
    assert store.led("fabai-01") == led


def test_D3_help_pending_idle_red_pulse() -> None:
    """D3: help pending, idle -> red_pulse."""
    store = make_store(FakeClock())
    store.set_help("fabai-01", HelpStatus.PENDING)
    assert store.led("fabai-01") == "red_pulse"


def test_D4_activity_beats_help() -> None:
    """D4: help pending, listening -> blue; back to idle -> red_pulse again."""
    store = make_store(FakeClock())
    store.set_help("fabai-01", HelpStatus.PENDING)
    store.set_activity("fabai-01", Activity.LISTENING)
    assert store.led("fabai-01") == "blue"
    store.set_activity("fabai-01", Activity.IDLE)
    assert store.led("fabai-01") == "red_pulse"


def test_D5_acknowledged_purple() -> None:
    """D5: help acknowledged, idle -> purple."""
    store = make_store(FakeClock())
    store.set_help("fabai-01", HelpStatus.ACKNOWLEDGED)
    assert store.led("fabai-01") == "purple"


def test_D6_error_flash_then_off() -> None:
    """D6: activity error -> red_flash; after 3 s -> off."""
    clock = FakeClock()
    store = make_store(clock)
    store.set_activity("fabai-01", Activity.ERROR)
    assert store.led("fabai-01") == "red_flash"
    clock.advance(2.9)
    assert store.led("fabai-01") == "red_flash"
    clock.advance(0.1)
    assert store.led("fabai-01") == "off"
    assert store.get("fabai-01").activity is Activity.IDLE


def test_D7_acknowledged_clears_after_timeout() -> None:
    """D7: acknowledged, advance 601 s -> help none, off."""
    clock = FakeClock()
    store = make_store(clock)
    store.set_help("fabai-01", HelpStatus.ACKNOWLEDGED)
    clock.advance(601)
    assert store.get("fabai-01").help is HelpStatus.NONE
    assert store.led("fabai-01") == "off"


def test_D7b_pending_has_no_timeout() -> None:
    """Only acknowledged help clears on a timer; pending stays until acted on."""
    clock = FakeClock()
    store = make_store(clock)
    store.set_help("fabai-01", HelpStatus.PENDING)
    clock.advance(10_000)
    assert store.led("fabai-01") == "red_pulse"


def test_D8_unknown_device_off() -> None:
    """D8: unknown device id -> off without error."""
    store = make_store(FakeClock())
    assert store.led("nope") == "off"
    state = store.get("nope")
    assert state.activity is Activity.IDLE
    assert state.help is HelpStatus.NONE
