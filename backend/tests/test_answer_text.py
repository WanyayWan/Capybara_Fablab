"""core/answer_text.py: deterministic source prefix, "Say next", refusal openers."""

import pytest

from core.answer_text import is_refusal_reply, shape_reply

SAY_NEXT = "Say next when you're ready."


@pytest.mark.parametrize(
    "reply",
    [
        "I don't have information about the cost of SLS printing per part.",
        "I don’t have that in the guides.",
        "i don't know. The Fab Lab has SLS printers.",
        "According to the 3D printer guide, I don't know.",
    ],
)
def test_AT1_refusal_openers(reply: str) -> None:
    """AT1: replies opening with the refusal phrases count as NO_ANSWER."""
    assert is_refusal_reply(reply)


@pytest.mark.parametrize(
    "reply",
    [
        "No. Never leave the laser cutter unattended.",
        "The build plate is marked for PETG. I don't know of other limits.",
        "I don't recommend cutting PVC.",
    ],
)
def test_AT2_normal_replies_not_refusals(reply: str) -> None:
    """AT2: only the opening counts; other "I don't" sentences are answers."""
    assert not is_refusal_reply(reply)


def test_AT3_prefix_replaces_model_source() -> None:
    """AT3: a model-named (wrong) guide is replaced by the top chunk's spoken_source."""
    reply = "According to the 3D printer guide, no. Never leave it unattended."
    assert shape_reply(reply, "the laser cutter guide", say_next=False) == (
        "According to the laser cutter guide, no. Never leave it unattended."
    )


def test_AT4_prefix_lowercases_plain_first_word_only() -> None:
    """AT4: "You" -> "you", but "I", "I'm" and acronyms keep their case."""
    assert shape_reply("You must book first.", "the Fab Lab website", False) == (
        "According to the Fab Lab website, you must book first."
    )
    assert shape_reply("SUTD staff run it.", "the Fab Lab website", False).endswith(", SUTD staff run it.")
    assert shape_reply("I'm not sure.", "x", False).endswith(", I'm not sure.")


def test_AT5_say_next_only_when_asked() -> None:
    """AT5: "Say next" is stripped when the model adds it without a pointer, appended
    exactly once with one, and curly apostrophes are handled."""
    assert shape_reply(f"Open the lid. {SAY_NEXT}", "the 3D printer guide", False) == (
        "According to the 3D printer guide, open the lid."
    )
    assert shape_reply("Open the lid.", "the 3D printer guide", True) == (
        f"According to the 3D printer guide, open the lid. {SAY_NEXT}"
    )
    assert shape_reply("Open the lid. Say next when you’re ready.", "g", True).count("Say next") == 1


def test_AT7_say_next_lead_in_stripped() -> None:
    """AT7: a model lead-in ("Next, say next ...") or quoted "next" is stripped whole."""
    assert shape_reply("It loads by itself. Next, say next when you're ready.", "g", True) == (
        f"According to g, it loads by itself. {SAY_NEXT}"
    )
    assert shape_reply("Push the tab. Say \"next\" when you're ready.", None, False) == "Push the tab."
    assert shape_reply("Load the next spool.", None, False) == "Load the next spool."


def test_AT8_bare_trailing_next_stripped() -> None:
    """AT8: a lone "Next" after the last sentence goes; "press next" in a sentence stays."""
    assert shape_reply("It loads automatically. Next", "g", True) == (
        f"According to g, it loads automatically. {SAY_NEXT}"
    )
    assert shape_reply("Done. Next.", None, False) == "Done."
    assert shape_reply("On the screen, press Next", None, False) == "On the screen, press Next"


def test_AT6_no_source_strips_and_capitalises() -> None:
    """AT6: without a source (NEXT via the LLM) the model's own prefix is removed."""
    reply = f"According to the 3D printer guide, first heat the nozzle. {SAY_NEXT}"
    assert shape_reply(reply, None, say_next=False) == "First heat the nozzle."
