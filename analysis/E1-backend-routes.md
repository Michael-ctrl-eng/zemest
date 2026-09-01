# E1 — Backend Routes Audit: Full Inventory + Live Smoke Test
**Agent:** E1 (error-finder, read-only) · **Date:** 2026-09-01 01:47 UTC · **Target:** FastAPI backend `http://127.0.0.1:8000` (daemon `running`, PID stable, untouched)
**Auth used:** owner `owner@cairo-sneakers.com` (JWT) + superadmin `admin@zemest.ai` (JWT). Login attempts spaced ≥ minutes apart; no unintended 429s hit.
**Scope guard:** findings already reported by E3 (auth flows/XFF bypass/429s), E5 (dashboard data shapes), E8 (DB schema/lifespan DDL), E10 (runtime/env/slowapi-import crash), Z4/Z5/Z11 (api-layer statics incl. postiz singleton + 500s, FB token-in-query), 18-b (pre-fix smoke) are **not re-reported**; where live-verified here they are listed in §7 as confirmations only.

---

## 1. Method
- Parsed `app/api/router.py` (17 routers registered) + each `app/api/*.py`, `app/admin/api.py`, `app/admin/dashboard.py`, `app/main.py` (root, mounts, sqladmin) → cross-checked against the **live** `/openapi.json` (92 routes).
- Live curl smoke: every GET (44/44, incl. negative paths w/ bogus UUIDs / wrong tokens), every safe POST (login, demo/chat, demo/welcome, test/chat, test/postiz-chat, webhook no-signature, bogus-platform channel negatives), response status + time captured.
- Destructive/mutating verbs (POST creates, PATCH, PUT, DELETE) not live-tested — marked in tables.
- Rate-limit probes spaced; one controlled 429 burst on the demo endpoint (11 rapid `POST /api/demo/welcome`) to confirm the limiter is armed.

**Totals: 92 OpenAPI routes (GET 44 · POST 34 · PATCH 7 · DELETE 6 · PUT 1) + ~11 non-schema routes/mounts + 9 DEAD routes (never registered). 66 paths live-tested: 63 pass, 3 fail (postiz external dependency down), 41 OpenAPI routes not live-tested (destructive or covered by E3).**

---

## 2. Route inventory + live results (auth = auth required & enforced; RL = rate limited)

### 2.1 auth.py — `/api/auth` (public)
| Method | Path | Auth | RL | Live test | Result |
|---|---|---|---|---|---|
| POST | `/api/auth/register` | none | **3/min/IP** | not live-tested (E3 covered; creates user) | — |
| POST | `/api/auth/login` | none | **5/min/IP** | ✅ 200 ×2 (owner 0.30 s bcrypt; superadmin 0.30 s) | PASS |
| POST | `/api/auth/facebook` | none | ✗ | not live-tested (E3: fake token → 401) | — |
| GET | `/api/auth/me` | JWT | ✗ | ✅ 200 (owner 5.3 ms; superadmin shows `is_superadmin:true`) | PASS |

### 2.2 tenants.py — `/api/tenants` (JWT; detail = JWT + ownership via `get_tenant`)
| Method | Path | Auth | RL | Live | Result |
|---|---|---|---|---|---|
| POST | `/api/tenants` | JWT | ✗ | not live-tested (mutation) | — |
| GET | `/api/tenants` | JWT | ✗ | ✅ 200 @5.2 ms | PASS |
| GET | `/api/tenants/{id}` | JWT+owner | ✗ | ✅ 200 @5.4 ms; bogus UUID → 404 `{"detail":"Tenant not found"}`; no-token → 401 | PASS |
| PATCH | `/api/tenants/{id}` | JWT+owner | ✗ | not live-tested | — |
| GET | `/api/tenants/{id}/stats` | JWT+owner | ✗ | ✅ 200 @12.9 ms | PASS |

### 2.3 products.py — `/api/tenants/{tid}/products` (all JWT+owner)
| Method | Path | RL | Live | Result |
|---|---|---|---|---|
| GET | `` (list) | ✗ | ✅ 200 @6.1 ms | PASS |
| POST | `` (create) | ✗ | not live-tested (mutation) | — |
| POST | `/upload-csv` | ✗ | not live-tested (500 MB body, mutation) | — |
| POST | `/import-url` | ✗ | not live-tested (mutation + fetch) | — |
| GET | `/{product_id}` | ✗ | ✅ 200 @6.4 ms (real id); bogus → 404 | PASS |
| PATCH | `/{product_id}` | ✗ | not live-tested | — |
| DELETE | `/{product_id}` | ✗ | not live-tested (destructive) | — |

