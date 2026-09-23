"""Procedure step parsing and pointers (core/steps.py)."""

from dataclasses import dataclass

from core.steps import ProcedurePointer, is_overview, pointer_for, step_number, step_reply


@dataclass
class Chunk:
    file: str
    heading: str


def test_step_number() -> None:
    assert step_number("Step 2: How do I load filament?") == 2
    assert step_number("step 12:  Something") == 12
    assert step_number("How do I use the 3D printer? (full procedure)") is None
    assert step_number("What is the maximum SD card size?") is None


def test_is_overview() -> None:
    assert is_overview("How do I use the laser cutter? (full procedure)")
    assert not is_overview("Step 1: Am I allowed to use the laser cutter?")


def test_pointer_overview_points_at_step_1() -> None:
    chunks = [Chunk("3d-printer", "How do I use it? (full procedure)"), Chunk("general", "Where is the Fab Lab?")]
    assert pointer_for(chunks) == ProcedurePointer("3d-printer", 1)


def test_step_reply_is_chunk_text_verbatim() -> None:
    text = "Open the AMS cover.  Push the grey tab,\nthen insert the filament."
    assert step_reply(2, text) == (
        "Step 2. Open the AMS cover. Push the grey tab, then insert the filament. "
        "Say next when you're ready."
    )


def test_pointer_only_from_top_ranked_chunk() -> None:
    """A step chunk below the top result never sets the pointer."""
    chunks = [
        Chunk("3d-printer", "What filament types are supported?"),
        Chunk("3d-printer", "Step 2: How do I load filament?"),
    ]
    assert pointer_for(chunks) is None
    assert pointer_for(chunks[1:]) == ProcedurePointer("3d-printer", 2)


def test_pointer_none_without_procedure_chunks() -> None:
    assert pointer_for([Chunk("general", "Where is the Fab Lab?")]) is None
    assert pointer_for([]) is None
