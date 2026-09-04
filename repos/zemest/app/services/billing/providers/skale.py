"""SKALE Network payout rail — calls the ethers.js sidecar mini-service.

The sidecar (``mini-services/skale-payout`` at the repo root) is a tiny
Node.js service that holds the payout wallet key SERVER-SIDE-ONLY and sends
USDC (ERC-20, 6 decimals) or the native chain token on the SKALE Network
(Europa chain — EVM-compatible, gas-free). The Python backend never touches
a private key; it authorizes each transfer with an HMAC-SHA256 signature
over the exact JSON body it sends:

    X-Signature: hex(HMAC_SHA256(raw_request_body, SKALE_PAYOUT_HMAC_SECRET))

The sidecar verifies the same way (constant-time) and enforces its own
idempotency on ``idempotency_key`` — a replayed payout request can never
double-send. This module is the Python half: sign, send, verify response.
"""
from __future__ import annotations

import hashlib
import hmac
import logging

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(connect=5.0, read=60.0, write=10.0, pool=5.0)

_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=_TIMEOUT,
            limits=httpx.Limits(max_connections=4, max_keepalive_connections=2),
        )
    return _client


async def close_client() -> None:
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
    _client = None


class SkalePayoutError(Exception):
    pass


def sign_body(raw_body: bytes, secret: str) -> str:
    """Hex HMAC-SHA256 over the raw request body (mirrors the sidecar)."""
    if not secret:
        raise SkalePayoutError("SKALE_PAYOUT_HMAC_SECRET is not configured")
    return hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()


def valid_eth_address(address: str) -> bool:
    """Cheap EVM address shape check (0x + 40 hex) — chain-agnostic sanity."""
    if not isinstance(address, str) or not address.startswith("0x") or len(address) != 42:
        return False
    try:
        int(address[2:], 16)
        return True
    except ValueError:
        return False


async def send_payout(
    *,
    to: str,
    amount: str,
    token: str = "usdc",
    idempotency_key: str,
) -> dict:
    """Send one payout through the sidecar.

    ``amount`` is a decimal string in whole units (e.g. "12.50"); the
    sidecar parses to the token's smallest unit (USDC → 6 decimals).
    Returns ``{"tx_hash", "status"}``.
    """
    s = get_settings()
    if not s.SKALE_PAYOUT_HMAC_SECRET:
        raise SkalePayoutError("SKALE_PAYOUT_HMAC_SECRET is not configured")
    if not valid_eth_address(to):
        raise SkalePayoutError(f"invalid destination wallet address: {to!r}")
    if token not in ("usdc", "native"):
        raise SkalePayoutError(f"unsupported token rail: {token!r}")

    import json as _json

    body = {
        "to": to,
        "amount": str(amount),
        "token": token,
        "idempotency_key": idempotency_key,
    }
    raw = _json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "X-Signature": sign_body(raw, s.SKALE_PAYOUT_HMAC_SECRET),
    }
    url = f"{s.SKALE_PAYOUT_URL.rstrip('/')}/payout"
    try:
        resp = await _get_client().post(url, content=raw, headers=headers)
    except httpx.HTTPError as e:
        raise SkalePayoutError(f"SKALE sidecar unreachable: {e}") from e
    if resp.status_code >= 400:
        raise SkalePayoutError(
            f"SKALE sidecar returned {resp.status_code}: {resp.text[:300]}"
        )
    try:
        out = resp.json()
    except ValueError as e:
        raise SkalePayoutError("invalid JSON from SKALE sidecar") from e
    return {"tx_hash": str(out.get("tx_hash") or ""), "status": str(out.get("status") or "sent")}


async def health() -> dict:
    s = get_settings()
    try:
        resp = await _get_client().get(f"{s.SKALE_PAYOUT_URL.rstrip('/')}/health", timeout=10.0)
        if resp.status_code != 200:
            return {"ok": False, "status": resp.status_code}
        return {"ok": True, **resp.json()}
    except httpx.HTTPError as e:
        return {"ok": False, "error": str(e)}
