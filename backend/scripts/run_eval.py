"""RAG eval: ask every question in tests/eval/questions.yaml against a running backend.

Checks `expect: answer` (not refused, contains a `must_include` keyword and none of the
optional `must_not_include` keywords),
`refuse` (refused), and `help` / `emergency` (matching intent). Prints a table of
id, pass/fail, intent, refused, best score and answer preview, then the pass rate
(target >= 80%).

Questions from the same device follow each other within the session timeout, so the
backend would merge them as follow-ups. Start it with `SESSION_TIMEOUT_S=0` to ask each
one fresh. `help` / `emergency` questions really call staff: set `TELEGRAM_BOT_TOKEN` and
`TELEGRAM_CHAT_ID` to a space (overrides `.env`, counts as unset; in PowerShell `''` deletes
the variable so `.env` would win) to use the console notifier instead.

Usage: python scripts/run_eval.py [--backend URL] [--questions PATH]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import yaml

DEFAULT_QUESTIONS = Path(__file__).resolve().parent.parent / "tests" / "eval" / "questions.yaml"
DEFAULT_BACKEND = "http://127.0.0.1:8000"
PASS_TARGET = 0.8
EXPECTATIONS = ("answer", "refuse", "help", "emergency")
REQUIRED_KEYS = ("id", "device_id", "question", "expect")
PREVIEW_CHARS = 70
TIMEOUT_S = 120.0


def load_questions(path: Path) -> list[dict[str, object]]:
    """Read the eval YAML (a list of question mappings) and validate each entry."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"{path}: expected a list of questions")
    for entry in data:
        if not isinstance(entry, dict) or any(k not in entry for k in REQUIRED_KEYS):
            raise ValueError(f"{path}: every question needs {', '.join(REQUIRED_KEYS)}: {entry!r}")
        if entry["expect"] not in EXPECTATIONS:
            raise ValueError(f"{path}: {entry['id']}: expect must be one of {', '.join(EXPECTATIONS)}")
    return data


def matched_keyword(question: dict[str, object], text: str) -> str | None:
    """The first `must_include` keyword found in `text` (case-insensitive), if any."""
    lowered = text.lower()
    keywords = question.get("must_include") or []
    return next((str(k) for k in keywords if str(k).lower() in lowered), None)  # type: ignore[union-attr]


def check(question: dict[str, object], response: dict[str, object]) -> bool:
    """True if `response` from /api/ask meets the question's expectation."""
    expect = question["expect"]
    if expect == "answer":
        text = str(response.get("text", ""))
        forbidden = [str(k).lower() for k in question.get("must_not_include") or []]  # type: ignore[union-attr]
        return (
            not response.get("refused")
            and matched_keyword(question, text) is not None
            and not any(k in text.lower() for k in forbidden)
        )
    if expect == "refuse":
        return response.get("refused") is True
    return response.get("intent") == expect


def ask(backend: str, device_id: str, question: str) -> dict[str, object]:
    """POST /api/ask; an HTTP or connection failure becomes `{"error": ...}`."""
    payload = json.dumps({"device_id": device_id, "question": question}).encode("utf-8")
    request = Request(
        backend.rstrip("/") + "/api/ask",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=TIMEOUT_S) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        return {"error": f"HTTP {error.code}: {error.read().decode('utf-8', 'replace')[:200]}"}
    except (URLError, OSError, ValueError) as error:
        return {"error": str(error)}


def _row(question: dict[str, object], response: dict[str, object], passed: bool) -> list[str]:
    score = response.get("best_score")
    text = str(response.get("error") or response.get("text", ""))
    preview = " ".join(text.split())
    if len(preview) > PREVIEW_CHARS:
        preview = preview[: PREVIEW_CHARS - 3] + "..."
    return [
        str(question["id"]),
        "PASS" if passed else "FAIL",
        str(question["expect"]),
        str(response.get("intent", "-")),
        str(response.get("refused", "-")),
        f"{score:.3f}" if isinstance(score, (int, float)) else "-",
        preview,
    ]


def print_table(rows: list[list[str]]) -> None:
    header = ["id", "result", "expect", "intent", "refused", "best", "answer preview"]
    widths = [max(len(r[i]) for r in [header, *rows]) for i in range(len(header) - 1)]
    for row in [header, *rows]:
        cells = [cell.ljust(width) for cell, width in zip(row, widths)]
        print("  ".join([*cells, row[-1]]))


def main(argv: list[str] | None = None) -> int:
    """Run the eval; exit code 0 if the pass rate is at least 80%."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--backend", default=DEFAULT_BACKEND)
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
    args = parser.parse_args(argv)

    questions = load_questions(args.questions)
    rows: list[list[str]] = []
    passed = 0
    for question in questions:
        response = ask(args.backend, str(question["device_id"]), str(question["question"]))
        ok = "error" not in response and check(question, response)
        passed += ok
        rows.append(_row(question, response, ok))
        print(f"{question['id']}: {'PASS' if ok else 'FAIL'}", flush=True)

    print()
    print_table(rows)
    rate = passed / len(questions) if questions else 0.0
    print(f"\nPass rate: {passed}/{len(questions)} = {rate:.0%} (target {PASS_TARGET:.0%})")
    return 0 if rate >= PASS_TARGET else 1


if __name__ == "__main__":
    raise SystemExit(main())
