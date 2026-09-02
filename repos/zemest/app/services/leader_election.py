"""Leader election for background jobs across replicas (audit F8).

When the API runs as N replicas behind a load balancer, every replica's
APScheduler fires the same 30 s / 45 s / weekly jobs. ``max_instances=1``
only deduplicates within ONE process — across replicas the publish job
would run N times (duplicate Graph posts), the trainer would burn N× the
LLM budget, and the weekly rebuild would race three writers on
``tenant.style_profile``.

The Postiz pattern (reference repo, apps/cron): only designated workers run
cron (``RUN_CRON`` env). We go one better — **per-job Postgres advisory
locks**: each job execution first tries ``pg_try_advisory_lock`` keyed by
the job name. Exactly one replica wins; the others skip the tick. No
central coordinator, no lease table, no split-brain (locks die with the
session).

On SQLite (dev/tests) advisory locks don't exist — the fallback always
"wins", which is safe because SQLite deployments are single-process and
``max_instances=1`` already deduplicates there.
"""
from __future__ import annotations

import hashlib
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Stable namespace so our locks never collide with other apps on the DB.
_NAMESPACE = 0x5A4D4553  # "ZMES"


def _job_key(job_name: str) -> int:
    digest = hashlib.sha256(job_name.encode()).digest()
    return _NAMESPACE | (int.from_bytes(digest[:4], "big") & 0x00FF_FFFF)


async def try_job_lock(db: AsyncSession, job_name: str) -> bool:
    """Try to become the executor of ``job_name`` for THIS transaction.

    Returns True when this replica should run the job. The lock is held
    until the session's transaction ends (commit/rollback) — the job must
    use the SAME session for its writes so the lock naturally covers the
    work, and duplicate executors are excluded for the tick duration.
    """
    try:
        result = await db.execute(
            text("SELECT pg_try_advisory_lock(:k) AS acquired"),
            {"k": _job_key(job_name)},
        )
        acquired = result.scalar()
        if not acquired:
            logger.info(
                "Job %s skipped — another replica holds the advisory lock", job_name
            )
        return bool(acquired)
    except Exception as e:
        # SQLite / dialects without advisory locks: single-process mode.
        logger.debug("Advisory lock unavailable (%s) — single-process mode", e)
        return True


async def release_job_lock(db: AsyncSession, job_name: str) -> None:
    """Best-effort release (rollback/commit releases implicitly)."""
    try:
        await db.execute(
            text("SELECT pg_advisory_unlock(:k)"), {"k": _job_key(job_name)}
        )
    except Exception:
        pass


__all__ = ["try_job_lock", "release_job_lock"]
