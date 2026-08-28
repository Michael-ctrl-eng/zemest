"""Egyptian address hierarchy — 27 Governorates with cities/areas.

Includes:
- Full list of all 27 Egyptian governorates (Arabic + English names)
- Per-governorate zones, shipping costs, free-delivery thresholds
- Cities and areas for major governorates
- Phone number validation (010/011/012/015 prefixes)
- Governorate detection from free text
- Shipping cost calculator
"""

import re

# Egyptian governorates with their zones and typical shipping costs (in EGP)
GOVERNORATES = {
    "cairo": {
        "name_ar": "القاهرة",
        "zone": 1,
        "shipping_cost": 35,
        "free_threshold": 300,
        "areas": [
            "المعادي", "مصر الجديدة", "مدينة نصر", "شبرا", "العبور", "حلوان",
            "الزمالك", "وسط البلد", "المنيل", "دار السلام", "البساتين",
            "المقطم", "التجمع الخامس", "التجمع الثالث", "الشروق", "البدرشين",
            "نادي الشمس", "العاصمة الإدارية", "عين شمس", "الزيتون",
        ],
    },
    "giza": {
        "name_ar": "الجيزة",
        "zone": 1,
        "shipping_cost": 35,
        "free_threshold": 300,
        "areas": [
            "المهندسين", "الدقي", "الهرم", "فيصل", "أكتوبر", "الشيخ زايد",
            "العجوزة", "المنيل", "الزمالك", "الوراق", "الوراق العرب",
            "البدرشين", "أوسيم", "كرداسة", "الصف", "أطفيح",
        ],
    },
    "alexandria": {
        "name_ar": "الإسكندرية",
        "zone": 2,
        "shipping_cost": 50,
        "free_threshold": 500,
        "areas": [
            "سيدي جابر", "سموحة", "المنشية", "المنطقة الأولى", "الجمرك",
            "العجمي", "الرمل", "اللبان", "جليم", "باكوس", "سيدي بشر",
            "كفر عبده", "المكس", "العصافرة", "المندرة", "بيطاش",
        ],
    },
    "dakahlia": {
        "name_ar": "الدقهلية",
        "zone": 2,
        "shipping_cost": 50,
        "free_threshold": 500,
        "areas": ["المنصورة", "طلخا", "ميت غمر", "شربين", "بلبيس", "منية النصر"],
    },
    "qalyubia": {
        "name_ar": "القليوبية",
        "zone": 2,
        "shipping_cost": 45,
        "free_threshold": 500,
        "areas": ["بنها", "قليوب", "شبرا الخيمة", "كفر شكر", "القناطر الخيرية"],
    },
    "sharqia": {
        "name_ar": "الشرقية",
        "zone": 2,
        "shipping_cost": 50,
        "free_threshold": 500,
        "areas": ["الزقازيق", "العاشر من رمضان", "بلبيس", "أبو حمص", "فاكس"],
    },
    "gharbia": {
        "name_ar": "الغربية",
        "zone": 2,
        "shipping_cost": 50,
        "free_threshold": 500,
        "areas": ["طنطا", "المحلة الكبرى", "كفر الشيخ", "زفتى", "سمنود"],
    },
    "monufia": {
        "name_ar": "المنوفية",
        "zone": 2,
        "shipping_cost": 50,
        "free_threshold": 500,
        "areas": ["شبين الكوم", "منوف", "تلا", "الباجور", "قويسنا"],
    },
    "beheira": {
        "name_ar": "البحيرة",
        "zone": 3,
        "shipping_cost": 60,
        "free_threshold": 600,
        "areas": ["دمنهور", "كفر الدوار", "رشيد", "أبو المطامير", "إدكو"],
    },
    "kafr-el-sheikh": {
        "name_ar": "كفر الشيخ",
        "zone": 3,
        "shipping_cost": 60,
        "free_threshold": 600,
        "areas": ["كفر الشيخ", "بلطيم", "دسوق", "فوه", "سيدي سالم"],
    },
    "damietta": {
        "name_ar": "دمياط",
        "zone": 3,
        "shipping_cost": 60,
        "free_threshold": 600,
        "areas": ["دمياط", "دمياط الجديدة", "رأس البر", "فارسكور", "كفر سعد"],
    },
    "port-said": {
        "name_ar": "بورسعيد",
        "zone": 3,
        "shipping_cost": 60,
        "free_threshold": 600,
        "areas": ["بور فؤاد", "الشرق", "الغرب", "المناخ", "العرب"],
    },
    "ismailia": {
        "name_ar": "الإسماعيلية",
        "zone": 3,
        "shipping_cost": 55,
        "free_threshold": 600,
        "areas": ["الإسماعيلية", "فايد", "التل الكبير", "القنطرة شرق", "القنطرة غرب"],
    },
    "suez": {
        "name_ar": "السويس",
        "zone": 3,
        "shipping_cost": 55,
        "free_threshold": 600,
        "areas": ["السويس", "العين السخنة", "عاتاقة", "فيصل", "الأربعين"],
    },
    "beni-suef": {
        "name_ar": "بني سويف",
        "zone": 3,
        "shipping_cost": 65,
        "free_threshold": 700,
        "areas": ["بني سويف", "ببا", "الواسطي", "ناصر", "الفسطاط"],
    },
    "fayoum": {
        "name_ar": "الفيوم",
        "zone": 3,
        "shipping_cost": 65,
        "free_threshold": 700,
        "areas": ["الفيوم", "تامية", "سنورس", "إطسا", "أبشواي"],
    },
    "minya": {
        "name_ar": "المنيا",
        "zone": 4,
        "shipping_cost": 75,
        "free_threshold": 800,
        "areas": ["المنيا", "ملوي", "بني مزار", "سمالوط", "مطاي"],
    },
    "assiut": {
        "name_ar": "أسيوط",
        "zone": 4,
        "shipping_cost": 75,
        "free_threshold": 800,
        "areas": ["أسيوط", "دير مواس", "منفلوط", "أبو تيج", "الفتح"],
    },
    "sohag": {
        "name_ar": "سوهاج",
        "zone": 4,
        "shipping_cost": 80,
        "free_threshold": 800,
        "areas": ["سوهاج", "جرجا", "أخميم", "طهطا", "بلينا"],
    },
    "qena": {
        "name_ar": "قنا",
        "zone": 4,
        "shipping_cost": 80,
        "free_threshold": 800,
        "areas": ["قنا", "نجع حمادي", "قوص", "ناصر", "أبو تشت"],
    },
    "luxor": {
        "name_ar": "الأقصر",
        "zone": 4,
        "shipping_cost": 85,
        "free_threshold": 800,
        "areas": ["الأقصر", "الكرنك", "الأرمنت", "إسنا", "الزينية"],
    },
    "aswan": {
        "name_ar": "أسوان",
        "zone": 4,
        "shipping_cost": 85,
        "free_threshold": 800,
        "areas": ["أسوان", "كوم أمبو", "نصر النوبة", "إدفو", "دراو"],
    },
    "red-sea": {
        "name_ar": "البحر الأحمر",
        "zone": 4,
        "shipping_cost": 90,
        "free_threshold": 900,
        "areas": ["الغردقة", "سفاجا", "رأس غارب", "مرسى علم", "القصير"],
    },
    "new-valley": {
        "name_ar": "الوادي الجديد",
        "zone": 5,
        "shipping_cost": 100,
        "free_threshold": 1000,
        "areas": ["الخارجة", "الداخلة", "الفرافرة", "بلد النوبة", "باريس"],
    },
    "matrouh": {
        "name_ar": "مطروح",
        "zone": 5,
        "shipping_cost": 100,
        "free_threshold": 1000,
        "areas": ["مرسى مطروح", "السلوم", "سيوة", "الحمام", "العلمين"],
    },
    "north-sinai": {
        "name_ar": "شمال سيناء",
        "zone": 5,
        "shipping_cost": 100,
        "free_threshold": 1000,
        "areas": ["العريش", "الشيخ زويد", "رفح", "بير العبد", "الحسنة"],
    },
    "south-sinai": {
        "name_ar": "جنوب سيناء",
        "zone": 4,
        "shipping_cost": 90,
        "free_threshold": 900,
        "areas": ["الطور", "شرم الشيخ", "دهب", "نويبع", "سان كاترين"],
    },
}

