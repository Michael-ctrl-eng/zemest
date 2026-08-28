"""Seed the database with a test user, tenant, and sample Egyptian products."""
import asyncio
import uuid
from decimal import Decimal

from app.database import async_session
from app.models.user import User
from app.models.tenant import Tenant
from app.models.product import Product
from app.utils.security import hash_password


async def seed():
    async with async_session() as db:
        user = User(
            id=uuid.uuid4(),
            name="Admin",
            email="admin@zemest.ai",
            hashed_password=hash_password("test123"),
        )
        db.add(user)
        await db.flush()

        tenant = Tenant(
            id=uuid.uuid4(),
            owner_id=user.id,
            page_name="Egyptian Fashion Store",
            fb_page_id="eg_fashion_123",
            website_url="https://example.com",
            business_email="admin@zemest.ai",
            business_phone="01012345678",
            notification_pref="email",
        )
        db.add(tenant)
        await db.flush()

        products = [
            Product(id=uuid.uuid4(), tenant_id=tenant.id, source="manual",
                name="Egyptian Cotton Galabiya", price=Decimal("450.00"), attributes={
                    "name_ar": "جلابية قطن مصري", "description": "Traditional Egyptian cotton galabiya.",
                    "discount_price": 380, "category": "Clothing", "sku": "GAL-001",
                    "stock_status": "in_stock", "material": "cotton", "color": "white",
                }),
            Product(id=uuid.uuid4(), tenant_id=tenant.id, source="manual",
                name="Handmade Khayamiya Wall Art", price=Decimal("1200.00"), attributes={
                    "name_ar": "خدامية يدوية", "description": "Traditional Egyptian tentmaker patchwork.",
                    "category": "Home Decor", "sku": "KHA-001",
                    "stock_status": "in_stock", "material": "cotton", "size": "90x90 cm",
                }),
            Product(id=uuid.uuid4(), tenant_id=tenant.id, source="manual",
                name="Papyrus Scroll - Pharaohs", price=Decimal("250.00"), attributes={
                    "name_ar": "بردي فرعون", "description": "Hand-painted papyrus scroll.",
                    "discount_price": 200, "category": "Art", "sku": "PAP-001",
                    "stock_status": "in_stock", "material": "papyrus",
                }),
            Product(id=uuid.uuid4(), tenant_id=tenant.id, source="manual",
                name="Sterling Silver Cartouche", price=Decimal("800.00"), attributes={
                    "name_ar": "كرتوش فضة", "description": "Personalized Egyptian cartouche necklace.",
                    "category": "Jewelry", "sku": "CAR-001",
                    "stock_status": "in_stock", "material": "sterling silver",
                }),
            Product(id=uuid.uuid4(), tenant_id=tenant.id, source="manual",
                name="Egyptian Leather Bag", price=Decimal("650.00"), attributes={
                    "name_ar": "حقيبة جلد مصري", "description": "Handcrafted leather shoulder bag.",
                    "discount_price": 550, "category": "Accessories", "sku": "BAG-001",
                    "stock_status": "in_stock", "material": "leather", "color": "brown",
                }),
            Product(id=uuid.uuid4(), tenant_id=tenant.id, source="manual",
                name="Copper Coffee Set (Finjan)", price=Decimal("950.00"), attributes={
                    "name_ar": "طقم قهوة نحاس", "description": "Traditional Egyptian copper coffee set with 6 finjan cups.",
                    "category": "Kitchen", "sku": "COF-001",
                    "stock_status": "in_stock", "material": "copper", "pieces": "pot + 6 cups",
                }),
        ]

        for p in products:
            db.add(p)

        await db.commit()

        print(f"\n{'='*50}")
        print(f"Seed completed!")
        print(f"{'='*50}")
        print(f"User email:    admin@zemest.ai")
        print(f"User password: test123")
        print(f"Tenant:        Egyptian Fashion Store")
        print(f"Tenant ID:     {tenant.id}")
        print(f"Products:      {len(products)} items seeded")
        print(f"{'='*50}")
        print(f"\nOpen http://localhost:8000/dashboard/login")
        print(f"Login and start chatting!\n")


if __name__ == "__main__":
    asyncio.run(seed())
