"""Load the Fab Lab knowledge base from markdown and retrieve relevant chunks.

Each `*.md` file has YAML frontmatter (`machine`, `source`, `type`) and is split into
one chunk per `## ` heading. Files without frontmatter are skipped with a warning.
Retrieval is cosine similarity over embeddings (the embedder adds any model-specific
prefixes), with a small boost for chunks matching
the device's machine (or `all`). Loads `knowledge/` and `knowledge/private/` if present.

Chunk embeddings can be cached in an `.npz` file (`EmbeddingCache`) keyed by
`knowledge_fingerprint`: a hash of every knowledge file's bytes plus the embed model name.
`build()` re-embeds only when the key changes or the cache is unreadable.
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np
import yaml

log = logging.getLogger(__name__)

ALL_MACHINES = "all"

_FRONTMATTER = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", re.DOTALL)
_HEADING = re.compile(r"^## +(.+?)\s*$", re.MULTILINE)


class Embedder(Protocol):
    """Model-specific prefixes (e.g. nomic's) are the embedder's job, not ours."""

    def embed_documents(self, texts: list[str]) -> np.ndarray: ...
    def embed_query(self, text: str) -> np.ndarray: ...


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


def _knowledge_files(dirs: list[Path]) -> list[Path]:
    return [path for d in dirs if d.is_dir() for path in sorted(d.glob("*.md"))]


def knowledge_fingerprint(dirs: list[Path], embed_model: str) -> str:
    """Hash of the embed model name and every knowledge file's name and bytes."""
    digest = hashlib.sha256(f"model={embed_model}\n".encode("utf-8"))
    for path in _knowledge_files(dirs):
        data = path.read_bytes()
        digest.update(f"{path.parent.name}/{path.name}:{len(data)}\n".encode("utf-8"))
        digest.update(data)
    return digest.hexdigest()


class EmbeddingCache:
    """Chunk vectors saved to one `.npz` file together with the key they were built for."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self, key: str, rows: int) -> np.ndarray | None:
        """The cached vectors if the file exists, matches `key` and has `rows` rows."""
        if not self.path.is_file():
            return None
        try:
            with np.load(self.path, allow_pickle=False) as data:
                cached_key, vectors = str(data["key"]), np.asarray(data["vectors"], dtype=np.float32)
        except Exception as error:  # corrupt or foreign file: rebuild
            log.warning("Ignoring unreadable embedding cache %s (%s)", self.path, error)
            return None
        if cached_key != key or vectors.ndim != 2 or vectors.shape[0] != rows:
            return None
        return vectors

    def save(self, key: str, vectors: np.ndarray) -> None:
        """Write atomically (temp file, then replace) so a crash never leaves half a cache."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_name(self.path.stem + ".tmp.npz")
        np.savez(temp, key=np.array(key), vectors=vectors)
        temp.replace(self.path)


def load_chunks(dirs: list[Path]) -> list[Chunk]:
    """Read every `*.md` in `dirs` (missing dirs are ignored) and return heading chunks."""
    return [chunk for path in _knowledge_files(dirs) for chunk in _load_file(path)]


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
        cache: EmbeddingCache | None = None,
        cache_key: str = "",
    ) -> None:
        self.chunks = list(chunks)
        self.embedder = embedder
        self.top_k = top_k
        self.threshold = threshold
        self.machine_boost = machine_boost
        self.cache = cache
        self.cache_key = cache_key
        self._vectors: np.ndarray | None = None

    def build(self) -> None:
        """Embed all chunks once, or load them from the cache if the key still matches."""
        if not self.chunks:
            self._vectors = np.zeros((0, 0), dtype=np.float32)
            return
        if self.cache is not None:
            cached = self.cache.load(self.cache_key, rows=len(self.chunks))
            if cached is not None:
                log.info("Loaded %d chunk embeddings from %s", len(cached), self.cache.path)
                self._vectors = cached
                return
        texts = [f"{c.heading}\n{c.text}" for c in self.chunks]
        self._vectors = np.asarray(self.embedder.embed_documents(texts), dtype=np.float32)
        if self.cache is not None:
            try:
                self.cache.save(self.cache_key, self._vectors)
            except OSError:
                log.warning("Could not write embedding cache %s", self.cache.path, exc_info=True)

    def retrieve(self, query: str, machine: str) -> list[ScoredChunk]:
        """Return up to `top_k` chunks sorted by boosted cosine score, highest first."""
        if self._vectors is None:
            self.build()
        if not self.chunks:
            return []
        query_vector = np.asarray(self.embedder.embed_query(query), dtype=np.float32)
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
