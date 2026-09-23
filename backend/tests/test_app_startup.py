"""Startup warm-up and keep-alive settings (demo latency, Part B)."""

from __future__ import annotations

from pathlib import Path

from app import warm_up
from config import Settings
from services.knowledge import KnowledgeBase, knowledge_dirs, load_chunks
from tests.fakes import FakeEmbedder, FakeLLM

KNOWLEDGE_ROOT = Path(__file__).resolve().parent.parent / "knowledge"


def make_kb(embedder: FakeEmbedder) -> KnowledgeBase:
    chunks = load_chunks(knowledge_dirs(KNOWLEDGE_ROOT))
    return KnowledgeBase(chunks, embedder, top_k=3, threshold=0.5, machine_boost=0.05)


class FailingEmbedder(FakeEmbedder):
    def embed_documents(self, texts: list[str]):  # type: ignore[no-untyped-def]
        raise RuntimeError("embed failed")


async def test_warm_up_when_ollama_up() -> None:
    """B1: Ollama reachable -> KB embedded now and one tiny LLM request, both timed."""
    embedder, llm = FakeEmbedder(), FakeLLM("OK")
    result = await warm_up(make_kb(embedder), llm, ollama_ok=lambda: True)
    assert result is not None
    assert len(embedder.calls) == 1 and len(embedder.calls[0]) >= 30
    assert llm.calls == 1
    assert llm.last_messages is not None and len(llm.last_messages) == 1
    assert len(llm.last_messages[0]["content"]) < 40
    assert result.embed_s is not None and result.embed_s >= 0
    assert result.llm_s is not None and result.llm_s >= 0


async def test_warm_up_skipped_when_ollama_down() -> None:
    """B1: Ollama down -> nothing is called (lazy embedding on first question)."""
    embedder, llm = FakeEmbedder(), FakeLLM("OK")
    assert await warm_up(make_kb(embedder), llm, ollama_ok=lambda: False) is None
    assert embedder.calls == []
    assert llm.calls == 0


async def test_warm_up_failures_do_not_raise() -> None:
    """A failing embed or LLM call during warm-up is logged, not fatal."""
    llm = FakeLLM("", error=RuntimeError("model not found"))
    result = await warm_up(make_kb(FailingEmbedder()), llm, ollama_ok=lambda: True)
    assert result is not None
    assert result.embed_s is None and result.llm_s is None


def test_keep_alive_setting() -> None:
    """B2: OLLAMA_KEEP_ALIVE defaults to 30m and is configurable."""
    assert Settings().ollama_keep_alive == "30m"
    assert Settings.from_mapping({"OLLAMA_KEEP_ALIVE": "1h"}).ollama_keep_alive == "1h"
    example = (KNOWLEDGE_ROOT.parent / ".env.example").read_text(encoding="utf-8")
    assert "OLLAMA_KEEP_ALIVE=30m" in example
