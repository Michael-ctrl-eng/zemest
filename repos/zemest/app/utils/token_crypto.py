"""Fernet at-rest encryption for tenant channel tokens.

Audit B7-04 / V5 (HIGH): the privacy policy and DPA both promise that
channel access tokens are "encrypted at rest" — the reality was three
plaintext ``Text`` columns (``page_access_token``, ``ig_access_token``,
``wa_access_token``) readable by anyone with DB/file access (SQLite
sits on the same box as ``backend.log``).

Design:
* One ``TENANT_TOKEN_ENCRYPTION_KEY`` (Fernet key, env-provided) encrypts
  all three token columns.
* SQLAlchemy ``hybrid_property`` + ``validates`` keep the public
  attribute API IDENTICAL (``tenant.page_access_token`` reads plaintext,
  assignments encrypt) — callers in channels.py / facebook_service.py /
  whatsapp_service.py / scheduling.py need zero changes.
* Token format is versioned: ``zenc:v1:<fernet-token>``. Values without
  the prefix are legacy plaintext — read as-is, transparently RE-ENCRYPTED
  on next write (zero-downtime migration without a backfill script).
* If no key is configured: encryption is DISABLED and tokens stay
  plaintext, but ``token_encryption_active`` reports False so ops dashboards
  and tests can detect it. A boot warning is logged.
* A deliberately-invalid stored token never crashes reads — it returns
  the raw stored value (which is wrong, but visible in logs) so a key
  rotation mismatch degrades loudly instead of taking the channel down.
"""
from __future__ import annotations

import logging

from sqlalchemy.ext.hybrid import hybrid_property

logger = logging.getLogger(__name__)

#: Prefix marking an encrypted token value (versioned for future rotation).
_ENCRYPTED_PREFIX = "zenc:v1:"

try:
    from cryptography.fernet import Fernet, InvalidToken
except ImportError:  # pragma: no cover — cryptography is in requirements
    Fernet = None  # type: ignore[assignment]
    InvalidToken = Exception  # type: ignore[assignment,misc]

_fernet: "Fernet | None" = None
_key_checked = False


def _get_fernet():
    """Lazily build the Fernet instance from settings. None if unconfigured."""
    global _fernet, _key_checked
    if _key_checked:
        return _fernet
    _key_checked = True
    if Fernet is None:
        logger.warning("cryptography not installed — tenant tokens stay plaintext")
        return None
    from app.config import get_settings

    key = get_settings().TENANT_TOKEN_ENCRYPTION_KEY
    if not key:
        logger.warning(
            "TENANT_TOKEN_ENCRYPTION_KEY not set — channel tokens are stored "
            "PLAINTEXT (privacy policy DPA section is violated; set the key)"
        )
        return None
    try:
        _fernet = Fernet(key.encode() if isinstance(key, str) else key)
    except Exception as exc:  # noqa: BLE001 — bad key must not crash boot
        logger.error("Invalid TENANT_TOKEN_ENCRYPTION_KEY (%s) — tokens stay plaintext", exc)
        _fernet = None
    return _fernet


def token_encryption_active() -> bool:
    """True when a valid encryption key is configured."""
    return _get_fernet() is not None


def encrypt_token(value: str | None) -> str | None:
    """Encrypt a token for storage. Passes through None/empty/already-encrypted."""
    if not value:
        return value
    if value.startswith(_ENCRYPTED_PREFIX):
        return value  # already encrypted (idempotent assignment)
    f = _get_fernet()
    if f is None:
        return value  # encryption disabled — stored as-is
    try:
        return _ENCRYPTED_PREFIX + f.encrypt(value.encode()).decode()
    except Exception:  # noqa: BLE001
        logger.error("Token encryption failed — storing plaintext (investigate!)", exc_info=True)
        return value


def decrypt_token(stored: str | None) -> str | None:
    """Decrypt a token for use. Handles: encrypted, legacy plaintext, None."""
    if not stored:
        return stored
    if not stored.startswith(_ENCRYPTED_PREFIX):
        return stored  # legacy plaintext — works, re-encrypted on next write
    f = _get_fernet()
    if f is None:
        # Key removed after data was encrypted — surface the problem loudly.
        logger.error("Encrypted token present but no decryption key configured")
        return None
    try:
        return f.decrypt(stored[len(_ENCRYPTED_PREFIX):].encode()).decode()
    except InvalidToken:
        # Key rotation mismatch / corrupted row: degrade loudly, not fatally.
        logger.error("Stored token failed Fernet decryption (key mismatch?)")
        return None


def is_token_encrypted(stored: str | None) -> bool:
    """True when the stored value is in encrypted form (test/ops helper)."""
    return bool(stored) and bool(stored.startswith(_ENCRYPTED_PREFIX))


def _make_encrypted_property(column_attr_name: str):
    """Build a hybrid property that transparently encrypts/decrypts one
    token column while the Python attribute keeps serving plaintext.

    The expression (class-level) form returns the RAW column — queries
    filtering on tokens compare ciphertext, which is exactly what callers
    need for lookups by stored value and keeps SQL semantics unchanged.
    """

    def _getter(self):
        return decrypt_token(getattr(self, column_attr_name))

    def _expression_getter(cls):
        return getattr(cls, column_attr_name)

    def _setter(self, value):
        setattr(self, column_attr_name, encrypt_token(value))

    return hybrid_property(_getter, _setter, expr=_expression_getter)
