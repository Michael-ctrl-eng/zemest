# Zemest — Master Fix List (Everything Found, Fixed & Remaining)

> Generated after live testing (real-user flows + active exploit testing) on 2026-08-28.
> Status legend: ✅ FIXED & VERIFIED LIVE · 🔧 FIXED, NEEDS PRODUCTION CHECK · ⏳ REMAINING

---

## PART 1 — CRITICAL SECURITY (proven by live exploits, then fixed)

| # | Issue | Severity | Status | Proof → Fix |
|---|-------|----------|--------|-------------|
| S1 | **Forged JWT with compiled-in default secret** — anyone who reads the public GitHub repo could sign admin tokens and take over ANY tenant | CRITICAL | ✅ | Live: forged token got 200 on /api/tenants → set strong random `JWT_SECRET_KEY` in .env + boot guard refuses default secret in production |
| S2 | **9 unauthenticated dashboard HTML routes** exposing tenant data (chat, orders, customers) | CRITICAL | ✅ | Live: 3 routes returned 200 with no login → legacy Jinja frontend removed entirely (Next.js platform is now the only UI) |
| S3 | **SSRF via crawl + import-url** — `file://`, `localhost`, private IPs accepted and fetched | CRITICAL | ✅ | Live: `file:///etc/passwd` job accepted → wired the existing-but-dead `ssrf_protection.py` into both endpoints (400 "blocked scheme: file") |
| S4 | **No rate limit on login** — unlimited brute force | HIGH | ✅ | Live: 25 rapid logins, zero 429s → slowapi `5/minute` on login, `3/minute` on register → now returns 429 |
| S5 | **Hardcoded webhook verify token** `zemest-verify-token` in public repo | HIGH | ✅ | Live: old token accepted → generated random `FB_VERIFY_TOKEN`; old one now 403 |
| S6 | Webhook signature verification | — | ✅ | Was already constant-time HMAC (good, kept) |
| S7 | **sqladmin panel** at /_admin with demo creds pre-filled in old login page | HIGH | ✅ | Old Jinja login page (with admin@zemest.ai/test123 pre-filled) removed with the dashboard; sqladmin auth remains behind its own login |
| S8 | Stored XSS via `customer_name` in old dashboard templates (innerHTML + unsanitized marked.parse) | HIGH | ✅ | Old templates removed; new React UI escapes by default. ⏳ Backend should still escape on API output for defense-in-depth |
| S9 | FB access tokens transported in query strings (leak to logs) | MEDIUM | ⏳ | Move to POST bodies / headers in `facebook.py`, `scheduling.py` |
| S10 | Postiz client process-wide singleton → cross-tenant session hijack | CRITICAL | ⏳ | Blocked: Postiz sidecar not deployed. Per-tenant sessions required BEFORE ever enabling it |
| S11 | Caddy `XTransformPort` open proxy rule | HIGH | ⏳ | Platform not deployed with Caddy here; **delete that rule** in any real deployment |

## PART 2 — BROKEN FUNCTIONALITY (found as real user, then fixed)

