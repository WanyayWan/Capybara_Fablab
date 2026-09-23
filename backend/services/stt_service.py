from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from faster_whisper import WhisperModel
from vosk import KaldiRecognizer, Model

from services.audio_service import Recording


class STTService:
    """Offline Vosk implementation. Swap this class for another provider later."""

    def __init__(self, model_path: Path) -> None:
        if not model_path.is_dir():
            raise RuntimeError(f"Vosk model not found: {model_path}")
        self.model = Model(str(model_path))

    def transcribe(self, recording: Recording) -> str:
        if recording.samples.size == 0:
            return ""
        recognizer = KaldiRecognizer(self.model, recording.sample_rate)
        pcm = np.clip(recording.samples * 32767, -32768, 32767).astype(np.int16).tobytes()
        recognizer.AcceptWaveform(pcm)
        result = json.loads(recognizer.FinalResult())
        return result.get("text", "").strip()


class WhisperSTTService:
    """Local Faster-Whisper provider used for higher-accuracy English transcription."""

    def __init__(self) -> None:
        self.model = WhisperModel("base.en", device="cpu", compute_type="int8")

    def transcribe(self, recording: Recording) -> str:
        if recording.samples.size == 0:
            return ""
        segments, _ = self.model.transcribe(
            recording.samples,
            language="en",
            beam_size=5,
            vad_filter=True,
        )
        return " ".join(segment.text.strip() for segment in segments).strip()

    def transcribe_file(self, audio_path: str) -> str:
        """Transcribe a browser-recorded audio container such as WebM or MP4."""
        segments, _ = self.model.transcribe(
            audio_path,
            language="en",
            beam_size=5,
            vad_filter=True,
        )
        return " ".join(segment.text.strip() for segment in segments).strip()
