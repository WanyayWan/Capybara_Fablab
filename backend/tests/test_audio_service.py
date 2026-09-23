"""Recorder with always-open stream and pre-roll (test-plan: test_audio_service.py)."""

import numpy as np

from services.audio_service import Recorder

RATE = 16000
CHUNK = 800  # 50 ms, like the real stream blocksize


def feed(recorder: Recorder, seconds: float, start_value: float = 0.0) -> np.ndarray:
    """Feed `seconds` of audio in CHUNK-sized (frames, 1) blocks; return what was fed."""
    total = int(seconds * RATE)
    data = (start_value + np.arange(total, dtype=np.float32)).astype(np.float32)
    for i in range(0, total, CHUNK):
        recorder._on_audio(data[i : i + CHUNK].reshape(-1, 1))
    return data


def make_recorder(max_seconds: float = 15.0, pre_roll_s: float = 0.0) -> Recorder:
    return Recorder(sample_rate=RATE, max_seconds=max_seconds, pre_roll_s=pre_roll_s)


def test_A1_one_second_16000_samples() -> None:
    """A1: start, feed 1 s, stop -> 16000 samples."""
    recorder = make_recorder()
    recorder.start()
    assert recorder.is_recording
    fed = feed(recorder, 1.0)
    samples = recorder.stop()
    assert samples.shape == (16000,)
    assert samples.dtype == np.float32
    np.testing.assert_array_equal(samples, fed)
    assert not recorder.is_recording


def test_A2_truncated_at_max() -> None:
    """A2: feed beyond max_seconds -> truncated at max."""
    recorder = make_recorder(max_seconds=1.0)
    recorder.start()
    fed = feed(recorder, 2.5)
    samples = recorder.stop()
    assert len(samples) == 16000
    np.testing.assert_array_equal(samples, fed[:16000])


def test_A3_cancel_returns_empty() -> None:
    """A3: cancel -> stop returns empty array, not recording."""
    recorder = make_recorder()
    recorder.start()
    feed(recorder, 1.0)
    recorder.cancel()
    assert not recorder.is_recording
    assert recorder.stop().size == 0


def test_A4_stop_without_start() -> None:
    """A4: stop without start -> empty array, no error."""
    recorder = make_recorder()
    samples = recorder.stop()
    assert samples.size == 0
    assert samples.dtype == np.float32


def test_A5_pre_roll_seeds_recording() -> None:
    """A5: 1 s before start + 1 s after -> 24000 samples, first 8000 are pre-roll."""
    recorder = make_recorder(pre_roll_s=0.5)
    before = feed(recorder, 1.0)
    recorder.start()
    after = feed(recorder, 1.0, start_value=100000.0)
    samples = recorder.stop()
    assert len(samples) == 24000
    np.testing.assert_array_equal(samples[:8000], before[-8000:])
    np.testing.assert_array_equal(samples[8000:], after)
    assert recorder.last_pre_roll_samples == 8000


def test_pre_roll_counts_toward_max() -> None:
    """max_seconds applies to the total including pre-roll (build-plan 9.3)."""
    recorder = make_recorder(max_seconds=1.0, pre_roll_s=0.5)
    feed(recorder, 1.0)
    recorder.start()
    feed(recorder, 2.0)
    assert len(recorder.stop()) == 16000


def test_second_recording_does_not_reuse_first() -> None:
    recorder = make_recorder(pre_roll_s=0.5)
    recorder.start()
    feed(recorder, 1.0)
    recorder.stop()
    recorder.start()
    feed(recorder, 0.25)
    # pre-roll is the last 0.5 s of the first recording's audio, then 0.25 s new
    assert len(recorder.stop()) == 12000


def test_open_uses_stream_factory_once() -> None:
    """The stream is opened once (always-open mic) with 16 kHz mono float32."""
    created: list[dict[str, object]] = []

    class FakeStream:
        def __init__(self, **kwargs: object) -> None:
            created.append(kwargs)
            self.started = False
            self.closed = False

        def start(self) -> None:
            self.started = True

        def stop(self) -> None:
            self.started = False

        def close(self) -> None:
            self.closed = True

    recorder = Recorder(sample_rate=RATE, max_seconds=15.0, pre_roll_s=0.5, stream_factory=FakeStream)
    recorder.open()
    recorder.open()
    assert len(created) == 1
    assert created[0]["samplerate"] == RATE
    assert created[0]["channels"] == 1
    assert created[0]["dtype"] == "float32"
    callback = created[0]["callback"]
    recorder.start()
    callback(np.ones((CHUNK, 1), dtype=np.float32), CHUNK, None, None)  # type: ignore[operator]
    assert len(recorder.stop()) == CHUNK
    recorder.close()
