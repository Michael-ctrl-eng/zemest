"""Optional Telegram notifications for admin alerts (reports, abuse signals).

Wiring: set ``TELEGRAM_BOT_TOKEN`` + ``TELEGRAM_ADMIN_CHAT_ID`` in the
environment. When either is missing every call is a silent no-op — the
feature is fully inert until the operator configures it, and it NEVER
affects the request path (fire-and-forget background task, all failures
logged and swallowed).

Setup (one-time):
1. Talk to @BotFather on Telegram → /newbot → copy the bot token.
2. Send any message to your new bot (opens the chat).
3. Visit https://api.telegram.org/bot<TOKEN>/getUpdates and copy your
   chat id from ``result[0].message.chat.id``.
4. Set both env vars and restart.
"""
from __future__ import annotations

import asyncio
import logging

from app.config import get_settings

logger = logging.getLogger(__name__)

_TELEGRAM_API = "https://api.telegram.org"


def telegram_configured() -> bool:
    try:
        s = get_settings()
        return bool(s.TELEGRAM_BOT_TOKEN and s.TELEGRAM_ADMIN_CHAT_ID)
    except Exception:  # noqa: BLE001 — settings must never break notifications
        return False


async def send_admin_message(text: str) -> bool:
    """Send a message to the admin chat. Returns True on success.

    Plain HTTP POST, short timeout, never raises to the caller path.
    """
    s = get_settings()
    if not (s.TELEGRAM_BOT_TOKEN and s.TELEGRAM_ADMIN_CHAT_ID):
        return False
    import httpx

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{_TELEGRAM_API}/bot{s.TELEGRAM_BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": s.TELEGRAM_ADMIN_CHAT_ID,
                    "text": text[:4000],
                    "parse_mode": "HTML",
                },
            )
            return resp.status_code == 200
    except Exception as e:  # noqa: BLE001 — notification must never bubble up
        logger.warning("Telegram notify failed: %s", e)
        return False


def notify_admin_async(text: str) -> None:
    """Fire-and-forget variant used from request handlers.

    Schedules the send on the running loop; the HTTP call and every failure
    happen entirely off the request path.
    """
    if not telegram_configured():
        return
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_send_swallowing(text))
    except RuntimeError:  # no running loop (tests/scripts) — skip
        pass


async def _send_swallowing(text: str) -> None:
    try:
        await send_admin_message(text)
    except Exception:  # noqa: BLE001
        pass


__all__ = ["telegram_configured", "send_admin_message", "notify_admin_async"]
