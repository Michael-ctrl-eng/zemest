"""
Zemest Store demo agent — a TINY rule-based "model" (zero LLM calls).

Why: the landing-page "Talk to Agent" demo must survive millions of playful
visitors at (near-)zero cost. This module is pure-Python keyword scoring:
no network, no model weights, no GPU — each reply costs microseconds of CPU
and nothing else. It runs an order-flow state machine:

    product inquiry -> offer + photo -> confirm -> ask address ->
    shipping quote + ETA + total -> "your package will arrive after X days"

Conversation rules (per the store's owner):
- Short, warm, human replies — never a wall of questions.
- The visitor must feel SAFE: no payment online, cash on delivery, address
  used for delivery only. Say it once at the right moments.
- The visitor's location is detected from their timezone (sent by the
  browser) and prices are quoted in the local currency, e.g.
  "I see you're in Cairo 🇪🇬". Zero external geo-IP APIs, zero cost.
Understands English and light Arabic (categories, colors, sizes, all 27
Egyptian governorates + their areas, Arabic names included).
"""

from __future__ import annotations

import re
import threading
import time
from typing import Any

from app.utils.egypt_address import GOVERNORATES

# --------------------------------------------------------------------------
# Catalog — every product ships with a locally-hosted photo (public/demo-products)
# --------------------------------------------------------------------------

CATALOG: list[dict[str, Any]] = [
    {
        "id": "nike-white-air", "name": "Nike Air Max — White", "brand": "nike",
        "category": "shoes", "keywords": ["shoe", "shoes", "sneaker", "sneakers", "air", "max", "حذاء", "أحذية", "بوت", "سبورت"],
        "colors": ["white"], "sizes": [40, 41, 42, 43, 44, 45],
        "price": 1250, "image": "/demo-products/nike-white-air.jpg",
        "stock": 4, "emoji": "👟",
    },
    {
        "id": "nike-black-runner", "name": "Nike Runner — Black", "brand": "nike",
        "category": "shoes", "keywords": ["shoe", "shoes", "sneaker", "sneakers", "running", "runner", "حذاء", "أحذية", "سبورت"],
        "colors": ["black"], "sizes": [40, 41, 42, 43, 44],
        "price": 1100, "image": "/demo-products/nike-black-runner.jpg",
        "stock": 6, "emoji": "👟",
    },
    {
        "id": "adidas-red", "name": "Adidas Court — Red", "brand": "adidas",
        "category": "shoes", "keywords": ["shoe", "shoes", "sneaker", "sneakers", "adidas", "حذاء", "أحذية"],
        "colors": ["red"], "sizes": [40, 41, 42, 43, 44],
        "price": 950, "image": "/demo-products/adidas-red.jpg",
        "stock": 3, "emoji": "👟",
    },
    {
        "id": "tshirt-white", "name": "Classic Cotton Tee — White", "brand": "zemest",
        "category": "tshirt", "keywords": ["tshirt", "t-shirt", "shirt", "tee", "top", "تيشيرت", "تي شيرت", "قميص", "توب"],
        "colors": ["white"], "sizes": ["S", "M", "L", "XL", "XXL"],
        "price": 250, "image": "/demo-products/tshirt-white.jpg",
        "stock": 25, "emoji": "👕",
    },
    {
        "id": "hoodie-black", "name": "Heavyweight Hoodie — Black", "brand": "zemest",
        "category": "hoodie", "keywords": ["hoodie", "sweatshirt", "jacket", "هودي", "سويت", "جاكيت"],
        "colors": ["black"], "sizes": ["S", "M", "L", "XL", "XXL"],
        "price": 450, "image": "/demo-products/hoodie-black.jpg",
        "stock": 12, "emoji": "🧥",
    },
    {
        "id": "perfume-oud", "name": "Royal Oud Perfume — 100ml", "brand": "zemest",
        "category": "perfume", "keywords": ["perfume", "fragrance", "oud", "عطر", "عطور", "عود", "برفان"],
        "colors": [], "sizes": [100],
        "price": 350, "image": "/demo-products/perfume-oud.jpg",
        "stock": 9, "emoji": "🌸",
    },
    {
        "id": "perfume-floral", "name": "Blossom Perfume — 50ml", "brand": "zemest",
        "category": "perfume", "keywords": ["perfume", "fragrance", "floral", "blossom", "عطر", "عطور", "برفان"],
        "colors": [], "sizes": [50],
        "price": 275, "image": "/demo-products/perfume-floral.jpg",
        "stock": 14, "emoji": "🌺",
    },
    {
        "id": "shampoo-avocado", "name": "Avocado Repair Shampoo — 400ml", "brand": "zemest",
        "category": "shampoo", "keywords": ["shampoo", "hair", "شامبو", "شعر"],
        "colors": [], "sizes": [400],
        "price": 220, "image": "/demo-products/shampoo-argan.jpg",
        "stock": 30, "emoji": "🧴",
    },
    {
        "id": "face-cream", "name": "Hydra Face Cream — 50ml", "brand": "zemest",
        "category": "cream", "keywords": ["cream", "skincare", "moisturizer", "face", "كريم", "مرطب", "بشرة"],
        "colors": [], "sizes": [50],
        "price": 190, "image": "/demo-products/face-cream.jpg",
        "stock": 18, "emoji": "🧼",
    },
    {
        "id": "bag-leather", "name": "Genuine Leather Handbag — Brown", "brand": "zemest",
        "category": "bag", "keywords": ["bag", "handbag", "purse", "leather", "شنطة", "حقيبة", "شنتة"],
        "colors": ["brown"], "sizes": [],
        "price": 890, "image": "/demo-products/bag-leather.jpg",
        "stock": 5, "emoji": "👜",
    },
    {
        "id": "watch-black", "name": "Classic Analog Watch — Black", "brand": "zemest",
        "category": "watch", "keywords": ["watch", "ساعة", "ساعات"],
        "colors": ["black"], "sizes": [],
        "price": 650, "image": "/demo-products/watch-black.jpg",
        "stock": 7, "emoji": "⌚",
    },
    {
        "id": "earbuds", "name": "Wireless Earbuds Pro", "brand": "zemest",
        "category": "earbuds", "keywords": ["earbuds", "earphone", "headphone", "headset", "airpod", "سماعة", "سماعات", "ايربود"],
        "colors": ["black", "white"], "sizes": [],
        "price": 480, "image": "/demo-products/earbuds.jpg",
        "stock": 20, "emoji": "🎧",
    },
    {
        "id": "phone-case", "name": "Minimal Phone Case — Black", "brand": "zemest",
        "category": "case", "keywords": ["case", "cover", "جراب", "كفر"],
        "colors": ["black"], "sizes": [],
        "price": 120, "image": "/demo-products/phone-case.jpg",
        "stock": 40, "emoji": "📱",
    },
    {
        "id": "sunglasses", "name": "Matte Sunglasses — Black", "brand": "zemest",
        "category": "sunglasses", "keywords": ["sunglasses", "glasses", "shades", "نظارة", "نظارات", "شمسية"],
        "colors": ["black"], "sizes": [],
        "price": 340, "image": "/demo-products/sunglasses.jpg",
        "stock": 11, "emoji": "🕶️",
    },
    {
        "id": "dress-floral", "name": "Summer Floral Dress", "brand": "zemest",
        "category": "dress", "keywords": ["dress", "فستان", "ملابس"],
        "colors": ["white", "blue"], "sizes": ["S", "M", "L", "XL"],
        "price": 520, "image": "/demo-products/dress-floral.jpg",
        "stock": 8, "emoji": "👗",
    },
]

