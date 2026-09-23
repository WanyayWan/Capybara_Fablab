"""Knowledge loading and retrieval (test-plan: test_knowledge.py).

Threshold-dependent tests set their own threshold (build-plan section 9.8)."""

from pathlib import Path

import pytest

import numpy as np

from services.knowledge import (
    Chunk,
    EmbeddingCache,
    KnowledgeBase,
    knowledge_dirs,
    knowledge_fingerprint,
    load_chunks,
)
from tests.fakes import FakeEmbedder

KNOWLEDGE_ROOT = Path(__file__).resolve().parent.parent / "knowledge"
# Test-level threshold (build-plan 9.8). With FakeEmbedder (no prefixes), "best pizza"
# tops out at 0.27 and the SD card queries score 0.78-0.84, so 0.5 separates them.
TEST_THRESHOLD = 0.5

THREE_HEADINGS = """\
---
machine: laser-cutter
spoken_source: the test guide
origin: Test guide
type: sop
---

Intro text before the first heading.

## First heading
Alpha text.

## Second heading
Beta text
over two lines.

## Third heading
Gamma text.
"""


def make_kb(chunks: list[Chunk], top_k: int = 3, boost: float = 0.05) -> KnowledgeBase:
    kb = KnowledgeBase(
        chunks, FakeEmbedder(), top_k=top_k, threshold=TEST_THRESHOLD, machine_boost=boost
    )
    kb.build()
    return kb


def real_kb() -> KnowledgeBase:
    return make_kb(load_chunks(knowledge_dirs(KNOWLEDGE_ROOT)))


def chunk(id: str, machine: str, heading: str, text: str) -> Chunk:
    return Chunk(
        id=id, machine=machine, spoken_source="the test guide", origin="Test guide", heading=heading, text=text
    )


def test_K1_load_real_knowledge() -> None:
    """K1: >= 30 chunks, every chunk has machine, spoken_source and origin."""
    chunks = load_chunks(knowledge_dirs(KNOWLEDGE_ROOT))
    assert len(chunks) >= 30
    assert all(c.machine and c.spoken_source and c.origin and c.heading and c.text for c in chunks)
    assert len({c.id for c in chunks}) == len(chunks)


def test_K2_split_on_headings(tmp_path: Path) -> None:
    """K2: 3 ## headings -> 3 chunks, frontmatter not in text."""
    (tmp_path / "guide.md").write_text(THREE_HEADINGS, encoding="utf-8")
    chunks = load_chunks([tmp_path])
    assert [c.heading for c in chunks] == ["First heading", "Second heading", "Third heading"]
    assert chunks[1].text == "Beta text\nover two lines."
    assert all(c.machine == "laser-cutter" and c.spoken_source == "the test guide" for c in chunks)
    assert all(c.origin == "Test guide" for c in chunks)
    for c in chunks:
        assert "machine:" not in c.text and "---" not in c.text and "Intro" not in c.text


def test_K3_skip_without_frontmatter(tmp_path: Path) -> None:
    """K3: file without frontmatter skipped, no crash."""
    (tmp_path / "bad.md").write_text("## Heading\nNo frontmatter here.\n", encoding="utf-8")
    (tmp_path / "broken.md").write_text("---\nmachine: [unclosed\n---\n## H\nx\n", encoding="utf-8")
    (tmp_path / "good.md").write_text(THREE_HEADINGS, encoding="utf-8")
    chunks = load_chunks([tmp_path])
    assert len(chunks) == 3
    assert {c.origin for c in chunks} == {"Test guide"}


def test_K4_private_missing_ok(tmp_path: Path) -> None:
    """K4: private/ missing -> loads fine."""
    (tmp_path / "guide.md").write_text(THREE_HEADINGS, encoding="utf-8")
    assert not (tmp_path / "private").exists()
    assert len(load_chunks(knowledge_dirs(tmp_path))) == 3


def test_K4b_private_loaded_once_when_present(tmp_path: Path) -> None:
    """private/ is loaded when present, and not twice."""
    (tmp_path / "guide.md").write_text(THREE_HEADINGS, encoding="utf-8")
    (tmp_path / "private").mkdir()
    (tmp_path / "private" / "internal.md").write_text(THREE_HEADINGS, encoding="utf-8")
    assert len(load_chunks(knowledge_dirs(tmp_path))) == 6


