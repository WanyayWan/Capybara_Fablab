"""Turn LLM output into text that sounds right when spoken by TTS.

Strips markdown (`*`, `#`, backticks, bullets), collapses whitespace, expands "e.g." to
"for example", keeps numbers, and cuts to at most `max_chars` at a sentence boundary.
"""

from __future__ import annotations

import re

MAX_SPEAKABLE_CHARS = 600

_EG_RE = re.compile(r"\be\.g\.", re.IGNORECASE)
_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]*\)")
_HEADING_RE = re.compile(r"^\s*#{1,6}\s*")
_BULLET_RE = re.compile(r"^\s*[-*+•]\s+")
_NUMBERED_RE = re.compile(r"^\s*\d+[.)]\s+")
_EMPHASIS_RE = re.compile(r"\*+|__|`+")
_SENTENCE_END_RE = re.compile(r"[.!?](?=\s|$)")


def _clean_line(line: str) -> str:
    """Strip heading and bullet markers; end list items and headings with a full stop.

    Numbered items keep their number ("1. Heat the nozzle.") since numbers are spoken.
    """
    marker = _HEADING_RE.match(line) or _BULLET_RE.match(line)
    is_list_item = bool(marker or _NUMBERED_RE.match(line))
    line = _EMPHASIS_RE.sub("", line[marker.end() :] if marker else line).strip()
    if is_list_item and line and line[-1] not in ".!?:;,":
        line += "."  # so TTS pauses between list items instead of running them together
    return line


def _truncate(text: str, max_chars: int) -> str:
    """Cut `text` to at most `max_chars`, at the last sentence end if there is one."""
    if len(text) <= max_chars:
        return text
    head = text[:max_chars]
    ends = [m.end() for m in _SENTENCE_END_RE.finditer(head)]
    if ends:
        return head[: ends[-1]]
    return head.rsplit(" ", 1)[0].rstrip(",;:") if " " in head else head


def to_speakable(text: str, max_chars: int = MAX_SPEAKABLE_CHARS) -> str:
    """Return `text` cleaned for speech and no longer than `max_chars`."""
    text = _EG_RE.sub("for example", text)
    text = _LINK_RE.sub(r"\1", text)
    lines = (_clean_line(line) for line in text.splitlines())
    text = " ".join(line for line in lines if line)
    text = re.sub(r"\s+", " ", text).strip()
    return _truncate(text, max_chars)
