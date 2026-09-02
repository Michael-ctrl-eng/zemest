# E5 — Dashboard Data Audit (mock vs real)

**Agent:** E5 (error-finder, read-only) · **Date:** 2026-09-01 · **Scope:** every page under `src/app/dashboard/**` + `src/app/admin/**` in /home/z/my-project (the live dev tree, not repos/zemest-platform).
**Method:** read every page file, traced each to its BFF endpoint, live-tested all endpoints with an owner JWT (`owner@cairo-sneakers.com`) and superadmin cookie (`admin@zemest.ai`), curl-fetched every route on :3000, checked SSR output for error boundaries.
**Prior context honored:** Task 18 (30/76 wiring, N+1/stats fixes) and Task 19 (admin fully wired) are not re-reported.

**Environment tested:** FastAPI :8000 (running, untouched), Next dev :3000. DB state at audit time: tenant "Cairo Sneakers" (`008dbf3a-64b5-4873-b914-407d2d9671bc`), 3 products, 1 customer (محمود), 1 test conversation (with messages), 0 orders, 0 crawl jobs, 0 scheduled posts, style profile BUILT (by the Task-19 silent trainer).

---

## 1. Page inventory + classification

### Dashboard (`src/app/dashboard/**`) — 13 pages + 1 layout

| # | Route (file) | Classification | Data source (endpoint via BFF `/api/zemest/*`) | Live test |
|---|---|---|---|---|
| 1 | `/dashboard` (`dashboard/page.tsx`) | **REAL** | `GET /tenants` + `GET /tenants/{id}/stats` per tenant (create: `POST /tenants`) | 200, 1 tenant + real stats. ⚠ silent per-tenant stats catch (F6), IG/WA chips dead (F3), formatting (F7) |
| 2 | `/dashboard/[tenantId]` (overview) | **REAL** | `GET /tenants/{id}` + `GET /tenants/{id}/stats` (SWR cache-seeded via `api.peek`) | 200: 3 products, 0 orders, `recent_orders:[]`, `top_products:[]` → both EmptyStates render |
| 3 | `/dashboard/[tenantId]/chat` | **REAL** | `POST /test/chat` (creates real conversation/customer/messages; tokens from TokenUsage) | Endpoint exists + used earlier (conv. 8df3575f created through it). ⚠ owner-mode toggle cosmetic (F4) |
| 4 | `/dashboard/[tenantId]/channels` | **REAL** | `GET /tenants/{id}/channels`, `POST …/channels/{messenger\|instagram\|whatsapp}`, `DELETE …/channels/{platform}`, `POST …/test` | 200 honest: all 3 "Not connected", real webhook URLs, `verify_token_configured:true`, `oauth.ready:false` |
| 5 | `/dashboard/[tenantId]/products` | **REAL** | `GET /tenants/{id}/products` (list+create) | 200: 3 products w/ attributes `{"stock":5,…}` — stock badges real |
| 6 | `/dashboard/[tenantId]/orders` | **REAL** | `GET /tenants/{id}/orders?page=`, `PATCH …/orders/{id}/status` | 200: `{"orders":[],"total":0}` → "Your first order awaits" EmptyState, no crash |
| 7 | `/dashboard/[tenantId]/customers` | **REAL** | `GET /tenants/{id}/customers` | 200: 1 customer with `orders_count/conversations_count/total_spent` |
| 8 | `/dashboard/[tenantId]/conversations` | **REAL** | `GET /tenants/{id}/conversations` (list), `GET …/conversations/{id}` (detail) | 200 both. ⚠ "Last message" column always "—" (F2) |
| 9 | `/dashboard/[tenantId]/crawl` | **REAL** | `GET /tenants/{id}/crawl/jobs`, `POST /tenants/{id}/crawl` | 200: `[]` → EmptyState, no crash |
| 10 | `/dashboard/[tenantId]/scheduler` | **REAL** | `GET/POST /tenants/{id}/schedule/post(s)`, `PATCH/DELETE …/schedule/posts/{id}`, `GET /tenants/{id}/calendar/url` (rotate: `POST …/calendar/token`) | 200: `{"posts":[],"total":0}` → "Nothing scheduled yet"; calendar token real |
| 11 | `/dashboard/[tenantId]/insights` | **REAL** | `GET /tenants/{id}/insights/overview?days=30` | 200: `{"facebook":null,"instagram":null,"period_days":30}` → no-sources EmptyState. ⚠ CTA misdirects to Settings (F5) |
| 12 | `/dashboard/[tenantId]/settings` | **PARTIAL** | Business+delivery: **REAL** (`GET/PATCH /tenants/{id}` — fields round-trip, live 200). "Channels & Integrations" section: **MOCK** — hardcoded "coming soon / not configurable from here yet" card (F5) | 200; PATCH path verified by code + tenant fields in response |
| 13 | `/dashboard/[tenantId]/style` | **MOCK** | **None** — hardcoded "Coming soon / Style learning isn't active yet" stub. Backend `GET /tenants/{id}/style-profile` returns **200 built profile** (F1) | `style-profile` → `{"status":"built","built_at":"…00:56:25","profile":{"tone":"friendly","formality_level":4.0,"greeting_patterns":["أهلاً بيكم","أهلا"],…}}` |
| — | `dashboard/[tenantId]/layout.tsx`, `mobile-sidebar.tsx`, `components/site/dash.tsx` | **N/A** (static shell/nav; no data fetching) | — | — |