def test_K5_retrieve_sd_card() -> None:
    """K5: "what size SD card" (3d-printer) -> top heading mentions SD card."""
    results = real_kb().retrieve("what size SD card", "3d-printer")
    assert "SD card" in results[0].chunk.heading


def test_K6_retrieve_pvc_banned() -> None:
    """K6: "can I cut PVC" (laser-cutter) -> top chunk is a laser cutter PVC safety chunk
    (the dedicated PVC/vinyl section or the banned-materials list)."""
    results = real_kb().retrieve("can I cut PVC", "laser-cutter")
    assert results[0].chunk.heading in {
        "Can I cut PVC or vinyl on the laser cutter?",
        "What materials are banned?",
    }


def test_K7_machine_boost_ranks_first() -> None:
    """K7: equally similar chunks -> device machine ranks first."""
    chunks = [
        chunk("a", "3d-printer", "Cleaning", "Wipe the bed after use."),
        chunk("b", "laser-cutter", "Cleaning", "Wipe the bed after use."),
    ]
    kb = make_kb(chunks)
    assert kb.retrieve("wipe the bed", "laser-cutter")[0].chunk.id == "b"
    assert kb.retrieve("wipe the bed", "3d-printer")[0].chunk.id == "a"


def test_K7b_all_machine_boosted() -> None:
    """Chunks for machine `all` get the boost too; other machines don't."""
    chunks = [
        chunk("a", "3d-printer", "Cleaning", "Wipe the bed after use."),
        chunk("b", "all", "Cleaning", "Wipe the bed after use."),
    ]
    results = make_kb(chunks, boost=0.1).retrieve("wipe the bed", "laser-cutter")
    assert results[0].chunk.id == "b"
    assert results[0].score - results[1].score == pytest.approx(0.1, abs=1e-6)


def test_K8_unrelated_not_confident() -> None:
    """K8: "best pizza" -> is_confident False."""
    kb = real_kb()
    assert not kb.is_confident(kb.retrieve("best pizza", "3d-printer"))
    assert kb.is_confident(kb.retrieve("what is the maximum SD card size", "3d-printer"))
    assert not kb.is_confident([])


def test_K9_top_k_sorted() -> None:
    """K9: top_k 3 -> at most 3 results, sorted by score desc."""
    results = real_kb().retrieve("how do I load filament", "3d-printer")
    assert 0 < len(results) <= 3
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)


def test_kb_passes_raw_text_to_embedder() -> None:
    """The KB sends unprefixed text; model prefixes are the embedder's job."""
    embedder = FakeEmbedder()
    kb = KnowledgeBase(
        [chunk("a", "all", "H", "T")], embedder, top_k=3, threshold=TEST_THRESHOLD, machine_boost=0.05
    )
    kb.build()
    kb.retrieve("hello", "all")
    assert embedder.calls == [["H\nT"], ["hello"]]


def test_empty_knowledge_base() -> None:
    kb = make_kb([])
    assert kb.retrieve("anything", "all") == []



def cached_kb(embedder: FakeEmbedder, cache: EmbeddingCache, key: str) -> KnowledgeBase:
    chunks = load_chunks(knowledge_dirs(KNOWLEDGE_ROOT))
    return KnowledgeBase(
        chunks, embedder, top_k=3, threshold=TEST_THRESHOLD, machine_boost=0.05, cache=cache, cache_key=key
    )


def test_K10_cache_hit_skips_embedding(tmp_path: Path) -> None:
    """K10: second build with the same key loads kb_cache.npz and never calls the embedder."""
    cache = EmbeddingCache(tmp_path / "data" / "kb_cache.npz")
    first = FakeEmbedder()
    cached_kb(first, cache, "key-1").build()
    assert len(first.calls) == 1 and cache.path.is_file()

    second = FakeEmbedder()
    kb = cached_kb(second, cache, "key-1")
    kb.build()
    assert second.calls == []
    assert "SD card" in kb.retrieve("what size SD card", "3d-printer")[0].chunk.heading


