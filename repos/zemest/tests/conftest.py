import asyncio
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings
from app.database import Base, get_db
from app.main import app
from app.models.user import User
from app.models.tenant import Tenant
from app.models.product import Product
from app.models.customer import Customer
from app.models.conversation import Conversation
from app.models.message import Message
from app.utils.security import create_access_token

# Use SQLite for tests (in-memory)
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session():
    async with TestSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_user(db_session):
    from app.utils.security import hash_password
    user = User(
        id=uuid.uuid4(),
        name="Test User",
        email="test@example.com",
        hashed_password=hash_password("testpass123"),
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def auth_headers(test_user):
    token = create_access_token({"sub": str(test_user.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def test_tenant(db_session, test_user):
    tenant = Tenant(
        id=uuid.uuid4(),
        owner_id=test_user.id,
        page_name="Test Fashion Store",
        fb_page_id="test_page_123",
        website_url="https://teststore.com",
        business_email="owner@teststore.com",
        business_phone="01012345678",
        notification_pref="email",
    )
    db_session.add(tenant)
    await db_session.commit()
    return tenant


@pytest_asyncio.fixture
async def test_products(db_session, test_tenant):
    products = [
        Product(
            id=uuid.uuid4(),
            tenant_id=test_tenant.id,
            name="Cotton Galabiya",
            price=Decimal("1500.00"),
            source="manual",
            attributes={
                "name_ar": "جلابية قطن",
                "description": "Premium quality cotton galabiya",
                "discount_price": 1200,
                "category": "Clothing",
                "sku": "GAL-001",
                "stock_status": "in_stock",
                "material": "cotton",
            },
        ),
        Product(
            id=uuid.uuid4(),
            tenant_id=test_tenant.id,
            name="Leather Bag",
            price=Decimal("2500.00"),
            source="manual",
            attributes={
                "name_ar": "حقيبة جلد",
                "description": "Elegant leather bag",
                "category": "Clothing",
                "sku": "PUN-001",
                "stock_status": "in_stock",
                "sizes": "M, L, XL",
            },
        ),
        Product(
            id=uuid.uuid4(),
            tenant_id=test_tenant.id,
            name="Leather Wallet",
            price=Decimal("800.00"),
            source="manual",
            attributes={
                "description": "Genuine leather wallet",
                "category": "Accessories",
                "sku": "WAL-001",
                "stock_status": "out_of_stock",
                "color": "brown",
                "card_slots": 8,
            },
        ),
    ]
    for p in products:
        db_session.add(p)
    await db_session.commit()
    return products


@pytest_asyncio.fixture
async def test_customer(db_session, test_tenant):
    customer = Customer(
        id=uuid.uuid4(),
        tenant_id=test_tenant.id,
        fb_psid="test_psid_123",
        name="Ahmed",
        phone="01012345678",
        governorate="cairo",
        city="Cairo",
    )
    db_session.add(customer)
    await db_session.commit()
    return customer


@pytest_asyncio.fixture
async def test_conversation(db_session, test_tenant, test_customer):
    conv = Conversation(
        id=uuid.uuid4(),
        tenant_id=test_tenant.id,
        customer_id=test_customer.id,
        status="active",
    )
    db_session.add(conv)
    await db_session.flush()

    messages = [
        Message(
            id=uuid.uuid4(),
            conversation_id=conv.id,
            role="customer",
            content="What products do you have?",
        ),
        Message(
            id=uuid.uuid4(),
            conversation_id=conv.id,
            role="assistant",
            content="We have cotton galabiyas for 1200 EGP (discounted). Would you like to order?",
        ),
    ]
    for m in messages:
        db_session.add(m)
    await db_session.commit()
    return conv
