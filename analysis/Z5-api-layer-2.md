# Z5 — API Layer Part 2: crawl, dashboard, facebook, postiz, scheduling, style_learning, tenants, address

**Repo:** `/home/z/my-project/repos/zemest` · **Scope:** 8 files in `app/api/` (all lines read)
**Auth model (from `app/dependencies.py`):**
- `get_current_user` — HTTP Bearer JWT (`decode_token`), 401 on missing/expired/unknown user.
- `get_tenant(tenant_id, db, user)` — resolves tenant **scoped by `owner_id == user.id`** → 404 "Tenant not found" for cross-tenant access (no info leak; effectively per-user tenant isolation).

---

## 1. Complete API Endpoint Catalog (48 endpoints)

### 1.1 `app/api/crawl.py` — prefix `/api/tenants/{tenant_id}/crawl`, tag "Crawling" (3 endpoints)

| # | Method | Path | Auth | Request body | Response | Purpose |
|---|--------|------|------|--------------|----------|---------|
| 1 | POST | `/api/tenants/{tenant_id}/crawl` | JWT + tenant ownership (`get_tenant`) | `CrawlRequest` `{url: str, depth: int=3}` (query-style body, no URL/depth validation) | **201** `CrawlJobResponse` `{id, url, status, pages_found, products_extracted, error_message, created_at}` | Create crawl job; dispatch to Celery if workers alive, else FastAPI BackgroundTasks |
| 2 | GET | `/api/tenants/{tenant_id}/crawl/jobs` | JWT + tenant | — | `list[CrawlJobResponse]` (max 20, newest first, hardcoded limit) | List recent crawl jobs for tenant |
| 3 | GET | `/api/tenants/{tenant_id}/crawl/jobs/{job_id}` | JWT + tenant | — (path `job_id: uuid.UUID`) | `CrawlJobResponse`; **404** if not found or owned by other tenant | Poll single job status (pending → crawling → indexing → completed/failed) |

### 1.2 `app/api/dashboard.py` — prefix `/dashboard`, tag "Dashboard", `include_in_schema=False` (9 endpoints)

| # | Method | Path | Auth | Request | Response | Purpose |
|---|--------|------|------|---------|----------|---------|
| 4 | GET | `/dashboard/login` | ❌ **NONE** | — | HTML `login.html` | Render dashboard login page |
| 5 | GET | `/dashboard` | ❌ **NONE** | — | HTML `dashboard.html` | Render main dashboard |
| 6 | GET | `/dashboard/{tenant_id}/chat` | ❌ **NONE** | path `tenant_id: str` (unvalidated) | HTML `chat.html` + `tenant_id` context | Render chat page for tenant |
| 7 | GET | `/dashboard/{tenant_id}/products` | ❌ **NONE** | path `tenant_id: str` | HTML `products.html` | Render products page |
| 8 | GET | `/dashboard/{tenant_id}/orders` | ❌ **NONE** | path `tenant_id: str` | HTML `orders.html` | Render orders page |
| 9 | GET | `/dashboard/{tenant_id}/customers` | ❌ **NONE** | path `tenant_id: str` | HTML `customers.html` | Render customers page |
| 10 | GET | `/dashboard/{tenant_id}/conversations` | ❌ **NONE** | path `tenant_id: str` | HTML `conversations.html` | Render conversations page |
| 11 | GET | `/dashboard/{tenant_id}/crawl` | ❌ **NONE** | path `tenant_id: str` | HTML `crawl.html` | Render crawl page |
| 12 | GET | `/dashboard/{tenant_id}/settings` | ❌ **NONE** | path `tenant_id: str` | HTML `settings.html` | Render settings page |

### 1.3 `app/api/facebook.py` — prefix `/api/facebook`, tag "Facebook" (3 endpoints)

| # | Method | Path | Auth | Request | Response | Purpose |
|---|--------|------|------|---------|----------|---------|
| 13 | GET | `/api/facebook/pages` | JWT (`get_current_user`) | **Query param** `fb_access_token: str` (required) | `{pages: [...]}` from Graph `/me/accounts` (id, name, access_token); **empty list on Graph error** (never raises) | List FB pages the user manages |
| 14 | POST | `/api/facebook/connect` | JWT | **Query params** `page_id: str`, `page_access_token: str`, `page_name: str` | `{message, tenant_id}`; **400** if webhook subscribe fails | Subscribe page to app webhooks (`subscribed_apps`) then create a Tenant for the user |
| 15 | POST | `/api/facebook/{tenant_id}/sync-catalog` | JWT + tenant (`get_tenant`) | — | `{message, imported}` — counts imported products | Pull products from first FB product catalog (`/{page_id}/product_catalogs` → `/{catalog_id}/products`) and create them locally |

### 1.4 `app/api/postiz.py` — prefix `/api/tenants/{tenant_id}/postiz`, tag "Postiz Scheduler" (12 endpoints)

