"""Sliding-window in-memory rate limiter.

Used by security tests to verify the rate-limiting defense actually exists.
Not wired into the FastAPI app by default — it's a building block. The
security tests can monkeypatch endpoints to use it.

Public API:
    >>> from app.middleware.rate_limiter import RateLimiter
    >>> limiter = RateLimiter(limit=5, window_seconds=60)
    >>> limiter.check("1.2.3.4")
    (True, 5)         # allowed, remaining=5
    >>> limiter.check("1.2.3.4")
    (False, 0)        # blocked, remaining=0
"""
from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class _Bucket:
    """Per-identifier request bucket."""

    hits: list[float] = field(default_factory=list)


class RateLimiter:
    """In-memory sliding-window rate limiter.

    Args:
        limit: maximum requests allowed per window.
        window_seconds: window duration in seconds.
    """

    def __init__(self, limit: int = 5, window_seconds: int = 60) -> None:
        if limit < 1:
            raise ValueError("limit must be >= 1")
        if window_seconds < 1:
            raise ValueError("window_seconds must be >= 1")
        self.limit = limit
        self.window_seconds = window_seconds
        self._buckets: dict[str, _Bucket] = defaultdict(_Bucket)

    def check(self, identifier: str) -> tuple[bool, int]:
        """Return ``(allowed, remaining)``.

        ``allowed`` is True if this request is within the limit.
        ``remaining`` is the number of additional requests allowed in the
        current window AFTER this one (0 if blocked).
        """
        if not identifier:
            return True, self.limit  # fail-open for missing identifier

        now = time.monotonic()
        bucket = self._buckets[identifier]
        cutoff = now - self.window_seconds

        # Drop expired entries (sliding window).
        bucket.hits = [t for t in bucket.hits if t > cutoff]

        if len(bucket.hits) >= self.limit:
            return False, 0

        bucket.hits.append(now)
        return True, self.limit - len(bucket.hits)

    def reset(self, identifier: str | None = None) -> None:
        """Clear the bucket for ``identifier`` (or all buckets)."""
        if identifier is None:
            self._buckets.clear()
        else:
            self._buckets.pop(identifier, None)
