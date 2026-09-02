# Task 18-c — Performance Audit: Backend ↔ Frontend Data Flow (Speed & Sharpness)

Scope: `/home/z/my-project` (Next.js 15 App Router, src/) + FastAPI backend at `repos/zemest/daemon_backend.py` (uvicorn :8000).
Method: code reading + **live measurements** against the running daemon (seeded tenant `1f8c6249-…`, SQLite `zemest_local.db`, OPENROUTER_API_KEY unset in sandbox → LLM path simulated by code analysis + log evidence).
Research only — no code was modified.

---

## 1. Perf Scorecard

### FRONTEND (src/)

| Area | Verdict | Evidence |
|---|---|---|
| Bundle / config | **B** | `next.config.ts`: `output: "standalone"`, avif/webp images, `skipTrailingSlashRedirect` (redirect-loop fix). No PPR/experimental flags (fine at this scale). Prod build not yet produced (only `.next/dev` exists) — bundle sizes unmeasured. |
| Client/server split | **C** | **14/14 files in `src/app/dashboard/**` are `"use client"`** (all pages + `[tenantId]/layout.tsx`). Zero server components in the dashboard subtree → every dashboard page ships JS + fetches after hydration. Marketing home (`src/app/page.tsx`) *is* a server shell importing client islands — good. No `loading.tsx` anywhere → no route-level streaming/skeleton. |
| Data fetching | **B+** | No React Query / SWR usage anywhere (grep: 0 hits). Instead a hand-rolled SWR-lite in `src/lib/zemest-api.ts`: in-flight dedupe map (:73), memCache + sessionStorage (:26-56), `api.peek()` instant paint (:123), hover-prefetch on tenant cards (`dashboard/page.tsx:191-193`). Overview/scheduler use `Promise.all` correctly. |
| Fetch robustness | **D** | `zemest-api.ts request()` (:75-103): **no AbortSignal/timeout, no retry**. BFF proxy `api/zemest/[...path]/route.ts:63` → `fetchWithHeal` main fetch **has no timeout** (`backend-health.ts:72`). Only demo routes + health ping set `AbortSignal.timeout`. |
| Heal-storm risk | **LOW (OK)** | `backend-health.ts:37-61`: module-level single-flight promise `healing` — all concurrent callers share one boot; daemon `start` double-forks and is idempotent (pid check). One Node process in standalone → no multi-process storm. Minor: no backoff between attempts, lock resets on failed heal (bounded to 1 concurrent restart). |
| Dead weight | **B-** | `@tanstack/react-query` in package.json:50 but **never imported** (dead dep → install/CI bloat, not bundle). `src/lib/api-client.ts` (direct-to-:8000 client, no timeouts/cache) is **never imported** — dead code. No moment/lodash. framer-motion only on marketing pages + `/dashboard` home (via `Navbar`); **not** in `[tenantId]/*` bundles. Unused shadcn heavies (chart/carousel/calendar) are tree-shaken (0 imports from app). |
| Static assets | **B-** | AVIF/WebP everywhere (good). **`layout.tsx:46` sets favicon to `/zemest-logo.png` = 396,867 B**; a 10 KB `zemest-logo-96.png` exists unused. 417 KB `tavus-hero.avif` etc. are behind `next/image` with proper formats. |
| Middleware | **A** | `src/middleware.ts`: pure cookie/regex check, zero I/O, no backend fetch per request. Runs on `/api/*` too but returns instantly. |

### BACKEND (repos/zemest)