| # | Method | Path | Auth | Request | Response | Purpose |
|---|--------|------|------|---------|----------|---------|
| 16 | GET | `/health` | ❌ **NONE** (path tenant_id never validated) | — | `{healthy: bool, url: str}` | Ping Postiz sidecar root URL |
| 17 | POST | `/login` | JWT + tenant | `PostizLoginRequest {email, password}` | `{status: "logged_in"}`; **401** if login fails | Login to Postiz; JWT cached in **singleton** `PostizClient` (process-wide!) |
| 18 | GET | `/can-register` | ❌ **NONE** | — | `{can_register: bool}` | Check if Postiz allows registrations |
| 19 | GET | `/integrations` | JWT + tenant | — | `{integrations: [...]}` | List social accounts connected in Postiz |
| 20 | POST | `/connect/{provider}` | JWT + tenant | path `provider: str` (free text) | `{url, provider}`; **400** if no OAuth URL | Get Postiz OAuth URL for provider (facebook, instagram, x, linkedin…) |
| 21 | POST | `/posts` | JWT + tenant | `PostizCreatePostRequest {integration_id: str, caption: str 1..5000, media_urls: list[str]=[], schedule_at: Optional[str]}` (no datetime validation) | `{status: "created", postiz_result}`; **500** on failure | Create/schedule a post in Postiz (draft if `schedule_at` None) |
| 22 | GET | `/posts` | JWT + tenant | Query `page: int=1 (ge=1)`, `limit: int=50 (1..200)`, `filter_type: str="scheduled"` (not enum-validated) | Postiz payload `{posts, total, page}` or **500** | List posts from Postiz (scheduled/published/draft/failed) |
| 23 | GET | `/posts/{post_id}/stats` | JWT + tenant | path `post_id: str` | Postiz statistics JSON; **500** on failure | Get post statistics via Postiz |
| 24 | DELETE | `/posts/{group_id}` | JWT + tenant | path `group_id: str` | `{status: "deleted", group_id}`; **500** on failure | Delete a post (by group id) in Postiz |
| 25 | PUT | `/posts/{post_id}/reschedule` | JWT + tenant | path `post_id`, **Query** `new_date: str` (ISO string, unvalidated) | `{status: "rescheduled", post_id, new_date}`; **500** on failure | Reschedule a Postiz post |
| 26 | GET | `/best-time` | JWT + tenant | Query `integration_id: Optional[str]` | `{next_free_slot: str}`; **500** on failure | Find next free posting slot in Postiz |
| 27 | POST | `/generate` | JWT + tenant | `PostizGenerateRequest {prompt: str, number_of_posts: int=3 (1..10), platforms: list[str]=[]}` | `{posts: [...], source: "postiz"\|"zemest_fallback"}`; **500** if both Postiz AI and local LLM fallback fail | AI caption generation via Postiz streaming API; falls back to local LLM using tenant style profile |

### 1.5 `app/api/scheduling.py` — prefix `/api/tenants/{tenant_id}`, tag "Scheduling & Insights" (8 endpoints)

| # | Method | Path | Auth | Request | Response | Purpose |
|---|--------|------|------|---------|----------|---------|
| 28 | POST | `/schedule/post` | JWT + tenant | `SchedulePostRequest {platform, caption 1..5000, media_urls=[], media_type="text", link?, scheduled_at: datetime, ai_generated=False}` | **201** `{id, status, scheduled_at, platform}`; **422** platform ∉ {facebook, instagram}, past `scheduled_at`, media missing for photo/video/reel/story/carousel | Schedule a post; published later by background worker |
| 29 | GET | `/schedule/posts` | JWT + tenant | Query `status?`, `platform?`, `limit: int=50 (1..200)` | `{posts: [...] (caption truncated to 200 chars), total}` | List scheduled posts for tenant |
| 30 | PATCH | `/schedule/posts/{post_id}/status` | JWT + tenant | `UpdatePostStatusRequest {status: draft\|scheduled\|cancelled}` | `{status, post_id, new_status}`; **404** not found; **400** published/publishing; **422** invalid status | Change post status (e.g. cancel) |
| 31 | DELETE | `/schedule/posts/{post_id}` | JWT + tenant | — | `{status: "deleted", post_id}`; **404**; **400** if published (but NOT if `publishing`) | Delete an unpublished scheduled post |
| 32 | POST | `/schedule/generate-caption` | JWT + tenant | `GenerateCaptionRequest {product_name?, product_description?, platform="facebook", tone="friendly", include_hashtags=True, language="arabic"}` | `{captions: [3 variants], hashtags, tokens_used}`; **500** on LLM failure | AI caption generation using tenant style profile; Egyptian Arabic / English / code-switching |
| 33 | GET | `/insights/overview` | JWT + tenant | Query `days: int=30 (1..90)` | `{facebook: {page_name, followers, fans, insights[]}\|{error}\|null, instagram: {insights[]}\|{error}\|null, period_days}` | FB Page + IG user insights for date range (since = now-days) |
| 34 | GET | `/insights/best-time` | JWT + tenant | — | 7×24 heatmap + top 5 slots (from IG `online_followers`); **400** if IG not connected; **500** on Graph error | Best time to post (Instagram only) |
| 35 | GET | `/insights/post/{post_id}` | JWT + tenant | path `post_id: uuid.UUID` | `{post_id, metrics, cached: bool}`; **404**; **400** not published; **500** on Graph error | Per-post insights with **1-hour PostInsights DB cache**; fetches FB post insights or IG media insights |

### 1.6 `app/api/style_learning.py` — prefix `/api/tenants/{tenant_id}`, tag "Style Learning" (3 endpoints)

