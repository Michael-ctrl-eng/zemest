"""API endpoints that bridge Zemest to the Postiz sidecar.

These endpoints let our dashboard talk to Postiz through our API,
so the frontend only needs to know about one backend (us).

Endpoints:
- GET  /api/tenants/{id}/postiz/health — check if Postiz is running
- POST /api/tenants/{id}/postiz/login — login to Postiz
- GET  /api/tenants/{id}/postiz/integrations — list connected social accounts
- POST /api/tenants/{id}/postiz/connect/{provider} — get OAuth URL for a provider
- POST /api/tenants/{id}/postiz/posts — create/schedule a post via Postiz
- GET  /api/tenants/{id}/postiz/posts — list posts from Postiz
- GET  /api/tenants/{id}/postiz/posts/{id}/stats — get post statistics
- DELETE /api/tenants/{id}/postiz/posts/{group_id} — delete a post
- GET  /api/tenants/{id}/postiz/best-time — find next free posting slot
- POST /api/tenants/{id}/postiz/generate — AI caption generation via Postiz
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_tenant
from app.models.tenant import Tenant
from app.scheduling.postiz_client import (
    get_postiz_client,
    get_postiz_client_for_tenant,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tenants/{tenant_id}/postiz", tags=["Postiz Scheduler"])


def _require_postiz_session(tenant: Tenant):
    """Per-tenant client; 401 when this tenant has no stored Postiz session.

    SECURITY (audit A4-H1): every authenticated Postiz call uses the TENANT's
    own persisted session token — never a shared process-wide login.
    """
    if not tenant.postiz_token:
        raise HTTPException(
            status_code=401,
            detail="Not logged in to Postiz — connect your scheduling account first",
        )
    return get_postiz_client_for_tenant(tenant)


# ============================================================
# Pydantic schemas
# ============================================================

class PostizLoginRequest(BaseModel):
    email: str
    password: str


class PostizCreatePostRequest(BaseModel):
    integration_id: str = Field(..., description="Postiz integration ID (from list_integrations)")
    caption: str = Field(..., min_length=1, max_length=5000)
    media_urls: list[str] = Field(default_factory=list)
    schedule_at: Optional[str] = Field(None, description="ISO datetime. If None, saves as draft.")


class PostizGenerateRequest(BaseModel):
    prompt: str = Field(..., description="What to write about")
    number_of_posts: int = Field(3, ge=1, le=10)
    platforms: list[str] = Field(default_factory=list)


# ============================================================
# Health & Auth
# ============================================================

@router.get("/health")
async def postiz_health():
    """Check if the Postiz sidecar is running and reachable.

    The internal sidecar URL is not exposed (audit A4-L2).
    """
    client = get_postiz_client()
    healthy = await client.health_check()
    return {"healthy": healthy}


@router.post("/login")
async def postiz_login(
    req: PostizLoginRequest,
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Log THIS tenant into Postiz with their own credentials.

    The session token is persisted on the tenant row (never in the old
    process-wide singleton — audit A4-H1) so every later Postiz call for
    this tenant uses this tenant's session and nothing else.
    """
    client = get_postiz_client_for_tenant(tenant)
    client.set_token(None)  # force a fresh login, not a stale session
    success = await client.login(req.email, req.password)
    if not success or not client.token:
        raise HTTPException(status_code=401, detail="Postiz login failed")

    tenant.postiz_email = req.email
    tenant.postiz_token = client.token
    await db.commit()
    return {"status": "logged_in"}


