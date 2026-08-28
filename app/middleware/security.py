"""Security middleware: rate limiting, IP banning, SSRF protection, security headers.

This module provides production-grade security middleware for Zemest.
"""
from __future__ import annotations

import ipaddress
import logging
import re
import socket
import time
from functools import wraps
from typing import Optional
from urllib.parse import urlparse

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


# ============================================================
# SSRF Protection
# ============================================================

BLOCKED_IP_RANGES = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),  # AWS metadata, link-local
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),  # Carrier-grade NAT
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),  # IPv6 unique local
    ipaddress.ip_network("fe80::/10"),  # IPv6 link-local
]


def is_safe_url(url: str) -> tuple[bool, str]:
    """Validate URL is safe to fetch (SSRF protection).

    Checks:
    - Scheme is http or https
    - Hostname resolves to a public IP (not private/loopback/link-local)
    - Blocks AWS metadata endpoint (169.254.169.254)

    Returns (is_safe, reason).
    """
    if not url or not isinstance(url, str):
        return False, "Empty or invalid URL"

    try:
        parsed = urlparse(url)
    except Exception as e:
        return False, f"URL parse error: {e}"

    if parsed.scheme not in ("http", "https"):
        return False, f"Scheme '{parsed.scheme}' not allowed (only http/https)"

    hostname = parsed.hostname
    if not hostname:
        return False, "No hostname in URL"

    # Block obvious localhost
    if hostname in ("localhost", "ip6-localhost", "metadata.google.internal"):
        return False, f"Blocked hostname: {hostname}"

    # Check if it's an IP literal
    try:
        ip = ipaddress.ip_address(hostname)
        for network in BLOCKED_IP_RANGES:
            if ip in network:
                return False, f"IP {hostname} in blocked range"
        return True, "OK (IP literal)"
    except ValueError:
        pass  # Not an IP — it's a hostname, do DNS lookup

    # DNS resolution + IP validation
    try:
        infos = socket.getaddrinfo(hostname, None)
        for info in infos:
            ip_str = info[4][0]
            try:
                ip = ipaddress.ip_address(ip_str)
                for network in BLOCKED_IP_RANGES:
                    if ip in network:
                        return False, f"DNS resolved {hostname} → {ip_str} (blocked range)"
            except ValueError:
                continue
    except socket.gaierror:
        return False, f"DNS resolution failed for {hostname}"

    return True, "OK"


class SSRFProtectionError(Exception):
    """Raised when a URL is blocked by SSRF protection."""


async def safe_http_get(client, url: str, **kwargs) -> Response:
    """Safe httpx GET that blocks SSRF attempts.

    Usage:
        async with httpx.AsyncClient() as client:
            resp = await safe_http_get(client, user_url)
    """
    is_safe, reason = is_safe_url(url)
    if not is_safe:
        logger.warning(f"SSRF blocked: {url} — {reason}")
        raise SSRFProtectionError(f"URL blocked: {reason}")
    return await client.get(url, **kwargs)


# ============================================================
# Prompt Injection Detection
# ============================================================

PROMPT_INJECTION_PATTERNS = [
    r"ignore\s+(previous|above|all|prior)\s+(instructions?|rules?|prompts?)",
    r"disregard\s+(previous|above|all|prior)\s+(instructions?|rules?)",
    r"you\s+are\s+now\s+(a|an)\s+\w+",
    r"system\s*:\s*",
    r"<\|im_start\|>",
    r"\[INSTRUCTIONS\]",
    r"\[SYSTEM\]",
    r"reveal\s+(your|the)\s+(system\s+)?prompt",
    r"what\s+(are|is)\s+your\s+(instructions?|rules?|prompt)",
    r"jailbreak",
    r"DAN\s+mode",
    r"developer\s+mode",
    r"override\s+(system|instructions|rules)",
    r"forget\s+(everything|all|previous)",
    r"act\s+as\s+(if\s+you\s+are\s+)?(a|an)\s+(different|new)",
    r"sudo\s+",
    r"admin\s+override",
]

_compiled_patterns = [re.compile(p, re.IGNORECASE) for p in PROMPT_INJECTION_PATTERNS]


def detect_prompt_injection(text: str) -> tuple[bool, list[str]]:
    """Check if user input contains prompt injection attempts.

    Returns (is_injection, matched_patterns).
    """
    if not text:
        return False, []
    matches = []
    for i, pattern in enumerate(_compiled_patterns):
        if pattern.search(text):
            matches.append(PROMPT_INJECTION_PATTERNS[i])
    return len(matches) > 0, matches


def sanitize_user_input(text: str) -> str:
    """Wrap user input to prevent prompt injection.

    Delimits user input so the LLM knows it's untrusted.
    """
    return f"[USER INPUT START]\n{text}\n[USER INPUT END]"


