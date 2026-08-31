# Task 18-a — API Wiring Audit: Frontend ⇄ Backend

**Scope:** research-only audit of every frontend→backend data path in the unified repo
(`/home/z/my-project` — Next.js App Router frontend + BFF; FastAPI backend at
`repos/zemest/app/` launched by `repos/zemest/daemon_backend.py` on `localhost:8000`).
Backend route inventory verified live against `GET /openapi.json` (daemon running,
79 paths / 92 operations). Frontend E2E verified with curl against the live Next.js
dev server on `:3000` (login → cookie → BFF proxy → backend), plus code reading of
every `src/app/api/**` route, `src/lib/**`, all dashboard/admin pages and hooks.

---

## 1. Executive verdict

**≈ 40 % of the backend's frontend-addressable API surface is actually wired (30 of 76
paths). The wired 40 % — the entire merchant dashboard + demo widget + core auth — is
genuinely REAL, verified end-to-end (cookie→Bearer proxy works, response schemas match).
The platform's *center of gravity* is honest; its *long tail* is not: the whole /admin
section (8 pages) is 100 % hardcoded mock despite 10 real `/api/admin/*` endpoints
existing and enforcing superadmin (403 verified), the Style-Learning feature is a
"coming soon" placeholder while its 3 backend endpoints are fully built, the entire
Postiz integration (11 endpoints) and Facebook OAuth loop are dead, and 45 of 76
frontend-addressable backend paths have zero frontend callers.**

Breakdown (76 frontend-addressable paths = 79 total − 3 Meta webhook paths, which are
correctly external-only):

| Category | Paths | % of 76 |
|---|---|---|
| REAL (wired, live-verified) | 30 | 39.5 % |
| PARTIAL/BROKEN (auth/facebook: BFF exists, OAuth loop 404s) | 1 | 1.3 % |
| UNUSED (no frontend caller at all) | 45 | 59.2 % |

Page-level view (26 user-facing data surfaces): 17 REAL (all 11 dashboard tenant pages +
dashboard index, demo chat/welcome widget, login, register, calendar .ics feed),
1 BROKEN (Facebook OAuth login), 8 MOCK (all /admin pages) + 2 placeholders
(style page "coming soon", forgot-password fake form) → **~63 % of screens show real
data, 100 % of the merchant product loop is real, 0 % of the admin section is real.**

Architecture quality note: the wiring that *does* exist is unusually clean — one
universal BFF proxy (`/api/zemest/[...path]`) doing cookie→Bearer translation,
`fetchWithHeal` self-healing with single-flight daemon restart, httpOnly cookies with
CHIPS/iframe-aware attributes, no tokens in localStorage, no CORS anywhere. The
problems are *missing* wiring (endpoints built but never called) and *dead* wiring
(refresh_token, auth/me, useAuthStore, api-client.ts), not broken plumbing.

---

## 2. BFF route inventory — every route → backend endpoint → status

BFF = `src/app/api/**` (9 route files in the live app at `/home/z/my-project`;
`repos/zemest-platform/src/app/api/**` is a **stale duplicate copy** of the frontend —
it lacks the `/api/zemest/[...path]` catch-all and calendar route and should not be
treated as the source of truth).

