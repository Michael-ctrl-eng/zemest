# P4 — Admin Area & Auth Pages: Deep Analysis (zemest-platform)

**Task ID:** P4 · **Agent:** general-purpose (admin & auth)
**Scope:** `/admin/*` (layout + 8 pages), `components/site/auth-page.tsx`, `/login`, `/register`, `/forgot-password`, `stores/auth-store.ts`, `stores/ui-store.ts`, hooks `use-toast.ts`, `use-debounce.ts`, `use-mobile.ts`.
**Method:** Every in-scope file read line-by-line; every claim cross-verified with grep (imports, call sites) against the full `src/` tree and against the FastAPI backend (`repos/zemest/app/admin/api.py`, `app/api/auth.py`, `app/schemas/auth.py`, `app/dependencies.py`, `app/main.py`). Prior findings from worklog (P1, P2, Z10, Z11) re-verified from primary sources.

**Headline verdict:** The admin area is a fully-designed, zero-function mockup — **not one of the 8 admin pages makes a single network request** (grep proof: the only imports across `src/app/admin/**` are `react`, `next/link`, `next/navigation`, and `lucide-react`). The auth surface is equally hollow: the login form is a `preventDefault()` stub, registration performs client-side validation and then fake-redirects to `/dashboard`, password reset fabricates a success screen with no backing endpoint, and the only real auth path (BFF login route → httpOnly cookie → middleware) is never triggered by any UI. Both Zustand stores are dead code (zero importers). Cross-referencing the backend, even the *intended* wiring is broken (Bearer-only backend auth vs cookie-based BFF client; missing `/api/auth/me` BFF route; missing Facebook OAuth callback).

---

## 1. Auth Architecture End-to-End

### 1.1 Component inventory

| File | Role | Lines | Real functionality |
|---|---|---|---|
| `src/components/site/auth-page.tsx` | Shared login/signup card (used by `/login` + `/get-started`) | 245 | **None** — form is a no-op |
| `src/app/login/page.tsx` | Server wrapper → `<AuthPage mode="login"/>` + metadata | 11 | Renders only |
| `src/app/get-started/page.tsx` | Server wrapper → `<AuthPage mode="get-started"/>` | 11 | Renders only |
| `src/app/register/page.tsx` | Standalone signup (does NOT reuse AuthPage) | 117 | Client-side validation only, fake redirect |
| `src/app/forgot-password/page.tsx` | Standalone reset request | 88 | Fake success state |
| `src/app/api/auth/login/route.ts` | BFF login → backend → httpOnly cookies | 52 | **Fully implemented, never called** |
| `src/app/api/auth/register/route.ts` | BFF register → backend → auto-login cookies | 49 | **Fully implemented, never called** |
| `src/app/api/auth/facebook/route.ts` | FB OAuth redirect + token exchange | 67 | Half-implemented (no callback route) |
| `src/app/api/auth/logout/route.ts` | Clears cookies | 12 | Works; only caller is dead code |
| `src/middleware.ts` | Route gate for `/dashboard`, `/admin` | 56 | Cookie-presence check only |
| `src/lib/api-client.ts` | Typed-ish fetch client incl. `authApi`/`adminApi` | 134 | **Never imported anywhere** |

### 1.2 `auth-page.tsx` — full anatomy

**Props:** single prop `mode: "get-started" | "login"` (auth-page.tsx:8-12). There is **no register or forgot mode** — those are separate page files that duplicate the entire card chrome (register/page.tsx:36-113 re-implements the background, giant title, window title bar, social buttons).

**Mode-driven copy (L15-23):** title "Getting Started"/"Login", eyebrow, submit label, footer link swaps (`/login` ↔ `/register`). Note the asymmetry: signup mode links to `/register` (the real page), login mode links to `/register` via footerCta "Get started" — but `/get-started` (the AuthPage signup mode) is a *third* registration surface reached only from the marketing funnel. Three sign-up paths, one stub.

**Form logic (L116):** `<form ... onSubmit={(e) => e.preventDefault()}>`. That is the entire submit handler. Consequences:
- Uncontrolled `Field` inputs (L211-244) — values never read; no `useState` for email/password at page level.
- No validation, no error display, no loading state, no API call, no redirect.
- The "Sign in" button (L144-150) is type=submit → preventDefault → nothing.
- Terms checkbox (L124-131) — decorative; not required, unchecked, links are `href="#"` (L128-129).
- "Remember me" (L134-136) — uncontrolled; the BFF login route accepts a `remember` flag (login/route.ts:8,27) that can never be sent from this UI.
- `Field` sub-component (L211-244) holds one piece of state — `focused` — used solely to animate the box-shadow (L238-239). No `aria-invalid`, no error slot.