# Egyptian phone number validation
# 010 Vodafone, 011 Etisalat, 012 Orange, 015 WE — all 8 digits after prefix
# Accepts: 01012345678 / +201012345678 / 201012345678 / 00201012345678
EGYPTIAN_PHONE_REGEX = r"^(?:\+20|0020|20|0)?(1[0125]\d{8})$"


def validate_egyptian_phone(phone: str) -> bool:
    """Validate Egyptian phone number format.

    Accepts:
    - 01012345678 (local, 11 digits)
    - 201012345678 (international without +)
    - +201012345678
    - 00201012345678

    Valid prefixes: 010 (Vodafone), 011 (Etisalat), 012 (Orange), 015 (WE).
    """
    if not phone:
        return False
    cleaned = re.sub(r"[\s\-\(\)]", "", phone)
    return bool(re.match(EGYPTIAN_PHONE_REGEX, cleaned))


def normalize_egyptian_phone(phone: str) -> str | None:
    """Normalize any valid Egyptian phone format to 01XXXXXXXXX (11 digits).

    Returns None if phone is invalid.
    """
    if not phone:
        return None
    cleaned = re.sub(r"[\s\-\(\)]", "", phone)
    match = re.match(EGYPTIAN_PHONE_REGEX, cleaned)
    if not match:
        return None
    return f"0{match.group(1)}"


