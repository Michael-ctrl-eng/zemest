from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.config import get_settings

settings = get_settings()


@asynccontextmanager
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
            "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(48))\" "
            "and set it in the environment before starting the server."
        )
    # Startup — auto-create missing tables
    from sqlalchemy import text
    from app.database import engine
    try:
        async with engine.begin() as conn:
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS token_usage (
                    id UUID PRIMARY KEY,
                    tenant_id UUID NOT NULL REFERENCES tenants(id),
                    usage_type VARCHAR(20) NOT NULL,
                    model VARCHAR(100) NOT NULL,
                    prompt_tokens INTEGER DEFAULT 0,
                    completion_tokens INTEGER DEFAULT 0,
                    total_tokens INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_token_usage_tenant ON token_usage(tenant_id)"))
            # Add missing columns (idempotent)
            migrations = [
                ("orders", "payment_phone_last2", "VARCHAR(10)"),
                ("orders", "payment_trx_id", "VARCHAR(50)"),
                ("tenants", "delivery_inside_cairo", "NUMERIC(10,2) DEFAULT 35"),
                ("tenants", "delivery_outside_cairo", "NUMERIC(10,2) DEFAULT 60"),
                ("tenants", "free_delivery_above", "NUMERIC(10,2)"),
                ("tenants", "payment_methods", "JSONB"),
                ("tenants", "order_api_config", "JSONB"),
                ("tenants", "style_profile", "JSONB"),
                ("tenants", "knowledge_base", "JSONB"),
                ("tenants", "knowledge_built_at", "TIMESTAMP"),
                ("tenants", "ig_user_id", "VARCHAR(64)"),
                ("tenants", "ig_access_token", "TEXT"),
                ("tenants", "wa_phone_number_id", "VARCHAR(64)"),
                ("tenants", "wa_access_token", "TEXT"),
                ("tenants", "wa_waba_id", "VARCHAR(64)"),
                ("tenants", "owner_psid", "VARCHAR(64)"),
                ("customers", "channel", "VARCHAR(20) DEFAULT 'messenger'"),
                ("customers", "governorate", "VARCHAR(100)"),
                ("customers", "city", "VARCHAR(100)"),
                ("customers", "area", "VARCHAR(100)"),
                ("customers", "address_detail", "TEXT"),
                ("messages", "channel", "VARCHAR(20) DEFAULT 'messenger'"),
                ("messages", "media_urls", "JSON"),
                ("orders", "api_status", "VARCHAR(20)"),
                ("orders", "api_response", "TEXT"),
                ("orders", "api_status_code", "INTEGER"),
                ("orders", "api_called_at", "TIMESTAMP"),
                ("orders", "api_external_id", "VARCHAR(100)"),
                # --- Admin / security tables (idempotent) ---
                ("users", "is_superadmin", "BOOLEAN DEFAULT FALSE"),
            ]
            for table, col, coltype in migrations:
                try:
                    await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {coltype}"))
                except Exception:
                    pass

            # Auto-create admin tables if missing (idempotent — safe for SQLite tests too)
            try:
                await conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS site_users (
                        id UUID PRIMARY KEY,
                        user_id UUID NOT NULL UNIQUE REFERENCES users(id),
                        is_blocked BOOLEAN DEFAULT FALSE,
                        blocked_reason TEXT,
                        blocked_at TIMESTAMP,
                        blocked_by UUID REFERENCES users(id),
                        last_ip VARCHAR(64),
                        last_country VARCHAR(64),
                        last_country_code VARCHAR(8),
                        last_city VARCHAR(64),
                        last_latitude DOUBLE PRECISION,
                        last_longitude DOUBLE PRECISION,
                        last_user_agent TEXT,
                        last_device_type VARCHAR(32),
                        last_seen TIMESTAMP,
                        created_at TIMESTAMP DEFAULT NOW(),
                        updated_at TIMESTAMP DEFAULT NOW()
                    )
                """))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_site_users_user_id ON site_users(user_id)"))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_site_users_blocked ON site_users(is_blocked)"))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_site_users_country ON site_users(last_country)"))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_site_users_last_seen ON site_users(last_seen)"))

                await conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS ip_bans (
                        id UUID PRIMARY KEY,
                        ip_or_cidr VARCHAR(64) NOT NULL UNIQUE,
                        reason TEXT,
                        banned_by UUID NOT NULL REFERENCES users(id),
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_ip_bans_ip_or_cidr ON ip_bans(ip_or_cidr)"))

                await conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS user_sessions (
                        id UUID PRIMARY KEY,
                        user_id UUID NOT NULL REFERENCES users(id),
                        ip_address VARCHAR(64) NOT NULL,
                        country VARCHAR(64),
                        country_code VARCHAR(8),
                        city VARCHAR(64),
                        latitude DOUBLE PRECISION,
                        longitude DOUBLE PRECISION,
                        user_agent TEXT,
                        device_type VARCHAR(32),
                        login_at TIMESTAMP DEFAULT NOW(),
                        logout_at TIMESTAMP,
                        last_activity TIMESTAMP DEFAULT NOW(),
                        is_active BOOLEAN DEFAULT TRUE
                    )
                """))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id ON user_sessions(user_id)"))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_user_sessions_ip ON user_sessions(ip_address)"))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_user_sessions_country ON user_sessions(country)"))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_user_sessions_login_at ON user_sessions(login_at)"))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_user_sessions_active ON user_sessions(is_active)"))

                await conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS admin_audit_log (
                        id BIGSERIAL PRIMARY KEY,
                        admin_id UUID NOT NULL REFERENCES users(id),
                        action VARCHAR(64) NOT NULL,
                        target_type VARCHAR(32),
                        target_id VARCHAR(64),
                        metadata_ JSON,
                        ip VARCHAR(64),
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_audit_log_admin_id ON admin_audit_log(admin_id)"))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_audit_log_action ON admin_audit_log(action)"))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_audit_log_target_id ON admin_audit_log(target_id)"))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_audit_log_created_at ON admin_audit_log(created_at)"))
            except Exception:
                pass  # SQLite / older Postgres may not support some types — ignore
    except Exception:
        pass  # DB may not be ready yet
    yield
    # Shutdown
    try:
        from app.ai.llm_client import close_client
        await close_client()
    except Exception:
        pass
    await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    description="Zemest — AI agents for moderating Facebook, Instagram, and WhatsApp. "
    "Two models: Rabbit v1 (Arabic specialist) and Rat v1 (English specialist). "
    "Understands voice, images, and text. Auto-trained on your chat history.",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# --------------------------------------------------------------------------- #
