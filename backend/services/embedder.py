"""Text embeddings from a local Ollama server (`POST /api/embed`).

Synchronous; callers run it via `asyncio.to_thread`. Rows are L2-normalised so a dot
product is cosine similarity.
"""

from __future__ import annotations

import numpy as np


class OllamaEmbedder:
    def __init__(self, url: str, model: str, timeout_s: float = 60.0) -> None:
        raise NotImplementedError

    def embed(self, texts: list[str]) -> np.ndarray:
        """Return an array of shape (len(texts), dim) with L2-normalised rows."""
        raise NotImplementedError
