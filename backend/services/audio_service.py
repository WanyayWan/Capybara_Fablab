from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import sounddevice as sd


@dataclass
class Recording:
    samples: np.ndarray
    sample_rate: int


class AudioService:
    """Captures one spoken request from the current Windows default microphone."""

    sample_rate = 16000
    channels = 1

    def list_input_devices(self) -> list[dict[str, object]]:
        default_input, _ = sd.default.device
        devices = []
        for index, device in enumerate(sd.query_devices()):
            if device["max_input_channels"] > 0:
                devices.append(
                    {
                        "index": index,
                        "name": device["name"],
                        "channels": int(device["max_input_channels"]),
                        "default": index == default_input,
                    }
                )
        return devices

    def record_utterance(self, duration_seconds: float = 5.0) -> Recording:
        """Record a fixed short request for the first reliable end-to-end test."""
        frames = int(self.sample_rate * duration_seconds)
        samples = sd.rec(
            frames,
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="float32",
            blocking=True,
        ).reshape(-1)
        return Recording(samples=samples, sample_rate=self.sample_rate)
