"""Multi-dialect Arabic + English + code-switching language engine.

Architecture (all CPU, all open-source, commercial-safe):
1. GlotLID v3 (optional) — sentence-level language + script detection
2. camel_tools.DialectIdentifier (optional) — 26-class city/region dialect detection
3. Rule-based Arabizi → Arabic transliteration (no external deps)
4. Code-switching detection via script analysis

Falls back gracefully if optional dependencies are missing.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class LanguageDetection:
    """Result of advanced language detection."""
    primary_language: str  # arabic, english, arabizi, mixed
    arabic_dialect: Optional[str] = None  # egyptian, gulf, levantine, maghrebi, iraqi, msa, none
    english_variant: Optional[str] = None  # us, uk, indian, none
    is_code_switched: bool = False
    detected_scripts: list[str] = field(default_factory=list)  # arabic, latin
    confidence: float = 0.0
    normalized_text: Optional[str] = None  # Arabizi → Arabic if applicable

    @property
    def legacy_label(self) -> str:
        """Backward-compat 3-class label: ``"arabic"`` | ``"arabizi"`` | ``"english"``.

        Several callers (``app.ai.agent.process_customer_message`` and the
        legacy ``app.ai.language.detect_language`` shim) historically relied
        on this attribute to pick a dialect-appropriate fallback response.
        The multi-dialect ``primary_language`` field can return ``"mixed"``
        which those callers cannot handle, so we collapse it back to the
        legacy 3-class space here.
        """
        if self.primary_language == "mixed":
            return "arabic" if self.arabic_dialect else "english"
        return self.primary_language


# ---------------------------------------------------------------
# Arabizi character mappings per dialect
# ---------------------------------------------------------------

ARABIZI_MAP: dict[str, dict[str, str]] = {
    "egyptian": {
        # NOTE: the dead duplicate key `"2": "ء"` was removed — Python kept
        # the last literal ("أ") anyway; documenting the effective mapping.
        "3": "ع", "7": "ح", "2": "أ", "5": "خ", "8": "غ",
        "6": "ط", "9": "ق", "3'": "غ", "5'": "خ",
        "7'": "خ", "kh": "خ", "gh": "غ", "sh": "ش", "ch": "تش",
        "th": "ث", "aa": "ا", "ee": "ي", "oo": "و",
    },
    "gulf": {
        "3": "ع", "7": "ح", "2": "ء", "5": "خ", "8": "غ",
        "6": "ط", "9": "ق", "kh": "خ", "gh": "غ", "sh": "ش",
        "ch": "تش", "th": "ث", "dh": "ذ", "zh": "ز",
    },
    "levantine": {
        "3": "ع", "7": "ح", "2": "ء", "5": "خ", "8": "غ",
        "6": "ط", "9": "ق", "kh": "خ", "gh": "غ", "sh": "ش",
        "ch": "تش", "th": "ث",
    },
    "maghrebi": {
        "kh": "خ", "gh": "غ", "7": "ح", "9": "ق", "3": "ع",
        "2": "ء", "5": "خ", "8": "غ", "ch": "ش",
    },
    "iraqi": {
        "3": "ع", "7": "ح", "2": "ء", "5": "خ", "8": "غ",
        "6": "ط", "9": "ق", "kh": "خ", "gh": "غ", "sh": "ش",
        "ch": "تش", "th": "ث",
    },
    "msa": {
        "3": "ع", "7": "ح", "2": "ء", "5": "خ", "8": "غ",
        "6": "ط", "9": "ق", "kh": "خ", "gh": "غ", "sh": "ش",
        "ch": "تش", "th": "ث",
    },
}

# Arabizi word patterns for dialect detection
ARABIZI_DIALECT_WORDS: dict[str, list[str]] = {
    "egyptian": ["3ayez", "3ayza", "keda", "mesh", "awy", "3andi", "3andak", "enta", "enti", "ana", "eh", "aiwa", "la2"],
    "gulf": ["abghi", "tabghi", "shlon", "shloun", "yalla", "khallas", "wlla", "3ndi", "tkoon", "weed"],
    "levantine": ["biddi", "shu", "keef", "3am", "leh", "hayda", "haydi", "wen"],
    "maghrebi": ["bghit", "kifash", "wach", "3ndk", "fin", "wash", "mnin"],
    "iraqi": ["arid", "tarid", "shino", "wayn", "leen", "chno"],
}


# ---------------------------------------------------------------
# Core detection functions
# ---------------------------------------------------------------

def _count_arabic_chars(text: str) -> int:
    return len(re.findall(r"[\u0600-\u06FF]", text))


def _count_latin_chars(text: str) -> int:
    return len(re.findall(r"[a-zA-Z]", text))


def _has_arabizi_digits(text: str) -> bool:
    """Check for Arabizi digit substitutions (3, 7, 2, 5, 8, 6, 9).

    Hardening (audit A6-H2): a digit must be **adjacent to a Latin letter**
    to count as Arabizi. Previously any Latin text containing a common
    digit was misdetected — "size 42 available?" and "order 2 items please"
    became "arabizi" and were then mangled by transliteration.
    """
    return bool(re.search(r"[a-zA-Z][378529]|[378529][a-zA-Z]", text))


# A token is "numeric" when it is only digits (Latin or Arabic-Indic),
# punctuation, currency/phone glue, or size/price-like shapes. These must
# NEVER be transliterated — "350" is a price, not ع-خ-0.
_NUMERIC_TOKEN_RE = re.compile(
    r"[0-9٠-٩]+(?:[.,:/-][0-9٠-٩]+)*"
)


def _is_numeric_token(token: str) -> bool:
    """True for phone numbers, prices, sizes, quantities, dates.

    Handles: 350, 40, 01276543210, 2.5, ١٢٣, +20, 10-12, 350.00,
    size40 (trailing digits attached to a Latin word go Latin-side).
    """
    if _NUMERIC_TOKEN_RE.fullmatch(token):
        return True
    # Phone with leading + / country code
    if re.fullmatch(r"\+?[0-9٠-٩][0-9٠-٩\-\s]*", token):
        return True
    return False


def _looks_like_arabizi(text: str) -> bool:
    """Arabizi requires letters ADJACENT to Arabizi digits, not just digits.

    Audit H2: any English sentence with a common digit ("size 42",
    "order 2 items", "iPhone 13") was misdetected as arabizi and then
    transliterated into garbage. Real Arabizi interleaves letters with the
    substituted digits INSIDE a word: "3ayez", "7aga", "2olt", "5alas".
    """
    text_lower = text.lower()
    # Digit directly attached to letters inside a word (either side).
    if re.search(r"[a-z][3782569]|[3782569][a-z]", text_lower):
        return True
    # Whole-word digit-words from the dialect lexicons ("5alas" caught by
    # adjacency; standalone tokens like "3" alone are NOT arabizi).
    for words in ARABIZI_DIALECT_WORDS.values():
        for w in words:
            if re.search(rf"\b{re.escape(w)}\b", text_lower):
                return True
    return False


def _detect_arabizi_dialect(text: str) -> Optional[str]:
    """Detect which Arabic dialect an Arabizi text uses.

    Word-boundary matching (audit A6-L5): previously raw substring ``in``
    let "ana" match inside "banana"/"canada".
    """
    text_lower = text.lower()
    scores: dict[str, int] = {}
    for dialect, words in ARABIZI_DIALECT_WORDS.items():
        score = sum(
            1 for w in words if re.search(rf"\b{re.escape(w)}\b", text_lower)
        )
        if score > 0:
            scores[dialect] = score
    if not scores:
        return "egyptian"  # default
    return max(scores, key=scores.get)


def _detect_arabic_dialect_by_words(text: str) -> Optional[str]:
    """Detect Arabic dialect from Arabic-script text using word patterns."""
    dialect_markers = {
        "egyptian": ["عايز", "عندك", "كده", "مش", "اوى", "ايوه", "لأ", "انا", "انت", "ازيك", "كل ده", "ابقا"],
        "gulf": ["ابغى", "تبغى", "شلون", "خلص", "يلا", "عندي", "تكون", "وش", "ويش"],
        "levantine": ["بدي", "شو", "كيف", "ليش", "هيدا", "هيدي", "وين", "عام", "هيك"],
        "maghrebi": ["بغيت", "كيفاش", "واش", "عندك", "فين", "منين", "دابا"],
        "iraqi": ["اريد", "تريد", "شينو", "واين", "لين", "چنو", "گلت"],
        "msa": ["أريد", "كيف", "ماذا", "لماذا", "هذا", "هذه", "أين", "لذلك", "لكن", "ثم"],
    }
    scores: dict[str, int] = {}
    for dialect, words in dialect_markers.items():
        score = sum(1 for w in words if w in text)
        if score > 0:
            scores[dialect] = score
    if not scores:
        return None
    return max(scores, key=scores.get)


# Tokens that are purely numeric (prices, sizes, phone numbers, order
# quantities, Arabic-Indic digits) must NEVER be transliterated — the old
# whole-string replace turned "el se3r 350" into "el seعر عخ0" and mangled
# the customer's phone number (audit A6-H1).
_NUMERIC_TOKEN_RE = re.compile(r"^[0-9٠-٩+\-.,:/()%\s]+$")


def _split_tokens(text: str) -> list[tuple[str, str]]:
    """Split into (token, trailing_separator) pairs. Separators preserved."""
    parts = re.split(r"(\s+)", text)
    out: list[tuple[str, str]] = []
    i = 0
    while i < len(parts):
        tok = parts[i]
        sep = parts[i + 1] if i + 1 < len(parts) else ""
        if tok:
            out.append((tok, sep))
        elif sep and out:
            # leading whitespace before first token — fold into first pair
            out[0] = (out[0][0], sep + out[0][1])
        elif sep:
            out.append(("", sep))
        i += 2
    return out


def transliterate_arabizi(text: str, dialect: str = "egyptian") -> str:
    """Transliterate Arabizi (Latin-script Arabic) to Arabic script.

    Hardening (audit A6-H1/H2):
    - **Numeric tokens are never transliterated.** Prices ("350"), sizes
      ("40"), phone numbers ("01276543210") and quantities survive intact;
      previously "350" became "عخ0" and phones were destroyed.
    - Token-by-token replacement with lowercase folding, so "3AYEZ" also
      transliterates (previously case-sensitive and stayed Latin).
    - Mixed letter+digit tokens ("3ayez", "se3r") still transliterate —
      that IS Arabizi.
    """
    if not text or not isinstance(text, str):
        return text

    mapping = ARABIZI_MAP.get(dialect, ARABIZI_MAP["egyptian"])
    replacements = sorted(mapping.items(), key=lambda x: -len(x[0]))

    out_parts: list[str] = []
    for token, sep in _split_tokens(text):
        if not token:
            out_parts.append(sep)
            continue
        if _NUMERIC_TOKEN_RE.match(token):
            # pure number / punctuation — leave untouched
            out_parts.append(token + sep)
            continue
        lowered = token.lower()
        result = lowered
        for latin, arabic in replacements:
            if latin in result:
                result = result.replace(latin, arabic)
        out_parts.append(result + sep)

    return "".join(out_parts)


def detect_code_switching(text: str) -> list[dict]:
    """Detect intra-sentence language mixing.

    Returns list of segments with their detected language:
    [{"text": "...", "language": "arabic|english|arabizi"}, ...]
    """
    segments: list[dict] = []
    # Split on script boundaries
    parts = re.split(r"([\u0600-\u06FF]+|[a-zA-Z][a-zA-Z0-9' ]*)", text)

    for part in parts:
        part = part.strip()
        if not part:
            continue
        if re.match(r"^[\u0600-\u06FF]+$", part):
            segments.append({"text": part, "language": "arabic"})
        elif re.match(r"^[a-zA-Z]", part):
            if _has_arabizi_digits(part):
                segments.append({"text": part, "language": "arabizi"})
            else:
                segments.append({"text": part, "language": "english"})

    return segments


def detect_language_advanced(text: str) -> LanguageDetection:
    """Detect language, dialect, and code-switching.

    This is the main entry point. It tries to use camel_tools/GlotLID
    if available, falling back to the rule-based detector otherwise.
    """
    if not text or not text.strip():
        return LanguageDetection(
            primary_language="english",
            confidence=0.0,
            detected_scripts=[],
        )

    arabic_count = _count_arabic_chars(text)
    latin_count = _count_latin_chars(text)
    total = arabic_count + latin_count

    if total == 0:
        return LanguageDetection(
            primary_language="english",
            confidence=0.0,
            detected_scripts=[],
        )

    arabic_ratio = arabic_count / total
    # Audit H2: require LETTER-DIGIT adjacency, not bare digit presence —
    # "size 42 available" is English, "3ayez el sandal" is arabizi.
    has_arabizi = _looks_like_arabizi(text) and latin_count > 0

    detected_scripts: list[str] = []
    if arabic_count > 0:
        detected_scripts.append("arabic")
    if latin_count > 0:
        detected_scripts.append("latin")

    is_code_switched = arabic_count > 5 and latin_count > 5

    # Primary language detection — mixed is evaluated BEFORE arabizi so a
    # genuinely code-switched Arabic+English sentence is not preempted by a
    # stray digit (audit A6-H2: the mixed branch was nearly unreachable).
    if arabic_ratio > 0.3:
        primary = "arabic"
        dialect = _detect_arabic_dialect_by_words(text) or "egyptian"
        normalized = None
        confidence = min(0.95, 0.6 + (arabic_ratio * 0.4))
    elif is_code_switched:
        primary = "mixed"
        dialect = _detect_arabic_dialect_by_words(text)
        normalized = None
        confidence = 0.8
    elif has_arabizi:
        primary = "arabizi"
        dialect = _detect_arabizi_dialect(text)
        normalized = transliterate_arabizi(text, dialect)
        confidence = 0.75
    else:
        primary = "english"
        dialect = None
        normalized = None
        confidence = 0.85

    # Try camel_tools for better dialect detection (optional)
    try:
        from camel_tools.dialectid import DialectIdentifier  # type: ignore

        if not hasattr(detect_language_advanced, "_did"):
            detect_language_advanced._did = DialectIdentifier.pretrained()  # type: ignore[attr-defined]
        did = detect_language_advanced._did  # type: ignore[attr-defined]
        preds = did.predict([text])
        if preds and preds[0].top_dialect:
            # camel_tools returns 26 city-level dialects; map to our 6 groups
            city = preds[0].top_dialect
            dialect = _map_camel_dialect(city) or dialect
            confidence = min(0.99, confidence + 0.1)
    except ImportError:
        pass  # camel_tools not installed — use rule-based
    except Exception as e:
        logger.debug(f"camel_tools dialect detection failed: {e}")

    return LanguageDetection(
        primary_language=primary,
        arabic_dialect=dialect,
        english_variant="us" if primary in ("english", "mixed") else None,
        is_code_switched=is_code_switched,
        detected_scripts=detected_scripts,
        confidence=confidence,
        normalized_text=normalized,
    )


def _map_camel_dialect(city: str) -> Optional[str]:
    """Map camel_tools 26-city dialect to our 6-group classification."""
    mapping = {
        # Egypt
        "Cairo": "egyptian", "Alexandria": "egyptian", "Asyout": "egyptian",
        # Gulf
        "Doha": "gulf", "Dubai": "gulf", "Kuwait": "gulf",
        "Manama": "gulf", "Muscat": "gulf", "Riyadh": "gulf",
        # Levant
        "Aleppo": "levantine", "Beirut": "levantine", "Damascus": "levantine",
        "Amman": "levantine", "Jerusalem": "levantine",
        # Maghreb
        "Tunis": "maghrebi", "Rabat": "maghrebi", "Casablanca": "maghrebi",
        "Algiers": "maghrebi", "Tripoli": "maghrebi",
        # Iraq
        "Baghdad": "iraqi", "Basra": "iraqi", "Mosul": "iraqi",
        # Sudan
        "Khartoum": "sudanese",
        # MSA
        "MSA": "msa",
    }
    return mapping.get(city)


def normalize_arabic_advanced(text: str) -> str:
    """Normalize Arabic text using rule-based approach.

    (camel_tools provides more advanced normalization if available.)
    """
    # Remove tashkeel
    text = re.sub(r"[\u0610-\u061A\u064B-\u065F\u0670]", "", text)
    # Normalize alef variants
    text = re.sub(r"[إأآا]", "ا", text)
    # Normalize taa marbuta
    text = re.sub(r"ة", "ه", text)
    # Normalize yaa
    text = re.sub(r"ى", "ي", text)
    # Remove tatweel
    text = re.sub(r"ـ", "", text)
    return text.strip()


# Backward compatibility with existing code
def detect_language(text: str) -> str:
    """Backward-compatible simple detection. Returns 'arabic', 'arabizi', or 'english'."""
    result = detect_language_advanced(text)
    if result.primary_language == "mixed":
        return "arabic" if result.arabic_dialect else "english"
    return result.primary_language
