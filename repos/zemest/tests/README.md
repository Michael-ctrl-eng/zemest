# Zemest — Test Suite

This directory contains **6 tiers of tests** that simulate real-world usage:

| Tier | Directory | Tooling | Speed | Run Command |
|------|-----------|---------|-------|-------------|
| 1. Unit | `tests/test_*.py` | pytest | ⚡ Fast (ms) | `pytest tests/test_*.py` |
| 2. Property | `tests/property/` | Hypothesis | 🐢 Slow (s) | `pytest tests/property/` |
| 3. Security | `tests/security/` | pytest + custom | ⚡ Fast | `pytest tests/security/` |
| 4. E2E | `tests/e2e/` | Playwright | 🐌 Very slow | `pytest tests/e2e/ -m e2e` |
| 5. Load | `tests/load/` | Locust | 🔥 External | `locust -f tests/load/locustfile.py --host=http://localhost:8000` |
| 6. Scraper | `tests/scraper/` | pytest | 🐢 Slow | `pytest tests/scraper/` |
| 7. Schema | `tests/schema/` | Schemathesis | 🐌 Very slow | `pytest tests/schema/ -m schema` |

## Quick start

```bash
# Install test dependencies
pip install -r requirements.txt
playwright install chromium

# Run all FAST tests (unit + security + property)
pytest tests/ -m "not slow and not e2e and not schema and not load"

# Run a single tier
pytest tests/security/ -v
pytest tests/property/ -v

# Run with coverage
pytest tests/ --cov=app --cov-report=html
```

## Test tiers — what each covers

### 1. Unit tests (`tests/test_*.py`) — fast, isolated

The original 145 tests covering individual functions:
- `test_phone.py` — Egyptian phone validation
- `test_egypt_address.py` — address / shipping calculations
- `test_auth.py` — JWT creation/decoding, password hashing
- `test_webhook.py` — Facebook Messenger webhook signature verification
- `test_products.py` — product CRUD
- `test_orders.py` — order lifecycle
- `test_system.py` — end-to-end integration flows

**Run:** `pytest tests/test_*.py`

### 2. Property tests (`tests/property/`) — random input fuzzing

Uses **Hypothesis** to generate hundreds of random inputs and verify
our validators/parsers never crash:

| File | Property under test |
|------|---------------------|
| `test_phone_property.py` | `validate_egyptian_phone()` never raises for any string |
| `test_address_property.py` | `calculate_shipping()` never raises; cost always ≥ 0 |
| `test_order_data_property.py` | `extract_order_from_response()` never raises on random JSON |
| `test_prompt_injection_property.py` | `detect_prompt_injection()` never raises; flags known patterns |

**Run:** `pytest tests/property/ -v --hypothesis-show-statistics`

### 3. Security tests (`tests/security/`) — hacker simulation

Simulates real attack vectors and verifies defenses work:

