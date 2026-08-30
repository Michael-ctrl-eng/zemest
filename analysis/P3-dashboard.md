# P3 — Tenant Dashboard Pages & API Client Deep Analysis

**Scope:** `src/app/dashboard/**` (12 files, ~2,691 LOC) + `src/lib/api-client.ts` (134 LOC) of `zemest-platform` (Next.js 16 App Router, TS, Tailwind, shadcn/ui, Bun).
**Method:** Line-by-line read of every page, every function, every fetch; grep-verified importer graph; backend contract cross-check against `repos/zemest` FastAPI routers/schemas.
**Headline finding:** **The entire tenant dashboard is a pixel-perfect static prototype. Not a single dashboard page imports `api-client.ts`; not one network request is made. The API client itself is 100% dead code AND carries a fatal auth-mechanism mismatch (cookies vs Bearer).**

---

## 1. API Client Deep-Dive — `src/lib/api-client.ts`

### 1.1 Base URL & transport
- `BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"` (line 9). `NEXT_PUBLIC_` prefix ⇒ resolved **in the browser** ⇒ the client calls the FastAPI origin **directly, cross-origin**, bypassing the Next.js BFF (`src/app/api/auth/*` routes) that the login flow actually uses.
- Single generic wrapper `request<T>(path, options)` (lines 21–55):
  - `fetch(BACKEND_URL + path, { ...options, credentials: "include", headers: { "Content-Type": "application/json", ...options.headers } })`.
  - Forces `Content-Type: application/json` on every method, including GET/DELETE (harmless but sloppy).
  - **Auth mechanism: cookies only.** `credentials: "include"` sends `zemest_auth` (an httpOnly cookie scoped to the *Next.js origin*) to the *backend origin*. Cross-origin cookie delivery additionally requires backend CORS `allow_credentials=True` + exact origin allowlist. Even if the cookie arrived, **the backend never reads cookies**: `app/dependencies.py:12–24` uses `HTTPBearer` (`Authorization: Bearer <jwt>`). ⇒ **Every authenticated call from this client would return 401.**
  - **401 handling** (lines 38–43): comment says "try refresh, then redirect" — **there is no refresh call anywhere**. It hard-redirects `window.location.href = "/login"` (client-only, guarded by `typeof window`) and throws `ApiError(401, "Session expired — please log in again")`. The BFF login route (`src/app/api/auth/login/route.ts:23,37–45`) destructures `refresh_token` from a `TokenResponse` that only has `access_token` (`app/schemas/auth.py:27–29`), so the `zemest_refresh` cookie is never set, and the backend exposes **no** `/api/auth/refresh` endpoint at all. The whole refresh story is fictitious.
  - **429 handling** (lines 46–49): reads `Retry-After` header (default "5") into the message text. No automatic retry.
  - Other errors: `res.json().catch(() => ({detail:"Something went wrong"}))` → `throw new ApiError(status, error.detail || "Something went wrong")`. Non-JSON 500 bodies (HTML) degrade gracefully. No timeout/AbortController, no retry/backoff, no CSRF handling, no request cancellation.
- `ApiError extends Error { status, detail }` (lines 11–19) — the only typed artifact; everything else is `any`/`Promise<any>` (comment at lines 4–6 admits openapi-fetch codegen was intended).

### 1.2 Exported functions (complete inventory)

| Export | Function | Method + Path | Body / Params | Backend route exists? | Notes |
|---|---|---|---|---|---|
| `authApi` | `login(email,password)` | POST `/api/auth/login` | `{email,password}` | ✅ `auth.py:28` | Backend returns `TokenResponse{access_token}` — client just returns JSON; token never stored/attached |
| | `register(name,email,password)` | POST `/api/auth/register` | `{name,email,password}` | ✅ `auth.py:18` | |
| | `me()` | GET `/api/auth/me` | — | ✅ `auth.py:46` | |
| `tenantsApi` | `list()` | GET `/api/tenants` | — | ✅ `tenants.py:45` | |
| | `get(id)` | GET `/api/tenants/{id}` | — | ✅ `tenants.py:54` | id must be UUID |
| | `create(data:any)` | POST `/api/tenants` | any | ✅ `tenants.py:33` | |
| | `update(id,data:any)` | PATCH `/api/tenants/{id}` | any | ✅ `tenants.py:59` | |
| | `stats(id)` | GET `/api/tenants/{id}/stats` | — | ✅ `tenants.py:71` | |
| `productsApi` | `list(tenantId,{page,page_size,search})` | GET `/api/tenants/{t}/products` | query: `page`,`page_size`,`search` | ✅ `products.py:35` | ✅ param names match backend Query params |
| | `get(tenantId,productId)` | GET `/api/tenants/{t}/products/{p}` | — | ✅ `products.py:147` | |
| | `create(tenantId,data:any)` | POST `/api/tenants/{t}/products` | any | ✅ `products.py:54` | |
| | `update(t,p,data:any)` | PATCH `.../products/{p}` | any | ✅ `products.py:164` | |
| | `delete(t,p)` | DELETE `.../products/{p}` | — | ✅ `products.py:186` | |
| | ❌ **missing** | POST `.../products/upload-csv` | multipart | ✅ `products.py:83` | Products page has a "CSV" button with no client fn |
| | ❌ **missing** | POST `.../products/import-url` | JSON | ✅ `products.py:102` | Products page has a "URL" button with no client fn |
| `ordersApi` | `list(t,{page,status})` | GET `/api/tenants/{t}/orders` | query: `page`,`status` | ✅ `orders.py:115` | ✅ matches backend Query params |
| | `get(t,orderId)` | GET `.../orders/{o}` | — | ✅ `orders.py:132` | |
| | `create(t,data:any)` | POST `.../orders` | any | ⚠️ `orders.py:46` — **endpoint is broken (500 MissingGreenlet)**, see §5 | |
| | `updateStatus(t,o,status,notes?)` | PATCH `.../orders/{o}/status` | `{status,notes}` | ✅ `orders.py:144`, `OrderStatusUpdate{status,notes?}` (`schemas/order.py:52–55`) | ✅ body shape matches |
| `addressApi` | `governorates()` | GET `/api/address/governorates` | — | ✅ `address.py` | |
| | `cities(governorate)` | GET `/api/address/cities` | `?governorate=` (encoded) | ✅ | |
| | `areas(governorate)` | GET `/api/address/areas` | `?governorate=` | ✅ | |
| | `shipping(governorate,subtotal)` | GET `/api/address/shipping` | `?governorate=&subtotal=` | ✅ | subtotal not encoded (number, fine) |
| `chatApi` | `test(tenantId,message,customerName)` | POST `/api/test/chat` | `{tenant_id,message,customer_name}` | ✅ `test_chat.py:15`; `TestChatRequest{tenant_id,customer_name="Test Customer",message}` (`schemas/webhook.py:6–11`) | ✅ **field-for-field match** — clearly designed for the Chat page, never wired |
| | `ownerChat(tenantId,message)` | POST `/api/test/postiz-chat` | `{tenant_id,message}` | ✅ `test_chat.py:100` | |
| `adminApi` | `stats()` | GET `/api/admin/analytics/overview` | — | ✅ `admin/api.py:279` | |
| | `geoDistribution()` | GET `/api/admin/analytics/geo-distribution` | — | ✅ `admin/api.py:315` | |
| | `activeSessions()` | GET `/api/admin/analytics/active-sessions` | — | ✅ `admin/api.py:420` | |
| | `auditLog({page,action})` | GET `/api/admin/audit-log` | query: `page`,`action` | ✅ `admin/api.py:372` | |
| `apiClient` | raw `request` | any | — | — | exported alias (line 133) |

