# Z1 — Architecture & Bootstrap Analysis (zemest backend)

**Task ID:** Z1 · **Agent:** general-purpose (architecture) · **Mode:** research-only (no code modified)
**Scope:** `app/main.py`, `app/config.py`, `app/database.py`, `app/dependencies.py`, `app/__init__.py`, `seed.py`, `Dockerfile`, `docker-compose.yml`, `init.sql`, `requirements.txt`, `pytest.ini`, `alembic.ini`, `alembic/env.py`, 3 migrations, `.dockerignore`, `.gitignore`, git history.
**Git history:** single commit `926f2f5 "Initial commit: Zemest — AI agents for social media moderation"` — no evolution visible in VCS; all history is inferred from migration timestamps (2026-03-17 → 2026-08-26).

---

## 1. Application Bootstrap Flow (`app/main.py`, 268 lines)

### Module import phase (in order)
1. `settings = get_settings()` (main.py:10) — cached settings singleton via `@lru_cache`.
2. **`lifespan(app: FastAPI) -> AsyncContextManager`** (main.py:13-157) — the ONLY lifespan hook:
   - **Startup DDL block** (main.py:18-154): opens `engine.begin()` and runs ~150 lines of raw SQL DDL:
     - `CREATE TABLE IF NOT EXISTS token_usage` + tenant index (main.py:20-32).
     - **29 idempotent `ALTER TABLE ... ADD COLUMN` statements** in a `(table, col, coltype)` tuple loop, each wrapped in its own `try/except Exception: pass` (main.py:34-70) — covers orders (2), tenants (15!), customers (5), messages (2), orders-API (5), users (1).
     - Creates 4 admin tables if missing: `site_users`, `ip_bans`, `user_sessions`, `admin_audit_log` + 13 indexes (main.py:73-150), all inside one broad `try/except pass` "SQLite / older Postgres may not support some types — ignore" (main.py:151-152).
     - **Outermost** `try/except Exception: pass` (main.py:153-154) with comment "DB may not be ready yet" — the app boots even if the DB is unreachable.
   - `yield` (main.py:155).
   - **Shutdown:** `await engine.dispose()` (main.py:157).
3. **`app = FastAPI(...)`** (main.py:160-169) — title from settings, marketing description ("Rabbit v1 Arabic / Rat v1 English specialists"), `version="0.1.0"`, docs at `/docs` + `/redoc` **unconditionally enabled**, lifespan wired.

### Middleware registration (exact order, main.py:191-223)
Starlette executes middleware in **reverse registration order** (last added = outermost). Registration sequence:

| # registered | Middleware | Line | Role |
|---|---|---|---|
| 1 (innermost) | `SessionMiddleware` | 191-197 | cookie signing for admin panel + sqladmin; `secret_key=settings.JWT_SECRET_KEY`, cookie `_zemest_session`, `same_site="lax"`, **`https_only=False`** |
| 2 | `IPBanMiddleware` | 200-202 | 403 banned IPs/CIDRs; fail-open if cache unreachable |
| 3 | `BotDetectionMiddleware` | 204-206 | log-only; tags `request.state.is_likely_bot` |
| 4 | `SlowAPIMiddleware` | via `setup_rate_limiting(app)` @213 (rate_limit.py:149) | 429 limiter; key = `tenant:{id}` for JWT'd requests else `ip:{addr}`; Redis storage w/ in-memory fallback; custom 429 handler with `Retry-After` |
| 5 (outermost) | `SecurityHeadersMiddleware` | 223 | HSTS/X-Frame-Options/CSP/Referrer-Policy on **every** response incl. 429s |

- Rate-limit setup wrapped in `try/except` so a slowapi failure disables limiting but never blocks boot (main.py:211-218).
- **ⓘ Doc/comment mismatch (main.py:171-185):** the comment claims request order `SecurityHeaders → BotDetection → IPBan → RateLimit → Session`, but the *actual* onion is `SecurityHeaders → **RateLimit** → BotDetection → IPBan → Session`. The stated intent "IP ban blocks before rate limiter" is violated — a banned IP is rate-limited (429, consuming budget) before being 403'd.
- **No CORS, TrustedHost, GZip, or proxy-headers middleware anywhere** (verified by grep). No `--proxy-headers` in uvicorn CMD → behind a reverse proxy, `get_remote_address` sees the proxy IP and rate limiting lumps all clients together.

