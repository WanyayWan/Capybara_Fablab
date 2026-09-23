"""Per-device activity and staff-help status, and the LED value derived from them.

LED values and priority follow build-plan section 2: activity (listening, thinking,
speaking, error) overrides help colours; when idle, the help colour shows. `error`
reverts to `idle` after 3 s and `acknowledged` reverts to `none` after
`help_ack_clear_s`, both checked lazily on read.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum


class Activity(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    ERROR = "error"


class HelpStatus(str, Enum):
    NONE = "none"
    PENDING = "pending"
    ACKNOWLEDGED = "acknowledged"


ERROR_REVERT_S = 3.0


@dataclass
class DeviceState:
    activity: Activity = Activity.IDLE
    help: HelpStatus = HelpStatus.NONE
    activity_since: float = 0.0
    help_since: float = 0.0


_ACTIVITY_LED = {
    Activity.LISTENING: "blue",
    Activity.THINKING: "yellow",
    Activity.SPEAKING: "green",
    Activity.ERROR: "red_flash",
}

_HELP_LED = {
    HelpStatus.NONE: "off",
    HelpStatus.PENDING: "red_pulse",
    HelpStatus.ACKNOWLEDGED: "purple",
}


class DeviceStateStore:
    def __init__(self, clock: Callable[[], float], help_ack_clear_s: float = 600.0) -> None:
        self._clock = clock
        self._help_ack_clear_s = help_ack_clear_s
        self._states: dict[str, DeviceState] = {}

    def _state(self, device_id: str) -> DeviceState:
        return self._states.setdefault(device_id, DeviceState())

    def set_activity(self, device_id: str, activity: Activity) -> None:
        state = self._state(device_id)
        state.activity = activity
        state.activity_since = self._clock()

    def set_help(self, device_id: str, status: HelpStatus) -> None:
        state = self._state(device_id)
        state.help = status
        state.help_since = self._clock()

    def get(self, device_id: str) -> DeviceState:
        """Return the device's state after applying lazy expiries; unknown ids are idle."""
        state = self._states.get(device_id)
        if state is None:
            return DeviceState()  # not stored, so polling unknown ids cannot grow memory
        now = self._clock()
        if state.activity is Activity.ERROR and now - state.activity_since >= ERROR_REVERT_S:
            state.activity = Activity.IDLE
            state.activity_since = now
        if (
            state.help is HelpStatus.ACKNOWLEDGED
            and now - state.help_since >= self._help_ack_clear_s
        ):
            state.help = HelpStatus.NONE
            state.help_since = now
        return state

    def led(self, device_id: str) -> str:
        """Return the LED value (`off`, `blue`, `yellow`, `green`, `red_pulse`, `purple`, `red_flash`)."""
        state = self.get(device_id)
        if state.activity is not Activity.IDLE:
            return _ACTIVITY_LED[state.activity]
        return _HELP_LED[state.help]
