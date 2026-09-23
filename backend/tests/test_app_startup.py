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
    assert len(embedder.calls) == 2 and len(embedder.calls[0]) >= 30
    assert len(embedder.calls[1]) == 1  # one query embed loads the embed model too
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


def test_warm_up_chat_matches_real_chat() -> None:
    """The warm-up chat sends exactly the model, options and keep_alive of a real chat,
    so the first question never reloads the model."""
    from app import WARM_UP_MESSAGES
    from services.llm_service import OllamaChat
    from tests.test_ollama_services import FakeOpener

    opener = FakeOpener({"message": {"content": "OK"}})
    chat = OllamaChat("http://x", "gemma3:4b", num_ctx=Settings().ollama_num_ctx, opener=opener)
    chat.chat(WARM_UP_MESSAGES)
    chat.chat([{"role": "system", "content": "rules"}, {"role": "user", "content": "How do I load filament?"}])
    warm, real = opener.body(0), opener.body(1)
    for key in ("model", "options", "keep_alive", "stream"):
        assert warm[key] == real[key]


def test_num_ctx_setting() -> None:
    """OLLAMA_NUM_CTX defaults to 4096 (prompts are under 1k tokens; less RAM than 8192)."""
    assert Settings().ollama_num_ctx == 4096
    assert Settings.from_mapping({"OLLAMA_NUM_CTX": "8192"}).ollama_num_ctx == 8192
    example = (KNOWLEDGE_ROOT.parent / ".env.example").read_text(encoding="utf-8")
    assert "OLLAMA_NUM_CTX=4096" in example


def test_rag_threshold_default_is_junk_filter() -> None:
    """RAG_THRESHOLD defaults to 0.55: a junk filter only; the LLM NO_ANSWER gate is the
    main refusal (nomic scores bunch together: "best pizza" 0.69 vs real questions 0.68)."""
    assert Settings().rag_threshold == 0.55
    example = (KNOWLEDGE_ROOT.parent / ".env.example").read_text(encoding="utf-8")
    assert "RAG_THRESHOLD=0.55" in example


async def test_warm_up_loads_embed_model_even_with_cache(tmp_path: Path) -> None:
    """With a cache hit no documents are embedded, but one query still loads the embed
    model, so the first real question doesn't pay for it."""
    from services.knowledge import EmbeddingCache

    cache = EmbeddingCache(tmp_path / "kb_cache.npz")
    chunks = load_chunks(knowledge_dirs(KNOWLEDGE_ROOT))
    KnowledgeBase(chunks, FakeEmbedder(), 3, 0.5, 0.05, cache=cache, cache_key="k").build()
    embedder = FakeEmbedder()
    kb = KnowledgeBase(chunks, embedder, 3, 0.5, 0.05, cache=cache, cache_key="k")
    result = await warm_up(kb, FakeLLM("OK"), ollama_ok=lambda: True)
    assert result is not None and result.embed_s is not None
    assert [len(call) for call in embedder.calls] == [1]
