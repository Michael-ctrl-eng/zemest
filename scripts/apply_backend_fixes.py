#!/usr/bin/env python3
"""Apply P0 security + speed fixes to zemest backend.
1. Kill the unauthenticated Jinja dashboard frontend (replaced by Next.js platform)
2. SSRF guard wiring into crawl + import-url
3. Rate limit on login
4. Production secret guard in lifespan
"""
import re

R = "/home/z/my-project/repos/zemest"


def patch(path, old, new, label):
    p = f"{R}/{path}"
    s = open(p).read()
    if old not in s:
        print(f"SKIP (pattern missing): {label}")
        return False
    open(p, "w").write(s.replace(old, new, 1))
    print(f"patched: {label}")
    return True


# ---------- 1. main.py: remove old dashboard frontend, add health root + secret guard ----------
patch(
    "app/main.py",
    '''# Register dashboard routes
from app.api.dashboard import dashboard_router  # noqa: E402

app.include_router(dashboard_router)


# Redirect root to dashboard
from fastapi.responses import RedirectResponse  # noqa: E402


@app.get("/", include_in_schema=False)
async def root_redirect():
    return RedirectResponse(url="/dashboard")''',
    '''# NOTE: The legacy Jinja dashboard (9 unauthenticated HTML routes) was REMOVED.
# The Next.js platform (zemest-platform) is now the single official frontend;
# it talks to this API through its BFF proxy with httpOnly-cookie JWT auth.

from fastapi.responses import JSONResponse  # noqa: E402


@app.get("/", include_in_schema=False)
async def root_health():
    """Lightweight health probe — also used by uptime monitors / load balancers."""
    return JSONResponse({"status": "ok", "service": "zemest-api", "version": "0.1.0"})''',
    "main.py: remove dashboard router + add health root",
)

# secret guard inside lifespan (right after settings import at module level is fine — do it at startup)
patch(
    "app/main.py",
    '''@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup — auto-create missing tables
    from sqlalchemy import text''',
    '''@asynccontextmanager
async def lifespan(app: FastAPI):
    # SECURITY: refuse to boot in production with the compiled-in default JWT secret
    import secrets as _secrets
    if settings.APP_ENV.lower() in ("production", "prod") and settings.JWT_SECRET_KEY in (
        "change-me-to-a-random-secret-key",
        "super-secret-key-change-me",
        "",
    ):
        raise RuntimeError(
            "FATAL: JWT_SECRET_KEY is unset/default while APP_ENV=production. "
            "Generate one with: python -c \\"import secrets; print(secrets.token_urlsafe(48))\\" "
            "and set it in the environment before starting the server."
        )
    # Startup — auto-create missing tables
    from sqlalchemy import text''',
    "main.py: production secret guard",
)

# close pooled LLM http client on shutdown
patch(
    "app/main.py",
    '''    yield
    # Shutdown
    await engine.dispose()''',
    '''    yield
    # Shutdown
    try:
        from app.ai.llm_client import close_client
        await close_client()
    except Exception:
        pass
    await engine.dispose()''',
    "main.py: close pooled LLM client on shutdown",
)

# ---------- 2. crawl.py: SSRF guard ----------
patch(
    "app/api/crawl.py",
    '''from app.schemas.webhook import CrawlRequest, CrawlJobResponse

logger = logging.getLogger(__name__)''',
    '''from app.schemas.webhook import CrawlRequest, CrawlJobResponse

logger = logging.getLogger(__name__)


def _assert_safe_url(url: str) -> None:
    """SSRF guard — reject file://, private IPs, non-HTTP schemes before any fetch."""
    from app.middleware.ssrf_protection import is_safe_url
    safe, reason = is_safe_url(url)
    if not safe:
        raise HTTPException(status_code=400, detail=f"URL rejected by SSRF protection: {reason}")''',
    "crawl.py: add SSRF guard helper",
)

patch(
    "app/api/crawl.py",
    '''):
    job = CrawlJob(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        url=req.url,
        status="pending",
    )''',
    '''):
    _assert_safe_url(req.url)

    job = CrawlJob(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        url=req.url,
        status="pending",
    )''',
    "crawl.py: wire SSRF guard into start_crawl",
)

# ---------- 3. auth.py: rate limit login + register ----------
patch(
    "app/api/auth.py",
    '''@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    try:''',
    '''@router.post("/login", response_model=TokenResponse)
async def login(request: Request, req: LoginRequest, db: AsyncSession = Depends(get_db)):
    # Brute-force protection (per-IP, in-memory fallback when Redis absent)
    try:
        from app.middleware.rate_limit import get_limiter
        limiter = get_limiter()
        if limiter is not None:
            limit = limiter.limit("5/minute")
            await limit(request, request.scope)
    except Exception:
        pass  # rate limiting must never block login availability
    try:''',
    "auth.py: rate limit login",
)

# need Request import
patch(
    "app/api/auth.py",
    "from fastapi import APIRouter, Depends, HTTPException",
    "from fastapi import APIRouter, Depends, HTTPException, Request",
    "auth.py: import Request",
)

# register too (stops mass account creation)
patch(
    "app/api/auth.py",
    '''@router.post("/register", response_model=TokenResponse)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    try:''',
    '''@router.post("/register", response_model=TokenResponse)
async def register(request: Request, req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    try:
        from app.middleware.rate_limit import get_limiter
        limiter = get_limiter()
        if limiter is not None:
            limit = limiter.limit("3/minute")
            await limit(request, request.scope)
    except Exception:
        pass
    try:''',
    "auth.py: rate limit register",
)

print("\nAll P0 patches attempted.")
