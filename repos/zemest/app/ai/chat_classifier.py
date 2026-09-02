"""Automatic conversation classification: work chat vs junk chat.

Runs silently on every conversation (imported DYI threads, live agent
chats, WhatsApp exports). Zero user interaction — the silent trainer
calls this before any message is used for learning, so friend-to-owner
chats ("فينك يا عم"، الماتش، خروجة) never contaminate the merchant's
learned voice, and never skew the buyer persona.

Design:
- Pure CPU, no network, no LLM — regex/lexicon scoring in microseconds.
- Egyptian-commerce lexicon (price / availability / delivery / address /
  payment / size / order confirmation) vs personal lexicon (family,
  social plans, football, laughter-only, meme/ link-only).
- Structural signals: merchant participation, phone-number patterns,
  currency amounts, thread length, media-only bursts.
- Explainable: returns the exact signals that fired, stored on the
  conversation row for later inspection/debugging.

Output label ∈ {"commerce", "junk", "mixed"} + confidence 0..1.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

CLASSIFIER_VERSION = "cc-2"

# ---------------------------------------------------------------------------
# Lexicons (Egyptian Arabic + Arabizi + English)
# ---------------------------------------------------------------------------

COMMERCE_LEXICON: dict[str, tuple[str, float]] = {
    # price inquiry — the strongest commerce signal in Egyptian DMs
    "price": ("بكام|بكم|بكام؟|كام|السعر|سعره|سعرها|الأسعار|الاسعار| pricing|price|how much|كام ده|بكام ده",
              3.0),
    # availability / stock
    "availability": ("متوفر|متاح|موجود|عندك|معاك|فيه منه|متوفرين|in stock|available|متوفر حالياً",
                     2.0),
    # delivery / shipping
    "delivery": ("التوصيل|توصيل|شحن|الشحن|بيوصل|يوصل|التسليم|delivery|shipping|شحن بكام|التوصيل بكام",
                 2.0),
    # address / PII collection (order flow)
    "address": ("العنوان|عنواني|محافظة|شارع|عمارة|الدور|رقم التليفون|رقم موبايل|الرقم بتاعك",
                2.5),
    # payment methods (Egyptian)
    "payment": ("كاش عند|الدفع عند|فودافون كاش|فودافون|انستاباي|إنستاباي|فوري|cod|payment|الفيزا|محفظة",
                2.0),
    # sizes / colors (fashion commerce)
    "size_color": ("مقاس|مقاسي|size|لون|اللون|الألوان|الوان|color|colour|٤١|۴۲|variants",
                   1.5),
    # order intent
    "order_intent": ("عايز أشتري|عايز اشتري|عايزة اشتري|هخد|هاخد|هاخده|عايزه|نفسي في|haz|order|اطلب|أطلب|أكد|اكد الطلب|حجز|احجز",
                     2.5),
    # order confirmation / follow-up
    "confirmation": ("تم الطلب|طلبك|الأوردر|الاوردر|أوردر|اوردر|order confirmed|رقم الطلب|تم التأكيد|هيبعت|هبعته|شحن الطلب",
                     3.0),
    # product vocabulary
    "product": ("الموديل|المنتج|البنزين|العرض|الاعلان|الإعلان|متجر|القطعة|جيب لي|هاتلي|product|item",
                1.0),
}

JUNK_LEXICON: dict[str, tuple[str, float]] = {
    # family / personal life
    "family": ("ماما|بابا|أمي|امي|ابويا|أختك|اخوكي|اختك|جدتي|عمك|خالتك|خالي|العيال|مراتي|جوزي|بنتي|ولادي|ولادي الصغار|أهل",
               2.5),
    # social plans between friends
    "social": ("نتقابل|نتشاف|اشوفك|أشوفك|قعدة|خروجة|نخرج|الحقني|تعالى|نتكلم في الصوت|كول|عزا|الفرح|جنازة|نتغدى|نتعشى|حد يوم",
               2.5),
    # football / entertainment talk
    "entertainment": ("الماتش|الأهلي|الاهلي|الزمالك|مباراة|الليجا|فيفا|بلايستيشن|الفيلم|مسلسل|الحلقة|أغنية|مليون صوت|الترند|تيك توك",
                      1.5),
    # "where are you / what's up" personal check-ins
    "checkin": ("فينك|فينك يا|ماليك|مالك|معلش تعبت|زعلان|مشغول ليه|بقالك|غايب|وحشني",
                2.0),
    # forwarded meme / link sharing
    "forwarded": ("فورورد|تم الإرسال|forwarded|شوف ده|بص على ده|هتضحك|dekh ke|see this",
                  2.0),
}

# Laughter-only content (whole message is هههه / hhhh / lol spam).
#
# SECURITY: the previous pattern
#   r"^(?:[هh]\s*ه*|[هh]{3,}|هه+|hh+|ههه+|\b(?:lol|lmao|😂+|🤣+)\b[\s😂🤣]*)+$"
# had catastrophic backtracking (nested quantifiers over a character class):
# 30+ repetitions of "هه" followed by any non-matching char froze the
# engine for 30+ SECONDS (audit C1, PoC reproduced). Reachable
# unauthenticated via the Messenger/IG/WhatsApp webhook on every message
# through the 45-second silent-trainer cycle.
#
# This replacement is pure linear-time tokenization: split the message into
# whitespace/emoji-separated runs and accept only if EVERY run is laughter.
# No backtracking is possible — each run is checked once with a simple
# fullmatch over a flat character class.
_LAUGHTER_TOKEN_RE = re.compile(r"[هh]+(?:\s+[هh]+)*")           # ه-runs
_LAUGHTER_ASCII_RE = re.compile(r"(?:ha|he){2,}", re.IGNORECASE)  # haha/hehe
_LAUGHTER_WORDS_RE = re.compile(r"^(?:lol|lmao|haha|hehe|hihi)$", re.IGNORECASE)
_LAUGHTER_EMOJI_RE = re.compile(r"[😂🤣]+")


def is_laughter_only(text: str) -> bool:
    """True when the message contains nothing but laughter (ههه / hhhh /
    lol / 😂 runs, possibly mixed and separated by spaces).

    Linear-time guarantee: the input is tokenized first; each token is
    matched with fullmatch (no unbounded quantifier nesting). Worst case
    is O(n) in the message length — immune to the old ReDoS.
    """
    stripped = text.strip()
    if not stripped:
        return False
    # Split on whitespace AND standalone emoji clusters: laughter messages
    # freely mix "ههه 😂 😂 هه".
    tokens = [t for t in re.split(r"\s+", stripped) if t]
    if not tokens:
        return False
    for tok in tokens:
        if _LAUGHTER_EMOJI_RE.fullmatch(tok):
            continue  # pure emoji run
        if _LAUGHTER_WORDS_RE.match(tok):
            continue  # lol / lmao / haha
        if _LAUGHTER_TOKEN_RE.fullmatch(tok):
            continue  # ههه / hhhh run
        if _LAUGHTER_ASCII_RE.fullmatch(tok):
            continue  # hahaha
        return False
    return True

# Egyptian mobile numbers: 010/011/012/015 + 8 digits (Arabic or Latin digits)
_PHONE_RE = re.compile(r"(?:\+?2)?01[0125]\d{8}")

# Currency amounts: 250 جنيه / 250 EGP / 250LE / ٢٥٠ ج
_CURRENCY_RE = re.compile(r"(?:\d{2,6}|[٠-٩]{2,6})\s*(?:جنيه|ج\b|EGP|LE|ج\.م|le\.|pounds?)", re.IGNORECASE)

# Bare size numbers (42, 43) — weaker, only when near size words
_URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)

_MERCHANT_ROLES = {"merchant", "assistant"}


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

@dataclass
class Classification:
    label: str = "mixed"          # commerce | junk | mixed
    commerce_score: float = 0.0
    junk_score: float = 0.0
    confidence: float = 0.0
    signals: list[str] = field(default_factory=list)
    merchant_participated: bool = False
    message_count: int = 0


def _score_text(text: str, lexicon: dict[str, tuple[str, float]]) -> tuple[float, list[str]]:
    """Score one message against a lexicon. Returns (score, fired_signal_names)."""
    score = 0.0
    fired: list[str] = []
    if not text:
        return 0.0, fired
    haystack = text.lower()
    for name, (pattern, weight) in lexicon.items():
        if re.search(pattern, haystack):
            score += weight
            fired.append(name)
    return score, fired


def classify_messages(messages: list[dict]) -> Classification:
    """Classify one conversation.

    ``messages``: list of {role, content} dicts in any order
    (roles: customer | assistant | merchant | system).
    Returns a Classification with an explainable signal list.
    """
    result = Classification(message_count=len(messages))

    if not messages:
        result.label = "junk"
        result.confidence = 0.2
        result.signals = ["empty_thread"]
        return result

    commerce_score = 0.0
    junk_score = 0.0
    signal_counts: dict[str, int] = {}

    laughter_msgs = 0
    url_only_msgs = 0
    customer_msgs = 0
    merchant_msgs = 0
    has_phone = False
    has_currency = False

    for msg in messages:
        role = (msg.get("role") or "").lower()
        content = msg.get("content") or ""

        if role in _MERCHANT_ROLES:
            merchant_msgs += 1
        elif role == "customer":
            customer_msgs += 1

        if not content or not content.strip():
            continue

        c_score, c_fired = _score_text(content, COMMERCE_LEXICON)
        j_score, j_fired = _score_text(content, JUNK_LEXICON)
        # merchant-side commerce content is extra strong evidence (the page
        # is doing business in this thread, not chatting with a friend)
        multiplier = 1.3 if role in _MERCHANT_ROLES else 1.0
        commerce_score += c_score * multiplier
        junk_score += j_score

        for s in c_fired:
            signal_counts[s] = signal_counts.get(s, 0) + 1
        for s in j_fired:
            signal_counts[s] = signal_counts.get(s, 0) + 1

        stripped = content.strip()
        if is_laughter_only(stripped):
            laughter_msgs += 1
            junk_score += 1.5
            signal_counts["laughter_only"] = signal_counts.get("laughter_only", 0) + 1

        without_urls = _URL_RE.sub("", stripped).strip()
        if _URL_RE.search(stripped) and len(without_urls) < 12:
            url_only_msgs += 1
            junk_score += 1.0
            signal_counts["link_only"] = signal_counts.get("link_only", 0) + 1

        if _PHONE_RE.search(content):
            has_phone = True
            commerce_score += 2.5
            signal_counts["phone_number"] = 1

        if _CURRENCY_RE.search(content):
            has_currency = True
            commerce_score += 2.0
            signal_counts["currency_amount"] = 1

    result.merchant_participated = merchant_msgs > 0

    # --- structural adjustments ---
    total = len(messages)
    # A thread that is ONLY laughter/links/greetings and never touches commerce
    if laughter_msgs + url_only_msgs >= max(2, total * 0.6) and commerce_score < 3:
        junk_score += 3.0
        signal_counts["meme_thread"] = 1

    # Very short thread with zero commerce and zero merchant participation
    # → most likely a friend popping in ("صباح الخير" then silence)
    if total <= 3 and commerce_score == 0 and merchant_msgs == 0:
        junk_score += 2.0
        signal_counts["short_no_commerce"] = 1

    # Merchant answered with substance → work thread bias
    if merchant_msgs >= 2 and commerce_score >= 4:
        commerce_score += 1.5
        signal_counts["merchant_active"] = 1

    result.commerce_score = commerce_score
    result.junk_score = junk_score

    # --- decision ---
    margin = commerce_score - junk_score
    if margin >= 2.5:
        result.label = "commerce"
    elif margin <= -2.5:
        result.label = "junk"
    else:
        result.label = "mixed"

    spread = abs(commerce_score - junk_score)
    result.confidence = round(min(0.99, 0.3 + spread / 12.0 + (0.1 if has_phone else 0) + (0.1 if has_currency else 0)), 2)

    # Order: strongest signals first
    result.signals = [f"{name}×{count}" for name, count in
                      sorted(signal_counts.items(), key=lambda kv: -kv[1])]
    return result


def is_commerce(label: str, score: float) -> bool:
    """Training-set membership rule: which conversations feed the learner.

    ``mixed`` conversations are INCLUDED when commerce evidence is at
    least as strong as junk evidence — Egyptian threads routinely mix
    "إزيك يا معلم" small talk with a real order, and dropping those
    would throw away the most natural examples of the page's voice.
    """
    if label == "commerce":
        return True
    if label == "mixed":
        return score >= -1.0  # commerce within striking distance
    return False
