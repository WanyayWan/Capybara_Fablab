"""In-memory fakes for every service, so unit, pipeline and API tests need no hardware,
network, or models. See docs/test-plan.md "Test fakes".
"""

from __future__ import annotations

import re
import zlib

import numpy as np

from core.pipeline import HelpRequest

_WORD = re.compile(r"[a-z0-9]+")
_STOPWORDS = frozenset(
    "a an the i can do does is are how what where which when of to for my me on in it and or with".split()
)


class FakeClock:
    """Manual clock: `now()` returns the current time, `advance(s)` moves it forward."""

    def __init__(self, start: float = 0.0) -> None:
        self._now = start

    def now(self) -> float:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now += seconds


class FakeEmbedder:
    """Bag-of-words hashing: lowercase words minus stopwords, CRC32-hashed into 4096 dims,
    L2-normalised rows. Tuned for low collisions; real retrieval quality is judged with
    the real embedder (build-plan section 9). No nomic prefixes: those belong to
    OllamaEmbedder. `calls` records the raw texts of every call."""

    dims = 4096

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        self.calls.append(list(texts))
        return self._vectors(texts)

    def embed_query(self, text: str) -> np.ndarray:
        self.calls.append([text])
        return self._vectors([text])[0]

    def _vectors(self, texts: list[str]) -> np.ndarray:
        vectors = np.zeros((len(texts), self.dims), dtype=np.float32)
        for row, text in enumerate(texts):
            for word in _WORD.findall(text.lower()):
                if word in _STOPWORDS:
                    continue
                vectors[row, zlib.crc32(word.encode("utf-8")) % self.dims] += 1.0
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        return vectors / np.where(norms == 0, 1.0, norms)


class FakeSTT:
    """Returns a fixed transcript and records every call."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.calls: list[np.ndarray] = []

    def transcribe(self, samples: np.ndarray) -> str:
        self.calls.append(samples)
        return self.text


class FakeLLM:
    """Returns a fixed reply (or raises `error` if set) and stores the last messages."""

    def __init__(self, reply: str, error: Exception | None = None) -> None:
        self.reply = reply
        self.error = error
        self.calls = 0
        self.last_messages: list[dict[str, str]] | None = None

    def chat(self, messages: list[dict[str, str]]) -> str:
        self.calls += 1
        self.last_messages = messages
        if self.error is not None:
            raise self.error
        return self.reply


class FakeTTS:
    """Records spoken strings; never blocks."""

    def __init__(self) -> None:
        self.spoken: list[str] = []

    def speak(self, text: str) -> None:
        self.spoken.append(text)


class FakeNotifier:
    """Records every HelpRequest it is asked to send."""

    def __init__(self) -> None:
        self.requests: list[HelpRequest] = []

    async def send_help(self, request: HelpRequest) -> None:
        self.requests.append(request)


class FakeRecorder:
    """start/stop/cancel with a controllable recorded duration. `pre_roll_samples` is how
    much of `samples` counts as pre-roll (reported via `last_pre_roll_samples`)."""

    def __init__(self, samples: np.ndarray, sample_rate: int = 16000) -> None:
        self.samples = samples
        self.sample_rate = sample_rate
        self.pre_roll_samples = 0
        self.last_pre_roll_samples = 0
        self.start_calls = 0
        self.cancel_calls = 0
        self._recording = False

    @property
    def is_recording(self) -> bool:
        return self._recording

    def start(self) -> None:
        self.start_calls += 1
        self.last_pre_roll_samples = min(self.pre_roll_samples, self.samples.size)
        self._recording = True

    def stop(self) -> np.ndarray:
        was_recording = self._recording
        self._recording = False
        return self.samples if was_recording else np.zeros(0, dtype=np.float32)

    def cancel(self) -> None:
        self.cancel_calls += 1
        self._recording = False


class FakeUnansweredLog:
    """In-memory list of logged questions."""

    def __init__(self) -> None:
        self.entries: list[dict[str, object]] = []

    def log(self, device_id: str, machine: str, question: str, best_score: float) -> None:
        self.entries.append(
            {
                "device_id": device_id,
                "machine": machine,
                "question": question,
                "best_score": best_score,
            }
        )

    def read_all(self) -> list[dict[str, object]]:
        return list(self.entries)
