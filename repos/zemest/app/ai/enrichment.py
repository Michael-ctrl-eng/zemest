"""Automatic chat enrichment — the "user intelligence" layer.

Every inbound customer message (WhatsApp / Messenger / Instagram) is scanned
server-side for structured intelligence, at ZERO extra cost (pure regex +
keyword heuristics, no LLM call):

* **sentiment** — positive/negative/neutral from emoji + keyword signals;
* **intent** — price_query | ordering | complaint | greeting | question | chat;
* **entities** — Egyptian phone numbers, email addresses, age, governorate,
  areas/cities, interest tags (products/categories the buyer keeps asking
  about);
* **when/where** — channel + timestamp + known customer geo at message time.

The extracted data is written to ``messages.enrichment`` AND folded into the
``Customer`` profile (age, interests list, phone, governorate/country) so
every conversation makes the buyer profile smarter. Profiles feed the
encrypted vault archives (see app/services/vault.py).
"""
from __future__ import annotations

import re
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer
from app.models.message import Message
from app.utils.egypt_address import normalize_egyptian_phone

# --------------------------------------------------------------------------- #
# Lexicons
# --------------------------------------------------------------------------- #

_POSITIVE_WORDS = {
    "شكرا", "شكراً", "تسلم", "جميل", "حلو", "تحفة", "ممتاز", "رائع", "زين",
    "تمام", "اوكي", "أوكي", "yes", "ok", "okay", "great", "perfect", "nice",
    "thanks", "thank", "love", "good", "awesome", "excellent",
}
_NEGATIVE_WORDS = {
    "غالي", "خراب", "سيء", "وحش", "زفت", "مشكله", "تأخير", "متأخر", "اسف",
    "استرجاع", "ارجاع", "شكوى", "غلط", "خربان", "مكسور", "تعبان",
    "expensive", "bad", "broken", "late", "refund", "complaint", "wrong",
    "problem", "issue", "scam", "fake",
}
_POSITIVE_EMOJI = ("😍", "🥰", "❤️", "❤", "💕", "👍", "👌", "🤩", "🔥", "✨",
                   "😃", "😄", "🙂", "😊", "🙏", "😎", "🥳")
_NEGATIVE_EMOJI = ("😡", "😠", "🤬", "😢", "😭", "💔", "👎", "😖", "😣",
                   "😞", "🤢", "🤮", "😤")

_PRICE_INTENT = {"كام", "بكام", "السعر", "سعر", "price", "how much", "cost",
                 "التمن", "فلوس"}
_ORDER_INTENT = {"عايز اشتري", "عيز اشتري", "اشتري", "اطلب", "أطلب", "اوردر",
                 "order", "buy", "purchase", "هاخد", "هاخذه", "نفسي اشتري",
                 "طلب", "اجيب", "عندي طلب"}
_COMPLAINT_INTENT = _NEGATIVE_WORDS
_GREETING_INTENT = {"سلام", "السلام", "اهلا", "أهلا", "هاي", "هلا", "مرحبا",
                    "hi", "hello", "hey", "صباح", "مساء"}

# Interest tags: keyword family -> canonical tag. Short and commerce-focused.
_INTEREST_MAP = {
    "شحنة": "delivery", "توصيل": "delivery", "شحن": "delivery",
    "delivery": "delivery", "shipping": "delivery", "شيبنج": "delivery",
    "خصم": "discounts", "عرض": "discounts", "تخفيض": "discounts",
    "discount": "discounts", "sale": "discounts", "سيل": "discounts",
    "صور": "photos", "صورة": "photos", "photo": "photos", "picture": "photos",
    "مقاس": "sizes", "مقاسات": "sizes", "size": "sizes", "sizes": "sizes",
    "لون": "colors", "الوان": "colors", "color": "colors", "colors": "colors",
    "متاح": "availability", "موجود": "availability", "stock": "availability",
    "متوفر": "availability", "available": "availability",
    "كشف": "cod", "الدفع عند الاستلام": "cod", "cod": "cod",
    "فيزا": "payment", "انستابي": "payment", "instapay": "payment",
    "فودافون كاش": "payment", "payment": "payment",
    "ملابس": "clothing", "قميص": "clothing", "تيشيرت": "clothing",
    "لبس": "clothing", "dress": "clothing", "fashion": "clothing",
    "احذية": "shoes", "حذاء": "shoes", "shoe": "shoes", "shoes": "shoes",
    "شنطة": "bags", "شنتة": "bags", "bag": "bags", "bags": "bags",
    "ساعة": "watches", "ساعات": "watches", "watch": "watches",
    "عطر": "perfumes", "عطور": "perfumes", "perfume": "perfumes",
    "موبايل": "phones", "فون": "phones", "phone": "phones",
    "اكسسوارات": "accessories", "accessories": "accessories",
    "بيت": "home", "منزل": "home", "home": "home",
    "حلويات": "food", "اكل": "food", "food": "food",
}