@router.post("/logout")
async def postiz_logout(
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Forget this tenant's stored Postiz session."""
    from app.scheduling.postiz_client import reset_tenant_client
    reset_tenant_client(str(tenant.id))
    tenant.postiz_token = None
    await db.commit()
    return {"status": "logged_out"}


@router.get("/can-register")
async def postiz_can_register():
    """Check if Postiz allows new registrations."""
    client = get_postiz_client()
    can = await client.check_can_register()
    return {"can_register": can}


# ============================================================
# Integrations (connected social accounts)
# ============================================================

@router.get("/integrations")
async def list_postiz_integrations(
    tenant: Tenant = Depends(get_tenant),
):
    """List social accounts connected to THIS tenant's Postiz session."""
    client = _require_postiz_session(tenant)
    integrations = await client.list_integrations()
    return {"integrations": integrations}


@router.post("/connect/{provider}")
async def get_connect_url(
    provider: str,
    tenant: Tenant = Depends(get_tenant),
):
    """Get the OAuth URL to connect a social account to Postiz.

    Supported providers: facebook, instagram, instagram_standalone, x, linkedin, etc.
    """
    client = _require_postiz_session(tenant)
    url = await client.get_connect_url(provider)
    if not url:
        raise HTTPException(status_code=400, detail=f"Failed to get OAuth URL for {provider}")
    return {"url": url, "provider": provider}


# ============================================================
# Posts
# ============================================================

@router.post("/posts")
async def create_postiz_post(
    req: PostizCreatePostRequest,
    tenant: Tenant = Depends(get_tenant),
):
    """Create/schedule a post via Postiz.

    Postiz handles the actual Graph API call to FB/IG — using THIS
    tenant's own connected integrations only.
    """
    client = _require_postiz_session(tenant)

    # Build the Postiz post payload
    posts_payload = [{
        "integrationId": req.integration_id,
        "content": req.caption,
        "mediaUrls": req.media_urls,
        "settings": {},  # platform-specific settings (can be extended)
    }]

    result = await client.create_post(
        posts=posts_payload,
        schedule_at=req.schedule_at,
    )

    if not result:
        raise HTTPException(status_code=500, detail="Postiz failed to create post")

    return {"status": "created", "postiz_result": result}


@router.get("/posts")
async def list_postiz_posts(
    tenant: Tenant = Depends(get_tenant),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    filter_type: str = Query("scheduled"),
):
    """List posts from Postiz for THIS tenant's session.

    filter_type: 'scheduled', 'published', 'draft', 'failed'
    """
    client = _require_postiz_session(tenant)
    result = await client.list_posts(page=page, limit=limit, filter_type=filter_type)

    if result is None:
        raise HTTPException(status_code=500, detail="Failed to fetch posts from Postiz")

    return result


@router.get("/posts/{post_id}/stats")
async def get_postiz_post_stats(
    post_id: str,
    tenant: Tenant = Depends(get_tenant),
):
    """Get statistics/insights for a specific post via Postiz."""
    client = _require_postiz_session(tenant)
    stats = await client.get_post_statistics(post_id)

    if stats is None:
        raise HTTPException(status_code=500, detail="Failed to fetch stats from Postiz")

    return stats


@router.delete("/posts/{group_id}")
async def delete_postiz_post(
    group_id: str,
    tenant: Tenant = Depends(get_tenant),
):
    """Delete a post from Postiz (by group ID) — in THIS tenant's session."""
    client = _require_postiz_session(tenant)
    success = await client.delete_post(group_id)

    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete post in Postiz")

    return {"status": "deleted", "group_id": group_id}


@router.put("/posts/{post_id}/reschedule")
async def reschedule_postiz_post(
    post_id: str,
    new_date: str = Query(..., description="ISO datetime string"),
    tenant: Tenant = Depends(get_tenant),
):
    """Reschedule a post to a new time."""
    client = _require_postiz_session(tenant)
    success = await client.update_post_date(post_id, new_date, action="update")

    if not success:
        raise HTTPException(status_code=500, detail="Failed to reschedule post in Postiz")

    return {"status": "rescheduled", "post_id": post_id, "new_date": new_date}


@router.get("/best-time")
async def find_postiz_free_slot(
    tenant: Tenant = Depends(get_tenant),
    integration_id: Optional[str] = Query(None),
):
    """Find the next free time slot for posting via Postiz."""
    client = _require_postiz_session(tenant)
    slot = await client.find_free_slot(integration_id)

    if not slot:
        raise HTTPException(status_code=500, detail="Failed to find free slot in Postiz")

    return {"next_free_slot": slot}


# ============================================================
# AI Caption Generation
# ============================================================

@router.post("/generate")
async def generate_postiz_posts(
    req: PostizGenerateRequest,
    tenant: Tenant = Depends(get_tenant),
):
    """Use Postiz's built-in AI to generate post ideas.

    Postiz streams results — this endpoint collects them all and returns
    as a list. Falls back to our own LLM if Postiz is unavailable.
    """
    client = _require_postiz_session(tenant)
    results = await client.generate_posts(
        prompt=req.prompt,
        number_of_posts=req.number_of_posts,
        platforms=req.platforms,
    )

    if not results:
        # Fallback to our own LLM
        try:
            from app.ai.llm_client import chat_completion_with_usage
            import json
            import re

            style_hint = ""
            if tenant.style_profile:
                p = tenant.style_profile
                style_hint = f"Tone: {p.get('tone', 'friendly')}. Emoji: {p.get('emoji_frequency', 'low')}."

            llm_result = await chat_completion_with_usage([
                {"role": "system", "content": "You are a social media content creator. Return valid JSON only."},
                {"role": "user", "content": f"""Generate {req.number_of_posts} social media post captions about: {req.prompt}
                {style_hint}
                Return JSON: {{"posts": ["caption1", "caption2", ...]}}"""},
            ])

            # Balanced extraction (audit A6-H3 class: greedy \{.*\} spans to
            # the last brace and fails whenever trailing prose has a brace).
            from app.utils.safe_json import extract_first_json_object
            data, _s, _e = extract_first_json_object(llm_result.content)
            if data:
                return {"posts": data.get("posts", []), "source": "zemest_fallback"}
        except Exception as e:
            logger.error(f"Fallback caption generation failed: {e}")

        raise HTTPException(status_code=500, detail="Postiz AI generation failed and fallback also failed")

    return {"posts": results, "source": "postiz"}
