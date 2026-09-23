"""Classify a transcribed utterance as an emergency, a staff-help request, or a question.

Pure logic: case-insensitive, whole-word regex matching. EMERGENCY is checked before
HELP, and everything else is a QUESTION ("help me load filament" is a question).
Strong triggers (injury, shock) are always EMERGENCY; fire/smoke phrases are EMERGENCY
only when the text is not hypothetical ("what do I do if there's a fire" is a question).
A transcript of only 1 to 3 bare alarm words ("Fire.", "smoke smoke") is EMERGENCY.
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


# Always EMERGENCY, even inside a question ("what if I cut myself").
STRONG_EMERGENCY_PHRASES = (
    "i'm hurt",
    "i am hurt",
    "injured",
    "bleeding",
    "cut myself",
    "burnt myself",
    "burned myself",
    "electric shock",
    "emergency",
)

# EMERGENCY only in present-tense form, and not when the text is hypothetical.
FIRE_SMOKE_PHRASES = (
    "there's a fire",
    "there is a fire",
    "on fire",
    "fire!",
    "flames",
    "there's smoke",
    "there is smoke",
    "smoke coming",
    "lots of smoke",
    "something is burning",
    "it's burning",
    "it is burning",
)

HYPOTHETICAL_MARKERS = (
    "if",
    "in case",
    "is it normal",
    "why",
    "should i",
    "how do i",
    "what happens when",
)

# A transcript made only of these words (1 to 3 of them) is a shouted alarm: EMERGENCY.
# Whisper usually transcribes a shouted "Fire!" as "Fire."
ALARM_WORDS = frozenset({"fire", "smoke", "burning", "flames", "help"})
ALARM_MAX_WORDS = 3

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
    # Lookarounds rather than \b so phrases ending in punctuation ("fire!") still match.
    alternatives = "|".join(re.escape(p).replace(r"\ ", r"\s+") for p in phrases)
    return re.compile(rf"(?<!\w)(?:{alternatives})(?!\w)", re.IGNORECASE)


_STRONG_RE = _phrase_pattern(STRONG_EMERGENCY_PHRASES)
_FIRE_SMOKE_RE = _phrase_pattern(FIRE_SMOKE_PHRASES)
_HYPOTHETICAL_RE = _phrase_pattern(HYPOTHETICAL_MARKERS)
_HELP_RE = _phrase_pattern(HELP_PHRASES)


def _is_bare_alarm(text: str) -> bool:
    """True if `text`, ignoring punctuation, is only 1 to 3 alarm words ("Fire.", "fire fire")."""
    words = re.findall(r"\w+", text.lower())
    return 1 <= len(words) <= ALARM_MAX_WORDS and all(w in ALARM_WORDS for w in words)


def detect_intent(text: str) -> Intent:
    """Return the intent of `text`, checking EMERGENCY first, then HELP, else QUESTION."""
    # STT may emit curly apostrophes ("there’s a fire").
    normalised = text.replace("\N{RIGHT SINGLE QUOTATION MARK}", "'")
    if _STRONG_RE.search(normalised) or _is_bare_alarm(normalised):
        return Intent.EMERGENCY
    if _FIRE_SMOKE_RE.search(normalised) and not _HYPOTHETICAL_RE.search(normalised):
        return Intent.EMERGENCY
    if _HELP_RE.search(normalised):
        return Intent.HELP
    return Intent.QUESTION
