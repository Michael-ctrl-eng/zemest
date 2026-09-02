"""Adversarial channel tests — one test per audit PoC (wave F3).

Audit sources: findings/A4-api-routes-2.md (H2), findings/D4-meta-research.md
(G5, G11, M1).

* H2/G5 — tokens in URLs: every Graph call and every API endpoint must
  keep tokens OUT of query strings (they land in proxy/access logs,
  httpx exception reprs, browser history).
* G11 — stale versions: everything speaks Graph v22.0 (Meta rejects
  < v22.0 since 2025-09-09); the old code had v21.0 twice + v18.0 in BFF.
* D4-M1 — WhatsApp media IDs were passed downstream as URLs.
"""
from __future__ import annotations

import ast
import inspect
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

import app.services.facebook_service as fb_service
import app.services.messenger_service as ms_service
import app.services.whatsapp_service as wa_service
from app.services.graph_client import GRAPH_API_VERSION, graph_get, graph_post

APP_DIR = Path(__file__).resolve().parents[2] / "app"


# --------------------------------------------------------------------------- #
# G5 — tokens never in URLs (source-level guarantee)
# --------------------------------------------------------------------------- #
class TestNoTokensInUrls:
    @pytest.mark.parametrize(
        "module_path",
        [
            "services/facebook_service.py",
            "services/messenger_service.py",
            "services/whatsapp_service.py",
            "services/graph_client.py",
            "api/facebook.py",
            "api/channels.py",
            "services/auth_service.py",
        ],
    )
    def test_no_access_token_in_query_params(self, module_path: str):
        """AST guard: no call may pass access_token inside params= kwargs.

        The old pattern — ``params={"access_token": token}`` — put
        long-lived Page tokens into URLs on every Graph call.
        """
        src = (APP_DIR / module_path).read_text()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                for kw in node.keywords:
                    if kw.arg == "params":
                        # dict literal containing an access_token key
                        if isinstance(kw.value, ast.Dict):
                            for key in kw.value.keys:
                                if isinstance(key, ast.Constant) and key.value == "access_token":
                                    raise AssertionError(
                                        f"{module_path}:{node.lineno} passes "
                                        "access_token as a URL query param — "
                                        "token leak (audit A4-H2/G5)"
                                    )

    def test_graph_helpers_send_bearer_header(self):
        """graph_get/graph_post put the token ONLY in the header."""
        import asyncio
        from app.services import graph_client as gc

        captured = {}

        class _FakeResp:
            status_code = 200

            def json(self):
                return {"ok": True}

        class _FakeClient:
            async def get(self, url, params=None, headers=None):
                captured["get"] = (url, params, headers)
                return _FakeResp()

            async def post(self, url, params=None, json=None, headers=None):
                captured["post"] = (url, params, json, headers)
                return _FakeResp()

        async def _fake_get_client():
            return _FakeClient()

        async def _drive():
            orig = gc.get_graph_client
            gc.get_graph_client = _fake_get_client
            try:
                out = await graph_get("me/accounts", token="SECRET-TOK", fields="id")
                assert out == {"ok": True}
                url, params, headers = captured["get"]
                assert "SECRET-TOK" not in url
                assert "SECRET-TOK" not in str(params)
                assert headers.get("Authorization") == "Bearer SECRET-TOK"

                out = await graph_post("123/messages", token="SECRET-TOK", json_body={"a": 1})
                url, params, body, headers = captured["post"]
                assert "SECRET-TOK" not in url
                assert headers.get("Authorization") == "Bearer SECRET-TOK"
            finally:
                gc.get_graph_client = orig

        # asyncio.run() closes the thread's current loop and leaves it
        # unset — pytest-asyncio's session loop must be saved/restored.
        _saved_loop = asyncio.get_event_loop_policy().get_event_loop()
        _loop = asyncio.new_event_loop()
        try:
            _loop.run_until_complete(_drive())
        finally:
            _loop.close()
            asyncio.set_event_loop(_saved_loop)


