"""Hold-to-talk recording from the laptop's default microphone.

The input stream is opened once (`open()`) and stays open, so Bluetooth headsets don't
switch profile on every question. While idle, the stream callback keeps the last
`pre_roll_s` seconds in a ring buffer; `start()` seeds the recording with it, covering
button-to-HTTP latency and the first syllable. `max_seconds` caps the total including
pre-roll. Audio is mono float32.
"""

from __future__ import annotations

import threading
from collections import deque
from collections.abc import Callable
from typing import Any

import numpy as np

StreamFactory = Callable[..., Any]
BLOCKSIZE = 800  # 50 ms at 16 kHz


def _empty() -> np.ndarray:
    return np.zeros(0, dtype=np.float32)


def list_input_devices() -> list[dict[str, object]]:
    """Input devices known to PortAudio, flagging the system default."""
    import sounddevice as sd

    default_input, _ = sd.default.device
    return [
        {
            "index": index,
            "name": device["name"],
            "channels": int(device["max_input_channels"]),
            "default": index == default_input,
        }
        for index, device in enumerate(sd.query_devices())
        if device["max_input_channels"] > 0
    ]


class Recorder:
    def __init__(
        self,
        sample_rate: int = 16000,
        max_seconds: float = 15.0,
        pre_roll_s: float = 0.5,
        stream_factory: StreamFactory | None = None,
    ) -> None:
        self.sample_rate = sample_rate
        self.max_samples = int(max_seconds * sample_rate)
        self.pre_roll_max = int(pre_roll_s * sample_rate)
        self.last_pre_roll_samples = 0
        self.level = 0.0
        self._stream_factory = stream_factory
        self._stream: Any = None
        self._lock = threading.Lock()
        self._ring: deque[np.ndarray] = deque()
        self._ring_len = 0
        self._chunks: list[np.ndarray] = []
        self._length = 0
        self._recording = False

    @property
    def is_recording(self) -> bool:
        return self._recording

    def open(self) -> None:
        """Open and start the input stream once; later calls do nothing."""
        if self._stream is not None:
            return
        factory = self._stream_factory
        if factory is None:
            import sounddevice as sd

            factory = sd.InputStream
        self._stream = factory(
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
            blocksize=BLOCKSIZE,
            callback=self._callback,
        )
        self._stream.start()

    def close(self) -> None:
        if self._stream is None:
            return
        self._stream.stop()
        self._stream.close()
        self._stream = None

    def start(self) -> None:
        """Begin a recording, seeded with the pre-roll buffer."""
        with self._lock:
            # the ring is only fed when pre_roll_max > 0, so the slice below is safe
            pre_roll = np.concatenate(self._ring)[-self.pre_roll_max :] if self._ring_len else _empty()
            pre_roll = pre_roll[-self.max_samples :] if self.max_samples else _empty()
            self._chunks = [pre_roll] if pre_roll.size else []
            self._length = pre_roll.size
            self.last_pre_roll_samples = int(pre_roll.size)
            self._recording = True

    def stop(self) -> np.ndarray:
        """End the recording and return its samples (empty if not recording)."""
        with self._lock:
            if not self._recording:
                return _empty()
            self._recording = False
            samples = np.concatenate(self._chunks) if self._chunks else _empty()
            self._chunks, self._length = [], 0
            return samples

    def cancel(self) -> None:
        """Discard the current recording."""
        with self._lock:
            self._recording = False
            self._chunks, self._length = [], 0

    def _callback(self, indata: np.ndarray, frames: int, time_info: object, status: object) -> None:
        self._on_audio(indata)

    def _on_audio(self, chunk: np.ndarray) -> None:
        """Take one block from the stream: feed the pre-roll ring and any active recording."""
        mono = np.asarray(chunk, dtype=np.float32).reshape(len(chunk), -1)[:, 0].copy()
        if mono.size:
            self.level = float(np.sqrt(np.mean(np.square(mono))))
        with self._lock:
            self._push_ring(mono)
            if self._recording and self._length < self.max_samples:
                part = mono[: self.max_samples - self._length]
                self._chunks.append(part)
                self._length += part.size

    def _push_ring(self, mono: np.ndarray) -> None:
        if self.pre_roll_max == 0:
            return
        self._ring.append(mono)
        self._ring_len += mono.size
        while self._ring and self._ring_len - self._ring[0].size >= self.pre_roll_max:
            self._ring_len -= self._ring.popleft().size
