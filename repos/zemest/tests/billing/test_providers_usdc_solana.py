"""USDC-Solana provider tests — vendored base58 + chain parsing.

The crypto rail must work with ZERO external Solana SDKs and ZERO
private keys: pure JSON-RPC reads. These tests cover the chain-parsing
primitives offline (mocked RPC responses shaped exactly like Solana's).
"""
from __future__ import annotations

import json
from decimal import Decimal

import pytest

from app.services.billing.providers.base import ProviderConfigError
from app.services.billing.providers.usdc_solana import (
    UsdcSolanaProvider,
    b58decode,
    b58encode,
    new_solana_reference,
)

MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
WALLET = "1" * 32  # 32 zero bytes — valid pubkey shape
ATA = "2" * 32  # fake associated token account


class TestBase58:
    def test_roundtrip_known_addresses(self):
        for s in (MINT, WALLET, ATA, "11111111111111111111111111111112"):
            assert b58encode(b58decode(s)) == s

    def test_decode_invalid_char(self):
        with pytest.raises(ValueError):
            b58decode("0OIl")  # not in the base58 alphabet

    def test_decode_leading_zeros(self):
        # 3 leading '1's = 3 zero bytes; '2' encodes the value 1.
        assert b58decode("1112") == b"\x00\x00\x00\x01"

    def test_encode_empty(self):
        assert b58encode(b"") == ""


class TestProviderConfig:
    def test_unconfigured_without_wallet(self):
        assert UsdcSolanaProvider(
            treasury_wallet=""
        ).is_configured() is False

    def test_configured_with_wallet(self, billing_settings):
        provider = UsdcSolanaProvider()
        assert provider.is_configured() is True

    def test_invalid_wallet_rejected_at_checkout(self, billing_settings):
        provider = UsdcSolanaProvider(treasury_wallet="not!!a!!pubkey")
        with pytest.raises(ProviderConfigError):
            import asyncio

            asyncio.get_event_loop().run_until_complete(
                provider.create_checkout(
                    amount=Decimal("15"), currency="USDC", reference="zm-x"
                )
            )

    def test_reference_is_high_entropy(self):
        refs = {new_solana_reference() for _ in range(100)}
        assert len(refs) == 100
        assert all(r.startswith("zm-") for r in refs)


def _tx(credit_micro: int, memo: str | None = None, owner: str = WALLET) -> dict:
    """A parsed Solana transaction JSON that credits the treasury ATA."""
    instructions = []
    if memo:
        instructions.append(
            {"program": "spl-memo", "parsed": {"type": "memo", "memo": memo}}
        )
    return {
        "slot": 123_000,
        "transaction": {
            "message": {
                "accountKeys": [{"pubkey": ATA}],
                "instructions": instructions,
            }
        },
        "meta": {
            "err": None,
            "preTokenBalances": [
                {"accountIndex": 0, "mint": MINT, "owner": owner,
                 "uiTokenAmount": {"amount": "1000000", "decimals": 6}}
            ],
            "postTokenBalances": [
                {"accountIndex": 0, "mint": MINT, "owner": owner,
                 "uiTokenAmount": {"amount": str(1000000 + credit_micro), "decimals": 6}}
            ],
        },
    }


class TestTreasuryCreditParsing:
    def test_credit_detected(self, billing_settings):
        provider = UsdcSolanaProvider()
        assert provider._parse_treasury_credit(_tx(15_000_000), ATA) == 15_000_000

    def test_debit_ignored(self, billing_settings):
        provider = UsdcSolanaProvider()
        tx = _tx(-5)
        assert provider._parse_treasury_credit(tx, ATA) == 0

    def test_other_mint_ignored(self, billing_settings):
        provider = UsdcSolanaProvider()
        tx = _tx(15_000_000)
        tx["meta"]["postTokenBalances"][0]["mint"] = "So11111111111111111111111111111111111111112"
        assert provider._parse_treasury_credit(tx, ATA) == 0

    def test_new_token_account_counts_as_credit(self, billing_settings):
        provider = UsdcSolanaProvider()
        tx = _tx(15_000_000)
        # A brand-new token account: no pre-balances, post = full amount.
        tx["meta"]["preTokenBalances"] = []
        tx["meta"]["postTokenBalances"][0]["uiTokenAmount"]["amount"] = "15000000"
        assert provider._parse_treasury_credit(tx, ATA) == 15_000_000


class TestMemoExtraction:
    @pytest.mark.asyncio
    async def test_memo_found(self, billing_settings):
        provider = UsdcSolanaProvider()
        memos = await provider._extract_memos(_tx(1, memo="zm-abc123"))
        assert "zm-abc123" in memos

    @pytest.mark.asyncio
    async def test_no_memo(self, billing_settings):
        provider = UsdcSolanaProvider()
        assert await provider._extract_memos(_tx(1)) == []


