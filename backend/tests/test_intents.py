"""Intent detection (test-plan: test_intents.py)."""

import pytest


@pytest.mark.skip(reason="not implemented")
def test_I1_fire_in_laser_cutter() -> None:
    """I1: "There's a fire in the laser cutter" -> EMERGENCY."""


@pytest.mark.skip(reason="not implemented")
def test_I2_cut_myself() -> None:
    """I2: "I cut myself" -> EMERGENCY."""


@pytest.mark.skip(reason="not implemented")
def test_I3_material_on_fire() -> None:
    """I3: "the material is on fire" -> EMERGENCY."""


@pytest.mark.skip(reason="not implemented")
def test_I4_please_call_staff() -> None:
    """I4: "please call staff" -> HELP."""


@pytest.mark.skip(reason="not implemented")
def test_I5_i_need_staff() -> None:
    """I5: "I need staff" -> HELP."""


@pytest.mark.skip(reason="not implemented")
def test_I6_call_someone_caps() -> None:
    """I6: "CALL SOMEONE" -> HELP."""


@pytest.mark.skip(reason="not implemented")
def test_I7_help_me_load_filament() -> None:
    """I7: "can you help me load filament" -> QUESTION."""


@pytest.mark.skip(reason="not implemented")
def test_I8_how_do_i_cut_acrylic() -> None:
    """I8: "how do I cut acrylic" -> QUESTION (no "cut myself")."""


@pytest.mark.skip(reason="not implemented")
def test_I9_what_does_help_button_do() -> None:
    """I9: "what does the help button do" -> QUESTION."""


@pytest.mark.skip(reason="not implemented")
def test_I10_emergency_wins_over_help() -> None:
    """I10: "fire! call staff" -> EMERGENCY."""


@pytest.mark.skip(reason="not implemented")
def test_I11_empty_text() -> None:
    """I11: "" -> QUESTION."""
