"""One more commerce conversation lands while the backend is down (or right
after a reap). The trainer must pick it up on the next cycle — and ONLY it."""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta

REPO = "/home/z/my-project/repos/zemest"
sys.path.insert(0, REPO)
os.chdir(REPO)
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./zemest_local.db"

from sqlalchemy import select
from app.database import async_session
from app.models.conversation import Conversation
from app.models.customer import Customer
from app.models.message import Message
from app.models.tenant import Tenant

MSGS = [
    ("customer", "مساء الخير، النايك الشنباط فيه مقاس 44؟"),
    ("merchant", "أهلاً مساء النور، موجود 44 آخر قطعتين"),
    ("customer", "بكام؟"),
    ("merchant", "1350 جنيه، الشحن 35 لو النهاردة"),
    ("customer", "هاخده، أنا مدينة نصر، رقمي 01234567890"),
    ("merchant", "تم الطلب، هيوصلك بكرة إن شاء الله"),
]


async def main():
    async with async_session() as db:
        tenant = (await db.execute(
            select(Tenant).where(Tenant.page_name == "Cairo Sneakers")
        )).scalar_one()
        base = datetime.utcnow() - timedelta(minutes=10)
        customer = Customer(
            id=uuid.uuid4(), tenant_id=tenant.id,
            fb_psid=f"seed_{uuid.uuid4().hex[:10]}", name="Late Buyer",
            channel="messenger",
        )
        db.add(customer)
        conv = Conversation(
            id=uuid.uuid4(), tenant_id=tenant.id, customer_id=customer.id,
            channel="messenger", status="imported",
            started_at=base, last_message_at=base,
        )
        db.add(conv)
        await db.flush()
        ts = base
        for role, content in MSGS:
            db.add(Message(
                id=uuid.uuid4(), conversation_id=conv.id, role=role,
                content=content, channel="messenger", created_at=ts,
            ))
            ts += timedelta(seconds=60)
        conv.last_message_at = ts
        await db.commit()
        print("Added 1 NEW commerce conversation while backend is down")


asyncio.run(main())