**Facebook OAuth (L166-172):** `onClick={() => (window.location.href = "/api/auth/facebook")}` — a full-page navigation to the BFF route's GET handler (facebook/route.ts:61-66), which redirects to `https://www.facebook.com/v18.0/dialog/oauth?client_id=…&redirect_uri=${origin}/api/auth/facebook/callback&scope=email&response_type=code`. Broken four ways:
1. **No callback route exists** — `src/app/api/auth/` contains only `facebook/`, `logout/`, `register/`, `login/` (LS-verified). The redirect_uri `/api/auth/facebook/callback` 404s, so the flow can never complete. (P2's "only Facebook OAuth works" is true only up to the outbound redirect.)
2. **Fallback client id** `NEXT_PUBLIC_FB_APP_ID || "demo_client_id"` (facebook/route.ts:62) → in any env without the var, users land on a Facebook error page.
3. **No `state` parameter** → classic OAuth CSRF window (login-csrf).
4. The POST variant (facebook/route.ts:8-58, expects `fb_access_token` in body and calls backend `/api/auth/facebook`) is dead — no frontend code issues that fetch (grep: only the two `window.location.href` navigations exist).

**Google/SSO buttons (L173-181):** rendered from `["Google", "SSO"].map(...)` with **no onClick handler at all** — pure decoration, identical in register/page.tsx:103-104. Dead on arrival.

### 1.3 `/register` (register/page.tsx)

The only auth form with real client-side logic (L12-33):
- Validation (L22-27): name ≥ 2 chars; email regex `^[^\s@]+@[^\s@]+\.[^\s@]+$`; password ≥ 8 chars AND `(?=.*[a-zA-Z])(?=.*\d)`; confirm match. Errors rendered inline per field (L74, 79, 87, 92).
- On success (L30-32): `window.location.href = "/dashboard"` — **no call to `/api/auth/register`** even though that BFF route is complete (register/route.ts). Since no cookie is set, middleware bounces the user to `/login?redirect=/dashboard` (middleware.ts:36-41), where the `redirect` param is silently dropped (login page never reads `searchParams`). Net effect: users who "register" are dumped on the login page with zero explanation. No duplicate-email error path, no server validation, no Terms enforcement.
- Password visibility toggle (L84-85, L91) shared by both password fields; Facebook button same broken OAuth; Google/SSO dead (L102-104).

### 1.4 `/forgot-password` (forgot-password/page.tsx)

- Two-state component: form ↔ `submitted` success card (L46-56).
- Submit handler (L58): `e.preventDefault(); setSubmitted(true);` — **no network request**. The success screen claims "We sent a reset link to {email}" (L52).
- Cross-checked backend: `app/api/auth.py` exposes only `register`, `login`, `facebook`, `me` — **no reset-request or reset-confirm endpoint exists anywhere in the FastAPI app**, and no BFF route exists either. This is a fabricated success state for a security-sensitive flow (P2 finding, re-verified).
- Only validation is the native `required` on the email input (L63).

### 1.5 The full login flow — as designed vs. as built

**Intended (BFF) flow, traceable in code:**
1. `POST /api/auth/login {email, password, remember}` (login/route.ts:5) →
2. backend `POST /api/auth/login` (auth.py:28-29) returns `TokenResponse {access_token, token_type}` →
3. BFF sets `zemest_auth` httpOnly cookie (24h, or 30d with remember) + `zemest_refresh` (7d) (login/route.ts:26-45) →
4. middleware.ts:34 checks cookie presence for `/dashboard|/admin` →
5. dashboard renders (mock data).

**Actual:** step 1 is never executed — AuthPage's form is a no-op (§1.2). The only way to obtain a session cookie is a manual `curl`-style POST. Steps 2-4 do work mechanically (verified by P1).

**Latent defects in the intended flow (found during trace):**
- **`refresh_token` is a phantom** — backend `TokenResponse` has only `access_token` + `token_type` (schemas/auth.py:27-29). login/route.ts:23 destructures `refresh_token` → always `undefined` → guard at L37 means `zemest_refresh` is **never set**. There is no refresh endpoint in the BFF and no refresh logic in `api-client.ts`. Auth silently expires at cookie maxAge with no renewal path.
- **The `remember` flag can never be true** (UI never sends it) → sessions always 24h.
- **`/api/auth/me` does not exist in the BFF.** middleware.ts:47 claims "real check happens client-side via GET /api/auth/me", but `src/app/api/auth/` has no `me/` route. The only `me()` is `api-client.ts:63`, which calls the **backend** `/api/auth/me` directly with `credentials: "include"` — and the backend authenticates via `HTTPBearer` (Authorization header, dependencies.py:5,12), **not cookies**. So every conceivable `me()` call from the browser returns 401, which the client helper converts into a hard redirect to `/login` (api-client.ts:38-43). The "client-side superadmin check" the middleware defers to is doubly nonexistent.
- **Dashboard performs no auth work at all** — `dashboard/page.tsx` is a pure mock ("use client", hardcoded `mockTenants`, zero fetch/effect/router usage — grep-verified across `src/app/dashboard/**`). No user hydration, no logout button wired to the API.

### 1.6 Logout

- BFF `POST /api/auth/logout` deletes both cookies (logout/route.ts:7-8) — correct, minimal.
- Only caller: `auth-store.ts:29` (fire-and-forget fetch) — but the store is never imported (§2), so in practice logout is reachable only by hand.
- The admin navbar's "LOGOUT" is a plain `<Link href="/">` (admin/layout.tsx:101-106) — navigates home **without clearing cookies**.

---

## 2. Zustand Stores

### 2.1 `stores/auth-store.ts` (33 lines) — dead code

- **State:** `{ user: User | null, loading: boolean }`, initial `loading: true` (L22-25). `User` shape: `{ id, name, email, fb_user_id?, is_superadmin, is_blocked }` (L5-12).
- **Actions:** `setUser` (sets user + loading:false), `setLoading`, `logout` (L27-32) — fire-and-forget `POST /api/auth/logout`, `set({user:null})`, hard `window.location.href = "/login"`.
- **Persistence: none.** No `persist` middleware, no localStorage/sessionStorage, no cookie read. The store is memory-only.
- **Hydration: none.** There is no `useEffect`/provider anywhere calling `/api/auth/me` to populate it. The `loading:true` sentinel implies an intended bootstrap that was never written.
- **Usage: ZERO.** `grep useAuthStore` → only the definition (auth-store.ts:22). `grep "auth-store"` → no importers. The entire client auth-state layer is aspirational dead code. Note also the `User` interface expects `is_superadmin`/`is_blocked`, which the backend `UserResponse` (`{id, name, email, fb_user_id}` — schemas/auth.py:32-38) does not return — so even a wired-up hydration would produce `is_superadmin: undefined`.
- Dependency note: package.json has `zustand ^5.0.6`; `create` import style is v5-correct.

### 2.2 `stores/ui-store.ts` (35 lines) — dead code

- **State:** `sidebarOpen` (+ open/close/toggle), `theme: "light"|"dark"` (+ toggleTheme), `locale: "en"|"ar"` (+ setLocale/toggleLocale) (L5-20, 22-34).
- **Persistence: none.** In-memory only; theme/locale reset on reload.
- **Usage: ZERO** — `grep useUIStore` → only the definition. No component reads `sidebarOpen` (the marketing mobile sidebar uses its own local state per P1), no `ThemeProvider`/`next-themes` consumption of `theme`, and `locale` connects to nothing (`next-intl` is installed in package.json:63 but never imported anywhere — grep-verified). An en/ar toggle for an Egypt-focused product exists only as unused state.

**Store verdict:** Zustand is effectively unused in the shipped app; the only live zustand store is `useToastStore` inside `components/site/toast.tsx` (also never triggered — §5).

---

## 3. Admin Layout & Guard

### 3.1 `src/app/admin/layout.tsx` (113 lines)

- **Client component** ("use client") wrapping all 8 admin pages.
- **Sidebar** (L36-66): 8 nav items — Dashboard, Users, Tenants, IP Bans, Sessions, Audit Log, Analytics, System Health (L17-26); active-state via `pathname.startsWith` with special-case exact match for `/admin` (L48). Styled in the brutalist design system (3px borders, hard shadows).
- **No auth guard whatsoever.** No `useEffect`, no store read, no `/api/auth/me` call, no redirect logic. Anyone who satisfies the middleware's cookie-presence check sees the full panel.
- **Navbar** (L77-112): black announcement bar "Restricted access — superadmins only" (L82-84) — pure typography; a static "SUPERADMIN" badge (L97-100) rendered for every visitor; LOGOUT link to `/` that doesn't clear cookies (L101-106).
- **Mobile gap:** sidebar is `hidden md:block` (L36) and there is **no mobile drawer alternative** — on <768px the admin panel has *no navigation at all* (the marketing site has `mobile-sidebar.tsx`; the admin area doesn't reuse it). Ironically `useIsMobile` (§5) exists but is unused here.

### 3.2 The middleware gate (middleware.ts) — auth theater, confirmed at primary source

- L34: `request.cookies.get("zemest_auth") || request.cookies.get("sb-access-token")` — **presence-only** check. No JWT decode, no signature/expiry verification. `sb-access-token` is a Supabase-legacy name; any value (e.g., `sb-access-token=x` set via devtools) grants access to `/dashboard` **and `/admin`** (P1 finding, re-verified).
- L36-41: unauthenticated users → `/login?redirect=<pathname>`. The `redirect` param is **never consumed** — `login/page.tsx` takes no `searchParams`, AuthPage has no post-login navigation at all (grep across src: zero readers of `redirect`).
- **L44-48 — the empty superadmin gate, quoted verbatim:**
  ```ts
  // Admin routes require superadmin
  if (pathname.startsWith("/admin")) {
    // In production, decode the JWT and check is_superadmin
    // For now, allow if cookie exists — real check happens client-side
    // via GET /api/auth/me
  }
  ```
  Two comments and no code. The deferral is doubly broken: (a) no `/api/auth/me` BFF route exists; (b) no client-side check exists in the admin layout/pages either. **Consequence: the entire admin panel's only access control is "has any auth cookie."** A blocked, non-superadmin, or fully fabricated session reaches every admin page. (Data exposure is currently nil only because the pages render mock data — but this becomes critical the moment real API wiring lands.)
- Backend contrast: the real gate lives at FastAPI `require_superadmin` (admin/api.py:35-41, `HTTPException 403` unless `user.is_superadmin`), backed by Bearer-JWT `get_current_user` (dependencies.py). The frontend never invokes any of it.

---

## 4. Admin Pages — Page-by-Page + Backend Mapping

**Global fact (grep-proven):** across all of `src/app/admin/**` the only imports are `react/useState`, `next/link`, `next/navigation`, `lucide-react`. No `api-client`, no `adminApi`, no react-query, no stores, no `fetch`. Every table, stat, badge, incident, and action below is hardcoded.

Backend reference: router mounted at `main.py:239-241`, `APIRouter(prefix="/api/admin")` (admin/api.py:28) — so endpoints live at **`/api/admin/*`** (not `/admin/api/*`); every handler takes `Depends(require_superadmin)` → **Bearer superadmin JWT required** (admin/api.py:35-41; HTTPBearer in dependencies.py:5,12 — cookies are not accepted). The `adminApi` client (api-client.ts:121-131) that *would* call these endpoints points at `BACKEND_URL` directly with `credentials: "include"` and no Authorization header → guaranteed 401 → helper hard-redirects to `/login` (api-client.ts:38-43). **Even the intended wiring is architecturally broken.**

### 4.1 `/admin` — Dashboard (page.tsx, 101 lines)
- **Data:** `platformStats` — 7 hardcoded cards (1,284 users / 37 tenants / 18,420 orders / 126 sessions / 23 blocked / 147 IP bans / "4.8M / 12M" tokens) (L5-13); `adminActions` — 8 fake feed rows (L15-24) with color map (L26-35).
- **Backend mapping:** `GET /api/admin/analytics/overview` (api.py:279-312) returns exactly `{total_users, total_tenants, total_orders, active_sessions, blocked_users, ip_bans, total_tokens_used}` — 6 of 7 cards map 1:1 (shape-compatible!), but: (a) no quota field exists for "4.8M / 12M" (no `/12M` source in backend); (b) **no endpoint exists for the recent-actions feed** at all; (c) `active_sessions` counts `UserSession` rows active in the last 30 min (api.py:293-299) — and `UserSession(` is never instantiated anywhere in the backend (grep: only the model class def, models/admin.py:26) → the real endpoint returns 0 forever. Also `adminApi.stats()` (the one correct client path) is never called.
- **States:** no loading/empty/error — static render.

### 4.2 `/admin/users` (users/page.tsx, 151 lines)
- **Data:** 8 mock users (L20-29); search by name/email + All/Active/Blocked filter (L35-39) — client-side filtering of mocks, **no debounce** (use-debounce exists, unused).
- **Columns:** name/email, FB ID, badges (SUPERADMIN / BLOCKED), tenant count, last login, last IP, country, device (L80-88).
- **Actions:** eye "view" button — **no onClick** (L127-129); block/unblock button — **no onClick** (L130-135). The single most important admin capability is a decorative icon.
- **Backend mapping:** **no user-list endpoint exists** (REST admin API has no GET /users). Only `POST /api/admin/users/{id}/block` (api.py:137-169) and `DELETE .../block` (api.py:172-189) — both uncallable from this UI. Backend takes `user_id` as UUID; mocks use "u1"…"u8" strings. Also note: `BlockedUser` rows are enforced nowhere in the backend request path (Z11), so blocking wouldn't do anything anyway.
- Footer counts (L143-146) recompute from filtered mocks.

### 4.3 `/admin/tenants` (tenants/page.tsx, 155 lines)
- **Data:** 6 mock tenants (L20-27) with page name, owner email, `fb_page_id` / `ig_user_id` / `wa_phone_id`, active flag, product/order/customer/token counts.
- **Columns:** 11 (L78-88); search + active filter (L33-37); "VIEW" eye button — **no onClick** (L135-141). `—` placeholders for missing social IDs (L100-119).
- **Backend mapping:** **no admin tenant-list endpoint exists.** `/api/tenants` is a tenant-owner-scoped route (requires the caller's tenant context), not a platform-wide admin listing. Token usage per tenant exists as a model (`TokenUsage`) with no admin aggregate endpoint. Nothing on this page has a data source.

### 4.4 `/admin/ip-bans` (ip-bans/page.tsx, 173 lines)
- **Data:** 5 mock bans (L15-21) — `{id, ip, reason, banned_by, banned_at, hits}`.
- **Actions (local-state theater):** `handleAdd` (L29-43) prepends to `useState` array with `banned_by: "root@zemest.com"` hardcoded, `banned_at: "Just now"`, `hits: 0` — **no API call**; `handleRemove` (L45-47) filters the array — no API call. Refresh = data reverts to mocks.
- **Add form:** IP input with **zero validation** (any string accepted, L86-92 — backend would 422 via `ipaddress` checks at api.py:225-234); optional reason.
- **Backend mapping:** `GET /api/admin/ip-bans` (api.py:196-214) returns `[{id, ip_or_cidr, reason, created_at}]` — **no `banned_by`, no `hits`** (the response dict is hand-built; the `IPBanResponse` schema at api.py:57-62, which includes `is_active`, is defined but never used). `POST /api/admin/ip-bans` (api.py:217-255, validates IP/CIDR, dup-check 400, audit-writes `ip.ban`); `DELETE /api/admin/ip-bans/{ban_id}` (api.py:258-272, soft-delete via `is_active=False`). Cross-referenced backend findings that make even direct API use fail: **`IPBan.is_active` is missing from the runtime DDL → UndefinedColumn 500s on the list/delete paths** (Z10/Z11, worklog:239); sqladmin's separate ban CRUD 500s via nonexistent `IPBanMiddleware.invalidate_all()` (admin_panel.py:281,299); and the middleware holds empty ban sets, so bans are never enforced (Z10, worklog:198). Frontend field names (`ip`, `banned_at`, `hits`, `banned_by`) vs backend (`ip_or_cidr`, `created_at`) — full shape mismatch.

### 4.5 `/admin/sessions` (sessions/page.tsx, 190 lines)
- **Data:** 8 mock sessions `{id, user_email, ip, country, device, started_at, last_activity, status: active|expired|revoked}` (L17-26); tabs Active/History derived from status (L44-46).
- **Actions:** row click → `SessionDetailModal` (L151-180, read-only detail rows); revoke button → `handleRevoke` (L39-42) flips local status to "revoked" — **no API call**, reverts on reload.
- **Backend mapping:** `GET /api/admin/analytics/active-sessions` (api.py:420-447) returns `[{id, user_id, ip_address, country, city, device_type, last_activity}]` — no `user_email` (frontend's primary column; backend returns an unresolved `user_id` UUID), no `status`, no `started_at`, no `device` string (device_type only), no browser. **No revoke endpoint exists at all** in the backend REST API. And the table is **never written**: `UserSession(` grep across backend = model definition only → endpoint returns `[]` eternally (backend worklog: "user_sessions table never written"). Per-user history exists (`GET /api/admin/analytics/user/{id}/activity`, api.py:337-365) with yet another shape (`login_at`, `browser`, `is_active`) — also unmapped and equally empty.

### 4.6 `/admin/audit-log` (audit-log/page.tsx, 183 lines)
- **Data:** 10 mock logs `{id, admin(email), action(UPPER_SNAKE), target_type, target_id, metadata{}, ip, timestamp}` (L17-28); 11 action types in the filter select (L30); admin-email text filter (L46-54).
- **Actions:** row click toggles a metadata JSON panel (L167-174 — note it re-reads from `mockLogs`, not `filtered`, so an expanded row can show an entry filtered out of the table); **CSV export** (L56-69) — the only "real" code on any admin page: builds CSV client-side from the *mock* array with proper quote-escaping (`"` → `""`), Blob + object URL + revoke. Exports fiction.
- **Backend mapping:** `GET /api/admin/audit-log?page&page_size&action` (api.py:372-413) returns `{logs: [{id:int, admin_id:uuid, action, target_type, target_id, ip, created_at}], total, page, page_size}`. Mismatches: `admin_id` (UUID) vs frontend `admin` (email string) — no join to User; **no `metadata` in the response** (the model has `metadata_` but the endpoint omits it, and `AuditLogItem` schema api.py:96-103 omits it too); action vocabulary differs (backend writes dotted lowercase `"user.block"`, `"ip.ban"`, `"ip.unban"`, `"user.unblock"` — api.py:165,187,251,270 — frontend filter list is UPPER_SNAKE `BLOCKED_USER`, `BANNED_IP`…, so even a wired filter would match nothing); no admin-email filter param exists server-side; frontend has **no pagination UI** (backend is paginated). Also `adminApi.auditLog` passes only `page`/`action` (api-client.ts:125-130).

### 4.7 `/admin/analytics` (analytics/page.tsx, 176 lines)
- Three tabs, all mock: **geo** — 9 countries with users/percentage/distribution bars (L6-16, computed totals L110); **tokens** — 6 tenants with used/quota bars + platform totals (L18-25, L123-151); **behavior** — 6 KPI cards with deltas (L27-34).
- **Backend mapping:** only `GET /api/admin/analytics/geo-distribution` (api.py:315-334) exists, returning `[{country, user_count}]` — no percentage, no country code; data source is `UserSession.country` (never written → `[]` forever). **No token-usage-by-tenant endpoint exists** (TokenUsage model unused by admin API); **no behavior-metrics endpoint exists** (no session-duration/messages-per-session/bounce/DAU/CTR anywhere in backend). The "TOKENS USED 4.8M / 12M" dashboard card similarly has no quota source. Roughly 80% of this page's data has no conceivable backend endpoint (task brief's "analytics endpoints shapes mismatched" confirmed and extended: shapes mismatch *and* coverage is ~20%).

### 4.8 `/admin/health` (health/page.tsx, 168 lines)
- **Data:** 8 hardcoded services incl. statuses "degraded" (Celery Worker 1240ms, OpenRouter LLM 2840ms) and "down" (Gemini Vision, with pulsing dot) (L17-26); summary cards derived from the hardcoded array (L42-44); 4 hardcoded incident rows (L125-129).
- **Actions:** REFRESH button → `setRefreshing(true); setTimeout(() => setRefreshing(false), 800)` (L37-40) — a **fake 800ms spinner** that changes nothing. This page actively *portrays* an outage ("Gemini Vision DOWN") that may not exist — worst kind of status theater for an ops console.
- **Backend mapping:** **none** — no `/health`, no per-service status, no uptime, no incidents endpoint anywhere in the FastAPI app (grep of main.py: no health/status routes). Backend's own admin dashboard HTML hits `/api/admin/analytics/active-users` (dashboard.html:273) which doesn't exist either (only `active-sessions`) — the backend has its own parallel mock-ish dashboard (Z11 rated it 3/10).

### 4.9 Cross-cutting observations
- Two disjoint admin systems exist in the product: this Next.js mock panel and the backend's own sqladmin (`/_admin` via admin_panel.py) + HTML dashboard — with the REST API in between. The frontend consumes none of the three.
- Consistent table/card chrome (win-title-bar, halftone overlay, brutalist borders) — visually coherent, mechanically empty. Empty states, loading skeletons, and error states are absent everywhere because nothing ever loads.

---

## 5. Hooks

### 5.1 `hooks/use-toast.ts` (194 lines) — shadcn/Radix system #1 of **three**
- Verbatim shadcn implementation: module-level `memoryState` + `listeners` + reducer (L77-141), `genId` counter (L28-33), `toast()` factory (L145-172), `useToast()` subscription hook (L174-192).
- Quirks inherited from upstream: `TOAST_REMOVE_DELAY = 1000000` (~16.7 **minutes**, L12) — toasts effectively never auto-dismiss; `TOAST_LIMIT = 1`; side effects inside the reducer's `DISMISS_TOAST` case (`addToRemoveQueue`, L93-104, flagged by the source's own comment); `useEffect` deps `[state]` (L185) re-subscribe on every state change.
- **Wiring:** consumed only by `components/ui/toaster.tsx` (L3,14), mounted globally in `app/layout.tsx:74`. **Zero call sites** for `toast(...)`/`useToast().toast` anywhere in the app (grep across `src/` → only toaster.tsx + the hook itself). Mounted, never fired.
- **Which of the two toast systems?** Both are mounted simultaneously: `layout.tsx:74-75` renders `<Toaster />` (Radix, this hook) *and* `<ToastContainer />` (components/site/toast.tsx — a **Zustand** store `useToastStore` with `toast.success/error/info/warning` helpers, 4s auto-dismiss, brutalist-styled). Neither is ever triggered (grep: no `toast.success|error|info|warning` calls outside its own file). A third library, `sonner`, sits unused in package.json:74. Three toast systems, zero notifications.

### 5.2 `hooks/use-debounce.ts` (19 lines) — correct, dead
- Textbook value-debounce: `useState` + `useEffect` timer, cleans up on change, default 300ms "per PDF spec" (L10-19). Implementation is sound (no leading edge, no cancel — fine for search).
- **Zero usages** (grep). The admin users/tenants search inputs and the audit-log email filter operate directly on `onChange` with no debounce — the one hook written for exactly this purpose is unused.

### 5.3 `hooks/use-mobile.ts` (19 lines) — correct, transitively dead
- `matchMedia("(max-width: 767px)")` + change listener, `undefined → false` coercion for SSR safety (L5-19). Standard shadcn pattern, correctly implemented.
- **Sole consumer:** `components/ui/sidebar.tsx` (L8,69) — the shadcn sidebar, which itself has **zero importers** (grep). So `useIsMobile` is transitively dead, while the admin layout's own `hidden md:block` sidebar (§3.1) leaves mobile admins with no navigation — the problem this hook's consumer would have solved.

---

## 6. Security Analysis

### 6.1 Token storage & XSS exposure
- **JWTs live in httpOnly cookies** (`zemest_auth`, `zemest_refresh`) set by the BFF (login/route.ts:29-45, register/route.ts:26-42, facebook/route.ts:36-52) — the right pattern; tokens are not readable by JS, so XSS cannot exfiltrate them directly. **No token ever touches localStorage/sessionStorage** (the auth-store has no persistence; nothing else stores tokens).
- Caveats: (a) the cookie is only obtainable via API calls no UI makes — so in practice no real sessions exist; (b) `api-client.ts` bypasses the BFF entirely, calling the backend cross-origin with `credentials: "include"` — cross-site cookies to `localhost:8000` won't carry the Next-origin cookie, and the backend wants a Bearer header anyway → the design accidentally avoids token-in-JS but by breakage, not by intent.

### 6.2 Cookie flags
- `zemest_auth`: `httpOnly: true`, `secure: NODE_ENV === "production"`, `sameSite: "lax"`, `path: "/"`, maxAge 24h/30d (login/route.ts:29-35). `zemest_refresh`: same flags, 7d (L37-45) — but never set (§1.5). Flags are correct for the happy path; `sameSite=lax` + POST-only BFF = reasonable CSRF posture; no explicit `__Host-` prefix (minor).

### 6.3 Role checks — client-side only, and there aren't any
- **Middleware checks cookie presence, not identity** (middleware.ts:34) and the superadmin branch is an empty comment block (L44-48). The `sb-access-token` legacy-name fallback means **any non-empty cookie value — hand-set, expired, or from the unrelated Supabase era — opens /admin**. No JWT decode, no `is_superadmin` verification, no expiry check anywhere in the frontend.
- The *real* authorization (Bearer JWT + `require_superadmin`, admin/api.py:35-41) exists only server-side and is never invoked by this frontend. Because the pages are mocks, the practical exposure today is limited to revealing the admin UI shell — but the architecture ships with zero client-side role enforcement, which will silently become "mock data swapped for real calls with no guard" if wiring lands.
- Contrast: backend sqladmin panel has its own cookie-session system (never re-validates adminship; secret = JWT_SECRET_KEY; https_only=False — Z11), so there are effectively **three uncoordinated auth systems** (BFF cookie, backend Bearer, sqladmin session).

### 6.4 Open redirect & redirect handling
- middleware.ts:38-40 builds the login URL from a fixed base and sets `redirect=pathname` — pathname is server-derived (`request.nextUrl.pathname`), not user input, so no open redirect *here*; but the param is dead (never read), so post-login return-to-page is also nonfunctional.
- Facebook OAuth `redirect_uri` is built from `request.nextUrl.origin` (facebook/route.ts:16,63) — not attacker-controllable in normal deployments. No other `window.location` assignments take user input (register/page.tsx:31 and auth-store.ts:31 are constant strings). **No open redirect vulnerabilities found** in scope.
- OAuth **CSRF**: the Facebook authorize URL carries no `state` parameter (facebook/route.ts:17,64) — login-CSRF possible if the flow ever worked; and it can't work because the callback route is missing (404).

### 6.5 Credential & sensitive-data handling
- Passwords transit as JSON bodies over the (assumed TLS) connection to same-origin BFF — fine. No password is logged, stored in state, or persisted client-side anywhere (grep-clean).
- Registration validation is client-side only (register/page.tsx:22-27) — the backend re-validates via Pydantic, so no server gap, but the fake "success" redirect means users believe accounts exist when none do.
- **Data fabrication as a security UX risk:** forgot-password claims an email was sent (no endpoint exists — a user with a compromised account has *no* recovery path while being told one exists); admin health page fabricates service outages; audit log/CSV exports fabricated compliance data. For a moderation SaaS, fake audit trails and fake status pages are a governance liability, not just a bug.

### 6.6 Threat summary
| # | Threat | Reality |
|---|---|---|
| 1 | XSS steals JWT | Mitigated by design (httpOnly cookies) — but no CSP/headers audit in scope (see P1/X1) |
| 2 | Forged admin access | **Trivial**: set any `sb-access-token`/`zemest_auth` cookie value → full admin UI (middleware.ts:34,44-48) |
| 3 | Non-superadmin reads admin data | Currently impossible (no data calls) — will become critical when wired |
| 4 | OAuth CSRF on FB login | Present (no `state`), flow currently dead at 404 callback |
| 5 | Session fixation/refresh | No refresh mechanism at all (phantom refresh_token); sessions hard-expire |
| 6 | Credential stuffing | No rate limiting on login (frontend has none; backend rate limiting dead per Z10) |

---

## 7. Issues / Risks Register (file:line)

**CRITICAL**
1. `middleware.ts:44-48` — empty superadmin gate: `/admin/*` protected only by cookie *presence*; comment defers to a client-side `/api/auth/me` check that has no BFF route and no caller.
2. `middleware.ts:34` — `sb-access-token` legacy-cookie fallback = forgeable bypass for `/dashboard` + `/admin` (any non-empty value).
3. `auth-page.tsx:116` — login form is `preventDefault()` no-op; the fully-implemented BFF login (login/route.ts) is unreachable from UI → **no user can actually sign in**.
4. `register/page.tsx:31` — fake registration: validates client-side then `window.location.href="/dashboard"` without calling `/api/auth/register`; middleware bounces to `/login`, `?redirect=` dropped (login/page.tsx has no searchParams) → silent failure loop.
5. `forgot-password/page.tsx:58` — fabricated "reset link sent" (L52); no reset endpoint exists in BFF or backend (auth.py exposes register/login/facebook/me only).
6. `api-client.ts:25-27,63,121-131` — direct-to-backend client with cookie credentials against a Bearer-only API (dependencies.py:5,12) → every `authApi`/`adminApi` call 401s and triggers hard redirect to `/login` (L38-43); the entire typed API layer is unusable as designed.
7. Entire admin area (8 pages) is hardcoded mock with zero network calls (grep: only react/next/lucide imports) — admin functionality is 100% nonfunctional.

**HIGH**
8. `facebook/route.ts:16,63` — OAuth redirect_uri `/api/auth/facebook/callback` has no route → 404; flow can never complete. Plus `:17,64` no `state` param (CSRF) and `:62` `demo_client_id` fallback.
9. `login/route.ts:23,37` / `register/route.ts:22,34` — `refresh_token` destructured but backend `TokenResponse` never returns it (schemas/auth.py:27-29) → `zemest_refresh` never set; no refresh endpoint exists → sessions hard-expire with no recovery.
10. `middleware.ts:39` — `redirect` param set but never consumed anywhere (grep: zero readers) → broken return-URL UX.
11. `admin/layout.tsx:101-106` — LOGOUT is `<Link href="/">`; doesn't call `/api/auth/logout` → cookies persist after "logout".
12. `admin/api.py:196-214` (backend) vs `ip-bans/page.tsx:6-13` — shape mismatch (`ip_or_cidr`/`created_at` vs `ip`/`banned_at`/`banned_by`/`hits`), compounded by backend DDL bug (is_active missing → 500s) and unenforced middleware — bans are triple-broken end-to-end (Z10).
13. `users/page.tsx:127-135` — view/block/unblock buttons have no onClick; block is the core admin action and the matching backend endpoints (admin/api.py:137,172) are uncallable; backend enforces BlockedUser nowhere (Z11).

**MEDIUM**
14. `admin/layout.tsx:36` — sidebar `hidden md:block` with no mobile drawer → no admin navigation <768px (useIsMobile exists but unused).
15. `auth-store.ts:22` / `ui-store.ts:22` — both stores have zero importers (grep-proven); no persistence, no hydration; `User.is_superadmin` has no backend source (schemas/auth.py:32-38).
16. Two toast systems mounted simultaneously (`layout.tsx:74-75`), zero call sites for either; `sonner` also installed (package.json:74) → three dead toast layers.
17. `use-debounce.ts` never used; admin search inputs un-debounced (users/page.tsx:58-64, tenants/page.tsx:56-62).
18. `use-mobile.ts` only consumed by unused shadcn sidebar (sidebar.tsx:8) — transitively dead.
19. `audit-log/page.tsx:171` — expanded metadata panel reads from `mockLogs` not `filtered`, can display entries excluded by filters; action-vocabulary mismatch vs backend (`BLOCKED_USER` vs `user.block`); no pagination UI.
20. `sessions/page.tsx:39-42` — revoke is local state only; no backend revoke endpoint exists; backend active-sessions shape (`user_id`, no status/email) incompatible with the table (admin/api.py:436-446); UserSession never written → endpoint eternally empty.
21. `health/page.tsx:37-40` — fake 800ms refresh spinner; fabricated outages ("Gemini Vision DOWN"); no backend health endpoint exists.
22. `analytics/page.tsx` — ~80% of displayed metrics have no backend endpoint; geo-distribution shape mismatch (`{country,user_count}` vs `{country,users,percentage,code}`).
23. `next-auth` (package.json:61), `next-intl` (:62), `@tanstack/react-query` (:50) installed with zero imports — dependency bloat signposting unfinished auth/i18n/data intentions.

**LOW**
24. `auth-page.tsx:128-129` — Terms/Privacy links are `href="#"`.
25. `auth-page.tsx:125,135` — Terms & Remember-me checkboxes uncontrolled/unused.
26. `ip-bans/page.tsx:29-43` — add-ban accepts any string (no IP/CIDR validation client-side; backend would 422).
27. `api/route.ts:4` — placeholder "Hello, world!" API root shipped in production routes.
28. `auth-store.ts:29` — logout fetch is fire-and-forget (no await/await error handling); race with `window.location` redirect (mostly moot — dead code).
29. `admin/page.tsx:95` — "VIEW FULL LOG" uses raw `<a>` instead of `<Link>` (full page reload; inconsistent with the rest of the layout).

---

## 8. Quality Ratings (per file, 1-10)

| File | Rating | Justification |
|---|---|---|
| `admin/layout.tsx` | **4/10** | Clean, accessible-enough nav with active states and consistent design language; but zero auth guard (the one job an admin layout has), logout that doesn't log out, no mobile nav, static "SUPERADMIN" badge = security cosplay. |
| `admin/page.tsx` | **3/10** | Polished stat cards and feed UI; 100% fabricated data, no loading/empty/error states, feed actions have no backend counterpart, token quota has no data source. Visual craft wasted on fiction. |
| `admin/analytics/page.tsx` | **3/10** | Nice tab UI, bar/distribution rendering with computed totals; ~80% of metrics have no conceivable backend source; geo shape mismatches the one endpoint that exists. |
| `admin/audit-log/page.tsx` | **4/10** | Best page of the set: filters, expandable rows, and a genuinely correct client-side CSV exporter (quote-escaping, object-URL cleanup) — but it exports mock data, has a filter/expand inconsistency (L171), no pagination, and vocabulary/shape total mismatch with the backend. |
| `admin/health/page.tsx` | **2/10** | Fabricated statuses incl. a fake "down" service and a fake refresh spinner on an ops page whose entire purpose is truth; no backend endpoint could serve it; harmless code, harmful semantics. |
| `admin/ip-bans/page.tsx` | **3/10** | Complete CRUD-feeling UI (add form, table, remove) that mutates only local state; no IP validation; shape mismatch with backend; backend itself 500s on the real paths (DDL bug) — the fiction papers over a triple-broken subsystem. |
| `admin/sessions/page.tsx` | **3/10** | Tabs, modal detail, revoke affordance — all local-state theater; backend table never written, no revoke endpoint, shape mismatch on every column that matters. |
| `admin/tenants/page.tsx` | **3/10** | 11-column table with sensible social-ID affordances and working client filters; zero backend data source, dead view button. |
| `admin/users/page.tsx` | **3/10** | Good table ergonomics (badges, filters, counts); dead action buttons for the core capability (block/unblock); no list endpoint exists to wire to. |
| `components/site/auth-page.tsx` | **3/10** | Beautiful, well-structured presentation component (props-driven modes, reusable Field); but as *auth* it is a shell — no-op submit, uncontrolled inputs, dead Google/SSO, decorative checkboxes, `#` links; register/forgot modes were forked into separate files instead of extending it. |
| `app/login/page.tsx` | **6/10** | Does its tiny job cleanly (server component, metadata, delegates to AuthPage); can't be blamed for the stub below it — but ignores `?redirect=`. |
| `app/register/page.tsx` | **3/10** | The only form with real validation (correct rules, inline errors, show/hide) — then throws the result away with a fake redirect; duplicated chrome instead of reusing AuthPage; dead social buttons. |
| `app/forgot-password/page.tsx` | **2/10** | Competent two-state UI whose success state is a lie about a security-critical flow; no endpoint exists to make it true. |
| `stores/auth-store.ts` | **3/10** | Idiomatic zustand v5, sensible shape, correct BFF-logout intent — but no persistence, no hydration, zero importers: dead code whose `loading:true` sentinel advertises an integration that never came. |
| `stores/ui-store.ts` | **3/10** | Tidy API (sidebar/theme/locale) for features that don't exist anywhere in the UI; zero importers; no persistence. |
| `hooks/use-toast.ts` | **5/10** | Faithful, working shadcn implementation (correct reducer/store/subscription mechanics); inherits upstream quirks (16.7-min remove delay, reducer side effects, `[state]` deps); mounted-but-never-fired; one of three overlapping toast systems. |
| `hooks/use-debounce.ts` | **6/10** | Correct, documented, minimal; unused. Quality of code high, value delivered zero. |
| `hooks/use-mobile.ts` | **6/10** | Correct SSR-safe matchMedia pattern; only consumer is itself dead code; the admin layout needed it and didn't use it. |

**Layer verdict (admin + auth): ~3/10.** Presentation engineering is consistently strong (design-system fidelity, accessible-ish tables, sensible component structure), but the layer has no working authentication path, no authorization, no data, no error/loading states, and several flows that actively lie to users (register success, reset email, service status, audit export). The gap between how real this looks and how real it is constitutes the primary risk of this codebase.

---

## 9. Recommendations (for X1/X2 synthesis)
1. Wire AuthPage submit → `POST /api/auth/login` (BFF) → honor `?redirect=` after success; call `/api/auth/register` from register page; delete or implement forgot-password (backend endpoint needed).
2. Replace middleware cookie-presence with signed-cookie verification (or move to next-auth, already installed); implement the superadmin branch with an actual JWT `is_superadmin` claim check; drop `sb-access-token`.
3. Build a BFF `/api/auth/me` that forwards the httpOnly cookie as a Bearer header to the backend (same forwarding needed for all `/api/admin/*` calls — the direct-to-backend `api-client.ts` pattern cannot work with HTTPBearer).
4. Backend: return `refresh_token` (or delete the dead refresh-cookie code); add user/tenant/health/session-revoke endpoints or cut those admin pages.
5. Delete dead code (both stores if unwired within a sprint, unused toast systems ×2, next-auth/next-intl/react-query if unused, placeholder api/route.ts); wire `useDebounce` into admin search; add a mobile admin drawer.
