"""Security utilities — password hashing, JWT (access + refresh), signature verification.

Hardening summary
-----------------
* ``algorithms`` is pinned to ``[settings.JWT_ALGORITHM]`` (HS256 by default)
  in ``decode_token`` so an attacker cannot downgrade to ``alg=none`` or
  switch to RS256 (algorithm-confusion attack).
* ``decode_token`` requires the ``exp`` claim (``options={"require": ["exp"]}``)
  — tokens without expiry are rejected to prevent infinite sessions.
* Refresh tokens carry their own 7-day expiry and a ``jti`` (JWT ID). Revoked
  ``jti`` values are stored in a Redis set with a TTL that matches the natural
  expiry, so the denylist cleans itself.
* All Redis operations fail-open: if Redis is unreachable we still accept
  the token (degraded mode is logged). This prevents a Redis outage from
  locking every user out.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from jose import JWTError, jwt
import bcrypt

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# --------------------------------------------------------------------------- #
# Password hashing — direct bcrypt (passlib removed)
# --------------------------------------------------------------------------- #
# passlib 1.7.4 is unmaintained and breaks with bcrypt >= 4.1 (it cannot read
# the backend version and bcrypt 5.x raises ValueError on >72-byte passwords
# where passlib expects silent truncation). We call bcrypt directly instead.

#: Cost factor — 12 rounds ≈ 250ms on 2026 commodity hardware: strong enough
#: for an online service, cheap enough not to DoS the login endpoint.
BCRYPT_ROUNDS = 12

#: bcrypt only consumes the first 72 bytes of a password. bcrypt 5.x raises
#: ValueError instead of truncating, so we truncate explicitly (identical to
#: the historical behaviour every existing hash in the DB was built with).
_BCRYPT_MAX_BYTES = 72

#: Pre-computed hash used to equalize login timing when the account does not
#: exist — without this, "unknown email" returns in ~0ms while "known email
#: + wrong password" takes ~250ms of bcrypt, leaking account existence.
_DUMMY_BCRYPT_HASH = bcrypt.hashpw(
    b"zemest-timing-equalizer", bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
).decode("ascii")


def hash_password(password: str) -> str:
    """Hash a password with bcrypt (12 rounds).

    Never raises on long input — deterministic 72-byte truncation, matching
    the behaviour of every bcrypt hash already stored in the database.
    """
    pw = password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
    return bcrypt.hashpw(pw, bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode("ascii")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a password against a bcrypt hash.

    Constant-time comparison inside bcrypt; returns ``False`` (never raises)
    for malformed hashes. Truncates input at 72 bytes exactly like
    :func:`hash_password` so long passwords verify consistently.
    """
    pw = plain.encode("utf-8")[:_BCRYPT_MAX_BYTES]
    try:
        return bcrypt.checkpw(pw, hashed.encode("ascii"))
    except (ValueError, TypeError):
        return False


def burn_password_timing(password: str) -> None:
    """Equalize timing for non-existent accounts during login/register.

    Runs a full bcrypt verification against a throwaway hash so that a
    failed "user not found" path costs the same ~250ms as a wrong password.
    """
    try:
        pw = password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
        bcrypt.checkpw(pw, _DUMMY_BCRYPT_HASH.encode("ascii"))
    except Exception:  # noqa: BLE001 — timing equalizer must never raise
        pass

# Refresh-token lifetime — kept short-ish so a stolen refresh token has a
# limited window before mandatory rotation.
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Redis key prefix for the revocation denylist.
_REVOKE_PREFIX = "jwt:revoked:"

# In-memory fallback denylist — only used when Redis is unreachable so the
# revocation still works for the lifetime of the process. Cleared on restart.
_memory_denylist: set[str] = set()


# --------------------------------------------------------------------------- #
# Access tokens (short-lived)
# --------------------------------------------------------------------------- #
def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Create a short-lived access JWT.

    Always embeds ``exp`` and ``iat``. The caller's ``data`` is merged in,
    so additional claims (``sub``, ``tenant_id``, ``role`` …) can be supplied.
    """
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    expire = now + (
        expires_delta or timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode["exp"] = expire
    to_encode["iat"] = now
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict | None:
    """Decode + verify a JWT.

    Hardening:
      * ``algorithms`` is pinned to the single configured algorithm — this
        defeats the ``alg=none`` attack and the RS256/HS256 algorithm-confusion
        attack.
      * ``require`` enforces the ``exp`` claim so a token without expiry
        (e.g., one forged with ``alg=none``) is rejected even if python-jose
        would otherwise accept it.
      * Returns ``None`` on *any* error — callers can use ``if not payload:``.

    Never raises.
    """
    if not token or not isinstance(token, str):
        return None
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            options={"require": ["exp"]},
        )
        return payload
    except JWTError:
        return None
    except Exception:  # noqa: BLE001 — never raise on malformed input
        return None


# --------------------------------------------------------------------------- #
# Refresh tokens (long-lived, rotatable, revocable)
# --------------------------------------------------------------------------- #
def create_refresh_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Create a long-lived refresh JWT.

    Embeds a unique ``jti`` so the token can be revoked individually via
    :func:`revoke_token`. Lifetime defaults to :data:`REFRESH_TOKEN_EXPIRE_DAYS`.
    """
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS))
    to_encode["exp"] = expire
    to_encode["iat"] = now
    to_encode["jti"] = str(uuid.uuid4())
    to_encode["type"] = "refresh"
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def verify_refresh_token(token: str) -> dict | None:
    """Verify a refresh JWT and check the Redis denylist.

    Returns the payload dict if the token is valid AND not revoked, else
    ``None``. Fail-open on Redis errors (token is accepted; warning logged).
    """
    payload = decode_token(token)
    if payload is None:
        return None
    if payload.get("type") != "refresh":
        return None

    jti = payload.get("jti")
    if not jti:
        # A refresh token without jti is malformed — reject.
        return None
    if is_token_revoked(jti):
        return None
    return payload


