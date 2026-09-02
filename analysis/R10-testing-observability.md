# R10 — Testing, API Contracts & Observability (GitHub research)

**Agent:** R10 (github-research) · **Date:** 2026-09-01 · **Scope:** automated full-stack regression checks (Next BFF → FastAPI → SQLite → LLM) + runtime error visibility, with hard sandbox constraints.

---

## 1. Ground truth: what the repo already has (this decides everything)

Measured in-repo, not assumed:

| Fact | Evidence |
|---|---|
| **452 backend tests exist** (unit/property/security/e2e/load/scraper/schema) but **~10 fail deterministically, 5 scraper + 3 schema tests ERROR, and no CI exists at all** | `analysis/Z12-tests-docs.md` (measured) |
| **Schemathesis, Playwright (1.58.0), pytest-playwright, hypothesis, locust, structlog are ALL already in `requirements.txt`** | `repos/zemest/requirements.txt` lines 48–60 |
| **Playwright Chromium browsers are already downloaded** in this sandbox | `~/.cache/ms-playwright/{chromium-1200,chromium-1234,…}` |
| **structlog is declared but used by ZERO code** — every module uses stdlib `logging.getLogger(__name__)` | grep across `app/` (30+ modules) |
| `repos/zemest/.venv` **is currently wiped** (sandbox reset), so none of the testing deps are installed right now | `ls repos/zemest/.venv` → NO VENV |
| **The e2e suite targets `http://localhost:8000`** (the legacy FastAPI-rendered dashboard templates), **not the real product: Next.js on :3000 → BFF proxy → :8000** | `tests/e2e/conftest.py:33` |
| The **BFF proxy is the single wiring chokepoint**: cookie→Bearer injection, `/api/zemest/*`→`/api/*` rewrite, hop-by-hop header strip, 502 fallback, `fetchWithHeal` auto-restart of the backend daemon | `src/app/api/zemest/[...path]/route.ts`, `src/lib/backend-health.ts` |
| **`fetchWithHeal` silently restarts a dead backend** — wiring regressions can be *papered over* by auto-heal; a regression suite must flag "test needed heal" as a failure, not let it pass | `src/lib/backend-health.ts:76-95` |
| Frontend has **zero test files, no vitest/jest config, no test script** | `package.json`, `find src -name "*.test.*"` → none |
| **No Docker/podman in this sandbox** | `which docker podman` → none |
| Uptime-Kuma already recommended/adopted (Task 18/19) + `/admin/health` real-probe page + FastAPI `/` lightweight probe exist | worklog.md Task 18/19, `app/main.py:365` |

**Implication:** the "wiring regression suite" is ~80% specified already — the tools are declared deps with scaffolding present — but they are **not installed, not green, and aimed at the wrong port**. The research question is therefore not "which tool to add" but "which 2–3 to actually wire up, and what to consciously skip."

**Methodology note:** the shared sandbox IP exhausted GitHub's unauthenticated REST quota (`core: 0 remaining`), so repo metadata (stars / last-push / license / description) was scraped from `github.com` HTML + `commits.atom` feeds (not API-limited) — one HTML + one atom fetch per repo, 17 repos total, equivalent fields to the API's `/repos/{owner}/{repo}`. Data as of 2026-09-01.

---

## 2. Ranked tools (max 5)

### 1. Schemathesis — OpenAPI contract fuzzing for FastAPI ⭐ top pick