# --------------------------------------------------------------------------
# Location (timezone -> city) + currency — zero external APIs, zero cost.
# The browser sends its IANA timezone; we map it to a city and local currency.
# --------------------------------------------------------------------------

# rate = how many EGP one unit of the currency is worth (fixed demo rates)
CURRENCIES: dict[str, dict[str, Any]] = {
    "EGP": {"sym": "EGP", "rate": 1.0},
    "USD": {"sym": "$", "rate": 48.5},
    "EUR": {"sym": "€", "rate": 52.8},
    "GBP": {"sym": "£", "rate": 61.5},
    "SAR": {"sym": "SAR", "rate": 12.9},
    "AED": {"sym": "AED", "rate": 13.2},
    "KWD": {"sym": "KD", "rate": 158.0},
    "TRY": {"sym": "₺", "rate": 1.35},
    "INR": {"sym": "₹", "rate": 0.57},
    "AUD": {"sym": "A$", "rate": 32.0},
    "CAD": {"sym": "C$", "rate": 35.5},
    "BRL": {"sym": "R$", "rate": 8.9},
    "ZAR": {"sym": "R", "rate": 2.6},
    "RUB": {"sym": "₽", "rate": 0.62},
}

# tz -> (city_en, city_ar, flag, currency, is_egypt)
TZ_LOCATIONS: dict[str, tuple[str, str, str, str, bool]] = {
    "Africa/Cairo": ("Cairo", "القاهرة", "🇪🇬", "EGP", True),
    "Europe/London": ("London", "لندن", "🇬🇧", "GBP", False),
    "Europe/Dublin": ("Dublin", "دبلن", "🇮🇪", "EUR", False),
    "Europe/Paris": ("Paris", "باريس", "🇫🇷", "EUR", False),
    "Europe/Berlin": ("Berlin", "برلين", "🇩🇪", "EUR", False),
    "Europe/Madrid": ("Madrid", "مدريد", "🇪🇸", "EUR", False),
    "Europe/Rome": ("Rome", "روما", "🇮🇹", "EUR", False),
    "Europe/Athens": ("Athens", "أثينا", "🇬🇷", "EUR", False),
    "Europe/Istanbul": ("Istanbul", "إستنبول", "🇹🇷", "TRY", False),
    "Europe/Moscow": ("Moscow", "موسكو", "🇷🇺", "RUB", False),
    "America/New_York": ("New York", "نيويورك", "🇺🇸", "USD", False),
    "America/Chicago": ("Chicago", "شيكاغو", "🇺🇸", "USD", False),
    "America/Denver": ("Denver", "دنفر", "🇺🇸", "USD", False),
    "America/Los_Angeles": ("Los Angeles", "لوس أنجلوس", "🇺🇸", "USD", False),
    "America/Toronto": ("Toronto", "تورونتو", "🇨🇦", "CAD", False),
    "America/Vancouver": ("Vancouver", "فانكوفر", "🇨🇦", "CAD", False),
    "America/Sao_Paulo": ("São Paulo", "ساو باولو", "🇧🇷", "BRL", False),
    "America/Mexico_City": ("Mexico City", "مكسيكو سيتي", "🇲🇽", "USD", False),
    "Asia/Dubai": ("Dubai", "دبي", "🇦🇪", "AED", False),
    "Asia/Abu_Dhabi": ("Abu Dhabi", "أبوظبي", "🇦🇪", "AED", False),
    "Asia/Riyadh": ("Riyadh", "الرياض", "🇸🇦", "SAR", False),
    "Asia/Kuwait": ("Kuwait City", "الكويت", "🇰🇼", "KWD", False),
    "Asia/Qatar": ("Doha", "الدوحة", "🇶🇦", "SAR", False),
    "Asia/Bahrain": ("Manama", "المنامة", "🇧🇭", "SAR", False),
    "Asia/Amman": ("Amman", "عمّان", "🇯🇴", "KWD", False),
    "Asia/Baghdad": ("Baghdad", "بغداد", "🇮🇶", "USD", False),
    "Asia/Beirut": ("Beirut", "بيروت", "🇱🇧", "USD", False),
    "Asia/Kolkata": ("Mumbai", "مومباي", "🇮🇳", "INR", False),
    "Asia/Karachi": ("Karachi", "كراتشي", "🇵🇰", "USD", False),
    "Asia/Tokyo": ("Tokyo", "طوكيو", "🇯🇵", "USD", False),
    "Asia/Shanghai": ("Shanghai", "شنغهاي", "🇨🇳", "USD", False),
    "Asia/Kuala_Lumpur": ("Kuala Lumpur", "كوالالمبور", "🇲🇾", "USD", False),
    "Asia/Jakarta": ("Jakarta", "جاكرتا", "🇮🇩", "USD", False),
    "Australia/Sydney": ("Sydney", "سيدني", "🇦🇺", "AUD", False),
    "Africa/Casablanca": ("Casablanca", "الدار البيضاء", "🇲🇦", "EUR", False),
    "Africa/Algiers": ("Algiers", "الجزائر", "🇩🇿", "EUR", False),
    "Africa/Tunis": ("Tunis", "تونس", "🇹🇳", "EUR", False),
    "Africa/Khartoum": ("Khartoum", "الخرطوم", "🇸🇩", "SAR", False),
    "Africa/Lagos": ("Lagos", "لاغوس", "🇳🇬", "USD", False),
    "Africa/Nairobi": ("Nairobi", "نيروبي", "🇰🇪", "USD", False),
    "Africa/Johannesburg": ("Johannesburg", "جوهانسبرغ", "🇿🇦", "ZAR", False),
}

