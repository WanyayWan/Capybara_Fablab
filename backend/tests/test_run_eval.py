"""scripts/run_eval.py: question loading and pass/fail checks (no backend needed)."""

from pathlib import Path

from scripts.run_eval import DEFAULT_QUESTIONS, check, load_questions


def _response(text: str = "", intent: str = "question", refused: bool = False) -> dict[str, object]:
    return {"text": text, "intent": intent, "refused": refused, "sources": [], "best_score": 0.7}


def test_load_real_questions() -> None:
    questions = load_questions(DEFAULT_QUESTIONS)

    assert len(questions) >= 20
    assert all({"id", "device_id", "question", "expect"} <= q.keys() for q in questions)


def test_load_questions_rejects_unknown_expect(tmp_path: Path) -> None:
    path = tmp_path / "q.yaml"
    path.write_text("- {id: X, device_id: d, question: q, expect: maybe}\n", encoding="utf-8")

    try:
        load_questions(path)
    except ValueError as error:
        assert "X" in str(error)
    else:
        raise AssertionError("expected ValueError")


def test_answer_needs_any_keyword_case_insensitive() -> None:
    question = {"expect": "answer", "must_include": ["grey tab", "AMS"]}

    assert check(question, _response("Push it into the ams slot."))
    assert not check(question, _response("Heat the nozzle first."))


def test_answer_fails_on_must_not_include() -> None:
    question = {"expect": "answer", "must_include": ["ABS"], "must_not_include": ["banned", "avoid"]}

    assert check(question, _response("Yes, the plate is marked for PLA, ABS and PETG."))
    assert not check(question, _response("No, ABS is BANNED."))
    assert not check(question, _response("Avoid ABS."))


def test_answer_fails_when_refused() -> None:
    question = {"expect": "answer", "must_include": ["32"]}

    assert not check(question, _response("Up to 32 GB.", refused=True))


def test_refuse_needs_refused_flag() -> None:
    question = {"expect": "refuse"}

    assert check(question, _response("Sorry, I don't have that.", refused=True))
    assert not check(question, _response("Try Pizza Place."))


def test_help_and_emergency_match_intent() -> None:
    assert check({"expect": "help"}, _response(intent="help"))
    assert not check({"expect": "help"}, _response(intent="question"))
    assert check({"expect": "emergency"}, _response(intent="emergency"))
    assert not check({"expect": "emergency"}, _response(intent="help"))
