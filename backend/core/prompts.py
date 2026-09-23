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
    raise NotImplementedError