| # | Issue | Status | Detail |
|---|-------|--------|--------|
| F1 | **Manual order creation ALWAYS 500** (MissingGreenlet: lazy `items` load after service commit) | ✅ | Live 500 → re-fetch with `selectinload` → now 201 with items |
| F2 | **Shipping quote ALWAYS 500** (`float()` wrapped a dict) | ✅ | Live 500 → returns full dict incl. `shipping_cost` → 200, Arabic message included |
| F3 | **AI chat took 8 SECONDS to fail** when no LLM key (4-model fallback chain × sleep(1)) | ✅ | 8000ms → **27ms** (fail-fast circuit breaker + pooled httpx client + snappy backoff) |
| F4 | New httpx client per LLM call (TLS handshake each time) | ✅ | Module-level pooled AsyncClient (20 conns / 10 keepalive) + closed on shutdown |
| F5 | `database.py` hardcoded `pool_size` breaks SQLite/tests | ✅ | Conditional pool args (SQLite → NullPool; Postgres → pool+pre_ping) |
| F6 | Frontend login/register forms were `preventDefault()` stubs | ✅ | Real auth → httpOnly cookie → dashboard |
| F7 | Frontend had ZERO wired data (100% mock: tenants, orders, products, chat, customers, conversations, crawl, settings, insights, admin) | ✅ | All 11 dashboard pages + tenant list now pull live data via BFF |
| F8 | Chat playground SIMULATED AI with setTimeout | ✅ | Real agent round-trip + live debug panel (conversation id, tokens, latency, LLM status) |
| F9 | Auth flow broken by construction (cookie set but never forwarded; backend HTTPBearer-only; no CORS) | ✅ | BFF proxy `/api/zemest/*` converts httpOnly cookie → `Authorization: Bearer` server-side; same-origin, zero CORS |
| F10 | Sidebar links rendered `/dashboard/undefined/*` (Next 16 Promise params bug) | ✅ | `use(params)` in layout + all pages |
| F11 | Settings SAVE buttons were no-ops | ✅ | GET loads real values → PATCH saves → success banner |
| F12 | Products page fake data | ✅ | Live list + real create round-trip (verified) |
| F13 | Order status changes were fake | ✅ | State machine enforced (pending→confirmed→shipped→delivered), illegal transitions blocked |
| F14 | Facebook OAuth dead-end (nonexistent callback + `demo_client_id`) | ⏳ | Needs real FB App ID (see API guide); callback route must be created |
| F15 | WhatsApp channel = facade (no onboarding, no webhook processing beyond stub) | ⏳ | Needs Meta WhatsApp Business API (see API guide) |
| F16 | Instagram onboarding missing | ⏳ | Same Meta app, IG messaging product |
| F17 | Style learning crashes on DYI ZIP import | ⏳ | Whole-file RAM read before 500MB check + parse crash — needs streaming + hardening |
| F18 | Knowledge base / PageIndex RAG missing from repo | ⏳ | Crawl works but embeddings pipeline absent |
| F19 | 3 admin analytics endpoints read never-written tables | ⏳ | `user_sessions` etc. never populated → always empty |
| F20 | Two UIs existed (backend Jinja + platform Next.js), zero shared sessions | ✅ | One platform now: Next.js only |

## PART 3 — SPEED (your #1 requirement)

| Metric | Before | After | How |
|--------|--------|-------|-----|
| AI chat failure path | ~8,000ms | **27ms** (300×) | Fail-fast + circuit breaker |
| AI chat success path | new client per call | **pooled** connections | Shared AsyncClient, no TLS handshake |
| LLM retry backoff | 4× sleep(1s) | 0.2–0.6s capped | Snappy backoff |
| API reads (products/tenants/stats) | — | **5–10ms** | Already fast; verified stable ×5 |
| Frontend pages | mock instant, no data | 200–320ms render | Parallel Promise.all fetches, no waterfall |
| BFF proxy overhead | — | ~1–3ms | Same-origin hop, no CORS preflight |

**Production speed todo:** Redis cache for insights (1h cache already coded in backend), CDN for static assets, Postgres connection pooler (pgbouncer) when scaling.

## PART 4 — REMAINING ROADMAP (priority order)

1. **P0 — before ANY real customer**: Set real `OPENROUTER_API_KEY` (agent replies live), rotate all secrets in production env, deploy Postgres+Redis via the existing docker-compose, delete Caddy proxy rule (S11)
2. **P1 — first pilot customers**: FB OAuth callback route (F14), webhook signature check stays, per-tenant Postiz sessions if you enable social scheduling (S10), token usage tracking wired to token_usage table (table exists, UI shows 0)
3. **P2 — scale**: WhatsApp Business onboarding (F15), IG (F16), style-learning hardening (F17), knowledge base RAG (F18), admin session tracking (F19), billing (marketing claims plans but no billing exists at all — Stripe/Paymob when ready)
4. **P3 — polish**: prompt-injection detector exists but unwired (wire into agent pipeline), remove dead code (llm_gateway.py, concurrency.py — never imported), unify LLM model config