INTERNATIONAL_SHIPPING_EGP = 250.0
INTERNATIONAL_ETA = "5-7"


def resolve_location(tz: str | None) -> dict[str, Any]:
    """Map the visitor's timezone to {city, city_ar, flag, cur, is_egypt}."""
    if tz and tz in TZ_LOCATIONS:
        city, city_ar, flag, cur, is_eg = TZ_LOCATIONS[tz]
        return {"city": city, "city_ar": city_ar, "flag": flag, "cur": cur, "is_egypt": is_eg}
    return {"city": None, "city_ar": None, "flag": None, "cur": "EGP", "is_egypt": True}


def fmt_price(egp: float, cur: str, arabic: bool = False) -> str:
    """Convert an EGP amount into the visitor's currency and format it."""
    info = CURRENCIES.get(cur, CURRENCIES["EGP"])
    value = egp / info["rate"]
    amount = f"{value:,.0f}"
    if cur == "EGP":
        return f"{amount} جنيه" if arabic else f"{amount} EGP"
    sym = info["sym"]
    if sym in ("$", "€", "£", "₺", "₹", "A$", "C$", "R$", "₽"):
        return f"{sym}{amount}"
    return f"{amount} {sym}"


# --------------------------------------------------------------------------
# Tiny "model" — weighted keyword intent classifier + entity extraction.
# The weights below ARE the pretrained parameters (a few hundred ints).
# --------------------------------------------------------------------------

