"""Seed the demo tenant (Cairo Sneakers) with realistic commerce + junk chats
so the silent trainer has real material to learn from and we can verify the
junk/commerce separation live."""
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

THREADS = [
    # (channel, days_ago, [(role, content), ...]) — role 'merchant' = the page
    # owner's own historic replies (like imported DYI history).
    ("messenger", 9, [
        ("customer", "السلام عليكم، النايك إير ماكس الأبيض بكام؟"),
        ("merchant", "أهلاً بيك، متوفر بـ 1250 جنيه ومقاساته كاملة"),
        ("customer", "مقاس 42 موجود؟"),
        ("merchant", "موجود 42 و 43، لو هتاخد النهاردة الشحن 35 جنيه جوه القاهرة"),
        ("customer", "تمام عايز أطلب واحد، أنا في المعادي القاهرة"),
        ("merchant", "حاضر ابعتلي رقم موبايل وهأكدلك الطلب، الدفع كاش عند التوصيل"),
        ("customer", "01012345678 اسمي أحمد"),
        ("merchant", "تم الطلب يا أحمد، هيوصلك خلال يومين إن شاء الله"),
    ]),
    ("instagram", 7, [
        ("customer", "el sneakers da bekam ??"),
        ("merchant", "1200 EGP ya gama3a, delivery byo2af tani yom"),
        ("customer", "ok ana ha5od size 42 el abyad"),
        ("merchant", "tmm 3andi el address? eb3atly el area w el telephone"),
        ("customer", "maadi, 01098765432"),
        ("merchant", "tamem el order et2akkad, hatslom 3la 2 days COD"),
    ]),
    ("whatsapp", 5, [
        ("customer", "مساء الخير، عايز أعرف الأديداس الجديد السعر بتاعه كام"),
        ("merchant", "مساء النور، الأديداس الجديد 1450 جنيه ومتوفر أسود وأبيض"),
        ("customer", "الأسود مقاس 43 هاخده، الشحن على الإسكندرية بكام"),
        ("merchant", "الشحن الإسكندرية 60 جنيه، بيوصل 3 أيام"),
        ("customer", "تمام أكد الطلب، العنوان سيدي جابر، رقمي 01112223344"),
        ("merchant", "أكدنا الطلب، رقم الطلب ORD-562، هتوصلك رسالة التأكيد"),
    ]),
    ("messenger", 3, [
        ("customer", "إزيك يا معلم عامل إيه"),
        ("customer", "الشنباط الجديد اللي نزل أمس بكام؟"),
        ("merchant", "أهلا حبيبي تمام الحمد لله، الجديد بـ 1100 جنيه"),
        ("customer", "حلو، فيه خصم لو أخدتتن؟"),
        ("merchant", "لو هتاخد زوج 2000 الاتنين، والتوصيل علينا"),
        ("customer", "ماشي هاخد التنين، وأكدلي وأنابه فلوس"),
    ]),
    # ---- JUNK: owner's friends chatting on the page ----
    ("messenger", 8, [
        ("customer", "فينك يا عم من يومين مش عامل online خالص"),
        ("customer", "هههههههه"),
        ("customer", "شفت الماتش امبارح؟ الأهلي جاب 3 في نص ساعة"),
        ("merchant", "ههههه والله شفته عظيم"),
        ("customer", "نتقابل بكرة في القعدة؟ ماما بتسلم عليك"),
        ("merchant", "تمام يا معلم أشوفك بكرة"),
    ]),
    ("messenger", 2, [
        ("customer", "https://youtu.be/dQw4w9WgXcQ"),
        ("customer", "ههههههه شوف ده"),
        ("customer", "lol"),
        ("customer", "بابا بيسأل عليك تعالى الغدا الاحد"),
        ("merchant", "ههههه تسلم، مااااشي اجي"),
    ]),
]


async def main():
    async with async_session() as db:
        tenant = (await db.execute(
            select(Tenant).where(Tenant.page_name == "Cairo Sneakers")
        )).scalar_one()

        created = 0
        for channel, days_ago, msgs in THREADS:
            base = datetime.utcnow() - timedelta(days=days_ago)
            customer = Customer(
                id=uuid.uuid4(), tenant_id=tenant.id,
                fb_psid=f"seed_{uuid.uuid4().hex[:10]}", name="Seeded Buyer",
                channel=channel,
            )
            db.add(customer)
            conv = Conversation(
                id=uuid.uuid4(), tenant_id=tenant.id, customer_id=customer.id,
                channel=channel, status="imported",
                started_at=base, last_message_at=base,
            )
            db.add(conv)
            await db.flush()
            ts = base
            for role, content in msgs:
                db.add(Message(
                    id=uuid.uuid4(), conversation_id=conv.id, role=role,
                    content=content, channel=channel, created_at=ts,
                ))
                ts += timedelta(seconds=90)
            conv.last_message_at = ts
            created += 1

        await db.commit()
        print(f"Seeded {created} conversations for {tenant.page_name} ({tenant.id})")


asyncio.run(main())
