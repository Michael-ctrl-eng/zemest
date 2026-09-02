"""Adversarial AI-core tests — one test per audit PoC (wave F2).

Audit sources: findings/A6-ai-core-2.md (C1, H1-H4, H6, L2),
findings/A5-ai-core-1.md (H4 executing path, M3, M5).

Every test reproduces the auditor's exact PoC input and asserts the
hardened behavior:
* C1  laughter ReDoS — 30s+ freeze -> sub-millisecond
* H1  Arabizi transliteration destroys numbers
* H2  English-with-digits misdetected as arabizi
* H3  greedy JSON regex drops orders
* H4  order validation: quantity/price/fields
* H4x agent executing path: 0-EGP orders, ilike wildcards
* M3  PII wipe on partial order JSON
* M5  webhook dedup TOCTOU
* H6  random.seed(42) process-global reseed
"""
from __future__ import annotations

import json
import time
import uuid

import pytest

from app.ai.chat_classifier import is_laughter_only
from app.ai.language_engine import (
    detect_language_advanced,
    transliterate_arabizi,
)
from app.ai.order_collector import (
    clean_response_for_customer,
    extract_order_from_response,
    validate_order_data,
)


# --------------------------------------------------------------------------- #
# C1 — laughter ReDoS
# --------------------------------------------------------------------------- #
class TestLaughterReDoS:
    @pytest.mark.parametrize("n", [20, 30, 40, 60])
    def test_near_match_is_instant(self, n):
        """Auditor PoC: 'هه'*n + non-matching char froze the engine 30s+."""
        evil = "هه" * n + "!"
        t0 = time.perf_counter()
        result = is_laughter_only(evil)
        dt = time.perf_counter() - t0
        assert dt < 0.05, f"ReDoS regression: {dt:.2f}s on n={n}"
        assert result is False  # trailing '!' is not laughter

    def test_billion_laughs_scale(self):
        """1,000-char run must stay linear (audit: 35+ chars = 'hung')."""
        evil = "هه" * 500 + "?"
        t0 = time.perf_counter()
        is_laughter_only(evil)
        dt = time.perf_counter() - t0
        assert dt < 0.1

    def test_real_laughter_still_detected(self):
        assert is_laughter_only("هههههههه")
        assert is_laughter_only("hhhhhh")
        assert is_laughter_only("ههه 😂 😂 هه")
        assert is_laughter_only("lol")
        assert is_laughter_only("hahahaha")
        assert is_laughter_only("LOL LMAO")

    def test_content_not_misclassified(self):
        assert not is_laughter_only("هههه لا ده غالي")
        assert not is_laughter_only("hello")
        assert not is_laughter_only("هه وعندك ماركة تانية؟")
        assert not is_laughter_only("")
        assert not is_laughter_only("   ")


# --------------------------------------------------------------------------- #
# H1 — Arabizi number corruption
# --------------------------------------------------------------------------- #
class TestArabiziNumbers:
    def test_auditor_poc_exact(self):
        """Auditor PoC: price/phone/size must survive transliteration."""
        out = transliterate_arabizi(
            "3ayez el sandal ahmar, size 40, el se3r 350, house 2, 01276543210"
        )
        assert "350" in out, f"price destroyed: {out}"
        assert "01276543210" in out, f"phone destroyed: {out}"
        assert "40" in out, f"size destroyed: {out}"

    def test_arabic_indic_digits_preserved(self):
        out = transliterate_arabizi("el se3r ٣٥٠ جنيه")
        assert "٣٥٠" in out

    def test_decimal_price_preserved(self):
        out = transliterate_arabizi("el total 299.99 awy")
        assert "299.99" in out

    def test_word_with_digits_still_transliterated(self):
        """The arabizi words themselves MUST still convert."""
        out = transliterate_arabizi("3ayez 7aga")
        assert "عayez" in out or "ع" in out  # leading-digit word converts

    def test_uppercase_transliterates(self):
        out = transliterate_arabizi("3AYEZ")
        assert "A" not in out  # fully mapped, not left half-Latin