INTENTS: dict[str, dict[str, list[str]]] = {
    "greeting": {"strong": ["hello", "hi ", " hi", "hey", "salam", "salaam", "أهلا", "اهلا", "السلام", "مرحبا", "صباح", "مساء"], "weak": []},
    "thanks": {"strong": ["thanks", "thank you", "thx", "شكرا", "متشكر"], "weak": ["great", "awesome", "جميل", "حلو"]},
    "bye": {"strong": ["bye", "goodbye", "see you", "مع السلامة"], "weak": []},
    "affirm": {"strong": ["yes", "yeah", "yep", "sure", "ok", "okay", "order it", "i want it", "want it", "want one", "i'll take it", "take it", "buy", "نعم", "ايوه", "أيوة", "تمام", "عايزه", "عايز", "هخد", "أكيد"], "weak": ["confirm", "correct"]},
    "deny": {"strong": ["no", "nope", "لا ", "لأ"], "weak": ["not now", "later"]},
    "order": {"strong": ["order", "buy", "purchase", "checkout", "اطلب", "شراء", "اشتري"], "weak": ["take", "get it", "reserve", "احجز"]},
    "shipping": {"strong": ["shipping", "delivery", "ship", "deliver", "arrive", "how long", "when will", "توصيل", "شحن", "هتيجي", "توصل"], "weak": ["how many days", "كم يوم"]},
    "address": {"strong": ["my address", "address is", "i live in", "i'm in", "im in", "عنواني", "ساكن في"], "weak": []},
    "price": {"strong": ["how much", "price", "cost", "بكام", "كام", "السعر", "سعر"], "weak": ["expensive", "cheap", "غالي", "رخيص"]},
    "product": {"strong": ["do you have", "you have", "have", "any", "looking for", "need", "want", "is there", "عندك", "موجود", "في"], "weak": []},
    # --- small talk / trust (keeps the conversation feeling human & safe) ---
    "who": {"strong": ["who are you", "are you a bot", "are you real", "are you human", "robot", "هل انت", "مين انت", "بوت"], "weak": ["what are you"]},
    "howareyou": {"strong": ["how are you", "how r u", "إزيك", "عامل ايه", "كيف حالك"], "weak": []},
    "whereyou": {"strong": ["where are you", "your location", "where is the shop", "فينكم", "انت فين"], "weak": ["located"]},
    "authentic": {"strong": ["original", "authentic", "real one", "fake", "اصلي", "أصلي", "تقليد"], "weak": ["genuine"]},
    "payment": {"strong": ["payment", "pay online", "card", "visa", "cash on delivery", "cod", "الدفع", "فيزا", "كاش"], "weak": ["pay"]},
    "refund": {"strong": ["refund", "return", "exchange", "استرجاع", "استبدال", "ارجاع"], "weak": []},
    "safety": {"strong": ["scam", "safe", "privacy", "secure", "trust", "نصب", "امان", "آمن", "خصوصية"], "weak": []},
}

CATEGORY_HINTS = {
    p["category"]: set(p["keywords"]) for p in CATALOG
}

COLOR_WORDS = {
    "white": "white", "black": "black", "red": "red", "blue": "blue",
    "green": "green", "pink": "pink", "brown": "brown", "أبيض": "white",
    "ابيض": "white", "أسود": "black", "اسود": "black", "أحمر": "red",
    "احمر": "red", "أزرق": "blue", "ازرق": "blue", "بني": "brown",
}

SIZE_PATTERNS = [
    (re.compile(r"\b(?:size\s*)?(4[0-5]|3[89])\s*(?:cm|eu)?\b", re.I), "shoe"),
    (re.compile(r"\b(xxs|xs|s|m|l|xl|xxl)\b", re.I), "letter"),
    (re.compile(r"\b(\d{2,3})\s*ml\b", re.I), "ml"),
]

GREETING_TRIGGERS = ["أهلا", "اهلا", "السلام", "مرحبا", "صباح", "مساء"]
# word-boundary regex so "hi" inside "this"/"white" can't trigger a greeting
_GREETING_RE = re.compile(r"\b(hello|hi|hey|heya|yo|salam|salaam|sup|hola)\b", re.I)

# governorate lookup: english key, arabic name, and every area name (lowercased)
_GOV_LOOKUP: list[tuple[str, str, str]] = []
for _key, _info in GOVERNORATES.items():
    _GOV_LOOKUP.append((_key, _info["name_ar"], _key))
    _GOV_LOOKUP.append((_key, _info["name_ar"], _info["name_ar"]))
    for _area in _info.get("areas", []):
        _GOV_LOOKUP.append((_key, _info["name_ar"], _area))
        # strip leading ال from area names for prefix matching
        if _area.startswith("ال"):
            _GOV_LOOKUP.append((_key, _info["name_ar"], _area[2:]))
_GOV_LOOKUP.sort(key=lambda t: -len(t[2]))  # longest-first so الدقي beats دق... etc
# common english city spellings
_GOV_LOOKUP += [
    ("cairo", "القاهرة", "cairo"), ("cairo", "القاهرة", "كايرو"),
    ("giza", "الجيزة", "giza"), ("giza", "الجيزة", "جيزة"),
    ("alexandria", "الإسكندرية", "alex"), ("alexandria", "الإسكندرية", "alexandria"),
    ("alexandria", "الإسكندرية", "اسكندرية"), ("alexandria", "الإسكندرية", "إسكندرية"),
]

