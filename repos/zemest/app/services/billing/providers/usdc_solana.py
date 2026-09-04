"""USDC-Solana provider — the crypto rail (direct JSON-RPC, no sidecar).

Design contract (direct-rail billing architecture):

* The backend talks DIRECTLY to a Solana JSON-RPC endpoint over the same
  pooled ``httpx.AsyncClient`` pattern used by every other provider —
  there is NO sidecar service, NO partner-chain dependency, and NO
  third-party custodian in the request path.
* **No private keys ever.** This module is read-only against the chain:
  it monitors the platform treasury wallet for incoming USDC (SPL token)
  transfers and verifies executed payouts. Signing transactions is the
  operator's job (bank portal / hardware wallet); the app reconciles.
* A tiny vendored base58 codec keeps the dependency surface at zero —
  no ``solders``/``solana-py`` needed for read paths.

Payment matching (how an on-chain transfer becomes a paid invoice):

1. Payer sends ``amount`` USDC to ``USDC_TREASURY_WALLET`` with the
   invoice's ``solana_reference`` in an spl-memo (the reference is a
   high-entropy token, so accidental collision is negligible).
2. ``find_deposits()`` sweeps recent signatures on the treasury's USDC
   token account, parses ``preTokenBalances``/``postTokenBalances`` for
   the USDC mint, and returns normalized deposits (micro-USDC deltas).
3. The subscription engine matches deposits to pending invoices by
   memo reference first, exact amount second (within a micro-USDC
   tolerance), requiring ``USDC_CONFIRMATIONS_REQUIRED`` confirmations.

Env contract (``app/config.py``): ``SOLANA_RPC_URL``,
``SOLANA_RPC_API_TOKEN``, ``USDC_MINT_ADDRESS``, ``USDC_TREASURY_WALLET``,
``USDC_CONFIRMATIONS_REQUIRED``, ``USDC_SCAN_LIMIT``,
``USDC_AMOUNT_TOLERANCE``.
"""
from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

import httpx

from app.config import get_settings
from app.services.billing.providers.base import (
    CheckoutResult,
    PaymentProvider,
    ProviderApiError,
    ProviderConfigError,
)

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Vendored base58 (Bitcoin alphabet) — the only chain primitive we need
# --------------------------------------------------------------------------- #
_B58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_B58_INDEX = {char: idx for idx, char in enumerate(_B58_ALPHABET)}


def b58encode(data: bytes) -> str:
    """Encode bytes to a base58 string (Solana address/signature format)."""
    num = int.from_bytes(data, "big")
    encoded = ""
    while num > 0:
        num, rem = divmod(num, 58)
        encoded = _B58_ALPHABET[rem] + encoded
    # Leading zero bytes become leading '1's.
    pad = 0
    for byte in data:
        if byte == 0:
            pad += 1
        else:
            break
    return "1" * pad + encoded


def b58decode(text: str) -> bytes:
    """Decode a base58 string to bytes; raises ValueError on bad input."""
    num = 0
    for char in text:
        if char not in _B58_INDEX:
            raise ValueError(f"invalid base58 character: {char!r}")
        num = num * 58 + _B58_INDEX[char]
    # Count leading '1's for zero padding.
    pad = 0
    for char in text:
        if char == "1":
            pad += 1
        else:
            break
    body = num.to_bytes((num.bit_length() + 7) // 8, "big") if num else b""
    return b"\x00" * pad + body


# --------------------------------------------------------------------------- #
# Shared pooled HTTP client
# --------------------------------------------------------------------------- #
_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )
    return _client


async def close_client() -> None:
    """Release pooled connections (call on app shutdown)."""
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
    _client = None


# --------------------------------------------------------------------------- #
# Deposit record
# --------------------------------------------------------------------------- #
def new_solana_reference() -> str:
    """Fresh high-entropy memo reference for one invoice.

    Two words from a URL-safe token — short enough for a memo, unique
    enough that guessing is hopeless (64 bits+ of entropy).
    """
    return f"zm-{secrets.token_urlsafe(12)}"


class Deposit(dict):
    """Normalized on-chain deposit (dict for easy serialization in tests)."""


