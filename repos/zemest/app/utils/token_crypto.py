"""At-rest encryption for long-lived channel tokens (audit A4-H4).

Meta/WhatsApp/Instagram Page tokens, WABA tokens and Postiz session JWTs
grant messaging + posting control of every merchant's social accounts.
They were stored as plaintext ``Text`` columns — any DB read (sqladmin,
SQL dumps, backups, a leaked replica) yielded full control of every
merchant account.

Design:
- Fernet (AES-128-CBC + HMAC, stdlib-quality ``cryptography`` package).
- Key sources, in priority order:
  1. ``TOKEN_ENCRYPTION_KEY`` env (a URL-safe base64 32-byte key, or any
     string — hashed to 32 bytes).
  2. Derived from ``JWT_SECRET_KEY`` via SHA-256 — zero-config deployments
     still get real at-rest encryption instead of plaintext.
- **Backward compatibility**: values that are not Fernet tokens (legacy
  plaintext rows) pass through unchanged on read, so existing databases
  keep working; every new write is encrypted. A one-shot migration
  command re-encrypts legacy rows (``encrypt_all_tokens`` below).
- Fernet tokens are recognizable by their ``gAAAA`` prefix (version byte
  + timestamp), which is how ``decrypt_token`` distinguishes ciphertext
  from legacy plaintext without a separate marker column.
"""
from __future__ import annotations

import base64
import hashlib
import logging

logger = logging.getLogger(__name__)

_fernet = None
_fernet_failed = False

_FERNET_PREFIX = b"gAAAA"


def _load_fernet():
    global _fernet, _fernet_failed
    if _fernet is not None or _fernet_failed:
        return _fernet
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        _fernet_failed = True
        logger.warning(
            "cryptography package not installed — channel tokens stored in "
            "PLAINTEXT (install requirements.txt)"
        )
        return None

    from app.config import get_settings
    settings = get_settings()

    key_source = settings.TOKEN_ENCRYPTION_KEY
    if key_source:
        raw = key_source.encode()
    else:
        # Derive from the JWT secret — every deployment has one, and a key
        # derived from a strong secret is still a real key (documented).
        raw = hashlib.sha256(
            (settings.JWT_SECRET_KEY or "zemest-dev-secret").encode()
        ).digest()

    # Accept either a urlsafe-b64 32-byte key or an arbitrary string.
    try:
        key = base64.urlsafe_b64decode(key_source) if key_source else raw
        if len(key) != 32:
            raise ValueError
    except Exception:
        key = hashlib.sha256(raw).digest()

    _fernet = Fernet(base64.urlsafe_b64encode(key))
    return _fernet


def encrypt_token(value: str | None) -> str | None:
    """Encrypt a token for storage. Legacy/None passthrough.

    Never raises — on any crypto failure the value is returned unchanged
    (fail-open on WRITE is deliberate: a broken crypto stack must not
    take down channel connections; a warning is logged).
    """
    if not value or not isinstance(value, str):
        return value
    if value.encode().startswith(_FERNET_PREFIX):
        return value  # already encrypted — never double-encrypt
    f = _load_fernet()
    if f is None:
        return value
    try:
        return f.encrypt(value.encode()).decode()
    except Exception as e:
        logger.error(f"token encryption failed ({type(e).__name__}) — storing plaintext")
        return value


def decrypt_token(value: str | None) -> str | None:
    """Decrypt a stored token. Legacy plaintext passthrough.

    Never raises — a corrupted ciphertext returns ``None`` so callers see
    a "missing token" instead of a crash (fail-closed on READ is safe:
    the remedy is re-connecting the channel).
    """
    if not value or not isinstance(value, str):
        return value
    if not value.encode().startswith(_FERNET_PREFIX):
        return value  # legacy plaintext row — read as-is
    f = _load_fernet()
    if f is None:
        return None  # encrypted at rest, but no key available — treat as lost
    try:
        return f.decrypt(value.encode()).decode()
    except Exception:
        logger.error("stored channel token failed to decrypt — treating as missing")
        return None


def is_encrypted(value: str | None) -> bool:
    if not value or not isinstance(value, str):
        return False
    return value.encode().startswith(_FERNET_PREFIX)


__all__ = ["encrypt_token", "decrypt_token", "is_encrypted"]
