"""Integration tests against a running Ollama (pytest -m integration).

Model names and the Ollama URL come from `Settings.load()` (env and `backend/.env`).
IT4 renders its WAV with Windows SAPI at test time, so no audio fixture is committed.
"""

from __future__ import annotations

import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
import pytest

from config import Settings
from services.embedder import OllamaEmbedder
from services.knowledge import KnowledgeBase, knowledge_dirs, load_chunks
from services.llm_service import OllamaChat, OllamaHealth
from services.stt_service import WhisperSTT

pytestmark = pytest.mark.integration

KNOWLEDGE_ROOT = Path(__file__).resolve().parent.parent / "knowledge"
SAMPLE_RATE = 16000
SPOKEN = "How do I load filament into the printer?"


@pytest.fixture(scope="module")
def settings() -> Settings:
    settings = Settings.load()
    if not OllamaHealth(settings.ollama_url).check():
        pytest.skip(f"Ollama not reachable at {settings.ollama_url}")
    return settings


@pytest.fixture(scope="module")
def embedder(settings: Settings) -> OllamaEmbedder:
    return OllamaEmbedder(settings.ollama_url, settings.embed_model, keep_alive=settings.ollama_keep_alive)


def test_IT1_embedder_normalised(embedder: OllamaEmbedder) -> None:
    """IT1: OllamaEmbedder on 2 texts -> shape (2, dim), rows normalised."""
    vectors = embedder.embed_documents(["How do I load filament?", "Can I cut PVC?"])

    assert vectors.ndim == 2
    assert vectors.shape[0] == 2
    assert vectors.shape[1] > 0
    np.testing.assert_allclose(np.linalg.norm(vectors, axis=1), 1.0, atol=1e-5)


def test_IT2_chat_non_empty(settings: Settings) -> None:
    """IT2: OllamaChat simple message -> non-empty string."""
    llm = OllamaChat(
        settings.ollama_url,
        settings.ollama_model,
        keep_alive=settings.ollama_keep_alive,
        num_ctx=settings.ollama_num_ctx,
    )

    reply = llm.chat([{"role": "user", "content": "Reply with the single word OK."}])

    assert isinstance(reply, str)
    assert reply.strip()


def test_IT3_kb_sd_card_32gb(settings: Settings, embedder: OllamaEmbedder) -> None:
    """IT3: real KB, "what is the max SD card size" -> top chunk mentions 32 GB."""
    kb = KnowledgeBase(
        load_chunks(knowledge_dirs(KNOWLEDGE_ROOT)),
        embedder,
        top_k=settings.rag_top_k,
        threshold=settings.rag_threshold,
        machine_boost=settings.rag_machine_boost,
    )

    results = kb.retrieve("what is the max SD card size", machine="3d-printer")

    top = results[0].chunk
    assert "32 GB" in top.text, top.heading


def _synthesise_wav(text: str, path: Path) -> None:
    """Speak `text` into a 16 kHz, 16-bit mono WAV with Windows SAPI."""
    script = (
        "Add-Type -AssemblyName System.Speech; "
        "$fmt = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo("
        f"{SAMPLE_RATE}, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, "
        "[System.Speech.AudioFormat.AudioChannel]::Mono); "
        "$voice = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        f"$voice.SetOutputToWaveFile('{path}', $fmt); "
        f"$voice.Speak('{text}'); $voice.Dispose()"
    )
    subprocess.run(["powershell", "-NoProfile", "-Command", script], check=True, capture_output=True)


def _read_wav(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as wav:
        assert wav.getframerate() == SAMPLE_RATE
        assert wav.getnchannels() == 1
        assert wav.getsampwidth() == 2
        frames = wav.readframes(wav.getnframes())
    return np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0


@pytest.mark.skipif(not sys.platform.startswith("win"), reason="WAV is generated with Windows SAPI")
def test_IT4_whisper_transcribes(tmp_path: Path) -> None:
    """IT4: WhisperSTT on a short WAV -> non-empty text."""
    wav_path = tmp_path / "question.wav"
    _synthesise_wav(SPOKEN, wav_path)
    samples = _read_wav(wav_path)

    text = WhisperSTT(Settings.load().whisper_model).transcribe(samples)

    assert text.strip()
    assert "filament" in text.lower()
