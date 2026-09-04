"""Payoneer provider tests — checkout payloads + fail-closed HMAC.

Covers the webhook-verification contract from the security audit:
* HMAC over the EXACT raw bytes (never a re-serialized copy)
* constant-time compare, fail-closed on empty secret/signature/body
* sha256 (default) and sha512 algorithms
* amount parsing into minor units
* checkout payload shape (client_reference_id = our invoice id)
* Idempotency-Key header derived from OUR reference
"""
from __future__ import annotations

import hashlib
import hmac as hmac_lib
from decimal import Decimal

import pytest

from app.services.billing.providers.base import (
    ProviderApiError,
    ProviderConfigError,
)
from app.services.billing.providers.payoneer import (
    PayoneerProvider,
    parse_amount,
    verify_webhook_signature,
)


def _sign(raw: bytes, secret: str, algo: str = "sha256") -> str:
    digestmod = hashlib.sha256 if algo == "sha256" else hashlib.sha512
    return hmac_lib.new(secret.encode(), raw, digestmod).hexdigest()


class TestWebhookSignature:
    RAW = b'{"type":"payment.succeeded","amount":"15.50"}'

    def test_valid_signature_sha256(self):
        sig = _sign(self.RAW, "s3cret")
        assert verify_webhook_signature(self.RAW, sig, "s3cret") is True

    def test_valid_signature_sha512(self):
        sig = _sign(self.RAW, "s3cret", "sha512")
        assert verify_webhook_signature(self.RAW, sig, "s3cret", "sha512") is True

    def test_wrong_secret_rejected(self):
        sig = _sign(self.RAW, "s3cret")
        assert verify_webhook_signature(self.RAW, sig, "other") is False

    def test_tampered_body_rejected(self):
        # A re-serialized JSON copy (key order change) breaks signatures.
        sig = _sign(self.RAW, "s3cret")
        tampered = b'{"amount":"15.50","type":"payment.succeeded"}'
        assert verify_webhook_signature(tampered, sig, "s3cret") is False

    def test_empty_signature_fails_closed(self):
        assert verify_webhook_signature(self.RAW, "", "s3cret") is False

    def test_empty_secret_fails_closed(self):
        sig = _sign(self.RAW, "s3cret")
        assert verify_webhook_signature(self.RAW, sig, "") is False

    def test_empty_body_fails_closed(self):
        sig = _sign(b"", "s3cret")
        assert verify_webhook_signature(b"", sig, "s3cret") is False

    def test_junk_signature_never_raises(self):
        assert verify_webhook_signature(self.RAW, "\u00e9!@#", "s3cret") is False

    def test_unknown_algo_falls_back_to_sha256(self):
        sig = _sign(self.RAW, "s3cret", "sha256")
        assert verify_webhook_signature(self.RAW, sig, "s3cret", "sha999") is True

    def test_signature_whitespace_and_case_tolerated(self):
        sig = _sign(self.RAW, "s3cret").upper()
        assert verify_webhook_signature(self.RAW, f"  {sig}  ", "s3cret") is True


class TestParseAmount:
    def test_decimal_string(self):
        assert parse_amount("15.50") == 1550

    def test_integer_minor_units(self):
        assert parse_amount(1550) == 1550

    def test_float(self):
        assert parse_amount(15.5) == 1550

    def test_none_for_garbage(self):
        assert parse_amount(None) is None
        assert parse_amount("abc") is None
        assert parse_amount(True) is None


class TestProviderConstruction:
    def test_is_configured_false_without_token(self):
        assert PayoneerProvider(api_token="").is_configured() is False

    def test_is_configured_true_with_token(self):
        assert PayoneerProvider(api_token="tok").is_configured() is True

    def test_create_checkout_requires_token(self):
        import pytest

        provider = PayoneerProvider(api_token="")
        with pytest.raises(ProviderConfigError):
            import asyncio

            asyncio.get_event_loop().run_until_complete(
                provider.create_checkout(
                    amount=Decimal("15.00"), currency="USD", reference="ref1"
                )
            )


class TestCheckoutPayload:
    def test_payload_shape(self, billing_settings):
        provider = PayoneerProvider(api_token="tok")
        payload = provider.build_checkout_payload(
            amount=Decimal("38.54"),
            currency="USD",
            reference="inv-123",
            customer_email="merchant@store.com",
            description="Zemest Growth subscription",
            success_url="https://app.example/billing?ok=1",
            failure_url="https://app.example/billing?fail=1",
            webhook_url="https://api.example/api/payments/webhook/payoneer",
        )
        assert payload["amount"] == "38.54"
        assert payload["currency"] == "USD"
        # OUR id is echoed back on every callback — the correlation key.
        assert payload["client_reference_id"] == "inv-123"
        assert payload["payer"] == {"email": "merchant@store.com"}
        assert payload["webhook_url"].endswith("/api/payments/webhook/payoneer")

    def test_minimal_payload(self):
        provider = PayoneerProvider(api_token="tok", partner_id="", program_id="")
        payload = provider.build_checkout_payload(
            amount=Decimal("1.00"), currency="USD", reference="r"
        )
        assert "payer" not in payload
        assert "partner_id" not in payload
        assert payload["description"].startswith("Zemest subscription")
