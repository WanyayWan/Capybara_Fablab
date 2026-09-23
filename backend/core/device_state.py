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


class DeviceStateStore:
    def __init__(self, clock: Callable[[], float], help_ack_clear_s: float = 600.0) -> None:
        raise NotImplementedError

    def set_activity(self, device_id: str, activity: Activity) -> None:
        raise NotImplementedError

    def set_help(self, device_id: str, status: HelpStatus) -> None:
        raise NotImplementedError

    def get(self, device_id: str) -> DeviceState:
        """Return the device's state after applying lazy expiries; unknown ids are idle."""
        raise NotImplementedError

    def led(self, device_id: str) -> str:
        """Return the LED value (`off`, `blue`, `yellow`, `green`, `red_pulse`, `purple`, `red_flash`)."""
        raise NotImplementedError
