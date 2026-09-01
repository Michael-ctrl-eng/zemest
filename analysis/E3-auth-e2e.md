# E3 — End-to-End Auth Flow Audit (Login / Register / Facebook / Session)

**Agent:** E3 (error-finder, read-only) · **Date:** 2026-09-01 · **Scope:** FastAPI :8000 `app/api/auth.py` + `app/services/auth_service.py` + `app/utils/security.py`, Next.js BFF `src/app/api/auth/*` + `/api/zemest/*` proxy, frontend `/login` `/register` `/get-started`, JWT lifecycle.

**Environment:** Next.js dev :3000 (running, untouched), uvicorn `app.main:app --host 0.0.0.0 --port 8000` (running, untouched), SQLite + in-memory rate limiter, persistent JWT secret (`repos/zemest/.jwt_secret`, 64 bytes, perms 600).

**Throwaway accounts created (allowed):** `e3test+1788224265@zemest.ai` (TestPass123), `e3test+weak1788224265@zemest.ai` (password "a" — deliberate weak-pw probe), `e3test+bff1788224414@zemest.ai` (TestPass123). Shared demo account `owner@cairo-sneakers.com` only received failed-login probes (no modification).

---

## 1. Test Matrix — Backend direct (:8000)

| # | Test | Expected | Actual | Verdict |
|---|------|----------|--------|---------|
| T1 | POST /api/auth/login happy (owner demo) | 200 + access_token | 200, 270ms, `{"access_token":…,"token_type":"bearer"}` | **PASS** |
| T2 | login wrong password | 401 | 401 `{"detail":"Invalid credentials"}` (513ms — bcrypt) | **PASS** |
| T3 | login unknown email | 401, same message as T2 | 401 `{"detail":"Invalid credentials"}` (6ms) | PASS (msg) / **FAIL** (timing oracle → F7) |
| T4 | login malformed JSON | 422 | 422 pydantic `json_invalid` detail | **PASS** |
| T5 | register happy (throwaway) | 200 + token | 200 + JWT (auto-login), 502ms | **PASS** |
| T6 | register duplicate email | 400 | 400 `{"detail":"Email already registered"}` | PASS (code) / **FAIL** (enumeration → F7) |
| T7 | register 1-char password `a` | 422/400 (policy) | **200 + valid token** | **FAIL** → F3 |
| T8 | register invalid email format | 422 | 422 `value is not a valid email address` | **PASS** |
| T9 | GET /api/auth/me, valid Bearer | 200 user | 200 `{id,name,email,fb_user_id,is_superadmin:false}` (is_superadmin passthrough live) | **PASS** |
| T10 | /me, no Authorization | 401 | 401 `Not authenticated` | **PASS** |
| T11 | /me, garbage token | 401 | 401 `Invalid or expired token` | **PASS** |
| T12 | /me, tampered signature (last char flipped) | 401 | 401 `Invalid or expired token` | **PASS** |
| T13 | /me, token forged with **default secret** `change-me-to-a-random-secret-key` | 401 | 401 `Invalid or expired token` | **PASS** (persistent .jwt_secret secret genuinely in use — old forgeable-token hole closed) |
| T14 | /me, expired token signed with real secret (exp −1h) | 401 | 401 `Invalid or expired token` | **PASS** |
| T15 | /me, `alg=none` token | 401 | 401 `Invalid or expired token` | **PASS** (algorithm pinning works) |
| T16 | POST /api/auth/facebook, fake token | 401 | 401 `Invalid Facebook token`, ~160–190ms — **real** Graph v21.0 call, not mock | **PASS** |
| T17 | facebook, missing field | 422 | 422 `Field required` | **PASS** |
| T18 | facebook, 6 rapid calls | rate limited? | 6× 401 — **no rate limit on this endpoint** | **FAIL** → F8 |
| R1 | register 429 trigger (4 calls > 3/min) | 429 + Retry-After | 429 `{"detail":"Rate limit exceeded","retry_after":60}`, `retry-after: 60` header | **PASS** |
| R2 | login 429 trigger (6 calls > 5/min) | 429 | 401×5 then 429 | **PASS** |

JWT payload (T1): `{"sub":"cf434f94-…","exp":…+86400,"iat":…}`, header `{"alg":"HS256","typ":"JWT"}` — 24h lifetime, required exp claim (decode pins algorithms + `require:["exp"]`).

Rate-limit nuance: 422 (body-parse) requests **don't consume quota** (validation runs before the limiter decorator) — see F13.

## 2. Test Matrix — BFF (:3000)

