"""OllamaEmbedder and OllamaChat with a fake HTTP opener (no Ollama needed)."""

from __future__ import annotations

import io
import json
from typing import Any
from urllib.error import URLError
from urllib.request import Request

import numpy as np
import pytest

from services.embedder import DOCUMENT_PREFIX, QUERY_PREFIX, EmbedderUnavailable, OllamaEmbedder
from services.llm_service import LLMUnavailable, OllamaChat


class FakeOpener:
    """Stands in for `urllib.request.urlopen`: records requests, returns a JSON body."""

    def __init__(self, reply: dict[str, Any] | None = None, error: Exception | None = None) -> None:
        self.reply = reply or {}
        self.error = error
        self.requests: list[Request] = []
        self.timeouts: list[float] = []

    def __call__(self, request: Request, timeout: float) -> io.BytesIO:
        self.requests.append(request)
        self.timeouts.append(timeout)
        if self.error is not None:
            raise self.error
        return io.BytesIO(json.dumps(self.reply).encode("utf-8"))

    def body(self, index: int = 0) -> dict[str, Any]:
        data = self.requests[index].data
        assert isinstance(data, bytes)
        return json.loads(data)


def test_embedder_posts_and_normalises() -> None:
    opener = FakeOpener({"embeddings": [[3.0, 4.0], [0.0, 2.0]]})
    embedder = OllamaEmbedder("http://127.0.0.1:11434/", "nomic-embed-text", opener=opener)
    vectors = embedder.embed(["a", "b"])

    assert opener.requests[0].full_url == "http://127.0.0.1:11434/api/embed"
    assert opener.body() == {"model": "nomic-embed-text", "input": ["a", "b"]}
    assert vectors.shape == (2, 2)
    np.testing.assert_allclose(vectors, [[0.6, 0.8], [0.0, 1.0]])


def test_embedder_empty_input_no_request() -> None:
    opener = FakeOpener()
    assert OllamaEmbedder("http://x", "m", opener=opener).embed([]).shape[0] == 0
    assert opener.requests == []


@pytest.mark.parametrize(
    "opener",
    [
        FakeOpener(error=URLError("refused")),
        FakeOpener({"embeddings": [[1.0]]}),  # wrong row count for 2 texts
        FakeOpener({"error": "model not found"}),
    ],
)
def test_embedder_unavailable(opener: FakeOpener) -> None:
    with pytest.raises(EmbedderUnavailable):
        OllamaEmbedder("http://x", "m", opener=opener).embed(["a", "b"])


def test_chat_posts_messages() -> None:
    opener = FakeOpener({"message": {"role": "assistant", "content": "  Load the filament.  "}})
    chat = OllamaChat("http://127.0.0.1:11434", "gemma3:4b", opener=opener)
    messages = [{"role": "user", "content": "hi"}]

    assert chat.chat(messages) == "Load the filament."
    assert opener.requests[0].full_url == "http://127.0.0.1:11434/api/chat"
    assert opener.body() == {
        "model": "gemma3:4b",
        "messages": messages,
        "stream": False,
        "options": {"temperature": 0.2, "num_ctx": 8192},
    }
    assert opener.timeouts == [120.0]


@pytest.mark.parametrize(
    "opener",
    [
        FakeOpener(error=URLError("refused")),
        FakeOpener(error=TimeoutError()),
        FakeOpener({"message": {"content": "   "}}),
        FakeOpener({"error": "model not found"}),
    ],
)
def test_chat_unavailable(opener: FakeOpener) -> None:
    with pytest.raises(LLMUnavailable):
        OllamaChat("http://x", "m", opener=opener).chat([{"role": "user", "content": "hi"}])


def test_embedder_documents_get_nomic_prefix() -> None:
    opener = FakeOpener({"embeddings": [[1.0, 0.0], [0.0, 1.0]]})
    vectors = OllamaEmbedder("http://x", "m", opener=opener).embed_documents(["a", "b"])
    assert vectors.shape == (2, 2)
    assert DOCUMENT_PREFIX == "search_document: "
    assert opener.body()["input"] == ["search_document: a", "search_document: b"]


def test_embedder_query_gets_nomic_prefix() -> None:
    opener = FakeOpener({"embeddings": [[3.0, 4.0]]})
    vector = OllamaEmbedder("http://x", "m", opener=opener).embed_query("hello")
    assert vector.shape == (2,)
    assert np.allclose(vector, [0.6, 0.8])
    assert QUERY_PREFIX == "search_query: "
    assert opener.body()["input"] == ["search_query: hello"]
