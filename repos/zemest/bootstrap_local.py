"""Bootstrap script: create all tables + a demo tenant owner + superadmin.

Runs against the SQLite DB configured in .env (DATABASE_URL).
Usage: .venv/bin/python bootstrap_local.py
"""
import asyncio
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.config import get_settings
from app.database import Base, engine, async_session
from app.models.user import User
from app.models.tenant import Tenant

settings = get_settings()


async def main() -> None:
    # Import ALL models so metadata knows every table
    import app.models  # noqa: F401  (pulls in the full model registry)
    from app.models import (  # noqa: F401
        admin, conversation, crawl_job, customer, knowledge_base,
        message, order, product, scheduled_post, tenant, token_usage, user,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    from passlib.context import CryptContext
    pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

    async with async_session() as session:
        # Superadmin
        sa = (await session.execute(select(User).where(User.email == "admin@zemest.ai"))).scalar_one_or_none()
        if not sa:
            sa = User(
                id=uuid.uuid4(),
                email="admin@zemest.ai",
                hashed_password=pwd.hash("ChangeMe Superadmin 123"),
                name="Super Admin",
                is_superadmin=True,
            )
            session.add(sa)
            print("created superadmin admin@zemest.ai")

        # Tenant owner
        owner = (await session.execute(select(User).where(User.email == "owner@cairo-sneakers.com"))).scalar_one_or_none()
        if not owner:
            owner = User(
                id=uuid.uuid4(),
                email="owner@cairo-sneakers.com",
                hashed_password=pwd.hash("OwnerPass123"),
                name="Cairo Sneakers Owner",
                is_superadmin=False,
            )
            session.add(owner)
            print("created owner owner@cairo-sneakers.com")

        await session.flush()

        tenant = (await session.execute(select(Tenant).where(Tenant.page_name == "Cairo Sneakers"))).scalar_one_or_none()
        if not tenant:
            tenant = Tenant(
                id=uuid.uuid4(),
                page_name="Cairo Sneakers",
                owner_id=owner.id,
                business_phone="+201001234567",
                business_email="owner@cairo-sneakers.com",
                delivery_inside_cairo=35,
                delivery_outside_cairo=60,
                free_delivery_above=300,
                is_active=True,
            )
            session.add(tenant)
            print(f"created tenant Cairo Sneakers ({tenant.id})")

        # A couple of products so the shop has data
        from app.models.product import Product
        existing = (await session.execute(select(Product).where(Product.tenant_id == tenant.id))).scalars().all()
        if not existing:
            for name, price, stock in [
                ("Air Max 90 White", 1850.0, 12),
                ("Air Force 1 Black", 1650.0, 8),
                ("Running Pro V2", 2200.0, 5),
            ]:
                session.add(Product(
                    tenant_id=tenant.id, name=name, price=price,
                    is_active=True, source="manual",
                    attributes={"stock": stock, "category": "Sneakers"},
                ))
            print("created 3 products")

        await session.commit()
        print("BOOTSTRAP OK")


if __name__ == "__main__":
    asyncio.run(main())
