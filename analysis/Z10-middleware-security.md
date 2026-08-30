# Z10 — Middleware & Security Deep Analysis (zemest backend)

Scope: `app/middleware/` (7 files) + `app/utils/{egypt_address,phone,security}.py` + both `__init__.py`.
Method: every line of every file read; all cross-references grep-verified; three bugs **proven by execution** (see §9).

A one-line summary of this layer: **it is a museum of well-documented, well-tested, and almost entirely disconnected security machinery.** Of the 7 middleware files, only 3 classes actually run (SecurityHeaders, BotDetection, IPBan), only 2 do anything observable (headers + logging), and every request-level *defense* (rate limit, IP ban, prompt injection, SSRF guard) is either unwired, broken, or both.

---

## 1. Middleware Inventory

Actual middleware onion (verified from `main.py:186-223` registration order; Starlette runs last-registered = outermost):

```
Request → SecurityHeadersMiddleware (pure ASGI)      [security_headers.py]
        → SlowAPIMiddleware (pure ASGI, no-op*)       [rate_limit.py → slowapi]
        → BotDetectionMiddleware (pure ASGI)          [bot_detection.py]
        → IPBanMiddleware (BaseHTTPMiddleware)        [security.py]
        → SessionMiddleware (Starlette, signed cookie)[main.py:191]
        → routes
```
\* no endpoint declares `@limiter.limit` and the `Limiter` has no `default_limits` → SlowAPI passes every request through untouched.
Note: `main.py:171-184` comment claims request flow `SecurityHeaders → BotDetection → IPBan → RateLimit → Session`; the real flow puts **RateLimit before BotDetection/IPBan** (confirms Z1's doc-vs-code mismatch).

### 1.1 `bot_detection.py` (138 LOC)
- **Class**: `BotDetectionMiddleware` — **pure ASGI** (`__init__(app)`, `async __call__(scope, receive, send)`).
- **Module function**: `is_likely_bot(user_agent: str | None) -> bool`.
- **Logic walkthrough**: `__call__` passes through non-HTTP scopes untouched. For HTTP scopes it scans `scope["headers"]` once (latin-1 decode, guarded by never-failing try/except) for `user-agent` and `authorization`. It computes `bot = is_likely_bot(ua)` via case-insensitive substring match against the 26-entry `BOT_USER_AGENTS` list, then stashes `scope["is_likely_bot"]` and `scope["bot_user_agent"]` directly on the ASGI scope (deliberately NOT `scope["state"]`, per comment). If `bot and not auth_header`, emits one `logger.info("bot_detected ua=… ip=… method=… path=…")` line. **Never blocks, never mutates the response.**
- **Config options**: none. **Storage**: none (stateless). **Bypass**: any UA avoiding the 26 substrings (trivial); auth'd requests never logged.
- **Performance**: one header pass + ≤26 C-level substring searches over the UA — single-digit microseconds; zero allocation pressure. Excellent.
- **Docstring rationale** (log-only because Meta webhooks legitimately use `facebookexternalua` and merchants use SDK clients) is honest and correct.

### 1.2 `prompt_injection.py` (101 LOC)
- **Class**: none — **not a middleware at all** despite living in `middleware/`. Pure function library.
- `detect_prompt_injection(text: str) -> tuple[bool, list[str]]`: iterates 25 precompiled regexes (`re.IGNORECASE | re.MULTILINE`) covering: direct override (`ignore/disregard/forget/override … previous|prior|above …`), DAN/jailbreak variants, system-prompt extraction, tag-spoofing (`[SYSTEM]`, `<system>`), role-prefix injection (`^(system|assistant|admin):`), role reset, and 5 Egyptian-Arabic variants (`تجاهل التعليمات`, `اهمل الأوامر`, `اطبع البرومبت`, `اعد ضبط الدور`, `تجاوز القيود`). Returns the matched *texts* (group(0)).
- `sanitize_user_input(text: str) -> str`: wraps input in `[USER INPUT START]` / `[USER INPUT END]` delimiters (defense by delimiting, keeps UX flowing).
- **Config**: none; patterns are a module constant. **Storage**: none.
- **Hook point**: **NOWHERE.** Grep proof: the only importers of `detect_prompt_injection`/`sanitize_user_input` in the entire repo are `tests/security/test_prompt_injection.py` and `tests/property/test_prompt_injection_property.py`. Neither `app/ai/agent.py` nor `app/api/webhook.py` nor `test_chat.py` ever calls them — customer text reaches the LLM **raw**.
- **Performance** (if it were wired): 25 regex searches per message — tens of µs; negligible.

### 1.3 `rate_limit.py` (158 LOC) — slowapi wrapper
- **Class**: none of its own; wires slowapi's `SlowAPIMiddleware` (pure ASGI).
- Functions:
  - `get_rate_limit_key(request: Request) -> str` — anonymous → `ip:{remote_address}`; `Bearer` token → best-effort `decode_token`, then `tenant:{tenant_id}` or `user:{sub}`; any failure → IP fallback. Key insight: **per-tenant key means all of a tenant's users+IPs share ONE bucket** (deliberate anti-IP-cycling design, but a self-DoS amplifier if limits ever get added).
  - `_build_limiter()` — `Limiter(key_func=get_rate_limit_key, storage_uri=settings.REDIS_URL or "memory://")`. Because `config.REDIS_URL` **defaults to** `redis://localhost:6379/0`, the documented "in-memory fallback if REDIS_URL unset" is unreachable in practice (memory:// only if env var is explicitly empty).
  - `get_limiter()` — lazy module-level singleton (`limiter: Limiter | None`).
  - `_rate_limit_handler(request, exc)` — 429 JSON with `Retry-After` (fallback 60s) + `X-RateLimit-Limit` — explicitly to keep Meta's webhook retry loop well-behaved.
  - `setup_rate_limiting(app)` — sets `app.state.limiter`, registers the exception handler, dedupes middleware registration by class name. Idempotent.
- **Algorithm**: whatever slowapi uses per decorated route (moving-window via the `limits` library) — **moot, since zero routes decorate** (grep: no `@limiter.limit` / `@rate_limit` anywhere; confirmed by Z4).
- **Storage backend**: Redis via `storage_uri` (would be shared across uvicorn workers); memory:// essentially never.
- **Bypass conditions**: N/A — nothing to bypass; the middleware enforces nothing without per-route decorators or `default_limits`.
- **Performance**: pure-ASGI pass-through ≈ 0 (a Redis RTT per limited request would only exist if limits existed).
- **Docstring defect**: "See `app/api/auth.py` for examples" — auth.py contains **no** limiter usage (Z4 flagged this too).

### 1.4 `rate_limiter.py` (75 LOC) — in-memory sliding window
- **Class**: `RateLimiter` (+ `_Bucket` dataclass holding `hits: list[float]`).
- `__init__(limit=5, window_seconds=60)` — validates `limit >= 1`, `window >= 1` (raises `ValueError`).
- `check(identifier) -> (allowed, remaining)` — empty identifier **fails open** (returns allowed); prunes hits older than `now - window` (`time.monotonic()`, correct clock choice); blocks when `len(hits) >= limit`; appends `now` only when allowed.
- `reset(identifier=None)` — clears one bucket or all.
- **Storage**: in-process `defaultdict(_Bucket)` — **not shared across workers, not persisted**; buckets are **never globally pruned** → unbounded memory growth keyed by attacker-controlled identifiers (DoS vector *if* it were ever wired).
- **Wired where**: **tests only** — `tests/security/conftest.py:28` (`isolated_rate_limiter` fixture) and `tests/security/test_rate_limiting.py`. Its own docstring admits "Not wired into the FastAPI app by default — it's a building block", and the integration tests for login throttling are marked `xfail(strict=False)` with the reason "Rate-limit middleware not yet installed on /api/auth/login". The test suite literally documents the absent defense.
- **Performance**: O(hits-in-window) list comprehension per check — fine for a primitive, irrelevant since unused.

### 1.5 `security.py` (355 LOC) — the grab-bag duplicate module
Everything in this file duplicates another module, usually in a weaker or divergent form:

| Item | In security.py | Canonical copy | Divergence |
|---|---|---|---|
| `is_safe_url(url)` / `safe_http_get` / `SSRFProtectionError` (l.41-113) | no redirect handling, no `allow_private` flag, returns "OK (IP literal)" early | `ssrf_protection.py` | weaker; unused |
| `PROMPT_INJECTION_PATTERNS` + `detect_prompt_injection` + `sanitize_user_input` (l.120-162) | 17 patterns, returns *pattern strings* as matches; over-broad (`r"system\s*:\s*"` matches any occurrence; `r"sudo\s+"`; `r"you\s+are\s+now\s+(a|an)\s+\w+"` matches innocuous text) | `prompt_injection.py` (25 patterns, returns matched text) | both unused; different return semantics for the same function name |
| `SecurityHeadersMiddleware` (l.169-184) | BaseHTTPMiddleware, 5 headers, no CSP/COOP/CORP | `security_headers.py` (8 headers + CSP) | **same class name in two modules** — import ambiguity; unused |
| `BOT_USER_AGENTS` + `is_likely_bot` + `BotDetectionMiddleware` (l.191-216) | 14 substrings; **empty/missing UA → `True`** (opposite of bot_detection.py) | `bot_detection.py` (26 substrings; empty UA → `False`) | same names, contradictory semantics; unused |
| `IPBanMiddleware` (l.223-277) | BaseHTTPMiddleware; `__init__(app, banned_ips=None, banned_cidrs=None)`; `ban_ip/ban_cidr/unban_ip/is_banned`; 403 JSON on ban | — | **the ONLY thing in this file that runs** (main.py:202) — but see §5 |
| `SimpleRateLimiter` + module singleton `_rate_limiter` + `rate_limit(limit, window)` decorator (l.284-354) | sliding window, `time.time()` wall clock, unbounded dict, decorator scans args for a `Request` | `rate_limiter.py` | decorator used by **zero** endpoints |

- `IPBanMiddleware.dispatch`: reads `request.client.host`, `is_banned()` → 403 `{"detail": "Access denied"}`. `is_banned` checks exact-IP set membership then every banned network via `ipaddress`. Correct logic — over an **always-empty** dataset (see §5).
- `rate_limit` decorator: extracts `Request` from args/kwargs, keys `"{path}:{ip}"`, returns 429 with `Retry-After`. Never imported by any endpoint.
- **Performance**: IPBanMiddleware is the only `BaseHTTPMiddleware` in the live stack → per-request anyio task + memory-stream plumbing (~50-200µs) plus the known BaseHTTPMiddleware edge cases (streaming/background-task interactions), for a check that can never trigger.

### 1.6 `security_headers.py` (122 LOC) — the best file in the layer
- **Class**: `SecurityHeadersMiddleware` — **pure ASGI**.
- `_is_https(scope)`: true if `scope["scheme"] == "https"` **or** first `X-Forwarded-Proto` value is `https`.
- `__call__`: wraps `send`; on `http.response.start` builds a lowercase set of existing header names and appends only missing headers (dedup — respects route-set headers). Static set (8 headers): `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `X-XSS-Protection` (legacy), **CSP** `default-src 'self'; img-src 'self' data: https:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy` (7 features denied), `Cross-Origin-Opener-Policy: same-origin`, `Cross-Origin-Resource-Policy: same-origin`. HSTS `max-age=31536000; includeSubDomains; preload` only when `_is_https`.
- **Config**: none (constants). **Storage**: none. **Bypass**: none needed — it's additive; but see M3 (X-Forwarded-Proto spoofing).
- **Performance**: one closure per request, 8 header appends — sub-microsecond. Textbook implementation.
- Notable: because it's outermost, even 429s/403s from inner middleware get the headers (per main.py comment — and that ordering is real).

### 1.7 `ssrf_protection.py` (214 LOC) — strong design, zero users
- `is_safe_url(url, *, allow_private=False) -> (bool, reason)` — never raises. Pipeline: non-empty str → `urlparse` → scheme ∈ {http, https} → host lowercased + trailing-dot stripped → exact-match `BLOCKED_HOSTS` (localhost, ip6-localhost, ip6-loopback, metadata.google.internal[.], "metadata", "169.254.169.254") → if literal IP: check 10 `BLOCKED_NETWORKS` (127/8, 10/8, 172.16/12, 192.168/16, 169.254/16, 0.0.0.0/8, 100.64/10 CGNAT, ::1/128, fc00::/7, fe80::/10) → else **DNS-resolve and check every address** (`socket.getaddrinfo`); DNS failure = unsafe (fail-closed). `allow_private=True` skips all network checks (local dev).
- `UnsafeURLError(ValueError)`.
- `SafeHTTPClient` — httpx wrapper: `__init__(*, timeout=30, connect_timeout=10, headers, max_redirects=10, allow_private=False)`; `_check()` raises on unsafe; `get()` validates the initial URL, **disables httpx auto-redirects, then manually follows up to max_redirects hops, re-validating every `Location` (resolved via `urljoin`) before fetching** — a genuine TOCTOU-redirect defense. Creates a new `httpx.AsyncClient` per `get()` call (no pooling — connection reuse lost).
- **Used by**: `tests/security/test_ssrf_protection.py` **only**. `app/` imports: **zero**. The crawl API (`api/crawl.py`), product import (`products/import-url`), and `knowledge/crawler.py` (Playwright/Katana) fetch user URLs with raw httpx/Playwright — confirming Z5's critical finding from the defense side.
- **Test coverage** (nice irony): the test file covers metadata endpoints, all RFC1918 ranges, CGNAT, `::1`, file/ftp/gopher/data/dict schemes, decimal (`2130706433`), octal (`0177.0.0.1`), hex (`0x7f000001`) IP encodings — decimal/octal/hex are caught because `getaddrinfo` resolves them to 127.0.0.1 which then hits the DNS-path block (verified by execution: `getaddrinfo('2130706433')` → `127.0.0.1`). What the tests do **not** cover: IPv4-mapped IPv6 — see §9 M2 (proven bypass).

### 1.8 `middleware/__init__.py` — one docstring line ("Make middleware package importable"). No re-exports.

---

## 2. Bot Detection (deep-dive)

- **Heuristics**: case-insensitive **substring** matching (not equality — versioned UAs like `curl/8.4.0` still match) over `BOT_USER_AGENTS` (26 entries): generic tools (`scrapy`, `curl`, `wget`, `python-requests`, `python-httpx`, `httpx/`, `aiohttp`, `go-http-client`, `java/`, `okhttp`), generic words (`bot`, `crawler`, `spider`, `scraper`), headless (`headlesschrome`, `phantomjs`, `selenium`), known crawlers incl. `facebookexternalua`, `whatsapp`, `telegrambot`, `googlebot`, `bingbot`, `baiduspider`, `yandexbot`, `applebot`, `twitterbot`, `linkedinbot`, `slackbot`, `discordbot`.
- **Headers used**: `User-Agent` (detection), `Authorization` (log gating). Nothing else — no header-ordering, TLS-fingerprinting, or behavioral analysis.
- **Action taken**: **log-only** (`logger.info`), never 403. Deliberate (docstring explains Meta webhooks + merchant SDKs would break under blocking). Flags on scope for downstream use — **but grep confirms nothing in the app ever reads `scope["is_likely_bot"]`/`scope["bot_user_agent"]`**; the "stricter rate-limit policy for bots" the flag enables doesn't exist.
- **Weaknesses**: (a) generic substrings `bot`/`headless` over-match benign UAs (e.g. anything containing "…bot…" or "Bottom"); (b) every Meta webhook delivery is logged as a bot (`facebookexternalua`) → log noise at webhook volume, not signal; (c) detection is trivially spoofable, which is fine for logging but would be useless as a gate.
- **The duplicate** in `security.py` (14 patterns, logs even authenticated traffic, treats **missing UA as bot**) is dead code but a semantic landmine (same function name, opposite empty-UA behavior).

## 3. Prompt Injection Middleware (deep-dive)

- **Detection patterns**: 25 regexes (list above, §1.2), English + 5 Egyptian-Arabic variants, compiled once at import. No scoring/weighting — any single match = flagged; returns all matched snippets. No censoring/rewriting — caller decides.
- **Where it hooks**: **nowhere in the live pipeline.** Webhook → `agent.process_customer_message` → `prompts.build_*` embeds the raw customer message; `/api/test/chat` likewise. The `sanitize_user_input` delimiters are never applied. Both were built, documented, and tested in isolation (`tests/security/test_prompt_injection.py` unit-tests the detector; its two "end-to-end" tests **mock `process_customer_message` with a canned safe reply** — they assert the mock doesn't leak, i.e. they test nothing about production).
- **Bypasses possible even if wired**: homoglyph substitution (е vs e), zero-width characters, diacritics (Arabic tatweel/kashida), leetspeak, translation to a third language, indirect phrasing ("it would be helpful if the assistant's rules were…"), or role-play framing — none handled because there is no Unicode normalization (`unicodedata.NFKC`) or de-obfuscation before matching. Regex blacklists are inherently a speed bump, not a wall; the delimiter-wrapping helper is the more robust half of the design and it's equally unwired. Second-order injection via crawled product/knowledge text embedded into the system prompt (Z2) is completely outside this guard's model even conceptually.
- **Duplication**: `security.py` ships a second, divergent detector (17 patterns, returns pattern-source not match-text, several over-broad patterns like `system\s*:\s*` and `sudo\s+`) — also dead.

## 4. Rate Limiting (both files)

| Aspect | `rate_limit.py` (slowapi) | `rate_limiter.py` (RateLimiter) | `security.py` (SimpleRateLimiter + `@rate_limit`) |
|---|---|---|---|
| Algorithm | slowapi/limits moving window (per decorated route) | sliding window (timestamp list per key) | sliding window (timestamp list per key) |
| Backend | Redis (`storage_uri=REDIS_URL`); `memory://` unreachable in practice (REDIS_URL has a default) | in-process dict | in-process dict |
| Key | `tenant:{id}` if valid Bearer JWT, else `user:{sub}`, else `ip:{addr}` | caller-chosen identifier | `{request.path}:{client_ip}` |
| Clock | limits lib | `time.monotonic()` ✓ | `time.time()` (wall clock) |
| Multi-worker safe | yes (Redis) — if used | no | no |
| Limits configured | **none** (no decorators, no `default_limits`) | none (constructor arg, tests use 5/60s) | none |
| Users | `main.py:212-213` (wires middleware; enforcement no-op) | tests only | **nobody** |

**Why endpoints don't use it**: there is no technical blocker — `setup_rate_limiting` is correctly wired at boot, `get_rate_limit_key` is a genuinely good key function, and the 429 handler even emits `Retry-After` for Meta's webhook retry loop. The decorators were simply never added to any of the 79 endpoints (Z4 grep-verified; re-verified here), no `default_limits` were set, and the two hand-rolled fallback limiters were never wired. `/api/auth/login` (credential stuffing), the webhook verify endpoints, and all unauthenticated dashboard routes run unthrottled, and the test suite's own `xfail` tests acknowledge it. Three generations of limiter code exist (slowapi wrapper, RateLimiter primitive, SimpleRateLimiter+decorator) — classic "build the mechanism, defer the policy" drift.

## 5. Security Middleware + Headers + Session/IP-ban

**Headers** (live, from `security_headers.py`): see §1.6. Evaluation: CSP is genuinely restrictive for a Jinja dashboard (`script-src 'self'`, no `unsafe-eval`, `frame-ancestors 'none'`, `base-uri 'self'`); concessions: `style-src 'unsafe-inline'` (inline Jinja styles), `img-src https:` (any remote image → tracking-pixel exfil channel). Missing: no `Cache-Control: no-store` on API responses, deprecated `X-XSS-Protection` retained (harmless but flagged by scanners). Duplicate weaker `SecurityHeadersMiddleware` in `security.py` is unused.

**HSTS**: emitted only on HTTPS-detected requests; detection trusts client-suppliable `X-Forwarded-Proto` (no `--proxy-headers` on uvicorn in compose, no trusted-proxy validation) — an attacker can force HSTS onto plain-HTTP responses by spoofing the header (minor, mostly self-inflicted DoS risk). "preload" claim without domain-control verification is aspirational.

**Session management**: `SessionMiddleware` (`main.py:191-197`) with `secret_key=settings.JWT_SECRET_KEY` (**the same secret as JWTs**, and the default is `"change-me-to-a-random-secret-key"`, config.py:21 — forgeable session cookies in default deployments), cookie `_zemest_session`, `same_site=lax`, `https_only=False`, no `max_age` (browser-session cookie). The `user_sessions` **table exists** (models/admin.py:26-41 + lifespan DDL main.py:112-133 with indexes on user/ip/country/login_at/active) and the admin panel + analytics read it (`admin/api.py` "active sessions (last 30 min)", UserSessionAdmin view) — but **grep proves no code ever instantiates `UserSession(...)`**: the table is permanently empty, all session analytics return 0, and there is no logout/last-activity tracking. Session management is a façade.

**IP bans**: the `ip_bans` table exists (models/admin.py:14-23), sqladmin CRUD works (validates IP/CIDR, dedupes, writes audit log), the admin REST API (`admin/api.py:196-272`) creates/deactivates rows correctly — and **none of it ever reaches the middleware**: `app.add_middleware(IPBanMiddleware)` (main.py:202) passes no initial sets, `IPBanMiddleware` has no DB/Redis loader (its own docstring admits "in production, banlist is loaded from Redis/Postgres" — that code was never written), and nothing refreshes it. Worse, the invalidation hook is broken: `admin_panel.py:281,299` call `IPBanMiddleware.invalidate_all()` — **a method that does not exist** (verified via AST: class methods are `__init__, ban_ip, ban_cidr, unban_ip, is_banned, dispatch`) → `AttributeError` → sqladmin 500 every time an admin creates/edits/deletes a ban. The main.py comment "IP ban middleware — fail-open (requests pass if cache cannot refresh)" describes a cache-refresh architecture that was never implemented. Net: IP banning is triple-broken (no data flow, no cache, broken invalidation) — a superadmin "bans" an attacking IP and nothing whatsoever happens.

## 6. SSRF Protection

Two implementations, one dead and one dead-with-better-design (§1.7). Assessment of `ssrf_protection.py` on its merits:

- **Scheme allowlist**: http/https only — blocks `file://`, `gopher://`, `dict://`, `data:`, `ftp://` (all covered by its test suite). ✓
- **Private ranges**: 10 IPv4+IPv6 networks including CGNAT 100.64/10 (covers Alibaba metadata 100.100.100.200) and link-local 169.254/16 (AWS/Azure/GCP metadata). **Gaps**: IPv4-mapped IPv6 (`::ffff:169.254.169.254` → **ALLOWED**, proven by execution — `ipaddress` does not treat mapped v6 as member of v4 networks), NAT64 `64:ff9b::/96`, `192.0.0.0/24`, `198.18.0.0/15` benchmark range, multicast `224.0.0.0/4`, unspecified `::/128`.
- **Non-standard IP encodings**: decimal/octal/hex literals (`http://2130706433/`, `0177.0.0.1`, `0x7f000001`) are caught **accidentally** — `ipaddress.ip_address` rejects the string, control falls to the DNS path, glibc's `getaddrinfo` resolves the weird literal to 127.0.0.1, which then matches 127/8. Verified live. Fragile-but-working.
- **DNS rebinding**: **TOCTOU remains** — `is_safe_url` resolves via `getaddrinfo`, then `SafeHTTPClient` fetches and httpx performs an *independent* resolution. An attacker-controlled authoritative DNS can answer the check with a public IP and the fetch with 169.254.169.254. Correct fix (pin resolved IP, connect to it with Host header / custom transport) not implemented.
- **Redirects**: **handled properly and unusually well** — manual redirect following with re-validation of each hop (defeats 302→metadata chains). The `security.py` copy (`safe_http_get`) has **zero** redirect handling and doesn't even disable httpx auto-follow (httpx 0.28 defaults to no-follow, so it's safe by accident).
- **Does the crawl API use it? NO.** Grep-verified: `app/` contains zero imports of `ssrf_protection` / `SafeHTTPClient` / `is_safe_url` / `safe_http_get`. `/api/v1/crawl` (Z5), `/products/import-url` (Z4), and `knowledge/crawler.py` (Playwright + Katana via Docker) fetch user-supplied URLs with no validation at all. The SSRF defense is a fully-built, fully-tested bunker around a door that was left open.

## 7. Utils Deep-Dive

### 7.1 `egypt_address.py` (351 LOC)
- **27-governorate model**: `GOVERNORATES` dict keyed by slug → `{name_ar, zone (1-5), shipping_cost (35-100 EGP), free_threshold (300-1000 EGP), areas: [...]}`. Count verified = 27 ✓ (all real Egyptian governorates; hyphenated slugs `kafr-el-sheikh`, `port-said`, …). Zone ladder: Cairo/Giza z1 (35/300), Delta+Canal z2 (45-50/500), Upper-Egypt-adjacent z3 (55-65/600-700), Upper Egypt+Red Sea/South Sinai z4 (75-90/800-900), frontier z5 (100/1000). Areas: 5-20 Arabic names per governorate (Cairo 20, Giza 16, Alexandria 16).
- **Data quality defects**: `المنيل`, `الزمالك`, `البدرشين` listed under **both** Cairo and Giza; `كفر الشيخ` (a governorate) listed as a Gharbia *area*; Sharqia area `فاكس` is a nonsense entry (likely typo of `فاقوس`); `بلبيس` appears under both Dakahlia and Sharqia (it's Sharqia).
- **Functions**: `validate_egyptian_phone` / `normalize_egyptian_phone` (see 7.2 — the *better* of the two phone implementations; regex `^(?:\+20|0020|20|0)?(1[0125]\d{8})$` accepts all four prefix conventions, normalize returns `0`+group → clean 11-digit, or `None` on invalid ✓); `detect_governorate_from_text` (Arabic `name_ar in text` OR English `key in normalized` — substring matching, no area-level detection, English keys with hyphens will never match free text, false positives like "cairo" inside words); `get_governorates` (API list); **`get_cities` ignores the entire areas dataset** — returns `[governorate_ar]` for every governorate ("our city lists are minimal" comment is wrong: the areas lists exist, cities/areas are just conflated) → `/api/address/cities` is a stub; `get_areas_for_governorate` (returns areas or []); `calculate_shipping` (see bug below); `validate_egyptian_address` (governorate must exist; **any non-empty city string passes** — explicitly documented stub).
- **`calculate_shipping` contract bug**: returns a **dict** with inconsistent shapes across branches (free branch lacks `free_threshold`/`remaining`; unknown-governorate branch lacks `governorate_ar`/`free_threshold`/`remaining`). The caller `api/address.py:31` does `float(calculate_shipping(...))` → **`TypeError: float() argument must be … not 'dict'` → guaranteed 500 on every call to `/api/address/shipping`** (proven by execution). The endpoint has never worked.
- **Callers**: `api/address.py` (5 unauthenticated endpoints), tests (unit + property). Phone functions here have **no** app callers.

### 7.2 `phone.py` (30 LOC)
- `validate_egyptian_phone(phone) -> bool`: strips `[\s\-\(\)\+]`, accepts `^01[0125]\d{8}$` or `^201[0125]\d{8}$`. Prefix model: 010 Vodafone / 011 Etisalat / 012 Orange / 015 WE ✓ (013/014/016 correctly rejected — 016 is a real WE prefix since 2023 but is rejected here; acceptable conservatism, worth a note).
- `normalize_egyptian_phone(phone) -> str`: strips separators; if starts with `"20"` → `"0" + cleaned[2:]`. **No validation, no None path**: `"2012345"` → `"012345"` (garbage in, garbage out); `"00201012345678"` → returned **unchanged** (no normalization); non-str input raises. Contract mismatch with `egypt_address.normalize` (returns `Optional[str]`, handles 0020).
- **Divergence with business impact**: the **order pipeline** (`ai/order_collector.py:7,55`) uses **this** file's validator — which **rejects** `00201012345678` (double-zero international prefix, a form Egyptian customers actually type), while `egypt_address.py`'s validator accepts it. Orders with that phone form are silently dropped (`return None` in order validation). Two same-named validators with different accept-sets is a latent correctness trap.
- `normalize_egyptian_phone` here has zero app callers (order_collector only validates, never normalizes → whatever format the LLM extracted is stored as-is).

### 7.3 `utils/security.py` (286 LOC)
- **Password hashing**: passlib CryptContext bcrypt (`hash_password`/`verify_password`); passlib 1.7.4 unmaintained (Z1) + known bcrypt-4 version-detection incompatibility (warning noise, works).
- **JWT access tokens**: `create_access_token(data, expires_delta=None)` — merges caller claims, forces `exp` + `iat`, HS256 with `settings.JWT_SECRET_KEY`; default TTL `JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 1440` = **24 h**. `decode_token` — **algorithm pinned to `[settings.JWT_ALGORITHM]`** (kills `alg=none` + RS256/HS256 confusion ✓), `options={"require": ["exp"]}` (rejects non-expiring tokens ✓), returns None on any error, never raises ✓. Solid — but the secret default is `"change-me-to-a-random-secret-key"` and there's no startup guard, so default deployments are trivially forgeable (Z1).
- **Refresh/revocation system (~130 LOC, fully implemented, ZERO callers — grep-verified, confirms Z4)**: `create_refresh_token` (7-day expiry + `jti` UUID + `type:"refresh"`), `verify_refresh_token` (decode + type check + jti required + denylist), `_get_redis` (lazy `redis.asyncio.from_url`, new connection per call — no pool), `is_token_revoked` (sync, **in-memory set only** — multi-process blind spot), `is_token_revoked_async` (Redis GET + memory fallback, **fail-open** by design), `revoke_token` (memory set + Redis SETEX with self-cleaning TTL = exp−now+60s or 7d). No `/auth/refresh`, no `/auth/logout`, no route touches it. Users are stuck with unrevokable 24h access tokens; a stolen token can't be killed except by rotating the global secret.
- **`verify_fb_signature(payload, signature)`**: HMAC-SHA256 with `settings.FB_APP_SECRET`, `hmac.compare_digest(f"sha256={expected}", signature)` — constant-time ✓, fails **closed** on empty secret/signature ✓ (config default `FB_APP_SECRET=""` means webhooks reject everything until configured — correct posture). This is the one defense in the utils that is both correct AND live (webhook.py:54).
- Redis connections are opened/closed per call (`aclose` in finally) — correct but chatty.

### 7.4 `utils/__init__.py` — empty file (0 LOC).

---

## 8. Function Inventory Table

| File | Function | Params | Returns | Purpose |
|---|---|---|---|---|
| bot_detection.py | `is_likely_bot` | `user_agent: str\|None` | `bool` | substring match vs 26 crawler signatures |
| bot_detection.py | `BotDetectionMiddleware.__init__` | `app: ASGIApp` | — | store next app |
| bot_detection.py | `BotDetectionMiddleware.__call__` | `scope, receive, send` | `None` | tag scope, log unauth crawler, pass through |
| prompt_injection.py | `detect_prompt_injection` | `text: str` | `tuple[bool, list[str]]` | 25-regex injection scan (matched texts) |
| prompt_injection.py | `sanitize_user_input` | `text: str` | `str` | wrap in [USER INPUT…] delimiters |
| rate_limit.py | `get_rate_limit_key` | `request: Request` | `str` | tenant:/user:/ip: key derivation |
| rate_limit.py | `_build_limiter` | — | `Limiter` | construct slowapi Limiter (Redis URI) |
| rate_limit.py | `get_limiter` | — | `Limiter` | lazy singleton accessor |
| rate_limit.py | `_rate_limit_handler` | `request, exc` | `JSONResponse` | 429 + Retry-After + X-RateLimit-Limit |
| rate_limit.py | `setup_rate_limiting` | `app: FastAPI` | `None` | wire state/handler/middleware, idempotent |
| rate_limiter.py | `RateLimiter.__init__` | `limit=5, window_seconds=60` | — | validate + init buckets (ValueError guards) |
| rate_limiter.py | `RateLimiter.check` | `identifier: str` | `tuple[bool, int]` | sliding-window allow check (fail-open on "") |
| rate_limiter.py | `RateLimiter.reset` | `identifier: str\|None` | `None` | clear one/all buckets |
| security.py | `is_safe_url` | `url: str` | `tuple[bool, str]` | SSRF check (no redirect/allow_private) — unused |
| security.py | `safe_http_get` | `client, url, **kwargs` | `Response` | guarded httpx GET (raises SSRFProtectionError) — unused |
| security.py | `detect_prompt_injection` | `text: str` | `tuple[bool, list[str]]` | 17-regex variant (returns patterns) — unused |
| security.py | `sanitize_user_input` | `text: str` | `str` | delimiter wrap (duplicate) — unused |
| security.py | `SecurityHeadersMiddleware.dispatch` | `request, call_next` | `Response` | 5 headers (weaker duplicate) — unused |
| security.py | `is_likely_bot` | `user_agent: str` | `bool` | 14-pattern variant; empty UA → True — unused |
| security.py | `BotDetectionMiddleware.dispatch` | `request, call_next` | `Response` | log bot traffic — unused |
| security.py | `IPBanMiddleware.__init__` | `app, banned_ips=None, banned_cidrs=None` | — | init empty ban sets/CIDR list |
| security.py | `IPBanMiddleware.ban_ip` | `ip: str` | `None` | add to set |
| security.py | `IPBanMiddleware.ban_cidr` | `cidr: str` | `None` | append parsed network |
| security.py | `IPBanMiddleware.unban_ip` | `ip: str` | `None` | discard from set |
| security.py | `IPBanMiddleware.is_banned` | `ip: str` | `bool` | exact + CIDR membership |
| security.py | `IPBanMiddleware.dispatch` | `request, call_next` | `Response` | 403 if banned (never fires: sets empty) |
| security.py | `SimpleRateLimiter.__init__` | — | — | init request dict |
| security.py | `SimpleRateLimiter.is_allowed` | `key, limit, window_seconds` | `tuple[bool, int]` | sliding window (wall clock) |
| security.py | `rate_limit` | `limit, window_seconds=60` | decorator | 429 wrapper — used by 0 endpoints |
| security_headers.py | `_is_https` | `scope: Scope` | `bool` | scheme or X-Forwarded-Proto=https |
| security_headers.py | `SecurityHeadersMiddleware.__init__` | `app: ASGIApp` | — | store next app |
| security_headers.py | `SecurityHeadersMiddleware.__call__` | `scope, receive, send` | `None` | inject 8 headers + conditional HSTS (dedup) |
| ssrf_protection.py | `is_safe_url` | `url, *, allow_private=False` | `tuple[bool, str]` | scheme+host+IP+DNS validation |
| ssrf_protection.py | `SafeHTTPClient.__init__` | `*, timeout, connect_timeout, headers, max_redirects, allow_private` | — | config |
| ssrf_protection.py | `SafeHTTPClient._check` | `url: str` | `None` | raise UnsafeURLError if unsafe |
| ssrf_protection.py | `SafeHTTPClient.get` | `url, **kwargs` | `httpx.Response` | guarded GET w/ per-hop redirect revalidation |
| egypt_address.py | `validate_egyptian_phone` | `phone: str` | `bool` | 4-prefix-format validator |
| egypt_address.py | `normalize_egyptian_phone` | `phone: str` | `str\|None` | → 01XXXXXXXXX or None |
| egypt_address.py | `detect_governorate_from_text` | `text: str` | `str\|None` | Arabic/English governorate guess |
| egypt_address.py | `get_governorates` | — | `list[dict]` | API catalog (key/name_ar/zone/cost/threshold) |
| egypt_address.py | `get_cities` | `governorate: str` | `list[str]` | **stub** — returns [governorate_ar] |
| egypt_address.py | `get_areas_for_governorate` | `governorate: str` | `list[str]` | areas list |
| egypt_address.py | `calculate_shipping` | `governorate, cart_total=0.0, default_inside=35, default_outside=60` | `dict` | cost/free/message (+threshold/remaining) |
| egypt_address.py | `validate_egyptian_address` | `governorate, city=None` | `bool` | gov exists; city merely non-empty |
| phone.py | `validate_egyptian_phone` | `phone: str` | `bool` | 2-format validator (rejects 0020…) |
| phone.py | `normalize_egyptian_phone` | `phone: str` | `str` | unvalidated strip/"20"→"0" munge |
| utils/security.py | `hash_password` | `password: str` | `str` | bcrypt hash |
| utils/security.py | `verify_password` | `plain, hashed` | `bool` | bcrypt verify |
| utils/security.py | `create_access_token` | `data: dict, expires_delta=None` | `str` | HS256 JWT w/ forced exp+iat |
| utils/security.py | `decode_token` | `token: str` | `dict\|None` | pinned-alg, require-exp decode; never raises |
| utils/security.py | `create_refresh_token` | `data, expires_delta=None` | `str` | 7d JWT w/ jti+type — **no callers** |
| utils/security.py | `verify_refresh_token` | `token: str` | `dict\|None` | decode+type+jti+denylist — **no callers** |
| utils/security.py | `_get_redis` | — | `redis\|None` (async) | lazy per-call redis connection |
| utils/security.py | `is_token_revoked` | `jti: str` | `bool` | memory-only sync check |
| utils/security.py | `is_token_revoked_async` | `jti: str` | `bool` (async) | Redis + memory, fail-open |
| utils/security.py | `revoke_token` | `jti, exp=None` | `bool` (async) | SETEX denylist + memory — **no callers** |
| utils/security.py | `verify_fb_signature` | `payload: bytes, signature: str` | `bool` | constant-time HMAC-SHA256, fail-closed ✓ live |

---

## 9. Vulnerability Register

Severity / location / issue / fix. (C=critical, H=high, M=medium, L=low.)

| # | Sev | Location | Vulnerability / Weakness | Fix |
|---|-----|----------|--------------------------|-----|
| C1 | CRITICAL | `ssrf_protection.py` (whole file); crawl API `api/crawl.py`; `products/import-url`; `knowledge/crawler.py` | Complete, redirect-hardened SSRF guard exists but has **zero app importers** — user URLs are fetched by raw httpx/Playwright/Katana with no scheme/host/IP validation (file:// reads, metadata creds, internal port scans). Confirms Z5. | Import `SafeHTTPClient` in crawl/import/crawler paths; reject non-http(s); add startup assert that the guard is referenced; add integration test hitting a blocked URL through the API. |
| C2 | CRITICAL | `security.py:223-277`, `main.py:202`, `admin_panel.py:281,299` | IP-ban system broken end-to-end: (a) middleware instantiated with empty sets; (b) `ip_bans` table never loaded into it; (c) admin hook calls **nonexistent** `IPBanMiddleware.invalidate_all()` → AttributeError → sqladmin 500 on every ban create/edit/delete (**proven**: AST shows class lacks the method). Bans are never enforced. | Implement classmethod registry `invalidate_all()` or instance handle; load bans from Postgres/Redis on boot + TTL refresh (as the docstring already promises); wire `admin/api.py` POST/DELETE to the same cache; add e2e test that a banned IP gets 403. |
| C3 | CRITICAL | `prompt_injection.py:56-93`; `ai/agent.py`; `api/webhook.py` | Prompt-injection detector + delimiter sanitizer never called by the live chat pipeline; customer text (and crawled knowledge text) reaches the LLM raw. Integration tests mock `process_customer_message`, so they pass vacuously. | Call `detect_prompt_injection` in webhook/test-chat before the agent (log/flag/refuse), always wrap messages with `sanitize_user_input`, and extend the guard to crawled product/knowledge text; fix tests to exercise the real path. |
| C4 | CRITICAL | `rate_limit.py` (wiring) vs 79 endpoints | Rate limiting is a no-op: SlowAPIMiddleware installed but no endpoint uses `@limiter.limit` and no `default_limits` configured → `/auth/login` (brute force), webhooks, dashboard all unthrottled; the suite's own `xfail` tests document the gap. | Set `default_limits` on the Limiter (e.g. 100/min per key) + explicit login/webhook limits; un-xfail the integration tests. |
| H1 | HIGH | `models/admin.py:26-41`, `admin/api.py:293-299,425-445` | `user_sessions` table never written (no `UserSession(...)` instantiation anywhere) — "active sessions" analytics and the admin view read a permanently empty table. | Record sessions on login (IP/UA/geo), update `last_activity` in `get_current_user`, set `is_active=False` on logout. |
| H2 | HIGH | `config.py:21`, `main.py:191-197`, `requirements.txt:14` | JWT secret insecure default `"change-me-to-a-random-secret-key"` **and reused** as Starlette session-cookie signing key; python-jose 3.3.0 carries CVE-2024-33663/33664 (confirms Z1). | Refuse to boot without explicit secret (Pydantic validator); separate `SESSION_SECRET_KEY`; upgrade to `pyjwt`/joserfc or jose ≥3.4. |
| H3 | HIGH | `utils/security.py:111-248` | Refresh/revocation system (create/verify/denylist/revoke) fully implemented, **zero callers**; access tokens live 24h (1440 min) with no logout/revocation path — stolen tokens are unkillable until expiry. | Add `/auth/refresh` + `/auth/logout` routes (Z4 same rec); shorten access TTL to 15-30 min once refresh works. |
| H4 | HIGH | `api/address.py:31` + `egypt_address.py:299-340` | `/api/address/shipping` does `float(calculate_shipping(...))` on a **dict** return → `TypeError` → guaranteed 500 on every call (**proven by execution**). Endpoint has never worked. | Return the dict directly (or add `calculate_shipping_cost() -> float`); add an endpoint test. |
| H5 | HIGH | `phone.py:4-29` vs `egypt_address.py:226-254`; `ai/order_collector.py:7,55` | Divergent duplicate validators: order pipeline uses `phone.py`, which **rejects** `00201012345678` (accepted by the other copy) → valid orders silently dropped; `phone.normalize` returns mangled strings for invalid input ("2012345"→"012345") and never returns None. | Delete `phone.py`, keep the `egypt_address` implementation (or extract a single `app/utils/phone.py` with its semantics); normalize before storing in orders. |
| M1 | MED | `ssrf_protection.py:104-119,186-203` | DNS-rebinding TOCTOU: guard resolves via `getaddrinfo`, httpx re-resolves independently — attacker DNS can pass the check then serve 169.254.169.254 on fetch. | Resolve once, pin the IP: connect to the validated IP with `Host`/SNI set to the hostname (custom httpx transport), or re-check inside the transport's connection hook. |
| M2 | MED | `ssrf_protection.py:45-56`, `security.py:27-38` | IPv4-mapped IPv6 (`::ffff:169.254.169.254`) and NAT64 (`64:ff9b::…`) literals **bypass** both blocked-network lists (**proven**: `ip_address('::ffff:169.254.169.254') in 10.0.0.0/8` etc. is False). Missing 192.0.0.0/24, 198.18.0.0/15, 224.0.0.0/4, ::/128. | Canonicalize: if `ip.version == 6 and ip.ipv4_mapped` → check the mapped v4; add the missing networks; test the mapped-vector. |
| M3 | MED | `security_headers.py:61-78` | HSTS emission trusts spoofable `X-Forwarded-Proto` (uvicorn runs without `--proxy-headers`; no trusted-proxy list) — clients can force HSTS onto plain-HTTP responses. | Run uvicorn with `--proxy-headers --forwarded-allow-ips=<proxy>` or make HSTS config-driven rather than header-driven. |
| M4 | MED | `rate_limiter.py:44,61`, `security.py:291-313` | In-memory limiters: unbounded bucket dict (attacker-controlled keys → memory growth), not multi-worker safe; `SimpleRateLimiter` uses wall-clock `time.time()`. | Cap dict size (LRU) + periodic sweep; use monotonic clock; prefer the Redis-backed slowapi path for anything real. |
| M5 | MED | `security.py` vs `bot_detection.py`/`prompt_injection.py`/`security_headers.py`/`rate_limiter.py` | Every security primitive exists twice with **divergent semantics** (e.g. `is_likely_bot("")`: `True` in security.py, `False` in bot_detection.py; two different `detect_prompt_injection` return contracts; two `SecurityHeadersMiddleware` classes with the same name). Import-path ambiguity + drift hazard. | Delete `security.py`'s dead duplicates wholesale; keep only `IPBanMiddleware` (moved to its own module). |
| M6 | MED | `bot_detection.py:36-66,115-116` | Overbroad substrings (`bot`, `headless`) → false positives; `scope["is_likely_bot"]` flag has **no consumers**; every Meta webhook is logged as a bot (noise at volume). | Word-boundary matching; either build the "stricter limits for bots" consumer or drop the flag; exclude `facebookexternalua` from logging or sample it. |
| M7 | MED | `prompt_injection.py:20-53` | Regex-only injection detection: bypassable via homoglyphs, zero-width chars, Arabic diacritics/tatweel, leetspeak, paraphrase — no Unicode normalization before matching. (Moot until C3 is fixed, but fix together.) | NFKC-normalize + strip zero-width/diacritics before matching; treat detection as signal for stricter handling, rely on the delimiter + system-prompt hardening as the real control. |
| M8 | MED | `main.py:191-197` | Session cookie: `https_only=False`, no `max_age` (browser-session only), secret shared with JWT (see H2). SameSite=lax is the only decent flag. | `https_only=True` behind TLS, set `max_age`, dedicated secret. |
| L1 | LOW | `egypt_address.py:282-288` | `get_cities` ignores the areas dataset — returns `[governorate_ar]` for every governorate; `/api/address/cities` is a misleading stub. | Return the real areas (or a curated city list); distinguish city vs neighborhood. |
| L2 | LOW | `egypt_address.py:21-217,257-265` | Area data errors: كفر الشيخ under Gharbia; المنيل/الزمالك/البدرشين duplicated in Cairo & Giza; "فاكس" (فاقوس typo); `detect_governorate_from_text` substring false-positives, no area-level detection, hyphenated English keys unmatchable. | Data review pass; tokenized matching with word boundaries for both scripts. |
| L3 | LOW | `security_headers.py:33,39` | Deprecated `X-XSS-Protection` header retained; `img-src https:` allows any remote image (tracking-pixel channel); no `Cache-Control: no-store` on API responses. | Drop XSS-Protection; consider `img-src 'self' data:`; add no-store for authenticated API responses. |
| L4 | LOW | `egypt_address.py:310-340` | `calculate_shipping` returns inconsistent dict shapes across the three branches (missing keys) — footgun that already caused H4. | Fixed schema with all keys always present. |
| L5 | LOW | `rate_limit.py:19,24-26,101` | Docstring cites nonexistent auth.py examples; "memory:// fallback if REDIS_URL unset" is unreachable because REDIS_URL has a non-empty default. | Fix docs; make fallback explicit via a `RATELIMIT_STORAGE` setting. |
| L6 | LOW | `utils/security.py:162-172` | `is_token_revoked` (sync) checks the in-memory set only → multi-process revocation blind spot (currently moot — no callers). | Route all revocation checks through the async Redis version; or document single-process constraint. |
| L7 | LOW | `utils/security.py:151-159,187,226` | New Redis connection per denylist check (no pool); `passlib` 1.7.4 unmaintained / bcrypt-4 warnings. | Module-level `redis.asyncio` client/pool; plan passlib replacement (argon2-cffi or bcrypt direct). |
| L8 | LOW | `egypt_address.py:223` & `phone.py:14` | 016 prefix (WE, allocated 2023) rejected by both validators — false negatives on a growing customer segment. | Add `1[0125 6]` after verifying carrier policy. |

**Positive findings worth keeping**: `verify_fb_signature` (constant-time, fail-closed) is exemplary and live; `security_headers.py` is a textbook pure-ASGI implementation (dedup + conditional HSTS + COOP/CORP); `SafeHTTPClient`'s per-hop redirect re-validation is better than most production SSRF guards; `decode_token`'s algorithm pinning + `require:["exp"]` is correct hardening; `RateLimiter` uses a monotonic clock and validates constructor args.

---

## 10. Quality Ratings (1-10)

| File | Score | Justification |
|---|---|---|
| `security_headers.py` | **8.5** | The only middleware that is both excellent and live: pure ASGI, header dedup, conditional HSTS, COOP/CORP, real CSP. Deductions: spoofable XFP (M3), legacy XSS header, no Cache-Control story. |
| `ssrf_protection.py` | **8** | Best engineering in the layer (redirect re-validation, DNS pinning attempt, fail-closed DNS, allow_private flag, never-raise contract) — but mapped-IPv6/rebinding gaps (M1/M2), no connection pooling, and **zero integration** with the actual fetch paths caps it at 8-despite-dead. |
| `bot_detection.py` | **7.5** | Clean, honest, fast, correctly log-only with documented rationale. Overbroad substrings, dead scope-flags, webhook log noise. |
| `rate_limiter.py` | **7** | Correct primitive (monotonic clock, arg validation, fail-open documented and tested) with unbounded memory and test-only usage. |
| `utils/security.py` | **7** | Live parts (JWT decode hardening, HMAC verify, bcrypt) are solid; ~130 LOC of never-called refresh/revocation machinery, sync denylist blind spot, per-call Redis connections, inherited weak-secret/jose-CVE exposure. |
| `egypt_address.py` | **6.5** | Rich, genuinely useful 27-governorate dataset and the better phone implementation; dragged down by get_cities stub, inconsistent calculate_shipping shapes (which broke the API — H4), data errors, duplicated phone code, weak city validation. |
| `prompt_injection.py` | **6** | Good pattern coverage incl. Egyptian Arabic and a sound delimiter strategy; but it's not a middleware, it's unwired, regex-only (M7), and duplicated in security.py with different semantics. |
| `rate_limit.py` | **5** | Thoughtful key function and 429 handler, idempotent setup — all in service of a limiter that enforces nothing; misleading docstring; unreachable memory fallback. |
| `phone.py` | **4** | Divergent duplicate that the **order pipeline** depends on; rejects a valid national format; normalize mangles invalid input; no None contract. Small, but wrong where it matters. |
| `security.py` | **3.5** | A graveyard of weaker duplicates of four other modules plus the one live-but-hollow IPBanMiddleware; contains the invalidate_all contract violation (C2) and a never-used decorator limiter. Should be deleted except for IPBanMiddleware (rewritten). |
| `middleware/__init__.py` / `utils/__init__.py` | n/a | Trivial/empty (as expected). |

**Layer verdict: 5/10.** The *code quality* of the two pure-ASGI middlewares and the SSRF client is high; the *security posture* is near-zero because every enforcement mechanism (rate limit, IP ban, prompt injection, SSRF) is disconnected from the request paths it was built to protect, and the admin tooling around them (sessions, bans) is façade analytics over empty tables.
