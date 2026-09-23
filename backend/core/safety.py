"""Safety net for materials that must never go in the laser cutter.

Retrieval can miss the "What materials are banned?" chunk for some wordings ("Can I cut
PVC on the laser cutter?"), and the model then guesses. If a question names a banned
material (pvc, vinyl, polycarbonate, lexan, hdpe, foam, fibreglass / fiberglass, carbon
fibre / fiber), the pipeline always puts that chunk first in CONTEXT, on every device.
ABS is deliberately not listed: it is a valid 3D printing filament.
"""

from __future__ import annotations

import re

BANNED_CHUNK_FILE = "laser-cutter"
BANNED_CHUNK_HEADING = "What materials are banned?"

_BANNED = re.compile(
    r"\b(?:pvc|vinyl|polycarbonate|lexan|hdpe|foam|fib(?:re|er)\s*glass|carbon\s+fib(?:re|er))s?\b",
    re.IGNORECASE,
)


def mentions_banned_material(text: str) -> bool:
    """True if `text` names a banned laser-cutter material (whole words, any case)."""
    return _BANNED.search(text) is not None
