"""core/safety.py: banned laser-cutter materials in a question (test-plan SF1-SF3)."""

import pytest

from core.safety import mentions_banned_material


@pytest.mark.parametrize(
    "question",
    [
        "Can I cut PVC on the laser cutter?",
        "Is vinyl okay to laser cut?",
        "Can I laser cut polycarbonate?",
        "what about lexan",
        "Can I engrave HDPE?",
        "Is foam fine?",
        "Can I cut fibreglass?",
        "can i cut fiberglass sheets",
        "Can I cut fibre glass?",
        "Can I cut carbon fibre?",
        "Carbon  Fiber panels?",
        "pvc.",
    ],
)
def test_SF1_banned_materials_detected(question: str) -> None:
    """SF1: every banned term, any case, British and American spellings."""
    assert mentions_banned_material(question)


@pytest.mark.parametrize(
    "question",
    [
        "Can I print with ABS?",  # ABS is a valid 3D printing filament
        "Can I cut ABS?",
        "Can I cut acrylic?",
        "What materials can I cut?",
        "How do I load filament?",
        "Can I cut plywood?",
        "What is carbon?",
        "the foamy stuff",  # whole words only
        "",
    ],
)
def test_SF2_other_questions_not_flagged(question: str) -> None:
    """SF2: ABS and ordinary materials don't trigger the safety net."""
    assert not mentions_banned_material(question)
