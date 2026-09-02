"""PII redaction for LLM-bound text (audit A6-H5).

Egyptian commerce messages routinely contain phone numbers, emails and
addresses. Before any customer-derived text is sent to a third-party LLM
(style learning, silent training, blog drafting), it passes through
``redact_pii`` so merchant/buyer PII never leaves the trust boundary in
cleartext.

Design:
- Pure regex, linear time, never raises.
- Egyptian mobile numbers (01x / +201x), international-style +NN runs and
  any long digit run (>= 7 digits: order IDs, tracking codes, national IDs).
- E-mails → ``[EMAIL]``. Phones → ``[PHONE]``. Long digit runs → ``[NUMBER]``.
- Words that merely *contain* digits mixed with letters (sizes, "3ayez")
  are untouched — only standalone numeric tokens are masked.
"""
from __future__ import annotations

import re

# Egyptian mobile: optional +20 / 0020 / 20 prefix, 01[0125] + 8 digits.
_EG_PHONE_RE = re.compile(
    r"(?<!\d)(?:\+?2?0?2?01[0125]\d{8})(?!\d)"
)

# International numbers: + followed by 7-15 digits.
_INTL_PHONE_RE = re.compile(r"(?<!\d)\+\d{7,15}(?!\d)")

# Standalone long digit runs (order IDs, national IDs, tracking codes, card
# numbers) — Arabic-Indic digits included.
_LONG_DIGIT_RE = re.compile(r"(?<![\d٠-٩])[\d٠-٩]{7,}(?![\d٠-٩])")

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def redact_pii(text: str | None) -> str:
    """Redact obvious PII from ``text``. Never raises; returns ``""`` for falsy.

    >>> redact_pii("كلمني على 01012345678")
    'كلمني على [PHONE]'
    >>> redact_pii("email me at buyer@gmail.com please")
    'email me at [EMAIL] please'
    """
    if not text or not isinstance(text, str):
        return ""

    out = text
    out = _EMAIL_RE.sub("[EMAIL]", out)
    out = _EG_PHONE_RE.sub("[PHONE]", out)
    out = _INTL_PHONE_RE.sub("[PHONE]", out)
    out = _LONG_DIGIT_RE.sub("[NUMBER]", out)
    return out


__all__ = ["redact_pii"]
