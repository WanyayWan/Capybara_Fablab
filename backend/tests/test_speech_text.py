"""Text sanitising for TTS (test-plan: test_speech_text.py)."""

from core.speech_text import to_speakable


def test_T1_strip_markdown() -> None:
    """T1: "**Press** the `button`" -> "Press the button"."""
    assert to_speakable("**Press** the `button`") == "Press the button"


def test_T1b_strip_headings() -> None:
    """Heading markers are removed and the heading becomes its own sentence."""
    assert to_speakable("## Loading filament\nHeat the nozzle.") == (
        "Loading filament. Heat the nozzle."
    )


def test_T2_bullets_one_line() -> None:
    """T2: "- step one\n- step two" -> no dashes, one line."""
    result = to_speakable("- step one\n- step two")
    assert "-" not in result
    assert "\n" not in result
    assert "step one" in result
    assert "step two" in result


def test_T3_expand_eg() -> None:
    """T3: "e.g. PLA" -> "for example PLA"."""
    assert to_speakable("e.g. PLA") == "for example PLA"


def test_T4_cut_at_sentence() -> None:
    """T4: 1,000-char text -> <= 600 chars, ends at a sentence boundary."""
    sentence = "The nozzle must reach temperature before you load filament. "
    text = sentence * (1000 // len(sentence) + 1)
    assert len(text) >= 1000
    result = to_speakable(text)
    assert len(result) <= 600
    assert result.endswith(".")
    assert text.startswith(result)


def test_T5_numbers_kept() -> None:
    """T5: "32 GB" -> numbers kept."""
    assert to_speakable("Use up to 32 GB, at 0.4 mm.") == "Use up to 32 GB, at 0.4 mm."


def test_T6_numbered_lines_pause() -> None:
    """T6: numbered list lines keep their numbers and get a sentence pause like bullets."""
    assert to_speakable("1. Heat the nozzle\n2) Load the filament") == (
        "1. Heat the nozzle. 2) Load the filament."
    )
