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
    # kwargs comes from TenantUpdate.model_dump(exclude_unset=True): only
    # fields the client explicitly sent are present, so None here means
    # "clear this field" — it must be written, not dropped.
    for key, value in kwargs.items():
        if hasattr(tenant, key):
            setattr(tenant, key, value)
    await db.flush()
    return tenant


# --- Stats cache: 20s TTL per tenant. Dashboards re-render from cache
# instantly; writes converge within 20s. (Was 14 sequential queries on
# every dashboard home load.)
import time as _time

_STATS_TTL_SECONDS = 20.0
_stats_cache: dict = {}


def invalidate_tenant_stats(tenant_id) -> None:
    """Drop the cached stats for a tenant (call after mutations)."""
    _stats_cache.pop(str(tenant_id), None)




def _today_start():
    from datetime import datetime as _dt
    return _dt.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)


async def get_tenant_stats(db: AsyncSession, tenant_id: uuid.UUID) -> dict:
    cache_key = str(tenant_id)
    hit = _stats_cache.get(cache_key)
    if hit and (_time.monotonic() - hit[0]) < _STATS_TTL_SECONDS:
        return hit[1]

    from app.models.product import Product
    from app.models.order import Order
    from app.models.conversation import Conversation

    from sqlalchemy import case

    REVENUE_STATUSES = ["confirmed", "shipped", "delivered"]

    products_count = await db.scalar(
        select(func.count(Product.id)).where(
            Product.tenant_id == tenant_id, Product.is_active == True  # noqa: E712
        )
    )
    # One aggregate pass over orders replaces 6 sequential COUNT/SUM queries.
    orders_row = (
        await db.execute(
            select(
                func.count(Order.id).label("orders_count"),
                func.coalesce(
                    func.sum(case((Order.status == "pending", 1), else_=0)), 0
                ).label("pending_orders"),
                func.coalesce(
                    func.sum(case((Order.status.in_(REVENUE_STATUSES), Order.total), else_=0.0)),
                    0,
                ).label("total_revenue"),
                func.coalesce(
                    func.sum(case((Order.created_at >= _today_start(), 1), else_=0)), 0
                ).label("today_orders"),
                func.coalesce(
                    func.sum(
                        case(
                            (Order.created_at >= _today_start(), Order.total),
                            (Order.status.in_(REVENUE_STATUSES), 0.0),
                        )
                    ),
                    0,
                ).label("today_revenue"),
            ).where(Order.tenant_id == tenant_id)
        )
    ).one()
    orders_count = orders_row.orders_count
    pending_orders = orders_row.pending_orders
    total_revenue = orders_row.total_revenue
    today_orders = int(orders_row.today_orders or 0)
    today_revenue = float(orders_row.today_revenue or 0)
    active_conversations = await db.scalar(
        select(func.count(Conversation.id)).where(
            Conversation.tenant_id == tenant_id, Conversation.status == "active"
        )
    )

    # Token usage stats — one aggregate instead of four sequential sums.
    from app.models.token_usage import TokenUsage

    tokens_row = (
        await db.execute(
            select(
                func.coalesce(func.sum(TokenUsage.total_tokens), 0).label("total"),
                func.coalesce(
                    func.sum(case((TokenUsage.usage_type == "chat", TokenUsage.total_tokens))),
                    0,
                ).label("chat"),
                func.coalesce(
                    func.sum(case((TokenUsage.usage_type == "crawl", TokenUsage.total_tokens))),
                    0,
                ).label("crawl"),
                func.count(TokenUsage.id).label("calls"),
            ).where(TokenUsage.tenant_id == tenant_id)
        )
    ).one()
    total_tokens_used = tokens_row.total
    chat_tokens = tokens_row.chat
    crawl_tokens = tokens_row.crawl
    llm_calls = tokens_row.calls

    # Month revenue — today's numbers already came from the orders
    # mega-aggregate above (2 fewer sequential queries).
    from app.models.customer import Customer
    from app.models.order import OrderItem

    month_start = _today_start().replace(day=1)

    month_revenue = await db.scalar(
        select(func.coalesce(func.sum(Order.total), 0)).where(
            Order.tenant_id == tenant_id,
            Order.created_at >= month_start,
            Order.status.in_(REVENUE_STATUSES),
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

    stats = {
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
    _stats_cache[cache_key] = (_time.monotonic(), stats)
    return stats
