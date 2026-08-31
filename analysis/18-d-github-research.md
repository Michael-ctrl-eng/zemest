# 18-d — GitHub Research: Production-Grade Tooling for Zemest

**Agent:** 18-d (general-purpose, RESEARCH ONLY) · **Date:** 2026-08-31 · **Method:** web-search skill (18 targeted queries) + GitHub repo/API probing + cross-read of prior audit findings (Z2, Z12, worklog Tasks 18/19) to ground every recommendation in the actual codebase state.

**Grounding facts from the repo (not assumptions):**
- `daemon_backend.py` = double-fork launcher exec'ing `uvicorn app.main:app --host 0.0.0.0 --port 8000` with **no `--workers` flag** (single worker, single process).
- Live LLM path is `app/ai/llm_client.py` (raw httpx, new client per call, `sleep(1)` between fallbacks, no backoff, no budget guard on paid fallback models) — the fancier `llm_gateway.py` (LiteLLM Router) is **dead code**, unimportable (missing `aiolimiter`) with an Ollama fallback pointing at a nonexistent service (Z2 finding).
- Background work today = two **in-process asyncio loops** (`app/tasks/inline_worker.py` 30s post-publish cycle, `app/tasks/training_worker.py` 45s silent-trainer cycle) — they work, have checkpoint/resume in the DB, but die with the process and share the request event loop.
- `slowapi` is already in requirements AND wired (rate_limit.py, now fail-open to `memory://` after the Redis-fix in Task 18). `structlog` is in requirements but **unwired**. `litellm`, `celery[redis]`, `redis`, `httpx`, `asyncpg`, `psycopg2` are all already declared dependencies.
- DB is SQLite (`sqlite+aiosqlite`) in the daemon; Postgres deps + alembic exist and Postgres is the stated direction. Frontend = Next.js 15 (App Router) + React Query + bun.

---

## ⭐ ADOPT NOW — Top 5 (ranked by reliability-per-effort on our exact stack)

### 1. Tenacity — retries with exponential backoff + jitter
- **Repo:** https://github.com/will-ockmore/tenacity (formerly jd/tenacity)
- **Stars:** ~6.7k · **Last release:** regular 9.1.x releases through 2025–2026 (active, stable)
- **Why it fits us:** Z2 measured a ~3-minute worst case on the live LLM fallback chain with `time.sleep(1)` and no retry of transient 429/5xx. Meta Graph API and OpenRouter both flap; tenacity gives exponential backoff + jitter + per-exception retry policies + Retry-After-friendly wait strategies as decorators on the *existing* `llm_client.py` / publisher functions. Zero dependencies, pure Python, works on our pinned 3.9-compat stack.
- **Effort:** **S** (decorators on ~4 call sites: LLM completion, Graph send, crawl fetch, Postiz client).
- **Risk:** Low. Mature (10+ years of lineage via retrying). Watch out for retrying non-idempotent POSTs (send-message) — cap attempts at 2–3 and only retry on connect/429/5xx.

