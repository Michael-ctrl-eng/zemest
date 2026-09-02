"""Silent trainer tests — classifier accuracy, profile build, crash-resume.

The contract under test (what the user asked for):
1. Junk chats (owner's friends) vs work chats are separated automatically.
2. The trainer runs with zero user interaction and builds a style profile
   that only reflects COMMERCE conversations.
3. A crash/interruption resumes exactly where it stopped — already
   classified conversations are not reprocessed, and state converges.
4. New-page cold start still produces a usable profile (buyer language
   from even a handful of messages).
5. The learned profile actually reaches the reply prompt (exemplars,
   buyer persona, greeting).
"""
import uuid
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.ai.chat_classifier import classify_messages, is_commerce
from app.ai.silent_trainer import run_tenant_cycle, TRAINER_VERSION
from app.models.conversation import Conversation
from app.models.customer import Customer
from app.models.message import Message
from app.models.tenant import Tenant

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def owner_user(db_session):
    from app.models.user import User
    from app.utils.security import hash_password
    user = User(id=uuid.uuid4(), name="Owner", email="trainer-test@example.com",
                hashed_password=hash_password("testpass123"))
    db_session.add(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def trainer_tenant(db_session, owner_user):
    tenant = Tenant(id=uuid.uuid4(), owner_id=owner_user.id, page_name="Cairo Kicks")
    db_session.add(tenant)
    await db_session.commit()
    return tenant


async def _add_conversation(db, tenant, msgs, age_minutes=0):
    customer = Customer(
        id=uuid.uuid4(), tenant_id=tenant.id,
        fb_psid=f"psid_{uuid.uuid4().hex[:8]}", name="Buyer",
    )
    db.add(customer)
    conv = Conversation(
        id=uuid.uuid4(), tenant_id=tenant.id, customer_id=customer.id,
        started_at=datetime.utcnow() - timedelta(minutes=age_minutes),
        last_message_at=datetime.utcnow() - timedelta(minutes=age_minutes),
    )
    db.add(conv)
    await db.flush()
    ts = datetime.utcnow() - timedelta(minutes=age_minutes)
    for role, content in msgs:
        db.add(Message(id=uuid.uuid4(), conversation_id=conv.id,
                       role=role, content=content, created_at=ts))
        ts += timedelta(seconds=1)
    conv.last_message_at = ts
    await db.commit()
    return conv


COMMERCE_THREAD = [
    ("customer", "السلام عليكم، الشنباط الأبيض بكام؟"),
    ("merchant", "أهلاً بيك، متوفر بـ 1250 جنيه"),
    ("customer", "مقاس 42 موجود؟"),
    ("merchant", "موجود مقاس 42 و 43، الشحن 35 جنيه جوه القاهرة"),
    ("customer", "تمام عايز اطلب واحد، عنواني المعادي القاهرة"),
    ("merchant", "حاضر، ابعتلي رقم موبايل وهأكد الطلب، الدفع كاش عند التوصيل"),
    ("customer", "01012345678"),
    ("merchant", "تم الطلب، هيوصلك خلال يومين"),
]

JUNK_THREAD = [
    ("customer", "فينك يا عم من يومين مش online"),
    ("customer", "ههههههههه"),
    ("customer", "شوف الماتش امبارح؟ الأهلي جاب 3"),
    ("merchant", "ههههه شفناه والله عظيم"),
    ("customer", "نتقابل بكرة في القعدة؟"),
    ("merchant", "تمام يا معلم أشوفك"),
]

MIXED_THREAD = [
    ("customer", "إزيك يا معلم عامل ايه"),
    ("customer", "الشنباط الجديد اللي نزل بكام؟"),
    ("merchant", "أهلا حبيبي تمام، هما بـ 1100 جنيه والتوصيل بيوصل تاني يوم"),
    ("customer", "حلو، هاخد واحدأسود مقاس 43"),
]

FRANCO_THREAD = [
    ("customer", "el sneakers da bekam?"),
    ("merchant", "1200 EGP ya gama3a, delivery byo gel 2 days"),
    ("customer", "ok ana ha5od size 42, address: maadi cairo"),
]


# ---------------------------------------------------------------------------
# 1. Classifier
# ---------------------------------------------------------------------------

async def test_classifier_separates_commerce_from_junk():
    commerce = classify_messages([{"role": r, "content": c} for r, c in COMMERCE_THREAD])
    assert commerce.label == "commerce", f"commerce thread misread: {commerce.label} {commerce.signals}"
    assert commerce.confidence > 0.5

    junk = classify_messages([{"role": r, "content": c} for r, c in JUNK_THREAD])
    assert junk.label == "junk", f"junk thread misread: {junk.label} {junk.signals}"

    mixed = classify_messages([{"role": r, "content": c} for r, c in MIXED_THREAD])
    # mixed with strong commerce evidence must be included in training
    assert is_commerce(mixed.label, mixed.commerce_score - mixed.junk_score)

    franco = classify_messages([{"role": r, "content": c} for r, c in FRANCO_THREAD])
    assert is_commerce(franco.label, franco.commerce_score - franco.junk_score), \
        f"franco thread should be commerce: {franco.label} {franco.signals}"


async def test_classifier_explains_itself():
    cls = classify_messages([{"role": r, "content": c} for r, c in COMMERCE_THREAD])
    assert any("price" in s for s in cls.signals)
    assert cls.signals, "signals must be stored for inspection"


# ---------------------------------------------------------------------------
# 2+3. Full cycle + profile build + crash-resume
# ---------------------------------------------------------------------------

async def test_cycle_classifies_and_builds_profile(db_session, trainer_tenant):
    c1 = await _add_conversation(db_session, trainer_tenant, COMMERCE_THREAD)
    c2 = await _add_conversation(db_session, trainer_tenant, JUNK_THREAD, age_minutes=30)
    c3 = await _add_conversation(db_session, trainer_tenant, MIXED_THREAD)
    c4 = await _add_conversation(db_session, trainer_tenant, FRANCO_THREAD, age_minutes=5)

    out = await run_tenant_cycle(db_session, trainer_tenant)
    assert out["classified"] == 4
    assert out["profiles_built"] == 1

    for conv_id, expected in ((c1.id, "commerce"), (c2.id, "junk")):
        conv = (await db_session.execute(
            select(Conversation).where(Conversation.id == conv_id)
        )).scalar_one()
        assert conv.classification == expected
        assert conv.classified_by  # stamped with classifier version
        assert conv.classification_signals  # explainable

    # profile exists, junk is invisible to the learner
    tenant = (await db_session.execute(
        select(Tenant).where(Tenant.id == trainer_tenant.id)
    )).scalar_one()
    profile = tenant.style_profile
    assert profile, "profile must be built automatically"
    stats = profile["commerce_stats"]
    assert stats["conversations"] == 3  # commerce + mixed + franco
    assert stats["junk_filtered"] == 1
    assert stats["merchant_messages"] >= 6

    # buyer persona learned from real buyers
    buyer = profile["buyer_persona"]
    assert buyer.get("language_mix")
    assert buyer.get("avg_message_chars", 0) > 0
    assert "franco" in str(buyer.get("language_mix", "")) or \
           "english" in str(buyer.get("language_mix", ""))  # franco thread counted

    # exemplars = real (customer, page reply) pairs from commerce chats only
    assert profile["exemplars"], "exemplars must be extracted"
    for ex in profile["exemplars"]:
        assert ex.get("customer") and ex.get("reply")

    # junk content must NOT leak into the learned voice
    vocab_blob = " ".join(profile.get("vocabulary", [])) + \
                 " ".join(str(ex["reply"]) for ex in profile["exemplars"])
    assert "الأهلي" not in vocab_blob and "نتقابل" not in vocab_blob

    # state checkpoint written
    state = tenant.training_state
    assert state["epochs"] == 1
    assert state["consecutive_errors"] == 0
    assert state["next_attempt_at"] is None
    assert state["stats"]["classified_conversations"] == 4


async def test_second_cycle_is_noop_and_new_messages_resume(db_session, trainer_tenant):
    await _add_conversation(db_session, trainer_tenant, COMMERCE_THREAD)
    await _add_conversation(db_session, trainer_tenant, JUNK_THREAD, age_minutes=30)
    first = await run_tenant_cycle(db_session, trainer_tenant)
    assert first["classified"] == 2

    # nothing changed → heartbeat, no re-classification, no rebuild
    second = await run_tenant_cycle(db_session, trainer_tenant)
    assert second["classified"] == 0
    assert second["profiles_built"] == 0

    # crash-sim: process dies, new message lands, daemon restarts → trainer
    # picks up ONLY the new conversation, keeps epoch continuity
    await _add_conversation(db_session, trainer_tenant, MIXED_THREAD)
    third = await run_tenant_cycle(db_session, trainer_tenant)
    assert third["classified"] == 1
    assert third["profiles_built"] == 1

    tenant = (await db_session.execute(
        select(Tenant).where(Tenant.id == trainer_tenant.id)
    )).scalar_one()
    assert tenant.training_state["epochs"] == 2  # resumed, not restarted
    assert tenant.style_profile["commerce_stats"]["conversations"] == 2


async def test_error_backoff_then_automatic_recovery(db_session, trainer_tenant, monkeypatch):
    await _add_conversation(db_session, trainer_tenant, COMMERCE_THREAD)

    # force a crash mid-cycle (production path: run_training_cycle_once
    # catches the tenant failure, records backoff, keeps the loop alive)
    from app.ai import silent_trainer as st

    async def boom(db, tenant, counts):
        raise RuntimeError("simulated crash")
    monkeypatch.setattr(st, "_rebuild_profile", boom)

    summary = await st.run_training_cycle_once(db_session)
    assert summary["errors"] == 1
    assert summary["profiles_built"] == 0

    tenant = (await db_session.execute(
        select(Tenant).where(Tenant.id == trainer_tenant.id)
    )).scalar_one()
    state = dict(tenant.training_state or {})
    assert state["consecutive_errors"] == 1
    assert state["last_error"] and "simulated crash" in state["last_error"]
    assert state["next_attempt_at"]  # retry scheduled in the future

    # classification progress SURVIVED the crash (granular checkpoint)
    conv_count = (await db_session.execute(
        select(Conversation).where(
            Conversation.tenant_id == trainer_tenant.id,
            Conversation.classification.is_not(None),
        )
    )).scalars().all()
    assert len(conv_count) == 1

    # backoff gates the next cycle…
    gated = await run_tenant_cycle(db_session, tenant)
    assert gated["skipped"] == 1
    assert gated["classified"] == 0

    # …and clears automatically once the window passes (self-heal: the
    # worker retries, the rebuild succeeds, backoff resets)
    from datetime import datetime as _dt
    tenant.training_state = {**tenant.training_state,
                             "next_attempt_at": (_dt.utcnow() - timedelta(minutes=1)).isoformat()}
    await db_session.commit()

    # restore the genuine rebuild (undo the monkeypatch)
    monkeypatch.undo()

    recovered = await run_tenant_cycle(db_session, tenant)
    assert recovered["profiles_built"] == 1
    tenant = (await db_session.execute(
        select(Tenant).where(Tenant.id == trainer_tenant.id)
    )).scalar_one()
    state = dict(tenant.training_state)
    assert state["consecutive_errors"] == 0
    assert state["next_attempt_at"] is None
    assert state["last_success_at"]


# ---------------------------------------------------------------------------
# 4. Cold start — brand new page, few messages
# ---------------------------------------------------------------------------

async def test_cold_start_new_page_still_learns_buyers(db_session, trainer_tenant):
    # brand-new page: 1 tiny conversation, no merchant replies at all
    await _add_conversation(db_session, trainer_tenant, [
        ("customer", "السلام عليكم"),
        ("customer", "الكرواسون بكام؟"),
    ])
    out = await run_tenant_cycle(db_session, trainer_tenant)
    assert out["profiles_built"] == 1

    tenant = (await db_session.execute(
        select(Tenant).where(Tenant.id == trainer_tenant.id)
    )).scalar_one()
    profile = tenant.style_profile
    # seeded merchant voice (natural Egyptian seller) + real buyer stats
    assert profile["seeded"] is True
    assert profile["greeting_patterns"]  # seed greetings exist
    st = profile["silent_training"]
    assert st["stage"] == "warming"
    assert st["maturity"] < 0.75  # keeps training as data grows


# ---------------------------------------------------------------------------
# 5. The learned profile reaches the reply prompt
# ---------------------------------------------------------------------------

async def test_profile_reaches_system_prompt():
    from app.ai.prompts import get_system_prompt
    profile = {
        "tone": "friendly",
        "greeting_patterns": ["أهلاً بيكم"],
        "signoff_patterns": ["تحياتي"],
        "emoji_use": 0.0,
        "avg_length_chars": 55.0,
        "vocabulary": ["متوفر", "مقاس"],
        "buyer_persona": {
            "language_mix": {"arabic": 0.8, "arabizi": 0.2},
            "dialects": {"egyptian": 1.0},
            "franco_ratio": 0.2,
            "avg_message_chars": 24.0,
        },
        "exemplars": [
            {"customer": "الشنباط بكام؟", "reply": "متوفر بـ 1250 جنيه، مقاسك إيه؟"},
        ],
    }
    prompt = get_system_prompt(
        business_name="Cairo Kicks",
        products_context="- Test Shoe: 1250 ج.م",
        style_profile=profile,
    )
    assert "أهلاً بيكم" in prompt          # greeting reaches prompt
    assert "متوفر بـ 1250 جنيه" in prompt  # exemplar few-shot reaches prompt
    assert "عملاء الصفحة" in prompt         # buyer persona section present
    assert "فرانكو" in prompt               # franco guidance present
    assert "55 حرف" in prompt               # length guidance present
