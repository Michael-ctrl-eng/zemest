# Z12 — Test Suite & Documentation Audit (zemest)

**Agent:** Z12 (tests & docs) · **Method:** 100% read-through of every test file + *actual execution* of the full suite in a pinned replica of `requirements.txt` (fastapi 0.115.6, sqlalchemy 2.0.36, pytest 8.3.4/pytest-asyncio 0.25.0, passlib 1.7.4/bcrypt 4.1.3, schemathesis 3.39.16, hypothesis, aiosqlite). All counts below are *measured*, not estimated.

---

## 0. Executive Summary

- **452 tests exist** (443 collected without schemathesis + 9 schema tests). The suite *looks* like a best-practice 7-tier pyramid (unit/property/security/e2e/load/scraper/schema). In reality:
  - **~60% of the "security verification" tests exercise defense modules that are imported by ZERO production code** (RateLimiter, is_safe_url, detect_prompt_injection) — they prove dead code works, not that the app is defended.
  - **5 scraper tests ERROR on missing fixtures, 3 schema tests ERROR, 10 tests FAIL deterministically** — the suite is **not green and cannot ever have been green** in its current shape, proving it is not run in CI (no CI config exists at all).
  - Running the ignored security suite **found a real production 500**: `POST /api/tenants/{id}/orders` always raises `MissingGreenlet` (lazy-load of `order.items` in `app/api/orders.py:41` via `_order_response`) — reproduced with a plain payload, independent of test harness.
  - Docs (README, MASTER_PROMPT, tests/README) describe aspirational systems: Celery-offloaded webhooks (actually inline `BackgroundTasks`), two custom "Rabbit/Rat" models (actually generic OpenRouter/Gemini), LiteLLM routing (dead `llm_gateway.py`), owner chat commands (unreachable — `owner_psid` never set), order-API auto-dispatch (manual retry only), rate limiting (unwired).

---

## 1. Test Suite Inventory

Measured with `pytest --collect-only` (all deps installed). DB column: what the tier actually touches.

