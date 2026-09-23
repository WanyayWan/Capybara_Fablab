from __future__ import annotations

import json
from urllib.error import URLError
from urllib.request import Request, urlopen


SYSTEM_PROMPT = """You are FabAI, an informational assistant for a fabrication lab.
There is no approved knowledge base connected yet. Do not invent lab-specific machine
settings, procedures, authorisations, or safety information. Do not claim a person is
authorised to operate equipment. Give concise general guidance and, when reliable
documentation is unavailable, tell the user to check official documentation or ask
Fab Lab staff."""


class OllamaLLMService:
    """Local Ollama provider. Replace this class to use another LLM later."""

    def __init__(self, model: str = "gemma3:1b") -> None:
        self.model = model

    def answer(self, question: str) -> str:
        payload = json.dumps(
            {
                "model": self.model,
                "system": SYSTEM_PROMPT,
                "prompt": question,
                "stream": False,
                "options": {"temperature": 0.2},
            }
        ).encode("utf-8")
        request = Request(
            "http://127.0.0.1:11434/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=120) as response:
                result = json.loads(response.read().decode("utf-8"))
        except URLError as error:
            raise RuntimeError(f"local LLM unavailable: {error.reason}") from error
        answer = str(result.get("response", "")).strip()
        if not answer:
            raise RuntimeError("local LLM returned an empty response")
        return answer