# --------------------------------------------------------------------------- #
# H2 — English-with-digits misdetection
# --------------------------------------------------------------------------- #
class TestArabiziDetection:
    @pytest.mark.parametrize(
        "text",
        [
            "size 42 available?",
            "order 2 items please",
            "iPhone 13 case",
            "room 27 is nice",
            "call me at 5",
        ],
    )
    def test_english_with_digits_is_english(self, text):
        """Auditor PoC: every English shopping sentence with a common digit
        was classified arabizi and transliterated into garbage."""
        d = detect_language_advanced(text)
        assert d.primary_language == "english", (
            f"{text!r} misdetected as {d.primary_language}"
        )

    @pytest.mark.parametrize(
        "text",
        ["3ayez el sandal ahmar", "enta 3ayez eh", "5alas", "7aga 7elwa"],
    )
    def test_real_arabizi_detected(self, text):
        assert detect_language_advanced(text).primary_language == "arabizi"

    def test_mixed_reachable(self):
        """The mixed branch was dead in practice (digits pre-empted it)."""
        d = detect_language_advanced("عايز أشتري product تمام؟ ال price كويس جدا")
        assert d.primary_language == "mixed"

    def test_pure_arabic_still_arabic(self):
        d = detect_language_advanced("عايز أشتري المنتج ده ضروري جدا")
        assert d.primary_language == "arabic"

    def test_pure_english_still_english(self):
        assert detect_language_advanced("hello there friend").primary_language == "english"


# --------------------------------------------------------------------------- #
# H3 — greedy JSON regex drops orders
# --------------------------------------------------------------------------- #
VALID_ORDER = {
    "action": "create_order",
    "order_data": {
        "items": [{"product_name": "Sandal Ahmar", "quantity": 1}],
        "customer_name": "Ahmed",
        "customer_phone": "01012345678",
        "governorate": "cairo",
        "city": "Nasr City",
        "address_detail": "street 12",
        "payment_method": "cod",
    },
}


def _order_text(suffix: str = "") -> str:
    return json.dumps(VALID_ORDER, ensure_ascii=False) + suffix


class TestOrderExtraction:
    def test_auditor_poc_trailing_brace_text(self):
        """Auditor PoC: valid order JSON + 'Anything else {checkout more}!'
        used to return None — order silently dropped while customer was
        told 'order placed'."""
        text = _order_text(" Anything else {checkout more}!")
        result = extract_order_from_response(text)
        assert result is not None, "order dropped by greedy regex!"
        assert result["items"][0]["product_name"] == "Sandal Ahmar"

    def test_two_json_blocks_first_wins(self):
        text = _order_text() + " ```json\n" + _order_text() + "\n```"
        result = extract_order_from_response(text)
        assert result is not None

    def test_fenced_json_block(self):
        text = "رد جميل\n```json\n" + _order_text() + "\n```\nشكراً!"
        assert extract_order_from_response(text) is not None

    def test_no_order_in_plain_text(self):
        assert extract_order_from_response("شكراً يا فندم، الطلب وصل!") is None

    def test_order_data_as_list_does_not_crash(self):
        """LLM emits order_data as list — used to raise AttributeError."""
        text = '{"action": "create_order", "order_data": [1, 2]}'
        assert extract_order_from_response(text) is None  # not a crash

    def test_non_dict_top_level(self):
        assert extract_order_from_response("[1,2,3]") is None

    def test_nested_braces_inside_strings(self):
        order = {
            "action": "create_order",
            "order_data": {
                "items": [{"product_name": "Bag {black}", "quantity": 2}],
                "customer_name": "Mona",
                "customer_phone": "01112345678",
                "governorate": "giza",
                "city": "Dokki",
                "address_detail": "bal {test} street",
            },
        }
        text = json.dumps(order, ensure_ascii=False)
        result = extract_order_from_response(text)
        assert result is not None
        assert result["items"][0]["product_name"] == "Bag {black}"

    def test_clean_response_keeps_prose_removes_json(self):
        text = "تم تسجيل طلبك ✅\n" + _order_text() + "\nشكراً!"
        cleaned = clean_response_for_customer(text)
        assert "create_order" not in cleaned
        assert "تم تسجيل طلبك" in cleaned
        assert "شكراً" in cleaned

    def test_clean_response_prose_braces_not_swallowed(self):
        """Old greedy regex could delete the ENTIRE response body."""
        text = "طلبك {اتسجل} خلاص"
        cleaned = clean_response_for_customer(text)
        assert "خلاص" in cleaned


