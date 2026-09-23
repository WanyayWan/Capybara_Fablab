"""Staff notifications: Telegram with On my way / Resolved buttons, or the console.

`format_help_message` and `parse_callback` are pure. `TelegramNotifier` sends the alert
and long-polls `getUpdates` for button presses; stale help ids are ignored. Without
Telegram config, `ConsoleNotifier` prints the message and `/api/help/ack` stands in for
the buttons.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import aiohttp

from config import Settings
from core.pipeline import HelpRequest

log = logging.getLogger(__name__)

HelpUpdateCallback = Callable[[str, str], Awaitable[None]]

ACTIONS = ("ack", "resolve")
TELEGRAM_API = "https://api.telegram.org"
POLL_TIMEOUT_S = 30
RETRY_DELAY_S = 5.0

__all__ = [
    "ConsoleNotifier",
    "HelpRequest",
    "NotifyError",
    "TelegramNotifier",
    "create_notifier",
    "format_help_message",
    "parse_callback",
]


class NotifyError(RuntimeError):
    """Telegram rejected a request or could not be reached."""


def format_help_message(req: HelpRequest) -> str:
    """Staff alert text: EMERGENCY first if urgent, then device, machine, location, time, questions."""
    lines = []
    if req.emergency:
        lines.append("EMERGENCY - urgent staff assistance needed")
    lines += [
        "FabAI help request",
        f"Device: {req.device_id}",
        f"Machine: {req.machine}",
        f"Location: {req.location}",
        f"Time: {req.time:%Y-%m-%d %H:%M}",
    ]
    if req.recent_questions:
        lines.append("Recent questions:")
        lines += [f"{i}. {q}" for i, q in enumerate(req.recent_questions, start=1)]
    else:
        lines.append("Recent questions: no questions yet")
    return "\n".join(lines)


def parse_callback(data: str) -> tuple[str, str, str] | None:
    """Parse `ack:<device_id>:<help_id>` or `resolve:<device_id>:<help_id>`; None if invalid."""
    parts = data.split(":")
    if len(parts) != 3 or parts[0] not in ACTIONS or not all(parts):
        return None
    return parts[0], parts[1], parts[2]


def _keyboard(device_id: str, help_id: str, actions: tuple[str, ...]) -> dict[str, Any]:
    labels = {"ack": "On my way", "resolve": "Resolved"}
    buttons = [{"text": labels[a], "callback_data": f"{a}:{device_id}:{help_id}"} for a in actions]
    return {"inline_keyboard": [buttons]}


@dataclass
class _ActiveHelp:
    help_id: str
    message_id: int | None
    text: str


class TelegramNotifier:
    def __init__(
        self,
        token: str,
        chat_id: str,
        session: aiohttp.ClientSession,
        api_base: str = TELEGRAM_API,
    ) -> None:
        self.chat_id = chat_id
        self._session = session
        self._base = f"{api_base.rstrip('/')}/bot{token}"
        self._offset = 0
        self._active: dict[str, _ActiveHelp] = {}

    async def send_help(self, req: HelpRequest) -> None:
        """sendMessage with an inline keyboard: On my way (ack) and Resolved (resolve)."""
        text = format_help_message(req)
        result = await self._call(
            "sendMessage",
            {
                "chat_id": self.chat_id,
                "text": text,
                "reply_markup": _keyboard(req.device_id, req.help_id, ACTIONS),
            },
        )
        message_id = result.get("message_id") if isinstance(result, dict) else None
        self._active[req.device_id] = _ActiveHelp(req.help_id, message_id, text)

    async def run_ack_poller(self, on_update: HelpUpdateCallback) -> None:
        """Long-poll getUpdates forever and call `on_update(device_id, action)` per button press."""
        while True:
            try:
                await self.poll_once(on_update)
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("Telegram poll failed; retrying in %.0f s", RETRY_DELAY_S)
                await asyncio.sleep(RETRY_DELAY_S)

    async def poll_once(self, on_update: HelpUpdateCallback) -> None:
        """Fetch one batch of updates and handle each button press."""
        updates = await self._call(
            "getUpdates",
            {"offset": self._offset, "timeout": POLL_TIMEOUT_S, "allowed_updates": ["callback_query"]},
            timeout_s=POLL_TIMEOUT_S + 10,
        )
        for update in updates or []:
            self._offset = max(self._offset, int(update["update_id"]) + 1)
            query = update.get("callback_query")
            if query:
                await self._handle_callback(query, on_update)

    async def _handle_callback(self, query: dict[str, Any], on_update: HelpUpdateCallback) -> None:
        parsed = parse_callback(str(query.get("data", "")))
        active = self._active.get(parsed[1]) if parsed else None
        if parsed is None or active is None or active.help_id != parsed[2]:
            await self._answer(query, "This help request is no longer active.")
            return
        action, device_id, help_id = parsed
        who = (query.get("from") or {}).get("first_name") or "staff"
        await self._answer(query, "Thanks!")
        if action == "ack":
            await self._edit(active, f"On my way: {who}", _keyboard(device_id, help_id, ("resolve",)))
        else:
            await self._edit(active, f"Resolved by {who}", None)
            del self._active[device_id]
        await on_update(device_id, action)

    async def _answer(self, query: dict[str, Any], text: str) -> None:
        try:
            await self._call("answerCallbackQuery", {"callback_query_id": query["id"], "text": text})
        except NotifyError:
            log.warning("answerCallbackQuery failed", exc_info=True)

    async def _edit(self, active: _ActiveHelp, status: str, markup: dict[str, Any] | None) -> None:
        if active.message_id is None:
            return
        body: dict[str, Any] = {
            "chat_id": self.chat_id,
            "message_id": active.message_id,
            "text": f"{active.text}\n\n{status}",
        }
        if markup is not None:
            body["reply_markup"] = markup
        try:
            await self._call("editMessageText", body)
        except NotifyError:
            log.warning("editMessageText failed", exc_info=True)

    async def _call(self, method: str, body: dict[str, Any], timeout_s: float = 15.0) -> Any:
        try:
            async with self._session.post(
                f"{self._base}/{method}", json=body, timeout=aiohttp.ClientTimeout(total=timeout_s)
            ) as response:
                data = await response.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as error:
            raise NotifyError(f"Telegram {method} failed: {error}") from error
        if not isinstance(data, dict) or not data.get("ok"):
            description = data.get("description") if isinstance(data, dict) else data
            raise NotifyError(f"Telegram {method} failed: {description}")
        return data.get("result")


class ConsoleNotifier:
    async def send_help(self, req: HelpRequest) -> None:
        """Print the formatted help message."""
        print(
            f"\n=== STAFF ALERT ===\n{format_help_message(req)}\n"
            f"(simulate staff: POST /api/help/ack with device_id {req.device_id})\n",
            flush=True,
        )


def create_notifier(
    settings: Settings, session: aiohttp.ClientSession
) -> TelegramNotifier | ConsoleNotifier:
    """TelegramNotifier if a token and chat id are configured, else ConsoleNotifier."""
    if settings.telegram_enabled:
        return TelegramNotifier(settings.telegram_bot_token, settings.telegram_chat_id, session)
    return ConsoleNotifier()
