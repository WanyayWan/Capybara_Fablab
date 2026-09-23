"""RAG eval: ask every question in tests/eval/questions.yaml against a running backend.

Checks `expect: answer` (not refused, contains a `must_include` keyword),
`refuse` (refused), and `help` / `emergency` (matching intent). Prints a table of
id, pass/fail, score and answer preview, then the pass rate (target >= 80%).
"""

from __future__ import annotations

from pathlib import Path

DEFAULT_QUESTIONS = Path(__file__).resolve().parent.parent / "tests" / "eval" / "questions.yaml"
DEFAULT_BACKEND = "http://127.0.0.1:8000"


def load_questions(path: Path) -> list[dict[str, object]]:
    raise NotImplementedError


def check(question: dict[str, object], response: dict[str, object]) -> bool:
    """True if `response` from /api/ask meets the question's expectation."""
    raise NotImplementedError


def main(argv: list[str] | None = None) -> int:
    """Run the eval; exit code 0 if the pass rate is at least 80%."""
    raise NotImplementedError


if __name__ == "__main__":
    raise SystemExit(main())
