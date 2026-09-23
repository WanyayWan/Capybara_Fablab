"""Per-device conversation sessions with a turn limit and an inactivity timeout.

A session expires after `timeout_s` with no activity; `get` then returns a fresh one.
`procedure` is the step-mode pointer (knowledge file + current step), or None.
The clock is injected so tests can advance time without sleeping.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field

from core.steps import ProcedurePointer


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
    procedure: ProcedurePointer | None = None
    clock: Callable[[], float] = field(default=time.monotonic, repr=False, compare=False)

    def add_turn(self, user: str, assistant: str) -> None:
        """Append a turn, keeping only the last `max_turns` turns."""
        self.turns.append(Turn(user, assistant))
        del self.turns[: -self.max_turns]
        self.last_active = self.clock()

    def last_user_messages(self, n: int) -> list[str]:
        """Return the last `n` user texts, oldest first (newest last)."""
        if n <= 0:
            return []
        return [turn.user for turn in self.turns[-n:]]

    def history_messages(self, last_turns: int | None = None) -> list[dict[str, str]]:
        """Return the turns (or only the last `last_turns`) in chat format: alternating
        user/assistant role dicts."""
        turns = self.turns if last_turns is None else self.turns[max(0, len(self.turns) - last_turns) :]
        messages: list[dict[str, str]] = []
        for turn in turns:
            messages.append({"role": "user", "content": turn.user})
            messages.append({"role": "assistant", "content": turn.assistant})
        return messages


class SessionManager:
    def __init__(
        self,
        timeout_s: float,
        max_turns: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._timeout_s = timeout_s
        self._max_turns = max_turns
        self._clock = clock
        self._sessions: dict[str, Session] = {}

    def get(self, device_id: str) -> Session:
        """Return the device's session, creating a new one if missing or expired.

        Getting a session counts as activity and refreshes its timeout.
        """
        now = self._clock()
        session = self._sessions.get(device_id)
        if session is None or now - session.last_active >= self._timeout_s:
            session = Session(device_id, self._max_turns, now, clock=self._clock)
            self._sessions[device_id] = session
        session.last_active = now
        return session

    def reset(self, device_id: str) -> None:
        """Drop the device's session so the next `get` starts fresh."""
        self._sessions.pop(device_id, None)
