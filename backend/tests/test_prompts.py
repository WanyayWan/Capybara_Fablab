"""Prompt building (test-plan: test_prompts.py)."""

from dataclasses import dataclass
from datetime import datetime

from core.device_state import HelpStatus
from core.prompts import build_messages


@dataclass
class Chunk:
    source: str
    heading: str
    text: str


CHUNKS = [
    Chunk("3D printer guide", "SD card", "Use an SD card up to 32 GB."),
    Chunk("Laser cutter guide", "Banned materials", "Never cut PVC."),
]


def build(**overrides: object) -> list[dict[str, str]]:
    args: dict[str, object] = {
        "machine": "3d-printer",
        "location": "3D Printing Lab",
        "chunks": CHUNKS,
        "history": [],
        "question": "what SD card?",
        "help_status": HelpStatus.NONE,
    }
    args.update(overrides)
    return build_messages(**args)  # type: ignore[arg-type]


def system_of(messages: list[dict[str, str]]) -> str:
    assert messages[0]["role"] == "system"
    return messages[0]["content"]


def test_P1_chunks_in_system() -> None:
    """P1: system message contains each [source] heading."""
    system = system_of(build())
    assert "[3D printer guide] SD card: Use an SD card up to 32 GB." in system
    assert "[Laser cutter guide] Banned materials: Never cut PVC." in system


def test_P2_history_between_system_and_question() -> None:
    """P2: history between system and new question."""
    history = [
        {"role": "user", "content": "how do I load filament"},
        {"role": "assistant", "content": "Heat the nozzle. Say next when you're ready."},
    ]
    messages = build(history=history, question="next")
    assert len(messages) == 4
    assert messages[1:3] == history
    assert messages[-1] == {"role": "user", "content": "next"}


def test_P3_help_pending_status() -> None:
    """P3: help pending -> system contains "called" and "waiting"."""
    called_at = datetime(2026, 9, 23, 14, 5)
    system = system_of(build(help_status=HelpStatus.PENDING, help_called_at=called_at))
    assert "called" in system
    assert "waiting" in system
    assert "14:05" in system


def test_P3b_help_pending_without_time() -> None:
    """Pending without a timestamp still says called and waiting."""
    system = system_of(build(help_status=HelpStatus.PENDING))
    assert "called" in system
    assert "waiting" in system


def test_P4_help_acknowledged_status() -> None:
    """P4: help acknowledged -> system contains "on the way"."""
    system = system_of(build(help_status=HelpStatus.ACKNOWLEDGED))
    assert "on the way" in system


def test_P4b_help_none_status() -> None:
    """No help requested -> staff status says not called."""
    assert "Staff status: not called" in system_of(build())


def test_P5_machine_and_location() -> None:
    """P5: machine + location appear in system message."""
    system = system_of(build(machine="laser-cutter", location="Laser Lab"))
    assert "laser-cutter" in system
    assert "Laser Lab" in system


def test_P6_rules_present() -> None:
    """P6: system mentions one step at a time and never authorising."""
    system = system_of(build()).lower()
    assert "one step at a time" in system
    assert "say next when you're ready" in system
    assert "never say someone is authorised" in system
    assert "call staff" in system
