"""Tests for Messenger webhook endpoints with proper signature verification."""
import hashlib
import hmac
import json

import pytest

from app.config import get_settings

settings = get_settings()


def _compute_signature(body: bytes, secret: str) -> str:
    """Compute the X-Hub-Signature-256 header value."""
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={expected}"


@pytest.mark.asyncio
class TestWebhook:

    async def test_webhook_verification_success(self, client):
        resp = await client.get("/api/webhook/messenger", params={
            "hub.mode": "subscribe",
            "hub.verify_token": settings.FB_VERIFY_TOKEN,
            "hub.challenge": "challenge_12345",
        })
        assert resp.status_code == 200
        assert resp.text == "challenge_12345"

    async def test_webhook_verification_wrong_token(self, client):
        resp = await client.get("/api/webhook/messenger", params={
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong_token",
            "hub.challenge": "challenge_12345",
        })
        assert resp.status_code == 403

    async def test_webhook_verification_missing_params(self, client):
        resp = await client.get("/api/webhook/messenger")
        assert resp.status_code == 403

    async def test_webhook_receive_message_with_valid_signature(self, client, test_tenant, monkeypatch):
        """Test receiving a Messenger event WITH valid HMAC signature."""
        # Set a known FB_APP_SECRET for testing
        monkeypatch.setattr(settings, "FB_APP_SECRET", "test_secret_for_signing")
        monkeypatch.setattr(settings, "APP_DEBUG", False)

        payload = {
            "object": "page",
            "entry": [
                {
                    "id": test_tenant.fb_page_id,
                    "messaging": [
                        {
                            "sender": {"id": "customer_psid_123"},
                            "recipient": {"id": test_tenant.fb_page_id},
                            "message": {
                                "mid": "mid.test123",
                                "text": "Hi, what products do you have?",
                            },
                        }
                    ],
                }
            ],
        }
        body = json.dumps(payload).encode()
        signature = _compute_signature(body, "test_secret_for_signing")

        resp = await client.post(
            "/api/webhook/messenger",
            content=body,
            headers={"Content-Type": "application/json", "X-Hub-Signature-256": signature},
        )
        assert resp.status_code == 200
        assert resp.text == "EVENT_RECEIVED"

    async def test_webhook_rejects_invalid_signature(self, client, monkeypatch):
        """Webhook without a valid signature should return 403 (fail-closed)."""
        monkeypatch.setattr(settings, "FB_APP_SECRET", "real_secret")
        monkeypatch.setattr(settings, "APP_DEBUG", False)

        payload = {"object": "page", "entry": []}
        body = json.dumps(payload).encode()
        bad_signature = "sha256=invalid_hex_string_here"

        resp = await client.post(
            "/api/webhook/messenger",
            content=body,
            headers={"Content-Type": "application/json", "X-Hub-Signature-256": bad_signature},
        )
        assert resp.status_code == 403

    async def test_webhook_rejects_missing_signature(self, client, monkeypatch):
        """Webhook without X-Hub-Signature-256 header should return 403."""
        monkeypatch.setattr(settings, "FB_APP_SECRET", "real_secret")
        monkeypatch.setattr(settings, "APP_DEBUG", False)

        payload = {"object": "page", "entry": []}
        body = json.dumps(payload).encode()

        resp = await client.post(
            "/api/webhook/messenger",
            content=body,
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 403

    async def test_webhook_rejects_when_secret_missing(self, client, monkeypatch):
        """When FB_APP_SECRET is empty, webhooks should be rejected (fail-closed)."""
        monkeypatch.setattr(settings, "FB_APP_SECRET", "")
        monkeypatch.setattr(settings, "APP_DEBUG", False)

        payload = {"object": "page", "entry": []}
        body = json.dumps(payload).encode()

        resp = await client.post(
            "/api/webhook/messenger",
            content=body,
            headers={"Content-Type": "application/json", "X-Hub-Signature-256": "sha256=abc"},
        )
        assert resp.status_code == 403

    async def test_webhook_non_page_event(self, client, monkeypatch):
        """Test that non-page events return 404."""
        monkeypatch.setattr(settings, "FB_APP_SECRET", "test_secret")
        monkeypatch.setattr(settings, "APP_DEBUG", False)

        payload = {"object": "not_a_page"}
        body = json.dumps(payload).encode()
        signature = _compute_signature(body, "test_secret")

        resp = await client.post(
            "/api/webhook/messenger",
            content=body,
            headers={"Content-Type": "application/json", "X-Hub-Signature-256": signature},
        )
        assert resp.status_code == 404

    async def test_webhook_empty_messaging(self, client, test_tenant, monkeypatch):
        """Empty messaging array should still return 200."""
        monkeypatch.setattr(settings, "FB_APP_SECRET", "test_secret")
        monkeypatch.setattr(settings, "APP_DEBUG", False)

        payload = {
            "object": "page",
            "entry": [{"id": test_tenant.fb_page_id, "messaging": []}],
        }
        body = json.dumps(payload).encode()
        signature = _compute_signature(body, "test_secret")

        resp = await client.post(
            "/api/webhook/messenger",
            content=body,
            headers={"Content-Type": "application/json", "X-Hub-Signature-256": signature},
        )
        assert resp.status_code == 200