def detect_governorate_from_text(text: str) -> str | None:
    """Detect Egyptian governorate from free text (Arabic or English)."""
    if not text:
        return None
    normalized = text.lower().strip()
    for key, info in GOVERNORATES.items():
        if info["name_ar"] in text or key in normalized:
            return key
    return None


def get_governorates() -> list[dict]:
    """Return list of all governorates (for API endpoints)."""
    return [
        {
            "key": key,
            "name_ar": info["name_ar"],
            "zone": info["zone"],
            "shipping_cost": info["shipping_cost"],
            "free_threshold": info["free_threshold"],
        }
        for key, info in GOVERNORATES.items()
    ]


def get_cities(governorate: str) -> list[str]:
    """Return list of cities for a governorate (defaults to governorate name itself)."""
    info = GOVERNORATES.get(governorate)
    if not info:
        return []
    # For governorates without explicit city list, return the governorate name
    return [info["name_ar"]]


def get_areas_for_governorate(governorate: str) -> list[str]:
    """Return list of areas/neighborhoods for a governorate."""
    info = GOVERNORATES.get(governorate)
    if not info:
        return []
    return info.get("areas", [])


def calculate_shipping(
    governorate: str,
    cart_total: float = 0.0,
    default_inside: float = 35,
    default_outside: float = 60,
) -> dict:
    """Calculate shipping cost for an Egyptian governorate.

    Returns dict with: cost, free, governorate, governorate_ar, message,
    free_threshold, remaining (if not free).
    """
    info = GOVERNORATES.get(governorate)
    if not info:
        return {
            "cost": default_outside,
            "free": False,
            "governorate": governorate,
            "message": f"شحن {default_outside} جنيه",
        }

    cost = info["shipping_cost"]
    threshold = info["free_threshold"]
    is_free = cart_total >= threshold

    if is_free:
        return {
            "cost": 0,
            "free": True,
            "governorate": governorate,
            "governorate_ar": info["name_ar"],
            "message": f"شحن مجاني! (للطلبات فوق {threshold} جنيه)",
        }

    return {
        "cost": cost,
        "free": False,
        "governorate": governorate,
        "governorate_ar": info["name_ar"],
        "message": f"شحن {cost} جنيه إلى {info['name_ar']}",
        "free_threshold": threshold,
        "remaining": threshold - cart_total,
    }


def validate_egyptian_address(governorate: str, city: str | None = None) -> bool:
    """Validate that a governorate exists (and optionally a city within it)."""
    if governorate not in GOVERNORATES:
        return False
    if city is None:
        return True
    # For now, accept any non-empty city string (since our city lists are minimal)
    return bool(city)
