"""Log questions the knowledge base couldn't answer, as JSON lines.

Each line has `ts, device_id, machine, question, best_score`. Default file is
`data/unanswered.jsonl` (gitignored).
"""

from __future__ import annotations

import json
import logging
import threading
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now().astimezone()


class UnansweredLog:
    def __init__(self, path: Path, now: Callable[[], datetime] = _now) -> None:
        self.path = path
        self._now = now
        self._lock = threading.Lock()

    def log(self, device_id: str, machine: str, question: str, best_score: float) -> None:
        """Append one JSON line, creating the parent folder if needed."""
        entry = {
            "ts": self._now().isoformat(timespec="seconds"),
            "device_id": device_id,
            "machine": machine,
            "question": question,
            "best_score": round(float(best_score), 4),
        }
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def read_all(self) -> list[dict[str, object]]:
        """Return every logged entry; empty list if the file doesn't exist."""
        if not self.path.is_file():
            return []
        entries = []
        with self._lock:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        for line in lines:
            if not line.strip():
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                log.warning("Skipping corrupt line in %s", self.path)
        return entries
