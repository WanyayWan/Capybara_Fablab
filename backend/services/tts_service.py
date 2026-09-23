from __future__ import annotations

import base64
import subprocess


class WindowsTTSService:
    """Offline Windows SAPI provider using the current default output."""

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
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            check=True,
            capture_output=True,
            text=True,
        )
