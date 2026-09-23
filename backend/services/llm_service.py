"""Chat completions from a local Ollama server (`POST /api/chat`).

Synchronous; callers run it via `asyncio.to_thread`. The system prompt is built by
`core.prompts.build_messages`, not here. `OllamaHealth` backs the `/health` Ollama check.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

Opener = Callable[..., Any]


class LLMUnavailable(RuntimeError):
    """Ollama could not be reached or returned an empty reply."""


class OllamaChat:
    def __init__(
        self, url: str, model: str, timeout_s: float = 120.0, opener: Opener = urlopen
    ) -> None:
        self.endpoint = url.rstrip("/") + "/api/chat"
        self.model = model
        self.timeout_s = timeout_s
        self._opener = opener

    def chat(self, messages: list[dict[str, str]]) -> str:
        """Send the conversation and return the assistant's reply text."""
        payload = json.dumps(
            {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "options": {"temperature": 0.2, "num_ctx": 8192},
            }
        ).encode("utf-8")
        request = Request(
            self.endpoint, data=payload, headers={"Content-Type": "application/json"}, method="POST"
        )
        try:
            with self._opener(request, timeout=self.timeout_s) as response:
                result = json.loads(response.read().decode("utf-8"))
        except (URLError, OSError, ValueError) as error:
            raise LLMUnavailable(f"local LLM unavailable: {error}") from error
        message = result.get("message") if isinstance(result, dict) else None
        reply = str(message.get("content", "")).strip() if isinstance(message, dict) else ""
        if not reply:
            raise LLMUnavailable(f"local LLM returned an empty response: {result!r:.200}")
        return reply


class OllamaHealth:
    """Is Ollama reachable? `GET /api/tags` with a short timeout, cached for `ttl_s`
    (build-plan section 9.9) so `/health` polling doesn't hammer it."""

    def __init__(
        self,
        url: str,
        timeout_s: float = 1.0,
        ttl_s: float = 10.0,
        opener: Opener = urlopen,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.endpoint = url.rstrip("/") + "/api/tags"
        self.timeout_s = timeout_s
        self.ttl_s = ttl_s
        self._opener = opener
        self._clock = clock
        self._cached: tuple[float, bool] | None = None

    def check(self) -> bool:
        now = self._clock()
        if self._cached is not None and now - self._cached[0] < self.ttl_s:
            return self._cached[1]
        try:
            with self._opener(Request(self.endpoint, method="GET"), timeout=self.timeout_s) as response:
                ok = isinstance(json.loads(response.read().decode("utf-8")), dict)
        except (URLError, OSError, ValueError):
            ok = False
        self._cached = (now, ok)
        return ok