### Mounts, routers, and routes (registration order matters — documented in comments)
1. `app.mount("/static", StaticFiles(directory="dashboard/static"))` (main.py:226) — relative path; verified dirs `dashboard/static/{css,js}` and `dashboard/templates/` exist at repo root.
2. `templates = Jinja2Templates(directory="dashboard/templates")` (main.py:229) — module-level instance (routes appear to build their own; this one is effectively unused in main.py).
3. `app.include_router(api_router)` (main.py:232-234) — 14 sub-routers: auth, tenants, products, orders, conversations, customers, address, crawl, webhook, facebook, test_chat, style_learning, scheduling, postiz (api/router.py:3-21).
4. `app.include_router(admin_api_router)` (main.py:239-241) — admin REST (block/unblock/ip-bans/analytics/audit-log).
5. `app.include_router(admin_dashboard_router)` (main.py:245-247) — custom `/_admin/dashboard`, deliberately before sqladmin mount so it wins the path match.
6. `setup_admin(app, engine)` (main.py:250-253) — mounts sqladmin at `/_admin` (Admin instance, custom auth backend per admin_panel.py:1-391).
7. `app.include_router(dashboard_router)` (main.py:256-258) — tenant dashboard.
8. **`root_redirect()`** — `async def root_redirect() -> RedirectResponse` (main.py:265-267): `GET /` → 302 `/dashboard`, hidden from OpenAPI.

### Exception handlers
Only one custom handler app-wide: `RateLimitExceeded` → JSON 429 + `Retry-After`/`X-RateLimit-Limit` (rate_limit.py:113-131, registered at 145). No global generic-exception handlers; FastAPI defaults otherwise.

**Verdict:** bootstrap is deliberate and well-commented (ordering rationale, fail-open philosophy), but carries a **runtime-DDL anti-pattern** duplicating Alembic's job 1:1 (see §4/§8) with triple-nested silent exception swallowing.

---

## 2. Configuration System (`app/config.py`, 71 lines)

Single `Settings(BaseSettings)` (pydantic-settings), `@lru_cache`d `get_settings()` (config.py:68-70). `model_config = {"env_file": ".env", "extra": "ignore"}` (config.py:65) — no `env_prefix`, no `case_sensitive`, no per-env validation, **no `SecretStr`** — every secret is a plain `str` (repr/log-leakable).

| Setting | Type | Default (env var name = setting name) | Purpose | Risk if misconfigured |
|---|---|---|---|---|
| `APP_NAME` | str | `"Zemest"` | FastAPI title | cosmetic |
| `APP_ENV` | str | `"development"` | environment label | **never checked anywhere** — "production" enables zero hardening |
| `APP_DEBUG` | bool | `False` | `engine.echo` (SQL logging) | SQL + bound params (PII/addresses) dumped to logs when true |
| `APP_HOST` | str | `0.0.0.0` | bind host | 0.0.0.0 in dev exposes service |
| `APP_PORT` | int | `8000` | bind port | — |
| `DATABASE_URL` | str | `postgresql+asyncpg://zemest:zemest_secret@localhost:5432/zemest` | async engine | **DB password in source default**; wrong host = silent boot failure (lifespan swallows) |
| `DATABASE_URL_SYNC` | str | `postgresql://zemest:zemest_secret@localhost:5432/zemest` | Alembic | drift risk if async/sync URLs diverge |
| `REDIS_URL` | str | `redis://localhost:6379/0` | rate-limit storage, Celery broker+backend, JWT denylist | no auth support in URL; single DB index shared by 3 subsystems |
| `JWT_SECRET_KEY` | str | `"change-me-to-a-random-secret-key"` | signs JWTs **AND session cookies** | **insecure default, no startup guard** — shipping default = full auth forgery; key reuse across two mechanisms |
| `JWT_ALGORITHM` | str | `HS256` | JWT alg | decode pins alg (good) |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | int | `1440` (24 h) | access-token TTL | security.py calls these "short-lived" — 24 h is *not*; window for stolen tokens |
| `OPENROUTER_API_KEY` | str | `""` | OpenRouter LLM | empty → provider calls fail at runtime |
| `OPENROUTER_BASE_URL` | str | `https://openrouter.ai/api/v1` | LLM endpoint | — |
| `OPENROUTER_MODEL` | str | `meta-llama/llama-4-maverick:free` | default model | free-tier rate limits |
| `GEMINI_API_KEY` | str | `""` | Gemini | — |
| `GEMINI_MODEL` | str | `gemini-2.0-flash` | model | — |
| `LLM_PROVIDER` | str | `"auto"` | auto/openrouter/gemini/ollama routing | — |
| `FB_APP_ID` / `FB_APP_SECRET` | str | `""` | Meta app creds | webhook sig verification disabled if empty |
| `FB_VERIFY_TOKEN` | str | `"zemest-verify-token"` | webhook handshake | **guessable default** — anyone can validate/subscribe webhooks if unset |
| `FB_GRAPH_API_URL` | str | `https://graph.facebook.com/v21.0` | Graph API base | v-pinning fine |
| `WHISPER_MODEL` | str | `"small"` | faster-whisper model | memory/CPU vs accuracy |
| `WHISPER_DEVICE` | str | `"cpu"` | device | gpu string on cpu-only container = crash |
| `WHISPER_COMPUTE_TYPE` | str | `"int8"` | quantization | — |
| `DEFAULT_DELIVERY_INSIDE_CAIRO` | float | `35` | EGP shipping default | wrong currency value → mispriced orders |
| `DEFAULT_DELIVERY_OUTSIDE_CAIRO` | float | `60` | EGP | idem |
| `DEFAULT_FREE_DELIVERY_ABOVE` | float | `300` | free-shipping threshold | idem |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` | str/int | `smtp.gmail.com`/587/`""`/`""` | notifications | Gmail default + app-password model; creds in plain str |
| `NOTIFICATION_FROM_EMAIL` | str | `noreply@zemest.ai` | from header | spoofed domain if SPF not set |
| `POSTIZ_URL` / `POSTIZ_EMAIL` / `POSTIZ_PASSWORD` | str | `http://localhost:4007`/`""`/`""` | Postiz sidecar | compose overrides to `http://postiz:5000`; local default dead inside Docker |
| *(model_config)* | — | `.env`, extra=ignore | env loading | `extra="ignore"` silently discards **typo'd env vars** |