### 2.4 orders.py — `/api/tenants/{tid}/orders` (all JWT+owner)
| Method | Path | RL | Live | Result |
|---|---|---|---|---|
| POST | `` | ✗ | not live-tested | — |
| GET | `` | ✗ | ✅ 200 @6.1 ms `{"orders":[],"total":0,"page":1,"page_size":20}` | PASS |
| GET | `/{order_id}` | ✗ | ✅ 404 bogus (0 orders in DB; 200 path not testable) | PASS (negative) |
| PATCH | `/{order_id}/status` | ✗ | not live-tested | — |
| PATCH | `/{order_id}/notes` | ✗ | not live-tested | — |
| POST | `/{order_id}/retry-api` | ✗ | not live-tested (external call) | — |
| PATCH | `/{order_id}/payment` | ✗ | not live-tested | — |

### 2.5 conversations.py / customers.py (all JWT+owner)
| Method | Path | RL | Live | Result |
|---|---|---|---|---|
| GET | `…/conversations` | ✗ | ✅ 200 @7.3 ms | PASS |
| GET | `…/conversations/{id}` | ✗ | ✅ 200 @10.2 ms (real); bogus → 404 | PASS |
| GET | `…/customers` | ✗ | ✅ 200 @8.3 ms | PASS |
| GET | `…/customers/{id}` | ✗ | ✅ 200 @13.4 ms (real); bogus → 404 | PASS |
| PATCH | `…/customers/{id}` | ✗ | not live-tested | — |

### 2.6 address.py — `/api/address` (**PUBLIC, no auth, no RL**)
| Method | Path | Live | Result |
|---|---|---|---|
| GET | `/governorates` | ✅ 200 @1.6 ms (27 entries, zones+costs) | PASS |
| GET | `/cities?governorate=…` | ✅ 200 — but `Cairo` → `[]`, `cairo` → `["القاهرة"]` | **BUG (F1)** |
| GET | `/areas?governorate=…` | ✅ 200 — same case sensitivity | **BUG (F1)** |
| GET | `/shipping?governorate=…&subtotal=…` | ✅ 200 — `cairo&subtotal=500` → free (cost 0, threshold 300); `Cairo&subtotal=500` → **cost 60, `free:false`** | **BUG (F1)** |
| GET | `/validate?governorate=…&city=…` | ✅ 200 — `Cairo` → `{"valid":false}`; `cairo` → true | **BUG (F1)** |

### 2.7 crawl.py — `…/crawl` (JWT+owner)
| Method | Path | Live | Result |
|---|---|---|---|
| POST | `` | not live-tested (spawns crawl job) | — |
| GET | `/jobs` | ✅ 200 @5.2 ms `[]` | PASS |
| GET | `/jobs/{job_id}` | ✅ 404 bogus (0 jobs; 200 path not testable) | PASS (negative) |

### 2.8 webhook.py — `/api/webhook` (public; Meta verify-token / HMAC signature — no JWT)
| Method | Path | Live | Result |
|---|---|---|---|
| GET | `/messenger` | ✅ 200 echoes `hub.challenge` with default token; wrong token → 403 | PASS |
| POST | `/messenger` | ✅ 403 `Invalid signature` (no `X-Hub-Signature-256`, fail-closed) | PASS |
| GET | `/instagram` | ✅ same | PASS |
| POST | `/instagram` | ✅ 403 fail-closed | PASS |
| GET | `/whatsapp` | ✅ same | PASS |
| POST | `/whatsapp` | ✅ 403 fail-closed | PASS |

### 2.9 facebook.py — `/api/facebook` (JWT; token via **query string** — Z5 finding, live 422 confirms required param)
| Method | Path | Live | Result |
|---|---|---|---|
| GET | `/pages?fb_access_token=…` | ✅ 422 without param (`{"detail":[…missing query fb_access_token…]}`) | PASS (validation) |
| POST | `/connect` | not live-tested | — |
| POST | `/{tenant_id}/sync-catalog` | not live-tested (external Graph call) | — |

