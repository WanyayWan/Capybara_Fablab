"""Text embeddings from a local Ollama server (`POST /api/embed`).

Synchronous; callers run it via `asyncio.to_thread`. Rows are L2-normalised so a dot
product is cosine similarity. nomic-embed-text needs task prefixes, so they are added
here (`embed_documents` / `embed_query`) rather than by callers.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

import numpy as np

Opener = Callable[..., Any]

DOCUMENT_PREFIX = "search_document: "
QUERY_PREFIX = "search_query: "


class EmbedderUnavailable(RuntimeError):
    """Ollama could not be reached or returned unusable embeddings."""


class OllamaEmbedder:
    def __init__(
        self,
        url: str,
        model: str,
        timeout_s: float = 60.0,
        keep_alive: str = "30m",
        opener: Opener = urlopen,
    ) -> None:
        self.endpoint = url.rstrip("/") + "/api/embed"
        self.model = model
        self.keep_alive = keep_alive
        self.timeout_s = timeout_s
        self._opener = opener

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        """Embed knowledge chunks, with the nomic document prefix."""
        return self.embed([DOCUMENT_PREFIX + t for t in texts])

    def embed_query(self, text: str) -> np.ndarray:
        """Embed one search query, with the nomic query prefix; returns shape (dim,)."""
        return self.embed([QUERY_PREFIX + text])[0]

    def embed(self, texts: list[str]) -> np.ndarray:
        """Return an array of shape (len(texts), dim) with L2-normalised rows."""
        if not texts:
            return np.zeros((0, 0), dtype=np.float32)
        payload = json.dumps({"model": self.model, "input": texts, "keep_alive": self.keep_alive}).encode("utf-8")
        request = Request(
            self.endpoint, data=payload, headers={"Content-Type": "application/json"}, method="POST"
        )
        try:
            with self._opener(request, timeout=self.timeout_s) as response:
                result = json.loads(response.read().decode("utf-8"))
        except (URLError, OSError, ValueError) as error:
            raise EmbedderUnavailable(f"Ollama embed failed: {error}") from error
        embeddings = result.get("embeddings") if isinstance(result, dict) else None
        if not embeddings or len(embeddings) != len(texts):
            raise EmbedderUnavailable(f"Ollama embed returned no usable embeddings: {result!r:.200}")
        vectors = np.asarray(embeddings, dtype=np.float32)
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        return vectors / np.where(norms == 0, 1.0, norms)