### 1.3 Verdict on the client
- **Dead code:** `grep` across `src/` for `api-client|chatApi|tenantsApi|ordersApi|productsApi|addressApi|authApi|adminApi|apiClient` matches **only the file itself**. Zero importers.
- **Endpoint coverage gap:** the client covers 7 of ~15 backend router groups. **No** `conversationsApi`, `customersApi`, `crawlApi`, `styleApi` (import/style-profile/rebuild), `schedulingApi` (schedule posts, generate-caption, insights/overview, insights/best-time), `postizApi` — i.e., **6 of the 11 sidebar pages have no data-layer support at all.**
- **Missing shape layer:** all request bodies are `data: any`; response types are `any` (`Promise<any>`); the codegen note (lines 4–6) never happened.
- Rating: **4/10** — sensible structure (grouped namespaces, error class, query-param handling) but wrong auth model for the backend, fictitious refresh, untyped, incomplete coverage, and entirely unused.

---

## 2. Dashboard Shell

### 2.1 `dashboard/page.tsx` (195 lines, client) — tenant selector
- **Purpose:** "Your businesses" — list tenant cards and create a new business.
- **Data:** `mockTenants` hardcoded array (lines 9–40): `tnt_001` "Cairo Sneakers Store", `tnt_002` "Alexandria Fashion Hub" with fb/ig/wa flags, today/month revenue, token quota. **No `tenantsApi.list()` call.**
- **Create business:** `CreateBusinessForm` (lines 161–195) is a toggle-revealed static form: 4 uncontrolled inputs (page name/website/email/phone), the "CREATE BUSINESS" button has **no onClick, no submit handler, no validation** — it renders and does nothing. `tenantsApi.create` unused.
- **Cards:** `TenantCard` (87–147) renders channel badges, 4 `StatBox`es, and a token-usage progress bar (`Math.min(100, used/quota*100)`); entire card is a `<Link href={/dashboard/${t.id}}>` — links to `tnt_001`-style IDs that the backend would reject as non-UUID (422 from `get_tenant`'s `uuid.UUID` path typing).
- Marketing `Navbar`/`Footer` from `@/components/site` (different chrome from the tenant layout's private navbar — inconsistent shells).
- **No redirect logic** to a default/last-used tenant; no auth check of its own (relies on `src/middleware.ts`).

### 2.2 `dashboard/[tenantId]/layout.tsx` (114 lines, client) — tenant shell
- **Sidebar:** 11 nav items (lines 21–33): Overview, Chat, Products, Orders, Customers, Conversations, Crawl & Knowledge, Style Learning, Scheduler, Insights, Settings. Active state: exact `pathname === fullPath` string equality (line 56) — fine for flat routes.
- **Auth guard: NONE in the layout.** The only protection is `src/middleware.ts:27–41`: server-side, checks **cookie presence** (`zemest_auth` or `sb-access-token`) for `/dashboard/*` and redirects to `/login?redirect=…`. It explicitly does **not** validate the JWT (comment lines 32–33, 43–48: "In production, decode the JWT… For now, allow if cookie exists"). No tenant-ownership check — **any tenantId string in the URL renders the dashboard**.
- **Tenant context: NONE.** No provider, no `tenantsApi.get(tenantId)`, no header showing the tenant name. `params.tenantId` is used only to build nav hrefs (line 37).
- **Params handling:** typed and accessed synchronously (`params: { tenantId: string }`, line 35). With `next@^16.1.1` (`package.json:60`) `params` is a **Promise** for client components and must be unwrapped via `React.use()`; direct property access yields `undefined`. A repo-wide grep finds **zero** `React.use(`/`use(params)` usage, and `next.config.ts` sets `typescript.ignoreBuildErrors: true`, which suppresses the type error that would have exposed this. ⇒ sidebar links likely resolve to `/dashboard/undefined/...` at runtime. (Same pattern in every `[tenantId]` page.)
- **Local `Navbar()`** (lines 88–114): fixed two-tier header — announcement bar ("Rabbit v1 is now live…") + ZEMEST logo + **LOGOUT as a plain `<Link href="/get-started">`** — it neither calls `useAuthStore.logout()` (which POSTs `/api/auth/logout` to clear cookies) nor clears the `zemest_auth` cookie; "logout" leaves a valid session cookie behind.
- **Mobile:** delegates to `MobileSidebar` (`src/components/site/mobile-sidebar.tsx`), a framer-motion drawer that **duplicates the entire 11-item `sidebarItems` array** (mobile-sidebar.tsx:24–36) — two sources of truth for nav.
- Layout uses `pt-[140px]` + sticky `aside` `top-[140px] h-[calc(100vh-140px)]` — magic numbers coupled to the navbar's height.

---

## 3. Page-by-Page Analysis

> Common pattern for **all** tenant pages (with exceptions noted): `"use client"`, hardcoded `const mock*` arrays at module scope, `useState` only for **UI** filters/modals, **zero** data fetching, **zero** CRUD network calls, **no loading / error / empty states** (filtered-out tables simply render fewer rows — no "no results" row), no React Query / zustand / react-hook-form / zod (all are installed dependencies), shadcn/ui components **not used** (hand-rolled brutalist "Tavus" design system via CSS vars + Tailwind).

### 3.1 `[tenantId]/page.tsx` — Overview (133 lines)
- **Purpose:** KPI tiles + recent orders + top products + quick actions.
- **Data:** module-level `stats`, `recentOrders` (5), `topProducts` (5) constants (lines 5–26). No `tenantsApi.stats()` call.
- **Header hardcodes tenant name** "Cairo Sneakers Store" (line 46) — ignores `params.tenantId`; every tenant shows the same name.
- Quick-action buttons are plain `<a href>` (not `<Link>`) — full page reloads; one contains a typo class `active:translate-x=1` (line 125, invalid Tailwind, dead style).
- `statusColors` map (lines 28–34) duplicated verbatim in customers + orders pages.

### 3.2 `[tenantId]/chat/page.tsx` — Chat Playground (160 lines) — see §4

### 3.3 `[tenantId]/conversations/page.tsx` — Conversation log (219 lines)
- **Purpose:** searchable/filterable conversation table + read-only thread modal.
- **Data:** `mockConversations` (6 rows: `customer_name, channel: fb|ig|wa, status: active|waiting|resolved|handed_off, message_count, last_message, last_message_at`), `mockThread` (5 messages). No API call; **no `conversationsApi` exists in the client at all** (backend has GET `/api/tenants/{t}/conversations` + `/{conversation_id}`, `conversations.py:21,59`).
- **State:** `search`, `statusFilter`, `selected` (modal). Client-side filtering over mocks (lines 57–61).
- **Modal:** `ConversationDetailModal` (155–218) — renders the **same `mockThread` for every conversation**; footer says "This thread is read-only. To reply, open the live chat interface." No pagination despite backend's page/page_size.
- Row `onClick` opens modal; the per-row VIEW button also opens modal (redundant double affordance, lines 117, 134–137). Modal lacks `role="dialog"`, focus trap, Escape-to-close.
- Footer counters: `{filtered.length} conversations` / `n active` (144–147) — only live logic in the page.

### 3.4 `[tenantId]/crawl/page.tsx` — Knowledge builder (188 lines)
- **Purpose:** start crawl jobs + knowledge-base stats + job history table.
- **Data:** `mockJobs` (5 rows: `url,status: queued|running|completed|failed,pages_found,products_extracted,started_at,finished_at`); KB stats hardcoded (62 pages, 87 products, "Aug 27, 09:14 AM", "14.2 MB").
- **Forms:** "START CRAWL JOB" button `onClick={() => { setUrl(""); setDepth("2"); }}` (line 83) — **resets the form instead of submitting**; no URL validation; depth select 1/2/3/5. Backend `POST /api/tenants/{t}/crawl` (`crawl.py:18`, `CrawlRequest{url,depth=3}`) is never called; no crawlApi in client.
- "REBUILD INDEX" button (108–110): no handler. No polling of running jobs (backend has `GET /crawl/jobs/{job_id}` for status, `crawl.py:254` — unused).
- `KBStat` component (173–188) is the 4th near-identical stat-tile variant in the dashboard.

### 3.5 `[tenantId]/customers/page.tsx` — Customer directory (234 lines)
- **Purpose:** searchable customer table + customer profile modal with order history.
- **Data:** `mockCustomers` (8 rows: `name, phone, governorate, channel, orders_count, total_spent, last_seen`) + `mockOrders` (5). Backend `GET /api/tenants/{t}/customers` exists (`customers.py:33`; `CustomerResponse` has `orders_count`, `total_spent` ✅ but **no `channel` and no `last_seen`** — contract mismatch if wired). **No customersApi in client.**
- **State:** `search` (name OR phone match), `channelFilter`, `selected`. Footer computes `filtered.reduce(... total_spent)` sum — 2nd live computation.
- **Modal:** `CustomerDetailModal` (161–234) — identity block, 4 stat tiles (AVG ORDER computed via `Math.round(total/Math.max(1,orders_count))`), and **the same 5 `mockOrders` shown as history for every customer**.
- `statusColors`/`channelColors` duplicated from other pages (43–55).

### 3.6 `[tenantId]/insights/page.tsx` — Performance insights (183 lines)
- **Purpose:** FB + IG 30-day overview, weekly engagement bar chart, top posts.
- **Data:** `fbOverview`/`igOverview` (followers/reach/impressions/engagement + deltas), `topPosts` (5), `trendBars` (7 days). **Static render — not even useState** (only page with zero state). No call to `GET /api/tenants/{t}/insights/overview` or `/insights/best-time` (`scheduling.py:309,368`) — no insightsApi in client.
- "Chart" is 7 divs with `style={{height: %}}` (90–99) — no axis, tooltips, or library; shadcn `chart.tsx` (Recharts wrapper) exists in the repo but unused here.
- Icon selection logic `s.label === "ENGAGEMENT" ? Heart : ...` (lines 62, 76) — fragile string-driven branching.
- Content near-100% duplicated by Scheduler→InsightsTab (§3.9).

### 3.7 `[tenantId]/orders/page.tsx` — Order management (237 lines)
- **Purpose:** orders table with search/status filter, create-order modal, per-row view/refresh actions.
- **Data:** `mockOrders` (5 rows incl. `payment_method: cod|vodafone_cash|instapay|fawry`, `api_status: not_configured|pending|success|failed`). `ordersApi.list` never called; backend GET supports `page`+`status` but page does client-side filtering only.
- **State:** `search`, `statusFilter`, `showCreate`.
- **CreateOrderModal** (154–237): fully uncontrolled inputs; governorate select hardcodes only Cairo/Giza/Alexandria (178–183) while `addressApi.governorates()` returns all 27 Egyptian governorates (unused); CITY select is empty (186–189 — would be populated by `addressApi.cities`, never wired); item rows static (one product select with 2 hardcoded products, 216–223); delivery charge input placeholder "auto" hints at `addressApi.shipping()` (never wired). **"CREATE ORDER" button's onClick is `onClose`** (line 228) — closes the modal without creating anything. If it were wired to `ordersApi.create`, the backend endpoint **always 500s (MissingGreenlet)** — see §5.
- **Eye/RefreshCw row buttons (130–135): no onClick at all** — pure decoration (backend has `POST /orders/{o}/retry-api`, `orders.py:182`, for the refresh concept).
- `statusColors`/`apiColors` duplicated (14–27).

### 3.8 `[tenantId]/products/page.tsx` — Product catalog (246 lines)
- **Purpose:** product table (search/source/stock filters), expandable attribute row, Add Product modal, CSV/URL import buttons.
- **Data:** `mockProducts` (5 rows: `name, name_ar, price, stock: in_stock|limited|out_of_stock, category, source: manual|url|crawl|facebook|owner, attributes{}`). Backend `ProductResponse` (`schemas/product.py:69–79`) = `id,name,price,is_active,source,created_at,attributes{}` — **no `name_ar`, `stock`, or `category` first-class fields**; they'd have to ride in `attributes`. `productsApi.list` never called.
- **State:** 3 filters + `showModal` + `expandedRow`. Pagination footer is fake ("1 / 1", dead PREV/NEXT buttons, 161–163) — backend list is paginated (page/page_size, total).
- **React key bug:** the table body maps products into a keyless `<>` fragment (lines 110–152) with `key` on the inner `<tr>` — React requires the key on the outermost mapped element (the Fragment); using `<>` (which can't take a key) produces the "unique key" warning and can cause incorrect reconciliation when the expansion row reorders.
- **Buttons with no handlers:** CSV and URL import header buttons (48–55) — backend `POST /products/upload-csv` (`products.py:83`) and `POST /products/import-url` (`products.py:102`) exist and are **missing from api-client**; EDIT/DELETE in the expansion row (146–147) — `productsApi.update/delete` exist but unwired.
- **AddProductModal** (174–246): uncontrolled; Arabic name field with `dir="rtl"` (191 — good RTL touch); custom attribute key/value rows static; **"SAVE PRODUCT" onClick = `onClose`** (237).
- Arabic secondary name rendering `dir="rtl"` (line 114) is the only i18n-aware render in the dashboard.

### 3.9 `[tenantId]/scheduler/page.tsx` — Social scheduler (439 lines — largest page)
- **Purpose:** 4 tabs — Calendar, Composer, Posts, Insights.
- **State:** single `tab` state; ComposerTab holds `platforms[]`, `caption`, `mediaType`, `scheduledAt`.
- **CalendarTab** (106–162): hardcoded "AUGUST 2026" with a fixed 35-cell `monthDays` array (30–36) with per-day post counts rendered as dots; prev/next month buttons dead (114–119). Backend has `GET /api/tenants/{t}/schedule/posts` (`scheduling.py:111`) — unused.
- **ComposerTab** (164–299): platform multi-toggle (FB/IG), caption textarea with live `caption.length / 2200` counter (220 — nice), media type select, `datetime-local` input, **"GENERATE WITH AI"** button (251–254, no handler — backend `POST /schedule/generate-caption` exists at `scheduling.py:215`), "SCHEDULE POST" disabled until caption+platform (258, good UX) but **no onClick** — backend `POST /schedule/post` (`scheduling.py:65`) unused. Live post preview card (268–296) reflecting caption/media/platforms/schedule — genuinely well-built prototype.
- **PostsTab** (301–351): `mockPosts` table (5 rows, status scheduled/published/failed/draft).
- **InsightsTab** (353–427): duplicated FB/IG overview stat cards (same numbers as insights page) + **best-time heatmap** — 7×6 intensity grid from hardcoded `heatmapData` (43–51) with legend; maps conceptually to backend `GET /insights/best-time` (`scheduling.py:368`) — unused. **Fragment-key bug again** (lines 402–413: `<>` wrapping label div + cells inside `.map`, key only on inner div).
- Postiz integration (`/api/tenants/{t}/postiz/*` — posts CRUD, best-time, generate) exists in backend and is wholly unrepresented.

### 3.10 `[tenantId]/settings/page.tsx` — Tenant configuration (356 lines)
- **Purpose:** 10 accordion sections: business, delivery, payment, FB/IG/WA integrations, order API, knowledge, owner chat, danger zone.
- **State:** single `open` accordion id. Every form is **uncontrolled** (`Field` uses `defaultValue`, lines 70–77; `SelectField`, `ToggleRow` with local `on` state, 92–108). **Every "SAVE CHANGES" and "DISCARD" button is dead** (`SaveBar`, 110–121) — `tenantsApi.update` unused. Backend PATCH `/api/tenants/{t}` covers only a subset (page_name/website/phone/email/delivery/payment_methods/order_api_config per `TenantResponse`) — FB/IG/WA integration settings, handoff config, knowledge settings have **no backend endpoints at all** (facebook.py is a canvas OAuth flow, not settings storage).
- **Mock secrets in plain sight:** access tokens ("EAAG•…"), webhook verify tokens ("zemest_verify_8s2k", "zemest_wa_verify"), API key "zemest_live_8s2k4m9x", API secret — fabricated but normalizing rendering live credentials in unmasked text inputs.
- **DangerForm** (320–338): 4 destructive actions (reset style profile, clear conversations, disconnect channels, delete tenant) with "EXECUTE" buttons — **no handlers, no confirmation dialogs**. Backend has `POST /rebuild-style` for #1; **no endpoints for the other three**.
- Interesting backend-backed concepts that exist but are unwired: delivery charge inside/outside Cairo + free_delivery_above (`TenantResponse` fields) vs the page's generic "DEFAULT COURIER"/"DELIVERY TIME WINDOW" selects — **field mismatch** (backend has no courier or time-window concept).

### 3.11 `[tenantId]/style/page.tsx` — Brand voice (216 lines)
- **Purpose:** display learned style profile; upload chat-history ZIP per channel; rebuild profile.
- **Data:** `styleProfile` const (tone, formality 65, greeting_patterns, emoji_frequency, top_emojis, language_mix, top_vocabulary, personality_summary). Backend `GET /api/tenants/{t}/style-profile` (`style_learning.py:134`) unused — no styleApi in client.
- **Upload UX (best form in the dashboard):** channel select, drag-and-drop zone with `onDragOver/onDragLeave/onDrop` setting `fileName` (139–160), hidden file input overlay with `accept=".zip"`, UPLOAD button disabled until a file is chosen (163). **But UPLOAD has no onClick** — backend `POST /import/chat-history` (multipart, 500MB cap, `style_learning.py:45`) is never called and the api-client has no multipart support at all (its `request()` always sets JSON content-type).
- Per-channel export instructions card (172–190) — good UX copy (Meta DYI / IG data download / WhatsApp export).
- "REBUILD STYLE PROFILE" button (193–196): no handler (backend `POST /rebuild-style`, `style_learning.py:153`).

---

## 4. Chat Page — Special Attention (`chat/page.tsx`)

**How it "works":** It doesn't hit any API. `handleSend` (lines 22–37):
1. Appends the typed text as a `{role:"customer"}` message.
2. `setTimeout(1200ms)` appends a **hardcoded canned reply** — `"I understand. Let me check that for you right away."` (customer mode) or `"I can help you generate posts, check insights, or find the best time to post…"` (owner mode).
- **Real-time:** none. No SSE, no WebSocket, no polling, no streaming. Not even a request/response cycle.
- **The intended backend contract is sitting right there, unwired:** `chatApi.test(tenantId, message, customerName)` → `POST /api/test/chat` (`test_chat.py:15`) with an exactly-matching `TestChatRequest{tenant_id, customer_name, message}` and a `TestChatResponse{reply, conversation_id, customer_id, tokens_used}` that maps **field-for-field onto the Debug panel** (`CONVERSATION ID`, `CUSTOMER ID`, `TOKENS USED (LAST)` — chat/page.tsx:140–143). The Owner-chat toggle maps to `chatApi.ownerChat` → `POST /api/test/postiz-chat` (`test_chat.py:100`). The wiring was clearly scoped and then never done.
- **Unused inputs:** `customerName` state (editable field, line 132–138) feeds nothing; `ownerMode` only flips the canned string; `tenantId` param is not used at all in the page body.
- **Message rendering / XSS:** all messages render as text children (`{m.content}`, line 91) — **no `dangerouslySetInnerHTML` anywhere in the dashboard** (repo-wide grep: only shadcn `chart.tsx:83` lib-internal). React escaping ⇒ **XSS-safe** by construction.
- **Media display:** none — no image/video/attachment rendering despite `media_type` concepts existing on the scheduler page.
- **Input ergonomics:** Enter sends, Shift+Enter does nothing (input, not textarea — line 103); send button disabled on empty (109); trash button clears thread (114–119). No auto-scroll to bottom, no typing indicator, no timestamps on playground bubbles (conversations modal does show time).
- **Debug panel:** all values hardcoded (`conv_test_001`, `cust_test_001`, `142`, `1,840`, `english`, `us_english` — lines 140–145). Language/dialect detection fields have **no counterpart in `TestChatResponse`** (backend doesn't return language/dialect) — a contract gap on the backend side.
- Rating driver: beautiful, safe UI; zero functionality.

---

## 5. Backend Contract Mapping & Mismatches

### 5.1 Which pages call which backend endpoints (intended vs actual)

| Page | Backend endpoints that exist | api-client coverage | Actually called? |
|---|---|---|---|
| dashboard home | GET `/api/tenants` (`tenants.py:45`); POST `/api/tenants` (`:33`); GET `/api/tenants/{id}/stats` (`:71`) | `tenantsApi.list/create/stats` ✅ | ❌ none |
| Overview | GET `/api/tenants/{id}/stats` → `{products_count, orders_count, pending_orders, active_conversations, total_revenue, total_tokens_used, chat_tokens, crawl_tokens}` (`tenant_service.py:32+`) | `tenantsApi.stats` ✅ | ❌ none |
| Chat | POST `/api/test/chat`, POST `/api/test/postiz-chat` (`test_chat.py:15,100`) | `chatApi.test/ownerChat` ✅ | ❌ none |
| Conversations | GET `/api/tenants/{t}/conversations`, GET `/{cid}` (`conversations.py:21,59`) | ❌ **no conversationsApi** | ❌ |
| Crawl | POST `/api/tenants/{t}/crawl`, GET `/crawl/jobs`, GET `/crawl/jobs/{jid}` (`crawl.py:18,232,254`) | ❌ **no crawlApi** | ❌ |
| Customers | GET `/api/tenants/{t}/customers`, GET/PATCH `/{cid}` (`customers.py:33,81,148`) | ❌ **no customersApi** | ❌ |
| Insights | GET `/api/tenants/{t}/insights/overview`, `/insights/best-time`, `/insights/post/{pid}` (`scheduling.py:309,368,391`) | ❌ **no insightsApi** | ❌ |
| Orders | GET/POST `/api/tenants/{t}/orders`, GET `/{oid}`, PATCH `/{oid}/status`, PATCH `/{oid}/notes`, POST `/{oid}/retry-api`, PATCH `/{oid}/payment` (`orders.py:46,115,132,144,167,182,198`) | `ordersApi.list/get/create/updateStatus` ✅ (notes/retry/payment missing) | ❌ |
| Products | GET/POST `/api/tenants/{t}/products`, GET/PATCH/DELETE `/{pid}`, POST `/upload-csv`, POST `/import-url` (`products.py:35,54,83,102,147,164,186`) | `productsApi` ✅ but **upload-csv / import-url missing** | ❌ |
| Scheduler | POST `/schedule/post`, GET `/schedule/posts`, PATCH/DELETE `/schedule/posts/{pid}`, POST `/schedule/generate-caption` (`scheduling.py:65–215`); full Postiz router `/api/tenants/{t}/postiz/*` (`postiz.py`) | ❌ **no schedulingApi / postizApi** | ❌ |
| Settings | PATCH `/api/tenants/{t}` (`tenants.py:59`) — covers business/delivery/payment/order_api only | `tenantsApi.update` ✅ | ❌ |
| Style | POST `/import/chat-history` (multipart), GET `/style-profile`, POST `/rebuild-style` (`style_learning.py:45,134,153`) | ❌ **no styleApi; client can't even send multipart** | ❌ |

### 5.2 The broken backend endpoint the pages would hit
- **`POST /api/tenants/{t}/orders` ALWAYS returns 500 (`sqlalchemy.exc.MissingGreenlet`)** — reproduced by agent Z6 (worklog:327): `orders.py:41 _order_response(o)` lazy-loads `o.items` after `order_service.create_order` inserted OrderItems directly, in an async session. **The Orders page's Create-Order modal is the UI designed to call exactly this endpoint** (via `ordersApi.create`). Today the page never calls it (so no user-visible failure), but the moment the data layer is wired, manual order creation — the core "dashboard" action — will 500 on every attempt. The modal's field set (`customer_name, customer_phone, governorate, city, area?, address_detail, payment_method, delivery_charge, notes?, items[{product_name,quantity,unit_price}]`) otherwise matches `ManualOrderCreate` (`schemas/order.py:70–80`) 1:1 — the contract was designed correctly and left disconnected from a broken backend.

### 5.3 Field-level mismatches (frontend mock shape vs backend schema)
- **Products:** mock `name_ar`, `stock`, `category` — not in `ProductResponse` (must move to `attributes` or backend must add columns).
- **Conversations:** mock `channel`, `message_count`, `last_message` preview — not in `ConversationResponse` (`id, customer_name, status, started_at, last_message_at`); backend also has no `status` query filter that the page's dropdown implies (list endpoint only takes page/page_size).
- **Customers:** mock `channel`, `last_seen` — not in `CustomerResponse`; `orders_count`/`total_spent` ✅ exist.
- **Crawl:** mock `started_at`/`finished_at` vs backend `created_at` (+ `error_message` unused by the UI).
- **Overview stats:** mock wants *today's* orders/revenue + token *quota*; backend stats returns lifetime aggregates and token usage **without quota** (no quota concept exists).
- **Chat debug:** `detected language/dialect` — no backend field.
- **Tenant card:** mock `fb_connected/ig_connected/wa_connected` — `TenantResponse` has only `fb_page_id`; IG/WA connection state not modeled.
- **Auth:** `TokenResponse` has no `refresh_token`, yet the BFF destructures one (login/route.ts:23) and api-client's 401 handler implies a refresh flow that has no endpoint.

---

## 6. Code Quality Assessment

### 6.1 Duplication (the big one)
- **`statusColors` order-status map duplicated 3×** — overview:28–34, customers:49–55, orders:14–20 (identical).
- **`channelColors` map duplicated 2×** — conversations:39–43, customers:43–47 (+ inline ternaries in scheduler/insights).
- **Sidebar nav array duplicated 2×** — layout.tsx:21–33 and mobile-sidebar.tsx:24–36 (11 items each; adding a page requires editing both).
- **7 near-identical stat-tile components**: `StatBox` (dashboard:149), overview stat tile (53–62), `CustomerDetailModal` stats (162–167), `OverviewStat` (insights:159), `InsightStat` (scheduler:429), `ProfileStat` (style:203), `KBStat` (crawl:173) — all "icon + tiny label + bold value" with the same wrapper div.
- The brutalist button class string (`border-[3px] … shadow-[3px_3px_0_0…] hover:shadow-[4px_4px…] hover:-translate-x-0.5 … transition-all`, ~400 chars) is copy-pasted **~20 times** across these files; no `Button`/`Panel`/`WindowTitleBar`/`StatusBadge` abstraction; **shadcn/ui is installed and unused on every dashboard page**.
- Insights content (FB/IG overview cards with identical numbers) duplicated between insights/page.tsx and scheduler InsightsTab.

### 6.2 Dead / fake code
- `api-client.ts` in its entirety (134 lines, zero importers).
- Buttons with no handlers: CREATE BUSINESS, START CRAWL JOB, REBUILD INDEX, REBUILD STYLE PROFILE, UPLOAD, GENERATE WITH AI, SCHEDULE POST, SAVE PRODUCT, CREATE ORDER, all SAVE CHANGES/DISCARD, all EXECUTE (danger zone), orders Eye/RefreshCw, products EDIT/DELETE/CSV/URL, calendar prev/next, pagination PREV/NEXT.
- Overview typo class `active:translate-x=1` (page.tsx:125).
- `ownerChat`'s/`test`'s owner-mode concept exists in the client but the chat page's owner toggle is cosmetic.

### 6.3 Inconsistent patterns
- Two different navbars: dashboard home uses marketing `Navbar`+`Footer`; tenant pages use the layout's private 2-tier fixed navbar with `pt-[140px]`.
- `<Link>` vs raw `<a href>` for internal navigation (overview quick actions use `<a>`).
- Mock field naming is snake_case (matches backend convention — good) but nothing consumes it.
- Forms: mixture of controlled (filters, composer, chat) and uncontrolled (`defaultValue`) forms; no react-hook-form/zod despite both installed.
- `params.tenantId` accessed synchronously in all client pages under Next 16 (Promise params) with `ignoreBuildErrors: true` hiding the type error.

### 6.4 i18n / Arabic
- No i18n framework (no next-intl/react-i18next in deps). All UI chrome English-only.
- Arabic appears only as *data*: `name_ar` with `dir="rtl"` (products:114, settings BusinessForm ARABIC NAME:131, AddProductModal:191), Arabic mock strings. Given the product is Egyptian-market AI moderation with Arabic dialect detection, the absence of an Arabic dashboard locale is a strategic gap (the announcement bar even advertises "Arabic moderation with every accent").

### 6.5 Accessibility
- Icon-only buttons without `aria-label`: orders view/refresh (130–135), products expand (124), conversations view (135–137); only MobileSidebar's menu button has one (mobile-sidebar:49).
- Modals: no `role="dialog"`/`aria-modal`, no focus trap, no Escape handling, no initial focus (conversation/customer/order/product modals).
- No `<label htmlFor>` ↔ input id linkage anywhere — labels are purely visual.
- Status conveyed by color alone (badges); heatmap cells rely on `title` (good) but tiny 8–10px uppercase text throughout strains WCAG legibility.
- Table rows as click targets with nested buttons (conversations) — marginal for keyboard/AT users.

---

## 7. Issues & Risks (file:line)

**Critical**
1. **Zero API integration** — every dashboard page renders only hardcoded mocks; no fetch anywhere under `src/app/dashboard/` (all 12 files).
2. **api-client is dead code** with a **fatal auth mismatch**: sends cookies to a Bearer-only backend (`api-client.ts:25–32` vs `zemest/app/dependencies.py:12–24`) ⇒ all authenticated calls would 401 if ever wired; correct pattern already exists in the BFF routes (`src/app/api/auth/login/route.ts:11–15,29–35`).
3. **Orders create → backend 500 MissingGreenlet** (`zemest/app/api/orders.py:41` lazy-load of `o.items`): the endpoint behind `ordersApi.create` (`api-client.ts:99`) and the Orders page Create-Order modal (`orders/page.tsx:154–237`) is broken server-side.
4. **Next 16 async-params violation**: `params` accessed synchronously in client layout/pages (`layout.tsx:35–37`, every `[tenantId]` page) with no `React.use()` anywhere; `next.config.ts:4–6 ignoreBuildErrors: true` masks it. Likely produces `/dashboard/undefined/...` links at runtime.
5. **No real auth guard in the app shell**: middleware only checks cookie *presence* (`src/middleware.ts:34–41`); no JWT validation, no tenant-ownership check — any tenantId renders; LOGOUT is a plain Link that never clears cookies (`layout.tsx:104–109` vs `auth-store.ts:27–32`).

**High**
6. Client data layer missing 6 of ~15 backend router groups — conversations, customers, crawl, style, scheduling/insights, postiz have no API functions at all (`api-client.ts`).
7. Mock tenant IDs `tnt_001/tnt_002` are not UUIDs — backend `get_tenant` would 422 (`dashboard/page.tsx:11,27`); even a "wired" home page links to invalid tenants.
8. Products page fragment-key bug: keyless `<>` wrapping mapped `<tr>`s (`products/page.tsx:110–152`); same in scheduler heatmap (`scheduler/page.tsx:402–413`).
9. `refresh_token` fiction: BFF destructures a field the backend never returns (`login/route.ts:23` vs `schemas/auth.py:27–29`); no refresh endpoint exists; api-client comment claims refresh it doesn't do (`api-client.ts:37–43`).

**Medium**
10. Field-shape mismatches on wire-up (products `name_ar/stock/category`, conversations `channel/message_count/last_message`, customers `channel/last_seen`, overview stats today/quota, chat language/dialect) — §5.3.
11. `productsApi` lacks `upload-csv`/`import-url` while the UI has buttons for both (`products/page.tsx:48–55` vs backend `products.py:83,102`); api-client cannot send multipart at all.
12. Fake but credential-shaped secrets rendered in settings (`settings/page.tsx:197–199,249–251,270–271`) normalize unmasked secret display.
13. Overview hardcodes tenant name "Cairo Sneakers Store" for every tenant (`page.tsx:46`); customer modal shows the same order history for all customers (`customers/page.tsx:216`); conversation modal shows the same thread for all conversations (`conversations/page.tsx:197`).
14. Duplication: 3× statusColors, 2× channelColors, 2× sidebarItems, 7× stat-tile components, ~20 copies of the brutalist button class string (§6.1) — maintenance hazard.
15. Danger-zone "EXECUTE" buttons (delete tenant, clear conversations) with no handler and — even when wired — no backend endpoints for 3 of 4 actions (`settings/page.tsx:320–338`).

**Low**
16. No loading/error/empty states anywhere (nothing async to load; filtered tables show no "no results" row).
17. `<a>` instead of `<Link>` for internal quick actions (`[tenantId]/page.tsx:117–128`); dead typo class `active:translate-x=1` (`:125`).
18. A11y gaps (§6.5); English-only UI for an Arabic-first market (§6.4).
19. api-client forces JSON Content-Type on GET/DELETE; no timeouts/retries (`api-client.ts:28–31`).

---

## 8. Quality Ratings (per file)

| File | Rating | Justification |
|---|---|---|
| `lib/api-client.ts` | **4/10** | Clean namespacing, working error class, correct URL/param building for what exists — but dead code, untyped (`any`), wrong auth mechanism (cookie→Bearer-only backend), fictitious refresh, missing 6 endpoint groups & multipart support. |
| `dashboard/page.tsx` | **3/10** | Attractive cards with channel badges + token bar; pure mock list, dead create form, non-UUID tenant links, no tenant fetch. |
| `[tenantId]/layout.tsx` | **5/10** | Best file of the set: responsive shell, working active-state nav, mobile drawer; but duplicated nav data, fake logout, no tenant context/guard, sync params access. |
| `[tenantId]/page.tsx` (overview) | **3/10** | Nice tile/list composition; hardcoded tenant name, mock data, typo class, `<a>` links. |
| `[tenantId]/chat/page.tsx` | **3/10** | Safe (no innerHTML), tidy chat UI with debug panel shaped exactly like the backend response — but zero API wiring, fake 1.2s canned replies, unused customerName/tenantId. |
| `[tenantId]/conversations/page.tsx` | **3/10** | Solid filter+modal UX; same thread for every row, no pagination, no conversationsApi exists, a11y-less modal. |
| `[tenantId]/crawl/page.tsx` | **3/10** | Good job-table UX; "START CRAWL" literally resets the form, no job polling, no crawlApi. |
| `[tenantId]/customers/page.tsx` | **3/10** | Search by name/phone + channel filter works on mocks; same order history for all, duplicated color maps, no customersApi. |
| `[tenantId]/insights/page.tsx` | **2/10** | Static-only (no state at all), div-bar chart, content duplicated by scheduler InsightsTab, no insightsApi. |
| `[tenantId]/orders/page.tsx` | **2/10** | Richest mock schema (payment/api_status columns well-modeled) — but CREATE closes the modal, row actions are decoration, and the wired backend endpoint 500s; hardcoded 3-governorate list vs 27 available. |
| `[tenantId]/products/page.tsx` | **3/10** | Expandable attribute rows + RTL Arabic name are thoughtful; React key bug, dead CSV/URL/EDIT/DELETE, fake pagination. |
| `[tenantId]/scheduler/page.tsx` | **3/10** | Most ambitious page (4 tabs, live preview, character counter, disabled-until-valid submit) — all mock; calendar hardcodes Aug 2026; key bug in heatmap; generate-caption endpoint exists unused. |
| `[tenantId]/settings/page.tsx` | **2/10** | 10 sections of uncontrolled dead forms; every SAVE/DISCARD/EXECUTE inert; mock secrets in plain text; most sections have no backing endpoints. |
| `[tenantId]/style/page.tsx` | **3/10** | Best form UX in the dashboard (drag-drop, disabled-until-file, per-channel instructions); upload does nothing and the client can't send multipart anyway. |

**Overall dashboard module: 3/10** — an excellent visual design-system prototype (consistent brutalist "Tavus" aesthetic, thoughtful micro-UX in places) that has not begun integration: 0 fetches, 0 wired CRUD, dead data layer with a broken auth model, and a known-broken backend endpoint at the end of its most important user flow.

---

## 9. Recommended Next Actions (for synthesis)
1. Decide BFF-first architecture: route all tenant-dashboard calls through Next route handlers (cookie→Bearer translation), delete or rewrite `api-client.ts` on that basis; add the missing 6 API groups; type them from the OpenAPI spec (`openapi-fetch`).
2. Fix backend `POST /orders` MissingGreenlet (eager-load items in `create_order` or `refresh`) before wiring the Orders page.
3. Migrate `params` to `React.use()` (or `async` server components) across `[tenantId]` pages; turn off `ignoreBuildErrors`.
4. Extract shared `Button`/`Panel`/`StatusBadge`/`StatTile` + single sidebar config + single status/channel color tokens; adopt shadcn/ui already in the tree.
5. Add real auth: JWT validation + tenant-ownership check in middleware (or server layout), real logout via `auth-store.logout()`, and a refresh story (needs a backend refresh endpoint).
6. Wire Chat page first (contract matches 1:1), then Products (including CSV/URL endpoints), then Orders — highest value, endpoints ready except orders-create.