| # | BFF route (file) | Method(s) | Backend endpoint called | Status | Evidence |
|---|---|---|---|---|---|
| 1 | `/api/zemest/[...path]` (`src/app/api/zemest/[...path]/route.ts`) | GET/POST/PATCH/PUT/DELETE | `${BACKEND_URL}/api/*` (all 76 addressable paths pass through here) | **REAL** | Universal proxy; reads `zemest_auth` cookie → `Authorization: Bearer` (lines 44–49); strips hop-by-hop headers; `no-store`. Live-verified: `/api/zemest/auth/me` → 200, `/api/zemest/tenants` → 200, no-cookie → 401. Used by `src/lib/zemest-api.ts` for every dashboard call. |
| 2 | `/api/auth/login` (`src/app/api/auth/login/route.ts`) | POST | `POST /api/auth/login` | **REAL** | `fetchWithHeal` (line 13); sets `zemest_auth` httpOnly cookie (+ `zemest_refresh` — never set, see §3.1). Live-verified: register→login→cookie→proxy round trip 200. |
| 3 | `/api/auth/register` (`src/app/api/auth/register/route.ts`) | POST | `POST /api/auth/register` | **REAL** | Same pattern (line 13); auto-login cookie; verified live (test user created, token returned). |
| 4 | `/api/auth/facebook` (`src/app/api/auth/facebook/route.ts`) | POST, GET | `POST /api/auth/facebook` (POST branch only) | **BROKEN (OAuth loop)** | POST branch proxies correctly (line 24) but has **zero frontend callers**; GET branch (line 58–63) redirects to FB dialog with `redirect_uri=/api/auth/facebook/callback` — **that route does not exist** (curl → 404), and `NEXT_PUBLIC_FB_APP_ID` is unset → falls back to `client_id=demo_client_id`. The login page's Facebook button (`auth-page.tsx:247` → `window.location.href="/api/auth/facebook"`) always dead-ends in a 404 after consent. |
| 5 | `/api/auth/logout` (`src/app/api/auth/logout/route.ts`) | POST | — (none) | **PARTIAL** | Cookie-clear only; backend has **no logout/revocation endpoint** — JWT stays valid until exp. Acceptable BFF pattern, but no server-side session kill. |
| 6 | `/api/demo/chat` (`src/app/api/demo/chat/route.ts`) | POST | `POST /api/demo/chat` | **REAL** | Forwards `X-Forwarded-For`/`X-Real-IP` for per-IP slowapi limits; 15 s timeout; catch returns 502 with canned reply (failure visible as 502 — good). Live-verified reply from rule matcher. |
| 7 | `/api/demo/welcome` (`src/app/api/demo/welcome/route.ts`) | POST | `POST /api/demo/welcome` | **REAL (with masking fallback)** | Proxies correctly; **catch returns HTTP 200 with a hardcoded welcome message** (lines 32–40) — masks backend outages for the marketing widget (intentional, but hides failures). |
| 8 | `/api/calendar/[token]` (`src/app/api/calendar/[token]/route.ts`) | GET | `GET /api/calendar/{token}/calendar.ics` | **REAL** | Token-format validated, `fetchWithHeal`, correct `text/calendar` headers. Live-verified 200 for real tenant token; 404 for invalid. Called by scheduler page (`webcal://…/api/calendar/{t}`) and external calendar apps. |
| 9 | `/api/route.ts` (root) | GET | — | **MOCK/STUB** | Returns `{"message":"Hello, world!"}` — leftover scaffold, no backend call, no callers. Dead code. |

**Client-side data layer (`src/lib/zemest-api.ts`)** — the only fetch layer actually used:
all calls go through `/api/zemest/*` (line 76) with `credentials: same-origin`; 401 →
redirect to `/login?redirect=…` (lines 94–99); stale-while-revalidate cache
(sessionStorage, `api.peek`) + in-flight dedupe; mutations invalidate cache. Domain
helpers (`tenantsApi`, `productsApi`, `ordersApi`, `customersApi`, `conversationsApi`,
`crawlApi`, `insightsApi`, `channelsApi`, `schedulerApi`, `calendarApi`, `chatApi`) map
1:1 onto real backend routes — all shapes verified live and matching (see §3 "matches").
`addressApi` and `authApi.me()` are defined but **never called** by any component.

**Dead/duplicate client layers:**
- `src/lib/api-client.ts` — fetches **directly** to `http://localhost:8000` from the
  browser (`credentials: include`, no Bearer header) — would hit CORS + cookie-domain
  problems; **imported by nothing** (grep: zero imports). Dead code with a security smell.
- `src/lib/db.ts` (Prisma) — instantiated, **imported by nothing**; the real DB is the
  backend's SQLAlchemy (SQLite `zemest_local.db` via daemon env override).
- `src/stores/auth-store.ts` (`useAuthStore`) — defined, **never used** by any component.
- `@tanstack/react-query` + `next-auth` in `package.json` — installed, **zero imports**.
- `src/hooks/*` (use-debounce, use-mobile, use-toast) — no fetch logic.

---

## 3. Schema & wiring mismatches (exact file + line)

### Real breaks

