"""Billing test-suite fixtures (post-Stripe rails).

The root conftest provides db_session/client/test_user/test_tenant —
here we add billing-specific helpers: patched provider credentials on
the cached Settings singleton, fake checkout sessions and a fake USDC
chain for offline settlement tests.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.config import get_settings
from app.models.billing import (
    BillingPlan,
    BillingSubscription,
    BillingTransaction,
    PaymentMethod,
)
from app.services.billing.providers.base import CheckoutResult

# A syntactically valid Solana pubkey (32 zero bytes in base58).
VALID_WALLET = "1" * 32

PAYONEER_TEST_TOKEN = "payoneer-test-token"
PAYONEER_TEST_SECRET = "payoneer-whsec-test"
PAYMOB_TEST_SECRET = "paymob-hmac-test"


@pytest.fixture
def billing_settings(monkeypatch):
    """Configure the cached Settings singleton for billing tests.

    monkeypatch restores the original attributes afterwards, so other
    suites (which assert fail-closed behavior on empty secrets) are
    unaffected.
    """
    s = get_settings()
    monkeypatch.setattr(s, "PAYONEER_API_TOKEN", PAYONEER_TEST_TOKEN)
    monkeypatch.setattr(s, "PAYONEER_WEBHOOK_SECRET", PAYONEER_TEST_SECRET)
    monkeypatch.setattr(s, "PAYMOB_API_KEY", "paymob-test-key")
    monkeypatch.setattr(s, "PAYMOB_INTEGRATION_IDS", "12345,6789")
    monkeypatch.setattr(s, "PAYMOB_WEBHOOK_HMAC_SECRET", PAYMOB_TEST_SECRET)
    monkeypatch.setattr(s, "USDC_TREASURY_WALLET", VALID_WALLET)
    monkeypatch.setattr(s, "USDC_CONFIRMATIONS_REQUIRED", 32)
    return s


def fake_checkout(provider: str, reference: str, url: str = "https://checkout.example/pay") -> CheckoutResult:
    return CheckoutResult(
        provider=provider,
        provider_reference=f"sess_{reference[:8]}",
        checkout_url=url,
        amount=Decimal("38.54"),
        currency="USD" if provider == "payoneer" else "EGP",
        deposit_address=VALID_WALLET if provider == "usdc_solana" else "",
        reference_memo=reference if provider == "usdc_solana" else "",
    )


@pytest.fixture
def fake_payoneer_checkout(monkeypatch):
    """Patch the Payoneer provider class: no HTTP, deterministic session."""
    from app.services.billing.providers.payoneer import PayoneerProvider

    async def _create(self, **kwargs):
        return fake_checkout("payoneer", kwargs["reference"])

    monkeypatch.setattr(PayoneerProvider, "create_checkout", _create)
    return _create


@pytest.fixture
def fake_paymob_checkout(monkeypatch):
    from app.services.billing.providers.paymob import PaymobBillingProvider

    async def _create(self, **kwargs):
        return fake_checkout(
            "paymob", kwargs["reference"], url="https://accept.example/checkout"
        )

    monkeypatch.setattr(PaymobBillingProvider, "create_checkout", _create)
    return _create


@pytest_asyncio.fixture
async def billing_plan(db_session):
    """One seeded plan (starter)."""
    from app.services.billing.subscription_engine import ensure_default_plans

    await ensure_default_plans(db_session)
    return await db_session.scalar(
        select(BillingPlan).where(BillingPlan.code == "starter")
    )


class FakeChain:
    """Deterministic offline Solana rail for settlement tests."""

    def __init__(self):
        self.deposits: list[dict] = []

    def add_deposit(self, amount_micro: int, reference: str | None = None,
                    confirmations: int = 40, status: str = "finalized") -> dict:
        deposit = {
            "signature": f"sig{uuid.uuid4().hex[:16]}",
            "slot": 123_000_000,
            "confirmations": confirmations,
            "confirmation_status": status,
            "amount_micro": amount_micro,
            "memos": [reference] if reference else [],
        }
        self.deposits.append(deposit)
        return deposit


@pytest.fixture
def fake_chain():
    return FakeChain()


@pytest.fixture
def fake_usdc_provider(monkeypatch, fake_chain):
    """UsdcSolanaProvider whose RPC surface is replaced by FakeChain."""
    from app.services.billing.providers.usdc_solana import UsdcSolanaProvider

    class _FakeUsdcProvider(UsdcSolanaProvider):
        def __init__(self):
            super().__init__()
            self.chain = fake_chain

        async def find_deposits(self, limit=None):
            return list(self.chain.deposits)

    instance = _FakeUsdcProvider()
    import app.services.billing.providers as registry
    import app.services.billing.subscription_engine as engine_mod

    def _fake_get_provider(name, **kw):
        if name == PaymentMethod.USDC_SOLANA:
            return instance
        return registry._PROVIDER_CLASSES[name](**kw)

    # Patch BOTH binding sites: the registry package and the engine's
    # direct import (settle_usdc_invoices resolves the provider via its
    # own module-level name).
    monkeypatch.setattr(registry, "get_provider", _fake_get_provider)
    monkeypatch.setattr(engine_mod, "get_provider", _fake_get_provider)
    return instance


async def make_pending_invoice(
    db_session,
    subscription: BillingSubscription,
    *,
    method: str = PaymentMethod.PAYONEER,
    amount: Decimal = Decimal("38.54"),
    amount_usdc: Decimal | None = None,
    created_days_ago: float = 0,
    solana_reference: str | None = "zm-ref-test",
) -> BillingTransaction:
    """Insert one open invoice directly (bypasses provider calls)."""
    when = datetime.utcnow() - timedelta(days=created_days_ago)
    txn = BillingTransaction(
        id=uuid.uuid4(),
        tenant_id=subscription.tenant_id,
        subscription_id=subscription.id,
        plan_id=subscription.plan_id,
        kind="subscription_payment",
        payment_method=method,
        status="pending",
        amount=amount,
        amount_usdc=amount_usdc,
        currency="USD" if method == PaymentMethod.PAYONEER else
                 ("USDC" if method == PaymentMethod.USDC_SOLANA else "EGP"),
        idempotency_key=f"test-{uuid.uuid4()}",
        provider_reference="sess_test",
        solana_reference=solana_reference if method == PaymentMethod.USDC_SOLANA else None,
    )
    txn.created_at = when
    db_session.add(txn)
    await db_session.commit()
    await db_session.refresh(txn)
    return txn


@pytest_asyncio.fixture
async def subscription(db_session, test_tenant, billing_plan, billing_settings):
    """An active subscription on the starter plan (payoneer rail)."""
    sub = BillingSubscription(
        tenant_id=test_tenant.id,
        plan_id=billing_plan.id,
        payment_method=PaymentMethod.PAYONEER,
        status="active",
        current_period_start=datetime.utcnow(),
        current_period_end=datetime.utcnow() + timedelta(days=31),
    )
    db_session.add(sub)
    await db_session.commit()
    await db_session.refresh(sub)
    return sub