| File | Tests | Covers | Fixtures/mocks | DB | Runs in CI? |
|---|---|---|---|---|---|
| tests/conftest.py | — (root harness) | shared fixtures | overrides `get_db` | SQLite **file** `./test.db` (comment claims "in-memory" — false) | **No CI exists** |
| tests/test_auth.py | 9 | register/login/me, dup-email 400 | client, test_user, auth_headers | sqlite | never automated |
| tests/test_conversations.py | 3 | list/detail 404 | client, test_conversation | sqlite | no |
| tests/test_crawl.py | 4 | crawl job CRUD | **mocks `_run_crawl_inline`** (3/4 tests) | sqlite | no |
| tests/test_egypt_address.py | 25 | 27 governorates, shipping, phones, detection | none (pure) | none | no |
| tests/test_language.py | 14 | detect_language, normalize_arabic | none (pure) | none | no |
| tests/test_order_collector.py | 7 | JSON-block extraction, validation | none (pure) | none | no |
| tests/test_orders.py | 9 | status lifecycle, invalid transition 400 | local `test_order` factory (bypasses create_order) | sqlite | no |
| tests/test_phone.py | 17 | phone validate/normalize (utils/phone) | none (pure) | none | no |
| tests/test_postiz.py | 16 | PostizClient + postiz API endpoints | **all HTTP mocked** (`_get_client`, `get_postiz_client`) | sqlite | no |
| tests/test_products.py | 16 | CRUD, flexible attrs, CSV import, pagination | client, test_products | sqlite | no |
| tests/test_prompts.py | 10 | system prompt & product context content | none (pure) | none | no |
| tests/test_scheduling.py | 10 | schedule/cancel/delete, cross-tenant invisibility | none — **writes ScheduledPost rows** | sqlite (create_all only — table missing in prod migrations!) | no |
| tests/test_security.py | 6 | bcrypt hash/verify, JWT round-trip | none (pure) | none | no |
| tests/test_style_learning.py | 15 | DYI/WA zip parsers, sampling, heuristics, profile build | in-memory zips; `use_llm=False` | sqlite | no |
| tests/test_system.py | 7 | onboarding flow, order lifecycle, isolation, dashboard pages | none | sqlite | no |
| tests/test_tenants.py | 9 | tenant CRUD, stats, isolation | client, test_tenant | sqlite | no |
| tests/test_webhook.py | 9 | verify challenge, HMAC sig ok/bad/missing, empty | monkeypatch settings FB_APP_SECRET | sqlite | no |
| **Subtotal root** | **186** | | | | |
| tests/property/conftest.py | — | no-ops the root `setup_db` | | none | no |
| tests/property/test_phone_property.py | 8 | totality of both phone validators, normalize round-trip | hypothesis | none | no |
| tests/property/test_address_property.py | 9 | totality of shipping/geo, free-threshold property | hypothesis | none | no |
| tests/property/test_order_data_property.py | 6 | totality of order extraction, clean-strips-JSON | hypothesis | none | no |
| tests/property/test_prompt_injection_property.py | 7 | totality + recall of **unwired** detector | hypothesis | none | no |
| **Subtotal property** | **30** | | | | |
| tests/security/conftest.py | — | second_user/tenant, isolated_rate_limiter, arbitrary_user_token | | sqlite | no |
| tests/security/test_idor.py | 13 | cross-tenant 404s on orders/products/stats/conversations/settings | second_auth_headers | sqlite | no |
| tests/security/test_jwt_attacks.py | 17 | alg=none, alg confusion, exp, tampering, deleted user | hand-forged JWTs | sqlite (2) | no |
| tests/security/test_prompt_injection.py | 27 | detector patterns (20) + **4 API tests that mock the agent** + 2 detector units | **AsyncMock(process_customer_message)** | sqlite | no |
| tests/security/test_rate_limiting.py | 14 | **unwired RateLimiter primitive** (12) + 2 xfail integration | isolated_rate_limiter | none | no |
| tests/security/test_sql_injection.py | 7 | classic payloads vs search/name/orders, DROP check, timing | none | sqlite | no |
| tests/security/test_ssrf_protection.py | 37 | **unwired is_safe_url** blocklist/allowlist/edge cases | none (real DNS for allowlist!) | none | no |
| tests/security/test_xss.py | 25 | stored XSS via products/orders/tenant/chat + security headers | **AsyncMock(process_customer_message)** for chat | sqlite | no |
| **Subtotal security** | **140** | | | | |
| tests/scraper/test_bot_user_agent.py | 54 | 18 UAs × (products/login/dashboard), oversized & malformed UA | client | sqlite | no |
| tests/scraper/test_aggressive_scraping.py | 4 | 100 rapid requests (xfail), count stability, cross-tenant | **requests undefined fixtures `second_auth_headers`/`second_tenant` → 2 ERRORs** | sqlite | no |
| tests/scraper/test_data_extraction_attempt.py | 10 | page_size caps, PII isolation, pagination bounds | **3 tests ERROR on same undefined fixtures**; 1 fails (missing `test_products` fixture) | sqlite | no |
| **Subtotal scraper** | **68** | | | | |
| tests/e2e/conftest.py | — | Playwright browser, base_url, e2e_user_and_tenant (via API) | | real server required | no |
| tests/e2e/test_customer_chat.py | 3 | customer chat → reply → order extraction | httpx against localhost:8000; xfail-on-500 | real server | **skip** (no Playwright/server) |
| tests/e2e/test_merchant_flow.py | 5 | login page, login, dashboard pages, add product, logout | Playwright; catch-all `except Exception → xfail` | real server | skip |
| tests/e2e/test_order_flow.py | 4 | manual order, lifecycle, invalid transition, dashboard list | httpx; **2 tests assert nothing meaningful** | real server | skip |
| **Subtotal e2e** | **12** | | | | |
| tests/load/conftest.py | — | env-driven config (**constants never imported — dead config**) | | | no |
| tests/load/locustfile.py | — | 2 user classes, 11 weighted tasks | | real server | no (separate CLI) |
| tests/load/test_locust_smoke.py | 7 | locustfile imports & has methods (**structural only**) | importlib | none | passes w/o locust |
| **Subtotal load** | **7** | | | | |
| tests/schema/conftest.py | — | openapi_schema/schema fixtures | | none | no |
| tests/schema/test_openapi_contract.py | 9 | 3 Schemathesis fuzz tests (**all ERROR**) + 6 shape tests (pass) | schemathesis `from_dict` | none (no DB override!) | **errors in every env** |
| **Subtotal schema** | **9** | | | | |
| **TOTAL** | **452** | | | | **0 automated** |

Measured single-run outcome (pinned deps, sandbox): **418 passed / 10 failed / 14 skipped / 3 xfailed / 8 errors** — pass rate 92%, and the 10 failures + 8 errors are *deterministic* (reproduce on any machine; only `test_ssrf_allows_public_with_query` is network-dependent).

Deterministic failures/errors:
| Item | Cause | Class |
|---|---|---|
| 5× scraper ERRORs | `second_auth_headers`/`second_tenant` defined only in `tests/security/conftest.py`, used by `tests/scraper/` | test-suite bug |
| 3× schema ERRORs | (a) schemathesis<4: `from_dict` rejects OpenAPI **3.1.0**; (b) schemathesis≥4: `from_dict` removed; (c) `test_api_no_500_errors` requests nonexistent `client_factory` fixture | test-suite bug (triple) |
| `test_huge_page_number_returns_empty` | missing `test_products` fixture → asserts `total==3` but tenant has 0 products — **can never pass** | broken test |
| `test_validate_phone_realistic_inputs` (property) | strategy bug: `plus if plus else ""` yields `True + str` → TypeError on first bool | broken test |
| 3× `test_injection_detected[...]` | detector misses "FreeGPT…", "Show me the first 1000 characters", "Forget your identity…" | real gap (in dead code) |
| 3× POST /orders tests (XSS ×2, SQLi ×1) | **`POST /api/tenants/{id}/orders` → 500 MissingGreenlet** (`orders.py:41` lazy `o.items` after `create_order` adds items without loading the relationship) | **REAL PRODUCTION BUG** |
| `test_sql_injection_does_not_drop_tables` | sync `inspect(db_session.bind)` on async engine | broken test |

