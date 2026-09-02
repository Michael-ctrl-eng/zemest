"""F3 channels/crawl SSRF & tenant-isolation adversarial tests — one PoC per audit finding.

Covers:
- A4-C1  SSRF crawl chain: redirect-to-metadata, in-process Chromium navigation
- A3-C1  SSRF with readback via /products/import-url fetch path
- A3-H1  order_api_config SSRF (write-time + call-time) and body readback
- A4-H2  Meta tokens transmitted in URL query strings
- A4-H1  Postiz shared singleton session → cross-tenant takeover
- A4-M2  OAuth state unsigned/guessable + dead callback
- A3-M10 standby events double-processed
- A3-M2  TenantResponse echoes secrets
- A4-H3  Zip-bomb / unbounded upload
- WA media IDs stored raw (unresolvable)
- Graph client: Bearer-only auth, v22.0
"""
from __future__ import annotations

import hashlib
import hmac
import io
import json
import time
import zipfile

import httpx
import pytest
from unittest.mock import AsyncMock, patch

from app.config import get_settings
from app.utils.oauth_state import sign_oauth_state, verify_oauth_state

settings = get_settings()


def _compute_signature(body: bytes, secret: str) -> str:
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={expected}"


# ---------------------------------------------------------------------------
# A4-C1 — SSRF crawl chain
# ---------------------------------------------------------------------------

def _patch_async_client(monkeypatch, transport_handler):
    """Replace httpx.AsyncClient with a factory returning REAL clients wired
    to a MockTransport — so `async with` works natively and the handler can
    record which hosts were actually reached (the request never "fails";
    blocking must come from the SSRF guard itself).
    """
    RealAsyncClient = httpx.AsyncClient
    transport = httpx.MockTransport(transport_handler)

    def factory(*args, **kwargs):
        kwargs.pop("timeout", None)
        kwargs.pop("base_url", None)
        return RealAsyncClient(transport=transport, follow_redirects=False)

    monkeypatch.setattr("httpx.AsyncClient", factory)
    return transport


@pytest.mark.asyncio
class TestCrawlSSRF:
    async def test_quick_fetch_blocks_redirect_to_metadata(self, monkeypatch):
        """Public URL that 302s to 169.254.169.254 must be blocked mid-hop."""
        from app.knowledge.crawler import _quick_fetch

        reached = []

        def transport_handler(request: httpx.Request) -> httpx.Response:
            reached.append(request.url.host)
            if "evil-redirector.example" in request.url.host:
                return httpx.Response(302, headers={"Location": "http://169.254.169.254/latest/meta-data/"})
            return httpx.Response(200, content=b"<html>" + b"x" * 600 + b"</html>",
                                  headers={"content-type": "text/html"})

        _patch_async_client(monkeypatch, transport_handler)
        result = await _quick_fetch("http://evil-redirector.example/")

        assert result is None, "fetch followed a redirect into the metadata endpoint"
        assert "169.254.169.254" not in reached, "metadata endpoint was reached"

    async def test_fetch_and_extract_blocks_internal_target(self, monkeypatch):
        """Direct fetch of an internal URL is blocked before any request."""
        from app.knowledge.crawler import _fetch_and_extract

        reached = []

        def transport_handler(request: httpx.Request) -> httpx.Response:
            reached.append(request.url.host)
            return httpx.Response(200, content=b"<html>" + b"y" * 600 + b"</html>",
                                  headers={"content-type": "text/html"})

        _patch_async_client(monkeypatch, transport_handler)
        result = await _fetch_and_extract("http://10.0.0.5:8000/_admin/secret")

        assert result is None
        assert reached == [], f"request reached internal host: {reached}"

    async def test_product_extractor_blocks_metadata_redirect(self, monkeypatch):
        """A3-C1: import-url fetch chain must re-validate every redirect."""
        from app.knowledge.product_extractor import _fetch_page

        reached = []

        def transport_handler(request: httpx.Request) -> httpx.Response:
            reached.append(request.url.host)
            if "evil-shop.example" in request.url.host:
                return httpx.Response(302, headers={"Location": "http://169.254.169.254/latest/"})
            return httpx.Response(200, content=b"<html>product</html>",
                                  headers={"content-type": "text/html"})

        _patch_async_client(monkeypatch, transport_handler)
        result = await _fetch_page("https://evil-shop.example/item")

        assert result is None
        assert "169.254.169.254" not in reached


