from __future__ import annotations

import math
import argparse
import time
import wave
from pathlib import Path

import numpy as np
import sounddevice as sd

from services.audio_service import AudioService, Recording
from services.stt_service import WhisperSTTService

ROOT = Path(__file__).resolve().parent
WAV_PATH = ROOT / "mic_test.wav"
SAMPLE_RATE = 16000
CHANNELS = 1
DURATION_SECONDS = 5


def meter(level: float) -> str:
    bars = min(24, int(math.sqrt(level) * 90))
    return "#" * bars or "."


def write_wav(samples: np.ndarray) -> None:
    pcm = np.clip(samples * 32767, -32768, 32767).astype(np.int16)
    with wave.open(str(WAV_PATH), "wb") as file:
        file.setnchannels(CHANNELS)
        file.setsampwidth(2)
        file.setframerate(SAMPLE_RATE)
        file.writeframes(pcm.tobytes())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--delay", type=int, default=0, help="Seconds to wait before recording")
    args = parser.parse_args()
    audio = AudioService()
    devices = audio.list_input_devices()
    default = next((device for device in devices if device["default"]), None)

    print("FabAI Microphone Test")
    print("\nAvailable Windows audio input devices:")
    for device in devices:
        marker = " (default)" if device["default"] else ""
        print(f'  [{device["index"]}] {device["name"]}{marker}')
    if not default:
        raise RuntimeError("No default Windows audio input device is available.")

    print(f'\nDevice: {default["name"]}')
    if args.delay:
        print(f"Recording begins in {args.delay} seconds. Prepare to speak.", flush=True)
        time.sleep(args.delay)
    print("Speak now...\n", flush=True)
    chunks: list[np.ndarray] = []

    def callback(indata: np.ndarray, frame_count: int, time_info, status) -> None:
        if status:
            print(f"Audio input status: {status}")
        chunk = indata.copy()
        chunks.append(chunk)
        level = float(np.sqrt(np.mean(np.square(chunk))))
        print(f"\rAudio: {meter(level):<24}  RMS {level:.4f}", end="", flush=True)

    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype="float32",
        blocksize=800,
        callback=callback,
    ):
        time.sleep(DURATION_SECONDS)

    print("\n\nRecording complete.")
    samples = np.concatenate(chunks, axis=0).reshape(-1) if chunks else np.array([], dtype=np.float32)
    if samples.size == 0:
        raise RuntimeError("No audio samples were captured.")
    write_wav(samples)
    peak = float(np.max(np.abs(samples)))
    rms = float(np.sqrt(np.mean(np.square(samples))))
    print(f"Recording duration: {samples.size / SAMPLE_RATE:.2f} seconds")
    print(f"Sample rate: {SAMPLE_RATE} Hz")
    print(f"Channels: {CHANNELS}")
    print(f"Peak audio level: {peak:.4f}")
    print(f"RMS audio level: {rms:.4f}")
    print(f"WAV file: {WAV_PATH}")

    print("\nPlaying the recording through the Windows default output...", flush=True)
    sd.play(samples, samplerate=SAMPLE_RATE)
    sd.wait()
    print("Playback complete.")

    stt = WhisperSTTService()
    print("\nTranscribing...", flush=True)
    transcription = stt.transcribe(Recording(samples=samples, sample_rate=SAMPLE_RATE))
    print(f'Transcription:\n"{transcription or "[No speech detected]"}"')


if __name__ == "__main__":
    main()
