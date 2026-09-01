# E2 — Next.js BFF Route Audit (error-finding, read-only)

**Task ID:** E2 · **Agent:** E2 (error-finder) · **Mode:** read-only — no code modified, no restarts, backend left running.
**Scope:** every route under `src/app/api/**` **except** auth-route internals (`/api/auth/login|register|logout|facebook`) already deep-audited by E3 (cross-referenced where relevant), plus the BFF helper contracts in `src/lib/backend-health.ts` (`fetchWithHeal`) and `src/lib/zemest-api.ts`.
**Stack under test:** Next.js dev server :3000 → FastAPI :8000 (SQLite, no Redis, in-memory slowapi fallback).

---

## 1. Route inventory (glob `src/app/api/**/route.ts` → 9 files / 10 routes)

| # | File | Methods | Path | Backend endpoint called | Auth handling | Error handling |
|---|------|---------|------|--------------------------|---------------|----------------|
| 1 | `src/app/api/route.ts` | GET | `/api` | none — static `{"message":"Hello, world!"}` | public | n/a (POST → 405, HEAD → 200) |
| 2 | `src/app/api/auth/login/route.ts` | POST | `/api/auth/login` | `POST ${BACKEND_URL}/api/auth/login` | public, sets httpOnly `zemest_auth` | **E3-covered** (500 on malformed JSON; Retry-After dropped on 429) |
| 3 | `src/app/api/auth/register/route.ts` | POST | `/api/auth/register` | `POST ${BACKEND_URL}/api/auth/register` | public, sets cookie | **E3-covered** |
| 4 | `src/app/api/auth/logout/route.ts` | POST | `/api/auth/logout` | none — client-side cookie clear only | cookie | **E3-covered** |
| 5 | `src/app/api/auth/facebook/route.ts` | GET, POST | `/api/auth/facebook` | POST → `POST ${BACKEND_URL}/api/auth/facebook`; GET → 307 redirect to FB dialog (demo_client_id) | public | **E3-covered** (OAuth dead end) |
| 6 | `src/app/api/zemest/[...path]/route.ts` | GET, POST, PATCH, PUT, DELETE (OPTIONS auto 204, **HEAD → 405**) | `/api/zemest/*` | `${BACKEND_URL}/api/<path>` — universal proxy for ~90 backend endpoints | reads `zemest_auth` cookie → `Authorization: Bearer …`; client `Authorization` passed through when no cookie; **cookie overwrites client header** | status/statusText/headers/body streamed back verbatim (hop-by-hop + `set-cookie` stripped, `Cache-Control: no-store` forced); network error → heal+retry once → 502 JSON |
| 7 | `src/app/api/calendar/[token]/route.ts` | GET (HEAD auto 200) | `/api/calendar/{token}` | `GET ${BACKEND_URL}/api/calendar/{token}/calendar.ics` | public by design — token-in-path IS the auth; token validated `^[A-Za-z0-9_-]+$`, len ≤ 128 → else 404 | backend non-OK → same status + fixed text "Invalid calendar token"; network error → 502 "Calendar unavailable" |
| 8 | `src/app/api/demo/chat/route.ts` | POST (GET → 405) | `/api/demo/chat` | `POST ${BACKEND_URL}/api/demo/chat` | public (backend slowapi 30/min per IP; forwards client `X-Forwarded-For`/`X-Real-IP`) | status+body passthrough; **rebuilds headers (drops `retry-after`)**; 15s timeout; network error → 502 fallback JSON |
| 9 | `src/app/api/demo/welcome/route.ts` | POST | `/api/demo/welcome` | `POST ${BACKEND_URL}/api/demo/welcome` | public (10/min per IP) | status+body passthrough; 15s timeout; network error → **HTTP 200** canned fallback JSON |
| 10 | `src/middleware.ts` (context) | — | — | — | `/api/*` explicitly public (line 13); cookie gate only for `/dashboard`, `/admin` pages | — |

`BACKEND_URL` resolution: `ZEMEST_BACKEND_URL || NEXT_PUBLIC_API_URL || "http://localhost:8000"` in routes 6–8; **auth routes 2/3/5 use only `NEXT_PUBLIC_API_URL || "http://localhost:8000"`** (inconsistent, see F9). No `.env` defines either var in the sandbox (`.env` only sets `DATABASE_URL`).

Backend ground truth: `openapi.json` on :8000 enumerates all proxied paths — every path `zemest-api.ts` builds exists (verified 1:1, §4).

---

