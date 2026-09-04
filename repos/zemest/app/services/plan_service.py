"""Subscription plans & hard usage limits.

Business model (per user account — every tenant/shop carries its own
channel set: one Facebook Page, one Instagram, one WhatsApp):

- **free**   — 1 shop, 1,000 inbound customer messages/month, 50k LLM
               tokens/day. Enough to prove the agent on one page.
- **growth** — 5 shops (multi-page / multi-brand / one channel per extra
               shop), 10,000 messages/month, 250k LLM tokens/day.
- **pro**    — 25 shops, 100,000 messages/month, 1M LLM tokens/day,
               priority in the crawl/scheduling queues.

Enforcement points:
- shop creation (`POST /api/tenants`, `/api/facebook/connect`) → 402
- tenant-scoped connect (`POST /channels/{platform}`) → 402 when the shop's
  channel set is complete and the plan allows no extra shop
- every customer message (`agent.process_customer_message`) → monthly
  message quota; over-quota traffic gets the honest fallback reply instead
  of burning LLM tokens (audit A5-H1: financial DoS with no ceiling)
- every LLM call → daily token budget from `token_usage` (finally giving
  the write-only telemetry a consumer)

All limits are checked *before* external side effects; the API surfaces
402 + machine-readable `limit` fields so the dashboard can offer the
upgrade path.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import Message
from app.models.tenant import Tenant
from app.models.token_usage import TokenUsage
from app.models.user import User

logger = logging.getLogger(__name__)


class PlanLimitError(Exception):
    """Raised when an action would exceed the account's plan limits.

    ``code`` is machine-readable (dashboard uses it to offer the upgrade
    path); ``message`` is safe to show the merchant.
    """

    def __init__(self, code: str, message: str, plan: str, limit: int, current: int):
        self.code = code
        self.message = message
        self.plan = plan
        self.limit = limit
        self.current = current
        super().__init__(message)


@dataclass(frozen=True)
class PlanLimits:
    key: str
    name: str
    price_egp_month: float
    max_shops: int                     # tenants per user account
    max_channels_per_shop: int         # 3 platforms — fixed by schema
    max_messages_per_month: int        # inbound customer messages
    max_llm_tokens_per_day: int        # across ALL LLM usage types
    max_products: int
    features: tuple[str, ...] = field(default_factory=tuple)


PLANS: dict[str, PlanLimits] = {
    "free": PlanLimits(
        key="free",
        name="Free",
        price_egp_month=0.0,
        max_shops=1,
        max_channels_per_shop=3,
        max_messages_per_month=1_000,
        max_llm_tokens_per_day=50_000,
        max_products=200,
        features=("AI sales agent", "1 shop (FB/IG/WA)", "Order pipeline", "Style learning"),
    ),
    "growth": PlanLimits(
        key="growth",
        name="Growth",
        price_egp_month=299.0,
        max_shops=5,
        max_channels_per_shop=3,
        max_messages_per_month=10_000,
        max_llm_tokens_per_day=250_000,
        max_products=5_000,
        features=(
            "Everything in Free", "5 shops / multi-page", "Post scheduling",
            "Blog + SEO toolkit", "Priority crawl queue",
        ),
    ),
    "pro": PlanLimits(
        key="pro",
        name="Pro",
        price_egp_month=899.0,
        max_shops=25,
        max_channels_per_shop=3,
        max_messages_per_month=100_000,
        max_llm_tokens_per_day=1_000_000,
        max_products=50_000,
        features=(
            "Everything in Growth", "25 shops", "API access", "Dedicated support",
        ),
    ),
}

DEFAULT_PLAN = "free"


# ---------------------------------------------------------------------------
# Trial-aware plan resolution (product: 7-day free trial)
# ---------------------------------------------------------------------------

def effective_plan(user) -> str:
    """The plan the user's limits should come from RIGHT NOW.

    While a 7-day trial is active (user on the free plan with
    ``trial_ends_at`` in the future) the account enjoys Growth-level
    limits. Expiry is evaluated lazily here — no cron, no write — so the
    moment the clock passes ``trial_ends_at`` every gate drops back to the
    Free tier automatically.
    """
    plan = (getattr(user, "plan", None) or DEFAULT_PLAN).lower()
    trial_end = getattr(user, "trial_ends_at", None)
    if plan == DEFAULT_PLAN and trial_end is not None:
        from datetime import datetime as _dt

        try:
            if trial_end.tzinfo is not None:  # naive-vs-aware safety
                trial_end = trial_end.replace(tzinfo=None)
        except Exception:  # noqa: BLE001
            pass
        if trial_end > _dt.utcnow():
            return "growth"
    return plan


def trial_state(user) -> dict:
    """Trial summary for dashboards/``/api/me``."""
    trial_end = getattr(user, "trial_ends_at", None)
    active = False
    days_left = 0
    if trial_end is not None:
        from datetime import datetime as _dt

        end = trial_end.replace(tzinfo=None) if trial_end.tzinfo is not None else trial_end
        remaining = (end - _dt.utcnow()).total_seconds()
        active = remaining > 0
        days_left = max(0, min(7, int(remaining // 86_400) + (1 if remaining % 86_400 else 0)))
    return {
        "active": active,
        "ends_at": trial_end.isoformat() if trial_end else None,
        "days_left": days_left,
    }


def get_limits(plan: str | None) -> PlanLimits:
    return PLANS.get((plan or DEFAULT_PLAN).lower(), PLANS[DEFAULT_PLAN])


def plan_catalog() -> list[dict]:
    return [
        {
            "key": p.key,
            "name": p.name,
            "price_egp_month": p.price_egp_month,
            "max_shops": p.max_shops,
            "max_channels_per_shop": p.max_channels_per_shop,
            "max_messages_per_month": p.max_messages_per_month,
            "max_llm_tokens_per_day": p.max_llm_tokens_per_day,
            "max_products": p.max_products,
            "features": list(p.features),
        }
        for p in PLANS.values()
    ]


def get_limits_for_user(user) -> PlanLimits:
    """Limits for the user's EFFECTIVE plan (trial-aware)."""
    return get_limits(effective_plan(user))


