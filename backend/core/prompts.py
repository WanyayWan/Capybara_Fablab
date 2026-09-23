"""Build the chat messages sent to the LLM: system prompt, history, and new question.

The system prompt carries the rules from build-plan section 5 (answer only from
CONTEXT, 1-3 spoken sentences, one step at a time, never authorise), the device's
machine and location, the staff help status, and CONTEXT as `[source] heading: text`.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from core.device_state import HelpStatus


class ContextChunk(Protocol):
    source: str
    heading: str
    text: str


SYSTEM_TEMPLATE = """\
You are FabAI, the voice assistant at the SUTD Fab Lab, at the {location} ({machine}).

Rules:
- Answer ONLY from CONTEXT. If CONTEXT does not answer the question, say you don't have \
that in the Fab Lab guides and suggest calling staff: double-press the button or say \
"call staff".
- Reply in 1 to 3 short sentences in a natural spoken style. No lists, no markdown, no emoji.
- Mention the source guide name naturally, for example "According to the 3D printer guide...".
- For procedures, give ONE step at a time and end with "Say next when you're ready." \
When the user says "next", give the following step based on the conversation so far.
- Never say someone is authorised to use a machine.
- If the user asks whether staff are coming, answer from the staff status below.

{staff_status}

CONTEXT:
{context}"""


def staff_status_line(help_status: HelpStatus, help_called_at: datetime | None = None) -> str:
    """Return the "Staff status: ..." line for the system prompt."""
    if help_status is HelpStatus.PENDING:
        called = f"called at {help_called_at:%H:%M}" if help_called_at else "called"
        return f"Staff status: {called}, waiting."
    if help_status is HelpStatus.ACKNOWLEDGED:
        return "Staff status: on the way."
    return "Staff status: not called."


def format_context(chunks: Sequence[ContextChunk]) -> str:
    """Return one `[source] heading: text` line per chunk."""
    if not chunks:
        return "(no matching guide sections)"
    return "\n".join(f"[{c.source}] {c.heading}: {c.text}" for c in chunks)


def build_messages(
    machine: str,
    location: str,
    chunks: Sequence[ContextChunk],
    history: list[dict[str, str]],
    question: str,
    help_status: HelpStatus,
    help_called_at: datetime | None = None,
) -> list[dict[str, str]]:
    """Return `[system, *history, user]` chat messages for the LLM."""
    system = SYSTEM_TEMPLATE.format(
        location=location,
        machine=machine,
        staff_status=staff_status_line(help_status, help_called_at),
        context=format_context(chunks),
    )
    return [
        {"role": "system", "content": system},
        *history,
        {"role": "user", "content": question},
    ]
