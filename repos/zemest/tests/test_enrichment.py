"""Chat enrichment: zero-cost intelligence extraction from customer messages
(age, phone, email, governorate, interests, sentiment, intent) + folding
into the customer profile + message.enrichment wiring.
"""
from __future__ import annotations

import uuid

import pytest

from app.ai.enrichment import (
    apply_enrichment,
    detect_intent,
    detect_sentiment,
    enrich_text,
    extract_age,
    extract_email,
    extract_governorate,
    extract_interests,
    extract_phone,
)
from app.models.customer import Customer
from app.models.message import Message


class TestExtraction:
    def test_egyptian_phone_formats(self):
        for text, expected in (
            ("كلمني على 01012345678", "01012345678"),
            ("رقمي 201012345678 لو سمحت", "01012345678"),
            ("+201012345678؟", "01012345678"),
            ("my number is 01112345678", "01112345678"),
        ):
            assert extract_phone(text) == expected, text

    def test_no_false_positive_phones(self):
        assert extract_phone("الطلب رقم 12345") is None
        assert extract_phone("سعره 1500 جنيه") is None

    def test_age_english_and_arabic(self):
        assert extract_age("I am 25 years old") == 25
        assert extract_age("ana 3andi 30 sana") is None  # Arabizi — no unit keyword
        assert extract_age("عمري ٢٥ سنة") == 25
        assert extract_age("عمري 25 سنة") == 25

    def test_age_rejects_implausible(self):
        assert extract_age("I am 5 years old") is None
        assert extract_age("I am 250 years old") is None

    def test_email(self):
        assert extract_email("ابعتلي على ali@gmail.com لو سمحت") == "ali@gmail.com"
        assert extract_email("مفيش ايميل هنا") is None

    def test_governorate_detected(self):
        assert extract_governorate("انا في اسكندرية") == "alexandria"
        assert extract_governorate("ساكن في القاهره") == "cairo"
        assert extract_governorate("I live in Giza") == "giza"
        assert extract_governorate("i am from port said") == "port-said"
        assert extract_governorate("مفيش حاجة هنا") is None

    def test_interests_extracted(self):
        tags = extract_interests("عايز اعرف المقاسات المتاحة والتوصيل بكام؟")
        assert "sizes" in tags
        assert "delivery" in tags

    def test_sentiment(self):
        assert detect_sentiment("شكرا جدا، المنتج تحفة 👌") == "positive"
        assert detect_sentiment("تأخير ١٠ ايام وغالي جدا 😡") == "negative"
        assert detect_sentiment("عايز اعرف السعر") == "neutral"

    def test_intent(self):
        assert detect_intent("السعر كام؟") == "price_query"
        assert detect_intent("عايز اشتري الجلبية") == "ordering"
        assert detect_intent("الشحنة متأخرة ومشكلة") == "complaint"
        assert detect_intent("hello") == "greeting"
        assert detect_intent("is this available?") == "question"


class TestApplyEnrichment:
    def _customer(self) -> Customer:
        return Customer(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            fb_psid="psid_1",
            channel="whatsapp",
            name="سارة",
        )

    def _message(self) -> Message:
        return Message(
            id=uuid.uuid4(),
            conversation_id=uuid.uuid4(),
            role="customer",
            content="",
            channel="whatsapp",
        )

    def test_message_enrichment_attached_with_context(self):
        msg = self._message()
        payload = apply_enrichment(
            msg, self._customer(), "عمري ٢٥ سنة وابعت على 01012345678", "whatsapp"
        )
        assert msg.enrichment is not None
        assert payload["channel"] == "whatsapp"
        assert payload["detected_at"]
        assert payload["intent"] in ("chat", "question")

    def test_customer_profile_folded(self):
        customer = self._customer()
        msg = self._message()
        payload = apply_enrichment(
            msg, customer,
            "انا من المنصورة في الدقهلية، عمري ٢٢ سنة، عايزة اعرف المقاسات",
            "messenger",
        )
        # Age stays in the enrichment payload (DOB is real PII, not a guess).
        assert payload["age"] == 22
        assert customer.governorate == "dakahlia"
        assert customer.phone is None  # no phone in this message
        assert "sizes" in (customer.interests or [])
        assert customer.country == "Egypt"

    def test_interests_accumulate_across_messages(self):
        customer = self._customer()
        msg1 = self._message()
        msg2 = self._message()
        apply_enrichment(msg1, customer, "المقاسات ايه؟", "whatsapp")
        apply_enrichment(msg2, customer, "التوصيل بكام؟", "whatsapp")
        assert "sizes" in customer.interests
        assert "delivery" in customer.interests
        assert len(customer.interests) == len(set(customer.interests))  # no dups

    def test_existing_customer_fields_not_overwritten(self):
        customer = self._customer()
        customer.phone = "01234567890"
        msg = self._message()
        apply_enrichment(msg, customer, "كلمني على 01012345678", "whatsapp")
        assert customer.phone == "01234567890"  # first value wins

    def test_none_customer_is_tolerated(self):
        msg = self._message()
        payload = apply_enrichment(msg, None, "hello", "instagram")
        assert payload["sentiment"] is not None

    def test_arabic_indic_digits_phone(self):
        customer = self._customer()
        msg = self._message()
        # ٠١٠ ١٢٣ ٤٥ ٦٧٨ = 01012345678 in Arabic-Indic digits.
        apply_enrichment(msg, customer, "رقمي ٠١٠١٢٣٤٥٦٧٨", "whatsapp")
        assert customer.phone is not None
        assert customer.phone.endswith("12345678")