1. **`refresh_token` does not exist — dead cookie wiring.**
   `src/app/api/auth/login/route.ts:25,37–42` (also `register/route.ts:25,34–39`,
   `facebook/route.ts:36,44–49`) destructure `refresh_token` from the backend response,
   but backend `TokenResponse` (`repos/zemest/app/schemas/auth.py:27–29`) is only
   `{access_token, token_type}` — **`zemest_refresh` is never set**. There is no
   `/api/auth/refresh` endpoint anywhere and no refresh logic in the frontend.
   Consequence: **"Remember me" is a lie beyond 24 h** — cookie maxAge is 30 d
   (`login/route.ts:30`) but the JWT TTL is 1440 min (`repos/zemest/app/config.py:23`);
   after 24 h the user is silently bounced to /login (401 handler `zemest-api.ts:94–99`).

2. **Facebook OAuth callback route missing → Facebook login button 100 % broken.**
   `src/app/api/auth/facebook/route.ts:18,60` builds `redirect_uri=
   ${origin}/api/auth/facebook/callback`; **no such route exists** (verified: HTTP 404).
   Additionally `NEXT_PUBLIC_FB_APP_ID` unset (only `DATABASE_URL` in `.env`) →
   `client_id=demo_client_id` (line 59). Login page button at
   `src/components/site/auth-page.tsx:247`. Same half-loop on the channel side:
   backend `GET /api/tenants/{id}/channels/oauth-url`
   (`repos/zemest/app/api/channels.py:417`) redirects to
   `/api/zemest/facebook/oauth/callback` — **which exists neither in the Next.js app
   nor in the backend's OpenAPI**. The manual page-token fallback (channels page) is
   the only working connection path.

3. **PATCH-with-null semantics: settings page can never clear a field.**
   `src/app/dashboard/[tenantId]/settings/page.tsx:91–98` sends `website_url: null` /
   `business_phone: null` … to *clear* values, but the backend drops nulls:
   `repos/zemest/app/api/tenants.py:66` uses `req.model_dump(exclude_none=True)`.
   Clearing a field in Settings silently does nothing (no error — the value just
   re-appears on reload).

4. **`/api/auth/me` never called → no identity anywhere; admin gate unenforced in UI.**
   `src/middleware.ts:47–51` comment says the real superadmin check "happens
   client-side via GET /api/auth/me" — **no component ever calls it**
   (`authApi.me` defined at `src/lib/zemest-api.ts:479`, zero call sites). Any
   authenticated user can open every `/admin/*` page (backend would 403 the API calls —
   but the pages never make any, see §4). `useAuthStore` (`src/stores/auth-store.ts`)
   which was built for exactly this is dead code. Also backend `UserResponse`
   (`app/schemas/auth.py:32–38`) does not expose `is_superadmin`/`is_blocked`, so a
   client-side gate isn't even possible without a schema change.

5. **`remember` field sent but unknown to backend.** `login/route.ts:16` sends
   `{email, password, remember}`; backend `LoginRequest` (`app/schemas/auth.py:18–19`)
   has no `remember` (Pydantic ignores extras — harmless today, brittle tomorrow).

### Matches verified live (no action needed)

- `TenantStats` interface (`zemest-api.ts:241–263`) ≡ `GET /tenants/{id}/stats` — all 16 fields identical.
- products/orders/customers list wrappers `{items[], total, page, page_size}` ≡ backend list responses (verified empty-state JSON).
- `ChannelsStatus`/`ChannelStatus` (`zemest-api.ts:374–396`) ≡ `GET /tenants/{id}/channels` (platforms/webhook_urls/verify_token_configured/oauth — verified live, including `oauth.ready:false`).
- `ScheduledPostItem` + create response `{id,status,scheduled_at,platform}` ≡ `scheduling.py:110–115`; `SchedulePostRequest` fields match composer payload (`scheduler/page.tsx:111–117`); tz-aware ISO `scheduled_at` handled by backend normalization (`scheduling.py:79–83`).
- `OrderStatusUpdate {status, notes?}` ≡ `ordersApi.updateStatus` body.
- `ProductCreate` (extra=allow) ≡ add-product modal payload incl. stock/category/description.
- `TestChatRequest {tenant_id, message, customer_name}` ≡ `chatApi.send` body; response `{reply, conversation_id, customer_id, tokens_used}` matches.
- `DemoChatRequest/WelcomeRequest {session_id ≥ 6 chars, tz}` ≡ agent-chat-modal body.
- Timestamps: `formatDateTime` (`zemest-api.ts:279–291`) handles both backend formats.
- Money as string-Decimal handled by `toNumber/egp`.

