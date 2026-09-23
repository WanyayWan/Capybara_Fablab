from __future__ import annotations

from faster_whisper import WhisperModel

from services.audio_service import Recording


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
