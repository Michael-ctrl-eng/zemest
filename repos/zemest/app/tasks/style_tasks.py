"""Celery tasks for rebuilding per-tenant personality/style profiles."""

import asyncio
import logging
import uuid

from sqlalchemy import select

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Helper to run async code in Celery synchronous tasks."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(bind=True, max_retries=1)
def rebuild_all_personalities(self):
    """Iterate all active tenants and rebuild their style/knowledge profiles.

    Scheduled weekly via Celery beat (see celery_app.beat_schedule).
    Safe to run manually: ``rebuild_all_personalities.delay()``.
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


@celery_app.task(bind=True, max_retries=1)
def rebuild_tenant_personality(self, tenant_id: str):
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