# --------------------------------------------------------------------------- #
# Provider
# --------------------------------------------------------------------------- #
class UsdcSolanaProvider(PaymentProvider):
    """Crypto rail — USDC (SPL) on Solana, read-only chain access."""

    name = "usdc_solana"

    def __init__(
        self,
        rpc_url: str | None = None,
        rpc_api_token: str | None = None,
        mint: str | None = None,
        treasury_wallet: str | None = None,
        confirmations_required: int | None = None,
        scan_limit: int | None = None,
        amount_tolerance: int | None = None,
    ):
        s = get_settings()
        self.rpc_url = (rpc_url or s.SOLANA_RPC_URL or "https://api.mainnet-beta.solana.com").rstrip("/")
        self.rpc_api_token = (
            rpc_api_token if rpc_api_token is not None else s.SOLANA_RPC_API_TOKEN
        )
        self.mint = mint or s.USDC_MINT_ADDRESS
        self.treasury_wallet = (
            treasury_wallet if treasury_wallet is not None else s.USDC_TREASURY_WALLET
        )
        self.confirmations_required = (
            confirmations_required
            if confirmations_required is not None
            else s.USDC_CONFIRMATIONS_REQUIRED
        )
        self.scan_limit = scan_limit if scan_limit is not None else s.USDC_SCAN_LIMIT
        self.amount_tolerance = (
            amount_tolerance
            if amount_tolerance is not None
            else s.USDC_AMOUNT_TOLERANCE
        )

    def is_configured(self) -> bool:
        return bool(self.treasury_wallet and self.mint and self.rpc_url)

    # -- JSON-RPC core ------------------------------------------------------ #
    async def _rpc(self, method: str, params: list) -> Any:
        """POST one JSON-RPC request; raises ProviderApiError on transport
        or JSON-RPC-level error (result-level ``err`` is the CALLER's to
        interpret — Solana embeds per-signature errors in results)."""
        url = self.rpc_url
        if self.rpc_api_token:
            url = f"{url}?api-token={self.rpc_api_token}"
        body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        try:
            resp = await _get_client().post(url, json=body)
        except httpx.TimeoutException as e:
            raise ProviderApiError(f"Solana RPC timeout ({method}): {e}") from e
        except httpx.HTTPError as e:
            raise ProviderApiError(f"Solana RPC connection error ({method}): {e}") from e
        if resp.status_code >= 400:
            raise ProviderApiError(
                f"Solana RPC returned HTTP {resp.status_code} ({method})",
                status_code=resp.status_code,
                body=resp.text[:2000],
            )
        try:
            data = resp.json()
        except ValueError as e:
            raise ProviderApiError(f"Invalid JSON from Solana RPC ({method})") from e
        if "error" in data:
            err = data["error"]
            raise ProviderApiError(
                f"Solana RPC error ({method}): {err.get('message', err)}",
                body=str(err)[:2000],
            )
        return data.get("result")

    # -- address helpers ---------------------------------------------------- #
    def validate_treasury_wallet(self) -> bool:
        """A valid Solana pubkey decodes to exactly 32 bytes."""
        try:
            return len(b58decode(self.treasury_wallet)) == 32
        except (ValueError, TypeError):
            return False

    async def get_treasury_token_account(self) -> str | None:
        """Resolve the treasury wallet's USDC associated token account.

        Returns None when the wallet holds no USDC account yet (fresh
        treasury → nothing to sweep, balance 0).
        """
        if not self.treasury_wallet:
            raise ProviderConfigError("USDC_TREASURY_WALLET is not configured")
        result = await self._rpc(
            "getTokenAccountsByOwner",
            [self.treasury_wallet, {"mint": self.mint}, {"encoding": "jsonParsed"}],
        )
        value = (result or {}).get("value") or []
        for entry in value:
            pubkey = entry.get("pubkey")
            if pubkey:
                return str(pubkey)
        return None

    async def get_treasury_balance_micro(self) -> int:
        """Live treasury USDC balance in micro-USDC (1e-6)."""
        ata = await self.get_treasury_token_account()
        if not ata:
            return 0
        result = await self._rpc("getTokenAccountBalance", [ata])
        amount = str(((result or {}).get("value") or {}).get("amount") or "0")
        try:
            return int(amount)
        except (TypeError, ValueError):
            return 0

    async def get_treasury_balance(self) -> Decimal:
        """Live treasury USDC balance in major units."""
        micro = await self.get_treasury_balance_micro()
        return Decimal(micro).scaleb(-6)

    # -- deposit sweep ------------------------------------------------------- #
    async def _extract_memos(self, tx: dict) -> list[str]:
        """Pull every memo-like string out of a parsed transaction.

        With ``encoding=jsonParsed`` the spl-memo program surfaces parsed
        instructions; different node versions phrase it slightly
        differently, so we walk instruction dicts recursively and collect
        string values of keys named ``memo``/``memo_text`` plus parsed
        spl-memo program payloads. Robust > pretty.
        """
        memos: list[str] = []

        def walk(node: Any) -> None:
            if isinstance(node, dict):
                for key, value in node.items():
                    if key in ("memo", "memo_text") and isinstance(value, str):
                        memos.append(value)
                    elif key == "program" and isinstance(value, str) and "memo" in value.lower():
                        # The parsed payload sits next to it.
                        payload = node.get("parsed")
                        if isinstance(payload, str):
                            memos.append(payload)
                        elif isinstance(payload, dict):
                            inner = payload.get("memo") or payload.get("text")
                            if isinstance(inner, str):
                                memos.append(inner)
                    else:
                        walk(value)
            elif isinstance(node, list):
                for item in node:
                    walk(item)

        walk(((tx.get("transaction") or {}).get("message") or {}).get("instructions"))
        # Solana also returns a top-level "memo" field on signature lists.
        top = tx.get("memo")
        if isinstance(top, str):
            memos.append(top)
        return memos

    async def find_deposits(self, limit: int | None = None) -> list[dict]:
        """Sweep recent successful USDC transfers INTO the treasury.

        Returns a list of normalized deposit dicts:
        ``{"signature", "slot", "confirmations", "confirmation_status",
            "amount_micro", "memos": [...]}`` (credits only — debits and
        failed transactions are skipped).
        """
        if not self.treasury_wallet:
            raise ProviderConfigError("USDC_TREASURY_WALLET is not configured")
        ata = await self.get_treasury_token_account()
        if not ata:
            return []
        scan_limit = limit or self.scan_limit or 40
        sigs = await self._rpc(
            "getSignaturesForAddress", [ata, {"limit": scan_limit}]
        )
        deposits: list[dict] = []
        for entry in sigs or []:
            signature = str(entry.get("signature") or "")
            if not signature or entry.get("err"):
                continue  # failed tx or malformed entry
            tx = await self._rpc(
                "getTransaction",
                [signature, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}],
            )
            if not tx:
                continue  # pruned / unavailable on this node
            amount_micro = self._parse_treasury_credit(tx, ata)
            if amount_micro <= 0:
                continue  # not a credit to the treasury ATA
            deposits.append(
                {
                    "signature": signature,
                    "slot": tx.get("slot"),
                    "confirmations": int(entry.get("confirmations") or 0),
                    "confirmation_status": entry.get("confirmationStatus") or "",
                    "amount_micro": amount_micro,
                    "memos": await self._extract_memos(tx),
                }
            )
        return deposits

    def _parse_treasury_credit(self, tx: dict, ata: str) -> int:
        """Credit to the treasury token account, in micro-USDC (0 if none).

        Uses ``meta.preTokenBalances``/``postTokenBalances`` — the runtime
        token balance diff — which needs no instruction decoding and is
        exact even for wrapped/complex transfers.
        """
        meta = tx.get("meta") or {}
        pre = {
            e.get("accountIndex"): e
            for e in (meta.get("preTokenBalances") or [])
            if isinstance(e, dict)
        }
        post = {
            e.get("accountIndex"): e
            for e in (meta.get("postTokenBalances") or [])
            if isinstance(e, dict)
        }
        credit = 0
        for idx, post_entry in post.items():
            if str(post_entry.get("mint") or "") != self.mint:
                continue
            # Credit only entries owned by the treasury (ATA may not carry
            # owner on all node versions — fall back to the ATA pubkey
            # itself via accountKeys).
            owner = post_entry.get("owner")
            account_keys = ((tx.get("transaction") or {}).get("message") or {}).get(
                "accountKeys"
            ) or []
            account_pubkey = ""
            if isinstance(idx, int) and 0 <= idx < len(account_keys):
                key_entry = account_keys[idx]
                account_pubkey = (
                    key_entry.get("pubkey")
                    if isinstance(key_entry, dict)
                    else str(key_entry)
                )
            if owner not in (self.treasury_wallet, None) and account_pubkey != ata:
                continue
            if owner is None and account_pubkey != ata:
                continue
            try:
                post_amount = int(
                    str((post_entry.get("uiTokenAmount") or {}).get("amount") or "0")
                )
                pre_entry = pre.get(idx)
                pre_amount = (
                    int(str((pre_entry.get("uiTokenAmount") or {}).get("amount") or "0"))
                    if pre_entry
                    else 0
                )
            except (TypeError, ValueError):
                continue
            delta = post_amount - pre_amount
            if delta > 0:
                credit += delta
        return credit

    # -- matching ------------------------------------------------------------- #
    def deposit_matches(
        self,
        deposit: dict,
        expected_amount_micro: int,
        reference: str | None = None,
    ) -> bool:
        """Does one deposit satisfy one invoice?

        Hard rule (same as the fiat rails): the AMOUNT must always cover
        the invoice — a memo reference identifies the invoice but never
        waives the amount validation. Amount-only matches are accepted
        (payers forget memos) within the micro-USDC tolerance.
        Confirmation gate handled by :meth:`deposit_settled`.
        """
        amount_micro = int(deposit.get("amount_micro") or 0)
        if abs(amount_micro - expected_amount_micro) > self.amount_tolerance:
            return False
        if reference:
            for memo in deposit.get("memos") or []:
                if reference in str(memo):
                    return True
            return False  # amount matched, but the memo names another invoice
        return True

    def deposit_settled(self, deposit: dict) -> bool:
        """Enough confirmations to call the deposit final."""
        status = str(deposit.get("confirmation_status") or "")
        if status in ("finalized",):
            return True
        if status in ("confirmed",):
            # "confirmed" on mainnet ≈ 32+ slots — treat as settled.
            return True
        return int(deposit.get("confirmations") or 0) >= self.confirmations_required

    async def check_payment(
        self, reference: str, expected_amount_micro: int
    ) -> dict | None:
        """Best matching settled deposit for one invoice (or None)."""
        for deposit in await self.find_deposits():
            if self.deposit_matches(deposit, expected_amount_micro, reference):
                if self.deposit_settled(deposit):
                    return deposit
        return None

    # -- payout reconciliation ------------------------------------------------- #
    async def verify_payout_execution(self, signature: str) -> dict | None:
        """Verify an operator-executed payout transaction exists and is
        confirmed. Returns ``{"signature", "confirmations", "status"}`` or
        None (never raises on missing tx — that IS the answer)."""
        if not signature:
            return None
        result = await self._rpc(
            "getSignatureStatuses", [[signature], {"searchTransactionHistory": True}]
        )
        value = (result or {}).get("value") or []
        status_entry = value[0] if value else None
        if not status_entry or status_entry.get("err"):
            return None
        return {
            "signature": signature,
            "confirmations": int(status_entry.get("confirmations") or 0),
            "status": status_entry.get("confirmationStatus") or "",
        }

    # -- PaymentProvider surface ----------------------------------------------- #
    async def create_checkout(
        self,
        *,
        amount: Decimal,
        currency: str,
        reference: str,
        customer_email: str = "",
        description: str = "",
        success_url: str = "",
        failure_url: str = "",
        webhook_url: str = "",
    ) -> CheckoutResult:
        """USDC payment "session" = on-chain instructions.

        There is nothing to create server-side (the chain is the session
        store): we hand back the treasury address, the exact micro-USDC
        amount and the reference memo. The engine persists the reference
        on the invoice; the sweep matches it later.
        """
        if not self.treasury_wallet:
            raise ProviderConfigError("USDC_TREASURY_WALLET is not configured")
        if not self.validate_treasury_wallet():
            raise ProviderConfigError(
                "USDC_TREASURY_WALLET is not a valid Solana pubkey (base58, 32 bytes)"
            )
        amount_micro = int((amount * Decimal(1_000_000)).to_integral_value())
        if amount_micro <= 0:
            raise ProviderConfigError("USDC payment amount must be positive")
        return CheckoutResult(
            provider=self.name,
            provider_reference=reference,
            checkout_url="",  # no hosted page — payer uses their wallet
            amount=Decimal(amount_micro).scaleb(-6),
            currency="USDC",
            deposit_address=self.treasury_wallet,
            reference_memo=reference,
            expires_at=datetime.utcnow() + timedelta(days=7),
            raw={"amount_micro": amount_micro, "mint": self.mint},
        )
