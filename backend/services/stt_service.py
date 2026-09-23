"""Speech to text with faster-whisper, loaded lazily on first use (CPU, int8).

Synchronous; callers run it via `asyncio.to_thread`. The glossary is passed as the
initial prompt so Fab Lab terms are spelled correctly.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

import numpy as np

GLOSSARY = (
    "Fab Lab, SUTD, PLA, PETG, ABS, AMS, Bambu, P1S, X1E, SD card, filament, nozzle, "
    "build plate, laser cutter, acrylic, plywood, MDF, kerf, engrave, extraction"
)

ModelFactory = Callable[[str], Any]


def _load_whisper(model_name: str) -> Any:
    from faster_whisper import WhisperModel

    return WhisperModel(model_name, device="cpu", compute_type="int8")


class WhisperSTT:
    def __init__(self, model_name: str, model_factory: ModelFactory = _load_whisper) -> None:
        self.model_name = model_name
        self._model_factory = model_factory
        self._model: Any = None
        self._lock = threading.Lock()

    def load(self) -> None:
        """Load the model now (e.g. at startup) instead of on the first question."""
        with self._lock:
            if self._model is None:
                self._model = self._model_factory(self.model_name)

    def transcribe(self, samples: np.ndarray) -> str:
        """Transcribe 16 kHz mono float32 samples; empty input gives ""."""
        if samples.size == 0:
            return ""
        self.load()
        segments, _ = self._model.transcribe(
            samples,
            language="en",
            beam_size=5,
            vad_filter=True,
            initial_prompt=GLOSSARY,
        )
        return " ".join(s.text.strip() for s in segments if s.text.strip()).strip()
