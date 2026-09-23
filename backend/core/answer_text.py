"""Post-process LLM answers so source naming and "Say next" are deterministic.

The model is told not to name sources and not to add "Say next". Whatever it does,
`shape_reply` strips a leading "According to ...," and any "Say next when you're
ready.", then adds "According to <spoken_source>, " from the top retrieved chunk and
the "Say next" line only when the pipeline set a step pointer. `is_refusal_reply`
catches refusals the model writes in its own words instead of NO_ANSWER.
"""

from __future__ import annotations

import re

from core.steps import SAY_NEXT_TEXT

REFUSAL_OPENERS = ("i don't have information", "i don't have that", "i don't know")

_ACCORDING_TO = re.compile(r"^\s*according to [^,.]{1,80},\s*", re.IGNORECASE)
# Also takes a lead-in the model may write before it: "Next, say next when you're ready."
_SAY_NEXT = re.compile(
    r"[\s,]*(?:\bnext[,.]?\s+)?say\s+[\"']?next[\"']?\s+when\s+you(?:'|’)re\s+ready\.?",
    re.IGNORECASE,
)
# A bare trailing "Next" after a sentence (gemma adds it when staff are called).
_TRAILING_NEXT = re.compile(r"(?<=[.!?])\s+next[.!]?\s*$", re.IGNORECASE)


def _straight(text: str) -> str:
    return text.replace("’", "'").replace("‘", "'")


def is_refusal_reply(reply: str) -> bool:
    """True if the reply opens with "I don't have information / that" or "I don't know"
    (after any "According to ...,"): the model refused without saying NO_ANSWER."""
    body = _ACCORDING_TO.sub("", _straight(reply).strip(), count=1).lower()
    return body.startswith(REFUSAL_OPENERS)


def _lower_first_word(text: str) -> str:
    """"You must..." -> "you must..." after a prefix; leaves "I", "I'm", "SUTD" alone."""
    word = text.split(" ", 1)[0]
    if len(word) > 1 and word[0].isupper() and word[1:].islower() and not word.startswith("I'"):
        return text[0].lower() + text[1:]
    return text


def _upper_first(text: str) -> str:
    return text[:1].upper() + text[1:]


def shape_reply(reply: str, spoken_source: str | None, say_next: bool) -> str:
    """Strip model-added source naming and "Say next", then add them deterministically:
    "According to <spoken_source>, " if `spoken_source`, "Say next..." if `say_next`."""
    body = _ACCORDING_TO.sub("", reply.strip(), count=1)
    body = " ".join(_SAY_NEXT.sub("", body).split())
    body = _TRAILING_NEXT.sub("", body)
    if spoken_source:
        body = f"According to {spoken_source}, {_lower_first_word(body)}"
    else:
        body = _upper_first(body)
    return f"{body} {SAY_NEXT_TEXT}" if say_next else body