### Admin (`src/app/admin/**`) — 8 pages + 1 layout (all wired in Task 19; re-verified, not re-reported)

| # | Route | Classification | Data source | Live check |
|---|---|---|---|---|
| 1 | `/admin` | **REAL** | `GET /admin/analytics/overview` + `GET /admin/audit-log` | 200 w/ superadmin cookie; 307→/login without cookie |
| 2 | `/admin/users` | **REAL** | audit-log (200 rows) + active-sessions + `GET /admin/analytics/user/{id}/activity`; block/unblock `POST/DELETE /admin/users/{id}/block` | fetches verified in source |
| 3 | `/admin/tenants` | **REAL** | `GET /tenants` + per-tenant `GET /tenants/{id}/stats` + overview | verified |
| 4 | `/admin/ip-bans` | **REAL** | `GET/POST /admin/ip-bans`, `DELETE /admin/ip-bans/{id}` | verified |
| 5 | `/admin/sessions` | **REAL** | `GET /admin/analytics/active-sessions` (rows legitimately empty — no backend writes; honest) | verified |
| 6 | `/admin/audit-log` | **REAL** | `GET /admin/audit-log?page=&page_size=` | verified |
| 7 | `/admin/analytics` | **REAL** | `geo-distribution`, `overview`, per-tenant stats; behavior tab renders "—" (no endpoint — honest) | verified |
| 8 | `/admin/health` | **REAL** | live probe `api.getFresh("/admin/analytics/overview")` (FastAPI+DB), others "—" (no probe endpoints) | verified |
| 9 | `admin/layout.tsx` | **REAL gate** | `GET /auth/me` → `is_superadmin`, fallback probe `GET /admin/analytics/overview` (200/403) | owner (non-superadmin) cookie → gate redirects client-side |

**Totals: 22 page files = 20 REAL · 1 PARTIAL (settings) · 1 MOCK (style).** Dashboard subset: 11 REAL / 1 PARTIAL / 1 MOCK.

---

## 2. Live endpoint matrix (owner JWT, FastAPI :8000 direct)