| # | Test | Expected | Actual | Verdict |
|---|------|----------|--------|---------|
| B1 | POST /api/auth/login happy | 200 + httpOnly cookie | 200; `Set-Cookie: zemest_auth=…; Path=/; Max-Age=86400; HttpOnly; SameSite=lax`; body `{success:true}` (no token in body/JS) | **PASS** |
| B2 | BFF login wrong password | 401 (parity) | 401 + backend detail `Invalid credentials` | **PASS** |
| B3 | BFF login unknown email | 401 (parity) | 401 same detail | **PASS** |
| B4 | BFF login **malformed JSON** | 422 (parity) | **500** `{"detail":"Network error — check your connection"}` | **FAIL** → F4 |
| B5 | BFF register happy (throwaway) | 200 + cookie | 200 + cookie (auto-login), HttpOnly/SameSite=lax/24h | **PASS** |
| B6 | BFF register duplicate | 400 (parity) | 400 `Email already registered` | **PASS** |
| B7 | BFF register malformed JSON | 422 (parity) | **500** same misleading message | **FAIL** → F4 |
| B8 | BFF register missing fields | 422 (parity) | 422 pydantic detail passthrough | **PASS** |
| M1 | GET /api/zemest/auth/me, valid cookie | 200 | 200 (cookie→Bearer conversion works) | **PASS** |
| M2 | same, tampered cookie | 401 (parity) | 401 `Invalid or expired token` | **PASS** |
| M3 | same, garbage cookie | 401 (parity) | 401 | **PASS** |
| M4 | BFF facebook POST fake token | 401 (parity) | 401 `Invalid Facebook token`, 216ms | **PASS** |
| M5 | POST /api/auth/logout | 200 + cookies cleared | 200; both zemest_auth & zemest_refresh expired to epoch | **PASS** (but see F9) |
| RL1 | 6 rapid BFF logins | 429 on 6th | 401×5 → 429; body `{"detail":"Rate limit exceeded","retry_after":60}` preserved | **PASS** |
| RL2 | 429 Retry-After header via BFF | forwarded | **dropped** — BFF re-serializes JSON only, no response headers copied | **FAIL** → F10 |
| X1 | /api/zemest/auth/login + spoofed `X-Forwarded-For` while 127.0.0.1 bucket is 429-limited | still 429 | **401** — limiter re-keyed to spoofed IP | **FAIL** → F2 |
| X2 | direct :8000 + spoofed XFF (control: no-XFF → 429) | 429 | **401**; backend.log shows client as `203.0.113.99:0` / `198.51.100.7:0` | **FAIL** → F2 |
| MW1 | /dashboard no cookie | redirect /login | 307 → `/login?redirect=%2Fdashboard` | **PASS** |
| MW2 | /dashboard + **garbage** cookie | gate on token validity | **200 HTML** — middleware checks cookie existence only | **FAIL** → F12 |
| MW3 | /admin + garbage cookie | superadmin gate | **200 HTML** (real gate is client-side /me + API 403) | **FAIL** → F12 |

## 3. Test Matrix — Frontend pages

| # | Test | Expected | Actual | Verdict |
|---|------|----------|--------|---------|
| F1 | GET /login | 200, form present, no error markers | 200 (64ms); "EMAIL/PASSWORD/Sign in" present; only benign `global-error` chunk refs in RSC payload | **PASS** |
| F2 | GET /register | 200, form present | 200 (807ms); FULL NAME/CONFIRM PASSWORD/Create account present | **PASS** |
| F3 | GET /get-started | 200 | 200 (39KB) | **PASS** |
| F4 | login form endpoint | POST /api/auth/login exists | exists & works (authApi.login → BFF route) | **PASS** |
| F5 | **register form endpoint** | POSTs to /api/auth/register | **`/register` page never calls any API** — client-side validation then `window.location.href="/dashboard"` → bounces to /login | **FAIL** → F1 |
| F6 | Facebook button | working OAuth | navigates to GET /api/auth/facebook → 307 → `facebook.com/v18.0/dialog/oauth?client_id=demo_client_id&redirect_uri=…/api/auth/facebook/callback` | **FAIL** → F6 |
| F7 | OAuth callback route | exists | `/api/auth/facebook/callback` → **404** | **FAIL** → F6 |
| F8 | /api/auth/me at :3000 | 200 | **404** (no such BFF route; the real path is /api/zemest/auth/me — works). 404 body is HTML, not JSON | **FAIL** → F12 (minor) |

## 4. Facebook flow — what is mock vs real

