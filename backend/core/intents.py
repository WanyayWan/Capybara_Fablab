"""Classify a transcribed utterance as an emergency, a staff-help request, or a question.

Pure logic: case-insensitive, word-boundary regex matching. EMERGENCY is checked before
HELP, and everything else is a QUESTION ("help me load filament" is a question).
"""

from __future__ import annotations

import re
from enum import Enum


class Intent(str, Enum):
    EMERGENCY = "emergency"
    HELP = "help"
    QUESTION = "question"


EMERGENCY_RESPONSE = (
    "Stop the machine if it is safe to do so, and move away. "
    "I'm alerting Fab Lab staff now."
)


EMERGENCY_PHRASES = (
    "fire",
    "on fire",
    "flames",
    "smoke",
    "burning",
    "burnt myself",
    "burned myself",
    "injured",
    "bleeding",
    "cut myself",
    "i'm hurt",
    "i am hurt",
    "emergency",
    "electric shock",
)

HELP_PHRASES = (
    "call staff",
    "call a staff",
    "get staff",
    "need staff",
    "talk to staff",
    "call someone",
    "call for help",
    "get a staff",
    "staff please",
)


def _phrase_pattern(phrases: tuple[str, ...]) -> re.Pattern[str]:
    alternatives = "|".join(re.escape(p).replace(r"\ ", r"\s+") for p in phrases)
    return re.compile(rf"\b(?:{alternatives})\b", re.IGNORECASE)


_EMERGENCY_RE = _phrase_pattern(EMERGENCY_PHRASES)
_HELP_RE = _phrase_pattern(HELP_PHRASES)


def detect_intent(text: str) -> Intent:
    """Return the intent of `text`, checking EMERGENCY first, then HELP, else QUESTION."""
    normalised = text.replace("’", "'")  # STT may emit curly apostrophes
    if _EMERGENCY_RE.search(normalised):
        return Intent.EMERGENCY
    if _HELP_RE.search(normalised):
        return Intent.HELP
    return Intent.QUESTION
