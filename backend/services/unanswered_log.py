"""Log questions the knowledge base couldn't answer, as JSON lines.

Each line has `ts, device_id, machine, question, best_score`. Default file is
`data/unanswered.jsonl` (gitignored).
"""

from __future__ import annotations

from pathlib import Path


class UnansweredLog:
    def __init__(self, path: Path) -> None:
        raise NotImplementedError

    def log(self, device_id: str, machine: str, question: str, best_score: float) -> None:
        """Append one JSON line, creating the parent folder if needed."""
        raise NotImplementedError

    def read_all(self) -> list[dict[str, object]]:
        """Return every logged entry; empty list if the file doesn't exist."""
        raise NotImplementedError
