"""Step-by-step procedures: which knowledge chunk is an overview or a numbered step.

A procedure is one knowledge file with a "(full procedure)" overview chunk and
"Step N: ..." chunks. The session keeps a `ProcedurePointer` (file, step) so "next" can
fetch "Step N+1" directly and speak its text as written ("Step N. <text> Say next when
you're ready."), with no retrieval and no LLM call.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

OVERVIEW_MARKER = "(full procedure)"
SAY_NEXT_TEXT = "Say next when you're ready."
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
    """The pointer if the TOP-ranked chunk is a procedure overview (-> step 0, so the
    first "next" reads Step 1) or a "Step N" chunk (-> N). Lower-ranked step chunks
    never set it."""
    if not chunks:
        return None
    top = chunks[0]
    if is_overview(top.heading):
        return ProcedurePointer(top.file, 0)
    number = step_number(top.heading)
    return ProcedurePointer(top.file, number) if number is not None else None


def step_reply(number: int, text: str) -> str:
    """The spoken step-mode reply: "Step N. <chunk text> Say next when you're ready."."""
    return f"Step {number}. {' '.join(text.split())} {SAY_NEXT_TEXT}"
