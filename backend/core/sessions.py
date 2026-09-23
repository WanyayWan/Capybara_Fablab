"""Per-device conversation sessions with a turn limit and an inactivity timeout.

A session expires after `timeout_s` with no activity; `get` then returns a fresh one.
The clock is injected so tests can advance time without sleeping.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass
class Turn:
    user: str
    assistant: str


@dataclass
class Session:
    device_id: str
    max_turns: int
    last_active: float
    turns: list[Turn] = field(default_factory=list)

    def add_turn(self, user: str, assistant: str) -> None:
        """Append a turn, keeping only the last `max_turns` turns."""
        raise NotImplementedError

    def last_user_messages(self, n: int) -> list[str]:
        """Return the last `n` user texts, oldest first (newest last)."""
        raise NotImplementedError

    def history_messages(self) -> list[dict[str, str]]:
        """Return the turns in chat format: alternating user/assistant role dicts."""
        raise NotImplementedError


class SessionManager:
    def __init__(
        self,
        timeout_s: float,
        max_turns: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        raise NotImplementedError

    def get(self, device_id: str) -> Session:
        """Return the device's session, creating a new one if missing or expired."""
        raise NotImplementedError

    def reset(self, device_id: str) -> None:
        """Drop the device's session so the next `get` starts fresh."""
        raise NotImplementedError
