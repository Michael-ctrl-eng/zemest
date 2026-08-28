"""Basic bot detection — logs suspicious traffic without blocking.

Why log-only?
-------------
This service legitimately serves:

* The dashboard (regular browsers).
* The Facebook / Instagram / WhatsApp webhooks (server-to-server, agent
  like ``facebookexternalua``).
* Programmatic API clients (the merchant's own scripts using our SDK).

A blanket block on ``curl`` / ``python-requests`` / ``scrapy`` would
break all three of those. So this middleware is purely observability:
it flags obvious scraping patterns (well-known crawler UAs with no
auth token) in the security log so an analyst can correlate with rate
limit / WAF events and decide whether to IP-ban via the admin API.

How it works
------------
``is_likely_bot(user_agent)`` does a case-insensitive substring match
against a list of well-known crawler signatures. The middleware calls
it on every request, attaches a ``request.state.is_likely_bot`` flag,
and emits a ``logger.info`` line for flagged requests with no auth
header (the highest-signal subset).
"""
from __future__ import annotations

import logging

from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)

# Substrings that indicate a well-known crawler / scraper. We match on
# substring (not equality) so versioned UAs (``curl/8.4.0``) still match.
BOT_USER_AGENTS: list[str] = [
    "scrapy",
    "curl",
    "wget",
    "python-requests",
    "python-httpx",
    "httpx/",
    "aiohttp",
    "go-http-client",
    "java/",
    "okhttp",
    "bot",
    "crawler",
    "spider",
    "scraper",
    "headlesschrome",
    "phantomjs",
    "selenium",
    "facebookexternalua",  # Meta's crawler — we want to LOG but not block
    "whatsapp",
    "telegrambot",
    "googlebot",
    "bingbot",
    "baiduspider",
    "yandexbot",
    "applebot",
    "twitterbot",
    "linkedinbot",
    "slackbot",
    "discordbot",
]


def is_likely_bot(user_agent: str | None) -> bool:
    """Return True if ``user_agent`` looks like a known crawler/scraper.

    Returns ``False`` for empty / ``None`` UAs (a missing UA is suspicious
    in a different way — handled by the rate limiter, not here).
    """
    if not user_agent or not isinstance(user_agent, str):
        return False
    ua_lower = user_agent.lower()
    return any(bot_ua in ua_lower for bot_ua in BOT_USER_AGENTS)


class BotDetectionMiddleware:
    """ASGI middleware that tags requests with ``is_likely_bot`` and logs them.

    Adds ``request.state.is_likely_bot`` (bool) for downstream code (e.g.,
    a stricter rate-limit policy could be applied to flagged requests).
    Emits a single ``logger.info`` line per flagged request — never blocks.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        user_agent = ""
        auth_header = ""
        for raw_key, raw_val in scope.get("headers") or []:
            if raw_key.lower() == b"user-agent":
                try:
                    user_agent = raw_val.decode("latin-1")
                except Exception:  # noqa: BLE001
                    user_agent = ""
            elif raw_key.lower() == b"authorization":
                try:
                    auth_header = raw_val.decode("latin-1")
                except Exception:  # noqa: BLE001
                    auth_header = ""

        bot = is_likely_bot(user_agent)
        # Stash on scope — set directly on scope (not scope["state"], which
        # Starlette initializes lazily as a State() object downstream). This
        # way downstream code can read request.scope.get("is_likely_bot").
        scope["is_likely_bot"] = bot
        scope["bot_user_agent"] = user_agent

        if bot and not auth_header:
            # Unauthenticated crawler — the highest-signal case for the
            # security log. We don't log authed requests (could be a legit
            # API client) to keep the log volume manageable.
            client_ip = (scope.get("client") or [None])[0]
            path = scope.get("path", "")
            method = scope.get("method", "")
            logger.info(
                "bot_detected ua=%r ip=%s method=%s path=%s",
                user_agent[:120], client_ip, method, path,
            )

        await self.app(scope, receive, send)


__all__ = [
    "BOT_USER_AGENTS",
    "is_likely_bot",
    "BotDetectionMiddleware",
]
