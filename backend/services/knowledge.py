"""Load the Fab Lab knowledge base from markdown and retrieve relevant chunks.

Each `*.md` file has YAML frontmatter (`machine`, `source`, `type`) and is split into
one chunk per `## ` heading. Files without frontmatter are skipped with a warning.
Retrieval is cosine similarity over embeddings, with a small boost for chunks matching
the device's machine (or `all`). Loads `knowledge/` and `knowledge/private/` if present.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np

DOCUMENT_PREFIX = "search_document: "
QUERY_PREFIX = "search_query: "


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


def load_chunks(dirs: list[Path]) -> list[Chunk]:
    """Read every `*.md` in `dirs` (missing dirs are ignored) and return heading chunks."""
    raise NotImplementedError


class KnowledgeBase:
    def __init__(
        self,
        chunks: list[Chunk],
        embedder: Embedder,
        top_k: int,
        threshold: float,
        machine_boost: float,
    ) -> None:
        raise NotImplementedError

    def build(self) -> None:
        """Embed all chunks once, with the document prefix."""
        raise NotImplementedError

    def retrieve(self, query: str, machine: str) -> list[ScoredChunk]:
        """Return up to `top_k` chunks sorted by boosted cosine score, highest first."""
        raise NotImplementedError

    def is_confident(self, results: list[ScoredChunk]) -> bool:
        """True if the best result scores at or above the threshold."""
        raise NotImplementedError
