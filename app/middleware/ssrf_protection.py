"""SSRF (Server-Side Request Forgery) protection.

Used by any code path that fetches an external URL supplied by a user
(product URL import, knowledge-base crawler, Facebook webhook fetch, …).

Public API:
    >>> is_safe_url("https://example.com/")
    (True, "ok")
    >>> is_safe_url("http://169.254.169.254/latest/meta-data/")
    (False, "blocked: metadata endpoint")

    >>> client = SafeHTTPClient()
    >>> await client.get("https://example.com/")  # validated pre+post-redirect

The functions in this module NEVER raise — they always return
``(bool, reason)`` so callers can use them directly in
``if not safe: ...`` without try/except noise. ``SafeHTTPClient`` itself
*does* raise ``ValueError`` for blocked URLs so the caller can surface a
clear error message to the user (and so unit tests can assert on it).
"""
from __future__ import annotations

import ipaddress
import logging
import socket
from typing import Any
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

# Hostnames / IP patterns that are always blocked.
BLOCKED_HOSTS = {
    "localhost",
    "ip6-localhost",
    "ip6-loopback",
    "metadata.google.internal",  # GCP metadata
    "metadata",  # AWS-style
    "169.254.169.254",  # AWS / Azure / GCP metadata
    "metadata.google.internal.",  # trailing dot
}

# Subnets we refuse to fetch from (RFC1918 + link-local + loopback).
BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),       # IPv4 loopback
    ipaddress.ip_network("10.0.0.0/8"),         # private
    ipaddress.ip_network("172.16.0.0/12"),      # private
    ipaddress.ip_network("192.168.0.0/16"),     # private
    ipaddress.ip_network("169.254.0.0/16"),     # link-local (metadata endpoints)
    ipaddress.ip_network("0.0.0.0/8"),          # reserved
    ipaddress.ip_network("100.64.0.0/10"),      # CGNAT
    ipaddress.ip_network("::1/128"),            # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),           # IPv6 ULA
    ipaddress.ip_network("fe80::/10"),          # IPv6 link-local
]

# Schemes we will actually fetch.
ALLOWED_SCHEMES = {"http", "https"}


def is_safe_url(url: str, *, allow_private: bool = False) -> tuple[bool, str]:
    """Return ``(safe, reason)``.

    Never raises — returns ``(False, reason)`` on any parsing/DNS error.

    Args:
        url: URL to check.
        allow_private: if True, allow RFC1918 ranges (useful for local dev).
    """
    if not url or not isinstance(url, str):
        return False, "empty url"

    try:
        parsed = urlparse(url)
    except (ValueError, TypeError) as exc:
        return False, f"invalid url: {exc}"

    scheme = (parsed.scheme or "").lower()
    if scheme not in ALLOWED_SCHEMES:
        return False, f"blocked scheme: {scheme or 'none'}"

    host = (parsed.hostname or "").lower().rstrip(".")
    if not host:
        return False, "missing host"

    # 1) hostname string blocklist (covers metadata endpoints & localhost)
    if host in BLOCKED_HOSTS:
        return False, f"blocked: {host}"

    # 2) If the host is a literal IP, check against blocked networks
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None

    if ip is not None and not allow_private:
        for net in BLOCKED_NETWORKS:
            if ip in net:
                return False, f"blocked ip range: {net}"

    # 3) DNS resolution — a hostname like "localhost.my-attacker.com" may
    #    resolve to 169.254.169.254. Resolve once and inspect the result.
    if ip is None:
        try:
            infos = socket.getaddrinfo(host, None)
        except (socket.gaierror, socket.herror, OSError):
            # DNS failure — treat as unsafe rather than risk a retry path.
            return False, f"dns resolution failed for {host}"
        for info in infos:
            addr = info[4][0]
            try:
                resolved_ip = ipaddress.ip_address(addr)
            except ValueError:
                continue
            if not allow_private:
                for net in BLOCKED_NETWORKS:
                    if resolved_ip in net:
                        return False, f"blocked: {host} resolves to private ip {resolved_ip}"

    return True, "ok"


# --------------------------------------------------------------------------- #
# SafeHTTPClient — httpx wrapper that validates every URL (incl. redirects)
# --------------------------------------------------------------------------- #
class UnsafeURLError(ValueError):
    """Raised when a URL is rejected by the SSRF guard."""


class SafeHTTPClient:
    """httpx wrapper that blocks SSRF attempts.

    Validates the requested URL *before* the request is sent AND validates
    every redirect target by following redirects manually and re-checking
    each ``Location`` header. This defeats TOCTOU redirects to metadata
    endpoints (e.g., a server returns a 302 to ``http://169.254.169.254/``).

    Usage:
        >>> client = SafeHTTPClient(timeout=30.0, headers={...})
        >>> resp = await client.get("https://example.com/")

    The client intentionally exposes only ``get`` — every other verb can be
    added on demand. Returns the final ``httpx.Response`` (after redirects).

    On an unsafe URL it raises :class:`UnsafeURLError` (a ``ValueError``
    subclass) — callers should catch ``ValueError`` or
    ``UnsafeURLError`` and treat the URL as user-rejected.

    ``allow_private`` defaults to ``False``. Pass ``True`` for local dev
    only (it disables the RFC1918 / link-local / loopback checks).
    """

    def __init__(
        self,
        *,
        timeout: float = 30.0,
        connect_timeout: float = 10.0,
        headers: dict[str, str] | None = None,
        max_redirects: int = 10,
        allow_private: bool = False,
    ) -> None:
        self.timeout = timeout
        self.connect_timeout = connect_timeout
        self.headers = headers or {}
        self.max_redirects = max_redirects
        self.allow_private = allow_private

    def _check(self, url: str) -> None:
        safe, reason = is_safe_url(url, allow_private=self.allow_private)
        if not safe:
            raise UnsafeURLError(f"URL blocked: {reason} ({url})")

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        """GET ``url`` with SSRF guard. Follows redirects manually, validating each hop."""
        self._check(url)

        # We disable httpx's own redirect following so we can inspect every
        # Location header before issuing the next request.
        kwargs.setdefault("follow_redirects", False)
        timeout = kwargs.pop("timeout", None) or httpx.Timeout(
            self.timeout, connect=self.connect_timeout
        )
        headers = kwargs.pop("headers", None) or dict(self.headers)

        async with httpx.AsyncClient(timeout=timeout) as client:
            current_url = url
            for _ in range(self.max_redirects + 1):
                resp = await client.get(current_url, headers=headers, **kwargs)
                if resp.is_redirect:
                    location = resp.headers.get("location", "")
                    if not location:
                        return resp
                    # Resolve relative redirects against the current URL.
                    from urllib.parse import urljoin

                    next_url = urljoin(current_url, location)
                    self._check(next_url)
                    current_url = next_url
                    continue
                return resp
            # Exceeded max_redirects — return the last response so caller can inspect.
            return resp


__all__ = [
    "BLOCKED_HOSTS",
    "BLOCKED_NETWORKS",
    "ALLOWED_SCHEMES",
    "is_safe_url",
    "SafeHTTPClient",
    "UnsafeURLError",
]
