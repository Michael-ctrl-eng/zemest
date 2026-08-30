"""Per-tenant concurrency gates and parallel multimodal processing.

Allows up to 8 concurrent conversations per tenant, with parallel
voice transcription + image analysis + LLM calls.
"""
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any, Awaitable, Coroutine, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Per-tenant semaphores — 8 concurrent conversations per tenant
MAX_CONCURRENT_PER_TENANT = 8
_tenant_semaphores: dict[str, asyncio.Semaphore] = {}


def _get_gate(tenant_id: str) -> asyncio.Semaphore:
    """Get or create the concurrency semaphore for a tenant."""
    key = str(tenant_id)
    if key not in _tenant_semaphores:
        _tenant_semaphores[key] = asyncio.Semaphore(MAX_CONCURRENT_PER_TENANT)
    return _tenant_semaphores[key]


async def run_with_tenant_limit(
    tenant_id: str, coro: Coroutine[Any, Any, T]
) -> T:
    """Run a coroutine within the tenant's concurrency limit.

    If 8 conversations are already running for this tenant, the 9th
    will wait until one finishes.
    """
    gate = _get_gate(tenant_id)
    async with gate:
        return await coro


async def gather_multimodal(*coros: Coroutine[Any, Any, T]) -> list[T | Exception]:
    """Run multiple modalities (voice, vision, text) in parallel.

    Uses asyncio.gather with return_exceptions=True so one failure
    (e.g., Gemini API down) doesn't block the others.

    Returns list of results; failures are returned as Exception objects
    so callers can check isinstance(result, Exception) and handle gracefully.
    """
    if not coros:
        return []
    results = await asyncio.gather(*coros, return_exceptions=True)
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.warning(f"Multimodal task {i} failed: {result}")
    return results


async def gather_with_limit(
    limit: int, *coros: Coroutine[Any, Any, T]
) -> list[T | Exception]:
    """Run coroutines in parallel with a global concurrency limit.

    Useful for batch operations like crawling multiple URLs.
    """
    if not coros:
        return []
    semaphore = asyncio.Semaphore(limit)

    async def _run(coro: Coroutine[Any, Any, T]) -> T | Exception:
        async with semaphore:
            try:
                return await coro
            except Exception as e:
                return e

    return await asyncio.gather(*[_run(c) for c in coros])


def get_tenant_active_count(tenant_id: str) -> int:
    """Get the number of currently-active conversations for a tenant."""
    key = str(tenant_id)
    sem = _tenant_semaphores.get(key)
    if sem is None:
        return 0
    return MAX_CONCURRENT_PER_TENANT - sem._value  # type: ignore[attr-defined]


def reset_tenant_gate(tenant_id: str) -> None:
    """Reset the concurrency gate for a tenant (for testing)."""
    key = str(tenant_id)
    if key in _tenant_semaphores:
        del _tenant_semaphores[key]