## 2. Live test matrix (all through :3000, cookie captured via one demo login)

**Auth/permissions**
| Test | Result |
|---|---|
| Login (single attempt) → cookie | 200, `zemest_auth` httpOnly JWT captured |
| `GET /api/zemest/auth/me` (cookie) | 200 — cookie→Bearer wiring works |
| No-auth `GET /api/zemest/tenants` / `…/stats` / `/admin/analytics/overview` | 401 `{"detail":"Not authenticated"}` — clean passthrough, no crash |
| Tampered cookie `eyJ…fake.sig` | 401 `{"detail":"Invalid or expired token"}` |
| Non-superadmin cookie → `/api/zemest/admin/analytics/overview` | 403 `{"detail":"Superadmin access required"}` |
| No cookie + raw valid Bearer header | 200 (header passthrough works) |
| Valid cookie + **garbage** Bearer header | 200 — **cookie wins** (proxy overwrites `Authorization`) |
| `OPTIONS /api/zemest/tenants` | 204 (Next auto) |
| `HEAD /api/zemest/tenants` | **405** (see F7); `HEAD /api` and `HEAD /api/calendar/{token}` → 200 |

**Malformed/empty bodies — the E3-bug-pattern check**
| Test | Result |
|---|---|
| `{bad json` → `/api/demo/welcome` | 422 (backend JSON-decode error passthrough) — **not 500** |
| `{bad json` → `/api/demo/chat` | 422 — not 500 |
| `{bad json` → `/api/zemest/demo/chat` (proxy, no auth) | 422 |
| `{bad json` → `/api/zemest/tenants/{id}/orders` (authed) | 422 |
| Empty body → `/api/demo/welcome` | 422 "Field required" |
| Missing `session_id` | 422 with field path |
| Empty-body POST + `Content-Type: application/json` (exact `calendarApi.rotate` client pattern) → `/api/zemest/tenants/{id}/calendar/token` | 200, token rotated |
| No `Content-Type` → `/api/demo/chat` | 200 (BFF hardcodes JSON content-type outbound) |
| `{}` → `/schedule/post`; bad platform `"telegram"` | 422 with field errors / custom detail |

> **E3's "BFF 500 on malformed JSON" bug is confined to the auth routes.** Every other BFF route passes bodies through verbatim and returns the backend's 422. No shared bug pattern.

**Wiring / 404 / status propagation**
| Test | Result |
|---|---|
| `GET /api/zemest/bogus-nonexistent` | 404 `{"detail":"Not Found"}` (backend passthrough) |
| `GET /api/zemest/tenants/notauuid` | 422 uuid_parsing detail |
| `GET /api/zemest/tenants/` (trailing slash) | 200 (empty segments filtered — no FastAPI 307 loop) |
| Fake messenger token → `POST …/channels/messenger` | **400 `{"detail":"OAuthException 190: Invalid OAuth access token data."}`** — real Meta error propagates, nothing stored |
| `DELETE …/channels/messenger` (not connected, no-op) | 200; unknown platform `telegram` → 404 |
| All domain GETs authed: `stats, products, orders, customers, conversations (+detail: 6 messages), crawl/jobs, insights/overview, schedule/posts, channels, calendar/url, style-profile` | 200 each; **field names match `zemest-api.ts` interfaces 1:1** (`{products,total,page,page_size}`, `{orders,…}`, `{conversations,total}`, channels `webhook_urls` relative + frontend prepends `origin` — correct) |

**Calendar**
| Test | Result |
|---|---|
| Valid token | 200 `text/calendar; charset=utf-8`, valid VCALENDAR |
| Unknown-but-valid-format token | 404 |
| Invalid chars (`bad%21token%24`) / 130-char token / `..%2f..%2fadmin` | 404 (BFF validation holds; no traversal) |
| After rotate: old token → 404, new token → 200 (rotation invalidation works end-to-end) | ✔ |

**Rate limiting through the BFF**
| Test | Result |
|---|---|
| 31 rapid `POST /api/zemest/demo/chat` with `X-Forwarded-For: 203.0.113.99` | 200 ×30 → **429 on #31** — limiter keyed on the **spoofed** header (uvicorn ProxyHeaders rewrites `request.client`) |
| 429 response via proxy | `retry-after: 60` **forwarded** ✔ (but junk header `x-ratelimit-limit: <slowapi.wrappers.Limit object at 0x7f16…>` — F11) |
| 429 via `/api/demo/chat` wrapper | body `{"detail":"Rate limit exceeded","retry_after":60}` but **HTTP `retry-after` header dropped** (F3) |
| 11 rapid `/api/demo/welcome` (10/min) | 429 on #11 ✔ |