# ---------------------------------------------------------------------------
# A3-H1 — order_api_config SSRF chain
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestOrderApiSSRF:
    async def test_tenant_patch_rejects_metadata_url(self, client, auth_headers, test_tenant):
        """Storing an order_api_config aimed at instance metadata → 422."""
        resp = await client.patch(
            f"/api/tenants/{test_tenant.id}",
            json={"order_api_config": {
                "enabled": True,
                "url": "http://169.254.169.254/latest/meta-data/iam/security-credentials/",
                "method": "GET",
            }},
            headers=auth_headers,
        )
        assert resp.status_code == 422, resp.text

    async def test_tenant_patch_rejects_localhost_url(self, client, auth_headers, test_tenant):
        resp = await client.patch(
            f"/api/tenants/{test_tenant.id}",
            json={"order_api_config": {
                "enabled": True,
                "url": "http://localhost:6379/",
                "method": "GET",
            }},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    async def test_tenant_patch_rejects_bad_method(self, client, auth_headers, test_tenant):
        resp = await client.patch(
            f"/api/tenants/{test_tenant.id}",
            json={"order_api_config": {
                "enabled": True,
                "url": "https://example.com/hook",
                "method": "TRACE",
            }},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    async def test_call_time_blocks_legacy_config(self, db_session, test_tenant):
        """A config written before the guard (or via direct DB edit) is
        still blocked at call time — and no body readback."""
        from app.services.order_api_service import call_order_api

        test_tenant.order_api_config = {
            "enabled": True,
            "url": "http://192.168.1.10:9000/internal",
            "method": "GET",
        }
        await db_session.flush()

        class FakeOrder:
            id = test_tenant.id
            items = []
            customer_name = "X"
            customer_phone = "01012345678"
            governorate = ""
            city = ""
            area = ""
            address_detail = ""
            payment_method = "cod"
            payment_phone_last2 = ""
            payment_trx_id = ""
            subtotal = 0
            delivery_charge = 0
            total = 0
            order_number = "ORD-1"
            notes = ""
            api_status = None
            api_response = None
            api_status_code = None
            api_external_id = None
            api_called_at = None

        result = await call_order_api(db_session, test_tenant, FakeOrder())
        assert result["status"] == "blocked"
        assert "192.168.1.10" not in json.dumps(result), "internal host leaked in result"


# ---------------------------------------------------------------------------
# A4-H2 — tokens in URL query strings
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestTokenTransport:
    async def test_graph_get_uses_bearer_not_query(self, monkeypatch):
        """The shared Graph client must put the token in the Authorization
        header, never in the URL query (proxy/access log capture)."""
        from app.services.graph_client import graph_get

        captured = {}

        def transport_handler(request: httpx.Request) -> httpx.Response:
            captured["url"] = str(request.url)
            captured["headers"] = dict(request.headers)
            return httpx.Response(200, json={"id": "123", "name": "Page"})

        _patch_async_client(monkeypatch, transport_handler)
        await graph_get("123", "SECRET-TOKEN-ABC", fields="name")

        assert "SECRET-TOKEN-ABC" not in captured["url"], "token leaked into URL"
        assert captured["headers"].get("authorization") == "Bearer SECRET-TOKEN-ABC"
        assert "v22.0" in captured["url"], "Graph version not bumped"

    async def test_facebook_pages_requires_body_not_query(self, client, auth_headers):
        """GET /api/facebook/pages?fb_access_token=… previously put the
        long-lived user token in the URL — now the token must come in a body."""
        resp = await client.get(
            "/api/facebook/pages?fb_access_token=EAAxxxxlongtoken",
            headers=auth_headers,
        )
        assert resp.status_code == 422, (
            "token accepted via query string — the leak pattern is still live"
        )

    async def test_facebook_connect_token_not_in_url(self, client, auth_headers):
        """POST /connect bound simple params to the query string — the Page
        token traveled in the URL even on POST."""
        resp = await client.post(
            "/api/facebook/connect?page_id=123&token-not-allowed=1",
            headers=auth_headers,
        )
        # Missing required body → 422, and the request never hit a URL-token path
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# A4-M2 — OAuth state signing
# ---------------------------------------------------------------------------

class TestOAuthState:
    def test_state_not_guessable(self):
        """The old state was literally 'tenant:{uuid}' — guessable."""
        state = sign_oauth_state("11111111-1111-1111-1111-111111111111")
        assert state != "tenant:11111111-1111-1111-1111-111111111111"
        assert len(state.split(".")) == 3  # tenant.ts.mac

    def test_verify_roundtrip(self):
        tenant_id = "22222222-2222-2222-2222-222222222222"
        state = sign_oauth_state(tenant_id)
        valid, extracted = verify_oauth_state(state)
        assert valid and extracted == tenant_id

    def test_tampered_state_rejected(self):
        state = sign_oauth_state("33333333-3333-3333-3333-333333333333")
        tenant, ts, mac = state.rsplit(".", 3)
        tampered = f"44444444-4444-4444-4444-444444444444.{ts}.{mac}"
        valid, _ = verify_oauth_state(tampered)
        assert not valid

    def test_expired_state_rejected(self):
        """Stale/replayed states (older than 15 min) are rejected."""
        with patch("app.utils.oauth_state.time.time", return_value=1000000.0):
            state = sign_oauth_state("tenant-a")
        # now = much later
        with patch("app.utils.oauth_state.time.time", return_value=1000000.0 + 3600):
            valid, _ = verify_oauth_state(state)
        assert not valid

    def test_wrong_tenant_pin_rejected(self):
        state = sign_oauth_state("tenant-a")
        valid, _ = verify_oauth_state(state, tenant_id="tenant-b")
        assert not valid


@pytest.mark.asyncio
async def test_oauth_url_contains_signed_state(
    client, auth_headers, test_tenant, monkeypatch
):
    monkeypatch.setattr(settings, "FB_APP_ID", "app-123", raising=False)
    resp = await client.get(
        f"/api/tenants/{test_tenant.id}/channels/oauth-url",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ready"] is True
    assert "state=" in data["url"]
    assert f"tenant:{test_tenant.id}" not in data["url"]


# ---------------------------------------------------------------------------
# A3-M2 — TenantResponse secret masking
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestSecretMasking:
    async def test_payment_methods_masked(self, client, db_session, auth_headers, test_tenant):
        test_tenant.payment_methods = {
            "vodafone_cash": "01277788999",   # distinct from business_phone
            "instapay": "merchant@instapay",
        }
        await db_session.commit()

        resp = await client.get(
            f"/api/tenants/{test_tenant.id}", headers=auth_headers
        )
        data = resp.json()
        assert data["payment_methods"]["vodafone_cash"] == "****8999"
        assert "01277788999" not in json.dumps(data["payment_methods"])
        assert "merchant@instapay" not in json.dumps(data["payment_methods"])

    async def test_order_api_auth_masked(self, client, db_session, auth_headers, test_tenant):
        test_tenant.order_api_config = {
            "enabled": True,
            "url": "https://example.com/hook",
            "auth_type": "bearer",
            "auth_value": "sk-super-secret-key-123",
        }
        await db_session.commit()

        resp = await client.get(
            f"/api/tenants/{test_tenant.id}", headers=auth_headers
        )
        data = resp.json()
        assert data["order_api_config"]["auth_value"] == "****"
        assert "sk-super-secret-key" not in json.dumps(data)


# ---------------------------------------------------------------------------
# A4-H1 — Postiz per-tenant sessions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestPostizTenantIsolation:
    async def test_login_persists_per_tenant(self, client, db_session, auth_headers, test_tenant):
        """Login stores THIS tenant's session — not a process singleton."""
        fake_client = AsyncMock()
        fake_client.token = "JWT-TENANT-A"
        fake_client.set_token = lambda t: None
        fake_client.login = AsyncMock(return_value=True)

        with patch("app.api.postiz.get_postiz_client_for_tenant", return_value=fake_client):
            resp = await client.post(
                f"/api/tenants/{test_tenant.id}/postiz/login",
                json={"email": "a@shop.com", "password": "pass"},
                headers=auth_headers,
            )
        assert resp.status_code == 200
        await db_session.refresh(test_tenant)
        assert test_tenant.postiz_token == "JWT-TENANT-A"
        assert test_tenant.postiz_email == "a@shop.com"

    async def test_tenant_without_session_gets_401(self, client, auth_headers, test_tenant):
        """No stored session → 401. Never another tenant's session."""
        assert not test_tenant.postiz_token
        resp = await client.get(
            f"/api/tenants/{test_tenant.id}/postiz/posts",
            headers=auth_headers,
        )
        assert resp.status_code == 401

    async def test_tenant_clients_isolated(self):
        """Two tenants → two distinct client instances with their own tokens."""
        from app.scheduling.postiz_client import (
            get_postiz_client_for_tenant,
            _tenant_clients,
        )
        _tenant_clients.clear()

        class FakeTenant:
            def __init__(self, tid, token):
                self.id = tid
                self.postiz_token = token

        a = FakeTenant("aaaa", "TOKEN-A")
        b = FakeTenant("bbbb", "TOKEN-B")

        client_a = get_postiz_client_for_tenant(a)
        client_b = get_postiz_client_for_tenant(b)

        assert client_a is not client_b
        assert client_a.token == "TOKEN-A"
        assert client_b.token == "TOKEN-B"


# ---------------------------------------------------------------------------
# A3-M10 — standby double-processing
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestWebhookStandby:
    async def test_standby_events_not_processed_as_messages(
        self, client, test_tenant, monkeypatch
    ):
        """The same message delivered via messaging AND standby must run the
        agent pipeline exactly once."""
        monkeypatch.setattr(settings, "FB_APP_SECRET", "test_secret_for_signing")
        monkeypatch.setattr(
            "app.api.webhook._process_messenger_message", AsyncMock()
        )
        from app.api import webhook as webhook_mod

        msg = {"sender": {"id": "user1"}, "message": {"mid": "m1", "text": "hi"}}
        payload = {
            "object": "page",
            "entry": [{
                "id": test_tenant.fb_page_id,
                "messaging": [msg],
                "standby": [msg],  # Meta duplicate
            }],
        }
        body = json.dumps(payload).encode()
        sig = _compute_signature(body, "test_secret_for_signing")

        resp = await client.post(
            "/api/webhook/messenger",
            content=body,
            headers={"Content-Type": "application/json", "X-Hub-Signature-256": sig},
        )
        assert resp.status_code == 200
        assert webhook_mod._process_messenger_message.call_count == 1, (
            "standby events double-processed the message"
        )

    async def test_standby_only_event_not_processed(
        self, client, test_tenant, monkeypatch
    ):
        """Standby without a messaging twin is skipped entirely."""
        monkeypatch.setattr(settings, "FB_APP_SECRET", "test_secret_for_signing")
        monkeypatch.setattr(
            "app.api.webhook._process_messenger_message", AsyncMock()
        )
        payload = {
            "object": "page",
            "entry": [{
                "id": test_tenant.fb_page_id,
                "standby": [{"sender": {"id": "user1"}, "message": {"mid": "m2"}}],
            }],
        }
        body = json.dumps(payload).encode()
        sig = _compute_signature(body, "test_secret_for_signing")
        await client.post(
            "/api/webhook/messenger",
            content=body,
            headers={"Content-Type": "application/json", "X-Hub-Signature-256": sig},
        )
        from app.api import webhook as webhook_mod
        assert webhook_mod._process_messenger_message.call_count == 0


# ---------------------------------------------------------------------------
# WhatsApp media ID resolution
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestWhatsAppMediaResolution:
    async def test_media_ids_resolved_to_urls(self, db_session, test_tenant, monkeypatch):
        """Webhook media IDs must become downloadable URLs before reaching
        the agent (raw IDs were stored where nothing could fetch them)."""
        from app.api import webhook as webhook_mod

        resolved_ids = []

        async def fake_resolve(media_id, token):
            resolved_ids.append(media_id)
            return f"https://cdn.example/media/{media_id}"

        monkeypatch.setattr(
            "app.services.graph_client.resolve_media_url", fake_resolve
        )

        async def fake_process(db, tenant, sender_psid, message_text, **kwargs):
            fake_process.media_urls = kwargs.get("media_urls")
            fake_process.audio_urls = kwargs.get("audio_urls")
            return "ok"

        monkeypatch.setattr(
            "app.ai.agent.process_customer_message", fake_process
        )
        monkeypatch.setattr(
            "app.services.whatsapp_service.send_whatsapp_message",
            AsyncMock(return_value=True),
        )

        # Point the tenant at our fake phone_number_id
        test_tenant.wa_phone_number_id = "PNID-TEST"
        test_tenant.wa_access_token = "WA-TOKEN"
        await db_session.flush()

        # The webhook opens its own production session — route it to the
        # test session so the tenant lookup works without a live DB.
        class _SessionCtx:
            async def __aenter__(self):
                return db_session
            async def __aexit__(self, *exc):
                return False

        monkeypatch.setattr("app.api.webhook.async_session", lambda: _SessionCtx())

        msg = {
            "from": "201012345678",
            "id": "wamid.1",
            "type": "image",
            "image": {"id": "MEDIA-IMG-1"},
        }
        await webhook_mod._process_whatsapp_message("PNID-TEST", msg, [])

        assert resolved_ids == ["MEDIA-IMG-1"]
        assert fake_process.media_urls == ["https://cdn.example/media/MEDIA-IMG-1"]


# ---------------------------------------------------------------------------
# A4-H3 — zip-bomb protections
# ---------------------------------------------------------------------------

class TestZipBombGuards:
    def test_messenger_dyi_oversized_member_skipped(self):
        """A zip member whose *uncompressed* size exceeds the cap is skipped."""
        from app.services.importers.messenger_dyi import parse_messenger_dyi_zip

        # Build a zip whose single member declares a huge uncompressed size
        # (real bytes are tiny; file_size in the header is what we check first).
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as bomb:
            # 60 MB of compressible content — exceeds the 50 MB member cap
            payload = ("x" * 1024) * 60 * 1024  # ~60 MB
            bomb.writestr("messages/message_1.json", json.dumps({"messages": []}) + payload)
        bomb_bytes = buf.getvalue()

        # Parse — the oversized member must be skipped, not OOM the process
        messages = parse_messenger_dyi_zip(bomb_bytes)
        assert isinstance(messages, list)  # no crash

    def test_whatsapp_oversized_export_rejected(self):
        from app.services.importers.whatsapp_export import parse_whatsapp_export_zip

        # >100 MB of highly-compressible text — the guard must reject on
        # declared uncompressed size BEFORE any line parsing happens.
        big_text = "[01/01/25, 10:00] Person: hello\n" * 4200000  # ~101 MB
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("_chat.txt", big_text)
        with pytest.raises(ValueError):
            parse_whatsapp_export_zip(buf.getvalue())

    def test_normal_zip_still_parses(self):
        """Small exports keep working — the guard doesn't over-block."""
        from app.services.importers.whatsapp_export import parse_whatsapp_export_zip

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(
                "_chat.txt",
                "[01/01/25, 10:00] Ahmed: السلام عليكم\n"
                "[01/01/25, 10:01] Me: أهلاً\n" * 5,
            )
        messages = parse_whatsapp_export_zip(buf.getvalue())
        assert len(messages) > 0


# ---------------------------------------------------------------------------
# Graph version + Bearer
# ---------------------------------------------------------------------------

class TestGraphVersion:
    def test_config_is_v22(self):
        assert "v22.0" in settings.FB_GRAPH_API_URL

    def test_whatsapp_service_uses_shared_version(self):
        from app.services.whatsapp_service import WHATSAPP_API_URL
        assert WHATSAPP_API_URL == settings.FB_GRAPH_API_URL
