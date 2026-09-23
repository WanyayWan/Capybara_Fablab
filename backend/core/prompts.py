"""Build the chat messages sent to the LLM: system prompt, history, and new question.

The system prompt carries the rules from build-plan section 5 (answer only from
CONTEXT or reply NO_ANSWER, 1-3 spoken sentences, one step at a time, never authorise,
no source names: the pipeline adds "According to ..."), the device's machine and location, the staff help status, and CONTEXT as
`[spoken_source] heading: text` (the spoken guide name, e.g. "the 3D printer guide").
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from core.device_state import HelpStatus


class ContextChunk(Protocol):
    spoken_source: str
    origin: str
    heading: str
    text: str
    file: str


SYSTEM_TEMPLATE = """\
You are FabAI, the voice assistant at the SUTD Fab Lab, at the {location} ({machine}).

Rules:
- Answer ONLY from CONTEXT. If CONTEXT does not answer this exact question, even if \
related facts exist, reply with exactly NO_ANSWER and nothing else.
- State only facts from CONTEXT. Never add details that are not in CONTEXT.
- {length_rule} No lists, no markdown, no emoji.
- Do not mention sources or guide names.
- For procedures, give ONE step at a time. When the user says "next", give the \
following step based on the conversation so far.
- Never say someone is authorised to use a machine.
- If the user asks whether staff are coming, answer from the staff status below.

{staff_status}

CONTEXT:
{context}"""


LENGTH_RULE = "Reply in 1 to 3 short sentences in a natural spoken style."
STEP_LENGTH_RULE = (
    "Reply in a natural spoken style, up to 5 sentences for step instructions, and "
    "include every action in the step."
)


def staff_status_line(help_status: HelpStatus, help_called_at: datetime | None = None) -> str:
    """Return the "Staff status: ..." line for the system prompt."""
    if help_status is HelpStatus.PENDING:
        called = f"called at {help_called_at:%H:%M}" if help_called_at else "called"
        return f"Staff status: {called}, waiting."
    if help_status is HelpStatus.ACKNOWLEDGED:
        return "Staff status: on the way."
    return "Staff status: not called."


def format_context(chunks: Sequence[ContextChunk]) -> str:
    """Return one `[spoken_source] heading: text` line per chunk."""
    if not chunks:
        return "(no matching guide sections)"
    return "\n".join(f"[{c.spoken_source}] {c.heading}: {c.text}" for c in chunks)


def build_messages(
    machine: str,
    location: str,
    chunks: Sequence[ContextChunk],
    history: list[dict[str, str]],
    question: str,
    help_status: HelpStatus,
    help_called_at: datetime | None = None,
    step_answer: bool = False,
) -> list[dict[str, str]]:
    """Return `[system, *history, user]` chat messages for the LLM.

    `step_answer` (the top chunk is a procedure step or overview) allows up to 5
    sentences and asks for every action in the step, so steps aren't trimmed."""
    system = SYSTEM_TEMPLATE.format(
        location=location,
        machine=machine,
        length_rule=STEP_LENGTH_RULE if step_answer else LENGTH_RULE,
        staff_status=staff_status_line(help_status, help_called_at),
        context=format_context(chunks),
    )
    return [
        {"role": "system", "content": system},
        *history,
        {"role": "user", "content": question},
    ]
