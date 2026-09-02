"""Paymob Intention API client + HMAC-SHA512 webhook verification.

Implements the integration plan from ``docs/PAYMENTS.md (content folded into the module docstrings)`` (the
authoritative spec for this integration):

* **Intention API only** — ``POST {base}/v1/intention/`` with
  ``Authorization: Token <secret key>``. The legacy 3-step flow
  (auth token → order → payment key) is deprecated and intentionally
  NOT implemented.
* **Amounts are sent in PIASTERS** (EGP × 100, integer) —
  1850.00 EGP → ``185000``. The single conversion point is
  :func:`to_piasters` so callers can never double-convert.
* **Webhook verification** — HMAC-SHA512 over the EXACT concatenated
  field order per event type (no separator, booleans as lowercase
  ``true``/``false``, missing values as empty string), compared with
  ``hmac.compare_digest`` (timing-safe, fail-closed).
* No maintained official/community Paymob Python SDK exists → hand-rolled
  REST client with a module-level pooled ``httpx.AsyncClient`` (same
  lifecycle pattern as ``app/ai/llm_client.py`` — one client per process,
  lazily created, ``close_client()`` on shutdown).

Env contract (``app/config.py``): ``PAYMOB_API_KEY`` (server secret key),
``PAYMOB_INTEGRATION_IDS`` (comma-separated payment-method ids),
``PAYMOB_WEBHOOK_HMAC_SECRET``, ``PAYMOB_BASE_URL``, ``PAYMOB_CURRENCY``.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Iterable

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

# Default Intention API base for the Egypt region (G1-payments.md; the
# legacy/global base https://accept.paymob.com also serves test-mode keys —
# override via PAYMOB_BASE_URL when needed).
DEFAULT_BASE_URL = "https://egypt.paymob.com"

INTENTION_PATH = "/v1/intention/"

# ---------------------------------------------------------------------------
# Shared pooled HTTP client (module-level, like app/ai/llm_client.py)
# ---------------------------------------------------------------------------
_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=5.0, read=25.0, write=10.0, pool=5.0),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )
    return _client


async def close_client() -> None:
    """Release pooled connections (call on app shutdown)."""
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
    _client = None


# ---------------------------------------------------------------------------
# Piaster math — the single conversion point
# ---------------------------------------------------------------------------
def to_piasters(amount_egp: Decimal | float | int | str) -> int:
    """Convert an EGP amount to integer piasters (× 100).

    1850.00 EGP → 185000. Uses Decimal (no float drift) and rounds
    half-up to the nearest piaster. Raises ValueError for garbage input.
    """
    try:
        d = amount_egp if isinstance(amount_egp, Decimal) else Decimal(str(amount_egp))
    except (InvalidOperation, ValueError, TypeError) as e:
        raise ValueError(f"cannot convert amount to piasters: {amount_egp!r}") from e
    return int((d * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


# ---------------------------------------------------------------------------
# HMAC-SHA512 webhook verification — EXACT field orders (G1-payments.md §3)
# ---------------------------------------------------------------------------
# Transaction callback: 20 fields concatenated in this exact order, no
# separator. NOTE: "error_occured" is Paymob's (sic) spelling — do NOT
# "fix" it to error_occurred or signatures stop matching.
TRANSACTION_HMAC_FIELDS: tuple[str, ...] = (
    "amount_cents",
    "created_at",
    "currency",
    "error_occured",  # sic — Paymob's actual field spelling
    "has_parent_transaction",
    "id",
    "integration_id",
    "is_3d_secure",
    "is_auth",
    "is_capture",
    "is_refunded",
    "is_standalone_payment",
    "is_voided",
    "order.id",
    "owner",
    "pending",
    "source_data.pan",
    "source_data.sub_type",
    "source_data.type",
    "success",
)

# Card-token (saved cards) callback: 8 fields in this exact order.
TOKEN_HMAC_FIELDS: tuple[str, ...] = (
    "card_subtype",
    "created_at",
    "email",
    "id",
    "masked_pan",
    "merchant_id",
    "order_id",
    "token",
)


def _field_value(obj: dict, dotted_key: str) -> str:
    """Extract one field (dotted path → nested dicts) rendered per spec:
    booleans as lowercase ``true``/``false``, None/missing as empty string,
    everything else as ``str(value)``.
    """
    cur: Any = obj
    for part in dotted_key.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            cur = None
            break
    return _render(cur)


def _render(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def build_hmac_message(obj: dict, fields: Iterable[str]) -> str:
    """Concatenate the given fields (in order, no separator) from ``obj``."""
    return "".join(_field_value(obj, f) for f in fields)


def _hmac_sha512_hex(message: str, secret: str) -> str:
    return hmac.new(
        secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha512
    ).hexdigest()


def _safe_digest_equals(expected_hex: str, received: str) -> bool:
    """Timing-safe compare that also tolerates non-ASCII junk input
    (hmac.compare_digest raises TypeError on non-ASCII str args)."""
    if not received or not expected_hex:
        return False
    try:
        return hmac.compare_digest(
            expected_hex.encode("ascii"), received.encode("ascii")
        )
    except UnicodeEncodeError:
        return False


def verify_transaction_hmac(obj: dict, received_hmac: str, secret: str) -> bool:
    """Verify a transaction webhook callback (20-field concatenation).

    Fails closed: empty signature or empty secret → False.
    """
    if not received_hmac or not secret:
        return False
    expected = _hmac_sha512_hex(build_hmac_message(obj, TRANSACTION_HMAC_FIELDS), secret)
    return _safe_digest_equals(expected, received_hmac)


def verify_token_hmac(obj: dict, received_hmac: str, secret: str) -> bool:
    """Verify a card-token (saved cards) callback (8-field concatenation)."""
    if not received_hmac or not secret:
        return False
    expected = _hmac_sha512_hex(build_hmac_message(obj, TOKEN_HMAC_FIELDS), secret)
    return _safe_digest_equals(expected, received_hmac)


def verify_subscription_hmac(obj: dict, received_hmac: str, secret: str) -> bool:
    """Verify a subscription callback.

    Message is the literal string ``"{trigger_type}for{subscription_data.id}"``
    (hmac delivered in the body rather than the query string).
    """
    if not received_hmac or not secret:
        return False
    message = (
        f"{_field_value(obj, 'trigger_type')}"
        f"for{_field_value(obj, 'subscription_data.id')}"
    )
    expected = _hmac_sha512_hex(message, secret)
    return _safe_digest_equals(expected, received_hmac)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------
class PaymobError(Exception):
    """Base class for Paymob integration errors."""


class PaymobConfigError(PaymobError):
    """Missing configuration (API key / integration ids)."""


class PaymobApiError(PaymobError):
    """Paymob API returned an error / transport failure."""

    def __init__(self, message: str, status_code: int = 0, body: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


# ---------------------------------------------------------------------------
# Intention payload builder (pure — unit-testable without HTTP)
# ---------------------------------------------------------------------------
def build_intention_payload(
    *,
    amount_egp: Decimal | float | int | str,
    billing_data: dict,
    merchant_order_id: str,
    payment_methods: list[int] | None = None,
    items: list[dict] | None = None,
    currency: str = "EGP",
    notification_url: str = "",
    redirection_url: str = "",
) -> dict:
    """Build the JSON body for ``POST /v1/intention/``.

    * ``amount`` is converted to integer PIASTERS via :func:`to_piasters`
      (1850.00 EGP → 185000).
    * ``merchant_order_id`` is sent as ``special_reference`` — Paymob echoes
      it back on every transaction webhook as ``order.merchant_order_id``,
      which is how we correlate callbacks to our orders.
    * ``items`` (optional) are passed through — item ``amount`` values must
      already be in piasters.
    * ``notification_url`` = our webhook endpoint (state changes happen ONLY
      there); ``redirection_url`` = browser UX redirect (never trusted).
    """
    payload: dict = {
        "amount": to_piasters(amount_egp),
        "currency": currency,
        "payment_methods": list(payment_methods or []),
        "billing_data": dict(billing_data),
        "special_reference": merchant_order_id,
    }
    if items:
        payload["items"] = list(items)
    if notification_url:
        payload["notification_url"] = notification_url
    if redirection_url:
        payload["redirection_url"] = redirection_url
    return payload


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------
class PaymobClient:
    """Thin async client for the Paymob Intention API.

    Configuration defaults come from settings (``PAYMOB_*``); every value
    can be overridden per instance (tests / future per-tenant credentials).
    Holds no connection state itself — all HTTP goes through the shared
    module-level ``httpx.AsyncClient``.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        integration_ids: str | list[int] | None = None,
        currency: str | None = None,
        hmac_secret: str | None = None,
    ):
        s = get_settings()
        self.api_key = api_key if api_key is not None else s.PAYMOB_API_KEY
        self.base_url = (base_url or s.PAYMOB_BASE_URL or DEFAULT_BASE_URL).rstrip("/")
        self.currency = currency or s.PAYMOB_CURRENCY or "EGP"
        self.hmac_secret = (
            hmac_secret if hmac_secret is not None else s.PAYMOB_WEBHOOK_HMAC_SECRET
        )
        raw_ids = integration_ids if integration_ids is not None else s.PAYMOB_INTEGRATION_IDS
        if isinstance(raw_ids, str):
            self.integration_ids = [
                int(x) for x in raw_ids.replace(" ", "").split(",") if x
            ]
        else:
            self.integration_ids = list(raw_ids or [])

    async def create_intention(
        self,
        *,
        amount_egp: Decimal | float | int | str,
        billing_data: dict,
        merchant_order_id: str,
        payment_methods: list[int] | None = None,
        items: list[dict] | None = None,
        notification_url: str = "",
        redirection_url: str = "",
        public_key: str = "",
    ) -> dict:
        """Create a Paymob Intention and return a normalized dict:

        ``{"intention_id", "client_secret", "payment_url", "raw"}``

        ``amount_egp`` is converted to piasters exactly once (here).
        ``public_key`` (frontend-safe, optional) is used to build the
        unified-checkout URL when Paymob's response does not carry one.
        Raises :class:`PaymobConfigError` / :class:`PaymobApiError`.
        """
        if not self.api_key:
            raise PaymobConfigError("Paymob API key is not configured (PAYMOB_API_KEY)")
        methods = payment_methods if payment_methods is not None else self.integration_ids
        if not methods:
            raise PaymobConfigError(
                "No Paymob payment methods configured (PAYMOB_INTEGRATION_IDS)"
            )

        payload = build_intention_payload(
            amount_egp=amount_egp,
            billing_data=billing_data,
            merchant_order_id=merchant_order_id,
            payment_methods=methods,
            items=items,
            currency=self.currency,
            notification_url=notification_url,
            redirection_url=redirection_url,
        )
        url = f"{self.base_url}{INTENTION_PATH}"
        headers = {"Authorization": f"Token {self.api_key}"}
        try:
            resp = await _get_client().post(url, json=payload, headers=headers)
        except httpx.TimeoutException as e:
            raise PaymobApiError(f"Paymob intention request timed out: {e}") from e
        except httpx.HTTPError as e:
            raise PaymobApiError(f"Paymob connection error: {e}") from e

        body_text = resp.text[:2000]
        if resp.status_code >= 400:
            logger.warning(
                "Paymob intention API error %s: %s", resp.status_code, body_text
            )
            raise PaymobApiError(
                f"Paymob intention API returned {resp.status_code}",
                status_code=resp.status_code,
                body=body_text,
            )
        try:
            data = resp.json()
        except ValueError as e:
            raise PaymobApiError(
                "Invalid JSON in Paymob response", resp.status_code, body_text
            ) from e
        logger.info("Paymob intention created (ref=%s)", merchant_order_id)
        return self._normalize_intention(data, public_key)

    def _normalize_intention(self, data: dict, public_key: str = "") -> dict:
        intention_id = str(data.get("id") or data.get("intention_id") or "")
        client_secret = str(data.get("client_secret") or "")
        payment_url = ""
        for key in (
            "payment_url",
            "checkout_url",
            "unified_checkout_url",
            "redirection_url",
            "redirect_url",
        ):
            val = data.get(key)
            if val:
                payment_url = str(val)
                break
        if not payment_url and client_secret and public_key:
            payment_url = (
                f"{self.base_url}/unifiedcheckout/"
                f"?publicKey={public_key}&clientSecret={client_secret}"
            )
        return {
            "intention_id": intention_id,
            "client_secret": client_secret,
            "payment_url": payment_url,
            "raw": data,
        }