| Endpoint | Status | Payload reality |
|---|---|---|
| `POST /api/auth/login` | 200 | real JWT |
| `GET /api/auth/me` | 200 | real user, `is_superadmin:false` |
| `GET /api/tenants` | 200 | real tenant (no `ig_user_id`/`wa_phone_number_id` keys — see F3) |
| `GET /api/tenants/{id}` / `/stats` | 200 | real: 3 products, 1 conv, 3294 tokens, 3 llm_calls, empty `top_products`/`recent_orders` |
| `GET …/products` / `orders` / `customers` / `conversations` | 200 | real; orders empty; conversations list has `messages:[]` (F2) |
| `GET …/conversations/{id}` | 200 | real messages (customer+assistant, Arabic) |
| `GET …/crawl/jobs` | 200 | `[]` |
| `GET …/insights/overview?days=30` | 200 | `{"facebook":null,"instagram":null,"period_days":30}` |
| `GET …/channels` | 200 | honest not-connected + real webhook paths |
| `GET …/schedule/posts` | 200 | `{"posts":[],"total":0}` |
| `GET …/calendar/url` | 200 | real token `LHTV2g…` |
| `GET …/style-profile` | **200 built** | real learned profile (unused by any page — F1) |
| `GET /api/address/governorates` | 200 | real 27-governorate table w/ zones+shipping |

BFF proxy (`/api/zemest/*` on :3000, cookie→Bearer): 200 with cookie, **401 without** — status codes pass through unmasked; backend 500 would surface as ErrorState in every page (verified `request()` throws on `!res.ok`). Only the per-field `.catch(()=>null)` spots fail silently (F6).

## 3. Route-level checks (:3000, cookies)

- All 13 dashboard routes + 8 admin routes: **200**, 42–62KB HTML, **no `Application error` / `__next_error__` / error-digest** in any SSR output → no route crashes or error boundaries.
- Unauthenticated: `/dashboard/{id}/orders` → **307 → `/login?redirect=…`**; `/admin` → **307 → `/login?redirect=%2Fadmin`** (middleware guard works).
- Bogus tenantId (`/dashboard/not-a-uuid`) → 200 shell; the page-level fetch 404s client-side into `ErrorState` (no crash) — acceptable.
- Empty-state behavior with the freshly-bootstrapped DB: orders page (0 orders), crawl page (0 jobs), scheduler (0 posts), insights (no sources), overview tiles (empty `recent_orders`/`top_products`) all render their EmptyState components — **no crashes, no fabricated numbers**.

## 4. Findings (severity ordered — NOT fixed, read-only audit)

**F1 — HIGH · /dashboard/[tenantId]/style is a mock stub while real data exists.**
Page hardcodes "Style learning isn't active yet … your agent uses the default Zemest voice." Backend `GET /api/tenants/{id}/style-profile` returns **200 `{"status":"built", "profile":{tone, formality_level:4.0, greeting/signoff patterns…}}`** for this exact tenant (built by the Task-19 silent trainer). Also unused: `POST …/import/chat-history`, `POST …/rebuild-style`. The flagship "self-training" feature is invisible to the user and the copy is factually wrong.
*Fix:* wire the page to `GET /tenants/{id}/style-profile` (+ rebuild button), or state "training happens automatically" with real maturity data.

**F2 — MEDIUM · Conversations list "Last message" column always shows "—".**
Backend `list_conversations` (`app/api/conversations.py:44-56`) builds `ConversationResponse` without messages → `messages:[]` in every list row (live-verified), while the detail endpoint loads them. Frontend `lastMessagePreview()` reads `c.messages` from the LIST → dead data path; column renders "—" even for conversations with 20 messages.
*Fix:* backend: add `last_message` preview field to the list response; or frontend: lazy-fetch detail per expanded row.

**F3 — MEDIUM · Dashboard home IG/WhatsApp channel chips can never turn on.**
`dashboard/page.tsx` seeds `ig_connected`/`wa_connected` from `t.ig_user_id`/`t.wa_phone_number_id`, but `TenantResponse` (backend schema) exposes only `fb_page_id` — the keys never exist in the API (live-verified). Connecting Instagram/WhatsApp via the (real) /channels page stores `instagram_meta`/`whatsapp_meta`, so tenant cards will keep showing "No channels" for IG/WA — contradicting the /channels page's "Connected" state.
*Fix:* derive chips from `GET /tenants/{id}/channels` (already fetched per tenant anyway via stats prefetch pattern), or extend `TenantResponse`.

