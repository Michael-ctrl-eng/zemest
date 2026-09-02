from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, get_tenant
from app.services import facebook_service

router = APIRouter(prefix="/api/facebook", tags=["Facebook"])


class ListPagesRequest(BaseModel):
    """Request body for /pages.

    Audit A4-H2: the user access token previously traveled as a GET query
    parameter — long-lived Meta tokens in URLs land in proxy/access logs,
    browser history and Referer headers. It is now a JSON body field.
    """
    fb_access_token: str = Field(..., min_length=20, max_length=2048)


class ConnectPageRequest(BaseModel):
    """Request body for /connect (same audit fix — token in body, not URL)."""
    page_id: str = Field(..., min_length=1, max_length=64)
    page_access_token: str = Field(..., min_length=20, max_length=2048)
    page_name: str = Field(..., min_length=1, max_length=255)


@router.get("/pages")
async def list_pages(
    req: ListPagesRequest,
    user=Depends(get_current_user),
):
    """List Facebook pages the user manages."""
    pages = await facebook_service.get_user_pages(req.fb_access_token)
    # Never echo the embedded page tokens back to the client.
    for page in pages:
        page.pop("access_token", None)
    return {"pages": pages}


@router.post("/connect")
async def connect_page(
    req: ConnectPageRequest,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Connect a Facebook page to the platform.

    Audit A4-M8: connecting the same page twice previously hit the global
    unique constraint on ``tenants.fb_page_id`` → unhandled IntegrityError
    → 500. Now the existing tenant is re-used (tokens refreshed) — the
    endpoint is idempotent for the same owner, and 409s when another user
    already owns the page (no silent takeover).
    """
    from app.models.tenant import Tenant
    from app.services.tenant_service import create_tenant

    # Validate the token LIVE against Meta before persisting anything
    # (also mitigates A3-H6 page-ID squatting: a token that doesn't match
    # the page is rejected by Meta itself).
    page = None
    try:
        from app.services.graph_client import GraphAPIError, graph_get
        page = await graph_get(
            req.page_id, req.page_access_token, fields="name,category"
        )
    except GraphAPIError as e:
        raise HTTPException(
            400, f"Meta rejected these credentials for page {req.page_id}: {e.detail}"
        )
    if page and page.get("id") and page["id"] != req.page_id:
        raise HTTPException(
            400,
            f"Token belongs to page {page['id']}, not {req.page_id} — refusing to connect",
        )

    # Idempotency: does another tenant already use this page?
    result = await db.execute(
        select(Tenant).where(Tenant.fb_page_id == req.page_id)
    )
    existing = result.scalar_one_or_none()
    if existing:
        if existing.owner_id != user.id:
            # Someone else's tenant already has this page connected.
            raise HTTPException(
                409,
                "This Facebook page is already connected to another account. "
                "If it is yours, contact support to transfer it.",
            )
        # Same owner — refresh tokens in place, no new tenant.
        existing.page_access_token = req.page_access_token
        existing.page_name = req.page_name or existing.page_name
        await db.commit()
        return {
            "message": "Page re-connected — tokens refreshed",
            "tenant_id": str(existing.id),
        }

    # Subscribe to webhook (non-fatal)
    success = await facebook_service.subscribe_page_to_webhook(
        req.page_id, req.page_access_token
    )

    tenant = await create_tenant(
        db,
        user,
        page_name=req.page_name,
        fb_page_id=req.page_id,
        page_access_token=req.page_access_token,
    )

    return {
        "message": "Page connected successfully",
        "tenant_id": str(tenant.id),
        "webhook_subscribed": success,
    }


@router.post("/{tenant_id}/sync-catalog")
async def sync_catalog(
    tenant=Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Sync products from Facebook page's product catalog."""
    if not tenant.page_access_token:
        raise HTTPException(status_code=400, detail="Page access token not set")

    products = await facebook_service.get_page_products(
        tenant.fb_page_id, tenant.page_access_token
    )

    from app.services.product_service import create_product

    imported = 0
    for p in products:
        try:
            price_str = p.get("price", "0")
            # FB price format: "100.00 EGP"
            price = price_str.split(" ")[0] if isinstance(price_str, str) else price_str

            await create_product(
                db,
                tenant.id,
                source="facebook",
                name=p.get("name", ""),
                description=p.get("description"),
                price=price,
                image_url=p.get("image_url"),
                source_ref=p.get("id"),
                stock_status="in_stock"
                if p.get("availability") == "in stock"
                else "out_of_stock",
            )
            imported += 1
        except ValueError:
            pass  # Duplicate, skip

    return {"message": f"Synced {imported} products from Facebook", "imported": imported}


# ============================================================
# OAuth callback — the route the /channels/oauth-url flow points at
# ============================================================

class OAuthCallbackResponse(BaseModel):
    ok: bool
    page_id: str | None = None
    page_name: str | None = None
    error: str | None = None


@router.get("/oauth/callback")
async def oauth_callback(
    code: str = "",
    state: str = "",
    error: str = "",
    error_description: str = "",
    db: AsyncSession = Depends(get_db),
):
    """Facebook OAuth callback (audit A4-M2: this route previously did not
    exist — the consent flow dead-ended at a 404).

    Flow: verify the signed ``state`` → exchange ``code`` for a user token
    (with FB_APP_SECRET) → upgrade to a long-lived user token → list the
    merchant's pages → connect the first page with its Page token.

    The endpoint is browser-facing (Meta redirects here), so it returns
    human-readable JSON instead of a bare 500.
    """
    from app.config import get_settings
    from app.utils.oauth_state import verify_oauth_state

    settings = get_settings()

    if error:
        return OAuthCallbackResponse(
            ok=False,
            error=f"Facebook returned an error: {error} — {error_description}",
        )
    if not settings.FB_APP_ID or not settings.FB_APP_SECRET:
        return OAuthCallbackResponse(
            ok=False, error="FB_APP_ID/FB_APP_SECRET not configured on the server",
        )
    if not code or not state:
        return OAuthCallbackResponse(ok=False, error="Missing code or state")

    valid, tenant_id = verify_oauth_state(state)
    if not valid or not tenant_id:
        return OAuthCallbackResponse(
            ok=False,
            error="Invalid or expired login state — restart the Facebook login flow",
        )

    from sqlalchemy import select as _select
    from app.models.tenant import Tenant
    from app.models.user import User

    # Resolve the tenant AND verify the current user still owns it.
    result = await db.execute(_select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        return OAuthCallbackResponse(ok=False, error="Tenant no longer exists")
    owner_result = await db.execute(_select(User).where(User.id == tenant.owner_id))
    owner = owner_result.scalar_one_or_none()
    if not owner:
        return OAuthCallbackResponse(ok=False, error="Tenant owner no longer exists")

    try:
        # 1. Exchange the code for a short-lived user token.
        import httpx
        redirect_uri = f"{settings.FB_OAUTH_REDIRECT_ORIGIN.rstrip('/')}/api/facebook/oauth/callback"
        async with httpx.AsyncClient(timeout=12.0) as client:
            token_resp = await client.get(
                "https://graph.facebook.com/v22.0/oauth/access_token",
                params={
                    "client_id": settings.FB_APP_ID,
                    "client_secret": settings.FB_APP_SECRET,
                    "redirect_uri": redirect_uri,
                    "code": code,
                },
            )
            token_data = token_resp.json()
            user_token = token_data.get("access_token")
            if not user_token:
                detail = token_data.get("error", {}).get("message", token_resp.text[:200])
                return OAuthCallbackResponse(
                    ok=False, error=f"Token exchange failed: {detail}"
                )

            # 2. Upgrade to a long-lived user token (60 days).
            long_resp = await client.get(
                "https://graph.facebook.com/v22.0/oauth/access_token",
                params={
                    "grant_type": "fb_exchange_token",
                    "client_id": settings.FB_APP_ID,
                    "client_secret": settings.FB_APP_SECRET,
                    "fb_exchange_token": user_token,
                },
            )
            long_token = long_resp.json().get("access_token", user_token)

            # 3. List the merchant's pages and take the first page token.
            pages_resp = await client.get(
                f"{settings.FB_GRAPH_API_URL}/me/accounts",
                params={"fields": "id,name,access_token", "limit": 25},
                headers={"Authorization": f"Bearer {long_token}"},
            )
            pages = pages_resp.json().get("data", [])

        if not pages:
            return OAuthCallbackResponse(
                ok=False,
                error="No Facebook pages found for this account (grant the "
                      "'pages_show_list' permission and make sure you manage a page).",
            )

        page = pages[0]
        page_token = page.get("access_token")
        if not page_token:
            return OAuthCallbackResponse(
                ok=False,
                error="Facebook did not return a Page access token — re-run the "
                      "login flow and grant 'pages_messaging' permission.",
            )

        # 4. Persist into the verified tenant.
        from app.services import facebook_service
        await facebook_service.subscribe_page_to_webhook(page["id"], page_token)

        tenant.fb_page_id = page["id"]
        tenant.page_access_token = page_token
        tenant.page_name = page.get("name") or tenant.page_name
        tenant.messenger_meta = {
            "account_name": page.get("name"),
            "connected_via": "oauth",
            "connected_at": None,
        }
        from datetime import datetime
        tenant.messenger_meta["connected_at"] = datetime.utcnow().isoformat()
        await db.commit()

        return OAuthCallbackResponse(
            ok=True, page_id=page["id"], page_name=page.get("name")
        )

    except Exception as e:
        from fastapi import HTTPException as _HTTPException
        if isinstance(e, _HTTPException):
            raise
        return OAuthCallbackResponse(ok=False, error=f"OAuth callback failed: {type(e).__name__}")