---

## 2. conftest Architecture

**Root `tests/conftest.py`** (mirrors MASTER_PROMPT §11 spec verbatim):
- `TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"` — **file-based**, despite README/tests/README claiming "in-memory". Leftover `test.db` sits in the repo root.
- `setup_db` is **autouse, function-scoped** `create_all`/`drop_all` — every test rebuilds the whole schema (~35 tables). Consequences:
  - **Masks all three schema authorities**: the `scheduled_posts`/`post_insights`/`blocked_users` tables that NO migration/DDL creates (Z6 CRITICAL) exist in every test run — `test_scheduling.py` (10 tests) passes while the feature 500s on a fresh production install.
  - Masks ORM↔Alembic column drift (orders, ip_bans, audit log — Z1/Z6).
  - `users.email` uniqueness, `fb_message_id` uniqueness, `order_number` collisions — all constraint-level differences between SQLite and Postgres are invisible.
- `client` overrides `get_db` with the test session — but **runs the real middleware onion** (SecurityHeaders/SlowAPI/BotDetection/IPBan), which is good; and `app` is imported once (module import creates the real async engine against `DATABASE_URL` — the suite **cannot even collect** unless a parseable `DATABASE_URL` exists in env; with pinned SQLAlchemy a sqlite URL crashes on `pool_size` kwargs).
- Factories: `test_user`, `auth_headers` (real JWT), `test_tenant`, `test_products` (3 Egyptian products), `test_customer`, `test_conversation`. No factory libraries; no rollback isolation (relies on drop_all); no second-tenant fixture at root level (security conftest adds it, scraper forgot).
- `event_loop` session-scoped override — deprecated pattern (pytest-asyncio warns, 2,086 warnings per run).
- **property/conftest.py** replaces `setup_db` with a no-op (good performance thinking; also honest about the "table-creation flakiness").
- **security/conftest.py**: adds `second_user`/`second_auth_headers`/`second_tenant`, `isolated_rate_limiter` (a fresh **unwired** `RateLimiter`), `arbitrary_user_token` (validly-signed JWT for a non-existent user — used by 2 good tests).
- **e2e/conftest.py**: `browser` session fixture skips whole tier without Playwright; `e2e_user_and_tenant` registers via API against the live server.
- **load/conftest.py**: defines `TARGET_HOST`, `DEFAULT_USERS`, `DEFAULT_SPAWN_RATE`, `LOAD_TEST_*` — **never imported by locustfile.py** (which reads `os.getenv` directly). Dead config.
- **schema/conftest.py**: `app.openapi()` → `schemathesis.from_dict` — broken for the app's own OpenAPI 3.1.0 with the pinned-allowed schemathesis versions; and the fuzz tests never override `get_db` anyway, so every request would hit the real DB and be swallowed by `except Exception: return` (see §3).

**Mock strategy taxonomy across the suite:**
1. *Pure-function tests* (phone/address/language/prompts/order_collector/security utils) — real, no mocks. Best part of the suite.
2. *API tests with real DB* (auth/tenants/products/orders/system/idor/xss/sql) — genuine integration via `ASGITransport`.
3. *Mock-the-collaborator tests* (postiz: mocks httpx & client — reasonable; crawl: mocks `_run_crawl_inline` — acceptable scope decision).
4. *Mock-the-system-under-test tests* (prompt-injection API, xss chat) — `patch("app.ai.agent.process_customer_message")` returns a hardcoded safe string; since `process_customer_message` is what persists messages AND produces the reply, the tests assert the mock's own string. Vacuous.

---

## 3. Test Quality Audit — vacuous & weak tests

**Definition used**: a test is *vacuous* if it cannot fail for the property it claims to verify (mock guarantees the assertion), asserts nothing, accepts all outcomes, or tests code that is never invoked in production.

### 3.1 Confirmed vacuous (cannot fail)

