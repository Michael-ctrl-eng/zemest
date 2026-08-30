"""Security headers middleware.

Adds a conservative set of HTTP security headers to *every* response:

* ``X-Content-Type-Options: nosniff`` — blocks MIME-type sniffing.
* ``X-Frame-Options: DENY`` — clickjacking defense (no framing).
* ``X-XSS-Protection: 1; mode=block`` — legacy IE XSS filter (still set;
  harmless on modern browsers, useful on older ones).
* ``Strict-Transport-Security`` — only emitted when the request was over
  HTTPS (or behind a trusted proxy that set ``X-Forwarded-Proto: https``).
  Setting HSTS on a plain-HTTP response would lock users out if they
  later moved off TLS.
* ``Content-Security-Policy`` — restrictive ``default-src 'self'``. The
  dashboard is server-rendered Jinja2 + a small static bundle, so a
  strict CSP doesn't break anything; API JSON responses are unaffected.
* ``Referrer-Policy: strict-origin-when-cross-origin`` — strips query
  string and path from the Referer on cross-origin navigations.
* ``Permissions-Policy`` — denies access to powerful browser features
  (camera, mic, geolocation, …) that an attacker could otherwise try to
  invoke via injected content.

The middleware is intentionally tiny and never raises — header injection
is a real risk if a header value were ever sourced from user input.
"""
from __future__ import annotations

from starlette.types import ASGIApp, Receive, Scope, Send

# Static headers applied to every response.
_STATIC_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    # Restrictive CSP — dashboard is server-rendered + small static bundle.
    # 'unsafe-inline' is needed for inline Jinja2 <style> blocks; we keep it
    # to 'self' otherwise. Adjust if you add a CDN or external fonts.
    "Content-Security-Policy": (
        "default-src 'self'; "
        "img-src 'self' data: https:; "
        "style-src 'self' 'unsafe-inline'; "
        "script-src 'self'; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'"
    ),
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": (
        "geolocation=(), microphone=(), camera=(), "
        "payment=(), usb=(), magnetometer=(), gyroscope=()"
    ),
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
}

# HSTS — only added when the request was HTTPS (or proxied HTTPS).
_HSTS_HEADER = (
    "max-age=31536000; includeSubDomains; preload"
)


def _is_https(scope: Scope) -> bool:
    """Detect whether the request reached us over TLS.

    Honours ``X-Forwarded-Proto`` set by a trusted reverse proxy
    (we only look at the *first* value, which is the original client hop).
    """
    if scope.get("scheme") == "https":
        return True
    # ASGI scope sometimes stores headers as byte pairs.
    for raw_key, raw_val in scope.get("headers") or []:
        if raw_key.lower() == b"x-forwarded-proto":
            try:
                first = raw_val.decode("latin-1").split(",")[0].strip().lower()
                if first == "https":
                    return True
            except Exception:  # noqa: BLE001
                continue
    return False


class SecurityHeadersMiddleware:
    """Pure-ASGI middleware that injects security headers into every response.

    Implemented at the ASGI level (rather than as a Starlette ``BaseHTTPMiddleware``)
    so it adds effectively zero overhead — we just mutate the response headers
    list in place before they hit the wire.

    Usage:
        >>> app.add_middleware(SecurityHeadersMiddleware)
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        is_https = _is_https(scope)

        async def send_wrapper(message):  # type: ignore[no-untyped-def]
            if message["type"] == "http.response.start":
                headers = message.setdefault("headers", [])
                # Build a lowercase set of existing header names so we don't
                # duplicate ones already set by the application (e.g., a route
                # might set its own CSP for an embedded view).
                existing = {k.decode("latin-1").lower() for k, _ in headers if isinstance(k, (bytes, bytearray))}
                for name, value in _STATIC_SECURITY_HEADERS.items():
                    if name.lower() not in existing:
                        headers.append((name.encode("latin-1"), value.encode("latin-1")))
                if is_https and "strict-transport-security" not in existing:
                    headers.append(
                        (b"Strict-Transport-Security", _HSTS_HEADER.encode("latin-1"))
                    )
            await send(message)

        await self.app(scope, receive, send_wrapper)


__all__ = ["SecurityHeadersMiddleware"]
