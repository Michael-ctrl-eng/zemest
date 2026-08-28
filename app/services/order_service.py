from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.order import Order, OrderItem


def _generate_order_number() -> str:
    now = datetime.utcnow()
    import random
    return f"ORD-{now.strftime('%y%m%d')}-{random.randint(100, 999)}"


async def create_order(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    customer_id: uuid.UUID,
    conversation_id: uuid.UUID | None,
    customer_name: str,
    customer_phone: str,
    governorate: str,
    city: str,
    area: str | None,
    address_detail: str,
    payment_method: str,
    items: list[dict],
    delivery_charge: Decimal = Decimal("0"),
    notes: str | None = None,
) -> Order:
    subtotal = sum(
        Decimal(str(item["unit_price"])) * item["quantity"] for item in items
    )
    total = subtotal + delivery_charge

    order = Order(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        customer_id=customer_id,
        conversation_id=conversation_id,
        order_number=_generate_order_number(),
        customer_name=customer_name,
        customer_phone=customer_phone,
        governorate=governorate,
        city=city,
        area=area,
        address_detail=address_detail,
        payment_method=payment_method,
        subtotal=subtotal,
        delivery_charge=delivery_charge,
        total=total,
        notes=notes,
    )
    db.add(order)
    await db.flush()

    for item in items:
        order_item = OrderItem(
            id=uuid.uuid4(),
            order_id=order.id,
            product_id=item.get("product_id"),
            product_name=item["product_name"],
            quantity=item["quantity"],
            unit_price=Decimal(str(item["unit_price"])),
            total_price=Decimal(str(item["unit_price"])) * item["quantity"],
        )
        db.add(order_item)

    await db.flush()
    return order


async def get_orders(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    page: int = 1,
    page_size: int = 20,
    status: str | None = None,
) -> tuple[list[Order], int]:
    query = select(Order).where(Order.tenant_id == tenant_id)
    count_query = select(func.count(Order.id)).where(Order.tenant_id == tenant_id)

    if status:
        query = query.where(Order.status == status)
        count_query = count_query.where(Order.status == status)

    total = await db.scalar(count_query) or 0
    result = await db.execute(
        query.options(selectinload(Order.items))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .order_by(Order.created_at.desc())
    )
    return list(result.scalars().all()), total


async def get_order_by_id(
    db: AsyncSession, tenant_id: uuid.UUID, order_id: uuid.UUID
) -> Order | None:
    result = await db.execute(
        select(Order)
        .where(Order.id == order_id, Order.tenant_id == tenant_id)
        .options(selectinload(Order.items))
    )
    return result.scalar_one_or_none()


async def update_order_status(
    db: AsyncSession, order: Order, new_status: str
) -> Order:
    valid_transitions = {
        "pending": ["confirmed", "cancelled"],
        "confirmed": ["shipped", "cancelled"],
        "shipped": ["delivered"],
        "delivered": [],
        "cancelled": [],
    }
    allowed = valid_transitions.get(order.status, [])
    if new_status not in allowed:
        raise ValueError(
            f"Cannot transition from '{order.status}' to '{new_status}'. "
            f"Allowed: {allowed}"
        )
    order.status = new_status
    await db.flush()
    return order
