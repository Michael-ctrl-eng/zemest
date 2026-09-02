# R1 — OAuth / Social-Login Library Research (Meta ecosystem: Facebook Login, Instagram, WhatsApp Business)

**Agent:** R1 (github-research) · **Task ID:** R1 · **Mode:** research only — no code changed, no git commands.

**Scope:** libraries usable from BOTH the Next.js BFF (TypeScript, `src/app/api/auth/*`) and the FastAPI backend (`repos/zemest/app/`). Focus: server-side Facebook Login OAuth with **long-lived page tokens**, Meta business account linking, token refresh, CSRF state.

**Already adopted (do not re-recommend):** ARQ, Tenacity, LiteLLM, Uptime-Kuma, slowapi. Auth stack already in place: HS256 JWT (`utils/security.py`), httpOnly `zemest_auth`/`zemest_refresh` cookies set by BFF, Bearer-only FastAPI (`dependencies.py`), httpx for all Graph calls.

---

## 1. Grounded current state (verified in code, not assumed)

| Piece | Where | State |
|---|---|---|
| Browser OAuth start | `src/app/api/auth/facebook/route.ts` GET | **Dead end**: falls back to `demo_client_id`, dialog pinned to **v18.0**, no `state` param, redirect to `/api/auth/facebook/callback` which **does not exist** (404, confirmed by E3 audit) |
| Token exchange (POST) | same route → `POST /api/auth/facebook` → `auth_service.py` | **Real**: short-lived token validated against Graph, exchanged for our JWT |
| Backend consent URL | `app/api/channels.py` `GET /oauth-url` | Real scopes (pages_show_list, pages_messaging, pages_manage_metadata, pages_read_engagement, pages_manage_posts, instagram_basic, instagram_manage_messages, business_management), Graph **v21.0**, redirect to BFF `/api/zemest/facebook/oauth/callback` — **route doesn't exist**; `state` is `"tenant:{id}"` = **guessable, not a CSRF nonce, never verified** |
| Page discovery / webhook subscribe | `facebook_service.py` (`/me/accounts`, `/subscribed_apps`) | Real, working (proven live in Task 18) |
| Long-lived token exchange (`fb_exchange_token`) | — | **Missing entirely** — no code path anywhere |
| Token refresh / re-validation | — | **Missing** (only per-call re-validation in `channels.py` status checks) |
| Env | `config.py` FB_APP_ID/FB_APP_SECRET exist; BFF uses `NEXT_PUBLIC_FB_APP_ID` | App secret must never live in NEXT_PUBLIC_*, and client-side app ID fallback must die |

**Gap = the browser leg of OAuth (start + callback + state) and the token-lifecycle layer (short→long-lived exchange, page-token harvesting, refresh).** No library in this report replaces our JWT/cookie stack — we only need to fill those two gaps.

---

## 2. Ranked picks (max 5)

### #1 — Arctic ⭐ ADOPT NOW (TypeScript side — the BFF browser leg)

