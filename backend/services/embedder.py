"""Text embeddings from a local Ollama server (`POST /api/embed`).

Synchronous; callers run it via `asyncio.to_thread`. Rows are L2-normalised so a dot
product is cosine similarity.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

import numpy as np

Opener = Callable[..., Any]


class EmbedderUnavailable(RuntimeError):
    """Ollama could not be reached or returned unusable embeddings."""


class OllamaEmbedder:
    def __init__(
        self, url: str, model: str, timeout_s: float = 60.0, opener: Opener = urlopen
    ) -> None:
        self.endpoint = url.rstrip("/") + "/api/embed"
        self.model = model
        self.timeout_s = timeout_s
        self._opener = opener

    def embed(self, texts: list[str]) -> np.ndarray:
        """Return an array of shape (len(texts), dim) with L2-normalised rows."""
        if not texts:
            return np.zeros((0, 0), dtype=np.float32)
        payload = json.dumps({"model": self.model, "input": texts}).encode("utf-8")
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