def test_K11_cache_rebuilt_when_key_changes(tmp_path: Path) -> None:
    """K11: a different key (knowledge or embed model changed) re-embeds and overwrites."""
    cache = EmbeddingCache(tmp_path / "kb_cache.npz")
    cached_kb(FakeEmbedder(), cache, "old").build()
    embedder = FakeEmbedder()
    cached_kb(embedder, cache, "new").build()
    assert len(embedder.calls) == 1
    assert cache.load("new", rows=len(load_chunks(knowledge_dirs(KNOWLEDGE_ROOT)))) is not None
    assert cache.load("old", rows=1) is None


def test_K12_corrupt_or_wrong_size_cache_ignored(tmp_path: Path) -> None:
    """K12: an unreadable cache file or one with the wrong row count is rebuilt, not fatal."""
    cache = EmbeddingCache(tmp_path / "kb_cache.npz")
    cache.path.write_bytes(b"not a zip file")
    embedder = FakeEmbedder()
    cached_kb(embedder, cache, "k").build()
    assert len(embedder.calls) == 1

    cache.save("k", np.zeros((2, 4), dtype=np.float32))
    assert cache.load("k", rows=3) is None


def test_K13_fingerprint_tracks_files_and_model(tmp_path: Path) -> None:
    """K13: the cache key changes when a knowledge file or the embed model changes."""
    (tmp_path / "guide.md").write_text(THREE_HEADINGS, encoding="utf-8")
    dirs = knowledge_dirs(tmp_path)
    base = knowledge_fingerprint(dirs, "nomic-embed-text")
    assert knowledge_fingerprint(dirs, "nomic-embed-text") == base
    assert knowledge_fingerprint(dirs, "other-model") != base
    (tmp_path / "guide.md").write_text(THREE_HEADINGS + "\n## Fourth\nDelta.\n", encoding="utf-8")
    assert knowledge_fingerprint(dirs, "nomic-embed-text") != base


def test_K14_spoken_source_names() -> None:
    """K14: prompts use the spoken name; the original citation is kept as origin."""
    chunks = load_chunks(knowledge_dirs(KNOWLEDGE_ROOT))
    by_machine = {c.machine: c for c in chunks}
    assert by_machine["all"].spoken_source == "the Fab Lab website"
    assert by_machine["3d-printer"].spoken_source == "the 3D printer guide"
    assert by_machine["laser-cutter"].spoken_source == "the laser cutter guide"
    assert by_machine["3d-printer"].origin == 'Fab Lab posted sign "Hands-On" (3D printing area)'


def test_K14b_legacy_source_frontmatter(tmp_path: Path) -> None:
    """A file with only the old `source:` key uses it as both origin and spoken name."""
    legacy = THREE_HEADINGS.replace("spoken_source: the test guide\norigin: Test guide", "source: Old guide")
    (tmp_path / "old.md").write_text(legacy, encoding="utf-8")
    chunks = load_chunks([tmp_path])
    assert len(chunks) == 3
    assert {(c.spoken_source, c.origin) for c in chunks} == {("Old guide", "Old guide")}


def test_K15_step_chunk_lookup() -> None:
    """K15: step mode fetches "Step N" of a file directly; missing steps are None."""
    kb = KnowledgeBase(
        load_chunks(knowledge_dirs(KNOWLEDGE_ROOT)), FakeEmbedder(), top_k=3, threshold=0.5, machine_boost=0.05
    )
    step = kb.step_chunk("3d-printer", 2)
    assert step is not None and step.heading == "Step 2: How do I load filament?"
    assert kb.step_chunk("laser-cutter", 2) is not None
    assert kb.step_chunk("laser-cutter", 2).file == "laser-cutter"  # type: ignore[union-attr]
    assert kb.step_chunk("3d-printer", 7) is None
    assert kb.step_chunk("general", 1) is None


def test_K16_chunk_lookup_by_heading() -> None:
    """K16: the safety net finds the banned-materials chunk by file and exact heading."""
    kb = KnowledgeBase(
        load_chunks(knowledge_dirs(KNOWLEDGE_ROOT)), FakeEmbedder(), top_k=3, threshold=0.5, machine_boost=0.05
    )
    banned = kb.chunk("laser-cutter", "What materials are banned?")
    assert banned is not None
    assert "PVC" in banned.text and banned.spoken_source == "the laser cutter guide"
    pvc = kb.chunk("laser-cutter", "Can I cut PVC or vinyl on the laser cutter?")
    assert pvc is not None and "chlorine" in pvc.text
    assert kb.chunk("3d-printer", "What materials are banned?") is None