**Secrets handling:** no `SecretStr`, no prod-mode assertion that `JWT_SECRET_KEY` was changed, secrets duplicated into compose environment blocks (docker-compose.yml:40-41, 62-63, 78-79). `.env` correctly gitignored (`.gitignore:25`) and excluded from image (`.dockerignore:18-20`), but `env_file: .env` in compose **fails hard** when the file is absent (it is absent in the repo — no `.env.example` shipped).

---

## 3. Database Setup

### `app/database.py` (32 lines)
- **Engine:** `create_async_engine(settings.DATABASE_URL, echo=settings.APP_DEBUG, pool_size=20, max_overflow=10)` (database.py:8-13) → up to **30 conns/process**; with app + celery worker (concurrency=2 prefork) + beat, worst case ~90+ conns vs Postgres default `max_connections=100` — thin headroom.
- **Missing:** `pool_pre_ping` (stale conns after PG restart surface as errors until app restart) and `pool_recycle` (long-lived conns behind NAT/LBs).
- **Session factory:** `async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)` (database.py:15) — correct async idiom.
- **`class Base(DeclarativeBase)`** (database.py:18-19) — SQLAlchemy 2.0 declarative base.
- **`async def get_db()`** (database.py:22-31): yields session, commits on success, rolls back + re-raises on exception, closes in `finally`.
  - ⚠ Anti-pattern: since FastAPI ≥0.106 the post-`yield` code runs **after the response is sent** — a failed commit (constraint/serialization error) cannot inform the client, which already received 200. Commit-in-endpoint (or unit-of-work service) is safer.
  - Every request commits — even pure reads — and holds its connection until after response transmission.
- Sync driver only used by Alembic (`psycopg2-binary` + `DATABASE_URL_SYNC`).

### `app/dependencies.py` (58 lines)
- `security = HTTPBearer(auto_error=False)` (line 12) — manual 401 instead of auto-403.
- **`get_current_user(credentials, db) -> User`** (15-38): decode JWT (`decode_token` pins alg + requires `exp`), `db.get(User, UUID(payload["sub"]))`, 401 on missing/invalid/unknown user. Lazy `from app.models.user import User` inside the body to dodge circular imports.
- **`get_tenant(tenant_id: uuid.UUID, db, user) -> Tenant`** (41-57): **ownership-scoped** query `Tenant.id == tenant_id AND Tenant.owner_id == user.id` → 404 otherwise. This is the multi-tenant isolation primitive — correct (fail-closed, no superadmin bypass here). Note the signature requires `tenant_id` as a path param, so this dependency can only be used on `/{tenant_id}/...` routes.

### `app/__init__.py`
Empty file — package marker only.

---

## 4. Migration Lineage (alembic)

**Chain:** `5179285ae0ae` (initial) → `927179233531` (flexible product) → `a89fe0001_egypt_pivot` (HEAD).

