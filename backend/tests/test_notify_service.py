"""Staff notifications (test-plan: test_notify_service.py).

Telegram HTTP is replaced by `FakeSession`; no test talks to the network."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest

from config import Settings
from core.pipeline import HelpRequest
from services.notify_service import (
    ConsoleNotifier,
    NotifyError,
    TelegramNotifier,
    create_notifier,
    format_help_message,
    parse_callback,
)

TOKEN = "123:abc"
API = f"https://api.telegram.org/bot{TOKEN}"


def make_request(
    questions: list[str] | None = None, emergency: bool = False, help_id: str = "h1"
) -> HelpRequest:
    return HelpRequest(
        device_id="fabai-01",
        machine="3d-printer",
        location="3D Printing Lab",
        time=datetime(2026, 9, 24, 14, 5),
        recent_questions=["how do I load filament", "what size SD card"]
        if questions is None
        else questions,
        emergency=emergency,
        help_id=help_id,
    )


class FakeResponse:
    def __init__(self, payload: dict[str, Any], status: int = 200) -> None:
        self.payload = payload
        self.status = status

    async def json(self, content_type: str | None = None) -> dict[str, Any]:
        return self.payload

    async def __aenter__(self) -> FakeResponse:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None


class FakeSession:
    """Records POSTs; replies from `replies[method]` (a list, consumed in order)."""

    def __init__(self, replies: dict[str, list[dict[str, Any]]] | None = None) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.replies = replies or {}

    def post(self, url: str, json: dict[str, Any], **kwargs: Any) -> FakeResponse:
        self.calls.append((url, json))
        method = url.rsplit("/", 1)[1]
        queue = self.replies.get(method)
        if queue:
            return FakeResponse(queue.pop(0))
        return FakeResponse({"ok": True, "result": {"message_id": 42}})

    def methods(self) -> list[str]:
        return [url.rsplit("/", 1)[1] for url, _ in self.calls]


def callback_update(update_id: int, data: str, name: str = "Priya") -> dict[str, Any]:
    return {
        "update_id": update_id,
        "callback_query": {
            "id": f"cb{update_id}",
            "from": {"first_name": name},
            "data": data,
            "message": {"message_id": 42, "chat": {"id": 555}, "text": "FabAI help request"},
        },
    }


def test_N1_format_normal() -> None:
    """N1: contains device, machine, location, time, questions."""
    text = format_help_message(make_request())
    for part in ["fabai-01", "3d-printer", "3D Printing Lab", "14:05", "how do I load filament", "what size SD card"]:
        assert part in text
    assert "EMERGENCY" not in text


def test_N2_format_emergency() -> None:
    """N2: message starts with EMERGENCY."""
    assert format_help_message(make_request(emergency=True)).startswith("EMERGENCY")


def test_N3_format_no_questions() -> None:
    """N3: no recent questions -> "no questions yet"."""
    assert "no questions yet" in format_help_message(make_request(questions=[]))


def test_N4_parse_callback_ack() -> None:
    """N4: parse_callback("ack:fabai-01:abc") -> ("ack", "fabai-01", "abc")."""
    assert parse_callback("ack:fabai-01:abc") == ("ack", "fabai-01", "abc")
    assert parse_callback("resolve:fabai-02:x9") == ("resolve", "fabai-02", "x9")


@pytest.mark.parametrize("data", ["garbage", "", "ack:fabai-01", "burn:fabai-01:abc", "ack::abc", "ack:a:b:c"])
def test_N5_parse_callback_garbage(data: str) -> None:
    """N5: parse_callback("garbage") -> None."""
    assert parse_callback(data) is None


def test_N6_console_without_token() -> None:
    """N6: create_notifier without token -> ConsoleNotifier."""
    session = FakeSession()
    assert isinstance(create_notifier(Settings(), session), ConsoleNotifier)  # type: ignore[arg-type]
    only_token = Settings(telegram_bot_token=TOKEN)
    assert isinstance(create_notifier(only_token, session), ConsoleNotifier)  # type: ignore[arg-type]
    both = Settings(telegram_bot_token=TOKEN, telegram_chat_id="555")
    assert isinstance(create_notifier(both, session), TelegramNotifier)  # type: ignore[arg-type]


async def test_N7_telegram_send_help() -> None:
    """N7: send_help posts sendMessage with chat_id and 2 inline buttons."""
    session = FakeSession()
    notifier = TelegramNotifier(TOKEN, "555", session)  # type: ignore[arg-type]
    await notifier.send_help(make_request(help_id="abc"))

    url, body = session.calls[0]
    assert url == f"{API}/sendMessage"
    assert body["chat_id"] == "555"
    assert "fabai-01" in body["text"]
    buttons = body["reply_markup"]["inline_keyboard"][0]
    assert [b["callback_data"] for b in buttons] == ["ack:fabai-01:abc", "resolve:fabai-01:abc"]
    assert [b["text"] for b in buttons] == ["On my way", "Resolved"]


async def test_telegram_send_help_error_raises() -> None:
    session = FakeSession({"sendMessage": [{"ok": False, "description": "chat not found"}]})
    notifier = TelegramNotifier(TOKEN, "555", session)  # type: ignore[arg-type]
    with pytest.raises(NotifyError):
        await notifier.send_help(make_request())


async def test_console_notifier_prints(capsys: pytest.CaptureFixture[str]) -> None:
    await ConsoleNotifier().send_help(make_request())
    assert "fabai-01" in capsys.readouterr().out


async def test_poll_ack_then_resolve() -> None:
    """Button presses call on_update, answer the callback, edit the message, advance offset."""
    session = FakeSession(
        {
            "getUpdates": [
                {"ok": True, "result": [callback_update(10, "ack:fabai-01:abc")]},
                {"ok": True, "result": [callback_update(11, "resolve:fabai-01:abc")]},
            ]
        }
    )
    notifier = TelegramNotifier(TOKEN, "555", session)  # type: ignore[arg-type]
    await notifier.send_help(make_request(help_id="abc"))
    updates: list[tuple[str, str]] = []

    async def on_update(device_id: str, action: str) -> None:
        updates.append((device_id, action))

    await notifier.poll_once(on_update)
    await notifier.poll_once(on_update)

    assert updates == [("fabai-01", "ack"), ("fabai-01", "resolve")]
    get_bodies = [body for url, body in session.calls if url.endswith("/getUpdates")]
    assert get_bodies[0]["offset"] == 0
    assert get_bodies[1]["offset"] == 11
    assert session.methods().count("answerCallbackQuery") == 2
    edits = [body for url, body in session.calls if url.endswith("/editMessageText")]
    assert "Priya" in edits[0]["text"]
    ack_buttons = edits[0]["reply_markup"]["inline_keyboard"][0]
    assert [b["callback_data"] for b in ack_buttons] == ["resolve:fabai-01:abc"]
    assert "reply_markup" not in edits[1]


async def test_poll_ignores_stale_help_id() -> None:
    session = FakeSession(
        {"getUpdates": [{"ok": True, "result": [callback_update(5, "ack:fabai-01:old")]}]}
    )
    notifier = TelegramNotifier(TOKEN, "555", session)  # type: ignore[arg-type]
    await notifier.send_help(make_request(help_id="new"))
    updates: list[tuple[str, str]] = []

    async def on_update(device_id: str, action: str) -> None:
        updates.append((device_id, action))

    await notifier.poll_once(on_update)
    assert updates == []
    assert "answerCallbackQuery" in session.methods()
    assert "editMessageText" not in session.methods()
