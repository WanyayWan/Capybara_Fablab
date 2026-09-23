"""Chat completions from a local Ollama server (`POST /api/chat`).

Synchronous; callers run it via `asyncio.to_thread`. The system prompt is built by
`core.prompts.build_messages`, not here.
"""

from __future__ import annotations

import json
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