---

## 3. Findings (severity, evidence, suggested fix — NOT implemented)

### F1 — HIGH (shared with E3-#2, extends to all proxied routes): X-Forwarded-For spoofing defeats every per-IP rate limit
- **Where:** `src/app/api/zemest/[...path]/route.ts` (forwards all non-hop-by-hop client headers incl. `x-forwarded-for`); backend uvicorn ProxyHeaders trusts loopback XFF → slowapi keys on the attacker's value.
- **Evidence:** my 31-burst with `XFF: 203.0.113.99` produced exactly 30×200 + 429 — the fake IP became the rate-limit key. Rotating the header per request = unlimited keys. Applies to login/register (brute force — E3 HIGH) **and** demo endpoints.
- **Fix:** in the proxy, overwrite (not forward) `x-forwarded-for` with the trusted value Next knows (`request.headers.get('x-forwarded-for')` from the real edge, or drop it and let uvicorn see the proxy IP), or configure uvicorn `--proxy-headers --forwarded-allow-ips` to trust only the real edge.

### F2 — MEDIUM: `fetchWithHeal` re-sends non-idempotent POSTs after a timeout → duplicate submissions
- **Where:** `src/lib/backend-health.ts:82-93` — `signal: init.signal ?? AbortSignal.timeout(30_000)` is evaluated **per attempt**, so the proxy (which passes no signal) gets a fresh 30s budget on retry; a slow-but-alive backend (LLM endpoints: `/test/chat`, `/test/postiz-chat`, `/schedule/generate-caption`, crawl) that trips attempt 1's timeout is re-POSTed in full.
- **Impact:** duplicate orders / scheduled posts / conversations / channel connects; worst-case BFF latency ≈ 30s + heal-ping + 30s ≈ 61.5s while the browser client already aborted at its own 30s (`zemest-api.ts:81`) — the BFF keeps double-submitting after the user gave up.
- **Fix:** retry only idempotent methods (GET/HEAD/DELETE?) or only when the failure is connection-refused (request never reached the backend), never on timeout; cap total attempt budget; respect a propagated idempotency key.

### F3 — LOW/MED: `/api/demo/*` drop the `Retry-After` header on 429
- **Where:** `src/app/api/demo/chat/route.ts:27-37` and `welcome/route.ts:26-30` rebuild response headers from scratch (`Content-Type` + `Cache-Control` only).
- **Evidence:** 429 via `/api/demo/chat` has no `retry-after` header (body does carry `retry_after: 60`). Same defect class E3 found on the auth routes. The `/api/zemest/*` proxy **does** forward it (`retry-after: 60` observed).
- **Fix:** copy `retry-after` (and `x-ratelimit-*`) from the backend response in the demo wrappers, or route demo traffic through the proxy.

### F4 — LOW: `/api/demo/welcome` returns **HTTP 200** with a canned fallback when the backend is down
- **Where:** `src/app/api/demo/welcome/route.ts:31-40` (catch → 200). Deliberate "widget never dead-ends" UX, but it masks real outages — uptime monitoring and the frontend cannot distinguish healthy vs degraded. (Its sibling `/api/demo/chat` correctly returns 502.)
- **Fix:** keep the friendly body but return 502/503, or add a header/degraded flag.

### F5 — LOW: calendar route mislabels backend failures as "Invalid calendar token"
- **Where:** `src/app/api/calendar/[token]/route.ts:31-33` — any non-OK backend status (incl. 500) gets the same 404-style text. Status code passes through, but the message lies for 5xx.
- **Fix:** distinguish `res.status === 404` (invalid token) from other statuses ("Calendar unavailable").

