"""Chat completions from a local Ollama server (`POST /api/chat`).

Synchronous; callers run it via `asyncio.to_thread`. The system prompt is built by
`core.prompts.build_messages`, not here. Every chat request (warm-up included) sends the
same `options` and `keep_alive`, and logs them with its duration and Ollama's model load
time. `OllamaHealth` backs the `/health` Ollama check.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

log = logging.getLogger(__name__)

Opener = Callable[..., Any]

NS_PER_S = 1e9


class LLMUnavailable(RuntimeError):
    """Ollama could not be reached or returned an empty reply."""


class OllamaChat:
    def __init__(
        self,
        url: str,
        model: str,
        timeout_s: float = 120.0,
        keep_alive: str = "30m",
        num_ctx: int = 4096,
        temperature: float = 0.2,
        opener: Opener = urlopen,
    ) -> None:
        self.endpoint = url.rstrip("/") + "/api/chat"
        self.model = model
        self.keep_alive = keep_alive
        self.options: dict[str, float | int] = {"temperature": temperature, "num_ctx": num_ctx}
        self.timeout_s = timeout_s
        self._opener = opener

    def chat(self, messages: list[dict[str, str]]) -> str:
        """Send the conversation and return the assistant's reply text."""
        payload = json.dumps(
            {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "options": self.options,
                "keep_alive": self.keep_alive,
            }
        ).encode("utf-8")
        request = Request(
            self.endpoint, data=payload, headers={"Content-Type": "application/json"}, method="POST"
        )
        started = time.perf_counter()
        try:
            with self._opener(request, timeout=self.timeout_s) as response:
                result = json.loads(response.read().decode("utf-8"))
        except (URLError, OSError, ValueError) as error:
            raise LLMUnavailable(f"local LLM unavailable: {error}") from error
        message = result.get("message") if isinstance(result, dict) else None
        reply = str(message.get("content", "")).strip() if isinstance(message, dict) else ""
        if not reply:
            raise LLMUnavailable(f"local LLM returned an empty response: {result!r:.200}")
        log.info(
            "chat %s options=%s keep_alive=%s: %.2f s (load %.2f s, prompt %s tokens)",
            self.model,
            self.options,
            self.keep_alive,
            time.perf_counter() - started,
            float(result.get("load_duration", 0)) / NS_PER_S,
            result.get("prompt_eval_count", "?"),
        )
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