### Method-level checks
- All frontend verbs match backend decorators (GET list / POST create / PATCH update /
  DELETE remove). No wrong-method calls found.
- Token forwarding: the universal proxy forwards the cookie as Bearer for every
  verb (verified 401 without cookie, 200 with). The dedicated auth routes don't need it.
- The only response-fallback that masks failure: `demo/welcome` returns 200-canned
  reply (route lines 32–40); `demo/chat` fails honestly with 502.

---

## 4. Mock data locations (frontend pages not wired to the backend)

| Location | What is mocked | Real backend alternative that exists |
|---|---|---|
| `src/app/admin/page.tsx:5–24` | `platformStats` (users 1,284 / tenants 37 / orders 18,420 …), `adminActions` feed | `GET /api/admin/analytics/overview`, `GET /api/admin/audit-log` |
| `src/app/admin/analytics/page.tsx:6–34` | `geoDistribution`, `tokenUsage`, `behaviorMetrics` | `GET /api/admin/analytics/geo-distribution`, `overview` |
| `src/app/admin/users/page.tsx:20` | `mockUsers` array; block/unblock buttons cosmetic | `GET/POST/DELETE /api/admin/users/{id}/block`, site_users table |
| `src/app/admin/tenants/page.tsx:20` | `mockTenants` array | tenants table (admin variant needed) |
| `src/app/admin/ip-bans/page.tsx:15` | `mockBans` array; add-ban form does nothing | `GET/POST /api/admin/ip-bans`, `DELETE /api/admin/ip-bans/{id}` |
| `src/app/admin/sessions/page.tsx:17` | `mockSessions` array | `GET /api/admin/analytics/active-sessions`, user_sessions table |
| `src/app/admin/audit-log/page.tsx:17` | `mockLogs` array (+ JSON viewer of mock metadata, line 171) | `GET /api/admin/audit-log?page&action` |
| `src/app/admin/health/page.tsx:17–26,39` | `services` array incl. fake "Gemini Vision: down"; refresh = `setTimeout(…,800)` fake | `GET /` health probe; per-service checks |
| `src/app/admin/layout.tsx:104–106` | "LOGOUT" is a `<Link href="/">` — never logs out | `POST /api/auth/logout` BFF exists |
| `src/app/dashboard/[tenantId]/style/page.tsx:6–27` | Whole page = "Coming soon" EmptyState while **3 real style endpoints idle** | `GET /style-profile`, `POST /import/chat-history`, `POST /rebuild-style` (verified live: `{"status":"not_built",…}`) |
| `src/app/forgot-password/page.tsx:56` | `onSubmit` = `setSubmitted(true)` — fake "check your email" | **No backend endpoint exists** (password reset not implemented at all) |
| `src/components/site/conversational-demo.tsx:10–17` | Marketing hero: scripted `script[]` chat playback on `setInterval` (acceptable marketing demo; the *real* interactive widget is `agent-chat-modal.tsx`) | — |
| `src/app/api/route.ts:3–5` | "Hello, world!" stub | — (delete) |
| `src/app/status/page.tsx:5–16` | "TITLE/EYEBROW/DESCRIPTION" template placeholder ("coming soon") | — (page content, not data) |

Marketing pages (/, pricing, solutions, blog, models, legal…) are static content by
design — not counted as mock-data violations.

---

## 5. Unused backend endpoints (zero frontend callers)

Of 79 OpenAPI paths: 3 webhook paths are external-only (Meta servers — correct).
**45 paths have no frontend caller** (59 % of the 76 addressable ones):

**Admin (8 paths — fully built + superadmin-guarded, verified 403):**
`GET /api/admin/analytics/overview` · `geo-distribution` · `active-sessions` ·
`user/{user_id}/activity` · `GET /api/admin/audit-log` · `GET+POST /api/admin/ip-bans` ·
`DELETE /api/admin/ip-bans/{ban_id}` · `POST+DELETE /api/admin/users/{user_id}/block`

