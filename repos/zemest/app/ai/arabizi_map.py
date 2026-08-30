"""Comprehensive Arabizi (Arabic chat alphabet) → Arabic transliteration maps.

Covers four major Arabic dialects written in Latin script:
- Egyptian Arabizi (most common online; uses digits 2,3,5,6,7,8,9)
- Gulf Arabizi (adds "q" for ق; uses "ch" for تش)
- Levantine Arabizi (similar to Egyptian; "sh" for ش)
- Maghrebi Arabizi (uses French-influenced digraphs: "kh", "gh", "ou")

The maps are layered:
1. ``ARABIZI_MAP`` (per dialect) — digit/digraph replacements. ``str`` → ``str``.
2. ``ARABIZI_LETTERS`` (universal) — single Latin letter → Arabic letter fallback.
3. ``ARABIZI_WORDS`` (per dialect + shared) — common whole-word lookups.

All maps are pure-Python ``dict`` (no external deps) so they work in any
environment. The :func:`app.ai.language_engine.transliterate_arabizi` function
applies them in order: words → digraphs → digits → letters.

Sources: derived from the well-known `amasad/arabish` conventions and
community-driven Arabizi standards used on Facebook/WhatsApp.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Per-dialect digit / digraph maps (exactly as specified in the design doc).
# Keys MUST be applied longest-first inside the engine.
# ---------------------------------------------------------------------------
ARABIZI_MAP: dict[str, dict[str, str]] = {
    "egyptian": {
        "3": "ع",
        "7": "ح",
        "2": "ء",
        "5": "خ",
        "8": "غ",
        "6": "ط",
        "9": "ق",
    },
    "gulf": {
        "3": "ع",
        "7": "ح",
        "2": "ء",
        "5": "خ",
        "8": "غ",
        "6": "ط",
        "9": "ق",
        "q": "ق",
    },
    "levantine": {
        "3": "ع",
        "7": "ح",
        "2": "ء",
        "5": "خ",
        "8": "غ",
        "6": "ط",
        "9": "ق",
    },
    "maghrebi": {
        "kh": "خ",
        "gh": "غ",
        "7": "ح",
        "9": "ق",
    },
}

# ---------------------------------------------------------------------------
# Universal multi-char digraphs applied across all dialects before single-char
# substitutions. (Order matters: digraphs must be replaced before letters so
# that "sh" → ش rather than "s" → س + "h" → ه.)
# ---------------------------------------------------------------------------
ARABIZI_DIGRAPHS: dict[str, str] = {
    "kh": "خ",
    "gh": "غ",
    "sh": "ش",
    "th": "ث",
    "ch": "تش",
    "ou": "و",
    "oo": "و",
    "ee": "ي",
    "aa": "ا",
    "2a": "أ",
    "2e": "إ",
    "2o": "أ",
    "3a": "عا",
    "7a": "حا",
    "9a": "قا",
}

# ---------------------------------------------------------------------------
# Universal single Latin-letter → Arabic-letter map (used as last-resort
# fallback for unknown tokens). Note: this is lossy — e.g. "c" → ك but
# could also be س. We pick the most common Arabizi convention.
# ---------------------------------------------------------------------------
ARABIZI_LETTERS: dict[str, str] = {
    "a": "ا",
    "b": "ب",
    "c": "ك",
    "d": "د",
    "e": "ي",
    "f": "ف",
    "g": "ج",
    "h": "ه",
    "i": "ي",
    "j": "ج",
    "k": "ك",
    "l": "ل",
    "m": "م",
    "n": "ن",
    "o": "و",
    "p": "ب",
    "q": "ق",
    "r": "ر",
    "s": "س",
    "t": "ت",
    "u": "و",
    "v": "ف",
    "w": "و",
    "x": "كس",
    "y": "ي",
    "z": "ز",
}

# ---------------------------------------------------------------------------
# Common whole-word lookups (Egyptian-first, with dialect-specific overrides).
# These are high-precision translations: if a token matches a key (case-folded),
# use the Arabic replacement directly — no character substitution needed.
# ---------------------------------------------------------------------------
ARABIZI_WORDS_SHARED: dict[str, str] = {
    # Pronouns
    "ana": "انا",
    "enta": "انت",
    "enti": "انتي",
    "enta2": "انت",
    "int": "انت",
    "inti": "انتي",
    "ehwa": "هو",
    "hwa": "هو",
    "hia": "هي",
    "hya": "هي",
    "ehna": "احنا",
    "ihna": "احنا",
    "nhna": "احنا",
    # Common verbs / questions
    "3ayez": "عايز",
    "3ayza": "عايزة",
    "3ayezni": "عايزني",
    "3andi": "عندي",
    "3andak": "عندك",
    "3andik": "عندك",
    "3ando": "عنده",
    "3andha": "عندها",
    "3andna": "عندنا",
    "3amlt": "عملت",
    "3aml": "عامل",
    "3amla": "عاملة",
    "awez": "عايز",
    "3ml": "عمل",
    # Greetings / fillers
    "yalla": "يلا",
    "yala": "يلا",
    "tayeb": "طيب",
    "tab": "طيب",
    "keda": "كده",
    "kida": "كده",
    "5alas": "خلاص",
    "khlas": "خلاص",
    "shukran": "شكرا",
    "shokran": "شكرا",
    "5las": "خلاص",
    "ya3ni": "يعني",
    "y3ni": "يعني",
    "yaani": "يعني",
    # Negation / common adverbs
    "mish": "مش",
    "mesh": "مش",
    "mosh": "مش",
    "msh": "مش",
    "fish": "فش",
    "mafish": "مافيش",
    "mafeesh": "مافيش",
    "maku": "ماكو",
    "mako": "ماكو",
    "awy": "أوي",
    "awii": "أوي",
    "jiddan": "جدا",
    # Common nouns (commerce context)
    "sillar": "سعر",
    "s3ar": "سعر",
    "price": "سعر",
    "cost": "تكلفة",
    "order": "طلب",
    "talab": "طلب",
    "delivery": "توصيل",
    "shipping": "شحن",
    "available": "متاح",
    "instock": "متوفر",
    "outofstock": "غير متوفر",
    "habibi": "حبيبي",
    "habibti": "حبيبتي",
    "yasta": "يا صاحبي",
    "amr": "أمر",
    "haga": "حاجة",
    "hagat": "حاجات",
    "hagaa": "حاجة",
    # Question words
    "kam": "كام",
    "leh": "ليه",
    "leesh": "ليش",
    "lesh": "ليش",
    "ezay": "إزاي",
    "izzay": "إزاي",
    "men": "مين",
    "min": "مين",
    "fien": "فين",
    "fein": "فين",
    "wein": "فين",
    "wen": "فين",
    # Connectors
    "w": "و",
    "wa": "و",
    "b": "ب",
    "l": "ل",
    "3la": "على",
    "ala": "على",
    "3lshan": "علشان",
    "3shan": "علشان",
    "3ashan": "علشان",
    "l2n": "لكن",
    "lkn": "لكن",
    "bs": "بس",
    "bas": "بس",
}

# Egyptian-specific overrides (capitalised / phrasal Egyptian markers)
ARABIZI_WORDS_EGYPTIAN: dict[str, str] = {
    "enta": "انت",
    "enta2": "انت",
    "enta3": "انت",
    "bta3": "بتاع",
    "bta3ty": "بتاعتك",
    "bta3ko": "بتاعكم",
    "bta3ha": "بتاعها",
    "bta3o": "بتاعه",
    "anhy": "انهي",
    "ehda": "واحدة",
    "2olly": "قوللي",
    "2oly": "قوللي",
    "2ol": "قول",
    "2ollak": "قولك",
    "2olo": "قولو",
    "el": "ال",
    "3aba": "عباية",
    "galabeya": "جلابية",
    "galabiya": "جلابية",
}

# Gulf-specific overrides
ARABIZI_WORDS_GULF: dict[str, str] = {
    "shlonik": "شلونك",
    "shlonk": "شلونك",
    "shlounik": "شلونك",
    "shakbar": "شخبار",
    "shkbar": "شخبار",
    "abhi": "أبي",
    "abi": "أبي",
    "tabi": "تبي",
    "yabi": "يبي",
    "wayed": "وايد",
    "waid": "وايد",
    "kidda": "كذا",
    "chithi": "جذي",
    "chthy": "جذي",
    "ya3l": "يعل",
    "yala": "يلا",
    "esh": "ايش",
    "aish": "ايش",
    "shfeek": "شفيك",
    "shfik": "شفيك",
    "tayyeb": "طيب",
    "shukran": "شكرا",
    "na3am": "نعم",
    "3afwan": "عفوا",
}

# Levantine-specific overrides
ARABIZI_WORDS_LEVANTINE: dict[str, str] = {
    "shu": "شو",
    "shou": "شو",
    "shoo": "شو",
    "shy": "شي",
    "shi": "شي",
    "heek": "هيك",
    "hik": "هيك",
    "ktir": "كتير",
    "kter": "كتير",
    "hallaa": "هلق",
    "hala2": "هلق",
    "halla2": "هلق",
    "nater": "ناطر",
    "natr": "ناطر",
    "leish": "ليش",
    "lesh": "ليش",
    "ken": "كان",
    "miish": "مش",
    "mish": "مش",
    "3amb": "عم",
    "3am": "عم",
    "3amlt": "عملت",
    "sharmuta": "شرمطة",
    "ya3ni": "يعني",
    "shukran": "شكرا",
    "afwan": "عفوا",
}

# Maghrebi (Darija) overrides — French-influenced spellings
ARABIZI_WORDS_MAGHREBI: dict[str, str] = {
    "wach": "واش",
    "wesh": "واش",
    "wash": "واش",
    "bash": "بش",
    "bghit": "بغيت",
    "bgha": "بغى",
    "bghiti": "بغيتي",
    "dyali": "ديالي",
    "dyalk": "ديالك",
    "dyalkom": "ديالكم",
    "dyalha": "ديالها",
    "khouya": "خويا",
    "khti": "ختي",
    "chnou": "شنو",
    "chno": "شنو",
    "ach": "اش",
    "3la": "على",
    "wach": "واش",
    "3afak": "عافاك",
    "3afrit": "عفريت",
    "baraka": "بركة",
    "safi": "صافي",
    "bzaf": "بزاف",
    "bezzaf": "بزاف",
    "yallah": "يلا",
    "yala": "يلا",
    "merci": "شكرا",
}


def get_word_map(dialect: str) -> dict[str, str]:
    """Return the merged word-lookup map for a given dialect.

    Layering (later wins): shared → egyptian (default) → dialect-specific.
    """
    dialect = (dialect or "egyptian").lower()
    merged: dict[str, str] = dict(ARABIZI_WORDS_SHARED)
    # Always include Egyptian as a base layer (largest shared vocab)
    merged.update(ARABIZI_WORDS_EGYPTIAN)
    if dialect == "gulf":
        merged.update(ARABIZI_WORDS_GULF)
    elif dialect == "levantine":
        merged.update(ARABIZI_WORDS_LEVANTINE)
    elif dialect == "maghrebi":
        merged.update(ARABIZI_WORDS_MAGHREBI)
    elif dialect == "egyptian":
        pass  # already applied
    else:
        # Iraqi / Sudanese / Yemeni / MSA — fall back to shared + Egyptian.
        pass
    return merged


def get_dialect_map(dialect: str) -> dict[str, str]:
    """Return the per-dialect digit/digraph map (falls back to Egyptian)."""
    dialect = (dialect or "egyptian").lower()
    if dialect in ARABIZI_MAP:
        return ARABIZI_MAP[dialect]
    return ARABIZI_MAP["egyptian"]


__all__ = [
    "ARABIZI_MAP",
    "ARABIZI_DIGRAPHS",
    "ARABIZI_LETTERS",
    "ARABIZI_WORDS_SHARED",
    "ARABIZI_WORDS_EGYPTIAN",
    "ARABIZI_WORDS_GULF",
    "ARABIZI_WORDS_LEVANTINE",
    "ARABIZI_WORDS_MAGHREBI",
    "get_word_map",
    "get_dialect_map",
]