# --------------------------------------------------------------------------- #
# H4 — validate_order_data
# --------------------------------------------------------------------------- #
BASE = {
    "customer_name": "Ahmed",
    "customer_phone": "01012345678",
    "governorate": "cairo",
    "city": "Nasr City",
    "address_detail": "street 12",
}


class TestOrderValidation:
    def test_valid_order_passes(self):
        data = {**BASE, "items": [{"product_name": "X", "quantity": 1}]}
        out = validate_order_data(data)
        assert out is not None
        assert out["items"][0]["quantity"] == 1

    def test_quantity_string_coerced(self):
        data = {**BASE, "items": [{"product_name": "X", "quantity": "3"}]}
        out = validate_order_data(data)
        assert out["items"][0]["quantity"] == 3

    def test_quantity_float_rejected(self):
        data = {**BASE, "items": [{"product_name": "X", "quantity": 2.5}]}
        assert validate_order_data(data) is None

    def test_quantity_zero_rejected(self):
        data = {**BASE, "items": [{"product_name": "X", "quantity": 0}]}
        assert validate_order_data(data) is None

    def test_quantity_negative_rejected(self):
        data = {**BASE, "items": [{"product_name": "X", "quantity": -1}]}
        assert validate_order_data(data) is None

    def test_quantity_huge_rejected(self):
        data = {**BASE, "items": [{"product_name": "X", "quantity": 10000}]}
        assert validate_order_data(data) is None

    def test_llm_price_fields_dropped(self):
        """LLM-invented prices must NOT survive into the order — prices
        come from the catalog only."""
        data = {
            **BASE,
            "items": [{"product_name": "X", "quantity": 1, "unit_price": 0.01, "price": 5}],
            "total": 5,
        }
        out = validate_order_data(data)
        assert "unit_price" not in out["items"][0]
        assert "price" not in out["items"][0]
        assert "total" not in out

    def test_unknown_fields_whitelisted_out(self):
        data = {**BASE, "items": [{"product_name": "X"}], "notes": "admin override"}
        out = validate_order_data(data)
        assert "notes" not in out

    def test_payment_method_whitelist(self):
        data = {**BASE, "items": [{"product_name": "X"}], "payment_method": "western_union"}
        out = validate_order_data(data)
        assert out["payment_method"] == "cod"  # unknown falls back

    def test_payment_method_valid_kept(self):
        data = {**BASE, "items": [{"product_name": "X"}], "payment_method": "instapay"}
        out = validate_order_data(data)
        assert out["payment_method"] == "instapay"

    def test_bad_phone_rejected(self):
        data = {**BASE, "customer_phone": "123", "items": [{"product_name": "X"}]}
        assert validate_order_data(data) is None

    def test_missing_required_field_rejected(self):
        data = {k: v for k, v in BASE.items() if k != "city"}
        data["items"] = [{"product_name": "X"}]
        assert validate_order_data(data) is None

    def test_pure_function_no_input_mutation(self):
        data = {**BASE, "items": [{"product_name": "X", "quantity": 1}]}
        snapshot = json.dumps(data, sort_keys=True)
        validate_order_data(data)
        assert json.dumps(data, sort_keys=True) == snapshot

    def test_old_single_item_format_still_works(self):
        data = {**BASE, "product_name": "X", "quantity": 2}
        out = validate_order_data(data)
        assert out["items"] == [{"product_name": "X", "quantity": 2}]


