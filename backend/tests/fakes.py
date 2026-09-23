"""In-memory fakes for every service, so unit, pipeline and API tests need no hardware,
network, or models. See docs/test-plan.md "Test fakes".
"""

from __future__ import annotations

import numpy as np

from core.pipeline import HelpRequest


class FakeClock:
    """Manual clock: `now()` returns the current time, `advance(s)` moves it forward."""

    def __init__(self, start: float = 0.0) -> None:
        self._now = start

    def now(self) -> float:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now += seconds


class FakeEmbedder:
    """Bag-of-words hashing: lowercase words hashed into 256 dims, L2-normalised rows."""

    dims = 256

    def embed(self, texts: list[str]) -> np.ndarray:
        raise NotImplementedError


class FakeSTT:
    """Returns a fixed transcript and records every call."""

    def __init__(self, text: str) -> None:
        raise NotImplementedError

    def transcribe(self, samples: np.ndarray) -> str:
        raise NotImplementedError


class FakeLLM:
    """Returns a fixed reply (or raises `error` if set) and stores the last messages."""

    def __init__(self, reply: str, error: Exception | None = None) -> None:
        raise NotImplementedError

    def chat(self, messages: list[dict[str, str]]) -> str:
        raise NotImplementedError


class FakeTTS:
    """Records spoken strings; never blocks."""

    def __init__(self) -> None:
        raise NotImplementedError

    def speak(self, text: str) -> None:
        raise NotImplementedError


class FakeNotifier:
    """Records every HelpRequest it is asked to send."""

    def __init__(self) -> None:
        raise NotImplementedError

    async def send_help(self, request: HelpRequest) -> None:
        raise NotImplementedError


class FakeRecorder:
    """start/stop/cancel with a controllable recorded duration."""

    def __init__(self, samples: np.ndarray, sample_rate: int = 16000) -> None:
        raise NotImplementedError

    @property
    def is_recording(self) -> bool:
        raise NotImplementedError

    def start(self) -> None:
        raise NotImplementedError

    def stop(self) -> np.ndarray:
        raise NotImplementedError

    def cancel(self) -> None:
        raise NotImplementedError


class FakeUnansweredLog:
    """In-memory list of logged questions."""

    def __init__(self) -> None:
        raise NotImplementedError

    def log(self, device_id: str, machine: str, question: str, best_score: float) -> None:
        raise NotImplementedError

    def read_all(self) -> list[dict[str, object]]:
        raise NotImplementedError