| Area | Verdict | Evidence |
|---|---|---|
| Process model | **C** | `daemon_backend.py:49-50`: uvicorn started with **no `--workers`** → single process (confirmed: exactly 1 uvicorn pid). All traffic + 2 background workers share one event loop. |
| Startup | **B+** | No import-time model loads (LLM client lazy, Whisper lazy `transcription.py:47`); `get_settings` lru_cached. Lifespan runs ~45 idempotent DDL statements (`main.py:40-185`) — fast on SQLite, would be slow on Postgres (ALTER = table rewrite). |
| DB layer | **B** | **Async** SQLAlchemy + aiosqlite, session-per-request via `get_db` (`database.py:30-39`). Composite indexes exist: orders(tenant,status), products(tenant,is_active), messages(conversation,created). **Missing**: `orders.created_at` (today/month revenue + recent-orders ORDER BY), `conversations.last_message_at` (list ORDER BY). **SQLite journal mode not set to WAL** (`database.py:13` — no PRAGMA) → writer lock (trainer/token_usage writes) stalls readers. |
| N+1 / query count | **D** | `get_tenant_stats`: **13 sequential awaited aggregates** per call (`tenant_service.py:37-155`). `list_customers`: **3 queries per row → 151 queries** for a 50-row page (`customers.py:61-74`). Conversations/products/orders use pagination + `selectinload` (good). |
| LLM calls | **B / C** | Provider = **OpenRouter** (`llm_client.py`) with pooled httpx client, real timeouts (connect 5 / read 25 / write 10 / pool 5), model fallbacks, no-key circuit breaker, 0.2-0.6s backoff — solid. **But**: no streaming; **2 sequential LLM round-trips per chat message** (retrieval `_select_nodes` then main completion); `litellm`/`llm_gateway.py` researched (RESEARCH_CONCURRENT_LLM.md) but not wired in. |
| External API calls | **C** | Channels status: 3 **sequential** live Graph validations, new `AsyncClient` per call, 12s timeouts, **no cache** (`channels.py:119-173`). Insights overview: 3 sequential Graph calls, no cache (`scheduling.py:338-370`). `auth_service.py:43`: `httpx.AsyncClient()` **with no timeout** (FB login can hang). |
| Caching | **D** | **None** for tenant stats / products / channels / insights — recomputed per request. Only demo_agent sessions have TTL (`demo_agent.py:409-421`). No Redis in this deployment (slowapi falls back to memory). |
| Event-loop blockers | **C** | bcrypt password verify runs inline in async handler — **measured 248ms** per login (blocks ALL concurrent requests on the single worker). `crawl.py:52-57`: **synchronous** `celery_app.control.inspect(timeout=1).ping()` inside async endpoint → ~1s event-loop stall on every crawl start. Whisper transcription correctly uses `to_thread`. |
| Live baseline (measured) | — | `GET /` 2-4ms; `/api/tenants` 5ms; `/tenants/{id}/stats` **12-34ms** (13 queries); `/customers` **20-28ms** (N+1, N≈4); `/products` 8-10ms; `/orders` 6-8ms; `/conversations` 7-8ms; **login 248ms** (bcrypt). BFF adds ~50ms in dev mode. |

---

## 2. Dashboard Waterfall / Duplicate-Fetch Map

All requests go browser → BFF `/api/zemest/*` (Next server) → FastAPI. Cookie→Bearer translation per hop.

| Page | Waterfall (in order) | Sequential? | Duplicate/cache behavior |
|---|---|---|---|
| `/dashboard` (tenant list) | 1. `GET /tenants` → 2. `Promise.all` of `GET /tenants/{id}/stats` × N | **2-deep waterfall** (`dashboard/page.tsx:75-95`: list awaited before stats fan-out) | Stats re-fetched on every visit (no TTL); hover-prefetch warms cards → click-through to overview re-fetches the *same* stats within seconds |
| `/dashboard/[t]` (overview) | 1. `api.peek` (instant paint if cached) → 2. `Promise.all([GET /tenants/{t}, GET /tenants/{t}/stats])` | Parallel ✅ (`[tenantId]/page.tsx:42-45`) | cachedGet always refetches (stale-while-revalidate by design); inflight dedupe only within same mount burst |
| `/dashboard/[t]/customers` | 1. `GET /customers` (page 1, 50 rows) | Single call | **Backend N+1: 151 queries** per render |
| `/dashboard/[t]/products` | 1. `GET /products` (page 1, 50 rows) | Single call | Search is **client-side filter** (`products/page.tsx:64-68`) — backend `?search=` param unused; >50 products silently unfetchable |
| `/dashboard/[t]/conversations` | 1. `GET /conversations` (page 1, 20) → 2. on thread click: `GET /conversations/{id}` | User-triggered, acceptable | Thread detail loads **all messages, unbounded** (`conversations.py:65-95`, no limit/pagination); fetch not aborted on thread switch (`conversations/page.tsx:201-219` — `cancelled` flag only, no AbortController) |
| `/dashboard/[t]/chat` (playground) | 1. `POST /test/chat` | Single request | **Backend chain per message: ~6 sequential DB awaits + LLM#1 (retrieval `retriever.py:118`) + LLM#2 (agent `agent.py:165`) — 2 sequential OpenRouter round-trips, no streaming** |
| `/dashboard/[t]/channels` | 1. `GET /channels` | Single call | **Backend fans into 3 sequential Graph API calls** (`channels.py:122,141,160`), 12s timeout each, no cache → 1-2.4s page |
| `/dashboard/[t]/insights` | 1. `GET /insights/overview?days=30` | Single call | **Backend: 3 sequential Graph calls** (`scheduling.py:341,347,360`), no cache → 1-3s page |
| `/dashboard/[t]/scheduler` | 1. `Promise.all([GET /schedule/posts, GET /calendar/url])` | Parallel ✅ (`scheduler/page.tsx:70-73`) | Fine |
| `/dashboard/[t]/settings` | 1. `GET /tenants/{t}` | Single call | Fine |
| Any mutation | `POST/PATCH/...` → `invalidateCache()` | — | **Global cache nuke** (`zemest-api.ts:59-70`): any mutation clears *every* cached GET → all mounted pages refetch on next interaction (over-invalidation) |