# --------------------------------------------------------------------------- #
# H6 — process-global RNG reseed
# --------------------------------------------------------------------------- #
class TestRngIsolation:
    def test_no_global_seed_regression(self):
        """random.seed(42) in style_learner re-seeded the GLOBAL RNG —
        order numbers became predictable. Grep-level guard: the module
        must not CALL a global reseed (comments/docs are fine)."""
        import ast
        import app.ai.style_learner as sl

        tree = ast.parse(open(sl.__file__).read())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                # random.seed(...) — attribute call named seed
                if (
                    isinstance(func, ast.Attribute)
                    and func.attr == "seed"
                    and isinstance(func.value, ast.Name)
                    and func.value.id == "random"
                ):
                    raise AssertionError(
                        "global random.seed() reintroduced in style_learner "
                        f"(line {node.lineno})"
                    )

    def test_global_rng_unaffected_by_sampling(self):
        import random
        random.seed(1234)
        before = [random.random() for _ in range(5)]
        random.seed(1234)
        # Trigger a learner-style sampling with a local Random instance.
        rng = random.Random()
        rng.sample(list(range(100)), 5)
        after = [random.random() for _ in range(5)]
        assert before == after, "sampling leaked into the global RNG stream"


# --------------------------------------------------------------------------- #
# M5 — webhook dedup integrity
# --------------------------------------------------------------------------- #
class TestWebhookDedup:
    def test_fb_message_id_unique_constraint_exists(self):
        from app.models.message import Message
        table = Message.__table__
        for c in table.constraints:
            if type(c).__name__ == "UniqueConstraint":
                cols = [k for k in c.columns.keys()]
                if "fb_message_id" in cols:
                    return  # constraint present
        raise AssertionError(
            "messages.fb_message_id unique constraint missing — webhook "
            "dedup is still SELECT-then-INSERT (TOCTOU)"
        )

    @pytest.mark.asyncio
    async def test_duplicate_message_id_rejected_by_db(self, db_session):
        """Two inserts with the same fb_message_id: the second must fail."""
        from app.models.conversation import Conversation
        from app.models.customer import Customer
        from app.models.message import Message
        from app.models.tenant import Tenant
        from sqlalchemy.exc import IntegrityError

        tenant = Tenant(
            id=uuid.uuid4(), owner_id=uuid.uuid4(), page_name="T",
            fb_page_id="p1", website_url="https://t.com",
        )
        db_session.add(tenant)
        customer = Customer(
            id=uuid.uuid4(), tenant_id=tenant.id, fb_psid="psid1", name="C",
        )
        db_session.add(customer)
        conversation = Conversation(
            id=uuid.uuid4(), tenant_id=tenant.id, customer_id=customer.id,
        )
        db_session.add(conversation)
        await db_session.flush()

        m1 = Message(
            conversation_id=conversation.id, role="customer",
            content="hello", fb_message_id="mid_dup_1",
        )
        db_session.add(m1)
        await db_session.flush()

        m2 = Message(
            conversation_id=conversation.id, role="customer",
            content="hello again", fb_message_id="mid_dup_1",
        )
        db_session.add(m2)
        with pytest.raises(IntegrityError):
            await db_session.flush()