# Egyptian mobile: optional country prefixes + the 10-digit national number
# (1[0125]xxxxxxxx). Lookarounds instead of \b so a prefix digit never
# blocks the match (verified: \b between "0" and "1" is never a boundary).
_PHONE_RE = re.compile(r"(?<!\d)(?:\+20|0020|20|0)?(1[0125]\d{8})(?!\d)")
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# Lookarounds on BOTH sides stop "250 years" from partially matching as 50.
_AGE_RE = re.compile(
    r"(?:\b(?:عمري|عمرى|age|i[' ]?am|i'm)\D{0,4})?(?<!\d)(\d{1,2})(?!\d)\s*(?:سنة|سنوات|سنين|years?|y/?o)\b",
    re.IGNORECASE,
)
# Arabic-Indic digits ٠-٩ normalization for age phrases like "عمري ٢٥ سنة".
_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")

MAX_INTERESTS = 25


def _norm_text(text: str) -> str:
    return text.translate(_AR_DIGITS)


# Arabic clitics: the conjunction/prefix letters users glue onto words
# ("وغالي", "بالمقاسات") and the feminine/plural suffixes ("متأخرة").
_AR_PREFIX_CLITICS = "وفب"


def _contains_word(text: str, phrase: str) -> bool:
    """Word-boundary-aware phrase match, Arabic-aware.

    Plain substring matching caused real false positives ("hi" inside
    "this", "ok" inside "broken"), so English phrases match on strict
    word boundaries. Arabic phrases additionally get: (1) orthographic
    folding (ة→ه, أ→ا, ...) and (2) tolerance for a one-letter clitic
    prefix and up to two suffix letters — Egyptian chat morphology.
    """
    import re as _re

    from app.utils.egypt_address import _norm_ar

    folded_text = _norm_ar(text.lower())
    folded_phrase = _norm_ar(phrase.lower())
    if not folded_phrase:
        return False

    is_arabic = any("\u0600" <= ch <= "\u06ff" for ch in folded_phrase)
    if is_arabic:
        pattern = _re.compile(
            r"(?<![\w])[" + _AR_PREFIX_CLITICS + r"]?"
            + _re.escape(folded_phrase) + r"[\w]{0,2}(?![\w])"
        )
    else:
        pattern = _re.compile(
            r"(?<![\w])" + _re.escape(folded_phrase) + r"(?![\w])"
        )
    return pattern.search(folded_text) is not None


def extract_governorate(text: str) -> str | None:
    """Scan free text for any Egyptian governorate (Arabic or English).

    ``detect_governorate_from_text`` only matches the exact "الاسكندرية"
    spelling; real customers write "اسكندرية" (no ال), "القاهره", or
    English. This scanner folds Arabic variants and tolerates the missing
    definite article.
    """
    from app.utils.egypt_address import GOVERNORATE_LOOKUP, _norm_ar

    folded = _norm_ar(text.lower())
    for alias, key in GOVERNORATE_LOOKUP.items():
        if not alias:
            continue
        if any("\u0600" <= ch <= "\u06ff" for ch in alias):
            alias_folded = _norm_ar(alias)
            if alias_folded in folded:
                return key
            # Tolerate the missing definite article "ال".
            if alias_folded.startswith("ال") and len(alias_folded) > 5:
                if alias_folded[2:] in folded:
                    return key
        else:
            if _contains_word(folded, alias):
                return key
    return None


