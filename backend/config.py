"""FabAI settings, loaded from environment variables and `backend/.env`.

Real environment variables win over values in `.env`. Unset values use the defaults
from build-plan section 4. The device registry lives here, not in the environment.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, fields
from pathlib import Path

from dotenv import dotenv_values

BACKEND_ROOT = Path(__file__).resolve().parent
DEFAULT_ENV_FILE = BACKEND_ROOT / ".env"

DEVICES: dict[str, dict[str, str]] = {
    "fabai-01": {"machine": "3d-printer", "location": "3D Printing Lab"},
    "fabai-02": {"machine": "laser-cutter", "location": "Laser Lab"},
}
FALLBACK_DEVICE: dict[str, str] = {"machine": "all", "location": "Fab Lab"}


def get_device(device_id: str) -> dict[str, str]:
    """Return a copy of the device's machine and location, or the Fab Lab fallback."""
    return dict(DEVICES.get(device_id, FALLBACK_DEVICE))


@dataclass(frozen=True)
class Settings:
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "gemma3:4b"
    embed_model: str = "nomic-embed-text"
    ollama_keep_alive: str = "30m"
    ollama_num_ctx: int = 4096
    whisper_model: str = "base.en"
    rag_top_k: int = 3
    rag_threshold: float = 0.5
    rag_machine_boost: float = 0.05
    session_timeout_s: float = 120.0
    session_max_turns: int = 6
    min_record_s: float = 0.5
    max_record_s: float = 15.0
    pre_roll_s: float = 0.5
    help_ack_clear_s: float = 600.0
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    port: int = 8000

    @property
    def telegram_enabled(self) -> bool:
        return bool(self.telegram_bot_token and self.telegram_chat_id)

    @classmethod
    def load(
        cls,
        env_file: Path | None = DEFAULT_ENV_FILE,
        environ: Mapping[str, str] | None = None,
    ) -> Settings:
        """Build settings from `env_file` (if it exists) overlaid with `environ`."""
        values: dict[str, str] = {}
        if env_file is not None and env_file.is_file():
            values.update({k: v for k, v in dotenv_values(env_file).items() if v is not None})
        values.update(os.environ if environ is None else environ)
        return cls.from_mapping(values)

    @classmethod
    def from_mapping(cls, values: Mapping[str, str]) -> Settings:
        """Parse upper-case setting names (e.g. `RAG_TOP_K`) into typed fields."""
        kwargs: dict[str, object] = {}
        for field in fields(cls):
            raw = values.get(field.name.upper())
            if raw is None or raw.strip() == "":
                continue
            kwargs[field.name] = _parse(field.name, field.type, raw.strip())
        return cls(**kwargs)


def _parse(name: str, type_name: object, raw: str) -> object:
    try:
        if type_name in (int, "int"):
            return int(raw)
        if type_name in (float, "float"):
            return float(raw)
    except ValueError as error:
        raise ValueError(f"Invalid value for {name.upper()}: {raw!r}") from error
    return raw