### F6 — LOW: heal-and-retry is dead code for demo routes on timeout failures
- **Where:** demo routes pass their own `signal: AbortSignal.timeout(15_000)`; `fetchWithHeal` reuses the **same (already-aborted) signal instance** on attempt 2 → instant rejection. Self-heal only works for connection-refused, not timeouts.
- **Fix:** create a fresh timeout per attempt in `fetchWithHeal` (while fixing F2's idempotency guard), or have callers pass a timeout duration instead of a signal.

### F7 — LOW: `HEAD` → 405 on `/api/zemest/*` and `/api/demo/chat`
- **Evidence:** `curl -X HEAD` → 405 on the catch-all proxy (and demo/chat, which exports POST only), while `/api` and `/api/calendar/{token}` serve HEAD 200. Uptime monitors that default to HEAD will read the whole BFF API as "down".
- **Fix:** export a HEAD handler (or rely on Next's auto-HEAD for non-catch-all routes) — low priority, but note for observability tooling.

### F8 — LOW: `authApi.login` / `authApi.register` in `zemest-api.ts` have no timeout
- **Where:** `src/lib/zemest-api.ts:566-591` — raw `fetch` with no `signal` (every other request is bounded at 30s). A wedged Next/BFF leg = infinite spinner on the login form.
- **Fix:** add `AbortSignal.timeout(30_000)` like `request()`.

### F9 — LOW: inconsistent / browser-exposed env contract for `BACKEND_URL`
- **Where:** auth routes (login/register/facebook) resolve `NEXT_PUBLIC_API_URL || "http://localhost:8000"` only; other routes prefer `ZEMEST_BACKEND_URL` first. If both are set, auth traffic and proxy traffic can target **different** backends. `NEXT_PUBLIC_API_URL` is embedded in client bundles — setting it to a public URL (normal in prod) silently retargets **server-side** BFF fetches away from the internal backend and breaks `backend-health.ts` self-heal (`REPO` is also hardcoded to `/home/z/my-project/repos/zemest`).
- **Fix:** single server-only resolution (`ZEMEST_BACKEND_URL` with localhost default) in one shared module; never read `NEXT_PUBLIC_*` for server fetches.

### F10 — INFO: dead duplicate API client `src/lib/api-client.ts` is an import landmine
- Direct browser → `:8000` with `credentials: "include"` while the backend is Bearer-only **and** has no CORS middleware — any future import breaks (401/CORS) despite "compiling fine". Zero imports found today (all pages use `@/lib/zemest-api`).
- **Fix:** delete the file.

### F11 — INFO (backend, visible through BFF): junk `x-ratelimit-limit` header on 429
- **Evidence:** live 429 response carries `x-ratelimit-limit: <slowapi.wrappers.Limit object at 0x7f16f5d8d430>` — Python object repr leaking from slowapi header emission; the proxy faithfully forwards it to browsers.
- **Fix (backend):** disable/format slowapi's rate-limit headers or stringify properly.

### F12 — INFO: instant cache (`peek`) has no TTL and any mutation nukes the whole cache
- `zemest-api.ts` cache: `peek()` returns sessionStorage entries for the life of the tab; only components that also call `api.get` revalidate. Any POST/PATCH/DELETE clears **every** cached GET (correct but shotgun). Cosmetic/design note, not an error path.

### Positive confirmations (explicitly verified — no bug)
- **Malformed JSON never 500s** on any non-auth BFF route (422 passthrough everywhere) — E3's auth-route bug does **not** generalize.
- Status/headers/body propagation is faithful through the proxy: 400/401/403/404/422/429 all observed with correct payloads; streaming `res.body` (no double serialization); `retry-after` forwarded by the proxy.
- **Zero field-name drift**: every path built by `zemest-api.ts` exists on the backend (openapi cross-check + live calls); response shapes match the TS interfaces (`products/orders/customers/conversations(+messages)/channels/schedule posts/calendar token/stats/insights`).
- Cookie→Bearer forwarding incl. precedence and tampered-cookie rejection works; empty-body POST (the `calendarApi.rotate` pattern) works; trailing-slash and double-slash segments are cleaned (no 307 loop); `%2f` traversal blocked by calendar token validation.
- Backend 4xx with **real upstream errors** (Meta `OAuthException 190`) propagate verbatim — no error swallowing.

---

## 4. Coverage note
- `/api/zemest/*` was exercised against 15 distinct backend endpoints + 8 negative paths; the remaining proxied endpoints (postiz, products CRUD, orders status/payment/notes, import, admin mutations) share the exact same proxy code path and were validated at the wiring level via openapi cross-check (all client-built paths exist; auth/security flags match expectations: all `AUTH` except demo/welcome/calendar/webhook/oauth-url/can-register/health).
- Backend-down behavior (502 fallbacks, self-heal) was assessed **by code only** — the constraint forbade stopping the backend to force it.
- Auth BFF routes were intentionally not re-tested in depth (E3, `analysis/E3-auth-e2e.md`).

**Totals: 9 route files audited, ~55 live probes, 12 findings (1 HIGH shared, 1 MEDIUM, 6 LOW, 4 INFO) + 12 positive confirmations.**