### 2.10 test_chat.py — `/api/test` (JWT+owner)
| Method | Path | Live | Result |
|---|---|---|---|
| POST | `/chat` | ✅ 200 @0.90 s — real LLM reply, `tokens_used:1437` (LLM live post-Task-18) | PASS |
| POST | `/postiz-chat` | ✅ 200 — `"hello"` → `{"reply":null,"action":"unknown"}`; `"list my scheduled posts"` → real reply | **BUG (F5)** |

### 2.11 style_learning.py — `…/` (JWT+owner)
| Method | Path | Live | Result |
|---|---|---|---|
| POST | `/import/chat-history` | not live-tested (FK fix verified by Task 18) | — |
| GET | `/style-profile` | ✅ 200 @5.0 ms `{"status":"built",…}` | PASS |
| POST | `/rebuild-style` | not live-tested (heavy job) | — |

### 2.12 scheduling.py — `/api/tenants/{tid}` (JWT+owner)
| Method | Path | Live | Result |
|---|---|---|---|
| POST | `/schedule/post` | not live-tested | — |
| GET | `/schedule/posts` | ✅ 200 @5.9 ms `{"posts":[],"total":0}` | PASS |
| PATCH | `/schedule/posts/{id}/status` | not live-tested | — |
| DELETE | `/schedule/posts/{id}` | not live-tested | — |
| POST | `/schedule/generate-caption` | not live-tested (LLM cost) | — |
| GET | `/insights/overview` | ✅ 200 @4.7 ms | PASS |
| GET | `/insights/best-time` | ✅ 400 honest error "Instagram account not connected" | PASS (negative) |
| GET | `/insights/post/{post_id}` | ✅ 404 bogus (0 posts; 200 path not testable) | PASS (negative) |

### 2.13 postiz.py — `…/postiz` (JWT+owner, except 2 unauthenticated — Z5, live-confirmed)
| Method | Path | Live | Result |
|---|---|---|---|
| GET | `/health` | ✅ 200 @18 ms `{"healthy":false,"url":"http://localhost:4007/api"}` — **no token required** | PASS (Z5) |
| POST | `/login` | not live-tested (mutates global singleton — Z5 CRITICAL) | — |
| GET | `/can-register` | ✅ 200 `{"can_register":false}` — **no token required** | PASS (Z5) |
| GET | `/integrations` | ✅ 200 `{"integrations":[]}` (auth required) | PASS |
| POST | `/connect/{provider}` | not live-tested | — |
| POST | `/posts` | not live-tested | — |
| GET | `/posts` | ❌ **500** `{"detail":"Failed to fetch posts from Postiz"}` @6.4 ms | **FAIL (Postiz sidecar down — Z5 design; should be 503)** |
| GET | `/posts/{post_id}/stats` | ❌ **500** (bogus id, Postiz down) | FAIL (same) |
| DELETE | `/posts/{group_id}` | not live-tested | — |
| PUT | `/posts/{post_id}/reschedule` | not live-tested | — |
| GET | `/best-time` | ❌ **500** `{"detail":"Failed to find free slot in Postiz"}` | FAIL (same) |
| POST | `/generate` | not live-tested (LLM cost) | — |

### 2.14 demo_chat.py — `/api/demo` (**public, no auth**)
| Method | Path | RL | Live | Result |
|---|---|---|---|---|
| POST | `/chat` | **30/min/IP** | ✅ 200 @2.0 ms (rule-based reply) | PASS |
| POST | `/welcome` | **10/min/IP** | ✅ 200 @2.4 ms; 11th rapid call → **429** (limiter armed, in-memory) | PASS |

### 2.15 channels.py — `…/channels` (JWT+owner)
| Method | Path | Live | Result |
|---|---|---|---|
| GET | `` | ✅ 200 @4.5 ms (live token re-validation per platform) | PASS |
| POST | `/messenger` `/instagram` `/whatsapp` | not live-tested (connect = mutation + external Graph validation) | — |
| DELETE | `/{platform}` | ✅ bogus platform → 404 `{"detail":"Unknown platform 'telegram'"}` (safe negative) | PASS |
| POST | `/{platform}/test` | ✅ bogus platform → 404 (safe negative; real platform needs connection) | PASS |
| GET | `/oauth-url` | ✅ 200 `{"ready":false,"reason":"FB_APP_ID not configured…"}` | PASS |

