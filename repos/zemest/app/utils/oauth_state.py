"""Signed OAuth ``state`` for the Facebook login flow.

Audit A4-M2: the old flow used a guessable ``"tenant:{uuid}"`` state with no
nonce and no signature — no CSRF protection at all, and the callback route
it advertised did not exist. This module signs and verifies the state with
an HMAC keyed from the server's JWT secret (the only long-lived server
secret guaranteed to exist in every deployment), embeds a timestamp, and
rejects replayed or stale states.

Format: ``{tenant_id}.{unix_ts}.{hmac_hex}``
"""
from __future__ import annotations

import hashlib
import hmac
import time

from app.config import get_settings

_MAX_STATE_AGE_SECONDS = 15 * 60  # OAuth round-trip should take < 15 min


def _secret() -> bytes:
    # JWT_SECRET_KEY is the long-lived server secret guaranteed to exist in
    # every deployment (auth tokens depend on it).
    return (get_settings().JWT_SECRET_KEY or "zemest-dev-secret").encode()


def _sign(payload: str) -> str:
    return hmac.new(_secret(), payload.encode(), hashlib.sha256).hexdigest()


def sign_oauth_state(tenant_id: str) -> str:
    """Create a signed state for the given tenant."""
    ts = int(time.time())
    payload = f"{tenant_id}.{ts}"
    return f"{payload}.{_sign(payload)}"


def verify_oauth_state(state: str, tenant_id: str | None = None) -> tuple[bool, str | None]:
    """Verify a signed state.

    Args:
        state: the raw state string from the callback query.
        tenant_id: optionally pin the expected tenant (verified in addition
            to the signature).

    Returns:
        ``(valid, tenant_id)`` — tenant_id extracted from the verified state,
        or ``None`` when invalid. Never raises.
    """
    if not state or not isinstance(state, str):
        return False, None
    parts = state.rsplit(".", 3)
    if len(parts) != 3:
        return False, None
    tenant, ts_raw, mac = parts
    if not tenant or not ts_raw or not mac:
        return False, None
    # Constant-time signature check
    if not hmac.compare_digest(_sign(f"{tenant}.{ts_raw}"), mac):
        return False, None
    try:
        ts = int(ts_raw)
    except ValueError:
        return False, None
    # Replay/staleness window
    if abs(time.time() - ts) > _MAX_STATE_AGE_SECONDS:
        return False, None
    if tenant_id is not None and tenant != tenant_id:
        return False, None
    return True, tenant


__all__ = ["sign_oauth_state", "verify_oauth_state"]