- **Repo:** https://github.com/pilcrowonpaper/arctic (canonical; task brief said "lucialabs" — `lucialabs/arctic` 404s, author is pilcrow, docs at arcticjs.dev)
- **Stars:** 1,717 · **Last push:** 2026-08-08 · **License:** MIT · **Open issues:** 0
- **Maintenance:** healthy (npm `arctic@3.7.0`, published 2025-05-21; author is the Lucia author, now focused on auth tooling)
- **What it solves for us:** ~60-line, zero-magic OAuth 2.0 client per provider. `new Facebook(clientId, clientSecret, redirectURI)` gives `createAuthorizationURL(state, scopes)` and `validateAuthorizationCode(code)` — exactly the two primitives the BFF lacks. **Caller owns state** (we generate the nonce, bind it to tenant + httpOnly cookie — the correct CSRF design, unlike next-auth's opaque cookie blob). Zero dependency tree, works in Next route handlers (fetch-based, no Node-only APIs). Same library covers Google/Apple later if we add SaaS social login.
- **Caveats (verified from source `v3/src/providers/facebook.ts`):** endpoints hardcoded to Graph **v16.0** (`dialog/oauth`, `oauth/access_token`) — works (Meta keeps old versions alive for years) but should be bumped to v21 to match the backend; trivial patch (vendored 60-line file or upstream PR). No PKCE for Facebook — correct, Meta's web-server flow doesn't support it; **state is the CSRF defense**, and arctic deliberately leaves it to us.
- **Integration sketch (files touched):**
  - `package.json`: + `arctic`
  - **NEW** `src/app/api/auth/facebook/start/route.ts` (GET): auth-cookie gate → `crypto.randomUUID`-based 32-byte state (+tenant id, HMAC-signed) → set httpOnly `fb_oauth_state` cookie (SameSite=Lax, 10 min) → 302 to arctic URL with channels.py's scope list
  - **NEW** `src/app/api/auth/facebook/callback/route.ts` (GET): compare state param vs cookie → `validateAuthorizationCode(code)` → forward code+tokens to new backend endpoint → set `zemest_auth`/`zemest_refresh` cookies → 302 to `/dashboard/{tenantId}/channels`
  - `src/app/api/auth/facebook/route.ts`: delete GET demo_client_id branch (keep the working POST token-exchange path)
  - `src/components/site/auth-page.tsx` + channels page: button → `/api/auth/facebook/start`
- **Verdict:** ✅ **Adopt now.** Smallest possible surface that closes the E3 HIGH finding "browser FB OAuth dead end".

### #2 — Authlib ⭐ ADOPT NOW (Python side — token lifecycle)

- **Repo:** https://github.com/authlib/authlib
- **Stars:** 5,408 · **Last push:** 2026-08-31 · **License:** BSD-3-Clause · **Open issues:** 142 (triaged, old ones)
- **Maintenance:** very healthy — **v1.8.0 released 2026-08-30** (2 days before this research). THE maintained Python OAuth/OIDC library.
- **What it solves for us:** `AsyncOAuth2Client` (httpx-based — **matches our async stack**; requests-oauthlib is the sync sibling and stale) handles token-endpoint POSTs with correct content-type/error handling, and — the key feature — **`fetch_token`/`update_token` hooks** designed for exactly our need: store token, refresh token automatically on expiry. Also ships `authlib.integrations.starlette_client.OAuth` (verified present in source) if we ever want FastAPI to own the whole redirect dance; we don't — BFF owns the browser, backend owns tokens. `debug_token`/token-introspection responses parse identically; authlib's error taxonomy maps Meta OAuthExceptions cleanly.
- **Caveats:** the Starlette client wants SessionMiddleware (signed cookie session) — skip that integration, use the raw `AsyncOAuth2Client`; Facebook issues **no refresh_token** (long-lived exchange is a bespoke `fb_exchange_token` grant authlib won't automate — we write 10 lines for it, hook it into the ARQ worker that already exists).
- **Integration sketch (files touched):**
  - `requirements.txt`: + `authlib>=1.8.0`
  - `app/services/facebook_service.py`: add `exchange_code()` and `exchange_long_lived()` using `AsyncOAuth2Client` (base Graph v21.0); keep existing `/me/accounts` page-token harvester (page tokens from a long-lived user token are **permanent** — the actual "long-lived page tokens" mechanism)
  - **NEW** `app/api/auth.py` or `channels.py`: `POST /api/auth/facebook/exchange` — receives code/tokens from BFF callback, runs: code→short user token → `fb_exchange_token`→60-day user token → `/me/accounts`→permanent page tokens → webhook subscribe → IG business link → store per-platform tokens on Tenant → return our JWT
  - `app/config.py`: keep FB_APP_ID/FB_APP_SECRET server-only; BFF gets them via backend, never `NEXT_PUBLIC_*`
  - `app/tasks/…` (ARQ/Celery worker): scheduled job = re-`fb_exchange_token` before 60d expiry + `/debug_token` revalidation per page token
- **Verdict:** ✅ **Adopt now** (server leg). Pairs 1:1 with arctic — arctic does browser redirect+code, authlib does server token lifecycle.

### #3 — next-auth / Auth.js v5 — VERDICT: SKIP for this goal, NEXT for SaaS-own social login

- **Repo:** https://github.com/nextauthjs/next-auth
- **Stars:** 28,355 · **Last push:** 2026-07-22 · **License:** ISC · **Open issues:** 600
- **Maintenance:** active repo, **but v5 has been `5.0.0-beta.32` for ~2 years** (npm dist-tags verified: `latest: 4.24.15`, `beta: 5.0.0-beta.32`); stable v4 is legacy-shaped for our App-Router BFF.
- **What it would give us:** full framework — cookie sessions, DB adapters, Facebook provider (confirmed re-exported in `next-auth@5.0.0-beta.32/providers/facebook` → `@auth/core/providers/facebook`).
- **Why not for THIS task:** (a) it **wants to own the session layer** — we already have a working, audited HS256-JWT + BFF-cookie stack (E3: 35 PASS on it); adopting next-auth means rewriting auth.py, auth-cookies.ts, middleware.ts for zero functional gain; (b) its Facebook provider is **user-login-shaped** (email/public_profile; business/page scopes need hand-rolled `authorization.params` anyway — at which point arctic is less code); (c) long-lived page tokens / business linking are out of its model entirely — those are Graph calls, not OAuth-framework calls; (d) beta-indefinitely on the core auth dependency of a multi-tenant SaaS is a risk we don't need.
- **Revisit trigger:** if we later want "Sign in with Google/Apple" for the *SaaS accounts themselves* (not channel linking) and want to outsource the whole session/adapter story.
- **Verdict:** ⏭️ **Skip now / next** — wrong shape (framework adoption vs 2 missing routes), beta status, replaces working code.

### #4 — facebook-python-business-sdk — VERDICT: NEXT (Graph/Business call layer, not OAuth)

- **Repo:** https://github.com/facebook/facebook-python-business-sdk
- **Stars:** 1,589 · **Last push:** 2026-08-25 · **License:** custom Meta license (API returns NOASSERTION — permissive for use, not OSI standard) · **Open issues:** 100
- **Maintenance:** Meta-maintained, actively pushed.
- **What it solves for us:** typed client for **Meta Marketing/Business APIs** — `FacebookAdsApi.init(app_id, app_secret, token)`, business management, catalog, Instagram publishing. Our future IG publishing (`scheduling/instagram_publisher.py`), WhatsApp Business onboarding, and `business_management` account linking would talk to exactly these endpoints.
- **Why not now:** it is **not an OAuth login library** — code→token exchange, state, CSRF are still ours; token-exchange grant (`fb_exchange_token`) is still a manual GET. Adding it now = a second HTTP layer next to our proven httpx Graph client (channels.py already does live validation fine). Custom license worth a skim before vendoring into a commercial SaaS.
- **Integration sketch (when adopted):** `requirements.txt` + `facebook-business`; refactor `scheduling/instagram_publisher.py` + `channels.py` IG/business-link calls onto `FacebookAdsApi`; keep httpx for login-leg.
- **Verdict:** ⏳ **Next** — pull it in when we build IG publishing/catalog/WhatsApp onboarding on top of the connected page tokens.

### #5 — pysnippet/fastapi-oauth2 — VERDICT: SKIP (pattern reference only)

- **Repo:** https://github.com/pysnippet/fastapi-oauth2
- **Stars:** 91 · **Last push:** 2026-07-12 · **License:** MIT · **Open issues:** 0
- **Maintenance:** active but **tiny adoption (91★)** — bus factor of one author.
- **What it is (README verified):** middleware-based social auth for FastAPI that **wraps python-social-auth/social-core backends**, stores tokens, ships its own router + `OAuth2Middleware`. A clean reference for "how to structure server-side social flows in FastAPI".
- **Why skip:** it would own middleware + token storage in the backend while our topology (BFF owns browser redirects) only needs the backend to accept a code and run Graph calls — authlib + arctic cover that with 2 mainstream-maintained deps instead of a 91★ wrapper. social-core itself (919★, BSD-3, pushed 2026-08-31) is healthy but Django/Flask-adapter-shaped; fastapi-oauth2 is its unofficial FastAPI shim.
- **Verdict:** ⏭️ **Skip** — read its middleware pattern when writing our `/exchange` endpoint, don't depend on it.

---

## 3. Explicit rejects (checked, with reasons)

| Library | Repo | Stars / last push | Reject reason |
|---|---|---|---|
| **Lucia** | lucia-auth/lucia | 10,452 / 2026-08-08 (docs-only) | **Officially deprecated March 2025** (README verified: "Lucia was deprecated on March 2025") — repo is now a learning resource; the author's own recommended path (small code, no magic) is exactly what arctic + our JWT stack already give us |
| **passport-facebook** | jaredhanson/passport-facebook | 1,308 / **2024-04-21** (>2y dead) | Unmaintained; Express middleware model doesn't fit Next route handlers or FastAPI; 130 open issues frozen |
| **requests-oauthlib** | requests/requests-oauthlib | 1,775 / 2025-06-18, last PyPI release **2.0.0 in 2024-03** | Stale >1y, **sync** (requests) vs our httpx/async stack; redundant — authlib's async client is the same project family, actively shipped |
| **python-social-auth/social-core** | python-social-auth/social-core | 919 / 2026-08-31 | Healthy but wrong shape: 100+ providers we don't need, Django/Flask adapter-first; no official FastAPI integration (only the 91★ shim above). Authlib is the direct fit |

---

## 4. Recommended architecture (arctic + authlib split)

```
Browser ──GET /api/auth/facebook/start (NEW, BFF)
   │  arctic.createAuthorizationURL(state, PAGE_SCOPES)   state = random32+tenant, HMAC'd, httpOnly cookie
   ▼
Meta dialog (v21.0, scopes from channels.py: pages_*, instagram_*, business_management)
   │
   ▼
GET /api/auth/facebook/callback (NEW, BFF)  — state cookie vs param, fail-closed mismatch
   │  arctic.validateAuthorizationCode(code) → short-lived user token (~1-2h)
   ▼
POST /api/auth/facebook/exchange (NEW, FastAPI, authlib AsyncOAuth2Client)
   1. code → short user token            (arctic did the POST, backend trusts BFF cookie)
   2. GET fb_exchange_token + app secret  → LONG-LIVED user token (~60d)   ← the missing piece
   3. GET /me/accounts                   → PERMANENT page access tokens    ← "long-lived page tokens"
   4. POST /{page}/subscribed_apps       → reuse facebook_service.py (already real)
   5. IG business link via business_management (channels.py pattern)
   6. persist tokens on Tenant (messenger_meta/instagram_meta/whatsapp_meta exist)
   7. issue zemest JWT → BFF sets zemest_auth cookies → 302 /dashboard/{id}/channels
```

**Token refresh (the part no library automates for Meta):** Facebook issues **no refresh tokens**. Long-lived *user* tokens (~60d) are re-extended via `fb_exchange_token` (idempotent, can be run daily); *page* tokens are permanent but must be re-validated (`/debug_token`) and re-harvested from `/me/accounts` when page roles change. This belongs in the **existing ARQ worker** as a scheduled job — no new daemon.

**CSRF:** Meta's web-server flow supports **no PKCE** — the defense is: random single-use state, HMAC-signed + tenant-bound, stored in httpOnly SameSite=Lax cookie, 10-min TTL, compare in callback before any code exchange. This fixes the current guessable `"tenant:{id}"` state in `channels.py:432` and the absent state in the BFF.

**Version hygiene:** pin BOTH the dialog and token endpoints to the backend's Graph **v21.0** (BFF currently v18.0, arctic ships v16.0 constants) — Meta deprecates old versions 2 years after release; v18 dialog dies 2026-10-22.

---

## 5. Sequencing (fits the existing roadmap)

1. **Phase 1 (this fix):** arctic (BFF start+callback) + authlib (backend `/exchange` w/ fb_exchange_token + `/me/accounts` page-token harvest). Files: 2 new BFF routes, 1 backend endpoint, facebook_service.py additions, delete demo_client_id branch. Env: FB_APP_ID/SECRET server-only.
2. **Phase 2:** ARQ job — 60d re-exchange + `/debug_token` revalidation + auto-reconnect flow on revocation (channels status endpoint already revalidates; extend it to self-heal).
3. **Phase 3 (next):** facebook-python-business-sdk for IG publishing / catalogs / WhatsApp Business onboarding on top of the stored page tokens.

## 6. Method / sources

- GitHub REST API (14 calls, ≤20 budget): direct `/repos` for nextauthjs/next-auth, pilcrowonpaper/arctic, lucia-auth/lucia, jaredhanson/passport-facebook, authlib/authlib, requests/requests-oauthlib, pysnippet/fastapi-oauth2, python-social-auth/social-core, facebook/facebook-python-business-sdk; 1 search (locate arctic — `lucialabs/arctic` and `lepture/authlib` are non-canonical 404s); `/readme` for lucia (deprecation notice). Raw source reads (free): arctic `v3/src/providers/facebook.ts`, authlib `integrations/starlette_client`, fastapi-oauth2 README, next-auth provider re-export. Version reality via npm/PyPI: next-auth dist-tags (beta 5.0.0-beta.32 vs latest 4.24.15), arctic 3.7.0 (2025-05-21), authlib 1.8.0 (2026-08-30), requests-oauthlib 2.0.0 (2024-03-22).
- Code grounding: `src/app/api/auth/facebook/route.ts`, `repos/zemest/app/api/channels.py` (`/oauth-url`, scopes, state), `app/services/facebook_service.py`, `app/config.py`, worklog Task 18/19 + E3 findings.