Cross-cutting: **no request in the dashboard has a client-side timeout or retry**; the BFF proxy adds one hop + heal-retry but no timeout; backend has per-tenant `?page=` support but several pages fetch only page 1.

---

## 3. Top 10 Ranked Speed Wins (backend / API / data-layer only)

Gains are estimates (sandbox measurements + provider RTT assumptions); ranked by (users affected × ms saved).

| # | Fix | Location | Expected gain |
|---|---|---|---|
| **1** | **Kill the 2nd LLM round-trip per chat message.** `retrieve_context` → `_select_nodes` makes an OpenRouter call (temp 0, max_tokens 50) *before* the main completion, sequentially. Cache the TOC per tenant in memory (tree_json is only rebuilt on crawl), and cache/derive node selection (skip LLM navigation for ≤3-token queries; or short-TTL LRU keyed by tenant+normalized query). At minimum run node selection concurrently with history/system-prompt build. | `repos/zemest/app/ai/agent.py:93-95` + `repos/zemest/app/knowledge/retriever.py:100-140` | **−1.5 to −3s per chat reply (≈−50% chat latency)**; also −1 LLM call/message (cost) |
| **2** | **Fix `list_customers` N+1**: 3 queries per customer (orders count, conv count, total spent) → replace with 3 `GROUP BY customer_id` aggregates over the page's customer ids (or one join+FILTER query). | `repos/zemest/app/api/customers.py:61-74` | **−90% query count** (151→~5); customers page **−200-400ms** at 50 rows; removes multi-hundred-ms lock window on single worker |
| **3** | **Cache `get_tenant_stats`** (in-memory 15-30s TTL keyed by tenant, invalidated on order/message writes) and/or collapse 13 sequential COUNT/SUMs into 1-2 multi-aggregate queries (`COUNT(...) FILTER (WHERE …)` / subselects). | `repos/zemest/app/services/tenant_service.py:37-155` | stats endpoint **−60-90%** (measured 12-34ms → ~2-5ms; scales with rows); `/dashboard` home with N tenants: 13N queries → ≤N cache hits, **−300-600ms backend time** |
| **4** | **Stream chat replies (SSE) end-to-end**: `test/chat` → BFF proxy → chat playground. Currently the client waits for the *full* completion (agent saves messages/usage after generation; response is one JSON blob). Add a streaming variant (`stream: true` to OpenRouter, persist after completion) and pass `text/event-stream` through the BFF (`fetchWithHeal` already passes `res.body` through). | `repos/zemest/app/ai/llm_client.py:159-163` (non-streaming post), `repos/zemest/app/api/test_chat.py:42-48`, `src/app/api/zemest/[...path]/route.ts:63-76`, `src/app/dashboard/[tenantId]/chat/page.tsx:47-49` | **TTFT ~400-800ms instead of 2-6s**; perceived latency −60-80% on the flagship chat flow |
| **5** | **Parallelize + cache external Graph calls** in channels status and insights overview: `asyncio.gather` the 3 platform validations / 3 insight calls, reuse ONE `httpx.AsyncClient` (module-level, like `llm_client._get_client()`), and add a 60s per-tenant cache. | `repos/zemest/app/api/channels.py:119-173` (+72-96 new client per call), `repos/zemest/app/api/scheduling.py:329-372` | channels & insights pages **−1-2s** (3× sequential RTT → 1× parallel, then cache hit ≈0ms on revisit); also removes 3 TCP+TLS handshakes per request |
| **6** | **Add timeout to `fetchWithHeal`'s primary fetch** (and to `zemest-api.ts request()`): merge `AbortSignal.timeout(30_000)` into the fetch init; add 1 retry with backoff for 502/503 in the BFF. A slow/hung FastAPI request currently hangs the browser fetch indefinitely (undici default ≈ no timeout). | `src/lib/backend-health.ts:70-72` (`return await fetch(path, init)` — no signal), `src/lib/zemest-api.ts:75-83` | **Bounds worst-case p99** (hung request 300s → 30s); prevents spinner-forever states; heal path already single-flight ✅ |
| **7** | **Move bcrypt off the event loop**: `verify_password` is sync CPU work inside async `login_user` — measured **248ms of full event-loop block per login** on the single worker (stalls every concurrent request, incl. webhook acks). Wrap in `asyncio.to_thread`. | `repos/zemest/app/services/auth_service.py:30-38` (call), `repos/zemest/app/utils/security.py:34,51-57` (CryptContext) | **−245ms event-loop stall per login**; concurrent-request p95 during logins improves ~10× on the single worker |
| **8** | **Favicon swap**: `layout.tsx` metadata icon points to `/zemest-logo.png` (397 KB PNG); the 10 KB `zemest-logo-96.png` already exists. | `src/app/layout.tsx:46` (`icons: { icon: "/zemest-logo.png" }`) | **−387 KB on first visit to every route** (favicon is fetched per page navigation until cached); ~−1-3s on 3G/edge-preview first loads; zero-risk one-line change |
| **9** | **Enable SQLite WAL + `synchronous=NORMAL`** (async engine `connect` event / `connect_args` pragma): default rollback-journal mode means every write (silent-trainer commits every 45s, token_usage insert per LLM call, message writes) takes an exclusive lock that **blocks all reads** (stats, lists) for the lock duration. Pair with `--workers 2` (or stay 1 worker but with WAL) — and add the missing hot indexes `orders(created_at)`, `conversations(last_message_at)`. | `repos/zemest/app/database.py:12-13` (engine create), `repos/zemest/daemon_backend.py:49-50` (uvicorn args), indexes via `app/models/order.py`, `app/models/conversation.py` + startup DDL in `app/main.py:40+` | Removes read stalls during writes (smoother p95 under load); recent-orders/today-revenue queries stop degrading with table growth; **−50-80% variance on stats endpoints during trainer cycles** |
| **10** | **Stop blocking the event loop with the sync Celery ping on crawl start** (`inspect(timeout=1)` is synchronous kombu I/O in an async handler; also runs when no Celery/Redis is configured). Use `asyncio.to_thread`, or skip the ping entirely when `REDIS_URL` is unconfigured (env is known at boot). | `repos/zemest/app/api/crawl.py:49-57` | **−1s stall for ALL concurrent requests each time a crawl is started**; crawl-start latency −1s itself |

