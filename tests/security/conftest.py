"""Fixtures shared across the security tests.

Adds:
- ``second_user`` / ``second_auth_headers`` / ``second_tenant`` — for IDOR tests
- ``isolated_rate_limiter`` — fresh in-memory limiter per test
- ``arbitrary_user_token`` — JWT signed with the real secret but for a
  non-existent user ID (to test token-valid-but-user-deleted scenarios)
"""
from __future__ import annotations

import os
import sys
import uuid
from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Import root conftest so shared fixtures (client, db_session, test_user,
# auth_headers, test_tenant, …) are available.
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.dependencies import get_current_user, get_tenant  # noqa: E402
from app.main import app  # noqa: E402
from app.middleware.rate_limiter import RateLimiter  # noqa: E402
from app.models.tenant import Tenant  # noqa: E402
from app.models.user import User  # noqa: E402
from app.utils.security import create_access_token, hash_password  # noqa: E402


@pytest_asyncio.fixture
async def second_user(db_session):
    """A second, fully-independent user (for cross-tenant IDOR tests)."""
    user = User(
        id=uuid.uuid4(),
        name="Attacker User",
        email="attacker@example.com",
        hashed_password=hash_password("attackerpass123"),
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def second_auth_headers(second_user):
    token = create_access_token({"sub": str(second_user.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def second_tenant(db_session, second_user):
    """Tenant owned by second_user."""
    tenant = Tenant(
        id=uuid.uuid4(),
        owner_id=second_user.id,
        page_name="Attacker Store",
        fb_page_id="attacker_page_456",
        website_url="https://attacker.com",
        business_email="attacker@attacker.com",
        business_phone="01098765432",
        notification_pref="email",
    )
    db_session.add(tenant)
    await db_session.commit()
    return tenant


@pytest_asyncio.fixture
async def isolated_rate_limiter():
    """Fresh in-memory rate limiter (limit=5, window=60s) for each test."""
    return RateLimiter(limit=5, window_seconds=60)


@pytest.fixture
def arbitrary_user_token():
    """JWT signed with the real secret but for a random non-existent user.

    Used to test scenarios where the token decodes successfully but the
    user no longer exists (e.g., account deleted).
    """
    fake_user_id = str(uuid.uuid4())
    return create_access_token({"sub": fake_user_id}), fake_user_id