### 2.16 calendar.py — `/api`
| Method | Path | Auth | Live | Result |
|---|---|---|---|---|
| POST | `/tenants/{tid}/calendar/token` | JWT+owner | not live-tested (rotates token, invalidates old URL) | — |
| GET | `/tenants/{tid}/calendar/url` | JWT+owner | ✅ 200 @4.3 ms (issues token on first call) | PASS |
| GET | `/api/calendar/{token}/calendar.ics` | **public token** | ✅ 200 @6.6 ms `text/calendar`, valid VCALENDAR; bogus token → 404 | PASS |

### 2.17 admin/api.py — `/api/admin` (**superadmin only**, verified RBAC)
| Method | Path | Live | Result |
|---|---|---|---|
| POST | `/users/{user_id}/block` | not live-tested (mutation) | — |
| DELETE | `/users/{user_id}/block` | not live-tested | — |
| GET | `/ip-bans` | ✅ 200 `[]` @7.8 ms | PASS |
| POST | `/ip-bans` | not live-tested (mutation) | — |
| DELETE | `/ip-bans/{ban_id}` | not live-tested | — |
| GET | `/analytics/overview` | ✅ 200 @9.7 ms (users 5, tenants 1, tokens 3294) | PASS |
| GET | `/analytics/geo-distribution` | ✅ 200 `[]` | PASS |
| GET | `/analytics/user/{user_id}/activity` | ✅ 200 `[]` | PASS |
| GET | `/audit-log` | ✅ 200 `{"logs":[],"total":0,"page":1,"page_size":50}` | PASS |
| GET | `/analytics/active-sessions` | ✅ 200 `[]` | PASS |
| — | *(all of the above)* with owner (non-superadmin) token | ✅ 403 `{"detail":"Superadmin access required"}` | PASS (RBAC) |

### 2.18 Non-schema routes (main.py / admin/dashboard.py / sqladmin)
| Method | Path | Auth | Live | Result |
|---|---|---|---|---|
| GET | `/` | public | ✅ 200 @1.5–2.0 ms `{"status":"ok","service":"zemest-api","version":"0.1.0"}` | PASS |
| GET | `/docs`, `/redoc`, `/openapi.json` | public | ✅ 200 all | PASS |
| GET | `/_admin/dashboard` | superadmin Bearer | ✅ 401 JSON w/o token; 200 HTML (12 071 B) w/ superadmin Bearer | PASS |
| GET | `/_admin/dashboard-login` | public | ✅ 302 → `/_admin/login` | PASS |
| GET | `/_admin/` (sqladmin mount) | session | ✅ 302 → `/_admin/login` | PASS |
| GET | `/_admin/login` | public | ✅ 200 HTML (2 485 B) | PASS |
| GET | `/static/*` (StaticFiles mount) | public | ✅ dir probe 404 (listing disabled) | PASS |
| GET | `/nonexistent-404-probe` | — | ✅ 404 (default JSON handler) | PASS |
| GET | `/api/tenants/` (trailing slash) | — | ✅ 307 → `/api/tenants` (FastAPI default) | PASS |

### 2.19 DEAD ROUTES — defined, never registered (404 live)
`app/api/dashboard.py` defines `dashboard_router` (prefix `/dashboard`, 9 unauthenticated Jinja HTML routes) but **`router.py` does not include it and nothing else imports it** (grep: zero references outside the file). `main.py:357` documents the removal ("legacy Jinja dashboard … was REMOVED") but the module + `dashboard/templates/*.html` + `dashboard/static/` remain.
- `GET /dashboard`, `GET /dashboard/login`, `GET /dashboard/{tenant_id}/{chat,products,orders,customers,conversations,crawl,settings}` → **404 live-verified**.

---

## 3. Findings (new; severity ordered — suggested fixes, NOT implemented)