- **Backend `POST /api/auth/facebook` — REAL.** `login_with_facebook()` calls `https://graph.facebook.com/v21.0/me?fields=id,name,email&access_token=…` (live outbound call — fake token rejected with real Graph failure → 401). Valid token → finds/creates user by `fb_user_id`, issues our JWT. Gaps: no token audience/app-id validation (any valid FB user token from any app is accepted), no rate limit, no explicit httpx timeout, Graph network error would surface as 500.
- **BFF `POST /api/auth/facebook` — real passthrough** (401 parity confirmed).
- **BFF `GET /api/auth/facebook` (the "Continue with Facebook" button) — MOCK/BROKEN.** Redirects to the FB OAuth dialog with `client_id=demo_client_id` (fallback because `NEXT_PUBLIC_FB_APP_ID` is unset), Graph **v18.0** (backend uses v21.0), `redirect_uri` http:// (FB requires https), **no `state` parameter**, and the callback route it points at **does not exist** (404). The browser OAuth flow is a dead end; only the programmatic token-exchange path works.

## 5. Findings (severity, evidence, suggested fix — NOT implemented)

### HIGH

**F1 — /register page is a dead form (never registers anyone).**
Flow: frontend /register. `src/app/register/page.tsx` `handleSubmit` only runs client-side regex checks then `window.location.href = "/dashboard"` — no fetch to `/api/auth/register`, no account created, no cookie. User lands on /dashboard → middleware redirects to `/login?redirect=/dashboard` (no cookie). The *working* signup lives at `/get-started` (AuthPage mode="get-started"). Suggested fix: replace the standalone /register page with `<AuthPage mode="get-started" />` (or make it POST via `authApi.register`).

**F2 — Rate-limit bypass via spoofed X-Forwarded-For (login & register brute-forceable).**
Flow: BFF proxy → backend; also direct :8000 from loopback. Evidence: with the 127.0.0.1 login bucket hard-limited (all further no-XFF requests 429), `POST /api/zemest/auth/login` with `X-Forwarded-For: 203.0.113.99` returned **401** (fresh bucket); direct :8000 requests with XFF show up in `backend.log` as `203.0.113.99:0` / `198.51.100.7:0` — uvicorn's ProxyHeadersMiddleware (loopback is in the trust list) rewrites `request.client` to the attacker-supplied XFF value, and `get_rate_limit_key()` keys on it. The universal proxy `src/app/api/zemest/[...path]/route.ts` forwards *all* client headers (XFF included) to the backend, so a public attacker can rotate a random XFF per request → **unlimited password guessing** through `/api/zemest/auth/login|register` (the dedicated `/api/auth/*` BFF routes do not forward client headers and are not affected). Suggested fix: strip/overwrite `x-forwarded-for` in the proxy (or have the limiter key on a trusted header only the BFF sets, e.g. `x-real-ip` set by the BFF from the actual socket peer), and/or block `/api/zemest/auth/*` in the proxy so auth only goes through the dedicated routes.

**F3 — No server-side password policy.**
Flow: backend register. `RegisterRequest` has `password: str` with no constraints — a 1-char password `"a"` registered successfully (200 + valid token). Frontend `/get-started` enforces ≥8 chars + letter+number, but the /register page (F1) enforces nothing and the API is directly callable. Suggested fix: pydantic `Field(min_length=8, ...)` + complexity check in `register_user()`; ideally reject common/breached passwords.

### MEDIUM

**F4 — BFF status-code parity broken on malformed JSON: 422 → 500 + misleading message.**
Flow: BFF login & register. `POST /api/auth/login` with invalid JSON → backend would 422, but the BFF route's `await request.json()` throws first and the catch-all returns **500** `{"detail":"Network error — check your connection"}` — wrong code and a lie about the cause. Same for register and facebook routes. Suggested fix: wrap `request.json()` in its own try → return 400/422 `{"detail":"Invalid JSON body"}`.

**F5 — No refresh-token flow; "Remember me" is cosmetic; silent 24h logout.**
Flow: BFF login. Backend `TokenResponse` returns only `access_token` (24h). BFF reads `refresh_token` (always undefined → `zemest_refresh` cookie never set — dead code), and sets `zemest_auth` maxAge 24h, or **30 days** when "Remember me" is checked — a cookie that outlives its token by 6 days with no `/api/auth/refresh` endpoint and no refresh issuance anywhere (`create_refresh_token`/`verify_refresh_token`/denylist exist in `app/utils/security.py` but are unused). Result: remembered users are silently logged out after 24h. Suggested fix: issue a refresh token on login (7d, jti) + BFF `/api/auth/refresh` route that rotates `zemest_refresh`.

**F6 — Browser Facebook OAuth path is a mock/dead end.**
Flow: frontend → BFF GET. `client_id=demo_client_id` fallback (env unset), Graph v18.0 vs backend v21.0, http redirect_uri, no `state` param (OAuth CSRF), callback route missing (404). Suggested fix: implement `/api/auth/facebook/callback` (code→token exchange against v21.0, state validation), set `NEXT_PUBLIC_FB_APP_ID`, or hide the FB button until configured.