# ---------------------------------------------------------------------------
# Counters
# ---------------------------------------------------------------------------

async def count_shops(db: AsyncSession, user: User) -> int:
    result = await db.execute(
        select(func.count(Tenant.id)).where(
            Tenant.owner_id == user.id, Tenant.is_active == True  # noqa: E712
        )
    )
    return int(result.scalar() or 0)


async def count_month_messages(db: AsyncSession, tenant: Tenant) -> int:
    """Inbound customer messages this calendar month (Africa/Cairo billing day)."""
    month_start = _month_start()
    result = await db.execute(
        select(func.count(Message.id)).where(
            Message.conversation_id.in_(
                select(Conversation_id_col()).where(
                    _conversation_tenant_col() == tenant.id
                )
            ),
            Message.role == "customer",
            Message.created_at >= month_start,
        )
    )
    return int(result.scalar() or 0)


async def count_day_llm_tokens(db: AsyncSession, tenant: Tenant) -> int:
    """Total LLM tokens consumed today (all usage types) for this tenant."""
    day_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    result = await db.execute(
        select(func.coalesce(func.sum(TokenUsage.total_tokens), 0)).where(
            TokenUsage.tenant_id == tenant.id,
            TokenUsage.created_at >= day_start,
        )
    )
    return int(result.scalar() or 0)


def _month_start() -> datetime:
    now = datetime.utcnow()
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _conversation_tenant_col():
    from app.models.conversation import Conversation
    return Conversation.tenant_id


def Conversation_id_col():
    from app.models.conversation import Conversation
    return Conversation.id


# ---------------------------------------------------------------------------
# Enforcement gates
# ---------------------------------------------------------------------------

async def check_can_create_shop(db: AsyncSession, user: User) -> None:
    limits = get_limits_for_user(user)
    current = await count_shops(db, user)
    if current >= limits.max_shops:
        raise PlanLimitError(
            code="shop_limit",
            message=(
                f"Your {limits.name} plan allows {limits.max_shops} shop(s). "
                "Upgrade to add more shops — each shop connects its own "
                "Facebook, Instagram and WhatsApp channel set."
            ),
            plan=limits.key,
            limit=limits.max_shops,
            current=current,
        )


async def check_message_quota(db: AsyncSession, tenant: Tenant, owner: User) -> None:
    """Raise when this tenant burned its monthly inbound-message quota."""
    limits = get_limits_for_user(owner)
    current = await count_month_messages(db, tenant)
    if current >= limits.max_messages_per_month:
        raise PlanLimitError(
            code="message_limit",
            message=(
                f"Monthly message quota exhausted ({limits.max_messages_per_month:,} "
                f"on the {limits.name} plan). The agent replies with a holding "
                "message until the quota resets or the plan is upgraded."
            ),
            plan=limits.key,
            limit=limits.max_messages_per_month,
            current=current,
        )


async def check_llm_budget(db: AsyncSession, tenant: Tenant, owner: User) -> int:
    """Return remaining tokens for today; raise when the budget is gone.

    This is the missing consumer of ``token_usage`` telemetry (audit A5-H1):
    the LLM ladder had no quota, so one spamming page burned the shared
    provider budget with no ceiling.
    """
    limits = get_limits_for_user(owner)
    used = await count_day_llm_tokens(db, tenant)
    if used >= limits.max_llm_tokens_per_day:
        raise PlanLimitError(
            code="llm_budget",
            message=(
                f"Daily AI budget exhausted ({limits.max_llm_tokens_per_day:,} tokens "
                f"on the {limits.name} plan). Replies fall back to canned responses "
                "until the budget resets at midnight UTC."
            ),
            plan=limits.key,
            limit=limits.max_llm_tokens_per_day,
            current=used,
        )
    return limits.max_llm_tokens_per_day - used


async def get_usage(db: AsyncSession, user: User) -> dict:
    """Usage vs limits for the dashboard's plan widget."""
    eff_plan = effective_plan(user)
    limits = get_limits(eff_plan)
    shops = await count_shops(db, user)

    tenants = (await db.execute(
        select(Tenant).where(Tenant.owner_id == user.id, Tenant.is_active == True)  # noqa: E712
    )).scalars().all()

    total_messages = 0
    total_tokens_today = 0
    for tenant in tenants:
        total_messages += await count_month_messages(db, tenant)
        total_tokens_today += await count_day_llm_tokens(db, tenant)

    return {
        "plan": {
            "key": limits.key,
            "name": limits.name,
            "price_egp_month": limits.price_egp_month,
            "features": list(limits.features),
            "effective": eff_plan,
        },
        "trial": trial_state(user),
        "usage": {
            "shops": {"used": shops, "limit": limits.max_shops},
            "messages_this_month": {
                "used": total_messages, "limit": limits.max_messages_per_month,
            },
            "llm_tokens_today": {
                "used": total_tokens_today, "limit": limits.max_llm_tokens_per_day,
            },
        },
    }