### 2. LiteLLM — **SDK Router mode** (NOT the proxy server)
- **Repo:** https://github.com/BerriAI/litellm
- **Stars:** ~57.7k (measured in this research pass) · **Last release:** v1.98.0 within the last week; ~1,449 releases — extremely active
- **Why it fits us:** The repo *already contains* a half-built LiteLLM Router gateway (`llm_gateway.py`) that was never wired. Finishing it in-process gives us: model fallback chain with per-model retries, **budget caps** (fixes Z2's "2 of 3 fallbacks are PAID models with no budget guard" cost risk), token/cost tracking (a `token_usage` model already exists in our schema), and concurrency limits via Router settings. Zero new infra: it's already in `requirements.txt`.
- **Effort:** **M** (finish wiring the existing gateway: add `aiolimiter`, delete the dead Ollama fallback, port `llm_client.py` call sites, keep one thin wrapper for OpenAI-compatible direct mode as escape hatch).
- **Risk:** Medium. Very frequent releases = occasional breaking changes; large dependency tree (already paid, since it's installed); pin the version. **Explicitly skip the standalone Proxy server** (see skip list).

### 3. Uptime-Kuma — external watchdog + public status page
- **Repo:** https://github.com/louislam/uptime-kuma
- **Stars:** ~84k+ (confirmed) · **Last release:** frequent 1.23.x releases, active maintenance
- **Why it fits us:** Pain point #1 is "sandbox restarts kill the backend; self-heal is crude." A *separate* monitor that pings `/health` + the frontend every 30–60s, keeps history, sends Telegram/WhatsApp/email alerts, and serves a branded public status page (we already ship a `/status` frontend page that currently has nothing behind it). Push monitors can also verify the daemon process from inside. Single Docker container, ~100–200MB RAM.
- **Effort:** **S** (one `docker run`, add monitors for :8000/health, :3000, and a push monitor inside the daemon).
- **Risk:** Low. Single-node SQLite-backed itself — fine for its job.

### 4. ARQ — async-native Redis task queue (the real job queue)
- **Repo:** https://github.com/python-arq/arq
- **Stars:** ~2.4k · **Last release:** 0.26.x (2024) — stable but slow-moving (samuelcolvin of Pydantic fame)
- **Why it fits us:** The single biggest architectural gap: **LLM calls in the webhook request path** and self-training jobs tied to the web process. ARQ is asyncio-native (matches our async SQLAlchemy stack — Celery/Dramatiq/RQ are sync-first), needs only Redis (already in our stack & docker-compose), and has exactly the three primitives we need: `retry` with exponential backoff (webhook processing), `cron_jobs` (post scheduler — replaces the 30s inline polling loop), and long-running jobs (self-training pipeline — the silent trainer's DB checkpoints already provide resumability, ARQ provides the process isolation + persistence).
- **Effort:** **M** (define `WorkerSettings`, move webhook reply generation + `run_training_cycle_once` + post publishing into task functions, keep inline workers as fallback via a setting like the existing `SCHEDULER_INLINE_WORKER` pattern).
- **Risk:** Medium-low. Low commit velocity is the main concern; mitigation: tiny codebase (~1 file of core), Taskiq (see skip list) is the drop-in escape hatch, and the inline-worker code stays as a degraded mode.

### 5. Granian — Rust ASGI server (drop-in uvicorn replacement)
- **Repo:** https://github.com/emmett-framework/granian
- **Stars:** ~3–4k · **Last release:** active 2.x line through 2025–2026
- **Why it fits us:** Benchmarks consistently show ~20–50% higher throughput than uvicorn for CPU-bound workloads and parity or better for I/O-bound. It's a single Rust wheel, no new Python deps, supports ASGI + HTTP/1.1/2 + WebSockets, and offers `--workers N` and `--blocking-threads` tuning in one binary. Swap = changing one `os.execve` line in `daemon_backend.py`.
- **Effort:** **S** for 1:1 swap; **M** if enabling multi-workers (see caveat).
- **Risk:** Medium. **Caveat that MUST ship with it:** (a) SQLite + multiple workers = lock storms — enable WAL + `busy_timeout` first or stay at 1 worker until Postgres; (b) our in-process `inline_worker`/`training_worker` loops would run in *every* worker → duplicate posts/training — requires a DB/env leader lock. Until Postgres lands, run granian with 1 worker (still gains the faster core) and treat `--workers 2` as the Postgres-day payoff.

---

## 📅 ADOPT NEXT SPRINT — 5

### 6. Sentry SDK (Python) — error tracking, free tier
- **Repo:** https://github.com/getsentry/sentry-python · **Stars:** ~2k · **Release:** constant (very active)
- **Why:** Z12 proved the suite isn't green and there is no CI — production errors currently vanish into `backend.log`. Sentry captures unhandled exceptions per request, release-tagged. S effort (init + FastAPIIntegration + `traces_sample_rate=0.1`). **Risk:** low; needs outbound HTTPS to sentry.io (self-host is heavy — don't).

### 7. prometheus-fastapi-instrumentator — `/metrics` endpoint
- **Repo:** https://github.com/trallnag/prometheus-fastapi-instrumentator · **Stars:** ~1k · **Release:** v8.1.0, active (regular releases through 2025–2026)
- **Why:** 3 lines of code → request latency histogram, status-code counts, in-flight requests per endpoint at `/metrics`. Exposes exactly what we need to answer "is the LLM call slowing the webhook path?" with numbers. Only dep: `prometheus-client`. S effort. **Risk:** low. (Pair with a tiny Prometheus/Grafana container later, or just curl the endpoint in Beszel checks.)

### 8. Instructor — Pydantic-validated structured LLM outputs
- **Repo:** https://github.com/567-labs/instructor · **Stars:** ~10k · **Release:** active 1.x line
- **Why:** Our order-collector parses JSON blocks out of LLM replies with regex (fragile); the silent trainer's optional LLM deep-extract is hand-rolled. Instructor wraps the *existing* httpx/OpenAI-compatible client (works with LiteLLM Router from Adopt-Now #2) and returns validated Pydantic models with automatic re-ask on validation failure. Lightweight (pydantic + your client). S–M effort. **Risk:** low-medium; adds one retry-reask loop to LLM latency — cap `max_retries=2`.

### 9. Beszel — lightweight server + Docker metrics with alerts
- **Repo:** https://github.com/henrygd/beszel · **Stars:** ~12k · **Release:** active through 2026 (hub + tiny Go agent)
- **Why:** Complements Uptime-Kuma (which watches *endpoints*) with *host/container* CPU, memory, network history + alerting — "lighter Grafana+Prometheus" explicitly built for a single VPS. Catches the "SQLite eating RAM / swap thrash" class of failure before it becomes downtime. S effort (hub container + agent on VPS). **Risk:** low; young project but Go binaries, minimal surface.

### 10. Frontend perf pack — bundle analysis + query devtools + API-route tests
- **@next/bundle-analyzer:** https://github.com/vercel/next.js (subpackage; npm `@next/bundle-analyzer` v16.3.3 published this month, Vercel-maintained) — visualize route-level JS in `ANALYZE=true next build` (webpack mode; Next 15 uses webpack for builds by default). **S.**
- **hashicorp/nextjs-bundle-analysis:** https://github.com/hashicorp/nextjs-bundle-analysis (~800★, HashiCorp-maintained) — GitHub Action that comments per-PR bundle deltas + fails on budgets; this also seeds the CI we currently lack entirely (Z12). **S.**
- **@tanstack/react-query-devtools:** https://github.com/TanStack/query (repo ~44k★, very active; devtools ship in-package) — we already run React Query; the devtools panel exposes cache staleness, retries, waterfalls in the dashboard chat/conversations views. Dev-only, zero prod bundle cost. **S.**
- **Vitest:** https://github.com/vitest-dev/vitest (~15k★, very active) — standard for testing Next.js API routes (our BFF `/api/zemest/*` proxies have zero tests); fast, TS-native. **M.**

---

## 🚫 SKIP — with reasons

| Tool | Repo | Why skip (for us, now) |
|---|---|---|
| **fastapi-limiter** | long2ice/fastapi-limiter (~600★) | slowapi already in requirements *and wired* (fail-open memory fallback). fastapi-limiter hard-requires Redis (breaks our Redis-less sandbox mode), less maintained, per-route decorators don't cover shared-limits across endpoints. Action: extend slowapi coverage per-tenant instead. |
| **hypercorn** | pgjones/hypercorn (~1.6k★) | Slower than uvicorn/granian in every comparison we found; HTTP/3 is its only card and we terminate TLS at Caddy anyway. No reason to exist in our stack. |
| **Celery (in-repo)** | celery/celery (~25k★) | Already proven dead weight: declared in requirements, celery_app.py exists, wired into *nothing* in the live daemon. Sync-first worker model fights our async SQLAlchemy stack (MissingGreenlet-class bugs), beat+broker+result-backend is 3 services to babysit on one VPS. ARQ replaces it with 1 process. Action: remove from requirements to slim the image (it drags in kombu/billiard/vine). |
| **Dramatiq** | Bogdanp/dramatiq (~4.5k★, active) | "The better Celery" — but still sync workers; our whole backend is asyncio (aiosqlite/asyncpg, httpx.AsyncClient, in-process loops). Would force thread-offload or process-per-task against async DB sessions. |
| **RQ** | rq/rq (~10k★) | Sync, Redis-only, no cron, retries are manual. No advantage over ARQ for an async codebase. |
| **Procrastinate** | procrastinate-org/procrastinate (~1.9k★, active) | Elegant (jobs = Postgres rows, no Redis, retries + cron built in) but **requires Postgres ≥13**; we're on SQLite today. Revisit the day the Postgres migration lands — it may then beat ARQ (no Redis dependency). Noted as conditional. |
| **Huey (SQLite jobstore)** | coleifer/huey (~5k★, maintained) | SQLite backend has documented "database is locked" failures under concurrency (issue #445) — exactly our load shape (webhook writes + trainer writes + scheduler writes on one SQLite file). Redis-backed huey would work but is sync; ARQ wins. |
| **APScheduler** | agronholm/apscheduler (~6.4k★) | Overlaps the already-working `inline_worker` 30s loop; 4.0 has been in alpha for ~3 years (issue #803 et al.); 3.x is in maintenance mode. Adds a jobstore to babysit and still dies with the process — no persistence win over the DB-checkpointed posts table we already have. |
| **LiteLLM Proxy (server mode)** | BerriAI/litellm | A second always-on service with its own DB, config, admin UI, and a history of CVEs/breaking proxy changes; on a single VPS that's pure ops tax. The in-process SDK Router (Adopt-Now #2) delivers ~90% (fallback/retry/cost) at zero infra. |
| **OpenTelemetry (full SDK)** | open-telemetry/opentelemetry-python (~2k★ per repo, 30+ instrumentation packages) | Heavy dependency fan-out, needs a collector (Jaeger/Tempo/Alloy) to be useful — overkill for one VPS. Sentry + instrumentator + Beszel + Kuma cover ~90% of the signal at ~10% of the weight. Revisit at multi-node scale. |
| **aiobreaker** | arlyon/aiobreaker (~200★) | Effectively unmaintained since ~2020; pybreaker port to asyncio. |
| **purgatory** | mardiros/purgatory (~120★, typed, sync+async) | Nice library, but redundant: tenacity (retries) + LiteLLM Router (fallback) already implement breaker semantics for our two flaky dependencies. Adopt only if Graph-API flapping recurs after tenacity. |
| **outlines** | dottxt-ai/outlines (~10k★, active) | Grammar-constrained decoding for *local* models (transformers/llama.cpp/vLLM). We call hosted APIs (OpenRouter/Gemini) — constrained decoding isn't available on that wire; JSON-mode + instructor is the right pattern. |
| **distilabel** | argilla-io/distilabel (~4k★) | Synthetic-data/feedback research pipelines with heavy deps. We have real customer chat corpora and a working pure-CPU classifier — synthetic generation would be solving a problem we don't have. |
| **glance** | glanceapp/glance (~37k★) | Beautiful, but it's a *personal feed dashboard* (RSS/Reddit/stocks), not ops monitoring. Kuma (external uptime) + Beszel (host metrics) own our use case. |
| **dozzle** | amir20/dozzle (~7k★, active) | Docker-only log viewer; our daemon runs as a bare-metal double-fork process in the sandbox. Revisit when the VPS deployment goes docker-compose (the repo already has one). |
| **taskiq** | taskiq-python/taskiq (~1.6k★, active) | Genuinely good async-native alternative with first-class FastAPI integration — skipped only to avoid a two-queue decision. Designated fallback if ARQ stalls. |
| **httpx-retries** | will-ockmore/httpx-retries (small, ~2025+ active, PyPI 0.6.x) | Transport-level httpx retries work, but tenacity is the more mature/flexible choice (custom wait strategies, per-exception policy, works around non-HTTP failures too). One retry mechanism, not two. |
| **aiohttp** | aio-libs/aiohttp (~15k★) | We're already all-in on httpx (AsyncClient, in requirements). No win from switching; httpx's transport-retry hooks + tenacity cover resilience. |
| **svix** | svix/svix-webhooks (~4k★) | A webhook *sending* service (with receiver verification docs). We *receive* Meta webhooks — their docs are the best reference for idempotency-key patterns, but the product doesn't apply. |
| *pymessbot / fbm-signature* | — | No maintained third-party Messenger-signature library exists worth adopting; verification is (correctly) ~10 lines of stdlib `hmac` — which our repo already implements and tests. |

**Webhook reliability pattern (no tool needed — recommendation):**
1. Read the **raw body** before any JSON parse; compute `hmac.new(APP_SECRET, raw, sha256).hexdigest()` and compare with `hmac.compare_digest` against `X-Hub-Signature-256` (strip the `sha256=` prefix). Already implemented in `app/api/webhook.py` + covered by `test_webhook.py` (9 tests) — keep fail-closed.
2. **Idempotency:** Meta retries webhooks on any non-2xx/slow response. Z2 found the current dedupe is SELECT-then-INSERT with **no unique constraint on `fb_message_id`** — a Meta retry race produces duplicate replies/orders. Fix = DB unique index + `INSERT OR IGNORE`-style insert (SQLite) / `ON CONFLICT DO NOTHING` (Postgres), keyed on the platform message id. This is the highest-leverage *code* fix in the whole webhook area.
3. **Queue pattern:** verify signature → persist event row (idempotent) → return 200 within <5s → process via ARQ job (retry w/ backoff) → send reply through the Graph API with tenacity. The 200-first shape is what Meta's platform demands anyway.

---

## Detailed findings by research area

### 1. FastAPI production hardening
- **Rate limiting:** slowapi (laurentS/slowapi, ~1.5k★, stable, production-tested wrapper around `limits`) vs fastapi-limiter (long2ice, ~600★, pyrate-limiter, Redis-required). **Winner for us: slowapi** — already installed, already wired with memory fallback, supports shared limits across endpoints and per-tenant key functions. Gap to close: apply to webhook + auth + LLM-proxy routes with tenant-scoped keys.
- **Server:** granian (Rust, ~3–4k★, active) > uvicorn ~9.5k★ (default, fine) > hypercorn (~1.6k★, skip). Granian's 20–50% CPU-bound throughput edge is real; the deciding factor for us is the single-binary + `--workers` story on the VPS. Multi-worker must wait for SQLite WAL/Postgres + leader lock on inline workers (documented in Adopt-Now #5).
- **Monitoring:** Sentry (S) + prometheus-fastapi-instrumentator (S) + structlog **wiring** (already in requirements — configure JSON renderer with tenant_id/request_id context, ~1h job) = 90% of APM value. Full OpenTelemetry = skip (weight/collector).
- **structlog** (hynek/structlog, ~3.7k★, active): note the sentry-python structlog integration issue (#4417) is still open — bridge via a processor that forwards warning+ events to `sentry_sdk` if needed.

### 2. Background jobs (single VPS, SQLite-today/Postgres-tomorrow)
| Candidate | Async | Broker/Store | Retries w/ backoff | Cron | Verdict |
|---|---|---|---|---|---|
| **ARQ** ~2.4k★ | ✅ native | Redis (in stack) | ✅ (`max_tries` + exp) | ✅ `cron_jobs` | **Adopt now** |
| Taskiq ~1.6k★ | ✅ native | Redis/PG/etc. | ✅ | ✅ schedules | Fallback if ARQ stalls |
| Procrastinate ~1.9k★ | ✅ | **Postgres only** | ✅ (retry job def) | ✅ recurring | Re-evaluate at Postgres migration |
| Celery ~25k★ | partial | Redis/Rabbit | ✅ | beat | Skip (unwired, sync friction, 3 services) |
| Dramatiq ~4.5k★ | ❌ sync | Redis/Rabbit | ✅ | middleware | Skip (sync vs our async DB) |
| RQ ~10k★ | ❌ sync | Redis | manual | ❌ | Skip |
| Huey ~5k★ | ❌ sync | redis/**sqlite**/fs | ✅ | ✅ | Skip (sqlite backend locking — #445) |
| APScheduler ~6.4k★ | partial | memory/sqlalchemy | ❌ | ✅ | Skip (overlaps inline_worker; 4.0 alpha-forever) |

Mapping to our three job shapes: **self-training** (long, resumable) → ARQ job + the trainer's existing DB checkpoints (already crash-resumable per Task 19); **post scheduler** (cron-like) → ARQ `cron_jobs` (or keep inline worker as degraded mode); **webhook retries** → ARQ `retry` + exponential backoff, idempotency at the DB layer.

### 3. LLM gateway/routing
- **LiteLLM SDK Router** (57.7k★, v1.98.0 weekly): the strategic choice — we own half the implementation already (dead `llm_gateway.py`). Router gives: fallback chain, retries, cooldowns on failing deployments, per-deployment rpm/budget caps, `litellm.completion` cost callback → our `token_usage` table. **Bundle weight:** heavy dep tree, but already installed via requirements — no marginal cost.
- **Direct OpenAI-compatible httpx + tenacity:** the minimal path (what we do now + retries/pooling). Legitimate to keep as the code path for one pinned provider; but multi-provider fallback + cost caps is exactly LiteLLM's job.
- **Proxy mode:** skip (ops tax on one VPS, CVE history, extra DB).

### 4. HTTP client resilience
- **httpx** stays (already async everywhere). Add ONE module-level shared `AsyncClient` with `httpx.Limits(max_connections=20, max_keep_alive_connections=10)` and sane timeouts (`httpx.Timeout(30, connect=5)`) — kills the new-client-per-call overhead Z2 flagged. Code change, not a tool.
- **tenacity** (Adopt #1) for retry policy; **httpx-retries** skipped (one retry system).
- Circuit breakers: aiobreaker (stale) / purgatory (fine but redundant). LiteLLM Router's cooldown + tenacity's `stop_after_attempt` cover breaker semantics for both LLM and Graph API. Only adopt purgatory if flapping persists.

### 5. Next.js 15 performance tooling
- Bundle: `@next/bundle-analyzer` (Vercel, v16.3.3, current) for local route-level analysis; `hashicorp/nextjs-bundle-analysis` (~800★) for CI budget gates — also seeds our missing CI (Z12: "no CI exists"). Note: with Next 15, run webpack builds for the analyzer (Turbopack analyzer lands in 16.1+).
- React Query devtools (TanStack Query ~44k★): dev-only panel; we already depend on the family. 
- Vitest (~15k★) for `/api/*` route tests (BFF proxies + calendar ICS route are untested today).

### 6. Webhook reliability (Messenger/IG/WA)
- Signature: stdlib HMAC (already correct in repo; keep fail-closed, raw-body, `compare_digest`). No third-party lib (none maintained; pymessbot/fbm-signature don't exist as real projects).
- Dedupe: unique index on platform message id + insert-ignore (fixes the Meta-retry duplicate-reply race Z2 found) — this is the pattern Meta's own docs and Svix's idempotency guidance converge on ("treat message id as idempotency key; drop repeats").
- Queue: verify → persist (idempotent) → 200 → ARQ process. Meta requires fast ACK; our current inline processing risks timeouts → retries → duplicates.

### 7. Self-hostable observability (single VPS)
- **uptime-kuma** (84k★, very active): endpoint uptime + alerts + status page → **adopt now**.
- **beszel** (~12k★, active): host/Docker CPU/RAM/net history + alerts → next sprint.
- **dozzle** (~7k★): real-time Docker logs → skip until Dockerized (currently bare-metal daemon; logs go to `backend.log`).
- **glance** (~37k★): personal feeds dashboard → skip (not ops).
- Combined: Kuma (outside-in) + Beszel (inside-out) + Sentry (errors) + instrumentator (`/metrics`) ≈ full-stack observability for ~1 vCPU and <500MB RAM — appropriate weight for one VPS.

### 8. AI agent frameworks for the self-training classifier
- **Keep the pure-Python classifier** (`chat_classifier.py`, Task 19) as the workhorse — zero deps, CPU-fast, explainable, already tested (7 tests).
- **instructor** (~10k★, active): adopt for the LLM-touched edges — order extraction (replacing regex JSON-block parsing) and silent-trainer deep-extract — giving validated Pydantic models + auto-reask. Small dep (pydantic + existing client). Works over LiteLLM Router.
- **outlines** (skip: local-model constrained decoding), **distilabel** (skip: synthetic data we don't need — we have real corpora).

---

## Integration sequence (suggested)

1. **Day 1 (all S):** tenacity on LLM/Graph/crawl calls · shared httpx AsyncClient with limits/timeouts · uptime-kuma container + health monitors · wire structlog JSON logging (already installed).
2. **Week 1 (M):** LiteLLM Router wiring (finish `llm_gateway.py`, budget caps, cost → `token_usage`) · granian 1-worker swap in `daemon_backend.py` (keep uvicorn line commented as fallback).
3. **Sprint 1 (M):** ARQ worker process + move webhook LLM replies & trainer cycles into jobs (keep inline workers behind settings flags as degraded mode) · unique index on `fb_message_id` (the dedupe fix) · SQLite WAL + busy_timeout.
4. **Sprint 2 (S/M):** Sentry, instrumentator `/metrics`, Beszel, instructor on order-extraction, frontend perf pack + CI bundle budgets.
5. **Postgres migration day (later):** re-evaluate Procrastinate vs ARQ; enable granian `--workers 2` + leader lock.

## Sources (primary)
GitHub repos linked above; granian/uvicorn/hypercorn comparison (blog.hashhackers.com, deployhq.com, gdevops.frama.io); task-queue landscape (aleksul.space "Choosing a Python task queue", judoscale.com, lab.abilian.com, steventen/python_queue_benchmark); LiteLLM releases (docs.litellm.ai/release_notes, repo); Meta webhook docs (developers.facebook.com — X-Hub-Signature-256); Svix idempotency/dedup guides; uptime-kuma/dozzle/glance/beszel repos + selfhosted community threads; @next/bundle-analyzer npm (v16.3.3) + hashicorp action repo; trallnag/prometheus-fastapi-instrumentator (v8.1.0); huey SQLite-locking issue #445; APScheduler 4.0 issue history (#803).
