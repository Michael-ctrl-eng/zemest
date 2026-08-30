"""Backward-compatible language detection API.

This module is the legacy entry point. It now delegates to the new
multi-dialect :mod:`app.ai.language_engine` while keeping the original
``detect_language(text) -> str`` and ``normalize_arabic(text) -> str``
signatures so existing callers (and tests) continue to work.

The new engine gracefully degrades: if ``camel_tools`` and/or ``fasttext``
are not installed, it falls back to the original regex/script-ratio
heuristics defined here.
"""

from __future__ import annotations

import re

from app.ai.language_engine import (
    LanguageDetection,
    detect_language_advanced,
    normalize_arabic_advanced,
)

__all__ = [
    "detect_language",
    "detect_language_advanced",
    "normalize_arabic",
    "normalize_arabic_advanced",
    "LanguageDetection",
]


def detect_language(text: str) -> str:
    """Detect if text is Arabic, Arabizi (Egyptian Arabic in Latin), or English.

    Returns: ``'arabic'`` | ``'arabizi'`` | ``'english'``.

    .. note::
       This is the legacy 3-class label. For full multi-dialect detection
       (8 Arabic dialects + English variants + code-switching), use
       :func:`app.ai.language_engine.detect_language_advanced` directly.
    """
    try:
        detection = detect_language_advanced(text)
        return detection.legacy_label
    except Exception:
        # Last-resort fallback: pure regex (identical to original impl)
        return _regex_detect_language(text)


def normalize_arabic(text: str) -> str:
    """Normalize Arabic text for better matching.

    Uses :func:`app.ai.language_engine.normalize_arabic_advanced` (which
    prefers camel_tools when available) and falls back to the original
    regex-based normalization on any error.
    """
    try:
        return normalize_arabic_advanced(text)
    except Exception:
        return _regex_normalize_arabic(text)


# ---------------------------------------------------------------------------
# Pure-regex fallbacks (used only if the new engine itself raises an error)
# ---------------------------------------------------------------------------


def _regex_detect_language(text: str) -> str:
    arabic_chars = len(re.findall(r"[\u0600-\u06FF]", text))
    latin_chars = len(re.findall(r"[a-zA-Z]", text))
    total = arabic_chars + latin_chars

    if total == 0:
        return "english"

    arabic_ratio = arabic_chars / total

    if arabic_ratio > 0.3:
        return "arabic"

    arabizi_patterns = [
        r"\bana\b", r"\benta\b", r"\benti\b", r"\behwa\b", r"\bhia\b",
        r"\byalla\b", r"\btayeb\b", r"\bkwayyes\b", r"\bshukran\b",
        r"\b3ayez\b", r"\b3ayza\b", r"\b3amel\b", r"\b3amla\b",
        r"\bye3ni\b", r"\byala\b", r"\bkeda\b", r"\bkeda\b",
        r"\bmish\b", r"\bmesh\b", r"\bfish\b", r"\bmafish\b",
        r"\bawy\b", r"\bawii\b", r"\bdeen\b", r"\byarab\b",
        r"\bhabibi\b", r"\bhabibti\b", r"\byasta\b", r"\bamr\b",
        r"\b3ndk\b", r"\b3ndy\b", r"\b3andi\b", r"\b3andak\b",
        r"\bkwys\b", r"\bkws\b", r"\bhag\b", r"\bhaga\b",
        r"\bsiller\b", r"\bprice\b", r"\bcost\b", r"\border\b",
        r"\bdelivery\b", r"\bship\b", r"\bavailable\b", r"\binstock\b",
        r"\b3o\b", r"\bwa7sh\b", r"\b2alb\b", r"\b5alas\b",
        r"\byebo3\b", r"\byeb3o\b", r"\byeshaghel\b", r"\byestakhdm\b",
        r"\bbta3\b", r"\bbta3ty\b", r"\bbta3ko\b", r"\bbta3ha\b",
        r"\banhy\b", r"\beh\b", r"\behda\b", r"\b2olly\b",
        r"\by3ni\b", r"\b3lshan\b", r"\bl2n\b", r"\b3shan\b",
        r"\b ya3ni\b", r"\b law 3ayez\b", r"\b mumken\b", r"\b momkn\b",
    ]

    arabizi_count = sum(
        1 for p in arabizi_patterns if re.search(p, text.lower())
    )

    if arabizi_count >= 2:
        return "arabizi"

    return "english"


def _regex_normalize_arabic(text: str) -> str:
    """Original regex-based normalization."""
    # Remove tashkeel (diacritics)
    text = re.sub(r"[\u0610-\u061A\u064B-\u065F\u0670]", "", text)
    # Normalize alef variants
    text = re.sub(r"[إأآا]", "ا", text)
    # Normalize taa marbuta
    text = re.sub(r"ة", "ه", text)
    # Normalize yaa
    text = re.sub(r"ى", "ي", text)
    return text.strip()