### Runner-ups (11-16, still worth doing)

11. **`auth_service.py:43`**: `httpx.AsyncClient()` with no timeout on Facebook login (`/me`) — one hung FB call wedges the login route; add `timeout=10.0`. (auth_service.py:41-50)
12. **Remove dead `@tanstack/react-query` dependency** (`package.json:50`) and dead `src/lib/api-client.ts` (0 imports) — faster installs/CI, less confusion. (not a runtime bundle win)
13. **Scope cache invalidation**: `invalidateCache()` nukes all GETs on any mutation (`src/lib/zemest-api.ts:59-70`) → replace with path-prefix invalidation so e.g. creating a product doesn't force tenants/stats/conversations refetches.
14. **Paginate conversation thread messages** (`repos/zemest/app/api/conversations.py:65-95` loads all messages, no limit) + abort stale thread fetches (`src/app/dashboard/[tenantId]/conversations/page.tsx:201-219`).
15. **Use server-side `?search=`** on products/customers instead of fetching page 1 + client filter — fixes the silent >50-rows cap and cuts payload for filtered views. (`src/app/dashboard/[tenantId]/products/page.tsx:51,64-68`)
16. **Dashboard home 2-step waterfall** (`src/app/dashboard/page.tsx:75-95`): add a backend `GET /tenants?include=stats` (one round trip, batched aggregates) — removes the list→stats dependency; with win #3 the fan-out becomes nearly free anyway.

### Non-issues (verified, no action needed)
- **Heal-storm**: `ensureBackend()` single-flight lock + idempotent daemon start = safe (`src/lib/backend-health.ts:37-61`).
- **Middleware cost**: pure cookie check, no I/O per request (`src/middleware.ts`).
- **Webhook acks**: Messenger webhook returns 200 immediately and processes via `BackgroundTasks` (`app/api/webhook.py:47-79`).
- **LLM client hygiene**: pooled httpx client, sane timeouts, fallback chain, no-key circuit breaker (`app/ai/llm_client.py:28-46`).
- **Transcription**: whisper runs in a thread (`app/services/transcription.py:27`); demo chat is rule-based, zero LLM (`app/api/demo_chat.py`).
- **Rate limiter**: slowapi with in-memory fallback — negligible per-request overhead.