**F4 — MEDIUM · Chat playground "Owner chat" mode is cosmetic and mislabels the transcript.**
`handleSend` never branches on `ownerMode` — every message POSTs the **customer** `/test/chat` endpoint; the error banner is suppressed in owner mode (`error && !ownerMode`); no owner-chat endpoint exists under `/api/test`. A user toggling "Owner chat" sees themselves answered as a customer, titled "Owner chat (connect FB to enable)".
*Fix:* disable the composer in owner mode (honest), or wire a real owner-chat endpoint (service `app/services/owner_chat.py` exists, webhook-only today).

**F5 — MEDIUM · Stale "coming soon" mock + misdirecting empty states around channels.**
(a) Settings → "CHANNELS & INTEGRATIONS" is a hardcoded mock card ("Facebook, Instagram and WhatsApp connections … not configurable from here yet") although the real connect UI (`/channels`) and live-validating endpoints shipped in Task 18. (b) Insights empty state CTA says "Go to settings" to connect Facebook → lands on that same dead-end mock instead of `/channels`. Navigation copy contradicts product reality.
*Fix:* replace the settings mock with a status row + link to `/dashboard/{id}/channels`; point the insights CTA at `/channels`.

**F6 — LOW/MEDIUM · Silent partial failures render zeros instead of errors.**
(a) `/dashboard` home: per-tenant `tenantsApi.stats()` failure is swallowed (`catch → {...t}` without stats) → the card shows 0 orders / 0 revenue / 0 chats / 0 customers under a "Today · live" label while the backend 500s. (b) Overview page: `tenantsApi.get(tenantId).catch(() => null)` silently drops the tenant name → generic "Overview" header with no signal. (Global list-level errors ARE shown via ErrorState — only these per-field paths are silent.)
*Fix:* track partial-error state and show a "stats unavailable" chip instead of 0s.

**F7 — LOW · Inconsistent money formatting across pages.**
`egp()` helper = `toLocaleString("en-EG", {maximumFractionDigits: 2}) + " EGP"` (overview, orders, products, customers). Dashboard home `MiniStat` revenue = `Number(x).toLocaleString()` (runtime-default locale, no fraction cap) + separate "EGP" unit; settings free-delivery note uses default `toLocaleString()` too. Same value can render `1,234.567 EGP` in one page and `1,234.57 EGP` in another.
*Fix:* use `egp()` everywhere.

**F8 — LOW · Chat telemetry "AI STATUS" heuristic can mislabel.**
"FALLBACK MODE — NO LLM KEY" is derived solely from `tokens_used === 0` on the last message, but the tenant has 3,294 tokens / 3 llm_calls in DB (z-ai internal provider active) — a single fallback reply flips the label incorrectly. (Info-level; behavior is honest per-message.)
*Fix:* derive from `/tenants/{id}/stats` `llm_calls`/provider state, or the response's own fallback flag if exposed.

**F9 — INFO · Admin "honest empty" cells** (`—` for behavior metrics, quotas, session history, service health rows) are backend gaps documented by Task 19 — not re-reported; visually they are indistinguishable from a failed fetch at a glance (suggestion: tooltip "not exposed by API yet").

## 5. Verdict

The dashboard is overwhelmingly real: **20/22 page files fetch live backend data, every data endpoint returns real DB rows for the demo tenant, all empty states render without crashing, and route guards work.** The two stragglers are the **style page (pure mock hiding a working backend feature — F1)** and the **settings integrations mock (F5)**, plus one real dead-data column (F2) and one dead-code field assumption (F3). No page fabricates numbers; zeros only appear from real empty data or the two silent-catch paths (F6).
