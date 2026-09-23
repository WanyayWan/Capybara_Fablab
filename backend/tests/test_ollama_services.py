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
from services.llm_service import LLMUnavailable, OllamaChat, OllamaHealth
from tests.fakes import FakeClock


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
    assert opener.body() == {"model": "nomic-embed-text", "input": ["a", "b"], "keep_alive": "30m"}
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
        "options": {"temperature": 0.2, "num_ctx": 4096},
        "keep_alive": "30m",
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


def test_health_ok_and_cached() -> None:
    opener = FakeOpener({"models": []})
    clock = FakeClock()
    health = OllamaHealth("http://x/", opener=opener, clock=clock.now)
    assert health.check() is True
    assert opener.requests[0].full_url == "http://x/api/tags"
    assert opener.timeouts == [1.0]
    clock.advance(9.9)
    assert health.check() is True
    assert len(opener.requests) == 1
    clock.advance(0.2)
    health.check()
    assert len(opener.requests) == 2


def test_health_down() -> None:
    health = OllamaHealth("http://x", opener=FakeOpener(error=URLError("refused")))
    assert health.check() is False


def test_keep_alive_configurable() -> None:
    """B2: keep_alive is passed on chat and embed requests and can be overridden."""
    chat_opener = FakeOpener({"message": {"content": "ok"}})
    OllamaChat("http://x", "m", keep_alive="-1", opener=chat_opener).chat([{"role": "user", "content": "hi"}])
    assert chat_opener.body()["keep_alive"] == "-1"
    embed_opener = FakeOpener({"embeddings": [[1.0]]})
    OllamaEmbedder("http://x", "m", keep_alive="5m", opener=embed_opener).embed_query("q")
    assert embed_opener.body()["keep_alive"] == "5m"


class EchoEmbedOpener(FakeOpener):
    """Returns one embedding per input text, so any batch size is valid."""

    def __call__(self, request: Request, timeout: float) -> io.BytesIO:
        super().__call__(request, timeout)
        count = len(json.loads(request.data)["input"])  # type: ignore[arg-type]
        self.reply = {"embeddings": [[1.0, float(i)] for i in range(count)], "load_duration": 0}
        return io.BytesIO(json.dumps(self.reply).encode("utf-8"))


def test_embedder_batches_of_32() -> None:
    """KB build: 70 texts -> 3 /api/embed requests of 32, 32, 6 inputs, rows in order."""
    opener = EchoEmbedOpener()
    vectors = OllamaEmbedder("http://x", "m", opener=opener).embed([f"t{i}" for i in range(70)])
    assert [len(opener.body(i)["input"]) for i in range(len(opener.requests))] == [32, 32, 6]
    assert opener.body(2)["input"][0] == "t64"
    assert vectors.shape == (70, 2)


def test_chat_options_and_num_ctx_configurable() -> None:
    opener = FakeOpener({"message": {"content": "ok"}})
    chat = OllamaChat("http://x", "m", num_ctx=2048, opener=opener)
    chat.chat([{"role": "user", "content": "hi"}])
    assert opener.body()["options"] == {"temperature": 0.2, "num_ctx": 2048}
    assert chat.options == {"temperature": 0.2, "num_ctx": 2048}


def test_chat_logs_options_and_timing(caplog: pytest.LogCaptureFixture) -> None:
    """Each chat request logs the model, the options it sent, and Ollama's load time."""
    opener = FakeOpener({"message": {"content": "ok"}, "load_duration": 2_500_000_000})
    caplog.set_level("INFO")
    OllamaChat("http://x", "gemma3:4b", opener=opener).chat([{"role": "user", "content": "hi"}])
    line = next(r.getMessage() for r in caplog.records if r.name == "services.llm_service")
    assert "gemma3:4b" in line and "num_ctx" in line and "keep_alive=30m" in line
    assert "load 2.50 s" in line