# Security middleware — added in order so the OUTERMOST wrapper is the one
# we want applied FIRST on the request path. Starlette executes middleware
# in *reverse* registration order (last registered = outermost), so we
# register them in REVERSE here to get this request flow:
#
#   1. SecurityHeaders   (tag EVERY response — incl. 429s — with X-Frame-Options etc.)
#   2. BotDetection      (log-only; never blocks)
#   3. IPBanMiddleware   (block banned IPs/CIDRs from admin tool)
#   4. RateLimit         (slowapi — 429 on abuse, per-IP AND per-tenant keys)
#   5. SessionMiddleware (cookie signing for the admin panel)
#
# Each registration is wrapped in try/except so a missing dep / misconfig
# in ONE middleware never blocks app boot — the rest still come up.
# --------------------------------------------------------------------------- #
from app.middleware.security_headers import SecurityHeadersMiddleware  # noqa: E402
from app.middleware.bot_detection import BotDetectionMiddleware  # noqa: E402

# SessionMiddleware — required by sqladmin's AuthenticationBackend (and the
# custom admin dashboard uses the same session for the JWT flag).
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.JWT_SECRET_KEY,
    session_cookie="_zemest_session",
    same_site="lax",
    https_only=False,
)

# IP ban middleware — fail-open (requests pass if cache cannot refresh).
from app.middleware.security import IPBanMiddleware  # noqa: E402

app.add_middleware(IPBanMiddleware)

# Bot detection — log-only, never blocks. Tagged on request.state so
# downstream middleware/routes can read request.state.is_likely_bot.
app.add_middleware(BotDetectionMiddleware)

# slowapi rate limiter — wires the SlowAPIMiddleware + 429 exception handler
# with a per-IP-OR-per-tenant key function. Falls back to in-memory storage
# if REDIS_URL is unset (handy for tests / local dev).
try:  # pragma: no cover — soft dependency
    from app.middleware.rate_limit import setup_rate_limiting
    setup_rate_limiting(app)
except Exception:  # noqa: BLE001
    import logging as _logging
    _logging.getLogger(__name__).warning(
        "Rate limiting disabled — slowapi setup failed", exc_info=True
    )

# Security headers — added LAST so it's the OUTERMOST wrapper and every
# response (including 429s from the rate limiter and 403s from IP ban)
# gets HSTS / X-Frame-Options / CSP / Referrer-Policy.
app.add_middleware(SecurityHeadersMiddleware)

# Mount static files for dashboard
app.mount("/static", StaticFiles(directory="dashboard/static"), name="static")

# Jinja2 templates
templates = Jinja2Templates(directory="dashboard/templates")

# Register API routes
from app.api.router import api_router  # noqa: E402

app.include_router(api_router)

# Register admin REST API (block/unblock/ip-bans/analytics/audit-log).
# Must be included BEFORE setup_admin so the routes exist regardless of
# sqladmin's mount ordering.
from app.admin.api import router as admin_api_router  # noqa: E402

app.include_router(admin_api_router)

# Register custom admin dashboard route — must run BEFORE setup_admin so
# `/_admin/dashboard` is matched before sqladmin's mount on `/_admin`.
from app.admin.dashboard import router as admin_dashboard_router  # noqa: E402

app.include_router(admin_dashboard_router)

# Mount the sqladmin panel at /_admin.
from app.database import engine  # noqa: E402
from app.admin.admin_panel import setup_admin  # noqa: E402

setup_admin(app, engine)

# NOTE: The legacy Jinja dashboard (9 unauthenticated HTML routes) was REMOVED.
# The Next.js platform (zemest-platform) is now the single official frontend;
# it talks to this API through its BFF proxy with httpOnly-cookie JWT auth.

from fastapi.responses import JSONResponse  # noqa: E402


@app.get("/", include_in_schema=False)
async def root_health():
    """Lightweight health probe — also used by uptime monitors / load balancers."""
    return JSONResponse({"status": "ok", "service": "zemest-api", "version": "0.1.0"})