# --------------------------------------------------------------------------- #
# G11 — version constants
# --------------------------------------------------------------------------- #
class TestGraphVersion:
    def test_single_version_constant_is_v22(self):
        assert GRAPH_API_VERSION == "v22.0", (
            "Graph version must be v22.0 (Meta rejects older since 2025-09-09)"
        )

    def test_whatsapp_url_uses_shared_version(self):
        assert GRAPH_API_VERSION in wa_service.WHATSAPP_API_URL
        assert "v21.0" not in wa_service.WHATSAPP_API_URL

    def test_no_hardcoded_stale_versions(self):
        """No module may hardcode v21.0/v18.0 Graph URLs anymore."""
        offenders = []
        for py in APP_DIR.rglob("*.py"):
            src = py.read_text()
            for stale in ("graph.facebook.com/v21.0", "graph.facebook.com/v18.0"):
                if stale in src:
                    offenders.append(f"{py.name}: {stale}")
        assert not offenders, f"stale Graph versions remain: {offenders}"


# --------------------------------------------------------------------------- #
# D4-M1 — WhatsApp media ID resolution
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
class TestWhatsAppMediaResolution:
    async def test_resolve_media_calls_graph_get(self, monkeypatch):
        """resolve_media turns a media ID into Graph metadata lookup."""
        from app.services import whatsapp_service as ws

        captured = {}

        async def fake_graph_get(path, token, fields=None, params=None):
            captured["path"] = path
            captured["token"] = token
            return {"url": "https://download.example/f.mp4", "mime_type": "video/mp4"}

        import app.services.graph_client as gc
        monkeypatch.setattr(gc, "graph_get", fake_graph_get)

        class FakeTenant:
            wa_access_token = "WA-TOKEN"

        result = await ws.resolve_media(FakeTenant(), "MEDIA123")
        assert result["url"] == "https://download.example/f.mp4"
        assert captured["path"] == "MEDIA123"
        assert captured["token"] == "WA-TOKEN"

    async def test_webhook_resolves_ids_before_agent(self, monkeypatch):
        """The WA webhook path must resolve media IDs to URLs before the
        agent consumes them (the PoC: IDs reached vision as 'URLs')."""
        from app.api import webhook as wh

        resolved_calls = []

        async def fake_resolve_media(tenant, media_id):
            resolved_calls.append(media_id)
            return {"url": f"https://mm.example/{media_id}"}

        class FakeTenant:
            wa_phone_number_id = "PN1"
            wa_access_token = "T"

        class FakeResult:
            def scalar_one_or_none(self):
                return FakeTenant()

        class FakeSession:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def execute(self, q):
                return FakeResult()

            async def commit(self):
                pass

        async def fake_process(**kwargs):
            assert kwargs.get("media_urls") == ["https://mm.example/MEDIA-XYZ"], (
                f"media ID NOT resolved: {kwargs.get('media_urls')}"
            )
            return "duplicate"

        import app.ai.agent as agent_mod
        import app.services.whatsapp_service as ws_mod
        monkeypatch.setattr(agent_mod, "process_customer_message", fake_process)
        monkeypatch.setattr(ws_mod, "resolve_media", fake_resolve_media)
        monkeypatch.setattr(
            ws_mod, "send_whatsapp_message", AsyncMock(return_value=True)
        )
        monkeypatch.setattr(wh, "async_session", lambda: FakeSession())

        msg = {
            "from": "201012345678",
            "id": "wamid.TEST1",
            "type": "image",
            "image": {"id": "MEDIA-XYZ"},
        }
        await wh._process_whatsapp_message("PN1", msg, [])
        assert "MEDIA-XYZ" in resolved_calls


# --------------------------------------------------------------------------- #
# A4-H2 — facebook API endpoints take bodies, not query strings
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
class TestFacebookApiBodies:
    async def test_list_pages_is_post_with_body(self, client, auth_headers):
        """GET /pages?fb_access_token=... must be GONE (token in URL).
        The route is POST with a JSON body now."""
        # Old route: GET with query token — must 404/405, NOT 200.
        resp = await client.get(
            "/api/facebook/pages",
            params={"fb_access_token": "x" * 30},
            headers=auth_headers,
        )
        assert resp.status_code in (404, 405), (
            f"GET /pages still accepted: {resp.status_code}"
        )

    async def test_connect_requires_body(self, client, auth_headers):
        """POST /connect with query-string params must NOT work — FastAPI
        must demand the body model."""
        resp = await client.post(
            "/api/facebook/connect",
            params={
                "page_id": "p1",
                "page_access_token": "t" * 30,
                "page_name": "Shop",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 422, (
            f"query-string connect accepted: {resp.status_code} — tokens in URLs!"
        )
