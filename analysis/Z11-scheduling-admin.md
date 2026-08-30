# Z11 — Scheduling, Celery Tasks, Admin Panel & Tenant Dashboard (Deep Analysis)

**Agent:** general-purpose (Z11) · **Scope:** `app/scheduling/{facebook_publisher,instagram_publisher,postiz_client}.py`, `app/tasks/*`, `app/admin/*`, `dashboard/templates/*`, `dashboard/static/*`
**Cross-referenced:** Z1 (bootstrap/compose), Z5 (API layer 2 — postiz singleton, dashboard auth, crawl race), Z6 (missing scheduled_posts DDL), Z8 (notification race, dead notifiers), Z10 (IPBanMiddleware.invalidate_all missing, dead rate limit), Z3 (style profile keys), Z9 (indexer fallback).

---

## 1. Publishers

### 1.1 `app/scheduling/facebook_publisher.py` (221 lines, 6 functions)

Direct-httpx Graph API client, no SDK, no shared client, no retry, no rate-limit handling. Base URL = `settings.FB_GRAPH_API_URL` = `https://graph.facebook.com/v21.0` (config.py:41 — EOL'd version on a 2026 codebase, per Z8).

| Function | Graph call | Token transport | Notes |
|---|---|---|---|
| `publish_feed_post(page_access_token, page_id, message, link=None, scheduled_publish_time=None) -> dict` | POST `/{page_id}/feed` (form data) | **form body** (OK) | If `scheduled_publish_time` set → adds `published=false` + `scheduled_publish_time`. Returns `{"id": post_id}`. Timeout 30s. |
| `publish_photo(page_access_token, page_id, photo_url, caption="", scheduled_publish_time=None) -> dict` | POST `/{page_id}/photos` with `url=` (FB fetches the image server-side) | form body | No multi-photo support (no `attached_media` array). Timeout 60s. |
| `publish_video(page_access_token, page_id, video_url, title="", description="") -> dict` | POST `/{page_id}/videos` with `file_url` | form body | **No scheduled_publish_time support** (asymmetric with photo/feed). Timeout 120s. |
| `get_page_insights(page_access_token, page_id, metric="page_impressions,page_reach,page_engaged_users,page_fans", period="day", since=None, until=None) -> dict` | GET `/{page_id}/insights` | **query string** (leaks to access logs/proxies; Z5 flag) | Docstring notes 100+ page likes requirement. |
| `get_page_post_insights(page_access_token, post_id) -> dict` | GET `/{post_id}/insights` (post_impressions, post_reach, post_engaged_users, post_reactions_like_total) | query string | Used by `/insights/post/{id}` with 1h DB cache. |
| `get_page_info(page_access_token, page_id) -> dict` | GET `/{page_id}?fields=name,followers_count,fan_count,about,website,phone` | query string | Used in insights overview. |

**Error handling (uniform):** every function does `data = resp.json()` then `if "error" in data: raise Exception(f"FB API error: {…message}")`.
- **Bare `Exception`** everywhere — no typed exception, no HTTP status code check, no `raise_for_status()`. A non-JSON error (HTML error page, 502 from proxy) makes `resp.json()` raise an opaque `json.JSONDecodeError` instead.
- **No retry / backoff** at any layer (Graph transient 500s/RateLimits fail the scheduled post permanently).
- **New `httpx.AsyncClient` per call** — no connection pooling.
- Error *message* from Graph is embedded in `Exception` → surfaces verbatim in `ScheduledPost.error_message` and (per Z5) in `/insights/overview` responses where the access token can appear in the error URL.
- Multi-image (`carousel`) posts: **not supported** — `scheduling_tasks._publish_to_facebook` only ever sends `media_urls[0]`.

### 1.2 `app/scheduling/instagram_publisher.py` (335 lines, 10 functions)

Implements the IG two-step container pattern (create container → publish container). Base URL = same `FB_GRAPH_API_URL`.

| Function | Behavior |
|---|---|
| `create_media_container(access_token, ig_user_id, media_type, media_url, caption="", **kwargs) -> str` | POST `/{ig-user-id}/media`. Payload key is chosen by `("image_url" if media_type == "IMAGE" else "video_url")` — **BUG: any non-IMAGE type (STORIES, CAROUSEL, REELS image-story) gets its URL sent as `video_url`**. REELS kwargs handled (`share_to_feed`, `audio_name`, `cover_url`). Returns `data.get("id")` → **can silently return `None`** on a 200 without id. |
| `check_container_status(access_token, container_id) -> str` | GET `/{container_id}?fields=status_code` → 'IN_PROGRESS'/'FINISHED'/'ERROR'. On API error returns "ERROR" and **swallows the error detail** (no log of why). |
| `publish_media_container(access_token, ig_user_id, creation_id) -> dict` | POST `/{ig-user-id}/media_publish` with `creation_id`. |
| `publish_image(access_token, ig_user_id, image_url, caption="") -> dict` | Convenience: container(IMAGE) → publish. |
| `publish_reel(access_token, ig_user_id, video_url, caption="", share_to_feed=True, cover_url=None) -> dict` | container(REELS) → **polls status up to 30×5s = 150s** → publish. Two flaws: (a) if still IN_PROGRESS after 150s it publishes anyway (publish call will then fail with a confusing error); (b) 150s of blocking inside a Celery worker whose `task_time_limit=600` and whose beat fires `publish_scheduled_posts` **every minute** — a batch with several reels can overlap ticks (see §2.6). |
| `publish_story(access_token, ig_user_id, media_url, media_type="IMAGE") -> dict` | container(STORIES) → publish immediately. Hit by the `video_url` bug above for image stories. |
| `get_ig_user_insights(access_token, ig_user_id, metric="impressions,reach,profile_views,follower_count", period="day", since=None, until=None) -> dict` | GET insights. 90-day retention noted. |
| `get_online_followers(access_token, ig_user_id) -> dict` | GET insights `metric=online_followers&period=total` — the "best time to post" source. |
| `get_ig_media_insights(access_token, media_id) -> dict` | GET `/{media_id}/insights` (impressions, reach, engagement, saved, likes, comments, shares). |
| `get_best_time_to_post(access_token, ig_user_id) -> dict` | Parses `data[0].total_value.value` → 7×24 heatmap (day names list assumes **0=Sunday**; Meta's API numbers days 1–7 with 1=Sunday — off-by-one day-label risk), sorts, returns top-5 slots with `score = value/max*100`. Gracefully returns `{"heatmap": [], "top_slots": []}` on shape mismatch. |
| `_format_hour(hour) -> str` (sync helper) | 12-hour AM/PM formatting. |

Same class-wide weaknesses as FB publisher: bare `Exception`, no retry, no status-code check, new client per call, GET tokens in query string.

### 1.3 `app/scheduling/postiz_client.py` (426 lines) — full Postiz API client

Async client for the Postiz sidecar (NestJS, compose service `postiz` at `http://postiz:5000`, dev `http://localhost:4007`). `POSTIZ_URL` exists in config (config.py:61, default `localhost:4007`; compose overrides to `http://postiz:5000`).

**Auth flow:** `login(email, password)` POSTs `/auth/login` `{"email","password","provider":"LOCAL"}`. Postiz (run with `NOT_SECURED=true` per docker-compose) returns the JWT in the **`auth` response header**; client stores it in `self._token` and thereafter sends it as **both** `Cookie: auth=<jwt>` and `auth: <jwt>` header (`_headers()`). If Postiz is ever run secured (httpOnly cookie), the code just `pass`es — cookie-jar on the shared httpx client is the implicit fallback. No token expiry handling: a 401 from Postiz is never re-interpreted as "re-login".

**Singleton (postiz_client.py:417–425):** module-level `_postiz_client` + `get_postiz_client()`. **One process-wide Postiz session shared by ALL tenants** — confirmed call sites: `api/postiz.py` (12×) and `ai/postiz_chat.py` (5×). Any authenticated tenant owner can POST `/api/tenants/{id}/postiz/login` (postiz.py:66–81) and overwrite the global token, then list/create/delete posts on whichever Postiz account is logged in → cross-tenant post hijack (Z5 CRITICAL, re-verified).

Endpoint map (all return "empty" values on any error — every method wraps in `except Exception: log + return []/None/False`):

| Method | Postiz endpoint | Returns |
|---|---|---|
| `login(email, password)` | POST `/auth/login` | bool; stores token from `auth` header |
| `register(email, password, name="")` | POST `/auth/register` | bool |
| `check_can_register()` | GET `/auth/can-register` | bool from `{"register": bool}` |
| `list_integrations()` | GET `/integrations` | list from `{"integrations": []}` |
| `get_connect_url(provider)` | POST `/integrations/social-connect/{provider}` | `url` or `oauthUrl` |
| `create_post(posts, schedule_at=None, group_id=None)` | POST `/posts` with `{"posts": [...], "type": "draft"\|"schedule", "date": schedule_at, "group"?}` | parsed JSON or None (200/201 accepted) |
| `list_posts(page=1, limit=50, filter_type="scheduled")` | GET `/posts?page&limit&type` | dict or None |
| `get_post(post_id)` | GET `/posts/{id}` | dict or None |
| `delete_post(group_id)` | DELETE `/posts/{group_id}` | bool (200/204) |
| `update_post_date(post_id, new_date, action="update")` | PUT `/posts/{id}/date` `{"date","action"}` | bool |
| `find_free_slot(integration_id=None)` | GET `/posts/find-slot[/{integration_id}]` | ISO date str or None |
| `get_post_statistics(post_id)` | GET `/posts/{id}/statistics` | dict or None |
| `generate_posts(prompt, number_of_posts=3, platforms=None)` | **streaming** POST `/posts/generator` | collects newline-JSON events with `name=="result"`; **doesn't check HTTP status before iterating the stream** — a 401/500 body is parsed line-by-line and usually yields `None` |
| `health_check()` | GET `/` (base URL, new 5s client per call) | bool on status 200 |
| `close()` / `_get_client()` / `_headers()` | lifecycle helpers | shared `httpx.AsyncClient` (timeout 30, follow_redirects=True) |

Other notes: `POSTIZ_EMAIL/POSTIZ_PASSWORD` config values exist (config.py:62-63) but **nothing auto-logs-in** — every Postiz call before someone manually logs in runs unauthenticated and silently returns empty (integration appears "connected but empty"). Tests (`tests/test_postiz.py`) mock httpx and cover login/list/create/delete/stats/find-slot — good unit coverage of the client itself, none of the singleton isolation problem.

---

## 2. Celery topology

### 2.1 `app/tasks/celery_app.py` (44 lines)

```python
celery_app = Celery("zemest", broker=settings.REDIS_URL, backend=settings.REDIS_URL)
celery_app.conf.update(
    task_serializer="json", accept_content=["json"], result_serializer="json",
    timezone="Africa/Cairo", enable_utc=True,
    task_track_started=True, task_time_limit=600, worker_max_tasks_per_child=50,
    beat_schedule={...})
```
- Broker & result backend: Redis (`redis://redis:6379/0` in compose; db 0 shared with rate-limit cache).
- **No routes, no queues, no `task_default_queue`** — everything on the default `celery` queue; a single worker (`--concurrency=2` in compose) serves crawls (up to 600s), publishing, notifications, and weekly style rebuilds together. One long crawl batch can delay minute-cadence post publishing.
- Beat schedule (2 entries):
  - `rebuild-personality-weekly` → task name `app.tasks.style_tasks.rebuild_all_personalities`, `crontab(hour=3, minute=0, day_of_week=0)` — Sunday 03:00 in `Africa/Cairo` tz (Celery evaluates crontab in the configured timezone).
  - `publish-scheduled-posts` → task name `publish_scheduled_posts`, `crontab(minute="*")` — every minute.
- Task name asymmetry: style task referenced by auto-generated module path; scheduling task has explicit `name=`. Both work, but a rename of `style_tasks.rebuild_all_personalities` silently breaks the beat entry (name computed at decoration).
- `worker_max_tasks_per_child=50` mitigates leaks (whisper model, playwright) by recycling children.
- Tasks imported at module bottom for registration. `app/tasks/__init__.py` is EMPTY (imports come from `celery_app` itself).

### 2.2 `app/tasks/crawl_tasks.py` (172 lines)

| Item | Detail |
|---|---|
| `run_crawl_pipeline(self, job_id, tenant_id, url, depth=3)` | `@task(bind=True, max_retries=2)` — **retry is dead config: `self.retry()` is never called.** Trigger: `api/crawl.py:50` `.delay()` after `flush()` but before the request-scoped `get_db` commit → worker may not see the row and return silently, job stuck "pending" (Z5 HIGH, re-verified at code level). |
| `_crawl_pipeline_async(job_id, tenant_id, url, depth)` | Loads `CrawlJob`; status crawl: `pending→crawling` (+`started_at=utcnow()` naive), `crawl_website(url, depth)`, `pages_found` commit; empty pages → `failed`; `indexing` → `_extract_and_save_products` → `build_knowledge_index` → `completed`. Exception → `failed` with `str(e)[:500]`. **Never verifies `job.tenant_id == tenant_id` param** and never verifies the tenant exists. **Not idempotent**: a redelivery re-crawls and re-inserts products (dup-guarded only by pg_trgm similarity in product_service). |
| `_extract_and_save_products(db, tenant_id, pages)` | LLM extraction with an inline prompt (first 20 pages × 2000 chars each, whole prompt truncated to 6000 chars — ~85% of crawl content discarded, matches Z9). Greedy regex `r'\[.*\]'` on the reply; `Decimal(price) > 0` filter; per-product `create_product` + `commit`, per-product `rollback` on error. **This is a near-duplicate of `api/crawl.py:_extract_products_from_pages`** (inline sync path) — two drifted copies of the extraction pipeline (the API version runs in-request and duplicates the DB writes if both paths ever run for one job). Uses `chat_completion` (no usage row → crawl TokenUsage not recorded here, unlike the API path). |
| `_run_async(coro)` | New event loop per task run (one per worker process invocation). |

### 2.3 `app/tasks/notification_tasks.py` (36 lines)

- `send_order_notification(tenant_id, order_id)` — plain `@task` (**no bind, no retries, no acks_late**). Loads Tenant + Order (`selectinload(Order.items)`) in a fresh session, calls `notify_new_order` (email via SMTP if `notification_pref == "email"` and `business_email` set; otherwise just a log line). If tenant or order missing → silent no-op.
- **Known race (Z8):** dispatched `agent.py:437` `.delay()` before the webhook's session commits — fast worker finds no Order → notification silently lost, no retry. If SMTP fails, exception propagates → task FAILURE, no retry policy → email lost.
- **Not idempotent** — but re-send risk is low given no retry.

### 2.4 `app/tasks/scheduling_tasks.py` (200 lines)

- `publish_scheduled_posts` — `@task(name="publish_scheduled_posts")` (beat: every minute). No Celery-level retry.
- `_publish_due_posts_async()`:
  1. `SELECT` posts `status=="scheduled" AND scheduled_at <= datetime.utcnow()` **LIMIT 50** (batch).
  2. Per post: set `status="publishing"` + commit (claim), fetch tenant, `_publish_post`.
  3. Success → `published` + `platform_post_id` + `published_at` + `error_message=None`; failure → `failed` + `error_message[:500]` + **`retry_count += 1`**.
  - **`retry_count` is write-only**: no code ever reads it, no cap, no requeue. Failed posts are terminal (only manual re-trigger is `PATCH /schedule/posts/{id}/status` back to `scheduled`, which the state-machine validator permits, and since `scheduled_at` is past the next tick re-publishes — an accidental retry loop is possible with no cap).
  - **Stuck "publishing" posts:** if the worker dies mid-publish (reel polling up to 150s + graph calls), the claim commit is durable and no reaper exists → post frozen in `publishing` forever.
  - **Overlapping ticks:** beat fires every minute; a batch containing IG reels can take >60s (150s polling per reel × several posts). Beat will enqueue another `publish_scheduled_posts` while the first still runs. The `status=="scheduled"` filter prevents double-publish *for rows already claimed*, but rows not yet claimed (beyond the first 50, or in a second batch) can be processed concurrently — and with `--concurrency=2` the two runs execute in parallel on the same queue. SELECT-then-update claim has **no `FOR UPDATE SKIP_LOCKED`** → two ticks can claim the same post in the window between SELECT and the `publishing` commit → **duplicate publish to Facebook** (the state race alluded to in the task brief; real, though narrow).
  - Naive `datetime.utcnow()` used consistently with the API (`scheduled_at` naive UTC) — internally consistent, but a tz-aware `scheduled_at` from the client makes `req.scheduled_at <= datetime.utcnow()` in scheduling.py:78 raise TypeError (500) instead of 422.
- `_publish_post(post, tenant)` → platform dispatch; raises `Exception("Unknown platform")` otherwise.
- `_publish_to_facebook(post, tenant)` — requires `page_access_token` + `fb_page_id`; `text`→feed (with `link`), `photo`→`publish_photo(media_urls[0])`, `video`→`publish_video(title=caption[:100])`, **else → silently falls back to a text feed post** (a `carousel`/`story` post on FB publishes caption-only — data loss rather than an error). Multi-image ignored (`media_urls[1:]` dropped).
- `_publish_to_instagram(post, tenant)` — requires IG creds + `media_urls`; `photo`→`publish_image`, `video|reel`→`publish_reel`, `story`→`publish_story(media_type="IMAGE" if post.media_type == "photo" else "VIDEO")` — **the branch condition is unreachable (we're inside `media_type == "story"`), so stories ALWAYS publish as VIDEO** → image-story posts send an image URL in the `video_url` field (double bug with instagram_publisher.py:45) → guaranteed Graph API failure for image stories.
- `_run_async(coro)` — same helper (duplicated in 3 of 4 task files).

### 2.5 `app/tasks/style_tasks.py` (75 lines)

- `rebuild_all_personalities` — `@task(bind=True, max_retries=1)` (**retry dead: never called**). Beat: Sunday 03:00 Cairo. Loads all active tenants in one session (list materialized, session closed → detached instances), then per-tenant fresh session + `build_and_persist_personality` with per-tenant try/except (one bad tenant doesn't kill the run — good). Passing the *detached* tenant object into a new session works only because the learner uses simple attributes.
- `rebuild_tenant_personality(tenant_id)` — `@task(bind=True, max_retries=1)` (dead retry). **Never dispatched by any code** (grep: zero call sites outside style_tasks/celery_app import) — registered dead task; the style-learning API path runs the rebuild inline instead.

### 2.6 Topology summary

| Task | Queue | Trigger | Retry | Idempotent | Failure mode |
|---|---|---|---|---|---|
| `run_crawl_pipeline` | celery | `POST /api/tenants/{id}/crawl` `.delay` | max_retries=2 **declared, never used** | No (re-crawls, re-inserts) | Job `failed` w/ message; dispatch race = stuck pending |
| `send_order_notification` | celery | agent.py:437 `.delay` | none | n/a | Silent loss (race / missing row / SMTP error) |
| `publish_scheduled_posts` | celery | beat `* * * *` | none (Celery) / retry_count++ (cosmetic) | No (duplicate publish window) | Post `failed` (terminal) or stuck `publishing` |
| `rebuild_all_personalities` | celery | beat Sun 03:00 Cairo | max_retries=1 dead | Yes-ish (rebuild overwrites profile) | Per-tenant log error |
| `rebuild_tenant_personality` | celery | **nothing** (dead) | max_retries=1 dead | — | — |

No DLQ, no `task_acks_late`, no per-task `time_limit/soft_time_limit` overrides (a 600s crawl limit applies to everything), no `worker_prefetch` tuning, result backend enabled but results never consumed (result expiry default 1d in Redis).

---

## 3. Admin panel

### 3.1 `app/admin/admin_panel.py` (392 lines) — sqladmin integration

- **sqladmin `Admin`** mounted at `/_admin` via `setup_admin(app, engine)` (main.py:253, async engine passed). 5 ModelViews: `UserAdmin` (User), `SiteUserAdmin` (SiteUser), `IPBanAdmin` (IPBan), `UserSessionAdmin` (UserSession, read-only-ish: `can_create=False, can_edit=False` but delete allowed), `AuditLogAdmin` (AuditLog, append-only: no create/edit/delete).
- **Auth mechanism (AdminAuth, sqladmin AuthenticationBackend):**
  1. Browser → `/_admin/login` form (fields `username`/`email` + `password`).
  2. `login()` does its own `SELECT User WHERE email=...` + `verify_password` (bcrypt) + `is_superadmin` check — the docstring claims it goes through `auth_service.login_user`, which is false (doc drift; login_user/JWT is not used here).
  3. Success → `request.session["_admin_user_id"] = str(user.id)` — Starlette **SessionMiddleware** cookie (`_zemest_session`, signed with `settings.JWT_SECRET_KEY`, `same_site=lax`, **`https_only=False`**, main.py:191-197 — the JWT secret is reused as the cookie-signing key, per Z1).
  4. `authenticate()` validates only that the session contains a parseable UUID — **never re-checks the user still exists or is still superadmin** (revoking adminship doesn't kill live admin sessions; no session TTL beyond the default signed-cookie max-age).
  5. `logout()` clears session; both login/logout write audit entries.
- `_write_audit(...)` — best-effort AuditLog insert, swallows all exceptions (Z6: `admin_audit_log` DDL lacks `user_agent` while ORM insert may require it depending on authority → audit writes can fail silently on fresh installs).
- `BaseAdminView.is_accessible` = session-key presence; `is_visible` always True.
- `UserAdmin` — **CRITICAL GAP: `form_columns` includes `User.hashed_password` with no `on_model_change` hashing hook** → an admin creating/editing a user writes the *plaintext* form value into `hashed_password`; bcrypt `verify_password` then fails forever (user bricked, and a plaintext password sits in the DB column). Also `is_superadmin` is one checkbox away — by design, but combined with the no-revocation session issue it's a durable privilege grant.
- `SiteUserAdmin.on_model_change` — on un-created edits touching `is_blocked`, sets `blocked_by`/`blocked_at`, writes `block_user`/`unblock_user` audit. (Note the action string mismatch with the REST API's `user.block` — see §3.2.)
- `IPBanAdmin` — `on_model_change` validates IP/CIDR via `ipaddress` (good); `after_model_change` (line 281) and `after_model_delete` (line 299) call **`IPBanMiddleware.invalidate_all()` which does not exist** (security.py `IPBanMiddleware` has only `__init__/ban_ip/ban_cidr/unban_ip/is_banned/dispatch`) → **AttributeError → sqladmin 500 on every IP-ban create/edit/delete** (re-verified; Z10 proven). Audit write for bans happens *after* the crash → ban audits also never persist.
- Enforcement gap: nothing enforces `SiteUser.is_blocked` or `BlockedUser` anywhere in the request path (grep confirmed — only admin UI/API read/write them), and the running `IPBanMiddleware` was instantiated with empty in-memory sets, never loading the `ip_bans` table (Z10).

### 3.2 `app/admin/api.py` (448 lines) — REST endpoints (prefix `/api/admin`)

Auth: **all 10 endpoints** require `require_superadmin` = `get_current_user` (JWT Bearer) + `is_superadmin` check → 403 otherwise. (Different credential model from the sqladmin cookie panel — two parallel admin auth systems.)

| # | Method & Path | Body / Params | Response | Notes |
|---|---|---|---|---|
| 1 | POST `/users/{user_id}/block` | `BlockUserRequest{reason?}` | `{"status":"blocked","user_id"}` | Creates `BlockedUser` row + audit `user.block`; 404 unknown user, 400 already blocked. **BlockedUser never enforced anywhere** (grep) — blocking is cosmetic. `blocked_users` table not created by any schema authority (Z6) → 500 on fresh installs. |
| 2 | DELETE `/users/{user_id}/block` | — | `{"status":"unblocked"}` | Deletes block row + audit `user.unblock`; 404 if not blocked. |
| 3 | GET `/ip-bans` | — | list `{id, ip_or_cidr, reason, created_at}` | Active only. Queries `IPBan.is_active` — **column missing from lifespan DDL** (Z6) → UndefinedColumn 500 on fresh prod. |
| 4 | POST `/ip-bans` (201) | `IPBanCreate{ip_or_cidr, reason?}` | `{"status":"banned",...}` | Validates IP/CIDR, dup-check, sets `banned_by`. Same DDL/`is_active` problem. Ban not propagated to the running middleware (no `invalidate_all` concept server-side at all). |
| 5 | DELETE `/ip-bans/{ban_id}` | — | `{"status":"unbanned"}` | **Soft delete** (`is_active=False`). |
| 6 | GET `/analytics/overview` | — | `{total_users, total_tenants, total_orders, active_sessions, blocked_users, ip_bans, total_tokens_used}` | `UserSession` is **never written by any code** (Z10) → active_sessions permanently 0. |
| 7 | GET `/analytics/geo-distribution` | — | list `{country, user_count}` | Groups distinct user_ids by `UserSession.country` — empty table → always `[]`. |
| 8 | GET `/analytics/user/{user_id}/activity` | `limit` (1–200, default 50) | list of session dicts | Same empty-table issue. |
| 9 | GET `/audit-log` | `page`, `page_size` (1–200), `action?` | `{logs:[...], total, page, page_size}` | Paginated; action filter exact-match. Note sqladmin writes actions like `block_user`/`add_ip_ban` while REST writes `user.block`/`ip.ban` — **two incompatible action vocabularies**. |
| 10 | GET `/analytics/active-sessions` | — | list of active sessions (last 30 min) | Compares `UserSession.last_activity > utcnow()-30min` on the never-written table. |

Unused response models defined *in this file* (`IPBanResponse`, `AnalyticsResponse`, `GeoDistributionItem`, `UserActivityItem`, `AuditLogItem`) are **never wired as `response_model`** — dead Pydantic duplicates of `admin/schemas.py`.

### 3.3 `app/admin/dashboard.py` (47 lines)

- `GET /_admin/dashboard` — returns `app/admin/templates/dashboard.html` (read from disk at request time) gated by `Depends(get_superadmin)` **which expects a Bearer JWT**. A browser navigation cannot send a Bearer header → **the page is unviewable in practice**: visiting it yields the 401 JSON error. The docstring admits this ("the browser shows the JSON error — callers should redirect to the sqladmin login first") but nothing implements the redirect.
- `GET /_admin/dashboard-login` — 302 to `/_admin/login` (sqladmin). Registered before `setup_admin` so it wins route ordering.

### 3.4 `app/admin/templates/dashboard.html` (403 lines) — the custom admin SPA

Dark-themed single page: 4 stat cards (Active Users Live, Blocked Users, Active IP Bans, Countries), Leaflet map (OpenStreetMap tiles, SRI-pinned), tables for recently blocked users / IP bans / audit log; `setInterval(loadActive, 30000)` live refresh.

**The dashboard is broken in four independent ways (verified against admin/api.py):**
1. **Auth mismatch:** every `fetch` uses `credentials: "include"` (cookie auth) but the REST API requires `Authorization: Bearer` JWT (get_current_user). No Authorization header is ever set → all calls 401 → every widget shows "—" / "Failed to load".
2. `loadActive()` calls **`/api/admin/analytics/active-users`** — **endpoint does not exist** (real one: `active-sessions`, and it returns a list, not `{active_count}`).
3. `loadGeo()` reads `d.distribution` — the API returns a bare **array**; `d.distribution.length` throws → Countries stuck at "—".
4. `loadAudit()`/`loadBlocked()` read `d.items` — the API returns `{"logs": [...]}`; `d.items.length` throws → both tables permanently "Failed to load". `loadBlocked` also filters `action=block_user`, which only matches sqladmin-generated audit entries, not the REST API's `user.block` (vocabulary mismatch above). `Blocked Users` count is thus wrong even if the shape bug were fixed.
Also: the one endpoint that *would* answer the stat cards (`/analytics/overview`) is never called. `removeBan()` DELETE works shape-wise but is unreachable due to bug 1. Escape helper present and used — no XSS in this template. `/analytics/overview`'s `total_tokens_used` etc. unused.

### 3.5 `app/admin/geo.py` (126 lines)

- `_get_reader()` — lazy singleton geoip2 Reader from `GEOLITE2_DB` env or `data/GeoLite2-City.mmdb`; ImportError/missing-file → geolocation silently disabled (documented). Module-level cache, initialized once.
- `locate_ip(ip)` — rejects localhost/`10.`/`192.168.`/`172.` prefixes (note: `172.` prefix over-matches e.g. `172.217.x.x` public Google IPs — sloppy but harmless since result is only "no geo"), then `reader.city(ip)` → `{country, country_code, city, lat, lon}` or None on any exception.
- `detect_device_type(user_agent)` — heuristic UA classifier → mobile/tablet/desktop/bot/unknown.
- **geo.py is imported by NOTHING in app/ (grep: zero importers)** — the whole geolocation/device layer is dead code; UserSession rows (which would carry geo data) are never written anyway (Z10), so the admin geo-distribution endpoint feeds on an eternally empty table end-to-end: `geo.py` (dead) → UserSession (never written) → `/analytics/geo-distribution` (always []) → dashboard map (broken client).

### 3.6 `app/admin/schemas.py` (106 lines)

10 Pydantic response models (`BlockUserRequest`, `IPBanCreate`, `IPBanResponse`, `SiteUserBlockResponse`, `UserSessionResponse`, `AuditLogResponse`, `PaginatedAuditLog`, `ActiveUsersResponse`, `GeoDistributionEntry/Response`) with `from_attributes=True`. **Imported by NOTHING** — `admin/api.py` defines its own inline duplicates and returns raw dicts. The whole file is dead code (the shape it promises — e.g. `PaginatedAuditLog.items`, `GeoDistributionResponse.distribution` — is exactly what the dashboard.html JS *expects* but the API *doesn't* return; the three layers (schemas, api, template) each disagree).

---

## 4. Tenant dashboard (Jinja2)

Server side (`app/api/dashboard.py`, 66 lines): 9 HTML routes (`/dashboard`, `/dashboard/login`, `/{tenant_id}/{chat,products,orders,customers,conversations,crawl,settings}`) — **all unauthenticated** (Z5 CRITICAL): any URL with an enumerable tenant UUID renders the shell; `tenant_id` is injected into `chat.html`/etc. via `'{{ tenant_id }}'` (Jinja autoescape makes this safe server-side). All real data protection is client-side: every fetch attaches `Authorization: Bearer <localStorage token>` and the API layer does enforce JWT+ownership — so the exposure is the HTML shell/nav + tenant-id enumeration, not data (except where noted XSS below).

Static assets: `dashboard/static/css/` and `dashboard/static/js/` contain **only `.gitkeep`** — both are EMPTY despite the StaticFiles mount at `/static` (main.py:226). All CSS is inline in `base.html` + Pico CSS CDN; all JS is inline per-template. Zero cacheable bundles.

Per template:

| Template | Purpose | JS behavior (endpoints) | Notable issues |
|---|---|---|---|
| **base.html** (243) | Layout: top-nav with 7 tenant links, Pico CSS, badge/chat/token-bar styles, `escapeHtml` helper, auth guard | Client-side "auth guard": `localStorage.token` check → redirect to `/dashboard/login` (cosmetic only). Fetches `/api/auth/me` w/ Bearer for the user badge; `logout()` clears localStorage; active-nav highlighting | `https_only` N/A; token in localStorage (XSS-exfiltratable); guard runs before content so the page flashes |
| **login.html** (124) | Login + Register | POST `/api/auth/login` / `/api/auth/register`; stores `access_token` in localStorage; redirects `/dashboard` | **Demo credentials `admin@zemest.ai` / `test123` pre-filled as input values AND printed in a `<details>` block** — shipped to production UI; password min length 4 enforced client-side only |
| **dashboard.html** (192) | Tenant list / first-business onboarding | GET `/api/tenants`, per-tenant GET `/api/tenants/{id}/stats`; create form POST `/api/tenants` then auto POST `/api/tenants/{id}/crawl` (depth 2); FB page-id + page token optional fields | **XSS: `renderTenantCard` interpolates `t.page_name`, `t.website_url`, `o.customer_name`, `p.name`, `o.status` into innerHTML WITHOUT escapeHtml** (helper exists in base but unused here) — a customer name from chat (`<img onerror=...>`) executes in the owner's dashboard. FB token typed into a plain `type="text"` input |
| **chat.html** (141) | Test-chat playground w/ Egyptian-Arabic quick replies (معاك عسل؟ …), marked.js markdown, session token meter | POST `/api/test/chat` `{tenant_id, message, customer_name:'Test Customer'}` per message; token counter from `tokens_used` | **XSS ×2:** customer text `addMessage(msg,'customer')` → innerHTML raw; assistant reply → `marked.parse()` with **no sanitizer** (LLM output/prompt-injection → script in dashboard). Writes real Conversation/Message rows + LLM spend (Z4 test_chat finding) |
| **conversations.html** (102) | Conversation list + message modal | GET `/api/tenants/{id}/conversations`, GET `.../conversations/{id}`; assistant markdown via marked, **customer content escapeHtml'd** (comment documents the policy) | Correctly escaped (best template); assistant markdown still unsanitized but that's the documented trust choice; dates formatted `ar-EG` |
| **crawl.html** (139) | Crawler launcher + job table w/ auto-refresh | POST `/api/tenants/{id}/crawl` `{url, depth:1-3}`; GET `.../crawl/jobs` polling every 8s while jobs active; pre-fills URL from tenant; status icons/badges | `j.url` and `j.error_message` interpolated unescaped (error_message includes upstream exception strings → reflected XSS vector is low-risk but real); SSRF surface per Z5/Z9 |
| **customers.html** (211) | Customer directory + detail + edit modals, debounced search | GET `.../customers?search=`, GET `.../customers/{id}`, PATCH `.../customers/{id}` (partial body) | Consistently uses escapeHtml; edit form omits empty fields (can't clear a field — PATCH-merge semantics leak into UX) |
| **orders.html** (438) | Order pipeline: filter, create modal (EG cascading governorate→city→area via GET `/api/address/governorates|cities|areas`), item rows from products (page_size=200), status buttons, cancel w/ reason, payment-verification fields, external-API retry, CSV export, print CSS | GET/POST/PATCH `/api/tenants/{id}/orders...`, PATCH `.../orders/{id}/notes`, `.../status`, `.../payment`, POST `.../retry-api` | Thoroughly escaped; state machine buttons match service states; `retryApi` re-submits even successful orders (Z7); CSV export naive quoting (no escaping of embedded quotes → CSV injection into Excel possible) |
| **products.html** (408) | Product CRUD: add w/ arbitrary custom attributes, edit, stock toggle, CSV upload (any-format), import-from-URL, search | POST/PATCH/DELETE `.../products...`, POST `.../products/upload-csv` (FormData), POST `.../products/import-url` | Escaped throughout; flexible-attribute UI matches the `extra="allow"` schema contract (Z6); import-url = SSRF surface (Z5) |
| **settings.html** (501) | 8 sections: token usage stats, business profile, delivery fees, MFS wallet numbers (Vodafone Cash/InstaPay/Fawry + account types), Order Placement API config (auth types, JSON template with 15 documented placeholders, sample loader, Test-API button), FB integration, KB info, Danger Zone (delete all crawled products) | GET/PATCH `/api/tenants/{id}` (settings, delivery, `mfs_numbers`, `order_api_config`, FB), GET `.../stats`, GET `.../crawl/jobs`, GET `.../products?page_size=200` + N× DELETE for danger zone, POST `.../orders/{id}/retry-api` for API test | Order-API secrets (`auth_value`, `auth_pass`) round-tripped to the client in GET and typed in plaintext inputs; Test-API re-sends a REAL latest order to the external API (duplicate real order risk, Z7); danger-zone deletes one-by-one (200-product cap then stops silently) |

**Auth model:** login page → JWT in localStorage → every data call Bearer-authenticated; page shells served unauthenticated (server), guarded only by a client-side redirect. Session lifetime = JWT lifetime (24h default). Logout = localStorage clear (no server revocation — refresh/revocation machinery unwired per Z4/Z10).

---

## 5. Function inventory (every Python function in scope)

| File | Function | Params | Returns | Purpose |
|---|---|---|---|---|
| facebook_publisher.py | `publish_feed_post` | page_access_token, page_id, message, link=None, scheduled_publish_time=None | dict `{"id":...}` | Publish text/link post to FB Page feed |
| facebook_publisher.py | `publish_photo` | page_access_token, page_id, photo_url, caption="", scheduled_publish_time=None | dict | Publish photo by URL to FB Page |
| facebook_publisher.py | `publish_video` | page_access_token, page_id, video_url, title="", description="" | dict | Publish video by URL to FB Page |
| facebook_publisher.py | `get_page_insights` | page_access_token, page_id, metric, period, since, until | dict | Page-level insights |
| facebook_publisher.py | `get_page_post_insights` | page_access_token, post_id | dict | Per-post insights |
| facebook_publisher.py | `get_page_info` | page_access_token, page_id | dict | Page name/followers/fans |
| instagram_publisher.py | `create_media_container` | access_token, ig_user_id, media_type, media_url, caption="", **kwargs | str (container id, may be None) | Step 1 of IG publish |
| instagram_publisher.py | `check_container_status` | access_token, container_id | str status | Poll container processing |
| instagram_publisher.py | `publish_media_container` | access_token, ig_user_id, creation_id | dict | Step 2 of IG publish |
| instagram_publisher.py | `publish_image` | access_token, ig_user_id, image_url, caption="" | dict | Convenience single-image publish |
| instagram_publisher.py | `publish_reel` | access_token, ig_user_id, video_url, caption="", share_to_feed=True, cover_url=None | dict | Reel publish w/ 150s status polling |
| instagram_publisher.py | `publish_story` | access_token, ig_user_id, media_url, media_type="IMAGE" | dict | Story publish |
| instagram_publisher.py | `get_ig_user_insights` | access_token, ig_user_id, metric, period, since, until | dict | Account-level IG insights |
| instagram_publisher.py | `get_online_followers` | access_token, ig_user_id | dict | online_followers heatmap raw |
| instagram_publisher.py | `get_ig_media_insights` | access_token, media_id | dict | Per-media insights |
| instagram_publisher.py | `get_best_time_to_post` | access_token, ig_user_id | dict {heatmap, top_slots} | Compute top-5 posting slots |
| instagram_publisher.py | `_format_hour` | hour: int | str | 12h AM/PM label |
| postiz_client.py | `PostizClient.__init__` | base_url=None | — | Init client state |
| postiz_client.py | `PostizClient._get_client` | — | httpx.AsyncClient | Lazy shared HTTP client |
| postiz_client.py | `PostizClient.close` | — | None | Close HTTP client |
| postiz_client.py | `PostizClient._headers` | — | dict | Cookie + auth headers |
| postiz_client.py | `PostizClient.login` | email, password | bool | Postiz JWT login |
| postiz_client.py | `PostizClient.register` | email, password, name="" | bool | Register Postiz account |
| postiz_client.py | `PostizClient.check_can_register` | — | bool | Registration open? |
| postiz_client.py | `PostizClient.list_integrations` | — | list[dict] | Connected social accounts |
| postiz_client.py | `PostizClient.get_connect_url` | provider | str/None | OAuth connect URL |
| postiz_client.py | `PostizClient.create_post` | posts, schedule_at=None, group_id=None | dict/None | Create/schedule Postiz posts |
| postiz_client.py | `PostizClient.list_posts` | page=1, limit=50, filter_type="scheduled" | dict/None | Paginated post list |
| postiz_client.py | `PostizClient.get_post` | post_id | dict/None | Single post |
| postiz_client.py | `PostizClient.delete_post` | group_id | bool | Delete post by group |
| postiz_client.py | `PostizClient.update_post_date` | post_id, new_date, action="update" | bool | Reschedule |
| postiz_client.py | `PostizClient.find_free_slot` | integration_id=None | str/None | Next free slot ISO date |
| postiz_client.py | `PostizClient.get_post_statistics` | post_id | dict/None | Post analytics |
| postiz_client.py | `PostizClient.generate_posts` | prompt, number_of_posts=3, platforms=None | list[dict]/None | Streamed AI generation |
| postiz_client.py | `PostizClient.health_check` | — | bool | Sidecar reachability |
| postiz_client.py | `get_postiz_client` (module) | — | PostizClient | **Process-wide singleton accessor** |
| celery_app.py | (module-level config) | — | — | Celery app, beat schedule, imports |
| crawl_tasks.py | `_run_async` | coro | Any | Event-loop bridge |
| crawl_tasks.py | `run_crawl_pipeline` (task) | self, job_id, tenant_id, url, depth=3 | None | Full crawl pipeline entry |
| crawl_tasks.py | `_crawl_pipeline_async` | job_id, tenant_id, url, depth | None | Crawl→extract→index with status transitions |
| crawl_tasks.py | `_extract_and_save_products` | db, tenant_id, pages | int | LLM product extraction + insert |
| notification_tasks.py | `send_order_notification` (task) | tenant_id, order_id | None | Async order email |
| notification_tasks.py | `_send_notification` | tenant_id, order_id | None | Load tenant/order, call notify_new_order |
| scheduling_tasks.py | `publish_scheduled_posts` (task) | — | dict counts | Beat: publish due posts |
| scheduling_tasks.py | `_publish_due_posts_async` | — | dict | Claim/publish/fail loop (limit 50) |
| scheduling_tasks.py | `_publish_post` | post, tenant | str platform_post_id | Platform dispatch |
| scheduling_tasks.py | `_publish_to_facebook` | post, tenant | str | FB media-type mapping |
| scheduling_tasks.py | `_publish_to_instagram` | post, tenant | str | IG media-type mapping |
| scheduling_tasks.py | `_run_async` | coro | Any | Event-loop bridge |
| style_tasks.py | `_run_async` | coro | Any | Event-loop bridge |
| style_tasks.py | `rebuild_all_personalities` (task) | self | None | Weekly all-tenant style rebuild |
| style_tasks.py | `_rebuild_all_personalities_async` | — | None | Iterate tenants, per-tenant sessions |
| style_tasks.py | `rebuild_tenant_personality` (task) | self, tenant_id | None | Single-tenant rebuild (**never dispatched**) |
| style_tasks.py | `_rebuild_tenant_personality_async` | tenant_id | None | Load tenant, rebuild |
| admin_panel.py | `AdminAuth.__init__` | secret_key=None | — | Backend init |
| admin_panel.py | `AdminAuth.login` | request | bool | Credential check + session set |
| admin_panel.py | `AdminAuth.logout` | request | bool | Session clear + audit |
| admin_panel.py | `AdminAuth.authenticate` | request | Response/bool | Session gate |
| admin_panel.py | `_write_audit` | admin_id, action, target_type, target_id, metadata, ip | None | Best-effort audit insert |
| admin_panel.py | `_current_admin_id` | request | UUID/None | Session admin id |
| admin_panel.py | `BaseAdminView.is_visible` / `is_accessible` | request | bool | Nav visibility / gate |
| admin_panel.py | `SiteUserAdmin.on_model_change` | data, model, is_created, request | None | Block metadata + audit |
| admin_panel.py | `IPBanAdmin.on_model_change` | data, model, is_created, request | None | CIDR validation + banned_by |
| admin_panel.py | `IPBanAdmin.after_model_change` | data, model, is_created, request | None | **invalidate_all() crash + audit** |
| admin_panel.py | `IPBanAdmin.after_model_delete` | model, request | None | **invalidate_all() crash + audit** |
| admin_panel.py | `setup_admin` | app, engine=None | Admin | Mount sqladmin at /_admin |
| admin/api.py | `require_superadmin` / `get_superadmin` | user (Depends) | User | JWT + is_superadmin gate |
| admin/api.py | `block_user_site_wide` | user_id, req, admin, db | dict | Site-wide user block |
| admin/api.py | `unblock_user` | user_id, admin, db | dict | Remove block |
| admin/api.py | `list_ip_bans` | admin, db | list | Active bans |
| admin/api.py | `create_ip_ban` | req, admin, db | dict | Ban IP/CIDR |
| admin/api.py | `delete_ip_ban` | ban_id, admin, db | dict | Soft-unban |
| admin/api.py | `get_analytics_overview` | admin, db | dict | 7 platform counters |
| admin/api.py | `get_geo_distribution` | admin, db | list | Users by country |
| admin/api.py | `get_user_activity` | user_id, admin, db, limit | list | Session history |
| admin/api.py | `get_audit_log` | admin, db, page, page_size, action | dict | Paginated audit |
| admin/api.py | `get_active_sessions` | admin, db | list | Live sessions (30 min) |
| admin/api.py | `_write_audit_log` | db, admin, action, target_type, target_id, ip, metadata | None | Audit insert (flush, caller commits) |
| admin/dashboard.py | `admin_dashboard` | request, admin | HTMLResponse | Serve admin SPA (Bearer-gated) |
| admin/dashboard.py | `dashboard_login_redirect` | — | RedirectResponse | → /_admin/login |
| admin/geo.py | `_get_reader` | — | Reader/None | Cached geoip2 reader |
| admin/geo.py | `locate_ip` | ip | dict/None | Geo lookup |
| admin/geo.py | `detect_device_type` | user_agent | str | UA heuristic |
| admin/schemas.py | (10 Pydantic models) | — | — | **Dead — zero importers** |

---

## 6. Issues / risks (prioritized, with file:line)

**CRITICAL**
1. **Postiz singleton cross-tenant session hijack** — postiz_client.py:417-425 + api/postiz.py:66-81: any tenant owner's `/postiz/login` overwrites the one global Postiz JWT; list/create/delete posts then act on that session (Z5 confirmed).
2. **Admin ban CRUD is 100% broken** — admin_panel.py:281,299 call `IPBanMiddleware.invalidate_all()` (nonexistent; security.py:223-268) → AttributeError → sqladmin 500 on every IP-ban create/edit/delete; ban audits (written after the call) never persist (Z10 proven, re-verified).
3. **Custom admin dashboard is unusable end-to-end** — dashboard.py:24-37 gates an HTML page behind Bearer-JWT (browsers can't pass it), and templates/dashboard.html fetches `/api/admin/analytics/active-users` (nonexistent endpoint; real: `active-sessions`), reads `d.distribution`/`d.items` shapes the API never returns, and sends cookie credentials to JWT-only endpoints — every widget permanently "—"/"Failed to load".
4. **Dashboard XSS** — dashboard.html:87-101 (`renderTenantCard`: `t.page_name`, `o.customer_name`, `p.name` unescaped) and chat.html:66-81 (`addMessage`: customer text raw innerHTML; assistant via `marked.parse` unsanitized) — customer-controlled strings execute in the merchant dashboard; combined with unauthenticated page shells (Z5) this is a stored-XSS chain.
5. **Admin geo/analytics pipeline is hollow end-to-end** — geo.py has zero importers; UserSession never written (Z10); `/analytics/overview|geo-distribution|active-sessions|user activity` all read the empty table; BlockedUser blocks are never enforced anywhere (grep-verified; only analytics counts them).
6. **scheduled publishing duplication race + terminal failures** — scheduling_tasks.py:35-41: SELECT-claim without `FOR UPDATE SKIP LOCKED`; minute-cadence beat + 150s reel polling (instagram_publisher.py:152-159) + concurrency=2 → two ticks can claim/publish the same post (duplicate FB post); failed posts are terminal (`retry_count` write-only, scheduling_tasks.py:74); worker crash mid-publish leaves rows stuck `publishing` forever.

**HIGH**
7. **IG story publish always broken** — scheduling_tasks.py:185 (`media_type="IMAGE" if post.media_type == "photo" else "VIDEO"` inside the story branch → always VIDEO) × instagram_publisher.py:45 (`video_url` key for any non-IMAGE type) → image stories send image URL as video_url → guaranteed Graph error.
8. **FB multi-image/carousel silently degraded** — scheduling_tasks.py:117-143 publishes only `media_urls[0]`; unknown media_type falls back to caption-only feed post instead of failing (silent content loss).
9. **Dead retry declarations** — crawl_tasks.py:21, style_tasks.py:23,58 (`max_retries` set, `self.retry()` never called); notification task has no retry at all; combined with the pre-commit `.delay()` races (api/crawl.py:50, agent.py:437 — Z5/Z8) crawls/orders silently no-op.
10. **sqladmin user CRUD bricks users / stores plaintext** — admin_panel.py:182 (`form_columns` includes `hashed_password`, no hashing hook): admin-set passwords are stored raw; that user can never log in.
11. **`rebuild_tenant_personality` is dead** — style_tasks.py:59 registered but zero dispatchers.
12. **Admin session never re-validates** — admin_panel.py:99-110 checks only session-key UUID presence; demoting/deleting a superadmin doesn't invalidate live admin cookies (no TTL config; secret reused from JWT_SECRET_KEY, main.py:191-197, https_only=False).
13. **Token-in-query-string on all Graph GET calls** — facebook_publisher.py:157,187,209; instagram_publisher.py:80-82,204-206,233-237,259-262 (log/proxy leakage; Z5 pattern).

**MEDIUM**
14. Single default Celery queue, no routes — celery_app.py:14-37: 600s crawls block minute-cadence publishing and order emails on the same 2-slot worker.
15. Duplicate product-extraction pipelines drift — crawl_tasks.py:86-171 vs api/crawl.py:137+ (inline sync twin; different token accounting).
16. `publish_media_container` id may be None → `platform_post_id=""` recorded as success (instagram_publisher.py:67 + scheduling_tasks.py:64-68).
17. tz-aware `scheduled_at` from client → TypeError 500 at scheduling.py:78 (`<= datetime.utcnow()`); naive-UTC convention is implicit everywhere (scheduling_tasks.py:34, crawl_tasks.py:42).
18. `get_best_time_to_post` day indexing assumes 0=Sunday (instagram_publisher.py:295-304) vs Meta's 1-7 convention — day labels likely off by one; Z3 separately noted best-time semantics in postiz_chat.
19. Demo credentials pre-filled/printed in production login page — login.html:36-39,49-51 (`admin@zemest.ai`/`test123`).
20. Bare `Exception` + no `raise_for_status` in all 16 publisher functions; non-JSON error responses crash as JSONDecodeError; error strings (may embed token-bearing URLs) persisted to `error_message` and returned by insights endpoints (scheduling.py:348,363,388,444 — Z5).
21. Postiz `generate_posts` streams without checking status (postiz_client.py:374-389); no auto-login despite POSTIZ_EMAIL/PASSWORD config existing (config.py:62-63).
22. settings.html Test-API button re-submits a real order to the external API (settings.html:438-466; duplicate-order risk Z7); order-API secrets round-trip in plaintext via GET tenant.
23. crawl.html interpolates `j.url`/`j.error_message` unescaped (crawl.html:107,113); orders.html CSV export lacks quote-escaping (CSV injection, orders.html:419-431).
24. Two parallel admin auth systems (sqladmin signed-cookie session vs REST Bearer JWT) with incompatible action vocabularies (`block_user` vs `user.block`) in one audit log.
25. Empty static dirs mounted (main.py:226; `.gitkeep` only) — all JS/CSS inline per page (no caching, duplication).

---

## 7. Quality ratings (1–10)

| File | Score | Justification |
|---|---|---|
| facebook_publisher.py | **6** | Clean, documented, correct Graph shapes, token in POST body; but bare exceptions, no retry/status checks, no multi-image, new client per call, GET tokens in query |
| instagram_publisher.py | **5.5** | Good two-step container implementation incl. reel polling and best-time math; but `video_url`-key bug breaks stories/carousels, poll-then-publish-anyway flaw, day-index assumption, same error/retry weaknesses |
| postiz_client.py | **6.5** | Most complete client: streaming AI, full CRUD, defensive error handling, unit-tested; but the singleton is an architectural defect (cross-tenant), error-swallowing hides auth failures, no token expiry/auto-login |
| celery_app.py | **6** | Correct minimal config, sane beat entries, worker recycling; no queues/routes/DLQ, name-drift trap, shared Redis db |
| crawl_tasks.py | **5** | Correct status machine and per-product resilience; dead max_retries, dispatch race (upstream), duplicated extraction logic, no idempotency |
| notification_tasks.py | **5** | Does one thing cleanly; no retry, silent no-op on missing rows, race with uncommitted order |
| scheduling_tasks.py | **5.5** | Solid claim-then-publish structure and per-post error capture; SELECT race without row locking, terminal failures (write-only retry_count), unreachable story branch, silent FB fallback |
| style_tasks.py | **6.5** | Small, correct, per-tenant isolation done right; dead retry params, one dead task, detached-tenant pattern |
| admin_panel.py | **5** | Thoughtful sqladmin usage (auth backend, append-only audit, CIDR validation); but invalidate_all crash bricks ban CRUD, plaintext hashed_password form, session never re-validates, doc drift |
| admin/api.py | **6** | Uniform superadmin guard, consistent audit writes, validation on bans; reads never-written tables, unused response models, action-vocabulary split, BlockedUser unenforced |
| admin/dashboard.py | **3** | 47 lines that cannot work in a browser (Bearer-gated HTML) — acknowledged in its own docstring |
| admin/geo.py | **7** | Clean, documented, graceful-degradation design — but 100% dead code |
| admin/schemas.py | **3** | Well-formed models, zero importers; actively misleading (promises shapes neither API nor template use) |
| admin/templates/dashboard.html | **4** | Polished UI (SRI-pinned Leaflet, escaping discipline) wired to a nonexistent endpoint, wrong response shapes, and mismatched auth — functionally dead |
| dashboard/templates/base.html | **6.5** | Solid shared layout + correct escapeHtml; client-side-only auth guard, localStorage token |
| login.html | **5** | Works, dual login/register; demo creds shipped, min-length only client-side |
| dashboard.html | **5** | Rich onboarding + stats; XSS in tenant card rendering |
| chat.html | **5** | Nice UX (quick replies, token meter); double XSS hole (customer + marked output) |
| conversations.html | **7.5** | Correct escaping policy (documented), clean modal; unsanitized assistant markdown is a stated trust choice |
| crawl.html | **6.5** | Good async job UX with auto-refresh; minor unescaped fields |
| customers.html | **7** | Consistent escaping, debounced search, edit modal; can't clear fields |
| orders.html | **7.5** | Most complete page: state machine, cascading geo, payment verification, print/CSV; retry re-submission + CSV quoting nits |
| products.html | **7.5** | Flexible-attribute UI matches schema contract; all actions escaped |
| settings.html | **7** | Impressive breadth (MFS, order-API templating with docs); plaintext secret round-trip, destructive test button, N+1 danger-zone deletes |

**Layer verdict ≈ 5.5/10** — the scheduling/publishing core is genuinely functional and the tenant dashboard is feature-rich, but the admin subsystem is largely non-functional (broken sqladmin hooks, dead custom dashboard, hollow analytics), the task layer lacks the reliability machinery its declared settings imply, and cross-cutting defects (singleton, races, XSS, terminal failures) sit exactly on the publish/notify paths that run unattended.