### MEDIUM-LOW

**F7 — User enumeration (two oracles).** (a) Register: 400 `Email already registered` reveals account existence. (b) Login timing: unknown email → **6ms** vs wrong password → **510ms** (bcrypt only runs when the user exists) — same body, different timing. Suggested fix: run bcrypt against a dummy hash for unknown emails; optionally normalize register to a generic "check your email" flow.

**F8 — /api/auth/facebook is not rate limited.** 6 rapid calls all processed (each triggers an outbound Graph request). Enables token brute-forcing and amplification of outbound calls. Suggested fix: `@_limiter.limit("5/minute")` on the endpoint.

**F9 — Logout is client-side only.** Cookie cleared but the access JWT stays valid ≤24h; the revocation denylist only covers (never-issued) refresh tokens. A stolen token is unrevocable until expiry. Suggested fix: short-lived access tokens + refresh rotation (ties into F5), or jti denylist for access tokens.

### LOW

**F10 — BFF drops `Retry-After` / `X-RateLimit-*` on 429.** Direct backend 429 has `retry-after: 60`; through `/api/auth/login` the header is lost (body still carries `retry_after`). UI shows "Rate limit exceeded" with no wait duration. Suggested fix: copy `retry-after` in the BFF error path.

**F11 — `X-RateLimit-Limit` header contains a Python object repr.** Direct 429 header: `x-ratelimit-limit: <slowapi.wrappers.Limit object at 0x7f16f61b22d0>` — garbage/leaky. Fix: `str(exc.limit.amount)` or drop the header.

**F12 — Middleware gate is cookie-presence-only; API 404s are HTML.** Any garbage `zemest_auth` cookie gets `/dashboard` and `/admin` server HTML (200); real enforcement is client-side + API 401/403 (data is protected, shells are not). Also `:3000/api/auth/me` → 404 **HTML** page (no such route; the working path is `/api/zemest/auth/me`). Suggested fix: validate JWT signature (not just existence) in middleware (jose in edge runtime or a lightweight check), return JSON 404 for unknown `/api/*`.

**F13 — 422 (invalid-body) requests bypass the rate-limit counter.** FastAPI body validation runs before the decorated endpoint (where the limiter lives) — unbounded malformed-body noise is free (does not enable credential guessing, only noise/DoS amplification). Suggested fix: move limiting to middleware (SlowAPIMiddleware is installed but the decorator-based check is what fires).

**F14 — `login_with_facebook` httpx client has no explicit timeout / no exception guard.** A Graph API network failure propagates as a 500. Default 5s timeout currently saves it from hanging. Suggested fix: `httpx.AsyncClient(timeout=5)` + try/except → 401/502.

**F15 (info) — FB token audience not validated.** Any valid FB *user* access token (from any app) is accepted; no `debug_token`/app_id check. Combined with auto-registration this lets anyone mint a Zemest account from any FB token.

**F16 (info) — No CSRF/origin checks on BFF auth POSTs.** Mitigated on HTTP by SameSite=lax cookies; on HTTPS the cookies become SameSite=None (needed for the iframe preview), which re-opens login/logout CSRF. Suggested fix: verify `Origin`/`Sec-Fetch-Site` on auth mutations.

## 6. What works well (verified)

- JWT core is solid: HS256 pinning (alg=none rejected), `exp` required, **persistent random secret** (forged-with-default-secret token rejected), tampered signature rejected, expired rejected; token never appears in URL or response body (httpOnly cookie only); cookie flags adapt to HTTP/HTTPS (lax→none+secure+partitioned).
- Login wrong-password vs unknown-email return identical bodies (message level).
- BFF error-status parity is correct for all *valid-JSON* error paths (401/400/422/429 pass through, never masked as 500).
- Cookie→Bearer conversion in the universal proxy works (M1/M2/M3); 401 parity maintained.
- Rate limiter is real (5/min login, 3/min register, 429 with Retry-After direct + JSON body preserved through BFF) and no longer 500s on dead Redis.
- Backend responses carry a full security-header set (CSP, nosniff, frame-ancestors none, referrer-policy…).
- /api/auth/me now returns is_superadmin (Task 19 fix confirmed live).
- Facebook backend token exchange is genuinely real (live Graph v21.0 validation, fake tokens rejected).

## 7. Score

**35 PASS / 16 findings** (3 HIGH: dead /register page, XFF rate-limit bypass, no server-side password policy; 3 MEDIUM: BFF 500-on-bad-JSON parity break, missing refresh flow, broken browser FB OAuth; 3 MED-LOW; 7 LOW/INFO). Core JWT + cookie architecture is sound; the holes are in the flows around it.
