"""Staff notifications: Telegram with On my way / Resolved buttons, or the console.

`format_help_message` and `parse_callback` are pure. `TelegramNotifier` sends the alert
and long-polls `getUpdates` for button presses; stale help ids are ignored. Without
Telegram config, `ConsoleNotifier` prints the message and `/api/help/ack` stands in for
the buttons.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import aiohttp

from config import Settings
from core.pipeline import HelpRequest

HelpUpdateCallback = Callable[[str, str], Awaitable[None]]

__all__ = [
    "ConsoleNotifier",
    "HelpRequest",
    "TelegramNotifier",
    "create_notifier",
    "format_help_message",
    "parse_callback",
]


def format_help_message(req: HelpRequest) -> str:
    """Staff alert text: EMERGENCY first if urgent, then device, machine, location, time, questions."""
    raise NotImplementedError


def parse_callback(data: str) -> tuple[str, str, str] | None:
    """Parse `ack:<device_id>:<help_id>` or `resolve:<device_id>:<help_id>`; None if invalid."""
    raise NotImplementedError


class TelegramNotifier:
    def __init__(self, token: str, chat_id: str, session: aiohttp.ClientSession) -> None:
        raise NotImplementedError

    async def send_help(self, req: HelpRequest) -> None:
        """sendMessage with an inline keyboard: On my way (ack) and Resolved (resolve)."""
        raise NotImplementedError

    async def run_ack_poller(self, on_update: HelpUpdateCallback) -> None:
        """Long-poll getUpdates forever and call `on_update(device_id, action)` per button press."""
        raise NotImplementedError


class ConsoleNotifier:
    async def send_help(self, req: HelpRequest) -> None:
        """Print the formatted help message."""
        raise NotImplementedError


def create_notifier(
    settings: Settings, session: aiohttp.ClientSession
) -> TelegramNotifier | ConsoleNotifier:
    """TelegramNotifier if a token and chat id are configured, else ConsoleNotifier."""
    raise NotImplementedError
