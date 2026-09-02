"""Shared Meta Graph API client — Bearer-only, v22.0.

Why this module exists (audit A4-H2 + D4 meta research):
- Access tokens previously traveled in **URL query strings**
  (``params={"access_token": ...}``) on every Graph call. Tokens in URLs
  are logged by reverse proxies, nginx access logs, WAFs and browser
  history — the classic credential-leak anti-pattern. Meta's own
  documentation recommends the Authorization header.
- Multiple services hand-rolled their own httpx calls with drifting
  timeouts, error handling and Graph versions (v21.0 hardcoded in three
  places, one of them wrong-host ``www.facebook.com`` for the OAuth
  dialog).

All Graph traffic now funnels through :func:`graph_get` /
:func:`graph_post` here:
- token in the ``Authorization: Bearer`` header only,
- one place to bump the Graph version,
- consistent timeouts and error surfaces,
- a media-ID → URL resolver for WhatsApp Cloud media (webhook payloads
  carry opaque media IDs, not URLs — previously stored raw into
  ``Message.media_urls`` where nothing could download them).
"""
from __future__ import annotations

import logging

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = httpx.Timeout(12.0, connect=8.0)


def _base_url() -> str:
    return get_settings().FB_GRAPH_API_URL


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class GraphAPIError(Exception):
    """Raised on non-200 Graph responses. ``message`` is safe to surface."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


async def graph_get(
    path: str,
    token: str,
    fields: str | None = None,
    params: dict | None = None,
    timeout: httpx.Timeout | None = None,
) -> dict:
    """GET ``{GRAPH}/{path}`` with a Bearer token. Returns parsed JSON.

    Raises :class:`GraphAPIError` on non-200 with a sanitized detail.
    Never logs the token.
    """
    query = dict(params or {})
    if fields:
        query["fields"] = fields
    try:
        async with httpx.AsyncClient(timeout=timeout or _DEFAULT_TIMEOUT) as client:
            resp = await client.get(
                f"{_base_url()}/{path.lstrip('/')}",
                params=query,
                headers=_auth_headers(token),
            )
    except httpx.TimeoutException:
        raise GraphAPIError(504, "Meta Graph API timed out")
    except httpx.HTTPError as e:
        logger.warning(f"Graph GET /{path} transport error: {type(e).__name__}")
        raise GraphAPIError(502, "Could not reach Meta Graph API")

    if resp.status_code != 200:
        detail = _extract_error(resp)
        logger.warning(f"Graph GET /{path} -> {resp.status_code} {detail}")
        raise GraphAPIError(resp.status_code, detail)
    return resp.json()


async def graph_post(
    path: str,
    token: str,
    json: dict | None = None,
    params: dict | None = None,
    timeout: httpx.Timeout | None = None,
) -> dict:
    """POST ``{GRAPH}/{path}`` with a Bearer token. Returns parsed JSON."""
    try:
        async with httpx.AsyncClient(timeout=timeout or _DEFAULT_TIMEOUT) as client:
            resp = await client.post(
                f"{_base_url()}/{path.lstrip('/')}",
                params=params or None,
                json=json,
                headers=_auth_headers(token),
            )
    except httpx.TimeoutException:
        raise GraphAPIError(504, "Meta Graph API timed out")
    except httpx.HTTPError as e:
        logger.warning(f"Graph POST /{path} transport error: {type(e).__name__}")
        raise GraphAPIError(502, "Could not reach Meta Graph API")

    if resp.status_code not in (200, 201):
        detail = _extract_error(resp)
        logger.warning(f"Graph POST /{path} -> {resp.status_code} {detail}")
        raise GraphAPIError(resp.status_code, detail)
    return _safe_json(resp)


async def resolve_media_url(media_id: str, token: str) -> str | None:
    """Resolve a WhatsApp Cloud media ID to its downloadable URL.

    Webhook payloads carry ``{"image": {"id": "1234..."}}`` — the ID is not
    a URL. The real URL requires ``GET /{media_id}`` which returns
    ``{"url": "https://download...", "mime_type":..., "sha256":...}``.
    The returned URL itself requires a Bearer token to download.
    """
    if not media_id:
        return None
    try:
        data = await graph_get(media_id, token)
        return data.get("url")
    except GraphAPIError as e:
        logger.warning(f"Media ID resolution failed for {media_id[:16]}…: {e.detail}")
        return None


def _extract_error(resp: httpx.Response) -> str:
    try:
        err = resp.json().get("error", {})
        return (
            f"{err.get('type', 'GraphError')} {err.get('code', '')}: "
            f"{err.get('message', resp.text[:300])}".strip()
        )
    except Exception:
        return resp.text[:300]


def _safe_json(resp: httpx.Response) -> dict:
    try:
        return resp.json()
    except Exception:
        return {}