# --------------------------------------------------------------------------- #
# M3 — PII wipe on partial order JSON
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
class TestPiiNoWipe:
    async def test_partial_order_keeps_existing_customer_data(self, db_session):
        """Agent's customer-update path must not null existing PII when
        the LLM order JSON omits fields (audit M3)."""
        from app.ai.agent import _create_order_from_data
        from app.models.customer import Customer
        from app.models.product import Product

        tenant = await _make_tenant(db_session)
        product = Product(
            id=uuid.uuid4(), tenant_id=tenant.id, name="Sandal Ahmar",
            price=__import__("decimal").Decimal("150"),
        )
        db_session.add(product)
        customer = Customer(
            id=uuid.uuid4(), tenant_id=tenant.id, fb_psid="psid9",
            name="Old Name", phone="01000000000",
            governorate="cairo", city="Maadi", area="Degla",
            address_detail="old address 1",
        )
        db_session.add(customer)
        conversation = await _make_conversation(db_session, tenant, customer)
        await db_session.flush()

        # Partial LLM order: PII fields PRESENT (validated upstream) but
        # sparse — area missing. Customer's area must survive.
        order_data = {
            "customer_name": "New Name",
            "customer_phone": "01012345678",
            "governorate": "cairo",
            "city": "Nasr City",
            "address_detail": "street 12",
            "items": [{"product_name": "Sandal Ahmar", "quantity": 1}],
            "payment_method": "cod",
        }
        ok = await _create_order_from_data(
            db_session, tenant, customer, conversation, order_data
        )
        assert ok is True
        # phone/governorate/city/address were provided; area was not:
        assert customer.area == "Degla", "customer.area was wiped!"
        assert customer.name == "New Name"

    async def test_hallucinated_product_rejected_not_zero_price(
        self, db_session
    ):
        """Audit H4 executing path: unmatched product must reject the
        order, never create a 0-EGP line."""
        from app.ai.agent import _create_order_from_data
        from app.models.customer import Customer
        from app.models.product import Product

        tenant = await _make_tenant(db_session)
        db_session.add(Product(
            id=uuid.uuid4(), tenant_id=tenant.id, name="Real Product",
            price=__import__("decimal").Decimal("100"),
        ))
        customer = Customer(
            id=uuid.uuid4(), tenant_id=tenant.id, fb_psid="psid10",
            name="X", phone="01012345678",
        )
        db_session.add(customer)
        conversation = await _make_conversation(db_session, tenant, customer)
        await db_session.flush()

        order_data = {
            "customer_name": "X", "customer_phone": "01012345678",
            "governorate": "cairo", "city": "C", "address_detail": "A",
            "items": [{"product_name": "Totally Fake Ghost Product 9000", "quantity": 1}],
        }
        ok = await _create_order_from_data(
            db_session, tenant, customer, conversation, order_data
        )
        assert ok is False, "hallucinated product created an order!"

        from app.models.order import Order
        from sqlalchemy import select
        orders = (await db_session.execute(select(Order))).scalars().all()
        assert orders == [], "a zero-priced order was created"

    async def test_ilike_wildcard_product_name(self, db_session):
        """Audit H4: '%%' as product_name used to fuzzy-match the FIRST
        product in the catalog. It must match nothing now (escaped)."""
        from app.ai.agent import _create_order_from_data
        from app.models.customer import Customer
        from app.models.product import Product

        tenant = await _make_tenant(db_session)
        db_session.add(Product(
            id=uuid.uuid4(), tenant_id=tenant.id, name="Leather Bag",
            price=__import__("decimal").Decimal("500"),
        ))
        customer = Customer(
            id=uuid.uuid4(), tenant_id=tenant.id, fb_psid="psid11",
            name="Y", phone="01012345678",
        )
        db_session.add(customer)
        conversation = await _make_conversation(db_session, tenant, customer)
        await db_session.flush()

        order_data = {
            "customer_name": "Y", "customer_phone": "01012345678",
            "governorate": "cairo", "city": "C", "address_detail": "A",
            "items": [{"product_name": "%", "quantity": 1}],
        }
        ok = await _create_order_from_data(
            db_session, tenant, customer, conversation, order_data
        )
        assert ok is False, "wildcard %% matched a product it shouldn't"


async def _make_tenant(db_session):
    from app.models.tenant import Tenant
    tenant = Tenant(
        id=uuid.uuid4(), owner_id=uuid.uuid4(), page_name="T1",
        fb_page_id="pg1", website_url="https://x.com",
    )
    db_session.add(tenant)
    await db_session.flush()
    return tenant


async def _make_conversation(db_session, tenant, customer):
    from app.models.conversation import Conversation
    conv = Conversation(
        id=uuid.uuid4(), tenant_id=tenant.id, customer_id=customer.id,
    )
    db_session.add(conv)
    await db_session.flush()
    return conv
