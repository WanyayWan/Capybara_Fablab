"""Step-by-step procedures: which knowledge chunk is an overview or a numbered step.

A procedure is one knowledge file with a "(full procedure)" overview chunk and
"Step N: ..." chunks. The session keeps a `ProcedurePointer` (file, step) so "next" can
fetch "Step N+1" directly instead of relying on retrieval or the LLM's memory.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

OVERVIEW_MARKER = "(full procedure)"
_STEP_RE = re.compile(r"^\s*Step\s+(\d+)\s*:", re.IGNORECASE)


class ProcedureChunk(Protocol):
    file: str
    heading: str


@dataclass(frozen=True)
class ProcedurePointer:
    file: str
    step: int


def step_number(heading: str) -> int | None:
    """N for a "Step N: ..." heading, else None."""
    match = _STEP_RE.match(heading)
    return int(match.group(1)) if match else None


def is_overview(heading: str) -> bool:
    return OVERVIEW_MARKER in heading.lower()


def pointer_for(chunks: Sequence[ProcedureChunk]) -> ProcedurePointer | None:
    """The pointer for the best-ranked overview or step chunk: an overview points at
    step 1, "Step N" at N. None if no chunk belongs to a procedure."""
    for chunk in chunks:
        if is_overview(chunk.heading):
            return ProcedurePointer(chunk.file, 1)
        number = step_number(chunk.heading)
        if number is not None:
            return ProcedurePointer(chunk.file, number)
    return None
