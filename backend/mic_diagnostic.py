"""Check the default microphone end to end: record, play back, transcribe.

Uses the same `Recorder` (always-open stream with pre-roll) and `WhisperSTT` as the
backend, so a passing run means the headset works for FabAI.
"""

from __future__ import annotations

import argparse
import math
import time
import wave
from pathlib import Path

import numpy as np
import sounddevice as sd

from config import Settings
from services.audio_service import Recorder, list_input_devices
from services.stt_service import WhisperSTT

ROOT = Path(__file__).resolve().parent
WAV_PATH = ROOT / "mic_test.wav"
SAMPLE_RATE = 16000
DURATION_SECONDS = 5


def meter(level: float) -> str:
    bars = min(24, int(math.sqrt(level) * 90))
    return "#" * bars or "."


def write_wav(samples: np.ndarray) -> None:
    pcm = np.clip(samples * 32767, -32768, 32767).astype(np.int16)
    with wave.open(str(WAV_PATH), "wb") as file:
        file.setnchannels(1)
        file.setsampwidth(2)
        file.setframerate(SAMPLE_RATE)
        file.writeframes(pcm.tobytes())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--delay", type=int, default=0, help="Seconds to wait before recording")
    args = parser.parse_args()
    settings = Settings.load()

    devices = list_input_devices()
    default = next((device for device in devices if device["default"]), None)
    print("FabAI Microphone Test")
    print("\nAvailable audio input devices:")
    for device in devices:
        marker = " (default)" if device["default"] else ""
        print(f'  [{device["index"]}] {device["name"]}{marker}')
    if not default:
        raise RuntimeError("No default audio input device is available.")
    print(f'\nDevice: {default["name"]}')

    recorder = Recorder(
        sample_rate=SAMPLE_RATE,
        max_seconds=DURATION_SECONDS + settings.pre_roll_s,
        pre_roll_s=settings.pre_roll_s,
    )
    recorder.open()
    try:
        if args.delay:
            print(f"Recording begins in {args.delay} seconds. Prepare to speak.", flush=True)
            time.sleep(args.delay)
        print("Speak now...\n", flush=True)
        recorder.start()
        end = time.monotonic() + DURATION_SECONDS
        while time.monotonic() < end:
            print(f"\rAudio: {meter(recorder.level):<24}  RMS {recorder.level:.4f}", end="", flush=True)
            time.sleep(0.05)
        samples = recorder.stop()
    finally:
        recorder.close()

    print("\n\nRecording complete.")
    if samples.size == 0:
        raise RuntimeError("No audio samples were captured.")
    write_wav(samples)
    peak = float(np.max(np.abs(samples)))
    rms = float(np.sqrt(np.mean(np.square(samples))))
    print(f"Recording duration: {samples.size / SAMPLE_RATE:.2f} seconds "
          f"(includes {recorder.last_pre_roll_samples / SAMPLE_RATE:.2f} s pre-roll)")
    print(f"Sample rate: {SAMPLE_RATE} Hz")
    print(f"Peak audio level: {peak:.4f}")
    print(f"RMS audio level: {rms:.4f}")
    print(f"WAV file: {WAV_PATH}")

    print("\nPlaying the recording through the default output...", flush=True)
    sd.play(samples, samplerate=SAMPLE_RATE)
    sd.wait()
    print("Playback complete.")

    stt = WhisperSTT(settings.whisper_model)
    print(f"\nTranscribing with {settings.whisper_model}...", flush=True)
    transcription = stt.transcribe(samples)
    print(f'Transcription:\n"{transcription or "[No speech detected]"}"')


if __name__ == "__main__":
    main()