**Postiz integration (11 paths — entire feature unreachable from UI):**
`…/postiz/health`, `login`, `can-register`, `integrations`, `connect/{provider}`,
`POST+GET …/postiz/posts`, `DELETE …/postiz/posts/{group_id}`,
`PUT …/postiz/posts/{post_id}/reschedule`, `GET …/postiz/posts/{post_id}/stats`,
`GET …/postiz/best-time`, `POST …/postiz/generate`

**Style learning (3):** `POST …/import/chat-history`, `GET …/style-profile`,
`POST …/rebuild-style`  ← the silent-trainer pipeline feeds these; the profile is
even injected into live replies (per 18-b worklog) yet the page says "coming soon".

**Product management (3):** `POST …/products/upload-csv`, `POST …/products/import-url`,
`GET+PATCH+DELETE …/products/{product_id}` (no edit/activate/delete UI)

**Order management (4):** `GET …/orders/{order_id}`, `PATCH …/orders/{order_id}/notes`,
`PATCH …/orders/{order_id}/payment`, `POST …/orders/{order_id}/retry-api`
(also `POST /orders` is backend-internal only — the AI agent creates orders; the
frontend `ordersApi.create` helper is defined-but-unused)

**Customer detail (2):** `GET/PATCH …/customers/{customer_id}`

**Facebook (3):** `GET /api/facebook/pages`, `POST /api/facebook/connect`,
`POST /api/facebook/{tenant_id}/sync-catalog` (channels page uses the
`/channels/messenger` route instead; catalog sync never triggered)

**Insights/Scheduler extras (3):** `GET …/insights/best-time`,
`GET …/insights/post/{post_id}`, `POST …/schedule/generate-caption`
(AI caption generator is built, tested, and idle)

**Address (5):** `governorates`, `cities`, `areas`, `shipping`, `validate` —
`addressApi` helpers exist in `zemest-api.ts:366–370` but **no component calls them**
(Egypt checkout auto-complete & shipping-quote data never surfaced)

