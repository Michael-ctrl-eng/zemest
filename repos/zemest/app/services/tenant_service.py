import uuid

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenant import Tenant
from app.models.user import User


async def create_tenant(db: AsyncSession, owner: User, **kwargs) -> Tenant:
    tenant = Tenant(id=uuid.uuid4(), owner_id=owner.id, **kwargs)
    db.add(tenant)
    await db.flush()
    return tenant


async def get_user_tenants(db: AsyncSession, user: User) -> list[Tenant]:
    result = await db.execute(
        select(Tenant).where(Tenant.owner_id == user.id, Tenant.is_active == True)
    )
    return list(result.scalars().all())


async def update_tenant(db: AsyncSession, tenant: Tenant, **kwargs) -> Tenant:
    for key, value in kwargs.items():
        if value is not None and hasattr(tenant, key):
            setattr(tenant, key, value)
    await db.flush()
    return tenant


async def get_tenant_stats(db: AsyncSession, tenant_id: uuid.UUID) -> dict:
    from app.models.product import Product
    from app.models.order import Order
    from app.models.conversation import Conversation

    products_count = await db.scalar(
        select(func.count(Product.id)).where(
            Product.tenant_id == tenant_id, Product.is_active == True
        )
    )
    orders_count = await db.scalar(
        select(func.count(Order.id)).where(Order.tenant_id == tenant_id)
    )
    pending_orders = await db.scalar(
        select(func.count(Order.id)).where(
            Order.tenant_id == tenant_id, Order.status == "pending"
        )
    )
    active_conversations = await db.scalar(
        select(func.count(Conversation.id)).where(
            Conversation.tenant_id == tenant_id, Conversation.status == "active"
        )
    )
    total_revenue = await db.scalar(
        select(func.coalesce(func.sum(Order.total), 0)).where(
            Order.tenant_id == tenant_id,
            Order.status.in_(["confirmed", "shipped", "delivered"]),
        )
    )

    # Token usage stats
    from app.models.token_usage import TokenUsage

    total_tokens_used = await db.scalar(
        select(func.coalesce(func.sum(TokenUsage.total_tokens), 0)).where(
            TokenUsage.tenant_id == tenant_id
        )
    )
    chat_tokens = await db.scalar(
        select(func.coalesce(func.sum(TokenUsage.total_tokens), 0)).where(
            TokenUsage.tenant_id == tenant_id, TokenUsage.usage_type == "chat"
        )
    )
    crawl_tokens = await db.scalar(
        select(func.coalesce(func.sum(TokenUsage.total_tokens), 0)).where(
            TokenUsage.tenant_id == tenant_id, TokenUsage.usage_type == "crawl"
        )
    )
    llm_calls = await db.scalar(
        select(func.count(TokenUsage.id)).where(
            TokenUsage.tenant_id == tenant_id
        )
    )

    # Today / month stats
    from datetime import datetime, timedelta
    from app.models.customer import Customer
    from app.models.order import OrderItem

    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = today_start.replace(day=1)

    today_orders = await db.scalar(
        select(func.count(Order.id)).where(
            Order.tenant_id == tenant_id,
            Order.created_at >= today_start,
        )
    ) or 0

    today_revenue = await db.scalar(
        select(func.coalesce(func.sum(Order.total), 0)).where(
            Order.tenant_id == tenant_id,
            Order.created_at >= today_start,
            Order.status.in_(["confirmed", "shipped", "delivered"]),
        )
    ) or 0

    month_revenue = await db.scalar(
        select(func.coalesce(func.sum(Order.total), 0)).where(
            Order.tenant_id == tenant_id,
            Order.created_at >= month_start,
            Order.status.in_(["confirmed", "shipped", "delivered"]),
        )
    ) or 0

    customers_count = await db.scalar(
        select(func.count(Customer.id)).where(Customer.tenant_id == tenant_id)
    ) or 0

    # Top selling products
    top_result = await db.execute(
        select(
            OrderItem.product_name,
            func.sum(OrderItem.quantity).label("total_qty"),
            func.sum(OrderItem.total_price).label("total_revenue"),
        )
        .join(Order, OrderItem.order_id == Order.id)
        .where(Order.tenant_id == tenant_id)
        .group_by(OrderItem.product_name)
        .order_by(func.sum(OrderItem.quantity).desc())
        .limit(5)
    )
    top_products = [
        {"name": row.product_name, "qty": int(row.total_qty), "revenue": float(row.total_revenue)}
        for row in top_result.all()
    ]

    # Recent orders
    recent_result = await db.execute(
        select(Order)
        .where(Order.tenant_id == tenant_id)
        .order_by(Order.created_at.desc())
        .limit(5)
    )
    recent_orders = [
        {
            "order_number": o.order_number,
            "customer_name": o.customer_name,
            "total": float(o.total),
            "status": o.status,
            "created_at": str(o.created_at),
        }
        for o in recent_result.scalars().all()
    ]

    return {
        "products_count": products_count or 0,
        "orders_count": orders_count or 0,
        "pending_orders": pending_orders or 0,
        "active_conversations": active_conversations or 0,
        "total_revenue": float(total_revenue or 0),
        "today_orders": today_orders,
        "today_revenue": float(today_revenue),
        "month_revenue": float(month_revenue),
        "customers_count": customers_count,
        "top_products": top_products,
        "recent_orders": recent_orders,
        "total_tokens": int(total_tokens_used or 0),
        "chat_tokens": int(chat_tokens or 0),
        "crawl_tokens": int(crawl_tokens or 0),
        "llm_calls": int(llm_calls or 0),
    }
