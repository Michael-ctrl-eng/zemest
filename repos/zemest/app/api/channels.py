"""Unified channel management API — connect, disconnect, status, live test.

One endpoint family for all three platforms (Messenger, Instagram, WhatsApp):

- GET  /api/tenants/{id}/channels              → live status of every channel
- POST /api/tenants/{id}/channels/messenger    → connect a Facebook Page (validates live)
- POST /api/tenants/{id}/channels/instagram    → connect an IG professional account (validates live)
- POST /api/tenants/{id}/channels/whatsapp     → connect a WhatsApp Business number (validates live)
- DEL  /api/tenants/{id}/channels/{platform}   → disconnect
- POST /api/tenants/{id}/channels/{platform}/test → send a REAL test message through the platform
- GET  /api/tenants/{id}/channels/oauth-url    → Facebook OAuth URL (when FB_APP_ID configured)

Every connect call validates the credentials LIVE against the Meta Graph API
before anything is stored — an invalid token returns the real Graph error.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.dependencies import get_tenant
from app.models.tenant import Tenant

settings = get_settings()
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tenants/{tenant_id}/channels", tags=["Channels"])

GRAPH = settings.FB_GRAPH_API_URL


# ============================================================
# Pydantic schemas
# ============================================================

class MessengerConnectRequest(BaseModel):
    """Connect a Facebook Page. Page ID optional — with a Page access token,
    Graph /me IS the page, so we resolve it automatically."""
    page_access_token: str = Field(..., min_length=10, max_length=2000)
    page_id: Optional[str] = Field(None, max_length=64)


class InstagramConnectRequest(BaseModel):
    ig_user_id: str = Field(..., min_length=3, max_length=64)
    access_token: str = Field(..., min_length=10, max_length=2000)


class WhatsAppConnectRequest(BaseModel):
    phone_number_id: str = Field(..., min_length=3, max_length=64)
    access_token: str = Field(..., min_length=10, max_length=2000)
    waba_id: Optional[str] = Field(None, max_length=64)


class TestMessageRequest(BaseModel):
    recipient: Optional[str] = None  # defaults to owner PSID / business phone
    text: str = Field("Zemest test message — your channel is connected.", max_length=500)


# ============================================================
# Live Graph API validation helpers (the "insanely real" part)
# ============================================================

async def _graph_get(path: str, token: str, fields: str) -> dict:
    """GET from the Graph API via the shared Bearer-only client (token
    never in the URL — audit A4-H2/D4-G5). Returns the parsed JSON on 200.
    Raises HTTPException with the REAL Graph error message otherwise."""
    from app.services.graph_client import get_graph_client

    try:
        client = await get_graph_client()
        resp = await client.get(
            f"{GRAPH}/{path}",
            params={"fields": fields},
            headers={"Authorization": f"Bearer {token}"},
        )
    except httpx.TimeoutException:
        raise HTTPException(504, "Meta Graph API timed out — try again")
    except httpx.HTTPError as e:
        raise HTTPException(502, f"Could not reach Meta Graph API: {e}")

    if resp.status_code != 200:
        # Surface the real Graph error to the user
        detail = "Meta rejected these credentials"
        try:
            err = resp.json().get("error", {})
            detail = f"{err.get('type', 'GraphError')} {err.get('code', '')}: {err.get('message', resp.text[:300])}".strip()
        except Exception:
            detail = resp.text[:300]
        logger.warning(f"Graph validation failed on /{path}: {resp.status_code} {detail}")
        raise HTTPException(400, detail)
    return resp.json()


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None


# ============================================================
# Channel status — one call, all platforms
# ============================================================

@router.get("")
async def channel_status(
    tenant: Tenant = Depends(get_tenant),
):
    """Live connection status for every channel.

    Reads stored connection metadata + re-checks the token LIVE against
    Graph API so a revoked token shows as disconnected/errored immediately.
    """
    platforms: dict[str, dict] = {}

    # ---- Messenger (Facebook Page) ----
    if tenant.fb_page_id and tenant.page_access_token:
        live = None
        try:
            live = await _graph_get(tenant.fb_page_id, tenant.page_access_token, "name,followers_count,category")
        except HTTPException as e:
            live = {"_error": e.detail}
        platforms["messenger"] = {
            "connected": not live.get("_error"),
            "page_id": tenant.fb_page_id,
            "account_name": live.get("name") or (tenant.messenger_meta or {}).get("account_name") or tenant.page_name,
            "category": live.get("category"),
            "followers": live.get("followers_count"),
            "error": live.get("_error"),
            "connected_at": (tenant.messenger_meta or {}).get("connected_at"),
        }
    else:
        platforms["messenger"] = {"connected": False, "error": None}

    # ---- Instagram ----
    if tenant.ig_user_id and tenant.ig_access_token:
        live = None
        try:
            live = await _graph_get(tenant.ig_user_id, tenant.ig_access_token, "username,profile_picture_url,followers_count")
        except HTTPException as e:
            live = {"_error": e.detail}
        platforms["instagram"] = {
            "connected": not live.get("_error"),
            "ig_user_id": tenant.ig_user_id,
            "account_name": live.get("username") or (tenant.instagram_meta or {}).get("account_name"),
            "avatar": live.get("profile_picture_url"),
            "followers": live.get("followers_count"),
            "error": live.get("_error"),
            "connected_at": (tenant.instagram_meta or {}).get("connected_at"),
        }
    else:
        platforms["instagram"] = {"connected": False, "error": None}

    # ---- WhatsApp ----
    if tenant.wa_phone_number_id and tenant.wa_access_token:
        live = None
        try:
            live = await _graph_get(tenant.wa_phone_number_id, tenant.wa_access_token, "display_phone_number,verified_name,quality_rating")
        except HTTPException as e:
            live = {"_error": e.detail}
        platforms["whatsapp"] = {
            "connected": not live.get("_error"),
            "phone_number_id": tenant.wa_phone_number_id,
            "display_phone_number": live.get("display_phone_number") or (tenant.whatsapp_meta or {}).get("display_phone_number"),
            "verified_name": live.get("verified_name"),
            "quality_rating": live.get("quality_rating"),
            "error": live.get("_error"),
            "connected_at": (tenant.whatsapp_meta or {}).get("connected_at"),
        }
    else:
        platforms["whatsapp"] = {"connected": False, "error": None}

    return {
        "platforms": platforms,
        # What the merchant must paste into the Meta App dashboard → Webhooks
        "webhook_urls": {
            "messenger": "/api/webhook/messenger",
            "instagram": "/api/webhook/instagram",
            "whatsapp": "/api/webhook/whatsapp",
        },
        "verify_token_configured": bool(settings.FB_VERIFY_TOKEN),
        "oauth": {
            "ready": bool(settings.FB_APP_ID),
        },
    }


# ============================================================
# Connect — Messenger (Facebook Page)
# ============================================================

@router.post("/messenger")
async def connect_messenger(
    req: MessengerConnectRequest,
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Connect a Facebook Page with a Page access token.

    1. Validates the token LIVE (Graph /me with a page token returns the page).
    2. Subscribes the page to our webhook (messages, reads, echoes …).
    3. Persists credentials + connection metadata.
    """
    page_id = req.page_id or "me"
    page = await _graph_get(page_id, req.page_access_token, "name,followers_count,category,link")

    resolved_id = page.get("id") or (req.page_id if req.page_id != "me" else None)
    if not resolved_id:
        raise HTTPException(400, "Could not resolve the Page ID from this token")

    # Try to subscribe the page to webhooks (real call; non-fatal if the
    # Meta app is not yet configured — we report the result honestly).
    from app.services.facebook_service import subscribe_page_to_webhook
    try:
        subscribed = await subscribe_page_to_webhook(resolved_id, req.page_access_token)
    except Exception as e:
        logger.warning(f"Webhook subscription error: {e}")
        subscribed = False

    tenant.fb_page_id = resolved_id
    tenant.page_access_token = req.page_access_token
    tenant.page_name = page.get("name") or tenant.page_name
    tenant.messenger_meta = {
        "account_name": page.get("name"),
        "category": page.get("category"),
        "followers": page.get("followers_count"),
        "connected_at": _iso(datetime.utcnow()),
        "webhook_subscribed": subscribed,
    }
    await db.commit()

    return {
        "connected": True,
        "page_id": resolved_id,
        "page_name": page.get("name"),
        "followers": page.get("followers_count"),
        "webhook_subscribed": subscribed,
        "webhook_note": None if subscribed else
            "Page connected and token verified. Webhook subscription needs the Meta App "
            f"(App ID) configured on the server — set FB_APP_ID/FB_APP_SECRET, then reconnect.",
    }


