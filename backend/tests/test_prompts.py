"""Prompt building (test-plan: test_prompts.py)."""

import pytest


@pytest.mark.skip(reason="not implemented")
def test_P1_chunks_in_system() -> None:
    """P1: system message contains each [source] heading."""


@pytest.mark.skip(reason="not implemented")
def test_P2_history_between_system_and_question() -> None:
    """P2: history between system and new question."""


@pytest.mark.skip(reason="not implemented")
def test_P3_help_pending_status() -> None:
    """P3: help pending -> system contains "called" and "waiting"."""


@pytest.mark.skip(reason="not implemented")
def test_P4_help_acknowledged_status() -> None:
    """P4: help acknowledged -> system contains "on the way"."""


@pytest.mark.skip(reason="not implemented")
def test_P5_machine_and_location() -> None:
    """P5: machine + location appear in system message."""


@pytest.mark.skip(reason="not implemented")
def test_P6_rules_present() -> None:
    """P6: system mentions one step at a time and never authorising."""