def detect_sentiment(text: str) -> str:
    lowered = text.lower()
    pos = sum(1 for w in _POSITIVE_WORDS if _contains_word(lowered, w))
    neg = sum(1 for w in _NEGATIVE_WORDS if _contains_word(lowered, w))
    pos += sum(1 for e in _POSITIVE_EMOJI if e in text)
    neg += sum(1 for e in _NEGATIVE_EMOJI if e in text)
    if neg > pos:
        return "negative"
    if pos > neg:
        return "positive"
    return "neutral"


def detect_intent(text: str) -> str:
    lowered = " " + text.lower() + " "
    if any(_contains_word(lowered, k) for k in _ORDER_INTENT):
        return "ordering"
    if any(_contains_word(lowered, k) for k in _PRICE_INTENT):
        return "price_query"
    if any(_contains_word(lowered, k) for k in _COMPLAINT_INTENT):
        return "complaint"
    if any(_contains_word(lowered, k) for k in _GREETING_INTENT):
        return "greeting"
    if "?" in text or "؟" in text:
        return "question"
    return "chat"


def extract_phone(text: str) -> str | None:
    match = _PHONE_RE.search(_norm_text(text))
    if not match:
        return None
    return normalize_egyptian_phone("0" + match.group(1)) or ("0" + match.group(1))


def extract_email(text: str) -> str | None:
    match = _EMAIL_RE.search(text)
    return match.group(0).lower() if match else None


def extract_age(text: str) -> int | None:
    normalized = _norm_text(text)
    match = _AGE_RE.search(normalized)
    if not match:
        return None
    try:
        age = int(match.group(1))
    except ValueError:
        return None
    return age if 13 <= age <= 100 else None


def extract_interests(text: str) -> list[str]:
    lowered = text.lower()
    found = []
    for keyword, tag in _INTEREST_MAP.items():
        if keyword in lowered and tag not in found:
            found.append(tag)
    return found[:MAX_INTERESTS]


def enrich_text(text: str) -> dict:
    """Full enrichment payload for one message text (pure, no DB)."""
    return {
        "sentiment": detect_sentiment(text),
        "intent": detect_intent(text),
        "phone": extract_phone(text),
        "email": extract_email(text),
        "age": extract_age(text),
        "governorate": extract_governorate(text),
        "interests": extract_interests(text),
    }


def apply_enrichment(
    message: Message,
    customer: Customer | None,
    text: str,
    channel: str,
) -> dict:
    """Attach enrichment to a stored message and fold facts into the
    customer profile. Returns the enrichment dict (caller persists)."""
    payload = enrich_text(text)
    # when/where context of this message.
    payload["channel"] = channel
    payload["detected_at"] = datetime.utcnow().isoformat()

    message.enrichment = payload

    if customer is not None:
        if payload["phone"] and not customer.phone:
            customer.phone = payload["phone"]
        if payload["email"] and not customer.email:
            customer.email = payload["email"]
        # Detected age stays in the enrichment payload; the customer's
        # date_of_birth column is real PII (encrypted at rest) and is only
        # set from trusted inputs, not from a chat estimate.
        if payload["governorate"] and not customer.governorate:
            customer.governorate = payload["governorate"]
        if not customer.country:
            customer.country = "Egypt"  # Egyptian commerce context default
        if payload["interests"]:
            merged = list(customer.interests or [])
            for tag in payload["interests"]:
                if tag not in merged:
                    merged.append(tag)
            customer.interests = merged[:MAX_INTERESTS]

    return payload


__all__ = [
    "enrich_text",
    "apply_enrichment",
    "detect_sentiment",
    "detect_intent",
    "extract_governorate",
    "extract_phone",
    "extract_email",
    "extract_age",
    "extract_interests",
]