- **URL:** https://github.com/schemathesis/schemathesis
- **Stars:** 3,573 · **Last push:** 2026-08-30 (daily-active) · **License:** MIT · 9 open issues
- **What it catches:** property-based fuzzing of *every* endpoint in the OpenAPI schema that FastAPI generates for free: (a) 500s from valid inputs (unhandled exceptions — Z12 already found one real one: `POST /api/tenants/{id}/orders` → `MissingGreenlet`), (b) **response bodies that drift from the declared schema** — i.e., exactly our top bug class, backend-side contract drift the frontend/BFF will choke on, (c) content-type/status-code non-conformance, (d) 422-leak where 200 is declared.
- **Why it fits this stack:** zero extra schema to author (FastAPI's `app.openapi()` IS the contract, and pydantic models make it rich); runs fully in-process against `ASGITransport` — no server, no Docker, no network; already in `requirements.txt` and `tests/schema/` exists with fixtures (`schemathesis.from_dict(app.openapi())`).
- **Integration sketch** (modern 3.x API; also fixes the 3 ERRORing legacy schema tests Z12 found):
  ```python
  # tests/schema/conftest.py — replace hand-rolled call_async plumbing
  import schemathesis
  from app.main import app

  schema = schemathesis.from_asgi("/openapi.json", app)   # native ASGI transport

  @schema.parametrize(max_examples=25)                     # bounds runtime
  def test_api_conforms(case):
      response = case.call_asgi()                         # in-process, no port
      case.validate_response(response, checks=(
          schemathesis.checks.not_a_server_error,
          schemathesis.checks.response_schema_conformance, # body matches contract
          schemathesis.checks.status_code_conformance,
          schemathesis.checks.content_type_conformance,
      ))
  ```
  Keep the `schema`/`slow` pytest markers already defined in `pytest.ini` so it runs as a separate tier. `max_examples=25` per endpoint keeps a full sweep to ~2–4 min. Optional: `schema.config.generation(...)` / auth header via `case` headers for protected endpoints.
- **Verdict:** ✅ **ADOPT — first.** Highest bug-class coverage per unit of setup in the entire research space: the contract is already generated, the dep is already declared, the test dir already exists. Action = reinstall venv, rewrite the 3 broken tests to `from_asgi + validate_response`, add to the pre-merge run.

### 2. Playwright (Python / pytest-playwright) — the only tool that tests the FULL stack

- **URL:** https://github.com/microsoft/playwright (+ `pytest-playwright` plugin)
- **Stars:** 95,439 · **Last push:** 2026-08-29 · **License:** Apache-2.0
- **What it catches:** wiring regressions *no* lower-level test can see: the httpOnly `zemest_auth` cookie being set by the BFF login route, the BFF proxy translating cookie→`Authorization: Bearer`, the path rewrite, Next.js SSR/client fetches through `/api/zemest/*`, SQLite actually returning seeded rows, and (optionally) a real LLM round-trip with the `tokens_used > 0` marker the smoke script already uses. This is the only layer where "frontend↔backend contract drift" is directly observed instead of inferred.
- **Why it fits:** **already a python dep (playwright==1.58.0) and Chromium is already cached in `~/.cache/ms-playwright`** → setup cost ≈ `pip install` only, no browser download. `tests/e2e/` fixtures (`browser`, `page`, `base_url`, `e2e_user_and_tenant`) are written and skip-gracefully.
- **Integration sketch:**
  - **Retarget:** `E2E_BASE_URL=http://localhost:3000` (Next BFF) — the current default `:8000` tests the *legacy* FastAPI-rendered dashboard, not the product (critical fix, zero new code).
  - 5 machine-checkable journeys to replace curl-hacks from `smoke-test-fixes.sh`:
    1. **Login wiring:** fill login form → cookie `zemest_auth` set (httpOnly) → redirect to dashboard.
    2. **BFF data path:** dashboard/products page renders seeded product names (proves BFF→FastAPI→SQLite).
    3. **Chat wiring:** send message in chat UI → assistant reply appears; assert the reply is a real LLM answer (marker: non-fallback text / `is_fallback=false`), bounded by `AbortSignal.timeout`-style page timeout.
    4. **Auth-expiry path:** strip/expire cookie → protected page bounces to `/login`, no data flash.
    5. **Heal sentinel:** assert the run **did not need `ensureBackend()`** — patch/wrap it to log; if heal fired, the test *fails* (auto-heal must not mask a dead backend in regression runs).
  - Data seeding: keep `e2e_user_and_tenant` (in-process httpx) or reuse `bootstrap_local.py` demo tenant — both already exist.
- **Verdict:** ✅ **ADOPT — second.** The words "full stack" in the task brief are literally Playwright's definition. Browsers already cached in this sandbox = lowest possible setup cost for the highest-fidelity layer.

### 3. structlog — runtime error visibility with zero new services

- **URL:** https://github.com/hynek/structlog
- **Stars:** 4,937 · **Last push:** 2026-08-06 · **License:** MIT OR Apache-2.0 (dual)
- **What it catches/gives:** the "runtime error visibility" half of the brief. JSON log events with `request_id`/`tenant_id` correlation, level, module, and stack traces in one grep-able stream; error events become structured records (not interleaved human text from 30 different `logging.getLogger` calls, which is the current state — structlog is declared in requirements.txt but unused).
- **Why it fits:** **already in requirements.txt** (v24.1.0) — it's a pip-install away, pure-python, no server, no Docker; the daemon already pipes stderr → `repos/zemest/backend.log`, so the output path exists.
- **Integration sketch (~30 LOC, no changes to the 30 existing `logger = logging.getLogger(...)` lines — they get structured automatically):**
  ```python
  # app/logging_conf.py — called once from app/main.py before basicConfig
  import logging, structlog

  structlog.configure(
      processors=[
          structlog.contextvars.merge_contextvars,          # request correlation
          structlog.processors.add_log_level,
          structlog.processors.TimeStamper(fmt="iso"),
          structlog.processors.format_exc_info,             # real stack traces
          structlog.processors.JSONRenderer(),              # machine-greppable
      ],
      wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
  )
  # Bridge ALL existing stdlib loggers (zero code changes in app/):
  formatter = structlog.stdlib.ProcessorFormatter(
      processors=[structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                  structlog.processors.JSONRenderer()])
  handler = logging.StreamHandler(); handler.setFormatter(formatter)
  logging.basicConfig(handlers=[handler], level=logging.INFO)
  ```
  ```python
  # app/main.py — request correlation middleware (new, ~6 lines)
  @app.middleware("http")
  async def bind_request_context(request, call_next):
      rid = request.headers.get("x-request-id", uuid4().hex[:12])
      structlog.contextvars.bind_contextvars(request_id=rid,
                                             path=request.url.path)
      resp = await call_next(request); resp.headers["x-request-id"] = rid
      return resp
  ```
  Then bind LLM call metadata (`tokens_used`, latency, provider) in `app/ai/llm_client.py` with one `structlog.get_logger("llm")` — this yields the LLM-call telemetry the smoke script currently prints ad-hoc.
- **Verdict:** ✅ **ADOPT — third.** The only observability tool that needs no external service, and it's literally already in the lockfile. Pairs with the already-adopted Uptime-Kuma (uptime) + `/admin/health` (stack probe): Kuma answers "is it up", structlog answers "what is it screaming about".

### 4. Vitest — unit/contract tests for the BFF (frontend side of the drift)

- **URL:** https://github.com/vitest-dev/vitest
- **Stars:** 17,028 · **Last push:** 2026-08-31 · **License:** MIT · 317 open issues (high activity)
- **What it catches:** regressions in the BFF proxy logic itself — the hop-by-hop header set, cookie→Bearer injection, empty-path-segment stripping (the 307-loop guard), 502 fallback body, and `fetchWithHeal`'s retry/timeout bounds. That file is the frontend↔backend contract *implementation*, and today it has **zero tests** (no test runner exists in the frontend at all).
- **Why it fits:** TypeScript-native, mocks-first (`vi.fn`), runs route handlers by direct import (`route.ts` exports plain `GET/POST/…(request, {params})` — call them with a constructed `NextRequest`, no Next server needed). Works under the project's Bun runtime via `bunx vitest`.
- **Integration sketch:**
  ```ts
  // src/app/api/zemest/__tests__/proxy.test.ts
  import { describe, it, expect, vi } from "vitest";
  // mock "@/lib/backend-health" → controlled fetch; construct NextRequest with
  // a zemest_auth cookie; call exported POST(req, { params: Promise } as any)
  // assert: Authorization header forwarded as Bearer <cookie>, path === /api/x/y,
  // set-cookie never echoed, 502 JSON on network error, body passthrough.
  ```
  Plus a **static BFF↔OpenAPI diff test** (the cheapest drift tripwire of all): fetch `repos/zemest` OpenAPI paths (generated JSON committed at build time) and assert every literal `/api/zemest/<path>` string in `src/lib/zemest-api.ts` + route files exists in the backend schema — pure string set-diff, fails on renames/removals before any browser opens.
- **Verdict:** ✅ **ADOPT as the frontend leg** (4th priority — the backend legs 1–3 catch more per effort first). Alternative considered: **`bun test`** (https://github.com/oven-sh/bun — 95,828★, jest-compatible, *already the project runtime, zero new deps*). Choose vitest for richer mocking/coverage + Next.js ecosystem docs; fall back to `bun test` if adding devDeps offline is a problem. Either is fine — the point is: **some** runner for the proxy code.

### 5. OpenObserve — local log/trace store, when grep stops being enough

- **URL:** https://github.com/openobserve/openobserve
- **Stars:** 21,592 · **Last push:** 2026-08-31 (daily) · **License:** AGPL-3.0 (fine for internal self-host)
- **What it gives:** a **single Rust binary** (runs natively — *no Docker required*, which is what disqualifies every Sentry-style option here) that stores + UI-searches logs, metrics, and traces; ingests JSON logs over HTTP/Elasticsearch-API and **OTLP natively**, and markets LLM-observability features. Feed it the structlog JSONL stream → stack-trace search, error rate graphs, per-request trace assembly.
- **Why it fits / doesn't:** it's the natural Phase-2 home for structlog events *and* (later) OpenTelemetry spans — one binary replaces Jaeger+Loki+Grafana for our scale. But it's still a background process with its own data dir; for a 2-service stack, `jq -c 'select(.level=="error")' backend.log` covers most needs.
- **Verdict:** 🟡 **ADOPT NEXT (Phase 2), not now.** Wire structlog first in a way that's already ingestable (JSON per line, OTLP-compatible fields), then `./openobserve` later is a 10-minute upgrade. **Alternative evaluated:** siglens (https://github.com/siglens/siglens — 1,781★, Apache-2.0, single Go binary, "100x cheaper than Splunk") — same idea, smaller community, last push 2026-03-12 (5 months ago). OpenObserve wins on community (12×) and cadence.

---

## 3. Evaluated and consciously skipped (with reasons)

| Tool | URL / stars / push / license | Why skipped in this sandbox |
|---|---|---|
| **pact-python** (consumer-driven contract testing) | pact-foundation/pact-python · 682★ · 2026-08-11 · MIT | Real value for contract drift, **but**: our BFF is a transparent byte-pipe proxy (no payload reshaping), so the consumer contract ≈ the backend's OpenAPI schema — Schemathesis already enforces that at the source, with zero extra spec files to maintain. No pact-broker (needs Docker) for cross-repo verification. Revisit the moment the BFF starts reshaping/renaming backend payloads. |
| **OpenTelemetry** (py + js + contrib) | opentelemetry-python 2,608★ · contrib 1,092★ · otel-js 3,453★ · all Apache-2.0 · pushed 2026-08-28..31 | Self-collection works (ConsoleSpanExporter→file, FastAPIInstrumentor + httpx + SQLAlchemy instrumentation in contrib), but in a sandbox with no Docker there's no Jaeger/Tempo to *view* spans, and our request graph is 2 hops — request_id correlation via structlog (pick #3) delivers 90% of the debuggability for 5% of the code. OpenObserve (pick #5) ingests OTLP natively, so otel becomes the natural Phase-3 bridge. |
| **sentry-python** (SDK) | getsentry/sentry-python · 2,202★ · 2026-08-31 · MIT | The SDK is excellent and the integration is 3 lines, but **it needs a Sentry-protocol server** (DSN) to be useful; `dsn=None` is a no-op. No such server can run here (see below). Keep as the drop-in for the day a server exists; structlog error events cover visibility meanwhile. |
| **Sentry self-hosted** | getsentry/self-hosted · 9,539★ · 2026-08-28 · FSL-1.1-Apache-2.0 (source-available, not OSI) | 9+ Docker services (Postgres, Redis, Kafka, Clickhouse, …) — **no Docker in sandbox**; FSL license restricts competitive use. SKIP. |
| **GlitchTip** (Sentry-compatible, lightweight) | glitchtip.com — **main code moved to GitLab** (`gitlab.com/glitchtip/glitchtip-backend`); the GitHub `glitchtip/glitchtip` repo is a 3★ "Readme config" stub, untouched since 2022 | Docker + Postgres + Redis required → cannot run here; also GitHub-metrics are misleading post-move. Revisit after the SQLite→Postgres migration (already on the roadmap per 18-d). |
| **Siglens** | siglens/siglens · 1,781★ · 2026-03-12 · Apache-2.0 | Viable OpenObserve alternative (single Go binary), but 12× smaller community and 5-month-old last push. Covered as the alternative under pick #5. |
| pytest + pytest-asyncio + httpx AsyncClient | pytest-asyncio 1,659★ · httpx 15,463★ (BSD-3) · both 2026-active | **Already in the stack** (`conftest.py` uses `ASGITransport(AsyncClient)`) — not a research pick, but the foundation all picks 1–2 sit on. Nothing to add; just reinstall the wiped venv and fix the 10 red tests. |

---

## 4. Proposed minimal "wiring regression suite" (2–3 tools)

**The stack: Schemathesis + Playwright on the existing pytest/httpx foundation, + structlog for the error-visibility leg.** Nothing new to invent; three declared deps, one of them with browsers already cached.

```
run order (~5 min total, machine-checkable, replaces curl-hack smoke):

1. venv + pip install -r requirements.txt        (venv currently wiped)
2. python bootstrap_local.py                     (seed demo tenant — exists)
3. python daemon_backend.py start && wait-for /  (exists)
4. cd ../ && bun dev (or standalone build) :3000 (exists)
5. pytest -m "not slow and not e2e and not schema and not load"   # unit/property
6. pytest tests/schema -m schema                 # Schemathesis (rewritten, from_asgi)
7. E2E_BASE_URL=http://localhost:3000 pytest tests/e2e -m e2e     # Playwright
8. grep guard: jq 'select(.level=="error")' backend.log == 0      # structlog JSONL
```

**The five tests that earn their keep** (in priority order — the first two are the direct frontend↔backend drift tripwires):

1. **BFF auth wiring (Playwright):** login form → `zemest_auth` httpOnly cookie set → dashboard renders seeded data through `/api/zemest/*` → proves cookie→Bearer + path rewrite + DB round-trip in one test.
2. **OpenAPI conformance sweep (Schemathesis):** `from_asgi` + `validate_response` over the whole schema → no 500s, response bodies match declared pydantic shapes → the backend side of the contract.
3. **Static path diff (vitest or a 20-line python test):** every `/api/zemest/...` string in `src/lib/zemest-api.ts` exists in `app.openapi()["paths"]` → catches renames/removals in seconds.
4. **Chat/LLM wiring (Playwright):** send message → real reply with `tokens_used > 0` / `is_fallback=false` (the smoke script's VERDICT logic, as an assertion).
5. **Heal sentinel (Playwright + vitest):** regression run must complete with zero `ensureBackend()` invocations — auto-heal firing = red build, not silent success.

**Observability leg:** structlog JSON logs with `request_id`/`tenant_id` → `backend.log` (daemon already wires the stream) + existing Uptime-Kuma + `/admin/health`. OpenObserve as the optional Phase-2 store; Sentry SDK + GlitchTip deliberately deferred until a server can exist.

**One structural warning from the research:** the existing `fetchWithHeal` auto-restart means *every* test tier above can silently pass after a backend crash — the heal sentinel (test #5) is what keeps the whole suite honest.