**`alembic/env.py`:** imports `app.config.get_settings()` and overrides `sqlalchemy.url` with `DATABASE_URL_SYNC` (env.py:14) — URL from env beats the stale hardcoded one in `alembic.ini:4`. `from app.models import *` populates metadata (env.py:8). Online mode uses `NullPool` (env.py:38). Offline mode standard. No `render_as_batch`/`compare_type` options.

**Revealed backstory:** initial schema (create-dated 2026-03-17) contains `products.name_bn` (Bengali!) and Bangladesh administrative geography (`division`/`district`/`upazila` on customers & orders) — **this project is a rebrand/pivot of a Bangladeshi social-commerce bot onto the Egyptian market**, which the third migration openly names ("egyptian pivot: rename BD address cols").

### `5179285ae0ae_initial_schema` — 10 tables
- `users` (id UUID, fb_user_id UNIQUE, name, email — **email not UNIQUE**, hashed_password, created_at)
- `tenants` (fb_page_id UNIQUE, page_name, **page_access_token TEXT plaintext**, owner FK, notification_pref, is_active, timestamps)
- `crawl_jobs` (url, status, pages_found, products_extracted, error_message, celery_task_id, started/completed)
- `customers` (tenant FK, fb_psid, unique `(tenant_id, fb_psid)`, BD geo columns, phone)
- `knowledge_bases` (tenant UNIQUE, tree_json JSON, source_documents JSON, last_indexed_at)
- `products` (tenant FK, name, name_bn, description, price/discount NUMERIC(12,2), currency, category, sku, stock_status, image_url, source, source_ref, is_active, metadata_extra JSON, unique `(tenant_id,sku)` + `(tenant_id,source,source_ref)`)
- `conversations` (tenant+customer FKs, status, started_at, last_message_at)
- `messages` (conversation FK, role, content, fb_message_id, created_at)
- `orders` (tenant/customer/conversation FKs, order_number UNIQUE, customer_name/phone, **BD geo columns NOT NULL**, payment_method, subtotal/delivery_charge/total, status, notes)
- `order_items` (order+product FKs, product_name snapshot, qty, unit/total price)
- Sensible indexes throughout (tenant_id everywhere, composite hot-path idxs). Clean symmetric `downgrade()`.

### `927179233531_flexible_product_schema` (same day, +19 min)
- Adds `products.attributes JSON`; **drops 9 typed columns** (sku, name_bn, discount_price, description, metadata_extra, category, currency, image_url, stock_status) and the `uq_product_sku` constraint.
- ⚠ **Destructive with no data migration:** existing product descriptions/SKUs/categories are *destroyed*, not copied into `attributes` — an ORM-driven autogenerate that assumes an empty/dev DB.
- `downgrade()` re-adds columns as `nullable=False` with no `server_default` → **fails on any non-empty table** (non-round-trippable).

### `a89fe0001_egypt_pivot` (2026-08-26) — the big reconciliation
Defensive/idempotent migration (`_column_exists`/`_index_exists` inspectors; PG-vs-SQLite branches):
1. `CREATE EXTENSION IF NOT EXISTS pg_trgm` (duplicates init.sql).
2. Renames BD→EG geo columns on customers+orders: division→governorate, district→city, upazila→area.
3. Adds `channel VARCHAR(20) DEFAULT 'messenger'` on customers, conversations, messages.
4. Adds `media_urls` JSON on messages.
5. Adds **13 tenant columns** (docstring says 12): IG creds (ig_user_id indexed, ig_access_token), WA creds (wa_phone_number_id indexed, wa_access_token, wa_waba_id), delivery fees (inside/outside Cairo, nullable), free_delivery_above, payment_methods JSON, style_profile JSON, knowledge_base JSON, knowledge_built_at, order_api_config JSON. Backfills NULL delivery fees to 35/60 and `payment_methods='{}'`.
6. Adds 7 order API-tracking/payment columns (payment_phone_last2, payment_trx_id, api_status, api_response, api_status_code, api_called_at, api_external_id); backfills `api_status='not_configured'`.
7. Hot-path indexes: `orders(tenant_id,created_at)`, `messages(fb_message_id)`, `token_usage(tenant_id,created_at)`, `order_items(product_id)`, `tenants(owner_id)`, `conversations(tenant_id,status,last_message_at)`, tenant channel indexes.
8. Creates `token_usage` table if absent (belt-and-braces vs lifespan DDL).
9. `pg_trgm` GIN index on `lower(products.name)` for fuzzy Arabic/Latin product search.
- ⚠ **Docstring vs code:** docstring claims "Makes messages.fb_message_id **unique** (webhook idempotency)" (line 17) but line 153-154 creates a **plain non-unique index**. Webhook dedup is NOT enforced at the DB level — duplicate webhook deliveries can double-insert messages.
- ⚠ **Schema drift, proven:** migration says `payment_phone_last2 String(2)`, `payment_trx_id String(255)`, `api_status String(30)`; the lifespan DDL says `VARCHAR(10)`, `VARCHAR(50)`, `VARCHAR(20)` (main.py:35, 58). Two authorities disagree; whichever ran first wins per environment.
- `downgrade()` reverses everything including re-pivoting to BD names — best of the three, but still no data preservation for dropped columns.

