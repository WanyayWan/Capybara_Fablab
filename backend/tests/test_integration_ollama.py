"""Integration tests against a running Ollama (pytest -m integration)."""

import pytest

pytestmark = pytest.mark.integration


@pytest.mark.skip(reason="not implemented")
def test_IT1_embedder_normalised() -> None:
    """IT1: OllamaEmbedder on 2 texts -> shape (2, dim), rows normalised."""


@pytest.mark.skip(reason="not implemented")
def test_IT2_chat_non_empty() -> None:
    """IT2: OllamaChat simple message -> non-empty string."""


@pytest.mark.skip(reason="not implemented")
def test_IT3_kb_sd_card_32gb() -> None:
    """IT3: real KB, "what is the max SD card size" -> top chunk mentions 32 GB."""


@pytest.mark.skip(reason="not implemented")
def test_IT4_whisper_transcribes() -> None:
    """IT4: WhisperSTT on a short WAV -> non-empty text."""
