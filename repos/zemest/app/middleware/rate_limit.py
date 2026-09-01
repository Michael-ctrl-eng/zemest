"""Per-IP and per-tenant rate limiting using slowapi.

This module wraps :mod:`slowapi` (MIT-licensed, supports Redis as a
storage backend) with a custom key function that picks the *right*
identifier for each request:

* Anonymous requests (no JWT) → keyed by client IP.
* Authenticated requests → keyed by ``tenant:{tenant_id}`` so a single
  attacker cannot get around the per-tenant budget by cycling IPs.

Wiring
------
``setup_rate_limiting(app)`` registers the limiter on
``app.state.limiter``, installs the ``RateLimitExceeded`` exception
handler (which returns a ``429`` with a ``Retry-After`` header), and
adds ``SlowAPIMiddleware``.

Endpoints opt in by decorating with ``@limiter.limit("5/minute")`` and
declaring ``request: Request`` as a parameter. See ``app/api/auth.py``
for examples.

Graceful degradation
--------------------
If ``REDIS_URL`` is unset or unreachable, slowapi falls back to an
in-memory store (single-process only). This keeps the limiter usable in
tests and local dev without Redis.
"""
from __future__ import annotations

import logging
from typing import Awaitable, Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Lazy imports — slowapi is an optional dep at import time so the rest of
# the app can boot even if it isn't installed yet (e.g., during a fresh
# `pip install -r requirements.txt` run).
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from slowapi.middleware import SlowAPIMiddleware
    from slowapi.util import get_remote_address

    _SLOWAPI_AVAILABLE = True
except ImportError:  # pragma: no cover — slowapi is in requirements.txt
    _SLOWAPI_AVAILABLE = False
    Limiter = None  # type: ignore[assignment,misc]
    RateLimitExceeded = None  # type: ignore[assignment,misc]
    SlowAPIMiddleware = None  # type: ignore[assignment,misc]
    get_remote_address = None  # type: ignore[assignment,misc]
    _rate_limit_exceeded_handler = None  # type: ignore[assignment,misc]


def get_rate_limit_key(request: Request) -> str:
    """Rate-limit key: IP for anonymous, ``tenant:{id}`` for authenticated.

    The JWT decode is best-effort — if the token is missing, malformed,
    or expired we fall back to the IP. This keeps the limiter's failure
    mode as "fail-open per-IP" rather than "deny everything".
    """
    client_ip = get_remote_address(request) if get_remote_address else None

    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        try:
            # Lazy import to avoid a circular dependency at module import time.
            from app.utils.security import decode_token

            token = auth[7:]
            payload = decode_token(token)
            if payload:
                tenant_id = payload.get("tenant_id")
                if tenant_id:
                    return f"tenant:{tenant_id}"
                # Authenticated but no tenant_id in token — fall back to user sub.
                sub = payload.get("sub")
                if sub:
                    return f"user:{sub}"
        except Exception:  # noqa: BLE001 — never break the request
            pass

    return f"ip:{client_ip or 'unknown'}"


# Module-level singleton limiter. Constructed lazily so importing this
# module never touches Redis.
limiter: Limiter | None = None


def _build_limiter() -> "Limiter":
    """Construct the slowapi Limiter, preferring Redis if configured.

    Probes Redis ONCE at construction; if it's unreachable we permanently
    fall back to the in-memory store so a dead Redis can never 500 requests
    (the docstring promised fail-open — this makes it real).
    """
    if not _SLOWAPI_AVAILABLE:
        raise RuntimeError("slowapi is not installed — add it to requirements.txt")

    storage_uri = settings.REDIS_URL or "memory://"
    if storage_uri.startswith("redis://"):
        try:
            import redis as _redis

            client = _redis.Redis.from_url(storage_uri, socket_connect_timeout=1.0)
            client.ping()
        except Exception:  # noqa: BLE001 — Redis optional, fail open to memory
            logger.warning(
                "Redis at %s unreachable — rate limiter falling back to in-memory storage",
                storage_uri,
            )
            storage_uri = "memory://"
    return Limiter(
        key_func=get_rate_limit_key,
        storage_uri=storage_uri,
        # Master switch (tests set RATELIMIT_ENABLED=false — see config.py)
        enabled=bool(getattr(settings, "RATELIMIT_ENABLED", True)),
    )


def get_limiter() -> "Limiter":
    """Return the singleton limiter, creating it on first use."""
    global limiter
    if limiter is None:
        limiter = _build_limiter()
    return limiter


def _rate_limit_handler(request: Request, exc: "RateLimitExceeded") -> JSONResponse:
    """Custom 429 handler that always includes a ``Retry-After`` header.

    slowapi's default handler omits ``Retry-After`` in some configurations;
    clients (and Meta's webhook retry loop) rely on it to back off cleanly.
    """
    retry_after = getattr(exc, "retry_after", None) or 60
    response = JSONResponse(
        status_code=429,
        content={
            "detail": "Rate limit exceeded",
            "retry_after": int(retry_after),
        },
        headers={
            "Retry-After": str(int(retry_after)),
            "X-RateLimit-Limit": str(getattr(exc, "limit", "")),
        },
    )
    return response


def setup_rate_limiting(app: FastAPI) -> None:
    """Wire the slowapi limiter + middleware into ``app``.

    Idempotent — safe to call multiple times (e.g., if main.py is reloaded).
    """
    if not _SLOWAPI_AVAILABLE:
        logger.warning("slowapi not installed — rate limiting disabled")
        return

    lim = get_limiter()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)
    # Avoid double-registration on reload.
    middleware_classes = {m.cls.__name__ for m in app.user_middleware}
    if "SlowAPIMiddleware" not in middleware_classes:
        app.add_middleware(SlowAPIMiddleware)


__all__ = [
    "get_rate_limit_key",
    "get_limiter",
    "setup_rate_limiting",
    "limiter",
]