### F1 · HIGH — `/api/address/*` governorate lookups are case/format-sensitive: "Cairo" silently charges the outside-Cairo rate (60 EGP instead of 35) and changes the response shape
**Where:** `app/api/address.py` → `app/utils/egypt_address.py` (`get_cities` L282, `get_areas_for_governorate` L291, `calculate_shipping` L299, `validate_egyptian_address` L343 — all do exact `GOVERNORATES.get(governorate)` / `in` on lowercase hyphenated keys).
**Live evidence:**
- `GET /api/address/shipping?governorate=Cairo&subtotal=500` → `{"cost":60,"free":false,"governorate":"Cairo","message":"شحن 60 جنيه","shipping_cost":60.0}` — Cairo is zone 1/35 EGP with free_threshold 300 (subtotal 500 should be **free**).
- `GET /api/address/shipping?governorate=cairo&subtotal=500` → `{"cost":0,"free":true,…,"governorate_ar":"القاهرة","free_threshold":300,"remaining":…}` — note the **miss-path response omits `governorate_ar`, `free_threshold`, `remaining`** entirely (shape drift on the same endpoint).
- `GET /api/address/cities?governorate=Cairo` → `[]` vs `governorate=cairo` → `["القاهرة"]`; same for `/areas`; `/validate?governorate=Cairo` → `{"valid":false}`.
- Keys are lowercase/hyphenated (`kafr-el-sheikh`, `port-said`), so any English/capitalized/space variant ("Port Said", "CAIRO", " Cairo ") fails; `detect_governorate_from_text()` (which DOES normalize) exists but is called by **nothing** (grep-verified).
**Impact:** silent mischarging (60 vs 35 / free-vs-paid), empty city/area dropdowns, false validation failures for any API consumer passing human input. Currently no TSX page calls `addressApi` (only `src/lib/zemest-api.ts:373` exposes it), so blast radius is API consumers today — but the contract is wrong.
**Suggested fix:** normalize in the 4 handlers (`governorate.lower().strip().replace(" ", "-")` + alias map of English names), return 404/400 on unknown governorate instead of silently billing `default_outside`, and make the miss path return the same keys.

### F2 · MEDIUM — Only 4 of 92 routes are rate-limited; every expensive LLM/crawler/import endpoint is unthrottled
**Evidence:** grep `\.limit(` across `app/`: only `POST /api/auth/register` (3/min), `POST /api/auth/login` (5/min), `POST /api/demo/chat` (30/min), `POST /api/demo/welcome` (10/min). Verified armed live (11th welcome in <1 s → 429).
Unthrottled expensive routes: `POST /api/test/chat` (0.9 s LLM round-trip, 1 437 tokens measured), `POST /api/test/postiz-chat`, `POST …/schedule/generate-caption`, `POST …/postiz/generate`, `POST …/import/chat-history` (up to 500 MB body per Z5), `POST …/rebuild-style`, `POST …/crawl`, `POST /api/facebook/{tid}/sync-catalog` (external Graph call), `POST /api/admin/*` mutations. All require auth (mitigation), but any single account (or stolen token) can burn the LLM budget / pin the event loop with zero throttle. (E3 already flagged the *unauthenticated* `/api/auth/facebook`; this is the fleet-wide picture.)
**Suggested fix:** add `@limiter.limit("10/minute")`-class decorators to the LLM/crawl/import/postiz mutations (limiter is already wired app-wide; opt-in is one line per route).

### F3 · LOW — List-endpoint envelope shapes are inconsistent (bare arrays vs `{items,total,page}` wrappers)
**Live evidence:** bare arrays — `GET /api/tenants`, `GET …/crawl/jobs` (`[]`), `GET /api/admin/ip-bans`, `GET …/postiz/integrations`, `GET /api/address/*`; envelopes — `{"products":…}`, `{"orders":…,"total","page","page_size"}`, `{"customers":…}`, `{"conversations":…}`, `{"posts":…,"total"}`, `{"logs":…,"total","page","page_size"}`. Frontend/BFF must special-case per endpoint; paginated vs non-paginated siblings in the same resource family (e.g. conversations list paginated, tenants list not).
**Suggested fix:** standardize on `{items, total, page, page_size}` for all collections (additive, backwards-compatible via a v2 or BFF mapping).

### F4 · LOW — Dead code: 9-route legacy dashboard router exists but is unreachable (and is an unauthenticated-HTML trap if ever re-registered)
**Where:** `app/api/dashboard.py` (`dashboard_router`, 9 routes incl. `/dashboard/login`, `/{tenant_id}/…` pages), zero importers; `dashboard/templates/*.html` (11 files) + `dashboard/static` still shipped via `/static` mount.
**Live:** `/dashboard`, `/dashboard/login` → 404. Intentional removal per `main.py:357`, but the module looks registerable — a future `include_router(dashboard_router)` would resurrect 9 unauthenticated HTML pages.
**Suggested fix:** delete `app/api/dashboard.py` + templates (or move to an `_legacy/` dir outside the import path).