# ============================================================
# Connect — Instagram
# ============================================================

@router.post("/instagram")
async def connect_instagram(
    req: InstagramConnectRequest,
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Connect an Instagram professional account via the Instagram Graph API."""
    ig = await _graph_get(req.ig_user_id, req.access_token, "username,profile_picture_url,followers_count")

    tenant.ig_user_id = req.ig_user_id
    tenant.ig_access_token = req.access_token
    tenant.instagram_meta = {
        "account_name": ig.get("username"),
        "avatar": ig.get("profile_picture_url"),
        "followers": ig.get("followers_count"),
        "connected_at": _iso(datetime.utcnow()),
    }
    await db.commit()

    return {
        "connected": True,
        "ig_user_id": req.ig_user_id,
        "username": ig.get("username"),
        "followers": ig.get("followers_count"),
    }


# ============================================================
# Connect — WhatsApp
# ============================================================

@router.post("/whatsapp")
async def connect_whatsapp(
    req: WhatsAppConnectRequest,
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Connect a WhatsApp Business Cloud API number.

    Validates the phone-number credentials live: Graph returns
    display_phone_number + verified_name for a valid phone_number_id.
    """
    wa = await _graph_get(req.phone_number_id, req.access_token, "display_phone_number,verified_name,quality_rating")

    tenant.wa_phone_number_id = req.phone_number_id
    tenant.wa_access_token = req.access_token
    if req.waba_id:
        tenant.wa_waba_id = req.waba_id
    tenant.whatsapp_meta = {
        "display_phone_number": wa.get("display_phone_number"),
        "verified_name": wa.get("verified_name"),
        "quality_rating": wa.get("quality_rating"),
        "connected_at": _iso(datetime.utcnow()),
    }
    await db.commit()

    return {
        "connected": True,
        "display_phone_number": wa.get("display_phone_number"),
        "verified_name": wa.get("verified_name"),
        "quality_rating": wa.get("quality_rating"),
    }


# ============================================================
# Disconnect
# ============================================================

@router.delete("/{platform}")
async def disconnect_channel(
    platform: str,
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    if platform == "messenger":
        tenant.fb_page_id = None
        tenant.page_access_token = None
        tenant.messenger_meta = None
    elif platform == "instagram":
        tenant.ig_user_id = None
        tenant.ig_access_token = None
        tenant.instagram_meta = None
    elif platform == "whatsapp":
        tenant.wa_phone_number_id = None
        tenant.wa_access_token = None
        tenant.wa_waba_id = None
        tenant.whatsapp_meta = None
    else:
        raise HTTPException(404, f"Unknown platform '{platform}'")

    await db.commit()
    return {"connected": False, "platform": platform}


# ============================================================
# Test — send a REAL message through the platform
# ============================================================

@router.post("/{platform}/test")
async def test_channel(
    platform: str,
    req: TestMessageRequest,
    tenant: Tenant = Depends(get_tenant),
):
    """Send a real message through the connected channel and report the
    actual platform API response — the fastest possible proof the wiring works."""
    if platform == "messenger":
        if not tenant.page_access_token:
            raise HTTPException(400, "Messenger is not connected")
        recipient = req.recipient or tenant.owner_psid
        if not recipient:
            raise HTTPException(
                400,
                "No test recipient: set your own Messenger PSID in Settings (owner PSID) "
                "or pass a recipient PSID. Message your page once from your own account "
                "and the PSID is captured automatically.",
            )
        from app.services.messenger_service import send_text_message
        return await send_text_message(tenant.page_access_token, recipient, req.text)

    elif platform == "instagram":
        if not tenant.ig_access_token:
            raise HTTPException(400, "Instagram is not connected")
        recipient = req.recipient or tenant.owner_psid
        if not recipient:
            raise HTTPException(
                400,
                "No test recipient: pass the IG-scoped ID of the account to message.",
            )
        from app.services.messenger_service import send_text_message
        return await send_text_message(tenant.ig_access_token, recipient, req.text)

    elif platform == "whatsapp":
        if not tenant.wa_access_token or not tenant.wa_phone_number_id:
            raise HTTPException(400, "WhatsApp is not connected")
        recipient = req.recipient or (
            tenant.business_phone.lstrip("+").replace(" ", "") if tenant.business_phone else None
        )
        if not recipient:
            raise HTTPException(
                400,
                "No test recipient: add your business phone in Settings or pass a recipient number.",
            )
        from app.services.whatsapp_service import send_whatsapp_message
        ok = await send_whatsapp_message(tenant, recipient, req.text)
        return {"sent": ok, "recipient": recipient}

    raise HTTPException(404, f"Unknown platform '{platform}'")


# ============================================================
# OAuth URL — Login with Facebook flow
# ============================================================

@router.get("/oauth-url")
async def oauth_url(
    request_url: str = "https://localhost:3000",
    tenant: Tenant = Depends(get_tenant),
):
    """Build the Facebook OAuth consent URL for this tenant.

    Works only when FB_APP_ID is configured on the server. The frontend uses
    `ready:false` to fall back to the manual token form.
    """
    if not settings.FB_APP_ID:
        return {"ready": False, "reason": "FB_APP_ID not configured on the server yet"}

    redirect = f"{request_url.rstrip('/')}/api/zemest/facebook/oauth/callback"
    scopes = [
        "pages_show_list",
        "pages_messaging",
        "pages_manage_metadata",
        "pages_read_engagement",
        "pages_manage_posts",
        "instagram_basic",
        "instagram_manage_messages",
        "business_management",
    ]
    from urllib.parse import urlencode
    params = urlencode({
        "client_id": settings.FB_APP_ID,
        "redirect_uri": redirect,
        "state": f"tenant:{tenant.id}",
        "response_type": "code",
        "scope": ",".join(scopes),
    })
    return {"ready": True, "url": f"https://www.facebook.com/v21.0/dialog/oauth?{params}"}