| File | Attack simulated | Defense tested |
|------|------------------|----------------|
| `test_idor.py` | Cross-tenant data access (User B reads User A's data) | `get_tenant` dependency checks `owner_id` |
| `test_sql_injection.py` | `' OR '1'='1`, `'; DROP TABLE products; --`, UNION | SQLAlchemy parameterized queries |
| `test_jwt_attacks.py` | `alg=none`, algorithm confusion, expired, tampered payload | `decode_token()` strict alg + signature + exp |
| `test_prompt_injection.py` | "Ignore previous instructions", DAN, `[SYSTEM]` tag spoofing | `detect_prompt_injection()` + LLM mocking |
| `test_rate_limiting.py` | Brute-force login, IP rotation, UA rotation | `RateLimiter` sliding-window primitive |
| `test_ssrf_protection.py` | `169.254.169.254`, `localhost`, `10.0.0.1`, `file://` | `is_safe_url()` blocklist + DNS resolution |
| `test_xss.py` | `<script>`, `<img onerror>`, `javascript:` payloads | Jinja2 autoescaping in dashboard HTML |

**Key design principle:** Security tests **verify defenses** — they don't
actually break the system. An attack that returns 404/401/422 is a *pass*.
Only a 500 or a successful data leak is a *fail*.

**Run:** `pytest tests/security/ -v`

### 4. E2E tests (`tests/e2e/`) — real user simulation

Uses **Playwright** to drive a real browser against a running server:

| File | User journey |
|------|--------------|
| `test_merchant_flow.py` | Login → create tenant → add product → verify in list |
| `test_customer_chat.py` | Customer message → AI reply → order extraction |
| `test_order_flow.py` | Create order → status: pending → confirmed → shipped → delivered |

**Setup required:**
```bash
pip install pytest-playwright
playwright install chromium
uvicorn app.main:app --port 8000  # in a separate terminal
```

**Run:** `pytest tests/e2e/ -v -m e2e`

Tests are marked `@pytest.mark.e2e` and `@pytest.mark.slow` so they can
be excluded from fast CI runs.

### 5. Load tests (`tests/load/`) — performance under load

Uses **Locust** to simulate 1000+ concurrent users:

```bash
# Headless
locust -f tests/load/locustfile.py \
    --host=http://localhost:8000 \
    --headless -u 1000 -r 50 --run-time 5m

# Interactive (web UI at http://localhost:8089)
locust -f tests/load/locustfile.py --host=http://localhost:8000
```

The locustfile defines two user classes:
- `MerchantUser` — logs in, views products/orders, sends chat messages
- `AnonymousUser` — hits public endpoints, attempts failed logins

**Environment variables** (set before running):
- `LOAD_TEST_EMAIL` / `LOAD_TEST_PASSWORD` — merchant credentials
- `LOAD_TEST_TENANT_ID` — tenant to exercise

There's also `test_locust_smoke.py` — a pytest-runnable smoke test
that just verifies the locustfile imports cleanly. Run it with:
`pytest tests/load/test_locust_smoke.py -v -m load`

### 6. Scraper tests (`tests/scraper/`) — data extraction defense

Simulates a malicious scraper:

| File | Scenario |
|------|----------|
| `test_aggressive_scraping.py` | 100 rapid product-listing requests; verifies rate limit + no cross-tenant leak |
| `test_data_extraction_attempt.py` | Walks pagination to harvest customers/orders; verifies page_size caps + PII isolation |
| `test_bot_user_agent.py` | Rotates User-Agents (Googlebot, HeadlessChrome, curl); verifies consistent behavior |

**Run:** `pytest tests/scraper/ -v`

### 7. Schema tests (`tests/schema/`) — API contract tests

Uses **Schemathesis** to fuzz every endpoint in the OpenAPI schema:

| Test | What it verifies |
|------|------------------|
| `test_api_no_500_errors` | No endpoint returns 500 for any valid input |
| `test_get_endpoints_no_500` | GET endpoints specifically never crash |
| `test_error_responses_are_json` | All 4xx/5xx responses are JSON (not HTML stack traces) |
| `TestOpenAPISchemaShape` | Schema is well-formed (no Schemathesis needed) |

**Run:** `pytest tests/schema/ -v -m schema --hypothesis-show-statistics`

## Mutation testing with mutmut

To verify the test suite catches real bugs, use **mutmut**:

```bash
# Install
pip install mutmut

# Run mutation testing on a specific module
mutmut run --paths-to-mutate=app/utils/security.py

# View results
mutmut results
```

Mutmut will mutate the source code (e.g., `==` → `!=`, `+` → `-`) and
verify the tests catch each mutation. A low "mutation score" means
the tests are missing edge cases.

## Defense modules added

This test suite added three defense primitives in `app/middleware/`:

| Module | Purpose |
|--------|---------|
| `ssrf_protection.py` | `is_safe_url()` — blocks metadata endpoints, loopback, private IPs |
| `rate_limiter.py` | `RateLimiter` — sliding-window in-memory limiter |
| `prompt_injection.py` | `detect_prompt_injection()` — flags known jailbreak patterns |

These are NOT yet wired into the FastAPI app as middleware — they're
testable primitives. Integration as actual middleware is the next step
(documented by the `xfail` tests in `test_rate_limiting.py` and
`test_aggressive_scraping.py`).

## Test counts

| Tier | Files | Tests (approx) |
|------|-------|----------------|
| Unit (existing) | 14 | ~145 |
| Property | 4 | ~20 (×500 examples each) |
| Security | 7 | ~120 |
| E2E | 3 | ~12 |
| Load (smoke) | 1 | ~7 |
| Scraper | 3 | ~40 |
| Schema | 1 | ~7 + hundreds of fuzz cases |
| **Total** | **33** | **~230 explicit + thousands of fuzz cases** |

## CI integration

Recommended CI pipeline:

```yaml
test-fast:
  - pytest tests/ -m "not slow and not e2e and not schema and not load"

test-security:
  - pytest tests/security/ -v

test-property:
  - pytest tests/property/ -v

test-e2e:  # only on staging
  - uvicorn app.main:app &
  - pytest tests/e2e/ -m e2e

test-schema:  # nightly
  - pytest tests/schema/ -m schema

load-test:  # weekly
  - locust -f tests/load/locustfile.py --headless -u 100 -r 10 --run-time 2m
```

## Troubleshooting

### "Rate limit never triggered" (xfail)
The app doesn't yet have rate-limit middleware installed. The test is
marked `xfail` — it will start passing once middleware is added.

### "LLM not configured" (xfail/skip)
E2E tests that exercise `/api/test/chat` require a real LLM. If
`OPENROUTER_API_KEY` or `GEMINI_API_KEY` isn't set, those tests skip.

### "Playwright not installed"
Run `pip install pytest-playwright && playwright install chromium`.

### "Server not reachable" (skip)
E2E tests skip automatically if the server isn't running on
`localhost:8000`. Override with `E2E_BASE_URL` env var.

### Schemathesis tests are slow
They fuzz every endpoint with hundreds of inputs. Run them nightly,
not on every commit.
