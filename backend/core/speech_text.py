"""Turn LLM output into text that sounds right when spoken by TTS.

Strips markdown (`*`, `#`, backticks, bullets), collapses whitespace, expands "e.g." to
"for example", keeps numbers, and cuts to at most `max_chars` at a sentence boundary.
"""

from __future__ import annotations

MAX_SPEAKABLE_CHARS = 600


def to_speakable(text: str, max_chars: int = MAX_SPEAKABLE_CHARS) -> str:
    """Return `text` cleaned for speech and no longer than `max_chars`."""
    raise NotImplementedError