ZONE_ETA = {1: "2-3", 2: "3-4", 3: "4-5"}


def classify_intent(text: str) -> tuple[str, float]:
    """Weighted keyword scoring — returns (intent, score)."""
    t = f" {text.lower().strip()} "
    best, best_score = "fallback", 0.0
    for intent, weights in INTENTS.items():
        score = sum(3.0 for k in weights["strong"] if k in t) + sum(1.0 for k in weights["weak"] if k in t)
        if score > best_score:
            best, best_score = intent, score
    return best, best_score


def extract_color(text: str) -> str | None:
    t = text.lower()
    for word, color in COLOR_WORDS.items():
        if word in t:
            return color
    return None


def extract_size(text: str) -> tuple[str | int | None, str | None]:
    for pattern, kind in SIZE_PATTERNS:
        m = pattern.search(text)
        if m:
            raw = m.group(1)
            if kind == "shoe":
                return int(raw), "shoe"
            if kind == "letter":
                return raw.upper(), "letter"
            return int(raw), "ml"
    return None, None


def extract_category(text: str) -> str | None:
    t = text.lower()
    for cat, kws in CATEGORY_HINTS.items():
        for kw in kws:
            if kw in t:
                return cat
    return None


def match_product(text: str, category: str | None, color: str | None,
                  size: str | int | None, size_kind: str | None, brand: str | None) -> dict | None:
    """Score every product: category is the big signal, then color/brand/size."""
    t = text.lower()
    best, best_score = None, 0.0
    for p in CATALOG:
        score = 0.0
        if category and p["category"] == category:
            score += 10.0
        if brand and p["brand"] == brand:
            score += 4.0
        if color and color in p["colors"]:
            score += 3.0
        if size and size_kind == "shoe" and isinstance(size, int) and size in p["sizes"]:
            score += 2.5
        if size and size_kind == "letter" and isinstance(size, str) and size in p["sizes"]:
            score += 2.5
        if size and size_kind == "ml" and isinstance(size, int) and size in p["sizes"]:
            score += 2.5
        # raw keyword hits (helps "air max" -> the air max shoe)
        for kw in p["keywords"]:
            if kw in t:
                score += 0.6
        if p["name"].lower().split("—")[0].strip() in t:
            score += 2.0
        if score > best_score:
            best, best_score = p, score
    return best if best_score >= 2.0 else None


def detect_governorate(text: str) -> tuple[str, str] | None:
    """(gov_key, name_ar) from an address string — longest-name-first matching."""
    t = text.lower()
    for key, name_ar, needle in _GOV_LOOKUP:
        if needle.lower() in t:
            return key, name_ar
    return None


def looks_like_address(text: str) -> bool:
    """Heuristic: has digits + comma / street words / governorate mention."""
    if detect_governorate(text):
        return True
    t = text.lower()
    if re.search(r"\d+", text) and ("," in text or "street" in t or " st" in t or "شارع" in t):
        return True
    return False


def is_arabic(text: str) -> bool:
    return bool(re.search(r"[\u0600-\u06FF]", text))


_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def normalize_digits(text: str) -> str:
    """Convert Arabic-Indic digits (٤٢) to Western digits (42)."""
    return text.translate(_ARABIC_DIGITS)


# --------------------------------------------------------------------------
# Session store (in-memory, TTL-evicted — microsecond access, no Redis cost)
# --------------------------------------------------------------------------

SESSION_TTL = 30 * 60  # 30 minutes
MAX_SESSIONS = 20_000
_sessions: dict[str, dict[str, Any]] = {}
_lock = threading.Lock()


