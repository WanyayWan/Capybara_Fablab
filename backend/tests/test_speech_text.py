"""Text sanitising for TTS (test-plan: test_speech_text.py)."""

import pytest


@pytest.mark.skip(reason="not implemented")
def test_T1_strip_markdown() -> None:
    """T1: "**Press** the `button`" -> "Press the button"."""


@pytest.mark.skip(reason="not implemented")
def test_T2_bullets_one_line() -> None:
    """T2: "- step one\n- step two" -> no dashes, one line."""


@pytest.mark.skip(reason="not implemented")
def test_T3_expand_eg() -> None:
    """T3: "e.g. PLA" -> "for example PLA"."""


@pytest.mark.skip(reason="not implemented")
def test_T4_cut_at_sentence() -> None:
    """T4: 1,000-char text -> <= 600 chars, ends at a sentence boundary."""


@pytest.mark.skip(reason="not implemented")
def test_T5_numbers_kept() -> None:
    """T5: "32 GB" -> numbers kept."""