# ============================================================
# Security Headers Middleware
# ============================================================

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds security headers to all responses."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        # HSTS only on HTTPS
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )
        return response


# ============================================================
# Bot Detection (logging only — don't block)
# ============================================================

BOT_USER_AGENTS = [
    "scrapy", "curl/", "wget/", "python-requests", "python-httpx",
    "bot", "crawler", "spider", "scraper", "headless",
    "googlebot", "bingbot", "ahrefsbot", "semrushbot",
]


def is_likely_bot(user_agent: str) -> bool:
    """Check if user agent looks like a bot."""
    if not user_agent:
        return True
    ua_lower = user_agent.lower()
    return any(bot_ua in ua_lower for bot_ua in BOT_USER_AGENTS)


class BotDetectionMiddleware(BaseHTTPMiddleware):
    """Logs suspicious bot traffic (doesn't block)."""

    async def dispatch(self, request: Request, call_next):
        ua = request.headers.get("user-agent", "")
        if is_likely_bot(ua):
            logger.info(
                f"Bot traffic: ua={ua[:100]} ip={request.client.host if request.client else 'unknown'} "
                f"path={request.url.path}"
            )
        return await call_next(request)


# ============================================================
# IP Ban Middleware
# ============================================================

class IPBanMiddleware(BaseHTTPMiddleware):
    """Blocks requests from banned IPs/CIDRs.

    In production, banlist is loaded from Redis/Postgres and cached in memory.
    For now, uses an in-memory set (suitable for single-instance deployments).
    """

    def __init__(self, app, banned_ips: Optional[set[str]] = None, banned_cidrs: Optional[list[str]] = None):
        super().__init__(app)
        self._banned_ips: set[str] = banned_ips or set()
        self._banned_networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
        if banned_cidrs:
            for cidr in banned_cidrs:
                try:
                    self._banned_networks.append(ipaddress.ip_network(cidr, strict=False))
                except ValueError:
                    logger.warning(f"Invalid CIDR in banlist: {cidr}")

    def ban_ip(self, ip: str) -> None:
        """Add an IP to the banlist."""
        self._banned_ips.add(ip)

    def ban_cidr(self, cidr: str) -> None:
        """Add a CIDR range to the banlist."""
        try:
            self._banned_networks.append(ipaddress.ip_network(cidr, strict=False))
        except ValueError as e:
            logger.error(f"Invalid CIDR '{cidr}': {e}")

    def unban_ip(self, ip: str) -> None:
        """Remove an IP from the banlist."""
        self._banned_ips.discard(ip)

    def is_banned(self, ip: str) -> bool:
        """Check if IP is banned."""
        if ip in self._banned_ips:
            return True
        try:
            addr = ipaddress.ip_address(ip)
            for network in self._banned_networks:
                if addr in network:
                    return True
        except ValueError:
            pass
        return False

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else None
        if client_ip and self.is_banned(client_ip):
            logger.warning(f"Blocked request from banned IP: {client_ip}")
            return JSONResponse(
                {"detail": "Access denied"},
                status_code=403,
            )
        return await call_next(request)


# ============================================================
# Rate Limiting (simple in-memory — use slowapi/Redis for production)
# ============================================================

class SimpleRateLimiter:
    """Simple in-memory rate limiter (sliding window).

    For production, use slowapi with Redis backend.
    """

    def __init__(self):
        self._requests: dict[str, list[float]] = {}

    def is_allowed(self, key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
        """Check if request is allowed under rate limit.

        Returns (allowed, retry_after_seconds).
        """
        now = time.time()
        window_start = now - window_seconds

        if key not in self._requests:
            self._requests[key] = []

        # Remove old entries
        self._requests[key] = [t for t in self._requests[key] if t > window_start]

        if len(self._requests[key]) >= limit:
            oldest = self._requests[key][0]
            retry_after = int(oldest + window_seconds - now) + 1
            return False, max(retry_after, 1)

        self._requests[key].append(now)
        return True, 0


# Singleton rate limiter
_rate_limiter = SimpleRateLimiter()


def rate_limit(limit: int, window_seconds: int = 60):
    """Decorator for rate-limiting endpoints.

    Usage:
        @router.post("/login")
        @rate_limit(limit=5, window_seconds=60)
        async def login(...):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract request from args
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            if request is None:
                # Look in kwargs
                request = kwargs.get("request")

            if request:
                client_ip = request.client.host if request.client else "unknown"
                key = f"{request.url.path}:{client_ip}"
                allowed, retry_after = _rate_limiter.is_allowed(key, limit, window_seconds)
                if not allowed:
                    return JSONResponse(
                        {"detail": "Rate limit exceeded", "retry_after": retry_after},
                        status_code=429,
                        headers={"Retry-After": str(retry_after)},
                    )
            return await func(*args, **kwargs)
        return wrapper
    return decorator
