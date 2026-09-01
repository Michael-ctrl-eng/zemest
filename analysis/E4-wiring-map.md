# E4 — Frontend→Backend Wiring Map + Mismatch Audit

**Task:** Complete call-chain map of every frontend→backend call, mismatch hunt (path existence, field drift, auth forwarding), orphan reverse-map, live verification.
**Scope:** live dev tree `/home/z/my-project/src/**` (not repos/zemest-platform), FastAPI `repos/zemest/app/` on :8000 (never stopped/restarted). Zero code changes.
**Method:** exhaustive grep of `fetch(`/`fetchWithHeal(`/`axios` (axios: not used anywhere), read of the full data layer + all 9 BFF route files + all 17 backend API router modules + schemas, live cross-check against `/openapi.json` (79 paths / 92 method-routes, E1's inventory), then ~60 curl probes through :3000 BFF and direct :8000 (owner + superadmin cookies; only safe negative/GET probes on mutating routes).
**Prior findings honored (NOT re-reported):** E1 (92-route inventory, address governorate case bug, postiz 500s, rate-limit coverage, dead dashboard_router), E2 (BFF proxy XFF spoof, fetchWithHeal re-POST duplication, demo 429 Retry-After), E3 (register page fake submit, FB OAuth dead end, no refresh flow, logout client-side), E5 (style page mock, conversations list omits messages, dashboard IG/WA dead fields, chat owner-mode endpoint never switches, insights CTA misdirect), Task 18/19 wiring history.

---

## 1. Verdict in one line

**45/45 frontend-called backend routes exist and answer correctly (0 path mismatches, 0 404/500 from pages, 0 field-name drift, auth forwarding correct on every call).** The wiring debt is on the *other* side: **41 backend routes (45% of the surface) have no frontend caller at all**, including three whole feature areas (Egypt address validation, manual order entry, channel OAuth URL builder) and one dead duplicate API client that is an import-away footgun.

- Frontend fetch call sites in src/**: **17** (3 in zemest-api.ts, 7 in BFF routes, 2 in backend-health.ts, 2 in agent-chat-modal.tsx, 2 logout calls, 1 dead in api-client.ts). No axios/XHR/EventSource/WebSocket/React-Query usage.
- Unique call templates: **46** (45 OpenAPI routes + 1 unauthed `GET /` daemon ping).
- Backend inventory: **92 method-routes** (79 paths) — matches E1 exactly.

---

## 2. Full call-chain map — frontend file → BFF path → backend route

All browser calls funnel through the same-origin BFF proxy `src/app/api/zemest/[...path]/route.ts` (`/api/zemest/X` → `http://localhost:8000/api/X`, cookie `zemest_auth` → `Authorization: Bearer`, hop-by-hop + `cookie`/`set-cookie` headers stripped, `Cache-Control: no-store`, fetchWithHeal auto-restart).

### 2.1 Tenants / dashboard

| # | Frontend file (caller) | Helper (src/lib/zemest-api.ts) | Method · path via BFF | Backend route | Match | Live | Auth fwd |
|---|---|---|---|---|---|---|---|
| 1 | dashboard/page.tsx:75, admin/analytics:53, admin/tenants:60, auth-page.tsx:59 (warm) | `tenantsApi.list` | GET `/api/zemest/tenants` | GET `/api/tenants` | ✅ | 200 | ✅ cookie→Bearer |
| 2 | dashboard/[tenantId]/page.tsx:43, settings:63 | `tenantsApi.get` | GET `/api/zemest/tenants/{id}` | GET `/api/tenants/{tenant_id}` | ✅ | 200 | ✅ |
| 3 | dashboard/page.tsx:303 (Create business form) | `tenantsApi.create` | POST `/api/zemest/tenants` | POST `/api/tenants` (TenantCreate) | ✅ | — (body verified: page_name/website_url/business_email/business_phone all in schema) | ✅ |
| 4 | settings/page.tsx:91 (handleSave) | `tenantsApi.update` | PATCH `/api/zemest/tenants/{id}` | PATCH `/api/tenants/{tenant_id}` (TenantUpdate) | ✅ | — (body verified: page_name/website_url/business_phone/business_email/delivery_×2/free_delivery_above; null-clearing supported via exclude_unset — Task 18) | ✅ |
| 5 | dashboard/[tenantId]/page.tsx:44 (+peek), dashboard/page.tsx:80, admin/analytics:68, admin/tenants:64 | `tenantsApi.stats` | GET `/api/zemest/tenants/{id}/stats` | GET `/api/tenants/{tenant_id}/stats` | ✅ | 200 — all 15 keys match `TenantStats` TS interface (verified live) | ✅ |
| 6 | dashboard/page.tsx:191-193 (hover/focus/touch prefetch) | `tenantsApi.prefetchOverview` | GET tenants/{id} + stats | same as #2/#5 | ✅ | cache-warm | ✅ |

### 2.2 Catalog

| # | Frontend file | Helper | Method · path | Backend route | Match | Notes |
|---|---|---|---|---|---|---|
| 7 | products/page.tsx:51 | `productsApi.list` | GET `/api/zemest/tenants/{id}/products` | GET `/api/tenants/{t}/products` | ✅ 200 | envelope {products,total,page,page_size} ✅; page never sends `search`/`page`/`page_size` (backend supports, unused) |
| 8 | products/page.tsx:282 (Add product modal) | `productsApi.create` | POST `/api/zemest/tenants/{id}/products` | POST `/api/tenants/{t}/products` (ProductCreate, extra=allow) | ✅ | body name/price/stock/category/description — extras land in flexible attributes ✅ |

### 2.3 Orders

| # | Frontend file | Helper | Method · path | Backend route | Match | Notes |
|---|---|---|---|---|---|---|
| 9 | orders/page.tsx:48 | `ordersApi.list` | GET `/api/zemest/tenants/{id}/orders?page=N` | GET `/api/tenants/{t}/orders` | ✅ 200 | envelope ✅ (0 orders live → empty array verified) |
| 10 | orders/page.tsx:69 (status dropdown) | `ordersApi.updateStatus` | PATCH `/api/zemest/tenants/{id}/orders/{oid}/status` | PATCH `/api/tenants/{t}/orders/{oid}/status` (OrderStatusUpdate) | ✅ | body `{status}` ✅; bogus-UUID probe → 404 ✅ |
| — | (no page) | `ordersApi.create` | POST orders | POST `/api/tenants/{t}/orders` (ManualOrderCreate) | route exists | **dead lib export — never called** (see F2) |

### 2.4 Customers / conversations

| # | Frontend file | Helper | Method · path | Backend route | Match | Notes |
|---|---|---|---|---|---|---|
| 11 | customers/page.tsx:30 | `customersApi.list` | GET `/api/zemest/tenants/{id}/customers` | GET `/api/tenants/{t}/customers` | ✅ 200 | 10 keys match `Customer` ✅ (page renders orders_count/total_spent/conversations_count ✅) |
| 12 | conversations/page.tsx:37 | `conversationsApi.list` | GET `/api/zemest/tenants/{id}/conversations` | GET `/api/tenants/{t}/conversations` | ✅ 200 | {conversations,total} ✅; `messages:[]` present but never populated in list → "Last message" always "—" (E5-known, cross-ref) |
| 13 | conversations/page.tsx:207 (row expand) | `conversationsApi.get` | GET `/api/zemest/tenants/{id}/conversations/{cid}` | GET `/api/tenants/{t}/conversations/{cid}` | ✅ | messages populated on detail ✅ |
| 14 | chat/page.tsx:47 (playground send) | `chatApi.send` | POST `/api/zemest/test/chat` | POST `/api/test/chat` (TestChatRequest) | ✅ | body {tenant_id, message, customer_name} ✅; response {reply, conversation_id, customer_id, tokens_used} ✅; bogus tenant → 404 ✅. Owner-mode toggle never switches to /test/postiz-chat (E5-known) |

### 2.5 Knowledge / crawl / insights

| # | Frontend file | Helper | Method · path | Backend route | Match | Notes |
|---|---|---|---|---|---|---|
| 15 | crawl/page.tsx:37 | `crawlApi.jobs` | GET `/api/zemest/tenants/{id}/crawl/jobs` | GET `/api/tenants/{t}/crawl/jobs` | ✅ 200 | CrawlJobResponse keys match `CrawlJob` ✅ |
| 16 | crawl/page.tsx:59 (start crawl form) | `crawlApi.start` | POST `/api/zemest/tenants/{id}/crawl` | POST `/api/tenants/{t}/crawl` (CrawlRequest {url,depth}) | ✅ | SSRF guard live: `http://127.0.0.1:9/x` → 400 ✅ |
| 17 | insights/page.tsx:52 | `insightsApi.overview` | GET `/api/zemest/tenants/{id}/insights/overview?days=30` | GET `/api/tenants/{t}/insights/overview` | ✅ 200 | {facebook, instagram, period_days} ✅; page handles null/{} + Graph `insights[].values[].value` defensively ✅ |

### 2.6 Channels (Messenger / Instagram / WhatsApp)

| # | Frontend file | Helper | Method · path | Backend route | Match | Notes |
|---|---|---|---|---|---|---|
| 18 | channels/page.tsx:85 | `channelsApi.status` | GET `/api/zemest/tenants/{id}/channels` | GET `/api/tenants/{t}/channels` | ✅ 200 | {platforms{messenger,instagram,whatsapp}, webhook_urls, verify_token_configured, oauth} ✅ |
| 19 | channels/page.tsx:219 | `channelsApi.connectMessenger` | POST `/api/zemest/tenants/{id}/channels/messenger` | POST (MessengerConnectRequest) | ✅ | {page_access_token, page_id|null} ✅; response {connected, page_id, page_name, followers, webhook_subscribed, webhook_note} ✅ |
| 20 | channels/page.tsx:222 | `channelsApi.connectInstagram` | POST `…/channels/instagram` | POST (InstagramConnectRequest) | ✅ | {ig_user_id, access_token} ✅; response has `username` ✅ |
| 21 | channels/page.tsx:225 | `channelsApi.connectWhatsapp` | POST `…/channels/whatsapp` | POST (WhatsAppConnectRequest) | ✅ | {phone_number_id, access_token} ✅ (waba_id optional, not sent — OK) |
| 22 | channels/page.tsx:242 (Disconnect) | `channelsApi.disconnect` | DELETE `/api/zemest/tenants/{id}/channels/{platform}` | DELETE `/api/tenants/{t}/channels/{platform}` | ✅ | bogus platform → 404 ✅ |
| 23 | channels/page.tsx:257 (Test message) | `channelsApi.test` | POST `…/channels/{platform}/test` | POST (TestMessageRequest {recipient?, text}) | ✅ | body `{text}` ✅; bogus platform → 404 ✅ |

### 2.7 Scheduler + calendar

| # | Frontend file | Helper | Method · path | Backend route | Match | Notes |
|---|---|---|---|---|---|---|
| 24 | scheduler/page.tsx:71 | `schedulerApi.list` | GET `/api/zemest/tenants/{id}/schedule/posts` | GET `/api/tenants/{t}/schedule/posts` | ✅ 200 | {posts,total}; post keys match `ScheduledPostItem` ✅ (note: backend truncates caption to 200 chars + "…") |
| 25 | scheduler/page.tsx:111 (composer) | `schedulerApi.create` | POST `…/schedule/post` | POST (SchedulePostRequest) | ✅ | body {platform, caption, media_type, media_urls, scheduled_at} ✅ (link optional not sent); past date → 422 ✅; ISO-Z→naive-UTC normalization handled server-side ✅ |
| 26 | scheduler/page.tsx:131 (Cancel) | `schedulerApi.cancel` | PATCH `…/schedule/posts/{pid}/status` | PATCH (UpdatePostStatusRequest {status}) | ✅ | body `{status:"cancelled"}` ✅; response {status,post_id,new_status} — frontend types only `{status}` (subset, OK) |
| 27 | scheduler/page.tsx:141 (Delete) | `schedulerApi.remove` | DELETE `…/schedule/posts/{pid}` | DELETE `/api/tenants/{t}/schedule/posts/{post_id}` | ✅ | |
| 28 | scheduler/page.tsx:72 | `calendarApi.url` | GET `…/calendar/url` | GET `/api/tenants/{t}/calendar/url` | ✅ 200 | {calendar_token} ✅ |
| 29 | scheduler/page.tsx:151 (Rotate) | `calendarApi.rotate` | POST `…/calendar/token` | POST `/api/tenants/{t}/calendar/token` | ✅ | |
| 30 | calendar apps (external) → BFF `src/app/api/calendar/[token]/route.ts`:27 | — | GET `/api/calendar/{token}` (BFF) → GET `/api/calendar/{token}/calendar.ics` | ✅ | token-in-path auth (no cookie needed) ✅ — E2 verified rotation invalidation |

### 2.8 Admin (superadmin)

| # | Frontend file | Helper | Method · path | Backend route | Match | Live (superadmin cookie) |
|---|---|---|---|---|---|---|
| 31 | admin/layout.tsx:48 (gate fallback), admin/page.tsx:57, admin/analytics:54, admin/tenants:61 | `adminApi.overview` | GET `/api/zemest/admin/analytics/overview` | GET `/api/admin/analytics/overview` | ✅ | 200; 7 keys match `AdminOverview` ✅; owner → 403 ✅ |
| 32 | admin/page.tsx:58, admin/audit-log:65, admin/users:98 | `adminApi.auditLog` | GET `/api/zemest/admin/audit-log?page=&page_size=` | GET `/api/admin/audit-log` | ✅ | 200; {logs,total,page,page_size} ✅ (action filter param exists, unused by audit page's dropdown — page filters client-side) |
| 33 | admin/ip-bans:45 | `adminApi.ipBans` | GET `/api/zemest/admin/ip-bans` | GET `/api/admin/ip-bans` | ✅ | 200; [{id, ip_or_cidr, reason, created_at}] ✅ |
| 34 | admin/ip-bans:62 (add form) | `adminApi.addIpBan` | POST `/api/zemest/admin/ip-bans` | POST (IPBanCreate {ip_or_cidr, reason}) | ✅ | bogus-UUID delete → 404 ✅ (Task 19 live-verified 201/422/400 paths) |
| 35 | admin/ip-bans:79 (trash) | `adminApi.removeIpBan` | DELETE `/api/zemest/admin/ip-bans/{id}` | DELETE `/api/admin/ip-bans/{ban_id}` | ✅ | |
| 36 | admin/sessions:56, admin/users:99 | `adminApi.activeSessions` | GET `/api/zemest/admin/analytics/active-sessions` | GET | ✅ | 200 [] (no session writes — Task 19 known) |
| 37 | admin/users:103 (per-user enrichment) | `adminApi.userActivity` | GET `…/admin/analytics/user/{id}/activity` | GET | ✅ | 200 with real admin UUID ✅ |
| 38 | admin/analytics:52 | `adminApi.geoDistribution` | GET `…/admin/analytics/geo-distribution` | GET | ✅ | 200 [] ✅ |
| 39 | admin/users:123 (Block) | `adminApi.blockUser` | POST `/api/zemest/admin/users/{id}/block` | POST (BlockUserRequest {reason}) | ✅ | bogus UUID → 404 "User not found" (no write) ✅ |
| 40 | admin/users:121 (Unblock) | `adminApi.unblockUser` | DELETE `/api/zemest/admin/users/{id}/block` | DELETE | ✅ | Task 19 live-verified |
| 41 | admin/health:53 (System Health probe) | `adminApi.overviewProbe` (getFresh, uncached) | GET `/api/zemest/admin/analytics/overview` | same as #31 | ✅ | 200 + real latency display |
| 42 | admin/layout.tsx:43 (superadmin gate) | `authApi.me` | GET `/api/zemest/auth/me` | GET `/api/auth/me` | ✅ 200 | {id,name,email,fb_user_id,is_superadmin} ✅ (is_superadmin passthrough live post Task 19) |

### 2.9 Auth + public demo (dedicated BFF routes, not the proxy)

| # | Frontend file | BFF route (src/app/api/…) | Backend route | Match | Notes |
|---|---|---|---|---|---|
| 43 | auth-page.tsx:55 (login+get-started) | POST `/api/auth/login` (route.ts:13) | POST `/api/auth/login` (LoginRequest) | ✅ | forwards {email,password} (drops `remember` — backend doesn't want it ✅); sets httpOnly zemest_auth (24h/30d). **Backend returns only {access_token, token_type} → the `refresh_token` cookie branch (route.ts:37) is dead code (F5)** |
| 44 | auth-page.tsx:53 (get-started signup) | POST `/api/auth/register` (route.ts:13) | POST `/api/auth/register` (RegisterRequest) | ✅ | auto-login cookie ✅. register/page.tsx is a fake submit (E3-known — no API call) |
| 45 | auth-page.tsx:247 / register page FB buttons → `window.location.href="/api/auth/facebook"` | GET+POST `/api/auth/facebook` (route.ts:24,58) | POST `/api/auth/facebook` (FacebookLoginRequest) | ✅ route exists | GET leg redirects to FB dialog with `demo_client_id` v18.0, no state, callback 404 — E3/R1-known dead end |
| 46 | agent-chat-modal.tsx:93 (welcome on open) | POST `/api/demo/welcome` (route.ts:15) | POST `/api/demo/welcome` (WelcomeRequest) | ✅ | {session_id, tz} ✅; public (no auth) ✅; XFF/X-Real-IP forwarded for slowapi keying (E2/E3 XFF-spoof known) |
| 47 | agent-chat-modal.tsx:146 (send) | POST `/api/demo/chat` (route.ts:20) | POST `/api/demo/chat` (DemoChatRequest) | ✅ | {session_id, message, tz} ✅; response {reply, image, quick_replies, order_done, is_arabic} ✅ (page uses reply/image/quick_replies) |
| — | dashboard/[tenantId]/layout.tsx:56 + stores/auth-store.ts:29 (logout) | POST `/api/auth/logout` | **no backend call** (cookie clear only) | n/a | E3-known (no token revocation; JWT valid ≤24h) |
| — | lib/backend-health.ts:26 (server-only daemon ping) | `GET http://localhost:8000/` | GET `/` | ✅ 200 | unauthed root ping — correct (public) |

### 2.10 Pages with NO backend calls (complete list)

- **style/page.tsx** — mock stub, zero fetches (E5-known HIGH: GET /tenants/{id}/style-profile returns a real BUILT profile, unwired)
- **register/page.tsx** — fake submit → /dashboard (E3-known)
- **settings/page.tsx channels card** — "coming soon" stub (E5-known)
- All marketing/legal pages, /status, /models, /research — static, correctly so
- `src/app/api/route.ts` (GET /api) — static "Hello, world!" placeholder (F6, INFO)

### 2.11 Dead code in the data layer (frontend-side orphans)

- **`src/lib/api-client.ts` — ENTIRE MODULE dead** (F1): 18 helpers, zero imports anywhere in src/**. Calls `http://localhost:8000` DIRECTLY with `credentials:"include"` (cross-origin; backend has no CORS and is Bearer-only → every call would fail if ever imported). Exports same names as zemest-api.ts (authApi/tenantsApi/productsApi/ordersApi/addressApi/chatApi/adminApi) — a wrong-module import compiles cleanly and silently bypasses the BFF/cookie pattern.
- `addressApi` (governorates + shipping) in zemest-api.ts:372 — never called by any page (F2)
- `ordersApi.create` (zemest-api.ts:334) — never called by any page (F2)
- `Tenant.owner_psid` interface field (zemest-api.ts:167) — never in backend response, never read by pages (dead field, INFO)

---

## 3. Reverse map — backend routes with NO frontend caller

**92 method-routes total (E1). 45 called by the frontend (map above). 47 uncalled → 6 are webhook endpoints (external Meta callbacks — by design, not orphans) → 41 true orphans (45% of backend surface).**

| Family | Orphan routes (method · path) | Count | Classification |
|---|---|---|---|
| Webhooks (by design) | GET+POST `/api/webhook/{messenger,instagram,whatsapp}` | 6 | external Meta only — NOT dead |
| Postiz integration | GET health/can-register/integrations/best-time/posts/posts/{id}/stats; POST login/connect/{provider}/posts/generate; DELETE posts/{group_id}; PUT posts/{post_id}/reschedule (all under `/api/tenants/{t}/postiz/*`) | 12 | unwired feature (needs Postiz sidecar; 3 GETs 500 when down — E1-known) |
| Egypt address | GET `/api/address/{governorates,cities,areas,shipping,validate}` | 5 | **whole domain backend-only** (F2; governorates/shipping have dead lib helpers) |
| Manual orders | POST `/api/tenants/{t}/orders` (ManualOrderCreate); GET orders/{oid}; PATCH notes; POST retry-api; PATCH payment | 5 | **no manual order UI exists** (F2) |
| Product detail/import | GET/PATCH/DELETE `/api/tenants/{t}/products/{pid}`; POST upload-csv; POST import-url | 5 | list+create only in UI (no edit/delete/CSV/URL import) |
| Facebook legacy | GET `/api/facebook/pages`; POST `/api/facebook/connect`; POST `/api/facebook/{t}/sync-catalog` | 3 | superseded by channels.py family; unwired |
| Style learning | POST import/chat-history; GET style-profile; POST rebuild-style | 3 | consumer page is a mock (E5-known HIGH; cross-ref) |
| Insights extras | GET `/api/tenants/{t}/insights/best-time`; GET insights/post/{pid} | 2 | no UI (best-time heatmap, per-post metrics) |
| Scheduler extras | POST `/api/tenants/{t}/schedule/generate-caption` | 1 | AI caption generator never invoked from scheduler composer |
| Customers | PATCH `/api/tenants/{t}/customers/{cid}` | 1 | no customer edit UI |
| Crawl | GET `/api/tenants/{t}/crawl/jobs/{job_id}` | 1 | list-only UI (job detail unused) |
| Channels | GET `/api/tenants/{t}/channels/oauth-url` | 1 | **the real v21.0 OAuth consent URL builder is unwired** (F3) |
| Test | POST `/api/test/postiz-chat` | 1 | owner-mode chat never switches endpoint (E5-known) |

Live existence probes through the BFF (owner cookie): style-profile 200 (returns BUILT), insights/best-time 400 ("Instagram not connected"), channels/oauth-url 200 ({ready:false…}), postiz/health 200, test/postiz-chat 200, schedule/generate-caption 200, facebook/pages 200 (with fb_access_token param) — all exist and are healthy; they simply have no UI caller. (Earlier 404 on facebook/pages was my probe using a wrong `/tenants/{id}/facebook/pages` prefix — corrected, no product issue.)

---

## 4. Field-name drift check (frontend bodies vs Pydantic, responses vs TS interfaces)

**Result: ZERO drift found** — full check, all 45 called routes:
- Request bodies: test/chat `{tenant_id, message, customer_name}` ✅; crawl `{url, depth}` ✅; channels messenger `{page_access_token, page_id}` / instagram `{ig_user_id, access_token}` / whatsapp `{phone_number_id, access_token}` / test `{text}` ✅; schedule/post `{platform, caption, media_type, media_urls, link?, scheduled_at}` ✅; orders/status `{status}` ✅; tenants create/update (TenantCreate/TenantUpdate field-for-field; delivery Decimals sent as JS numbers — Pydantic coerces ✅); products create (name/price + extra="allow" attributes ✅); admin block `{reason}` / ip-ban `{ip_or_cidr, reason}` ✅; auth login/register/facebook ✅; demo welcome/chat `{session_id, tz[, message]}` ✅.
- Response shapes: all 21 called GET endpoints verified live — keys match the TS interfaces exactly (tenants/stats/products/orders/customers/conversations/crawl-jobs/channels/schedule-posts/calendar-url/insights/auth-me + 6 admin). E2's earlier partial "zero drift" result now confirmed COMPLETE.
- Superset/subset notes (not drift): backend returns extra fields the frontend ignores (Order.area/notes/api_*, Tenant.notification_pref/payment_methods — harmless); frontend types a few optional fields the backend can't return in that endpoint (`ChannelStatus.ig_user_id` etc. appear only in per-platform status; dashboard/page.tsx reads `ig_user_id`/`wa_phone_number_id` off the *tenants list* which never returns them → E5-known MED, cross-ref).

## 5. Auth token forwarding per call (complete audit)

| Call path | Forwarding | Verdict |
|---|---|---|
| `/api/zemest/*` (all 30 client-side data helpers) | proxy reads `zemest_auth` cookie → `Authorization: Bearer`, strips `cookie` + hop-by-hop + `set-cookie` on the way back | ✅ correct; live: no-cookie → 401, owner→admin route → 403, superadmin → 200 |
| BFF login/register/facebook | no forwarding (they *receive* credentials; set httpOnly cookie via authCookieAttributes — SameSite Lax HTTP / None+Secure+Partitioned HTTPS) | ✅ |
| BFF demo welcome/chat | public; forwards XFF/X-Real-IP for slowapi per-visitor limiting | ✅ (XFF spoof = E2/E3 known, not re-reported) |
| BFF calendar/{token} | token-in-path auth, no cookie needed | ✅ |
| backend-health ping `GET /` | unauthenticated root ping | ✅ correct |
| 401 client handling | zemest-api `request()` redirects to `/login?redirect=…`; middleware gates /dashboard+/admin on cookie presence; admin/layout does the real /auth/me + overview-probe superadmin gate | ✅ (middleware /admin superadmin check is a cookie-presence stub — E10-known) |
| Legacy api-client.ts (dead) | `credentials:"include"` direct to :8000, no Bearer — would 401/CORS-fail if ever imported | ⚠ dead-code trap (F1) |

## 6. Live verification summary (~60 probes, zero backend restarts, no mutations except one harmless generate-caption existence call + negative probes that 404/422/400 before any DB write)

- Owner sweep: 14/14 frontend-called GETs → **200** through the BFF.
- Superadmin sweep: 5/5 admin GETs → **200**; RBAC negatives: owner → 403, no-cookie → 401 ✅.
- Negative mutation probes (existence + validation): test/chat bogus tenant → 404; PATCH orders/{bogus}/status → 404; POST admin/users/{bogus}/block → 404; DELETE admin/ip-bans/{bogus} → 404; POST channels/bogus/test → 404; POST schedule/post past date → 422; POST crawl private IP → 400 (SSRF guard) — every wired mutation reaches the real backend validation ✅.
- Login body: backend returns exactly `{access_token, token_type}` (no refresh_token) — see F5.
- Demo widget through BFF: POST /api/demo/welcome → 200 real reply ✅.

## 7. Findings (NEW — none implemented; suggestions only)

| ID | Severity | Where | Issue | Suggested fix |
|---|---|---|---|---|
| **F1** | **MEDIUM** | `src/lib/api-client.ts` (whole module) | Dead duplicate API client (18 helpers, 0 imports) that calls `:8000` DIRECTLY with `credentials:"include"` — cross-origin, backend has no CORS and is Bearer-only → any future import produces silent total failure (plus its own 401→`window.location.href="/login"` redirect). Exports the SAME names as zemest-api.ts (`tenantsApi`, `ordersApi`, `addressApi`, `chatApi`, `adminApi`, `authApi`) — `import {tenantsApi} from "@/lib/api-client"` compiles cleanly and bypasses the BFF/cookie wiring. | Delete the file (git history keeps it), or gut it to `export {} from "./zemest-api"` re-exports. Add a lint rule/no-restricted-imports guard. |
| **F2** | **MEDIUM** (LOW by orphan rubric; MEDIUM by product impact) | lib exports `addressApi` (zemest-api.ts:372) + `ordersApi.create` (:334); backend: 5× `/api/address/*`, 5× order extras (POST create, GET/{id}, PATCH notes, POST retry-api, PATCH payment) | Two whole merchant flows are backend-only with dead lib helpers: (a) Egypt address validation/shipping/checkout; (b) manual order entry + payment recording + notes + retry-API. The ONLY order-creation path is the AI agent (webhook / test-chat). Merchants cannot create/edit an order or correct a phone/address by hand. | Wire a manual "New order" form (orders page) using the existing `ordersApi.create` (ManualOrderCreate); build the checkout/address UI on `addressApi.governorates/shipping` (fix E1's case bug first); optionally surface PATCH notes/payment + retry-api on the order row. |
| **F3** | **MEDIUM** | backend `app/api/channels.py:404` GET `/api/tenants/{t}/channels/oauth-url`; channels/page.tsx | The REAL channel-connection OAuth URL builder (v21.0 dialog, 8 page scopes, works when FB_APP_ID is set) is never called by any page. The channels page only offers manual token paste; the only OAuth-looking UI is the BFF `/api/auth/facebook` GET which redirects to a dead `demo_client_id` v18 dialog with no callback (E3/R1 known). The one working server-side OAuth entry point is orphaned. | Add a "Connect with Facebook" button on the channels page → GET `/api/zemest/tenants/{id}/channels/oauth-url` → redirect to `data.url` when `ready:true`, keep the manual form as fallback; implement the callback route (R1's arctic plan). |
| **F4** | **LOW** | 41 backend routes (§3 table) | 45% of the backend surface has no frontend caller: 12 postiz, 5 address, 5 product-detail/import, 5 order extras, 3 facebook-legacy, 3 style (page is mock — E5), 2 insights (best-time heatmap, per-post metrics), generate-caption, customers PATCH, crawl job detail, channels oauth-url, test/postiz-chat. Several are finished AI features (generate-caption, best-time, style-profile/rebuild) with zero UI. | Triage: wire style page to style-profile (E5's fix), scheduler composer to generate-caption, insights to best-time; decide postiz vs native scheduler overlap; delete or quarantine facebook-legacy trio (superseded by channels). |
| **F5** | **INFO** (cross-ref E3 #5) | BFF login/register/facebook route.ts (`if (refresh_token)`) | Backend `TokenResponse` = `{access_token, token_type}` only (verified live) — the refresh-token cookie branch in all 3 BFF auth routes is dead code; `zemest_refresh` is never set. Confirms at the wire level that no refresh flow exists (30d "remember me" cookie outlives the 24h JWT → silent logouts). | Remove the dead branch, or implement refresh on the backend and then set the cookie for real. |
| **F6** | **INFO** | `src/app/api/route.ts` | `GET /api` returns a static "Hello, world!" — a scaffold placeholder from the template; no backend probe, harmless. | Delete or redirect to `/api/zemest/` health. |

**Counts: 45 frontend→backend call templates audited · 45 matched / 0 mismatched / 0 field-drift · 41 orphaned backend routes (+6 webhook-by-design) · 6 new findings (0 CRITICAL, 0 HIGH, 3 MEDIUM, 1 LOW, 2 INFO).**

**Positive confirmations (no action):** every called route exists and is healthy live; response/request shapes are exact; auth forwarding (cookie→Bearer) is correct on all 30 proxied helpers with correct 401/403/RBAC behavior; admin superadmin gate + probe fallback works both pre/post /me fix; calendar token flow + ICS BFF route correct; demo widget public + rate-limit-forwarded; negative probes prove mutations reach real backend validation.
