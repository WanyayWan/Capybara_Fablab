"""Unanswered question log (test-plan: test_unanswered_log.py)."""

import json
from pathlib import Path

from services.unanswered_log import UnansweredLog

FIELDS = {"ts", "device_id", "machine", "question", "best_score"}


def test_U1_log_twice(tmp_path: Path) -> None:
    """U1: log twice to tmp path -> 2 JSON lines with all fields."""
    path = tmp_path / "data" / "unanswered.jsonl"
    log = UnansweredLog(path)
    log.log("fabai-01", "3d-printer", "best pizza?", 0.12)
    log.log("fabai-02", "laser-cutter", "can I weld here?", 0.31)

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    entries = [json.loads(line) for line in lines]
    assert all(set(e) == FIELDS for e in entries)
    assert entries[0]["question"] == "best pizza?"
    assert entries[1]["best_score"] == 0.31
    assert log.read_all() == entries


def test_U2_read_all_missing_file(tmp_path: Path) -> None:
    """U2: read_all on missing file -> empty list."""
    assert UnansweredLog(tmp_path / "nope.jsonl").read_all() == []


def test_read_all_skips_corrupt_lines(tmp_path: Path) -> None:
    path = tmp_path / "unanswered.jsonl"
    log = UnansweredLog(path)
    log.log("fabai-01", "all", "q1", 0.1)
    with path.open("a", encoding="utf-8") as f:
        f.write("{not json\n\n")
    log.log("fabai-01", "all", "q2", 0.2)
    assert [e["question"] for e in log.read_all()] == ["q1", "q2"]


def test_U3_missing_score_is_null(tmp_path: Path) -> None:
    """U3: no retrieval ran (step-mode NEXT) -> best_score is written as null."""
    log = UnansweredLog(tmp_path / "unanswered.jsonl")
    log.log("fabai-01", "3d-printer", "next", None)
    assert log.read_all()[0]["best_score"] is None