def _prune(now: float) -> None:
    if len(_sessions) < MAX_SESSIONS:
        return
    dead = [sid for sid, s in _sessions.items() if now - s["ts"] > SESSION_TTL]
    for sid in dead:
        _sessions.pop(sid, None)
    if len(_sessions) >= MAX_SESSIONS:  # still full? drop oldest quarter
        ordered = sorted(_sessions.items(), key=lambda kv: kv[1]["ts"])
        for sid, _ in ordered[: len(ordered) // 4]:
            _sessions.pop(sid, None)


def get_session(session_id: str, tz: str | None = None) -> dict[str, Any]:
    now = time.time()
    with _lock:
        _prune(now)
        s = _sessions.get(session_id)
        if not s:
            loc = resolve_location(tz)
            s = {"stage": "start", "product": None, "address": None, "ts": now, **loc}
            _sessions[session_id] = s
        elif tz:
            # keep currency/location fresh if the visitor's tz is known
            loc = resolve_location(tz)
            for k, v in loc.items():
                if v:
                    s[k] = v
        s["ts"] = now
        return s


def reset_session(session_id: str) -> None:
    with _lock:
        _sessions.pop(session_id, None)


# --------------------------------------------------------------------------
# Response generation — bilingual templates (EN + AR)
# --------------------------------------------------------------------------

def _t(arabic: bool, en: str, ar: str) -> str:
    return ar if arabic else en


def _location_line(session: dict[str, Any], arabic: bool) -> str:
    """Location line is no longer announced unprompted (users found it creepy).
    Kept for reference: only used when the visitor asks where we ship / who we are."""
    return ""


def _currency_of(session: dict[str, Any]) -> str:
    return session.get("cur", "EGP")


def build_reply(message: str, session_id: str, tz: str | None = None) -> dict[str, Any]:
    """The whole brain: classify -> extract -> state machine -> reply dict."""
    msg = message.strip()
    arabic = is_arabic(msg)
    msg = normalize_digits(msg)
    low = msg.lower()
    session = get_session(session_id, tz)
    stage = session["stage"]
    cur = _currency_of(session)

    def price(egp: float) -> str:
        return fmt_price(egp, cur, arabic)

    intent, score = classify_intent(msg)
    color = extract_color(msg)
    size, size_kind = extract_size(msg)
    category = extract_category(msg)
    brand = None
    for b in ["nike", "adidas", "puma", "zara"]:
        if b in low:
            brand = b

    # --- 0. "what about X" follow-up on a shipping question ---
    if session.get("last_intent") == "shipping" and not product_intent_pending(intent, category):
        gov = detect_governorate(msg)
        # only a REAL address (digits/street markers) should skip this branch
        has_address_markers = bool(re.search(r"\d", msg)) or "," in msg or "شارع" in msg
        if gov and not has_address_markers:
            session["last_intent"] = intent
            return _shipping_quote(gov, session, arabic, price)
    session["last_intent"] = intent

    # --- 1. new product inquiry (highest priority — works at ANY stage) ---
    product_hit = match_product(msg, category, color, size, size_kind, brand)
    product_intentish = intent in ("product", "price") or category or score == 0
    if product_hit and product_intentish:
        session["stage"] = "offered"
        session["product"] = product_hit
        size_txt = ""
        if size and size_kind == "shoe" and size in product_hit["sizes"]:
            size_txt = _t(arabic, f" in your size ({size})", f" بمقاسك ({size})")
        elif size and size_kind == "letter" and size in product_hit["sizes"]:
            size_txt = _t(arabic, f" — size {size}", f" — مقاس {size}")
        elif size:
            closest = [s for s in product_hit["sizes"] if isinstance(s, int)][:3] if size_kind == "shoe" else []
            if size_kind == "shoe" and closest:
                size_txt = _t(arabic, f" — we carry sizes {closest[0]}-{closest[-1]}", f" — المقاسات المتاحة {closest[0]}-{closest[-1]}")
        return {
            "reply": _t(
                arabic,
                f"Yes, we have it in stock.\n{product_hit['name']}{size_txt} — {price(product_hit['price'])}\nHere's a photo:",
                f"أيوه موجود.\n{product_hit['name']}{size_txt} — {price(product_hit['price'])}\nدي الصورة:",
            ),
            "image": product_hit["image"],
            "quick_replies": [
                _t(arabic, "I'll take it", "هخده"),
                _t(arabic, "Show me something else", "وريني حاجة تانية"),
            ],
        }

    # --- 2. confirm order -> ask address (short + safe-feeling) ---
    if intent in ("affirm", "order") and stage == "offered" and session["product"]:
        session["stage"] = "awaiting_address"
        return {
            "reply": _t(
                arabic,
                "Great choice.\nWhat's the delivery address? (street, area, city)\nNo payment now — you pay when it arrives.",
                "اختيار ممتاز.\nعنوان التوصيل إيه؟ (الشارع، المنطقة، المدينة)\nمش هتدفع حاجة دلوقتي — الدفع عند الاستلام.",
            ),
            "quick_replies": [_t(arabic, "Cancel", "إلغاء")],
        }

    # --- 3. address given -> total + ETA + confirmation ---
    if stage == "awaiting_address" and (looks_like_address(msg) or intent == "address"):
        gov = detect_governorate(msg)
        p = session["product"]
        if not p:
            session["stage"] = "start"
            return _fallback(session, arabic, price)
        address = msg
        if gov and session.get("is_egypt", True):
            key, _ = gov
            info = GOVERNORATES[key]
            shipping = 0.0 if p["price"] >= info["free_threshold"] else float(info["shipping_cost"])
            eta = ZONE_ETA[info["zone"]]
        elif session.get("is_egypt", True):
            shipping = 60.0
            eta = "3-4"
        else:
            shipping = INTERNATIONAL_SHIPPING_EGP
            eta = INTERNATIONAL_ETA
        total = p["price"] + shipping
        session["stage"] = "confirmed"
        ship_txt = (
            _t(arabic, "free", "مجاني")
            if shipping == 0 else price(shipping)
        )
        return {
            "reply": _t(
                arabic,
                f"All set.\n\n{p['name']} — {price(p['price'])}\nDelivery — {ship_txt}\nTotal — {price(total)}\n\nYour package arrives in {eta} days at:\n{address}\n\nPay on delivery — nothing to pay now.",
                f"تمام.\n\n{p['name']} — {price(p['price'])}\nالتوصيل — {ship_txt}\nالإجمالي — {price(total)}\n\nطلبك يوصلك خلال {eta} أيام على:\n{address}\n\nالدفع عند الاستلام — مش هتدفع حاجة دلوقتي.",
            ),
            "order_done": True,
            "quick_replies": [
                _t(arabic, "Thank you", "شكراً"),
                _t(arabic, "Ask something else", "أسأل عن حاجة تانية"),
            ],
        }

    # --- 4. shipping questions ---
    if intent == "shipping":
        gov = detect_governorate(msg)
        if gov and session.get("is_egypt", True):
            return _shipping_quote(gov, session, arabic, price)
        if not session.get("is_egypt", True):
            return {
                "reply": _t(
                    arabic,
                    f"We ship worldwide. Delivery to you is {price(INTERNATIONAL_SHIPPING_EGP)} — {INTERNATIONAL_ETA} days, and it's free on bigger orders.",
                    f"بنشحن لكل العالم. التوصيل ليك بـ{price(INTERNATIONAL_SHIPPING_EGP)} — {INTERNATIONAL_ETA} أيام، ومجاني للطلبات الكبيرة.",
                ),
                "quick_replies": [_t(arabic, "What do you sell?", "بتبيعوا إيه؟")],
            }
        return {
            "reply": _t(
                arabic,
                f"Delivery is {price(35)} in Greater Cairo, {price(45)}-{price(60)} elsewhere in Egypt — free on bigger orders.\n2-3 days for Cairo, 3-5 days for other cities.",
                f"التوصيل {price(35)} داخل القاهرة الكبرى، {price(45)}-{price(60)} لبقية المحافظات — ومجاني للطلبات الكبيرة.\n2-3 أيام للقاهرة، 3-5 أيام لباقي المحافظات.",
            ),
            "quick_replies": [_t(arabic, "What do you sell?", "بتبيعوا إيه؟")],
        }

    # --- 5. greetings (short + warm) ---
    if intent == "greeting" or _GREETING_RE.search(msg) or any(g in low for g in GREETING_TRIGGERS):
        return {
            "reply": _t(
                arabic,
                f"Hi! What can I help you find today?",
                f"أهلاً! أقدر أساعدك بإيه النهارده؟",
            ),
            "quick_replies": [
                _t(arabic, "White Nike shoes, size 42", "حذاء نايك أبيض مقاس 42"),
                _t(arabic, "Do you have shampoo?", "عندكم شامبو؟"),
                _t(arabic, "How much is shipping?", "الشحن بكام؟"),
            ],
        }

    # --- 6. small talk / trust (the "real friendly conversation") ---
    if intent == "who":
        return {
            "reply": _t(
                arabic,
                "I'm the Zemest Store agent. I run this shop's chat 24/7 — everything I promise is the shop's promise. Ask me about anything we sell.",
                "أنا وكيل متجر Zemest. بشتغل على شات المحل 24 ساعة — وكل اللي أقوله ده كلام المحل. اسألني عن أي حاجة بنبيعها.",
            ),
            "quick_replies": [_t(arabic, "What do you sell?", "بتبيعوا إيه؟")],
        }
    if intent == "howareyou":
        return {
            "reply": _t(arabic, "Doing well, thanks for asking. How can I help?", "تمام، تسأل عني؟ أقدر أساعدك بإيه؟"),
            "quick_replies": [_t(arabic, "Show me shoes", "وريني الأحذية")],
        }
    if intent == "whereyou":
        city = session.get("city") if not arabic else session.get("city_ar")
        if city:
            return {
                "reply": _t(
                    arabic,
                    f"You're writing from {city}, and I'm at the shop. What are you looking for?",
                    f"انت بتكلمني من {city} — وأنا في المحل. تدور على إيه؟",
                ),
                "quick_replies": [_t(arabic, "What do you sell?", "بتبيعوا إيه؟")],
            }
        return {
            "reply": _t(arabic, "Zemest Store — an Egyptian shop, and we ship everywhere. What are you looking for?", "متجر Zemest — محل مصري بنشحن لكل مكان. تدور على إيه؟"),
            "quick_replies": [_t(arabic, "What do you sell?", "بتبيعوا إيه؟")],
        }
    if intent == "authentic":
        return {
            "reply": _t(
                arabic,
                "Yes — everything we sell is authentic, sourced directly from the brand.",
                "أيوه — كل حاجة عندنا أصلية، من الوكيل مباشرة.",
            ),
            "quick_replies": [_t(arabic, "Show me shoes", "وريني الأحذية")],
        }
    if intent == "payment":
        return {
            "reply": _t(
                arabic,
                "No payment online. You pay cash when your package arrives — safe and simple.",
                "مفيش دفع أونلاين. بتدفع كاش لما الطلب يوصلك.",
            ),
            "quick_replies": [_t(arabic, "What do you sell?", "بتبيعوا إيه؟")],
        }
    if intent == "refund":
        return {
            "reply": _t(
                arabic,
                "Of course — you can return anything within 14 days, no questions asked.",
                "أكيد — تقدر ترجع أي حاجة خلال 14 يوم، من غير أي أسئلة.",
            ),
            "quick_replies": [_t(arabic, "What do you sell?", "بتبيعوا إيه؟")],
        }
    if intent == "safety":
        return {
            "reply": _t(
                arabic,
                "Completely safe. We only use your address for the delivery — nothing else, and we never share it.",
                "أمان تماماً. بنستخدم عنوانك للتوصيل بس — ومش بنشاركه مع أي حد.",
            ),
            "quick_replies": [_t(arabic, "What do you sell?", "بتبيعوا إيه؟")],
        }

    # --- 7. price question without a product match ---
    if intent == "price":
        # "how much is it?" right after an offer — recall the offered product
        if stage == "offered" and session.get("product"):
            p = session["product"]
            return {
                "reply": _t(
                    arabic,
                    f"{p['name']} is {price(p['price'])}. Want it?",
                    f"{p['name']} بـ{price(p['price'])}. تحبه؟",
                ),
                "quick_replies": [_t(arabic, "I'll take it", "هخده")],
            }
        return {
            "reply": _t(
                arabic,
                f"Which item? Shoes from {price(950)}, tees {price(250)}, hoodies {price(450)}, perfume from {price(275)}, shampoo {price(220)}, bags {price(890)}.",
                f"بتسأل على إيه؟ أحذية من {price(950)}، تيشيرتات {price(250)}، هوديز {price(450)}، عطور من {price(275)}، شامبو {price(220)}، شنط {price(890)}.",
            ),
            "quick_replies": [_t(arabic, "Show me shoes", "وريني الأحذية")],
        }

    # --- 8. thanks / bye ---
    if intent == "thanks":
        session["stage"] = "start"
        return {
            "reply": _t(arabic, "Anytime — happy to help.", "في أي وقت، تحت أمرك."),
            "quick_replies": [_t(arabic, "Ask something else", "أسأل عن حاجة تانية")],
        }
    if intent == "bye":
        session["stage"] = "start"
        return {
            "reply": _t(arabic, "See you.", "تشرفنا."),
            "quick_replies": [],
        }

    # --- 9. bare affirm/deny outside flow ---
    if intent == "affirm":
        return {
            "reply": _t(
                arabic,
                "Sure — what would you like?",
                "تمام — تحب إيه؟",
            ),
            "quick_replies": [
                _t(arabic, "White Nike shoes, size 42", "حذاء نايك أبيض مقاس 42"),
                _t(arabic, "Do you have perfume?", "عندكم عطور؟"),
            ],
        }
    if intent == "deny":
        session["stage"] = "start"
        return {
            "reply": _t(arabic, "No problem — anything else I can help with?", "مش مشكلة — أقدر أساعدك بحاجة تانية؟"),
            "quick_replies": [_t(arabic, "What do you sell?", "بتبيعوا إيه؟")],
        }

    # --- 10. fallback (short, friendly, never a wall of text) ---
    return _fallback(session, arabic, price)


def product_intent_pending(intent: str, category: str | None) -> bool:
    """True when the message itself is about a product (don't hijack it as a follow-up)."""
    return intent in ("product", "price") or bool(category)


def _shipping_quote(gov: tuple[str, str], session: dict[str, Any], arabic: bool, price) -> dict[str, Any]:
    key, name = gov
    info = GOVERNORATES[key]
    return {
        "reply": _t(
            arabic,
            f"Shipping to {name} is {price(float(info['shipping_cost']))} — free over {price(float(info['free_threshold']))}. Arrives in {ZONE_ETA[info['zone']]} days.",
            f"الشحن لـ{name} بـ{price(float(info['shipping_cost']))} — ومجاني فوق {price(float(info['free_threshold']))}. بيوصل في {ZONE_ETA[info['zone']]} أيام.",
        ),
        "quick_replies": [_t(arabic, "What do you sell?", "بتبيعوا إيه؟")],
    }


def _fallback(session: dict[str, Any], arabic: bool, price) -> dict[str, Any]:
    return {
        "reply": _t(
            arabic,
            "I can help with anything in the shop — shoes, perfume, shampoo, bags. What are you looking for?",
            "أقدر أساعدك بأي حاجة في المحل — أحذية، عطور، شامبو، شنط. تدور على إيه؟",
        ),
        "quick_replies": [
            _t(arabic, "White Nike shoes, size 42", "حذاء نايك أبيض مقاس 42"),
            _t(arabic, "Do you have shampoo?", "عندكم شامبو؟"),
            _t(arabic, "How much is shipping?", "الشحن بكام؟"),
        ],
    }


def welcome(session_id: str, tz: str | None = None) -> dict[str, Any]:
    """Opening message shown when the chat window opens (location-aware)."""
    reset_session(session_id)
    session = get_session(session_id, tz)
    arabic = False
    return {
        "reply": "Hi, welcome to Zemest Store.\nWhat are you looking for today?",
        "quick_replies": ["White Nike shoes, size 42", "Do you have shampoo?", "How much is shipping?"],
        "is_arabic": False,
    }