| # | Test | Why vacuous |
|---|---|---|
| 1 | `test_prompt_injection.py::test_chat_response_does_not_contains_system_prompt` | `process_customer_message` mocked to return a clean Arabic string; forbidden-substring asserts are guaranteed by the mock. No message is even persisted (persistence lives inside the mocked function). |
| 2 | `test_prompt_injection.py::test_chat_handles_dan_jailbreak_safely` | same mock; "DAN compliance" phrases can never appear in the hardcoded reply |
| 3 | `test_prompt_injection.py::test_chat_handles_tag_spoofing_safely` | same mock; phone/email regexes checked against the mock's string |
| 4 | `test_prompt_injection.py::test_repeated_injection_attempts_handled_gracefully` | same mock; only asserts status ∈ {200,422} |
| 5 | `test_xss.py::TestXSSInChat::test_xss_in_customer_message` | same mock — the XSS payload is never stored anywhere; dashboard check finds nothing because nothing exists |
| 6 | `test_e2e/test_merchant_flow.py::test_logout_clears_session` | **no assertion at all** after navigation (ends with a comment "Should redirect to login…") |
| 7 | `test_e2e/test_order_flow.py::test_order_appears_in_dashboard_list` | the key check is literally `if customer_name not in body: pass  # ok` — cannot fail |
| 8 | `test_e2e/test_order_flow.py::test_invalid_status_transition_rejected` | `assert resp.status_code in (200, 400)` — accepts both valid and invalid behavior; only a 500 fails |
| 9 | `test_e2e/test_merchant_flow.py::test_add_product_via_dashboard_form` | entire flow inside `try/except Exception → pytest.xfail`, incl. the final `assert product_name in body`; a genuinely missing product reports as xfail, not failure |
| 10 | `test_e2e/test_customer_chat.py::test_customer_order_placement_flow` | xfails when chat fails at any step *and* when no order was extracted — the headline behavior (AI order extraction) is optional |
| 11 | `test_ssrf_protection.py::test_ssrf_blocks_decimal_localhost` | asserts only `isinstance(safe, bool)` — "must be checked" but any answer passes (and decimal/hex/octal-IP bypass nuances are exactly where the real risk is) |
| 12 | `test_ssrf_protection.py::test_ssrf_blocks_octal_localhost` | same — `isinstance` only |
| 13 | `test_ssrf_protection.py::test_ssrf_blocks_hex_localhost` | same |
| 14 | `test_ssrf_protection.py::test_ssrf_blocks_172_15` | same ("Either way, no crash") |
| 15 | `test_rate_limiting.py` — all 12 `TestRateLimiterPrimitive`/`TestRateLimitEvasionAttempts` | The `RateLimiter` is **imported by zero app code** (only tests). 12 green tests certify a defense that does not exist in the request path. Docstring admits: "The FastAPI app doesn't yet wire it into a middleware." |
| 16 | `test_ssrf_protection.py` — remaining 33 | `is_safe_url` is likewise imported by **zero app code** (Z10 grep-verified). Tests certify the dead guard, not the app. (The 4 allowlist tests additionally require live DNS — they *fail* offline.) |
| 17 | `test_prompt_injection_property.py` — 7 tests | property-test the same **unwired** detector |
| 18 | `test_xss.py::TestXSSContentSecurityPolicy::test_dashboard_has_security_headers` | near-vacuous by design: xfails if headers absent. (Currently passes — security_headers middleware is live.) |
| 19 | `test_xss.py::test_xss_in_product_name_stored_safely` (20 params) | weak-vacuous: passes if the products dashboard simply doesn't render the product (pagination/JS); no positive check that the escaped form (`&lt;script&gt;`) is present — asserting absence only |
| 20 | `test_crawl.py` 3/4 tests | mock `_run_crawl_inline` — verifies job-row bookkeeping only, never the crawl pipeline (justifiable scope, but the pipeline — with its SSRF/file:// surface — has zero tests) |

**Vacuous-by-environment:** all 12 e2e tests skip without Playwright + a running server (5 of them don't even use the browser they require — pure httpx); the 3 schema contract tests error in every configuration; the 3 xfail tests (2 login rate-limit, 1 scraping rate-limit) permanently document absent rate limiting.

**Net: of 452 tests, ≈ 50 are outright vacuous (mock-the-SUT / no-assertion / accept-all-outcomes), ≈ 52 more test dead defense code, 12 always-skip, 3 always-error, 3 always-xfail → only ~330 tests genuinely exercise live production behavior.**

### 3.2 Tests that would NOT catch the known production bugs (cross-referenced from Z1–Z10)

| Production bug (finding agent) | Why the suite misses it |
|---|---|
| Rate limiting dead — SlowAPI installed, no endpoint opts in (Z4/Z10) | Suite *documents* it via 3 xfails and 12 tests of the unwired primitive; nothing can fail |
| SSRF via `/products/import-url`, `/crawl`, order_api_service (Z4/Z5/Z7/Z9) | 37 SSRF tests target `is_safe_url` only; **no test posts a URL to any real endpoint**. Zero tests for crawl/import-url at all |
| Prompt-injection detector never called in pipeline (Z10) | The 4 "end-to-end" tests mock `process_customer_message` — the integration point is exactly what's mocked |
| Postiz process-wide singleton / cross-tenant session hijack (Z5) | All postiz tests mock `get_postiz_client` — the singleton wiring is precisely what's mocked out |
| `scheduled_posts`/`post_insights`/`blocked_users` missing from migrations (Z6) | `create_all` fabricates the tables; test_scheduling passes |
| Schema drift (orders cols, ip_bans.is_active, audit user_agent) (Z1/Z6) | Same `create_all` masking; schema contract tier (which could catch it) errors out |
| Webhook dedup race (`fb_message_id` plain index, SELECT-then-insert) (Z4/Z6) | **No test sends the same webhook twice**; no test asserts the "duplicate" sentinel; grep confirms zero references to `fb_message_id` in tests |
| Order-number collision `ORD-YYMMDD-rand(100-999)` vs UNIQUE (Z4/Z7) | test_orders uses a handcrafted order_number; nobody creates ≥900 orders/day; property tests don't touch persistence |
| Owner chat unreachable (`owner_psid` never written) (Z7) | Zero tests for owner chat commands |
| `call_order_api` never auto-dispatched; retry re-submits success (Z4/Z7) | Zero tests for order API dispatch |
| Arabizi misclassification of English-with-digits (Z3) | test_language covers only clean cases ("12345"→english); "size 7 please" not tested |
| Transliteration corrupts phone numbers (Z3) | no transliteration tests at all |
| Style-profile key mismatch (Z3) | test_style_learning asserts profile keys written, never that prompts.py reads them |
| `POST /orders` 500 MissingGreenlet (found *by this audit*, §1) | Only the security suite hits the endpoint — and those tests are red, so the signal is lost. Root suite never POSTs an order |
| FB login accepts any-app tokens (Z4) | zero facebook-OAuth tests |
| WA/IG onboarding gap — tokens in no schema (Z8) | zero tests |
| WA media IDs passed as URLs (Z8) | zero tests |

### 3.3 Things the suite genuinely does well
- **IDOR suite is real and strong**: 13 tests through the actual request path with a second tenant — matches Z4/Z7's finding that per-query tenant scoping is genuinely enforced. This is the best security file.
- **JWT attack suite is real** (17 tests, hand-forged tokens against `decode_token` + `get_current_user`); it even *documents* (via skip) that python-jose accepts no-exp tokens — an honest, self-aware test.
- **Webhook signature tests are real** (fail-closed verified for bad/missing/empty-secret).
- **Property tests of pure validators** are solid totality checks (ReDoS-size inputs, unicode, non-strings).
- **XSS via products/orders/tenant settings** are real stored-XSS probes against Jinja rendering (they'd catch an autoescape regression), modulo absence-only assertions.
- **SQL-injection suite** is real through the request path (the SQLAlchemy-parameterization claim is legitimately verified).

---

## 4. Security Test Analysis — do the 8 files verify real defenses?

| File | Tests | Verdict |
|---|---|---|
| test_idor.py | 13 | ✅ **Real** — live path, second tenant, 404-not-403 verified. Would catch regressions. |
| test_jwt_attacks.py | 17 | ✅ **Real** — alg=none/confusion/expiry/tampering/deleted-user all against production code. One documented gap (no-exp acceptance) surfaced as an honest skip. |
| test_sql_injection.py | 7 | 🟡 Mostly real (parameterization verified through API). 1 broken test (sync inspect). Would NOT catch ORM-level issues on Postgres (runs on SQLite). Indirectly **caught the POST /orders 500** — but as a red test nobody heeds. |
| test_xss.py | 25 | 🟡 Real for products/orders/tenant pages (absence-only assertions); **vacuous for chat** (mocked agent); CSP test is xfail-by-design. |
| test_prompt_injection.py | 27 | 🔴 **20 detector units + 2 detector-only = tests dead code** (detector imported by zero app modules); **4 API tests mock the SUT**. Zero verification that any injection defense exists in the live chat pipeline — which is precisely where Z2/Z3 showed raw customer text is embedded. |
| test_rate_limiting.py | 14 | 🔴 **12 tests of an unwired primitive** + 2 xfail integration tests that codify "login is unthrottled" as expected-failure. The suite *knows* brute-force protection doesn't exist and marks that knowledge green-as-xfail. |
| test_ssrf_protection.py | 37 | 🔴 All 37 test the **unwired** `is_safe_url`. Not one exercises `/products/import-url`, `/crawl`, or the order-API bridge — the actual SSRF surfaces. 4 "bypass-encoding" tests assert only `isinstance(bool)`, so even the dead guard's known holes (IPv4-mapped-IPv6, NAT64 — Z10) aren't asserted. 4 allowlist tests require live DNS (fail offline). |
| test_ssrf_protection (vs scraper) | — | The one genuinely-scrapable surface (public dashboard pages, /docs) is covered in scraper tests only for "returns 200" — consistent-behavior checks, not defense. |

**Bottom line:** of 140 security tests, ~13 (IDOR) + 17 (JWT) + ~7 (SQLi-through-API) + ~21 (XSS real subset) ≈ **58 verify live defenses**; **~52 verify dead code**; 4 mock the SUT; the rest are xfail/broken. The three middleware defenses the security suite most loudly "verifies" (rate limiter, SSRF guard, injection detector) are the three that Z10 proved are imported by zero application code. The security suite is thus an elaborate **proof-of-concept catalog for defenses that were never installed** — and its own README admits it: *"These are NOT yet wired into the FastAPI app as middleware — they're testable primitives."*

---

## 5. Load Testing (locustfile.py)

**Coverage** (11 weighted tasks, 2 user classes):
- `MerchantUser` (auth'd, think-time 1–5s): `view_products` ×3 (pages 1–3, size 50), `view_orders`, `view_conversations`, `view_stats`, `list_tenants`, `view_me`, `test_chat` ×1 (10 Egyptian-Arabic/English messages; the LLM-heavy path).
- `AnonymousUser` (weight 1, think 0.5–2s): `/dashboard/login`, `/docs`, `/openapi.json`, failed login (401/429 both counted success).
- Threshold: `events.quitting` fails the run if `fail_ratio > 10%`. **No latency (p95/p99) thresholds, no RPS floor, no error-budget on the LLM endpoint.**

**Realism assessment:**
- ✅ Good: catch_response with status-code assertions per endpoint, realistic Arabic message corpus, JWT caching, tenant auto-discovery, login-failure marking, sane wait times, headless CI example in docstring.
- 🔴 Gaps: **no webhook traffic at all** — the single highest-scale production surface (Messenger bursts, Meta retries) is never loaded; no customer-side concurrency (only merchant dashboards); `test_chat` accepts 500 *initially* then marks failure (ok) but 429 is counted success although nothing in the app can emit 429; `failed_login_attempt` treats 401 as success so **the scenario cannot detect that brute-force protection is absent** (matches Z10's finding); single-tenant focus (all users share `LOAD_TEST_TENANT_ID`) → no multi-tenant contention, no order-number collision stress, no DB-pool exhaustion across schemas; conftest config constants dead (see §2); smoke tests are hasattr-only.

**Verdict:** a competent *dashboard smoke-load* script, not a capacity model of the actual product (chat moderation at Meta-webhook scale).

---

## 6. Documentation vs Reality Audit

### README.md (625 lines)
| Claim | Reality |
|---|---|
| "two specialist models — **Rabbit v1** (Arabic) / **Rat v1** (English)" | **Fiction.** No such models anywhere; llm_client calls OpenRouter `:free` models / Gemini. Pure marketing veneer over generic LLM calls. |
| "heavy work is offloaded to a **Celery worker**… enqueues a Celery task" (webhook flow) | **False.** `webhook.py` processes messages inline via `BackgroundTasks` (same process); Celery is used only for notifications/crawl/style tasks. Z2/Z4 concur. |
| "**Owner chat commands** — update prices… from Messenger" | **Unreachable in production**: `owner_psid` is never set by any code path (Z7). |
| "**Order API bridge** … Zemest drops orders into their ERP/Shopify" | **Never auto-invoked**; only the manual `/retry-api` endpoint calls it — and re-submits already-successful orders (Z4/Z7). |
| "Voice notes … zero per-message cost" (implying WA support) | Voice/vision **broken on WhatsApp** (media IDs passed as URLs, Z8); works only where real URLs exist (Messenger attachments). |
| "auto-trained on your existing chat history across WA/FB/IG" | Style learner exists but the learned profile is **partially dead** (key mismatch — Z3) and the import endpoint has an IntegrityError path (Z3). |
| Tech stack table: "**LLM routing — LiteLLM**" | LiteLLM referenced only by **dead** `llm_gateway.py`/`indexer.py`; live path is raw httpx (Z2). |
| "Testing: pytest + pytest-asyncio + aiosqlite (**in-memory**)" / "pytest # full suite, ~120+ tests" | File-based SQLite; actual count 452; suite **not green** (10 fail + 8 error deterministically); the 6 extra tiers undocumented in README. |
| "every PR must keep the suite green" (Contributing) | **No CI exists** (no .github/, no gitlab-ci, no Makefile) — nothing enforces anything. |
| Quick start: `cp .env.example .env` | **`.env.example` does not exist** in the repo. |
| "Released under the MIT License. See LICENSE" | **LICENSE file does not exist.** |
| "Alembic … migration chain is idempotent — main.py also runs ALTER batch" | True but inverted: three competing schema authorities produce the drift Z1/Z6 documented; the ALTER batch is silent `except: pass`. |
| "best-time-to-post insights, per-post engagement analytics", Postiz `/generate` | Endpoints exist; but Postiz client is a **process-wide singleton shared across tenants** (Z5), so the feature is cross-tenant unsafe. |
| "27 governorates … per-tenant rates" | ✅ Accurate (verified by tests). |
| "webhook … under a second; echo events skipped" | ✅ Mostly accurate (fast-ACK + echo skip verified in code). |

### MASTER_PROMPT.md (695 lines)
- This is the *build spec*, and the root test suite follows §11 to the letter (fixture names, counts ≥120, pitfalls list). Aspirational-by-design, but notable deltas vs shipped code:
  - §11 prescribes `test_webhook(6): … echo-skip (no reply generated), postback routed` — **those two tests were never written**; echo-skip is pitfall #10 ("MANDATORY") yet remains untested.
  - §11 `test_webhook` count 6 vs actual 9; `test_egypt_address(13)` vs 25; counts drifted.
  - §12 ".env.example ships complete" — the file is absent.
  - §5.4 SUBSCRIPTIONS (`subscribe_instagram_to_webhook`) — dead code (Z8).
  - §14 acceptance checklist "pytest green ≥120 tests" — the root tier alone satisfies it (186 tests, green); the added tiers broke greenness and nobody re-checked.
- Net: MASTER_PROMPT is accurate about the *root* tier and the files it specifies; the later-added systems it describes (owner chat, order API, subscriptions) exist as code but not as reachable behavior.

### REAL_WORLD_TESTING_REPORT.md (400 lines)
- A tool-selection research doc (Playwright/Locust/ZAP/Pumba/Hypothesis/Schemathesis/mutmut/respx) that **correctly diagnoses the codebase's own test problem**: "Current tests … assert exact status codes / strings ('fit the code exactly'), so they pass even when real-world behaviour breaks" and "they prove the code *runs*, not that it *works*". Every later tier (e2e/load/schema/property/security/scraper) was built from its 10-scenario plan — but the implementation is where quality collapsed:
  - Report prescribes `schemathesis.openapi.from_asgi(...)` + `case.call_asgi()` — implemented instead as broken `from_dict` + nested-parametrize + nonexistent fixture.
  - Report's JWT-tamper sketch uses `/api/tenants/me` — actual tests correctly used real endpoints (better than the sketch).
  - Report's locustfile sketch hits `/api/products` (nonexistent route) — the shipped locustfile fixed this.
  - Recommends mutmut as quality gate — mutmut ships in requirements but has no config/CI; never run.
  - Recommends respx to replace "brittle unittest.mock patches" — the shipped security tests *added* the most brittle mock of all (`process_customer_message`).

### RESEARCH_CONCURRENT_LLM.md (278 lines)
- Research basis for `llm_gateway.py` (LiteLLM Router, aiolimiter, Redis quotas, per-tenant semaphores). The doc is internally honest ("litellm … not yet used for calls"), but the shipped "reference implementation" is **dead and unimportable** (aiolimiter missing from requirements, ollama service absent, cache host misconfigured — Z2). Zero tests reference the gateway. This doc describes an architecture the codebase does not have.

### tests/README.md (246 lines)
- The most honest doc in the repo: admits the 3 defense primitives are "NOT yet wired into the FastAPI app", documents the xfail rationale, gives real run commands. Still inaccurate on counts ("~230 explicit" vs 452; "Security ~120" vs 140) and its "CI integration" YAML is a recommendation with no corresponding pipeline.

---

## 7. Coverage Gaps (untested behaviors)

1. **Webhook dedup race** — no test sends the same `mid` twice; no test of the `"duplicate"` sentinel; no concurrency test of SELECT-then-insert (the exact race Z4/Z6 identified; SQLite single-writer hides it anyway).
2. **Order-number collision** — random `ORD-YYMMDD-100..999` vs UNIQUE: untested (needs ≥900 inserts or a seeded RNG test).
3. **Concurrent message processing** — no test exercises two in-flight `process_customer_message` calls for the same conversation (autoflush/double-reply risk), or concurrent status transitions.
4. **Facebook OAuth flow** — `/api/facebook/*` (login-with-Facebook, page connect, catalog sync incl. the proven `create_product` TypeError, subscription) has **zero tests**.
5. **Owner chat commands** — zero tests (feature unreachable).
6. **Order API bridge** — zero tests for `call_order_api` dispatch/retry/idempotency.
7. **WhatsApp/Instagram webhooks** — only Messenger webhook tested; IG "text_plain" typo (Z4) and WA media-ID-as-URL bug (Z8) are precisely in the untested files.
8. **Crawl/import pipeline** — mocked away; SSRF surfaces (`file://`, katana, docker socket), product extraction, tree rebuild semantics untested.
9. **Scheduler workers** — Celery tasks (publish scheduled posts, retry, style beats) have no tests; scheduling tests only cover CRUD/state endpoints.
10. **Admin panel/API** — zero tests (ip-bans, audit log, the proven `invalidate_all()` AttributeError would fail instantly if tested).
11. **Migrations** — nothing runs `alembic upgrade` in tests (drift undetectable by design).
12. **Multi-worker semantics** — in-memory rate limiter, singleton Postiz client: nothing tests behavior across >1 process (locust could, but doesn't target those paths).
13. **Auth hardening** — refresh/revocation machinery (Z4), no-exp JWT acceptance (self-documented skip), password policy: untested.
14. **Load** — no webhook/Celery/postgres under load; no p95/p99 gates.

---

## 8. Quality Ratings & Maturity

| Suite | Rating | Justification |
|---|---|---|
| Root unit/integration (186) | **7/10** | Real request-path tests, good fixtures, honest asserts (order totals, CSV detection). Minus: create_all masking, no POST /orders test (the 500 slipped through), deprecated event_loop, spec-shaped "fit the code" cases. |
| Property (30) | **6.5/10** | Genuine totality properties, good corpora (Arabic/emoji/non-string), ReDoS sizing. Minus: 1 never-passing test, no cross-validator consistency property (would have caught the phone-validator divergence), 7 tests target dead detector, "acceptable TypeError" escape hatches. |
| Security (140) | **4/10** | IDOR + JWT files are genuinely excellent (9/10 in isolation); but ~52 tests certify dead defenses, 4 mock the SUT, xfail-normalized missing rate limiting, SSRF/XSS suites never touch the real attack surfaces, and the tier is red (6 deterministic failures) yet shipped. |
| E2E (12) | **2.5/10** | Never runs in default env; 5/12 don't use the browser; catch-all xfail/skip swallows failures; 2 tests have no meaningful assertion; only login-page and page-200 checks are real. |
| Load (7 + locustfile) | **5/10** | Well-built merchant dashboard smoke-load with proper failure accounting; but no webhook/customer traffic, no latency thresholds, brute-force scenario structurally cannot fail, dead conftest, hasattr-only smoke. |
| Schema (9) | **1/10** | 3 contract tests error in every possible environment (triple-broken); 6 shape tests are trivially true; the one tier that could catch schema drift/500s across all 48 endpoints simply does not function. |
| Scraper (68) | **3/10** | Bot-UA consistency checks are fine; PII-isolation tests are real but 5 of them error on missing fixtures; the rate-limit probe is a permanent xfail; 1 never-passing test. |
| **conftest architecture** | **5/10** | Clean layering, sensible overrides, honest per-tier conftests; but function-scoped create_all/drop_all masks every migration bug (the single most consequential test-design decision in the repo), file-based "in-memory" DB, fixture reuse failure across sibling dirs. |
| **Docs accuracy** | **4/10** | tests/README is honest and useful; README is ~50% aspirational (fictional models, Celery webhooks, dead features as headlines, nonexistent files referenced); MASTER_PROMPT is a spec not a description; research docs describe unbuilt systems. |
| **Overall testing maturity** | **4.5/10** | Impressive breadth vocabulary (7 tiers, property/contract/load/security personas) over weak execution: no CI, not green, ~25% of tests vacuous or dead-code-certifying, migration/constraint layer structurally untestable by design, and the strongest signal in the repo (red security tests revealing a live 500) is being ignored. The suite proves the team *knows* what good testing looks like (their own REAL_WORLD report says it) but hasn't operationalized it. |

---

## 9. Notable New Findings (not in prior agents' reports)

1. **CRITICAL (new): `POST /api/tenants/{id}/orders` always returns 500** — `MissingGreenlet` from lazy-loading `order.items` in `_order_response` (app/api/orders.py:41) because `order_service.create_order` inserts `OrderItem` rows directly without populating the relationship and the endpoint renders immediately. Reproduced with a plain payload outside pytest. The dashboard's "create manual order" button and the e2e order-flow scenario are broken in production. Caught by 3 security tests that are failing and ignored.
2. The scraper tier **errors on 5 tests** (fixtures defined in a sibling conftest) and 1 more can never pass — the tier was never executed even once in its current form.
3. The schema tier is broken three independent ways (OpenAPI 3.1 vs schemathesis<4; `from_dict` removed in ≥4; nonexistent `client_factory` fixture) — the "contract testing" claim in tests/README is void.
4. A property test has a strategy bug (`plus if plus else ""` → `True + str`) that makes it fail on the first boolean sample — never could have passed.
5. The suite cannot even **collect** without a parseable `DATABASE_URL` env (and with pinned SQLAlchemy, a sqlite URL crashes on `pool_size`) — a hidden environmental coupling in "you don't need Postgres to run tests" (README).
6. Tests contradict docs on DB: file-based `test.db`, not in-memory; `test.db` lingers in the repo root.
7. Detector recall gap measured: 3/20 curated injection phrases missed by `detect_prompt_injection` (moot in prod — detector unwired).