---

## PART 5 — FRONTEND DESIGN REGRESSION (user-reported 2026-08-28, "colors/icons/type/animation became worst") — FIXED

| # | Issue | Severity | Status | Root cause → Fix |
|---|-------|----------|--------|------------------|
| D1 | **Entire Tavus design system dead** — every `var(--tavus-*)` resolved to empty string: no cream bg, no pastel palette, no blue CTAs, no halftone, transparent auth overlay (white-on-pink login) | CRITICAL | ✅ | **Turbopack stale-CSS cache**: dev server booted BEFORE platform src was copied; compiled globals.css kept old shadcn scaffold tokens with the whole tavus block stripped. Fix: `rm -rf .next` + restart → all tokens live. If you EVER see gray/colorless pages again: stop server, delete `.next`, restart. |
| D2 | Raw Tailwind status colors (bg-yellow-400/green-500/blue-500/red-600, text-green-700) clashing with palette in 6 dashboard files + pricing | HIGH | ✅ | Built shared kit `src/components/site/dash.tsx` — STATUS_STYLE map (Tavus palette only), all pages converted, raw colors grep-verified zero |
| D3 | Dashboard pages lost design identity (looked like default admin template) | HIGH | ✅ | All 11 pages converted to kit: WinCard OS-windows, StatTile big numbers, DashHeader serif+italic, hard shadows, halftone overlays |
| D4 | Dashboard LOGOUT was a dead link (never cleared cookie) | HIGH | ✅ | Real logout: POST /api/auth/logout clears zemest_auth → redirect home |
| D5 | Fake token-usage bar on tenant cards (hardcoded 0/100k) | MEDIUM | ✅ | Removed — honest live stats only (orders/revenue/chats/customers) |
| D6 | Pricing cards flat/empty, generic toggle look | MEDIUM | ✅ | Pale-yellow popular card (Tavus signature), dark enterprise card, coral CTA, signal-green save pill, serif tabular prices |
| D7 | Missing Tavus live-site accents | LOW | ✅ | Added tokens extracted from tavus.io Aug 2026: --tavus-coral-1/2/3 (#fb6182…), --tavus-signal-green/-2 (#1bd944/#0cb531) |

**Design QA (VLM vs tavus.io reference):** tenants 8.5 · overview 9.2 · orders 8.8 · products 8.8 · chat 8.7 · pricing 9.8 — all PASS.
**Speed after redesign:** pages 43–570ms · chat 96ms · orders PATCH 88ms · products POST 89ms.
**New rule:** `src/components/site/dash.tsx` is the ONLY place dashboard styling primitives live. Never inline a status color again — use `StatusBadge`.
**Known quirk:** if dev-server CSS ever goes stale again (Turbopack cache), stop server → `rm -rf .next` → restart. Content-hash watcher can miss adjacent-file changes.


## Task 10 fixes (Aug 29, 2026)
- **Sign-in "network error" root-fixed**: BFF now self-heals — `src/lib/backend-health.ts` auto-restarts the FastAPI daemon (single-flight, race-safe) and retries once. Verified by killing the backend: login still returns 200 in 2.8s.
- **Chat widget robustness**: 12s fetch timeout + 1 silent retry; typing indicator can never stick. Freeze reports were dev-server HMR churn (state resets) + slow next/image optimizer — product photos are now plain `<img>` from /public (always load).
- **Hero headline illegibility bug**: `--tavus-neon-field-2` is a dark-gray token (was near-black text on indigo bg) → headline now `--tavus-signal-green` (rgb(27,217,68)).
- **Greeting false-positive**: "hi" substring in "this"/"white" triggered greeting path → word-boundary regex `_GREETING_RE`.
- **Rooster rename**: Rat v1 → Rooster v1 across models.tsx, models/page.tsx, products.tsx, products/page.tsx, pricing, footer, layout metadata. Rabbit v1 icon → lucide `Rabbit`; Rooster icon → custom `rooster-icon.tsx` (Fluent Emoji High Contrast, MIT).
