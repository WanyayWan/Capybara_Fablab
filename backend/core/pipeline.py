"""Voice pipeline: button events → recording → STT → intent → RAG/LLM → TTS, plus staff help.

Depends only on the small interfaces below, so tests drive it entirely with fakes.
Blocking calls (STT, TTS) run via `asyncio.to_thread`. A per-device `asyncio.Lock`
stops a second press from starting a parallel run. Any processing exception sets
activity `error` and speaks a best-effort apology.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

import numpy as np

from config import Settings
from core.device_state import DeviceStateStore
from core.intents import Intent
from core.prompts import ContextChunk
from core.sessions import SessionManager


@dataclass
class Answer:
    text: str
    intent: Intent
    sources: list[str] = field(default_factory=list)
    refused: bool = False


@dataclass
class HelpRequest:
    device_id: str
    machine: str
    location: str
    time: datetime
    recent_questions: list[str]
    emergency: bool
    help_id: str


class ScoredChunkLike(Protocol):
    chunk: ContextChunk
    score: float


class RecorderLike(Protocol):
    @property
    def is_recording(self) -> bool: ...
    def start(self) -> None: ...
    def stop(self) -> np.ndarray: ...
    def cancel(self) -> None: ...


class STTLike(Protocol):
    def transcribe(self, samples: np.ndarray) -> str: ...


class KnowledgeBaseLike(Protocol):
    def retrieve(self, query: str, machine: str) -> Sequence[ScoredChunkLike]: ...
    def is_confident(self, results: Sequence[ScoredChunkLike]) -> bool: ...


class LLMLike(Protocol):
    def chat(self, messages: list[dict[str, str]]) -> str: ...


class TTSLike(Protocol):
    def speak(self, text: str) -> None: ...


class NotifierLike(Protocol):
    def send_help(self, request: HelpRequest) -> Awaitable[None]: ...


class UnansweredLogLike(Protocol):
    def log(self, device_id: str, machine: str, question: str, best_score: float) -> None: ...


DeviceLookup = Callable[[str], Mapping[str, str]]


class VoicePipeline:
    def __init__(
        self,
        settings: Settings,
        recorder: RecorderLike,
        stt: STTLike,
        kb: KnowledgeBaseLike,
        llm: LLMLike,
        tts: TTSLike,
        notifier: NotifierLike,
        states: DeviceStateStore,
        sessions: SessionManager,
        unanswered: UnansweredLogLike,
        devices: DeviceLookup,
    ) -> None:
        raise NotImplementedError

    async def talk_pressed(self, device_id: str) -> dict[str, object]:
        """Start recording unless busy; returns `{"accepted": bool, ...}`."""
        raise NotImplementedError

    async def talk_released(self, device_id: str, held_ms: int) -> dict[str, object]:
        """Stop recording; reject if shorter than MIN_RECORD_S, else process in the background."""
        raise NotImplementedError

    async def _process_audio(self, device_id: str, samples: np.ndarray) -> None:
        """Transcribe `samples` and hand the text to `handle_text` with speech on."""
        raise NotImplementedError

    async def handle_text(self, device_id: str, text: str, speak: bool) -> Answer:
        """Route `text` by intent (emergency, help, question) and optionally speak the answer."""
        raise NotImplementedError

    async def request_help(
        self,
        device_id: str,
        source: str,
        emergency: bool = False,
        speak: bool = True,
    ) -> str:
        """Call staff (deduped while pending) and return the confirmation text."""
        raise NotImplementedError

    async def help_update(self, device_id: str, action: str) -> None:
        """Apply a staff action: `ack` → acknowledged, `resolve` → none."""
        raise NotImplementedError
