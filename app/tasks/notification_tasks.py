import asyncio
import uuid

from app.tasks.celery_app import celery_app


@celery_app.task
def send_order_notification(tenant_id: str, order_id: str):
    """Send order notification asynchronously."""
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_send_notification(tenant_id, order_id))
    finally:
        loop.close()


async def _send_notification(tenant_id: str, order_id: str):
    from app.database import async_session
    from app.models.tenant import Tenant
    from app.models.order import Order
    from app.services.notification_service import notify_new_order
    from sqlalchemy.orm import selectinload

    async with async_session() as db:
        tenant = await db.get(Tenant, uuid.UUID(tenant_id))
        from sqlalchemy import select
        result = await db.execute(
            select(Order)
            .where(Order.id == uuid.UUID(order_id))
            .options(selectinload(Order.items))
        )
        order = result.scalar_one_or_none()

        if tenant and order:
            await notify_new_order(tenant, order)