| # | Method | Path | Auth | Request | Response | Purpose |
|---|--------|------|------|---------|----------|---------|
| 36 | POST | `/import/chat-history` | JWT + tenant | multipart `file: UploadFile` (ZIP) + Query `channel: str="auto"` (auto/messenger/instagram/whatsapp, unvalidated) | `{status, channel, imported_messages, style_profile, zip_stats}`; **413** >500 MB; **400** empty/invalid ZIP/no messages/parse error | Import FB Messenger DYI / IG DYI / WhatsApp export ZIP; parse locally (no Meta API calls — "zero ban risk"); build style profile |
| 37 | GET | `/style-profile` | JWT + tenant | — | `{status: "built"\|"not_built", built_at?, profile?}` | Read current style profile from `tenant.style_profile` |
| 38 | POST | `/rebuild-style` | JWT + tenant | Query `use_llm: bool=True` | `{status: "rebuilt", profile}` | Re-analyze all merchant messages in DB and rebuild profile |

### 1.7 `app/api/tenants.py` — prefix `/api/tenants`, tag "Tenants" (5 endpoints)

| # | Method | Path | Auth | Request | Response | Purpose |
|---|--------|------|------|---------|----------|---------|
| 39 | POST | `/api/tenants` | JWT | `TenantCreate {page_name, fb_page_id?, page_access_token?, website_url?, business_phone?, business_email?, notification_pref="email"}` | **200** `TenantResponse` (no `page_access_token` in response — good) | Create tenant owned by current user |
| 40 | GET | `/api/tenants` | JWT | — | `list[TenantResponse]` (only `is_active=True`, no pagination) | List user's tenants |
| 41 | GET | `/api/tenants/{tenant_id}` | JWT + tenant | — | `TenantResponse` | Get tenant detail |
| 42 | PATCH | `/api/tenants/{tenant_id}` | JWT + tenant | `TenantUpdate` (all optional: page_name, page_access_token, fb_page_id, website_url, business_phone, business_email, notification_pref, delivery_inside_cairo, delivery_outside_cairo, free_delivery_above, payment_methods, order_api_config) | `TenantResponse` | Update tenant settings incl. shipping rates & payment config (`exclude_none=True`) |
| 43 | GET | `/api/tenants/{tenant_id}/stats` | JWT + tenant | — | `{products_count, orders_count, pending_orders, active_conversations, total_revenue, today_orders, today_revenue, month_revenue, customers_count, top_products[5], recent_orders[5], total_tokens, chat_tokens, crawl_tokens, llm_calls}` | Aggregated tenant dashboard stats |

### 1.8 `app/api/address.py` — prefix `/api/address`, tag "Egypt Address" (5 endpoints)

| # | Method | Path | Auth | Request | Response | Purpose |
|---|--------|------|------|---------|----------|---------|
| 44 | GET | `/api/address/governorates` | ❌ **NONE** | — | `[{key, name_ar, zone, shipping_cost, free_threshold}]` × 27 | List all 27 Egyptian governorates with zones/shipping |
| 45 | GET | `/api/address/cities` | ❌ **NONE** | Query `governorate: str` (required) | `["القاهرة"]`-style list — **returns only the governorate's own Arabic name, not real cities** | "Cities" for a governorate |
| 46 | GET | `/api/address/areas` | ❌ **NONE** | Query `governorate: str` | list of area names (Arabic) or `[]` | Areas/neighborhoods for a governorate |
| 47 | GET | `/api/address/shipping` | ❌ **NONE** | Query `governorate: str`, `subtotal: float=0` (no bounds) | `{shipping_cost: float}` — note: only `shipping_cost` key extracted from rich dict `{cost, free, governorate_ar, message, free_threshold, remaining}` | Calculate shipping cost (zone-based, free above threshold) |
| 48 | GET | `/api/address/validate` | ❌ **NONE** | Query `governorate: str`, `city: str=None` | `{valid: bool}` (city check accepts any non-empty string) | Validate Egyptian governorate/city |

**Total: 48 endpoints** (3 crawl + 9 dashboard + 3 facebook + 12 postiz + 8 scheduling + 3 style + 5 tenants + 5 address).
**Auth coverage:** 37 JWT-protected, **11 unauthenticated** (9 dashboard HTML + postiz health/can-register + all 5 address… i.e. 9+2+5=16 unauthenticated — of which only address is defensibly public).

Correction: unauthenticated = 9 (dashboard) + 2 (postiz health, can-register) + 5 (address) = **16 of 48**.

---

## 2. Crawl API (`crawl.py`, 273 lines)

**Job creation flow (`start_crawl`, lines 18–75):**
1. Creates `CrawlJob(status="pending")` row, `db.flush()` (commit deferred to `get_db` teardown — database.py:26).
2. **Dual dispatch:** imports Celery app, `inspect(timeout=1).ping()`; if any worker answers → `run_crawl_pipeline.delay(job_id, tenant_id, url, depth)` and stores `job.celery_task_id`; else falls back to `background_tasks.add_task(_run_crawl_inline, ...)`. All Celery failures are swallowed into the fallback.
3. Returns the job snapshot immediately (201).