**Misc (3):** `GET /api/auth/me` (defined in lib, never invoked),
`POST /api/test/postiz-chat` (only referenced by dead `api-client.ts:117`),
`GET …/channels/oauth-url` (its callback target doesn't exist on either side)

---

## 6. Top 10 highest-impact wiring fixes (ranked, backend/API only — no UI/design changes)

1. **Fix the Facebook login OAuth loop (currently a guaranteed 404).**
   Add `src/app/api/auth/facebook/callback/route.ts` (exchange `?code` → Graph token →
   `POST ${BACKEND}/api/auth/facebook` with `fb_access_token` → set `zemest_auth`
   cookie exactly like `login/route.ts:32–35`); set `NEXT_PUBLIC_FB_APP_ID` in env and
   remove the `|| "demo_client_id"` fallback (`auth/facebook/route.ts:59`). Until then
   the Facebook button on the login page is a dead end.

2. **Wire the 8 admin pages to the 10 real `/api/admin/*` endpoints.**
   The BFF proxy already forwards auth — pages just need to call
   `/api/zemest/admin/…` (replace `mockTenants/users/bans/sessions/logs/platformStats`
   in the files listed in §4). Requires superadmin gate first (fix #3). This is the
   single largest real-data gap: an entire protected section displays fiction while
   real, superadmin-enforced data sits one fetch away.

3. **Enforce the superadmin gate and surface identity: call `GET /api/auth/me`.**
   Backend: add `is_superadmin`/`is_blocked` to `UserResponse`
   (`repos/zemest/app/schemas/auth.py:32–38`). Frontend: invoke the already-written
   `authApi.me()` (`src/lib/zemest-api.ts:479`) in the dashboard/admin layouts (or
   wire the dead `useAuthStore`), making the comment at `src/middleware.ts:49–51`
   true instead of aspirational. Today any logged-in user can browse every admin page.

4. **Make "Remember me" honest: add refresh-token support (or remove the dead branch).**
   Backend: add `refresh_token` to `TokenResponse` + `POST /api/auth/refresh` (and a
   logout/revocation endpoint so `/api/auth/logout` can invalidate server-side).
   Frontend: the BFF already has the `zemest_refresh` cookie branch
   (`login/route.ts:37–42`) — it's currently dead because the field never arrives.
   Alternatively delete the branch and cap `remember` maxAge at 24 h.

5. **Ship the Style-Learning page (backend is 100 % built, page is a placeholder).**
   Wire `GET /tenants/{id}/style-profile`, `POST /import/chat-history`,
   `POST /rebuild-style` through the existing proxy into
   `src/app/dashboard/[tenantId]/style/page.tsx` (replace the "Coming soon"
   EmptyState at lines 13–25). The silent trainer is already building profiles in
   production — the merchant just can't see or trigger it.

6. **Fix PATCH-null semantics so Settings can clear fields.**
   `repos/zemest/app/api/tenants.py:66`: `exclude_none=True` silently drops the
   frontend's explicit `null` clears (`settings/page.tsx:93–98`). Switch to
   `model_dump(exclude_unset=True)` (Pydantic v2) so explicit nulls distinguish
   "clear" from "don't touch".

7. **Wire order-management depth: notes, payment, retry-API, order detail.**
   `PATCH …/orders/{id}/notes`, `PATCH …/orders/{id}/payment`,
   `POST …/orders/{id}/retry-api`, `GET …/orders/{id}` all idle while the orders page
   only PATCHes status. These power COD confirmation and the external order-API
   retry path — operationally the most valuable unused group after admin.

8. **Wire product CSV/import + edit/deactivate.**
   `POST …/products/upload-csv` and `POST …/products/import-url` (bulk onboarding —
   the fastest path to a populated demo tenant) plus `PATCH/DELETE
   …/products/{product_id}` are unused; the products page can only add one-by-one.

9. **Wire AI caption generation + best-time + post performance.**
   `POST …/schedule/generate-caption`, `GET …/insights/best-time`,
   `GET …/insights/post/{post_id}` are built, tested endpoints that would complete
   the scheduler/insights pages' story (scheduler composer currently has no "generate
   caption" action; insights has no per-post stats).

10. **Delete dead/duplicate data layers and close the failure-masking hole.**
    Remove `src/lib/api-client.ts` (browser→8000 direct fetch, CORS/cookie-broken,
    imported by nothing), `src/lib/db.ts` (unused Prisma), `src/app/api/route.ts`
    ("Hello, world!"), unused deps (`@tanstack/react-query`, `next-auth` — or actually
    adopt react-query as 18-c suggested); decide on the stale
    `repos/zemest-platform/` duplicate. Change `/api/demo/welcome`'s 200-canned-reply
    fallback (`welcome/route.ts:32–40`) to log a warning metric so backend outages
    don't look like success.

**Honorable mentions:** surface `addressApi` (governorates/shipping) in checkout-ish
flows; hook the channels page to `GET …/channels/oauth-url` once a callback exists;
use `/api/facebook/{tenant_id}/sync-catalog` after connecting a page; per-customer
detail `GET /customers/{id}`; `webcal://` calendar URL already works — consider
exposing `GET /insights/overview` fans/followers history. Also: `middleware.ts:37`
still checks a Supabase-style `sb-access-token` cookie — leftover.

---

### Verification artifacts
- Backend live: `GET /` → `{"status":"ok"}`; OpenAPI = 79 paths.
- E2E through Next BFF (:3000): register → 200 + `access_token`; BFF login → 200 +
  `zemest_auth` httpOnly cookie; `/api/zemest/auth/me` → user JSON (Bearer forwarding
  works); `/api/zemest/tenants` → tenant list; no-cookie `/api/zemest/tenants` → 401;
  `/api/demo/chat` → real rule-matcher reply; `/api/calendar/{real-token}` → 200;
  `/api/calendar/{bad}` → 404; `/api/auth/facebook` GET → 307 to FB with
  `demo_client_id`; `/api/auth/facebook/callback` → **404**;
  `/api/admin/analytics/overview` as non-superadmin → 403 (real RBAC).
- Direct backend smoke: tenant create/stats/products/orders/customers/conversations/
  channels/schedule/insights/crawl/calendar/style-profile/address — all 200 with
  shapes matching `src/lib/zemest-api.ts` interfaces.

*Task 18-a — research only: zero files modified.*
