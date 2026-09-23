"""Load the Fab Lab knowledge base from markdown and retrieve relevant chunks.

Each `*.md` file has YAML frontmatter (`machine`, `source`, `type`) and is split into
one chunk per `## ` heading. Files without frontmatter are skipped with a warning.
Retrieval is cosine similarity over embeddings, with a small boost for chunks matching
the device's machine (or `all`). Loads `knowledge/` and `knowledge/private/` if present.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np
import yaml

log = logging.getLogger(__name__)

DOCUMENT_PREFIX = "search_document: "
QUERY_PREFIX = "search_query: "
ALL_MACHINES = "all"

_FRONTMATTER = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", re.DOTALL)
_HEADING = re.compile(r"^## +(.+?)\s*$", re.MULTILINE)


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> np.ndarray: ...


@dataclass(frozen=True)
class Chunk:
    id: str
    machine: str
    source: str
    heading: str
    text: str


@dataclass(frozen=True)
class ScoredChunk:
    chunk: Chunk
    score: float


def knowledge_dirs(root: Path) -> list[Path]:
    """The public knowledge folder and its gitignored `private/` subfolder."""
    return [root, root / "private"]


def load_chunks(dirs: list[Path]) -> list[Chunk]:
    """Read every `*.md` in `dirs` (missing dirs are ignored) and return heading chunks."""
    chunks: list[Chunk] = []
    for directory in dirs:
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.md")):
            chunks.extend(_load_file(path))
    return chunks


def _load_file(path: Path) -> list[Chunk]:
    parsed = _parse_frontmatter(path.read_text(encoding="utf-8"))
    if parsed is None:
        log.warning("Skipping %s: missing or invalid frontmatter", path)
        return []
    meta, body = parsed
    machine, source = str(meta.get("machine") or ""), str(meta.get("source") or "")
    if not machine or not source:
        log.warning("Skipping %s: frontmatter needs machine and source", path)
        return []
    prefix = f"{path.parent.name}/{path.stem}" if path.parent.name == "private" else path.stem
    return [
        Chunk(id=f"{prefix}#{i}", machine=machine, source=source, heading=heading, text=text)
        for i, (heading, text) in enumerate(_split_sections(body), start=1)
    ]


def _parse_frontmatter(content: str) -> tuple[dict[str, object], str] | None:
    """Return (frontmatter, body), or None if the frontmatter is missing or not a mapping."""
    match = _FRONTMATTER.match(content)
    if match is None:
        return None
    try:
        meta = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        return None
    return (meta, content[match.end() :]) if isinstance(meta, dict) else None


def _split_sections(body: str) -> list[tuple[str, str]]:
    """Return (heading, text) per `## ` heading; text before the first heading is dropped."""
    matches = list(_HEADING.finditer(body))
    sections = []
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        text = body[match.end() : end].strip()
        if text:
            sections.append((match.group(1), text))
    return sections


class KnowledgeBase:
    def __init__(
        self,
        chunks: list[Chunk],
        embedder: Embedder,
        top_k: int,
        threshold: float,
        machine_boost: float,
    ) -> None:
        self.chunks = list(chunks)
        self.embedder = embedder
        self.top_k = top_k
        self.threshold = threshold
        self.machine_boost = machine_boost
        self._vectors: np.ndarray | None = None

    def build(self) -> None:
        """Embed all chunks once, with the document prefix."""
        if not self.chunks:
            self._vectors = np.zeros((0, 0), dtype=np.float32)
            return
        texts = [f"{DOCUMENT_PREFIX}{c.heading}\n{c.text}" for c in self.chunks]
        self._vectors = np.asarray(self.embedder.embed(texts), dtype=np.float32)

    def retrieve(self, query: str, machine: str) -> list[ScoredChunk]:
        """Return up to `top_k` chunks sorted by boosted cosine score, highest first."""
        if self._vectors is None:
            self.build()
        if not self.chunks:
            return []
        query_vector = np.asarray(self.embedder.embed([QUERY_PREFIX + query]), dtype=np.float32)[0]
        scores = self._vectors @ query_vector  # type: ignore[operator]
        boosts = np.array(
            [self.machine_boost if c.machine in (machine, ALL_MACHINES) else 0.0 for c in self.chunks]
        )
        scores = scores + boosts
        order = np.argsort(-scores, kind="stable")[: self.top_k]
        return [ScoredChunk(chunk=self.chunks[i], score=float(scores[i])) for i in order]

    def is_confident(self, results: list[ScoredChunk]) -> bool:
        """True if the best result scores at or above the threshold."""
        return bool(results) and max(r.score for r in results) >= self.threshold
