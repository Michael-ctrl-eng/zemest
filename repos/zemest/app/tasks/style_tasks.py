"""Huey tasks for rebuilding per-tenant personality/style profiles."""

import asyncio
import logging
import uuid

from sqlalchemy import select

from app.tasks.huey_app import huey_app

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Helper to run async code in Huey synchronous tasks."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@huey_app.task(retries=1)
def rebuild_all_personalities():
    """Iterate all active tenants and rebuild their style/knowledge profiles.

    Scheduled weekly via APScheduler (app/main.py lifespan — replaces the
    old Celery beat entry). Safe to run manually: enqueue by calling
    ``rebuild_all_personalities()`` (Huey semantics) or run inline via
    ``rebuild_all_personalities.call_local()``.
    """
    _run_async(_rebuild_all_personalities_async())


async def _rebuild_all_personalities_async():
    from app.database import async_session
    from app.models.tenant import Tenant
    from app.ai.style_learner import build_and_persist_personality

    async with async_session() as db:
        result = await db.execute(
            select(Tenant).where(Tenant.is_active == True)
        )
        tenants = list(result.scalars().all())

    logger.info(f"Rebuilding personality for {len(tenants)} tenants")

    for tenant in tenants:
        # Each tenant gets its own session so failures don't roll back others
        async with async_session() as db:
            try:
                await build_and_persist_personality(db, tenant)
            except Exception as e:
                logger.error(
                    f"Personality rebuild failed for tenant {tenant.id}: {e}",
                    exc_info=True,
                )


@huey_app.task(retries=1)
def rebuild_tenant_personality(tenant_id: str):
    """Rebuild a single tenant's personality (async dispatch helper)."""
    _run_async(_rebuild_tenant_personality_async(tenant_id))


async def _rebuild_tenant_personality_async(tenant_id: str):
    from app.database import async_session
    from app.models.tenant import Tenant
    from app.ai.style_learner import build_and_persist_personality

    async with async_session() as db:
        tenant = await db.get(Tenant, uuid.UUID(tenant_id))
        if not tenant:
            logger.warning(f"Tenant {tenant_id} not found — skipping personality rebuild")
            return
        await build_and_persist_personality(db, tenant)