**Inline pipeline (`_run_crawl_inline`, 78–134):** opens a *fresh* `async_session`, sets `crawling` → `crawl_website(url, depth)` → `indexing` → `build_knowledge_index()` → `_extract_products_from_pages()` (LLM) → `completed`. Any exception → `failed` with `error_message` truncated to 500 chars. Mirrors `app/tasks/crawl_tasks.py:_crawl_pipeline_async` almost line-for-line (but with a different step order: Celery extracts products *before* building the index, inline does index first; only the inline version records `TokenUsage`).

**Product extraction (`_extract_products_from_pages`, 137–229):** concatenates first 20 pages (2,000 chars each), prompts LLM (temp 0.1, max_tokens 3000) to return a JSON array; regex-extracts `\[.*\]`; records `TokenUsage(usage_type="crawl")`; per-product errors trigger `db.rollback()` (which also rolls back the TokenUsage insert — usage row lost on first bad product).

**URL validation / SSRF: NONE.** `CrawlRequest.url` is a bare `str` (schemas/webhook.py:34). No scheme allow-list, no private/loopback/metadata-IP blocking (169.254.169.254 reachable), no DNS-rebinding protection. `app/knowledge/crawler.py` fetches arbitrary URLs via httpx (`follow_redirects=True`) and — critically — **Playwright `page.goto(url)` accepts `file://` URLs** (crawler.py:182), so `url=file:///etc/passwd` yields local-file read: httpx quick-fetch fails on `file://` → Playwright path selected → Chromium renders the local file → content extracted & returned to the tenant's knowledge base. Katana URL discovery shells out to Docker (`docker run projectdiscovery/katana -u <url>`, crawler.py:285-296) — argv-based (no shell injection) but allows internal-network scanning by a tenant.

**Job monitoring:** `GET /jobs` (hardcoded `limit(20)`, no pagination params, no status filter); `GET /jobs/{job_id}` (404 for cross-tenant ids — isolation OK). No cancel/retry endpoint; no concurrency cap (a tenant can spam unlimited concurrent crawls → Playwright + Docker per job → resource-exhaustion DoS).

---

## 3. Dashboard API (`dashboard.py`, 66 lines)

Not a metrics API — it is the **server-rendered HTML shell** for the legacy Jinja2 dashboard (`dashboard/templates/*.html`, static mounted at `/static` by main.py:226). Nine GET routes render: login, dashboard home, and per-tenant pages for chat/products/orders/customers/conversations/crawl/settings.

**No authentication/authorization on any route.** `tenant_id` is a raw path string echoed into template context with zero verification (no `get_tenant`, not even UUID format check). The data behind the pages is fetched by the templates' JS from the real APIs (which are JWT-protected), so actual data exposure depends on how the templates obtain tokens — but the pages themselves are enumerable by anyone (`/dashboard/<uuid>/chat`), `include_in_schema=False` hides them from `/docs` only. Templates directory is a **relative path** (`dashboard/templates`) — breaks if the process CWD differs. No caching headers, no CSRF protection on the login form handling.

---

## 4. Facebook Integration API (`facebook.py`, 95 lines)