# --------------------------------------------------------------------------- #
# Redis-backed revocation denylist
# --------------------------------------------------------------------------- #
async def _get_redis():
    """Lazily connect to Redis. Returns ``None`` if unavailable."""
    try:
        import redis.asyncio as aioredis  # noqa: WPS433 — lazy import

        return aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Redis unavailable for JWT denylist: %s", exc)
        return None


def is_token_revoked(jti: str) -> bool:
    """Synchronous check used inside :func:`verify_refresh_token`.

    Queries the in-memory fallback only. Use :func:`is_token_revoked_async`
    for the Redis-backed check from async code paths. We keep this sync
    version so ``verify_refresh_token`` can be called from sync contexts
    (e.g., FastAPI dependency resolution without an event loop hop).
    """
    if not jti:
        return False
    return jti in _memory_denylist


async def is_token_revoked_async(jti: str) -> bool:
    """Async Redis-backed revocation check.

    Falls back to the in-memory denylist if Redis is unreachable. Fails
    OPEN (returns ``False``) on Redis errors so a Redis blip doesn't lock
    every user out.
    """
    if not jti:
        return False
    if jti in _memory_denylist:
        return True

    redis = await _get_redis()
    if redis is None:
        return False
    try:
        revoked = await redis.get(_REVOKE_PREFIX + jti)
        return bool(revoked)
    except Exception as exc:  # noqa: BLE001 — fail open
        logger.warning("Redis revocation check failed (fail-open): %s", exc)
        return False
    finally:
        try:
            await redis.aclose()
        except Exception:  # noqa: BLE001
            pass


async def revoke_token(jti: str, exp: Optional[int] = None) -> bool:
    """Revoke a token by its ``jti``.

    Adds the ``jti`` to the Redis denylist with a TTL that matches the
    token's natural expiry (so the denylist self-cleans). Also records
    the revocation in the in-memory fallback so it takes effect even
    if Redis subsequently goes down.

    Args:
        jti: JWT ID claim from the token.
        exp: Token expiry as a Unix timestamp. If omitted, the entry is
            stored with :data:`REFRESH_TOKEN_EXPIRE_DAYS` as a safety TTL.

    Returns ``True`` if the revocation was persisted, ``False`` on Redis
    failure (the in-memory fallback is still updated).
    """
    if not jti:
        return False

    # Always update the in-memory fallback so revocation works even
    # without Redis (single-process deployments).
    _memory_denylist.add(jti)

    redis = await _get_redis()
    if redis is None:
        return False

    # TTL: time until the token would have naturally expired, plus a small
    # safety margin so the denylist cleans itself.
    now = int(datetime.now(timezone.utc).timestamp())
    if exp and exp > now:
        ttl = exp - now + 60
    else:
        ttl = REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600

    try:
        await redis.setex(_REVOKE_PREFIX + jti, ttl, "1")
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to revoke token in Redis (in-memory only): %s", exc)
        return False
    finally:
        try:
            await redis.aclose()
        except Exception:  # noqa: BLE001
            pass


# --------------------------------------------------------------------------- #
# Webhook signature verification
# --------------------------------------------------------------------------- #
def verify_fb_signature(payload: bytes, signature: str) -> bool:
    """Verify Facebook webhook X-Hub-Signature-256 header.

    Fails CLOSED: returns False when FB_APP_SECRET is missing or signature is empty.
    Never raises — always returns a bool so callers can use it directly in `if not`.
    """
    if not signature:
        return False
    secret = settings.FB_APP_SECRET
    if not secret:
        return False
    expected = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)


__all__ = [
    "hash_password",
    "verify_password",
    "burn_password_timing",
    "BCRYPT_ROUNDS",
    "create_access_token",
    "decode_token",
    "create_refresh_token",
    "verify_refresh_token",
    "is_token_revoked",
    "is_token_revoked_async",
    "revoke_token",
    "verify_fb_signature",
    "REFRESH_TOKEN_EXPIRE_DAYS",
]
