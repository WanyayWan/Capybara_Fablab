"""Recorder with always-open stream and pre-roll (test-plan: test_audio_service.py)."""

import pytest


@pytest.mark.skip(reason="not implemented")
def test_A1_one_second_16000_samples() -> None:
    """A1: start, feed 1 s, stop -> 16000 samples."""


@pytest.mark.skip(reason="not implemented")
def test_A2_truncated_at_max() -> None:
    """A2: feed beyond max_seconds -> truncated at max."""


@pytest.mark.skip(reason="not implemented")
def test_A3_cancel_returns_empty() -> None:
    """A3: cancel -> stop returns empty array, not recording."""


@pytest.mark.skip(reason="not implemented")
def test_A4_stop_without_start() -> None:
    """A4: stop without start -> empty array, no error."""


@pytest.mark.skip(reason="not implemented")
def test_A5_pre_roll_seeds_recording() -> None:
    """A5: 1 s before start + 1 s after -> 24000 samples, first 8000 are pre-roll."""
