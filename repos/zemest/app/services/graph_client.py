"""Shared Facebook Graph API client — Bearer-only, keep-alive, v22.0.

Audit fixes (A4-H2 / D4-G5 / D4-G11):
* **G5 — tokens in URLs:** every Graph call used
  ``params={"access_token": token}``. Query strings land in Caddy access
  logs, intermediary proxies, ``httpx`` exception reprs and browser
  history. Graph accepts ``Authorization: Bearer <token>`` — the token
  now travels ONLY in headers.
* **G11 — stale API version:** backend default was v21.0 (config) and
  WhatsApp hardcoded v21.0; Meta rejects calls older than v22.0 since
  2025-09-09. All calls now go through a single version constant.
* **Keep-alive:** one module-scoped ``AsyncClient`` instead of a new
  connection per call (connection churn + TLS handshake on every send).
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

#: The ONLY Graph API version zemest speaks. Meta deprecates versions
#: ~2 years after release and rejects <v22.0 since 2025-09-09.
GRAPH_API_VERSION = "v22.0"

_client: httpx.AsyncClient | None = None
_client_lock = asyncio.Lock()


async def get_graph_client() -> httpx.AsyncClient:
    """Module-scoped keep-alive client (created lazily, closed on shutdown)."""
    global _client
    if _client is None or _client.is_closed:
        async with _client_lock:
            if _client is None or _client.is_closed:
                _client = httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=10.0))
    return _client


async def aclose() -> None:
    """Close the shared client (wired into app lifespan shutdown)."""
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
    _client = None


def _base_url() -> str:
    settings = get_settings()
    url = settings.FB_GRAPH_API_URL.rstrip("/")
    # Re-version whatever the config says: the config's version segment is
    # historical (v21.0 default) — force the single supported constant.
    if "/v" in url:
        head = url.rsplit("/v", 1)[0]
        url = f"{head}/{GRAPH_API_VERSION}"
    return url


async def graph_get(
    path: str,
    token: str,
    fields: str | None = None,
    params: dict[str, Any] | None = None,
) -> dict:
    """GET ``{path}`` with the Bearer token. NEVER puts the token in the URL.

    Returns the parsed JSON dict; ``{}`` on any failure (never raises —
    channel calls are best-effort by design and callers already handle
    empty results).
    """
    client = await get_graph_client()
    query: dict[str, Any] = dict(params or {})
    if fields:
        query["fields"] = fields
    try:
        resp = await client.get(
            f"{_base_url()}/{path.lstrip('/')}",
            params=query,
            headers={"Authorization": f"Bearer {token}"},
        )
        if resp.status_code == 200:
            return resp.json()
        logger.warning("graph_get %s failed: %s %s", path, resp.status_code, resp.text[:200])
        return {}
    except Exception as e:  # noqa: BLE001
        logger.error("graph_get %s error: %s", path, e)
        return {}


async def graph_post(
    path: str,
    token: str,
    json_body: dict | None = None,
    params: dict[str, Any] | None = None,
) -> dict:
    """POST ``{path}`` with the Bearer token (token never in the URL)."""
    client = await get_graph_client()
    try:
        resp = await client.post(
            f"{_base_url()}/{path.lstrip('/')}",
            params=params,
            json=json_body,
            headers={"Authorization": f"Bearer {token}"},
        )
        if resp.status_code == 200:
            return resp.json()
        logger.warning("graph_post %s failed: %s %s", path, resp.status_code, resp.text[:200])
        return {}
    except Exception as e:  # noqa: BLE001
        logger.error("graph_post %s error: %s", path, e)
        return {}


def resolve_whatsapp_media_url(media_id: str) -> str:
    """Graph URL that RESOLVES a WhatsApp media ID to its download payload.

    Audit D4-M1: the codebase passed media IDs around as if they were
    URLs (WhatsApp Cloud API sends ``media_id``s, not URLs). The real
    flow is: ``GET /{media_id}`` (Bearer) -> JSON with a 5-minute
    ``url``, then download THAT with the same Bearer token.
    """
    return f"{_base_url()}/{media_id.lstrip('/')}"
