"""Classify a transcribed utterance as an emergency, a staff-help request, or a question.

Pure logic: case-insensitive, word-boundary regex matching. EMERGENCY is checked before
HELP, and everything else is a QUESTION ("help me load filament" is a question).
"""

from __future__ import annotations

from enum import Enum


class Intent(str, Enum):
    EMERGENCY = "emergency"
    HELP = "help"
    QUESTION = "question"


EMERGENCY_RESPONSE = (
    "Stop the machine if it is safe to do so, and move away. "
    "I'm alerting Fab Lab staff now."
)


def detect_intent(text: str) -> Intent:
    """Return the intent of `text`, checking EMERGENCY first, then HELP, else QUESTION."""
    raise NotImplementedError