class TestDepositMatching:
    def _deposit(self, micro: int, memos=None, confirmations=40, status="finalized"):
        return {
            "signature": "sig1",
            "confirmations": confirmations,
            "confirmation_status": status,
            "amount_micro": micro,
            "memos": memos or [],
        }

    def test_reference_match(self, billing_settings):
        provider = UsdcSolanaProvider()
        assert provider.deposit_matches(
            self._deposit(15_000_000, memos=["zm-ref"]), 15_000_000, "zm-ref"
        )

    def test_reference_with_wrong_amount_does_not_match(self, billing_settings):
        # The memo alone never waives amount validation.
        provider = UsdcSolanaProvider()
        assert not provider.deposit_matches(
            self._deposit(9, memos=["zm-ref"]), 15_000_000, "zm-ref"
        )

    def test_amount_only_match_when_no_reference(self, billing_settings):
        provider = UsdcSolanaProvider()
        assert provider.deposit_matches(self._deposit(15_000_000), 15_000_000, None)

    def test_amount_match_names_other_invoice(self, billing_settings):
        provider = UsdcSolanaProvider()
        assert not provider.deposit_matches(
            self._deposit(15_000_000, memos=["zm-other"]), 15_000_000, "zm-mine"
        )

    def test_amount_match_within_tolerance(self, billing_settings):
        provider = UsdcSolanaProvider(amount_tolerance=100)
        assert provider.deposit_matches(self._deposit(15_000_050), 15_000_000, None)

    def test_amount_mismatch(self, billing_settings):
        provider = UsdcSolanaProvider(amount_tolerance=100)
        assert not provider.deposit_matches(self._deposit(14_000_000), 15_000_000, None)

    def test_settled_finalized(self, billing_settings):
        provider = UsdcSolanaProvider()
        assert provider.deposit_settled(self._deposit(1, status="finalized"))

    def test_settled_confirmed(self, billing_settings):
        provider = UsdcSolanaProvider()
        assert provider.deposit_settled(self._deposit(1, status="confirmed"))

    def test_not_settled_low_confirmations(self, billing_settings):
        provider = UsdcSolanaProvider()
        assert not provider.deposit_settled(
            self._deposit(1, status="processed", confirmations=3)
        )


class TestRpcFlow:
    """find_deposits / balances / payout verification over mocked _rpc."""

    @pytest.mark.asyncio
    async def test_find_deposits_full_flow(self, billing_settings):
        provider = UsdcSolanaProvider()
        rpc_calls = []

        async def fake_rpc(method, params):
            rpc_calls.append(method)
            if method == "getTokenAccountsByOwner":
                return {"value": [{"pubkey": ATA}]}
            if method == "getSignaturesForAddress":
                return [
                    {"signature": "sigOK", "err": None, "confirmations": 40,
                     "confirmationStatus": "finalized"},
                    {"signature": "sigERR", "err": {"InstructionError": 0},
                     "confirmations": 40},
                ]
            if method == "getTransaction":
                sig = params[0]
                return _tx(15_000_000, memo="zm-pay-me") if sig == "sigOK" else _tx(1)
            return {}

        provider._rpc = fake_rpc  # type: ignore[method-assign]
        deposits = await provider.find_deposits()
        assert len(deposits) == 1
        assert deposits[0]["signature"] == "sigOK"
        assert deposits[0]["amount_micro"] == 15_000_000
        assert "zm-pay-me" in deposits[0]["memos"]
        # failed transactions are skipped
        assert all(d["signature"] != "sigERR" for d in deposits)

    @pytest.mark.asyncio
    async def test_no_token_account_no_deposits(self, billing_settings):
        provider = UsdcSolanaProvider()

        async def fake_rpc(method, params):
            if method == "getTokenAccountsByOwner":
                return {"value": []}
            return {}

        provider._rpc = fake_rpc  # type: ignore[method-assign]
        assert await provider.find_deposits() == []

    @pytest.mark.asyncio
    async def test_check_payment_match(self, billing_settings):
        provider = UsdcSolanaProvider()

        async def fake_rpc(method, params):
            if method == "getTokenAccountsByOwner":
                return {"value": [{"pubkey": ATA}]}
            if method == "getSignaturesForAddress":
                return [{"signature": "sigOK", "err": None, "confirmations": 40,
                         "confirmationStatus": "finalized"}]
            if method == "getTransaction":
                return _tx(15_000_000, memo="zm-wanted")
            return {}

        provider._rpc = fake_rpc  # type: ignore[method-assign]
        match = await provider.check_payment("zm-wanted", 15_000_000)
        assert match is not None and match["signature"] == "sigOK"

    @pytest.mark.asyncio
    async def test_verify_payout_execution_missing(self, billing_settings):
        provider = UsdcSolanaProvider()

        async def fake_rpc(method, params):
            if method == "getSignatureStatuses":
                return {"value": [None]}
            return {}

        provider._rpc = fake_rpc  # type: ignore[method-assign]
        assert await provider.verify_payout_execution("nonexistent") is None

    @pytest.mark.asyncio
    async def test_verify_payout_execution_confirmed(self, billing_settings):
        provider = UsdcSolanaProvider()

        async def fake_rpc(method, params):
            if method == "getSignatureStatuses":
                return {"value": [{"err": None, "confirmations": 65,
                                   "confirmationStatus": "finalized"}]}
            return {}

        provider._rpc = fake_rpc  # type: ignore[method-assign]
        result = await provider.verify_payout_execution("sigexists")
        assert result is not None and result["status"] == "finalized"
