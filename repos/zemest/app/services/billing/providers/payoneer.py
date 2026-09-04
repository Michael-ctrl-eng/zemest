"""Payoneer provider — checkout collection + payouts (Egypt / worldwide).

Payoneer "for platforms" integration posture, fully env-parameterized:

* **Auth** — OAuth2 client_credentials: ``POST {base}/v1/oauth/token`` with
  HTTP Basic (client_id:client_secret). The access token is cached until
  ``expires_in``; a 401 on any call refreshes it once and retries.
* **Payouts** — ``POST {base}/v1/programs/{program_id}/payouts`` with
  ``{payee_id, amount, currency, client_reference_id}`` (our payout request
  id — the idempotency anchor Payoneer echoes back on status callbacks).
* **Webhooks** — Payoneer partner callbacks POST a JSON body to the
  ``callback_url`` configured in the partner portal; the signature header
  (default name ``X-Payoneer-Signature``) is an HMAC over the RAW body with
  the program's callback secret. Algorithm is program-configured →
  ``PAYONEER_WEBHOOK_ALGO`` (sha256 | sha512).

When the concrete Payoneer integration link/code is provided by the user,
THIS file is the single adapter to align (endpoint paths, header names,
payload field names) — nothing else in the billing stack changes. The
``payoneer-webhook-analyzer`` skill maps any real payload onto this client.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import time
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0)

TOKEN_PATH = "/v1/oauth/token"
PAYOUTS_PATH = "/v1/programs/{program_id}/payouts"
STATUS_PATH = "/v1/programs/{program_id}/payouts/{client_reference_id}"

DEFAULT_SIGNATURE_HEADER = "X-Payoneer-Signature"


class PayoneerError(Exception):
    def __init__(self, message: str, status_code: int = 0, body: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class PayoneerConfigError(PayoneerError):
    pass


_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=_TIMEOUT,
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )
    return _client


async def close_client() -> None:
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
    _client = None


# --------------------------------------------------------------------------- #
# Webhook verification — HMAC over the RAW body, fail closed
# --------------------------------------------------------------------------- #
def verify_webhook_signature(
    raw_body: bytes, signature: str, secret: str, algo: str = "sha256"
) -> bool:
    """Constant-time HMAC check of a Payoneer partner callback.

    ``signature`` is the hex digest delivered in the callback's signature
    header. Fails closed on empty secret / empty signature / algo mismatch
    (only sha256 and sha512 are accepted).
    """
    if not secret or not signature or not raw_body:
        return False
    algo = (algo or "sha256").lower()
    if algo not in ("sha256", "sha512"):
        return False
    digestmod = hashlib.sha256 if algo == "sha256" else hashlib.sha512
    expected = hmac.new(secret.encode("utf-8"), raw_body, digestmod).hexdigest()
    try:
        return hmac.compare_digest(expected.encode("ascii"), signature.encode("ascii"))
    except UnicodeEncodeError:
        return False


# --------------------------------------------------------------------------- #
# Client
# --------------------------------------------------------------------------- #
class PayoneerClient:
    """Payoneer partner/payout API client (token-cached, idempotent payouts)."""

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        program_id: str | None = None,
        base_url: str | None = None,
    ):
        s = get_settings()
        self.client_id = client_id if client_id is not None else s.PAYONEER_CLIENT_ID
        self.client_secret = (
            client_secret if client_secret is not None else s.PAYONEER_CLIENT_SECRET
        )
        self.program_id = program_id if program_id is not None else s.PAYONEER_PROGRAM_ID
        self.base_url = (base_url or s.PAYONEER_API_BASE or "").rstrip("/")
        self._token: str = ""
        self._token_expires_at: float = 0.0

    def configured(self) -> bool:
        return bool(self.client_id and self.client_secret and self.base_url)

    def payouts_configured(self) -> bool:
        return self.configured() and bool(self.program_id)

    # -- auth --------------------------------------------------------------
    async def _get_token(self, force_refresh: bool = False) -> str:
        if (
            not force_refresh
            and self._token
            and time.monotonic() < self._token_expires_at - 60
        ):
            return self._token
        if not self.configured():
            raise PayoneerConfigError(
                "Payoneer is not configured (PAYONEER_CLIENT_ID / CLIENT_SECRET / API_BASE)"
            )
        # httpx does the Basic auth encoding
        auth = (self.client_id, self.client_secret)
        data = {"grant_type": "client_credentials"}
        try:
            resp = await _get_client().post(
                f"{self.base_url}{TOKEN_PATH}", data=data, auth=auth
            )
        except httpx.HTTPError as e:
            raise PayoneerError(f"Payoneer token request failed: {e}") from e
        if resp.status_code >= 400:
            raise PayoneerError(
                f"Payoneer auth failed ({resp.status_code})", resp.status_code, resp.text[:2000]
            )
        try:
            payload = resp.json()
        except ValueError as e:
            raise PayoneerError("Invalid JSON from Payoneer token endpoint") from e
        self._token = str(payload.get("access_token") or "")
        expires_in = int(payload.get("expires_in") or 3600)
        self._token_expires_at = time.monotonic() + expires_in
        if not self._token:
            raise PayoneerError("Payoneer token response carried no access_token")
        return self._token

    async def _request(
        self, method: str, path: str, json_body: dict | None = None
    ) -> dict:
        token = await self._get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        url = f"{self.base_url}{path}"
        try:
            resp = await _get_client().request(
                method, url, headers=headers, json=json_body
            )
        except httpx.HTTPError as e:
            raise PayoneerError(f"Payoneer request failed: {e}") from e
        # One refresh-and-retry on auth expiry (token revoked server-side)
        if resp.status_code == 401:
            token = await self._get_token(force_refresh=True)
            headers["Authorization"] = f"Bearer {token}"
            try:
                resp = await _get_client().request(
                    method, url, headers=headers, json=json_body
                )
            except httpx.HTTPError as e:
                raise PayoneerError(f"Payoneer retry failed: {e}") from e
        if resp.status_code >= 400:
            raise PayoneerError(
                f"Payoneer API returned {resp.status_code}", resp.status_code, resp.text[:2000]
            )
        try:
            return resp.json()
        except ValueError:
            return {"raw": resp.text[:2000]}

    # -- payouts -----------------------------------------------------------
    async def send_payout(
        self,
        *,
        payee_id: str,
        amount: int,
        currency: str,
        client_reference_id: str,
        description: str = "Zemest merchant payout",
    ) -> dict:
        """Create a payout. ``client_reference_id`` = our payout request id
        (idempotency anchor — repeated calls with the same reference are
        answered with the existing payout, never a double send)."""
        if not self.payouts_configured():
            raise PayoneerConfigError("PAYONEER_PROGRAM_ID is not configured")
        path = PAYOUTS_PATH.format(program_id=self.program_id)
        body: dict[str, Any] = {
            "payee_id": payee_id,
            "amount": amount,
            "currency": currency,
            "client_reference_id": client_reference_id,
            "description": description[:200],
        }
        out = await self._request("POST", path, body)
        return {
            "provider_ref": str(out.get("payout_id") or out.get("id") or ""),
            "status": str(out.get("status") or "processing"),
            "raw": out,
        }

    async def payout_status(self, client_reference_id: str) -> dict:
        if not self.payouts_configured():
            raise PayoneerConfigError("PAYONEER_PROGRAM_ID is not configured")
        path = STATUS_PATH.format(
            program_id=self.program_id, client_reference_id=client_reference_id
        )
        out = await self._request("GET", path)
        return {
            "status": str(out.get("status") or ""),
            "provider_ref": str(out.get("payout_id") or out.get("id") or ""),
            "raw": out,
        }