**Evolution story:** v1 Bangladeshi FB-page commerce bot (10 tables, typed product columns) → pivot #1: EAV-style flexible products (JSON attributes) → pivot #2: Egyptian market + multi-channel (IG/WhatsApp) + AI-personality/knowledge JSONB blobs on tenants + external order-API integration tracking + performance indexes. Schema management then forked into *three* competing mechanisms (ORM metadata, Alembic, lifespan DDL), which is why the pivot migration is defensive.

---

## 5. Deployment Topology

### Dockerfile (37 lines, single-stage `python:3.12-slim`)
1. apt: `build-essential`, `curl` + 16 Playwright/Chromium system libs (Dockerfile:6-14).
2. `pip install -r requirements.txt` **before** `COPY . .` — good layer caching.
3. `playwright install chromium` + `playwright install-deps` (Dockerfile:20-21).
4. `COPY . .` (respects `.dockerignore`: excludes .git, .env, `*.md` except README/MASTER_PROMPT, `scripts/`, tests NOT excluded — test deps are installed into prod image).
5. Non-root `appuser` (uid 1000), `chown -R` (Dockerfile:27-28) — good.
6. `EXPOSE 8000`; `HEALTHCHECK` curl `/docs` every 30 s (Dockerfile:33-34); `CMD uvicorn app.main:app --host 0.0.0.0 --port 8000` (single worker).
- ⚠ **Likely Playwright runtime bug:** `playwright install chromium` runs as **root** during build → browsers land in `/root/.cache/ms-playwright`; runtime `USER appuser` cannot read `/root` → "Executable doesn't exist" at first crawl unless `PLAYWRIGHT_BROWSERS_PATH` is set to a shared path (it isn't). The official Playwright images set `/ms-playwright` for exactly this reason.
- No multi-stage build → `build-essential` ships in the final image; image well over ~2 GB (Chromium + camel-tools + whisper + test tooling).
- No `--proxy-headers`/`--forwarded-allow` → client-IP-based rate limiting/bot detection breaks behind any proxy.
- No lockfile-based install (`pip install` from mixed `==`/`>=` requirements) → non-reproducible builds.

### docker-compose.yml — 7 services, 2 networks, 5 volumes
```
                        ┌────────────────────── Host (docker compose) ─────────────────────┐
                        │                                                                   │
  host:8000 ──────────► │  app (build .)  uvicorn :8000        celery_worker  (-c 2)        │
                        │     │  env_file .env                    │      celery_beat        │
                        │     │        ASGI HTTP / SQLAlchemy    │      (crontab: weekly    │
                        │     ▼        async                     ▼       03:00 Sun + */1min)│
                        │  ┌──────────────────┐  broker+backend  ┌──────────────────┐        │
                        │  │ redis:7-alpine   │◄────────────────►│  (same Redis)    │        │
                        │  │ host:6379 NO AUTH│                  └──────────────────┘        │
                        │  └──────────────────┘                                              │
                        │  ┌────────────────────────┐   ┌───────────────┐ ┌──────────────┐  │
                        │  │ postgres:16-alpine     │   │ postiz:latest │ │ postiz-pg17  │  │
                        │  │ host:5432              │   │ host:4007→5000│ │ postiz-redis │  │
                        │  │ init.sql → pg_trgm     │◄──│ (social media │ │ (isolated    │  │
                        │  │ vol postgres_data      │   │  scheduler)   │ │  postiz-net) │  │
                        │  └────────────────────────┘   └───────────────┘ └──────────────┘  │
                        └───────────────────────────────────────────────────────────────────┘
   External: Meta webhooks ─► /webhook (FB/IG/WA) · OpenRouter/Gemini · SMTP · crawled sites (Playwright)
```
- **db** (postgres:16-alpine): env-default creds `zemest/zemest_secret`; **host port 5432 published**; `init.sql` mounted to `docker-entrypoint-initdb.d` (pg_trgm); healthcheck `pg_isready` 5s×5; `restart: unless-stopped`; named volume.
- **redis** (redis:7-alpine): **no password, no persistence (no volume, no appendonly)** → rate-limit counters + Celery results + JWT revocation denylist vanish on restart; host port 6379 published.
- **app**: `env_file: .env` + inline env (DATABASE_URL/REDIS_URL/POSTIZ_URL overrides); `depends_on: db/redis (service_healthy)` — good; healthcheck via `python -c urllib...` (works, no curl needed in compose); `restart: unless-stopped`; `command` duplicates the Dockerfile CMD.
- **celery_worker**: same image/env; `--concurrency=2`; `worker_max_tasks_per_child=50` and `task_time_limit=600` set in code; **no healthcheck** (a wedged worker is invisible); no volume for whisper model cache (re-downloads per container).
- **celery_beat**: timezone `Africa/Cairo`; two schedules — `rebuild-personality-weekly` (Sun 03:00) and `publish-scheduled-posts` (every minute).
- **postiz** (ghcr.io/gitroomhq/postiz-app:**latest** — unpinned, mutable tag): env `NOT_SECURED: "true"` (JWT in header, not httpOnly cookie), `DISABLE_REGISTRATION: "false"` (open registration!), dev JWT secret default, local storage provider; ports `4007:5000`; joins `default` + `postiz-network` so the app can reach it at `http://postiz:5000`; depends on its own healthy pg/redis.
- **postiz-postgres** (postgres:17-alpine) & **postiz-redis** (7.2): **hardcoded creds** `postiz-user/postiz-password`, isolated on `postiz-network`, no host ports — good isolation.
- **Gaps:** no resource limits (cpu/mem) on any service; no `deploy:` section; single uvicorn worker (scale-up story undefined); no reverse-proxy/TLS termination service; production Postgres/Redis exposed on host.

### init.sql
Two lines: `CREATE EXTENSION IF NOT EXISTS pg_trgm;` — enables trigram fuzzy matching (used by `idx_products_name_trgm`). Requires superuser at first-boot init (fine with the official image; needs pre-provisioning on RDS/CloudSQL). Duplicates a89fe migration step — harmless belt-and-braces.

---

## 6. Dependency Audit (`requirements.txt` — 38 packages, NO lockfile)

| Package | Pin | Purpose | Assessment |
|---|---|---|---|
| fastapi | ==0.115.6 | web framework | current-ish (Dec 2024); OK |
| uvicorn[standard] | ==0.34.0 | ASGI server | OK; no gunicorn supervisor |
| pydantic[email] | ==2.10.4 | validation + email-validator | OK |
| pydantic-settings | ==2.7.1 | env config | OK |
| sqlalchemy[asyncio] | ==2.0.36 | ORM | OK, modern 2.0 style |
| asyncpg | ==0.30.0 | async PG driver | OK |
| alembic | ==1.14.1 | migrations | OK |
| psycopg2-binary | ==2.9.11 | sync driver for Alembic | OK; binary wheels only |
| **python-jose[cryptography]** | ==3.3.0 | JWT | ⚠ **CVE-2024-33663 (ECDSA alg confusion) + CVE-2024-33664 (JWE decompression bomb) — fixed in 3.4.0; upgrade required** |
| **passlib** | ==1.7.4 | password hashing | ⚠ unmaintained since 2020; known bcrypt-4.x friction (hence the explicit bcrypt pin) |
| bcrypt | ==4.1.3 | bcrypt backend | pinned specifically to coexist w/ passlib; works w/ warning |
| python-multipart | ==0.0.20 | form/file parsing | OK (also CVE-2024-24762-era fixed) |
| httpx | ==0.28.1 | async HTTP client | OK |
| celery[redis] | ==5.4.0 | task queue | OK |
| redis | ==5.2.1 | redis client | OK |
| trafilatura | ==2.0.0 | content extraction (crawler) | heavy dep chain; OK |
| beautifulsoup4 | ==4.12.3 | HTML parsing | OK |
| jinja2 | ==3.1.5 | templating | OK (3.1.5 fixed the CVE-2025-… sandbox issues era) |
| **litellm** | >=1.82.0 | LLM provider router | ⚠ floor-pin only — non-reproducible; litellm moves fast |
| pyyaml | >=6.0 | YAML config | floor-pin; OK |
| faster-whisper | >=1.0.0 | local voice→text | floor-pin; pulls ctranslate2 (~large) |
| sqladmin | >=0.19.0 | admin panel | floor-pin; couples to fastapi/sqla versions — drift risk |
| slowapi | >=0.1.9 | rate limiting | floor-pin; thin wrapper over limits |
| geoip2 | >=4.8.0 | IP geolocation (admin analytics) | requires local MMDB to be useful |
| python-dotenv | ==1.0.1 | .env loading | redundant with pydantic-settings env_file |
| aiofiles | ==24.1.0 | async file IO | OK |
| structlog | >=24.1.0 | structured logging | OK — but main.py uses stdlib logging fallback |
| pytest / pytest-asyncio / pytest-cov / aiosqlite | ==pinned | test rig | **test deps in the production image** |
| hypothesis / schemathesis / locust / pytest-playwright / mutmut | >=floors | property/contract/load/e2e/mutation testing | ⚠ **all shipped in prod requirements → bloated prod image & attack surface; belongs in requirements-dev.txt** |
| aiosmtplib | ==3.0.2 | async SMTP | OK |
| python-Levenshtein | ==0.26.1 | fuzzy matching | C extension; OK |
| playwright | ==1.58.0 | JS-rendered crawling | + Chromium in image; see Dockerfile browser-path issue |
| camel-tools | >=1.5.0 | Arabic dialect ID (26 classes) | very heavy NLP stack in prod image |
| fasttext-wheel | >=0.2.5 | GlotLID language ID | idem |
| eval_type_backport | ==0.3.1 | "Python 3.9 compatibility" | ⚠ **vestigial** — Dockerfile is 3.12; dead weight |

**Pinning verdict:** core stack properly `==`-pinned; the newest/most critical integrations (litellm, sqladmin, slowapi, camel-tools, whisper, all test tiers) are `>=` floors with **no lockfile** → `docker build` today ≠ build next month. Combined with test-tooling in prod requirements, the image is fat and non-reproducible.

---

## 7. Seed & Init

### `seed.py` (96 lines)
`async def seed()` run via `asyncio.run(seed())`:
1. Creates user `Admin / admin@zemest.ai` with password **`test123`** (hash via passlib bcrypt) — credentials printed to stdout (seed.py:81-91).
2. Creates tenant "Egyptian Fashion Store" (fb_page_id `eg_fashion_123`, notification_pref email) — no delivery-fee/channel columns set (relies on DB defaults).
3. Creates **6 Egyptian-themed products** (galabiya, khayamiya, papyrus, cartouche, leather bag, copper finjan set; EGP 250–1200) using the flexible schema: `source="manual"`, `price` Decimal, all other fields inside `attributes` JSON (Arabic names, categories, SKUs) — i.e. seed is written for post-`927179233531` schema.
4. `flush()` between inserts, single `commit()`, prints login instructions pointing at `/dashboard/login`.
- ⚠ Not idempotent: users.email has **no unique constraint** (initial migration) → re-running seed duplicates the admin user; password `test123` is trivially brute-forceable if ever run against a shared env; seeded user is not flagged `is_superadmin`.
- `init.sql`: see §5 — pg_trgm bootstrap only.

---

## 8. Issues & Risks Found (ranked)

| # | Severity | Issue | Evidence |
|---|---|---|---|
| 1 | **HIGH (sec)** | `JWT_SECRET_KEY` insecure default `"change-me-..."`, no startup guard, no `SecretStr`; same key signs JWTs **and** session cookies | config.py:21; main.py:191-197 |
| 2 | **HIGH (sec)** | `python-jose==3.3.0` carries CVE-2024-33663 (algorithm confusion) & CVE-2024-33664 (JWT bomb); fix = 3.4.0 | requirements.txt:14 |
| 3 | **HIGH (arch)** | **Three competing schema authorities** — ORM metadata, Alembic migrations, and 150 lines of raw DDL in lifespan with `except: pass`. Proven drift: `payment_phone_last2` VARCHAR(10) vs String(2); `payment_trx_id` VARCHAR(50) vs String(255); `api_status` VARCHAR(20) vs String(30) | main.py:33-70 vs a89fe0001:129-135 |
| 4 | **HIGH (data)** | Migration `927179233531` drops 9 product columns **without backfilling** into the new `attributes` JSON — destructive on populated DBs; its own downgrade fails on non-empty tables | 9271792335:23-33, 39-48 |
| 5 | **MED (sec)** | Silent exception swallowing in lifespan: outer `except Exception: pass` boots the app with an unreachable/incorrect DB; inner blocks hide partial DDL failure | main.py:66-70, 151-152, 153-154 |
| 6 | **MED (sec)** | Docstring/code mismatch: `fb_message_id` claimed UNIQUE for webhook idempotency, but only a plain index is created → duplicate webhook deliveries can double-process | a89fe0001:17 vs 153-154 |
| 7 | **MED (sec)** | Redis: no auth, no persistence, host port published; serves as rate-limit store, Celery broker/backend, and JWT revocation denylist → restart wipes all three; restart also un-bans nothing (IP bans are in PG) but un-limits everyone | docker-compose.yml:23-32; security.py:1-14 |
| 8 | **MED (deploy)** | Playwright browsers installed as root into `/root/.cache/ms-playwright` while runtime user is `appuser` → likely "executable doesn't exist" failures in the containerized crawler | Dockerfile:20-28 |
| 9 | **MED (deploy)** | `postiz:latest` mutable tag + `NOT_SECURED=true` + open registration + hardcoded DB creds `postiz-user/postiz-password`; postgres & redis host ports published for the core stack; zero resource limits on any service | docker-compose.yml:94-146, 12, 26 |
| 10 | **MED (ops)** | No `pool_pre_ping`/`pool_recycle`; 30 conns/process × 3+ processes vs PG `max_connections=100` | database.py:8-13 |
| 11 | **MED (api)** | `get_db` commits in post-`yield` teardown — runs **after** the response is sent; failed commits yield silent 200s | database.py:24-31 |
| 12 | **MED (api)** | No CORS/TrustedHost/proxy-headers anywhere; uvicorn lacks `--proxy-headers` → client-IP rate limiting is wrong behind a proxy | main.py:191-223; Dockerfile:36 |
| 13 | **LOW (sec)** | Middleware doc mismatch: actual onion is `SecurityHeaders → RateLimit → BotDetection → IPBan → Session` (RateLimit runs *before* IP-ban, contradicting the comment); banned IPs burn rate-limit budget first | main.py:171-185 vs 191-223 |
| 14 | **LOW (sec)** | `/docs` + `/redoc` enabled unconditionally; `https_only=False` session cookie; 24 h access tokens labeled "short-lived"; `FB_VERIFY_TOKEN` guessable default; `page_access_token`/IG/WA tokens stored plaintext in DB | main.py:167-168, 196; config.py:23, 40; 5179285ae0ae:37 |
| 15 | **LOW (hygiene)** | `.env` required by compose but absent (no `.env.example`); `alembic.ini` hardcodes creds; vestigial `eval_type_backport` (py3.9) on py3.12; test tiers in prod requirements; seed password `test123`; `users.email` not UNIQUE | docker-compose.yml:38; alembic.ini:4; requirements.txt:51-60, 78; seed.py:19 |
| 16 | **LOW (perf)** | `token_usage`/admin tables created without FK indexes beyond listed; engine echo in debug logs SQL w/ params (PII); structlog installed but main.py falls back to stdlib logging | main.py:20-32, 215; requirements.txt:48 |

---

## 9. Quality Ratings

| Area | Score | Justification |
|---|---|---|
| Bootstrap flow (main.py) | **6/10** | Well-ordered, unusually well-commented (mount ordering, fail-open rationale), sensible security onion; dragged down by runtime DDL, triple `except: pass`, doc-vs-code onion mismatch |
| Configuration (config.py) | **5/10** | Clean pydantic-settings layout, lru_cache singleton; but insecure defaults with no prod guards, no SecretStr, APP_ENV unused, extra=ignore hides typos |
| Database (database.py + dependencies.py) | **6/10** | Correct modern async SQLA 2.0 idiom + ownership-scoped tenant isolation; loses points for no pre_ping/recycle, commit-after-response, aggressive pool sizing |
| Migrations | **4/10** | Honest, heavily-documented pivot migration w/ inspectors and downgrades; but destructive column drops, false uniqueness claim, type drift vs lifespan DDL, non-round-trippable downgrade |
| Deployment (Dockerfile + compose) | **5/10** | Healthchecks + `service_healthy` gating + non-root user are above average; unpinned `:latest`, exposed DB/Redis, no resource limits, Playwright path bug, fat single-stage image |
| Dependency management | **5/10** | Core pinned; >= floors without lockfile, known CVE in python-jose, unmaintained passlib, test tooling & vestigial packages in prod |
| Seed & init | **6/10** | Dev-useful, correct flexible-schema demo data; non-idempotent, weak hardcoded creds |
| **Overall architecture** | **5.5/10** | A competently-assembled solo-dev stack with real security thinking at the edges (headers, rate limiting, IP bans, alg pinning) undermined by schema-management chaos, secret-handling defaults, and deployment hardening gaps |

---

*Next actions for downstream agents: Z2-Z12 should treat the lifespan DDL (main.py:13-157) as a de facto 4th migration when reconciling models; X1 (security) should prioritize issues #1, #2, #14; anyone touching orders/tenants columns must check all three schema authorities.*