**Flow implemented (no server-side OAuth!):** the client is expected to obtain a *user* access token via FB Login elsewhere (frontend), then:
1. `GET /api/facebook/pages?fb_access_token=...` — proxies Graph `/me/accounts` with `fields=id,name,access_token` (returns embedded **page tokens** to the caller). Service returns `[]` on any Graph error/status ≠ 200 — the API can never fail, so the frontend gets a silently empty list on invalid tokens (facebook_service.py:21–27).
2. `POST /api/facebook/connect?page_id&page_access_token&page_name` — first calls `subscribe_page_to_webhook()` → Graph `POST /{page_id}/subscribed_apps` with fields `messages, message_deliveries, message_echoes, message_reads, messaging_postbacks, standby` (mirrors Chatwoot's field set). If subscribe succeeds → `create_tenant()` with the page token stored **plaintext** in `tenants.page_access_token`. **No verification that the page/token belongs to the calling user** — any authenticated user can connect any page id + a valid page token they somehow hold; also no dedup (same page connectable by multiple users → webhook events routed by page id, see webhook.py analysis in Z-agent scope).
3. `POST /api/facebook/{tenant_id}/sync-catalog` — fetches `/{page_id}/product_catalogs`, takes **first catalog only**, then `/{catalog_id}/products` with fields `id,name,description,price,image_url,availability`. Price parsing: `"100.00 EGP".split(" ")[0]`. Duplicates raise `ValueError` from `create_product` and are silently skipped (`except ValueError: pass`); any *other* exception (e.g. bad price format) → unhandled 500. Requires Graph permissions: `pages_show_list`, `pages_manage_metadata` (subscribe), `pages_read_engagement` + catalog read (`catalog_management`).

**Design issues:** tokens transported in **query strings** (GET pages — facebook.py:13) leak into logs/proxies/history. Inconsistent prefix (`/api/facebook/{tenant_id}/...` vs the rest of the app's `/api/tenants/{tenant_id}/...`). Only the first catalog is synced; no pagination on Graph results (`data` truncated at 25 by Graph default).

---

## 5. Postiz API (`postiz.py`, 287 lines)

A clean **BFF bridge** to the Postiz sidecar (`app/scheduling/postiz_client.py`, NestJS service at `POSTIZ_URL`, default `http://localhost:4007`). Endpoint groups: health/auth (health, login, can-register), integrations (list, OAuth connect URL per provider), posts CRUD (create draft/scheduled, list with `page/limit/filter_type`, stats, delete by group_id, reschedule via PUT with `new_date` **query** param), best-time slot finder, and AI generation (Postiz `/posts/generator` streaming → collected; falls back to local LLM `chat_completion_with_usage` with tenant `style_profile` tone hint, regex-parses `{"posts": [...]}`).

**Fatal architectural flaw — shared singleton session:** `get_postiz_client()` returns a **module-level singleton** `PostizClient` (postiz_client.py:417–425) whose `_token` is set by `/login`. Because *every* tenant's requests go through this one client, **all tenants share one Postiz account/session** — tenant A's integrations, posts, and analytics are visible/modifiable by tenant B via `/postiz/posts`, `/postiz/integrations`, `/postiz/posts/{id}` DELETE, etc. Moreover **any authenticated tenant owner can call `/login` with their own credentials and overwrite the global session** (postiz.py:71–81). The `tenant_id` path parameter is decorative for these operations.

Other gaps: `schedule_at` is an unvalidated string (no datetime/future check — contrast with scheduling.py which validates); `filter_type`/`provider` not enum-validated; error paths return 500 with generic details (Postiz's real error hidden); `/health` and `/can-register` are fully unauthenticated (any UUID in path works, tenant never resolved); no timeout/retry policy surfaced; fallback LLM generation does **not** record `TokenUsage` (cost tracking inconsistency).

---

## 6. Scheduling API (`scheduling.py`, 445 lines)

**CRUD** for `ScheduledPost` (local DB; published by a Celery/worker elsewhere):
- `POST /schedule/post` — validates platform ∈ {facebook, instagram}, `scheduled_at > utcnow()`, media_urls required when `media_type ∈ {photo, video, reel, story, carousel}` (media_type itself is free text — "textx" passes). **Naive-datetime bug:** `req.scheduled_at <= datetime.utcnow()` throws `TypeError` (→ 500) if the client sends a tz-aware ISO datetime; naive values are treated as UTC so Cairo (UTC+2) clients schedule 2 h late. `media_urls` accepted as-is (no URL validation, no limit on count) — later fetched by publishers (SSRF-ish on publish).
- `GET /schedule/posts` — optional `status`/`platform` filters, `limit ≤ 200`, caption truncated to 200 chars in list view; returns `total = len(posts)` (post-limit count, not real total).
- `PATCH .../status` — state machine guard: rejects modifying `published`/`publishing` (400); accepts only `draft|scheduled|cancelled` (422).
- `DELETE .../{post_id}` — refuses only `published` (400); a post in `publishing` can be deleted **while the publisher is mid-flight** (race → orphaned platform post).

**AI caption generation** — 3 variants + hashtags; prompt assembles tenant style profile (tone, greeting/signoff patterns, emoji frequency, language mix), language modes (Egyptian Arabic / English / code-switching), platform hints (FB 5000 chars vs IG 2200/first-125/5–10 hashtags). Returns raw LLM content as a single caption if JSON parse fails. No TokenUsage recorded (unlike crawl) — inconsistent billing.

**Insights:** `overview` (days 1–90) merges FB page info (`followers_count`, `fan_count`) + page insights and IG user insights, swallowing per-platform errors into `{"error": str(e)}` — **`str(e)` of httpx/Graph errors can embed the request URL containing `access_token` → token leak in response body** (scheduling.py:348, 363). `best-time` requires IG connection (400 otherwise), returns `online_followers` heatmap + top-5 slots. `insights/post/{post_id}` — DB-cached for 1 h in `PostInsights` (unbounded growth, no pruning), platform-dispatched fetch, metrics cached as raw `data[]`.

---

## 7. Style Learning API (`style_learning.py`, 170 lines)

**Import flow** (`POST /import/chat-history`): reads **entire** upload into memory (`contents = await file.read()`) and *then* checks `len(contents) > 500 MB` (413) — the 500 MB cap therefore does not protect the read itself; a single 2 GB body is fully buffered (memory DoS; no streaming/chunked check). Content sniffing: `get_zip_stats()` peek; auto-detection = filename contains "whatsapp" → whatsapp; `thread_count > 0` → messenger; else ZIP contains `.txt` → whatsapp; else messenger (instagram chosen only when explicitly passed as `channel=instagram`). Parsers: `parse_messenger_dyi_zip`, `parse_instagram_dyi_zip`, `parse_whatsapp_export_zip` (local parse — no Meta API calls, "zero ban risk" holds). Parsed messages → `import_messages_and_build_style()` (style_learner.py:425): groups by thread → creates `Conversation(status="imported", customer_id=None)` + `Message` rows → `build_and_persist_personality()` (heuristics + optional LLM merge, persists `tenant.style_profile` + `knowledge_built_at`). Response returns the full profile + zip stats.

**Gaps:** `channel` query param unvalidated (unknown values silently fall through to messenger parser); 500 MB is very generous for a sync request (long request timeouts, worker blockage); `get_zip_stats` runs before BadZipFile check in auto-detect branch only — explicit-channel path passes garbage bytes straight to parsers (they raise ValueError → 400, OK); no rate limit on this expensive endpoint; `rebuild-style` runs the full LLM pipeline synchronously in-request (2–40 s+ per docstring) with no concurrency guard.

---

## 8. Tenants API (`tenants.py`, 81 lines)

Lifecycle: **create** (owner = current user; accepts optional `page_access_token` stored plaintext), **list** (active only, no pagination), **get**, **patch**, **stats**. Note in file (line 79) that `rebuild-style` lives in style_learning.py. Deactivation/deletion endpoints do **not** exist (tenants are immortal; `is_active` can't even be set via PATCH — not in `TenantUpdate`).

Settings via PATCH: shipping config (`delivery_inside_cairo`, `delivery_outside_cairo`, `free_delivery_above` as `Decimal`), `payment_methods` (free-form dict), `order_api_config` (free-form dict — downstream used for outbound order API calls, unvalidated → stored-SSRF surface for tenant-controlled URLs). `exclude_none=True` means fields **cannot be cleared** once set (set `delivery_inside_cairo=35`, can never go back to NULL) — validation gap. No format validation on `website_url`/`business_phone` despite `validate_egyptian_phone` existing in the codebase. `TenantResponse` omits `page_access_token` (good) but also omits IG/WA connection flags and `style_profile` presence, so the frontend can't show connection state without extra calls.

**Stats endpoint** delegates to `tenant_service.get_tenant_stats` — ~12 sequential aggregate queries (products, orders ×3, conversations, revenue ×3, customers, tokens ×4, top-5 products GROUP BY, recent 5 orders) executed serially per request; no caching, no date-range params. Revenue counts only `confirmed|shipped|delivered`.

---

## 9. Address API (`address.py`, 36 lines)

Thin wrapper over `app/utils/egypt_address.py` (27 governorates, 5 zones, EGP 35–100 shipping, free-delivery thresholds EGP 300–1000, Arabic area lists, phone regex `^(?:\+20|0020|20|0)?(1[0125]\d{8})$`). All five GET endpoints are unauthenticated (defensible as public reference data — but `/shipping` also exposes business pricing defaults). Quirks: `/cities` returns only `[governorate_ar_name]` — not real cities (utils get_cities, egypt_address.py:282–289 admits lists are minimal); `/validate` accepts any non-empty city; `/shipping` discards the rich result (free flag, threshold, remaining, Arabic message) and returns only `{"shipping_cost": float(cost)}` — the *cost* key is coerced to float but when `is_free` the dict's `cost` is 0 so OK; unknown governorate → default 60 EGP "outside" cost. `subtotal` has no `ge=0` constraint (negative values produce nonsense `remaining`). No caching of the static governorate payload.

---

## 10. Function Inventory (all helpers in the 8 files)

| File | Function | Signature | Purpose |
|------|----------|-----------|---------|
| crawl.py | `start_crawl` | `(req: CrawlRequest, background_tasks, tenant, db) -> CrawlJobResponse` | Create crawl job, dual-dispatch Celery/BackgroundTasks |
| crawl.py | `_run_crawl_inline` | `(job_id: str, tenant_id: str, url: str, depth: int) -> None` | Full pipeline fallback when no Celery worker (crawl → index → LLM product extract) |
| crawl.py | `_extract_products_from_pages` | `(db, tenant_id: uuid.UUID, pages: list[dict]) -> int` | LLM JSON-array extraction of products + TokenUsage recording + `create_product` loop |
| dashboard.py | `login_page` | `(request: Request) -> TemplateResponse` | Render login.html |
| dashboard.py | `dashboard_page` | `(request: Request) -> TemplateResponse` | Render dashboard.html |
| dashboard.py | `chat_page` / `products_page` / `orders_page` / `customers_page` / `conversations_page` / `crawl_page` / `settings_page` | `(request: Request, tenant_id: str) -> TemplateResponse` | Render per-tenant pages with tenant_id context |
| facebook.py | `list_pages` | `(fb_access_token: str, user) -> {pages}` | Proxy Graph `/me/accounts` |
| facebook.py | `connect_page` | `(page_id, page_access_token, page_name, user, db) -> {message, tenant_id}` | Webhook-subscribe page + create tenant |
| facebook.py | `sync_catalog` | `(tenant, db) -> {message, imported}` | Import products from FB catalog |
| postiz.py | `postiz_health` | `() -> {healthy, url}` | Ping sidecar |
| postiz.py | `postiz_login` | `(req: PostizLoginRequest, tenant) -> {status}` | Postiz login (stores JWT in singleton) |
| postiz.py | `postiz_can_register` | `() -> {can_register}` | Registration-open check |
| postiz.py | `list_postiz_integrations` | `(tenant) -> {integrations}` | List Postiz social accounts |
| postiz.py | `get_connect_url` | `(provider: str, tenant) -> {url, provider}` | OAuth URL for provider |
| postiz.py | `create_postiz_post` | `(req: PostizCreatePostRequest, tenant) -> {status, postiz_result}` | Create/schedule post in Postiz |
| postiz.py | `list_postiz_posts` | `(tenant, page, limit, filter_type) -> dict` | Paginated post list from Postiz |
| postiz.py | `get_postiz_post_stats` | `(post_id: str, tenant) -> dict` | Post statistics from Postiz |
| postiz.py | `delete_postiz_post` | `(group_id: str, tenant) -> {status, group_id}` | Delete post in Postiz |
| postiz.py | `reschedule_postiz_post` | `(post_id: str, new_date: str, tenant) -> {status, post_id, new_date}` | Reschedule Postiz post |
| postiz.py | `find_postiz_free_slot` | `(tenant, integration_id?) -> {next_free_slot}` | Next free slot |
| postiz.py | `generate_postiz_posts` | `(req: PostizGenerateRequest, tenant) -> {posts, source}` | Postiz AI generation + local LLM fallback |
| scheduling.py | `schedule_post` | `(req: SchedulePostRequest, tenant, db) -> dict` | Create ScheduledPost with validation |
| scheduling.py | `list_scheduled_posts` | `(tenant, db, status?, platform?, limit) -> {posts, total}` | Filtered post list |
| scheduling.py | `update_post_status` | `(post_id, req, tenant, db) -> dict` | Status transition with guards |
| scheduling.py | `delete_scheduled_post` | `(post_id, tenant, db) -> dict` | Delete unpublished post |
| scheduling.py | `generate_caption` | `(req: GenerateCaptionRequest, tenant) -> {captions, hashtags, tokens_used}` | Local LLM caption gen with style profile |
| scheduling.py | `get_insights_overview` | `(tenant, days) -> overview dict` | FB+IG insights aggregate |
| scheduling.py | `get_best_time_to_post` | `(tenant) -> heatmap dict` | IG online_followers heatmap |
| scheduling.py | `get_post_insights` | `(post_id, tenant, db) -> {post_id, metrics, cached}` | Cached per-post insights |
| style_learning.py | `import_chat_history` | `(file: UploadFile, tenant, db, channel: str="auto") -> dict` | ZIP upload → parse → import → style build |
| style_learning.py | `get_style_profile` | `(tenant) -> dict` | Read style profile |
| style_learning.py | `rebuild_style` | `(tenant, db, use_llm: bool=True) -> {status, profile}` | Rebuild from DB messages |
| tenants.py | `_tenant_response` | `(t: Tenant) -> TenantResponse` | Map ORM → response DTO (drops token) |
| tenants.py | `create_tenant` / `list_tenants` / `get_tenant_detail` / `update_tenant_detail` / `get_stats` | route handlers | CRUD + stats delegation to `tenant_service` |
| address.py | `list_governorates` / `list_cities` / `list_areas` / `shipping_cost` / `validate_address` | query-param handlers | Static Egyptian geography lookups |

**Key upstream dependencies invoked:** `tenant_service.create_tenant/get_user_tenants/update_tenant/get_tenant_stats`; `facebook_service.get_user_pages/subscribe_page_to_webhook/get_page_products`; `product_service.create_product`; `knowledge.crawler.crawl_website`; `knowledge.indexer.build_knowledge_index`; `ai.llm_client.chat_completion_with_usage`; `ai.style_learner.build_and_persist_personality/import_messages_and_build_style`; `importers.{messenger_dyi,whatsapp_export}`; `scheduling.{postiz_client,facebook_publisher,instagram_publisher}`; `tasks.crawl_tasks.run_crawl_pipeline`.

---

## 11. Issues & Risks (prioritized)

### Critical
1. **Postiz singleton session = total multi-tenant collapse** — postiz.py:71–81 + postiz_client.py:417–425. One process-wide Postiz JWT shared by ALL tenants; `/postiz/posts`, `/integrations`, DELETE, reschedule all operate on the shared account. Any tenant owner can call `/login` and hijack/replace the session. Cross-tenant post data exposure + unauthorized deletion.
2. **SSRF + local-file-read in crawl** — crawl.py:19–30 (no URL validation) + crawler.py:182 (Playwright `goto` supports `file://`) + crawler.py:285 (Katana internal-network scanning). `POST /crawl {"url": "file:///app/.env"}` or `http://169.254.169.254/...` exfiltrates internal content into tenant knowledge base / LLM prompts (which can leak via chat responses). `depth` unbounded (schemas/webhook.py:35).
3. **Unauthenticated dashboard pages with enumerable tenant ids** — dashboard.py:19–65. No `get_tenant`, no auth at all on all 9 routes; page existence enumerates valid tenant UUIDs.

### High
4. **Celery race on job creation** — crawl.py:50 dispatches `.delay()` after only `flush()`; commit occurs in `get_db` teardown (database.py:26). Worker can query `crawl_jobs` before the row is visible → `run_crawl_pipeline` silently no-ops (crawl_tasks.py:35–37) → job stuck "pending" forever.
5. **FB access token in query strings** — facebook.py:13 (GET `/pages`), facebook.py:23–25 (POST `/connect` params). Tokens land in access logs / proxies; page tokens also returned wholesale to the client.
6. **Graph error strings returned to clients (possible token leak)** — scheduling.py:348, 363: `overview["facebook"] = {"error": str(e)}` — httpx/Graph exceptions frequently embed the full request URL (with `access_token` query param).
7. **Style-import memory DoS** — style_learning.py:65–70: whole file read into RAM before size check; 500 MB cap per request, unthrottled.

### Medium
8. **`publishing` race on delete** — scheduling.py:202 blocks only `published`, not `publishing` (contrast PATCH at :173 which blocks both).
9. **Naive-datetime handling** — scheduling.py:78: tz-aware input → 500 (TypeError); naive input interpreted as UTC while the product targets Cairo clients (UTC+2) — systematic 2-hour scheduling skew.
10. **No crawl concurrency cap / pagination** — crawl.py:240 (hardcoded `limit(20)`), no max-jobs-per-tenant → each job spawns Docker+Playwright → resource exhaustion.
11. **Duplicated crawl pipeline** — crawl.py:78–229 vs crawl_tasks.py:27–171 (~150 duplicated lines, divergent ordering & token accounting; maintenance hazard already visible: only one path records TokenUsage).
12. **Tenants PATCH cannot clear fields** (`exclude_none=True`, tenants.py:66) and `order_api_config`/`payment_methods` are free-form dicts persisted unvalidated (stored outbound-URL surface).
13. **Silent failure modes** — facebook_service returns `[]` on every error (facebook.py:17 → empty "pages" for invalid token looks like "no pages"); sync-catalog swallows only `ValueError`, others → raw 500 (facebook.py:91–92).
14. **Unvalidated enums/params** — postiz `filter_type`/`provider`/`schedule_at` string (postiz.py:50, 161, 209); scheduling `media_type` free text (scheduling.py:42); style `channel` falls through to messenger (style_learning.py:100–105); address `subtotal` unbounded (address.py:30).

### Low
15. Postiz `/health` + `/can-register` unauthenticated (tenant path param ignored) — postiz.py:63–89.
16. `PostInsights` cache grows unbounded; 1 h TTL only honored on read (scheduling.py:411–419).
17. `datetime.utcnow()` deprecated (naive) used throughout; crawl_job.py imports `timezone` unused.
18. Relative `dashboard/templates` directory (dashboard.py:4) breaks under different CWD.
19. Token usage not recorded for caption-generation LLM calls (scheduling.py:279, postiz.py:270) — billing under-count vs crawl path.
20. `list_scheduled_posts` `total` = page length, not row count (scheduling.py:151); `/cities` endpoint mislabeled (address.py:19–21 → utils egypt_address.py:282).
21. Inconsistent API prefixes: facebook uses `/api/facebook/{tenant_id}/...` while everything else uses `/api/tenants/{tenant_id}/...` (facebook.py:8, 55).

---

## 12. Quality Ratings

| File | Rating | Justification |
|------|--------|---------------|
| `crawl.py` | **5/10** | Thoughtful Celery-with-fallback dispatch and status machine, correct tenant scoping on reads; but zero URL/SSRF validation, file:// read via Playwright, flush-vs-commit race, ~150 lines duplicated with the Celery task (divergent behavior), dead imports (lines 82–87), hardcoded list limit, no concurrency control. |
| `dashboard.py` | **4/10** | Does its one job (render 9 Jinja pages) but with zero auth, zero tenant validation, enumerable tenant ids, relative template paths, hidden from schema. Fine as a dev tool, unacceptable as shipped surface. |
| `facebook.py` | **5/10** | Correct minimal Graph flow with good webhook field set and duplicate-tolerant import; but tokens in query strings, no token→user ownership verification, silent `[]` error handling, unhandled non-ValueError 500s, first-catalog-only sync, inconsistent route prefix. |
| `postiz.py` | **5.5/10** | Clean BFF design, good Pydantic field constraints (caption length, post count, pagination bounds), sensible LLM fallback; ruined by the shared singleton session (multi-tenant isolation failure), unauthenticated health/can-register under a tenant-scoped path, unvalidated datetime/filter enums, and 500s that mask Postiz's real errors. |
| `scheduling.py` | **7/10** | Best file of the set: real validation (platform, future time, media requirements, status enum, days 1–90), state-machine guards on PATCH, 1 h insights cache, graceful per-platform degradation; docks for naive-datetime bugs, publishing-delete race, `str(e)` token-leak risk, no TokenUsage on caption gen, free-text media_type. |
| `style_learning.py` | **6.5/10** | Excellent product feature (local DYI parsing, auto-detect, style build pipeline) with size + empty-file + BadZipFile handling; docks for read-then-check memory model, unvalidated channel enum, no rate limit on a 500 MB/LLM-heavy sync endpoint. |
| `tenants.py` | **6/10** | Simple, correct, well-scoped CRUD with token-free response DTO; docks for `exclude_none` clearing gap, missing is_active toggle/delete lifecycle, unvalidated phone/URL/free-form JSONB, uncached 12-query stats endpoint, no pagination. |
| `address.py` | **6/10** | Tiny, dependency-free, correct for its purpose; unauthenticated (acceptable for reference data), but `/cities` is misleading, `/shipping` discards its rich payload, `subtotal` unvalidated, no caching of static data. |

**Layer average: ≈ 5.6/10** — strong product breadth (48 endpoints, FB/IG/WhatsApp/Postiz/crawling/style-learning), consistently good tenant-row scoping in SQL, but security hardening (SSRF, session isolation, token hygiene, datetime correctness) lags well behind feature depth.
