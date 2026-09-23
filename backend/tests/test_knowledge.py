"""Knowledge loading and retrieval (test-plan: test_knowledge.py).

Threshold-dependent tests set their own threshold (build-plan section 9.8)."""

from pathlib import Path

import pytest

from services.knowledge import Chunk, KnowledgeBase, knowledge_dirs, load_chunks
from tests.fakes import FakeEmbedder

KNOWLEDGE_ROOT = Path(__file__).resolve().parent.parent / "knowledge"
# Test-level threshold (build-plan 9.8). With FakeEmbedder (no prefixes), "best pizza"
# tops out at 0.27 and the SD card queries score 0.78-0.84, so 0.5 separates them.
TEST_THRESHOLD = 0.5

THREE_HEADINGS = """\
---
machine: laser-cutter
source: Test guide
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
    return Chunk(id=id, machine=machine, source="Test guide", heading=heading, text=text)


def test_K1_load_real_knowledge() -> None:
    """K1: >= 30 chunks, every chunk has machine and source."""
    chunks = load_chunks(knowledge_dirs(KNOWLEDGE_ROOT))
    assert len(chunks) >= 30
    assert all(c.machine and c.source and c.heading and c.text for c in chunks)
    assert len({c.id for c in chunks}) == len(chunks)


def test_K2_split_on_headings(tmp_path: Path) -> None:
    """K2: 3 ## headings -> 3 chunks, frontmatter not in text."""
    (tmp_path / "guide.md").write_text(THREE_HEADINGS, encoding="utf-8")
    chunks = load_chunks([tmp_path])
    assert [c.heading for c in chunks] == ["First heading", "Second heading", "Third heading"]
    assert chunks[1].text == "Beta text\nover two lines."
    assert all(c.machine == "laser-cutter" and c.source == "Test guide" for c in chunks)
    for c in chunks:
        assert "machine:" not in c.text and "---" not in c.text and "Intro" not in c.text


def test_K3_skip_without_frontmatter(tmp_path: Path) -> None:
    """K3: file without frontmatter skipped, no crash."""
    (tmp_path / "bad.md").write_text("## Heading\nNo frontmatter here.\n", encoding="utf-8")
    (tmp_path / "broken.md").write_text("---\nmachine: [unclosed\n---\n## H\nx\n", encoding="utf-8")
    (tmp_path / "good.md").write_text(THREE_HEADINGS, encoding="utf-8")
    chunks = load_chunks([tmp_path])
    assert len(chunks) == 3
    assert {c.source for c in chunks} == {"Test guide"}


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
    """K6: "can I cut PVC" (laser-cutter) -> top chunk is banned materials."""
    results = real_kb().retrieve("can I cut PVC", "laser-cutter")
    assert results[0].chunk.heading == "What materials are banned?"


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