### F5 · LOW — `POST /api/test/postiz-chat` returns HTTP 200 with `"reply": null` for non-postiz messages (null-reply contract leaks to the API surface)
**Live evidence:** `{"tenant_id":…,"message":"hello"}` → `200 {"reply":null,"action":"unknown","data":{}}` in 8 ms. `handle_postiz_chat_request()` intentionally returns `reply: None` as an internal "not handled" signal (`app/ai/postiz_chat.py:63-69`), but the route passes it straight through (no response_model, no fallback). `src/lib/api-client.ts:117` calls this endpoint; a client rendering `reply` shows an empty bubble.
**Suggested fix:** in the route, if `action == "unknown"` return a help/fallback reply (or 422) instead of surfacing the internal null sentinel.

### F6 · INFO — Bot-detection middleware: verified live as **log-only, never blocks** (task-question closure)
`app/middleware/bot_detection.py` has no blocking path at all: it sets `scope["is_likely_bot"]` and emits `logger.info("bot_detected ua=… ip=… method=… path=…")` only for flagged requests **without** an Authorization header. Live proof: 164 `bot_detected` lines in `backend.log`, every one of my 70+ curl requests (UA `curl/8.14.1`, mostly unauthenticated) was logged as a bot **and still served** (incl. the 429 burst — all 10 allowed calls completed). Nuance: the signature list is substring-based and includes `"whatsapp"` and `"bot"`, so any UA containing them (e.g. Meta's `WhatsApp/2.x` webhook agents) is tagged — harmless (INFO log volume only). No change needed unless log noise appears.

---

## 4. Rate limiting / 429 observations
- Configured (grep `@…limit(`): register 3/min, login 5/min, demo/chat 30/min, demo/welcome 10/min — all per-IP (in-memory store since Redis absent; slowapi fallback active).
- **Limiter verified armed:** 11 rapid `POST /api/demo/welcome` → 10×200 then **429** on the 11th. Intentional, functioning as designed → not a defect finding.
- No 429 encountered on auth routes (login attempts spaced; concurrent-agent friendly). E3's XFF-bypass caveat still applies (not re-tested).
- 88/92 routes carry no limiter at all → see F2.

## 5. Response-time summary (fresh DB, single user)
All authed GETs 4–19 ms; admin GETs 5–10 ms; `/` 1.5–2.0 ms; `POST /api/test/chat` 0.90 s (LLM round-trip, expected); `POST /api/auth/login` 0.30 s (bcrypt, expected); `POST /api/demo/*` ~2 ms. No slow-route finding at route level (Task 18-c owns perf).

## 6. Not live-tested (by policy) — 41 OpenAPI routes
All destructive/mutating verbs: tenant/product/order/customer PATCH+DELETE, creates (tenants, products ×3, orders, crawl, import, rebuild-style, generate-caption, schedule/post, postiz login/connect/posts/generate, admin block/ip-bans POST/DELETE, channels connect ×3, calendar/token rotation, retry-api, sync-catalog, facebook/connect, auth/register, auth/facebook (E3-covered). Safe negatives exercised instead where possible (bogus UUID → 404, bogus platform → 404, no-signature webhook → 403, no-token → 401, non-superadmin → 403).

## 7. Prior-agent findings live-confirmed here (NOT re-reported as new)
- postiz GET `/posts`, `/posts/{id}/stats`, `/best-time` → 500 when sidecar down (Z5 flagged "500s mask Postiz's real errors"; live: 3×500, health says `healthy:false`). Would be better as 503.
- postiz `/health` + `/can-register` reachable **without auth** under a tenant-scoped path (Z5; live-confirmed 200 no-token).
- FB access token required as **query param** on `GET /api/facebook/pages` (Z5; live 422 shape).
- `insights/overview` cannot distinguish not-connected vs empty (18-b; live `{"facebook":null,…}`).
- Conversations list omits `messages` (E5; live-confirmed).
- Webhook GET verify uses default `FB_VERIFY_TOKEN="zemest-verify-token"` and completes the handshake (E10 default-token guard gap; live-confirmed echo).
- `/docs`, `/redoc`, `/openapi.json` public (E10; live 200).

## 8. Deduplication notes
Checked `worklog.md` (Tasks 0/18/19, 18-a…e, E3/E5/E8/E10) + `analysis/Z4/Z5/Z11/18-b/18-e` before reporting. F1 (address case-sensitivity) is **not** present in any prior report (Z5:§229 calls address.py "static lookups"; E5 tested only `/governorates`; 18-b didn't test address sub-routes). F2's fleet-wide rate-limit gap, F3, F4, F5, F6 are likewise new at route level.
