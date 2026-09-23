"""Text to speech on the system default output. `speak(text)` blocks until done.

`create_tts()` picks Windows SAPI, macOS `say`, or a console fallback by platform.
"""

from __future__ import annotations

import base64
import subprocess
import sys
from collections.abc import Callable
from typing import Any

Runner = Callable[..., Any]


class WindowsTTS:
    """Offline Windows SAPI provider using the current default output."""

    def __init__(self, runner: Runner = subprocess.run) -> None:
        self._run = runner

    def speak(self, text: str) -> None:
        if not text.strip():
            return
        encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")
        command = (
            "$text=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('"
            + encoded
            + "')); Add-Type -AssemblyName System.Speech; "
            "$voice=New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            "$voice.Rate=0; $voice.Volume=100; $voice.Speak($text); $voice.Dispose()"
        )
        self._run(
            ["powershell", "-NoProfile", "-Command", command],
            check=True,
            capture_output=True,
            text=True,
        )


class MacTTS:
    """macOS `say` command."""

    def __init__(self, runner: Runner = subprocess.run) -> None:
        self._run = runner

    def speak(self, text: str) -> None:
        if not text.strip():
            return
        self._run(["say", text], check=True)


class ConsoleTTS:
    """Prints instead of speaking (other platforms, headless runs)."""

    def speak(self, text: str) -> None:
        print(f"[FabAI says] {text}", flush=True)


def create_tts(platform: str = sys.platform) -> WindowsTTS | MacTTS | ConsoleTTS:
    if platform.startswith("win"):
        return WindowsTTS()
    if platform == "darwin":
        return MacTTS()
    return ConsoleTTS()
