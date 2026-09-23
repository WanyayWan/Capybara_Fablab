"""WhisperSTT and TTS selection with fakes (no model download, no audio output)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest

from services.stt_service import GLOSSARY, WhisperSTT
from services.tts_service import ConsoleTTS, MacTTS, WindowsTTS, create_tts


class FakeWhisperModel:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def transcribe(self, audio: np.ndarray, **kwargs: Any) -> tuple[list[SimpleNamespace], None]:
        self.calls.append(kwargs)
        return [SimpleNamespace(text=" Load the "), SimpleNamespace(text="filament. ")], None


def test_stt_lazy_loads_once_and_transcribes() -> None:
    model = FakeWhisperModel()
    loads: list[str] = []

    def factory(name: str) -> FakeWhisperModel:
        loads.append(name)
        return model

    stt = WhisperSTT("base.en", model_factory=factory)
    assert loads == []
    samples = np.ones(16000, dtype=np.float32)
    assert stt.transcribe(samples) == "Load the filament."
    stt.transcribe(samples)
    assert loads == ["base.en"]
    kwargs = model.calls[0]
    assert kwargs["language"] == "en"
    assert kwargs["beam_size"] == 5
    assert kwargs["vad_filter"] is True
    assert kwargs["initial_prompt"] == GLOSSARY


def test_stt_empty_samples_skip_model() -> None:
    loads: list[str] = []
    stt = WhisperSTT("base.en", model_factory=lambda name: loads.append(name))  # type: ignore[arg-type,func-returns-value]
    assert stt.transcribe(np.zeros(0, dtype=np.float32)) == ""
    assert loads == []


@pytest.mark.parametrize(
    ("platform", "cls"),
    [("win32", WindowsTTS), ("darwin", MacTTS), ("linux", ConsoleTTS)],
)
def test_create_tts_by_platform(platform: str, cls: type) -> None:
    assert isinstance(create_tts(platform), cls)


def test_windows_tts_runs_powershell_sapi() -> None:
    calls: list[list[str]] = []
    tts = WindowsTTS(runner=lambda args, **kw: calls.append(args))
    tts.speak("Hello there")
    tts.speak("   ")
    assert len(calls) == 1
    assert calls[0][0] == "powershell"
    assert "System.Speech" in calls[0][-1]


def test_mac_tts_uses_say() -> None:
    calls: list[list[str]] = []
    MacTTS(runner=lambda args, **kw: calls.append(args)).speak("Hello")
    assert calls == [["say", "Hello"]]


def test_console_tts_prints(capsys: pytest.CaptureFixture[str]) -> None:
    ConsoleTTS().speak("Hello")
    assert "Hello" in capsys.readouterr().out
