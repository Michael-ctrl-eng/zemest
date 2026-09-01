# Task 18-b — Runtime Smoke Test: Live Backend Audit

**Agent:** 18-b (runtime smoke tester) · **Date:** 2026-08-31 23:0x · **Mode:** research + live testing, zero code changes
**Target:** FastAPI backend at `localhost:8000`, launched by `repos/zemest/daemon_backend.py` → `uvicorn app.main:app --host 0.0.0.0 --port 8000` (pid 5747, single worker, 2 threads)
**Test creds:** `owner@cairo-sneakers.com` / `OwnerPass123` → tenant `1f8c6249-26ae-42f2-b93e-c5e5ab13fa92` ("Cairo Sneakers")
**Method:** `curl -w '%{http_code} %{time_total}'`, 3 attempts per endpoint (1 for negative tests), fresh WhatsApp-format ZIP built for the import test.

---

## 1. Endpoint-by-Endpoint Test Table

| # | Endpoint | Method | Status | Time (avg) | Verdict |
|---|----------|--------|--------|-----------|---------|
| 1 | `/api/auth/login` | POST | 200 | **248–271 ms** | ✅ PASS (slow by design: bcrypt ≈ 242 ms of it) |
| 2 | `/api/auth/me` | GET | 200 | 5.2 ms | ✅ PASS |
| 3 | `/api/tenants` | GET | 200 | 10.1 ms | ✅ PASS |
| 4 | `/api/tenants/{id}/stats` | GET | 200 | 16.3 ms | ✅ PASS (but 14 sequential COUNT/SUM queries) |
| 5 | `/api/tenants/{id}/conversations` | GET | 200 | 8.9 ms | ✅ PASS (`messages: []` always in list view — detail call required) |
| 6 | `/api/tenants/{id}/conversations/{cid}` | GET | 200 | 9.3 ms | ✅ PASS (messages load correctly here) |
| 7 | `/api/tenants/{id}/customers` | GET | 200 | 20.3 ms | ✅ PASS (slowest data endpoint; N+1 — 3 queries/customer) |
| 8 | `/api/tenants/{id}/products` | GET | 200 | 7.1 ms | ✅ PASS |
| 9 | `/api/tenants/{id}/orders` | GET | 200 | 6.6 ms | ✅ PASS (empty list — zero orders in DB) |
| 10 | `/api/tenants/{id}/insights/overview` | GET | 200 | 5.5 ms | ⚠️ **SOFT FAIL** — returns `{"facebook":null,"instagram":null,"period_days":30}` (no channels connected; can't distinguish "not connected" from "no data") |
| 11 | `/api/tenants/{id}/insights/best-time` | GET | 400 | 6.1 ms | ✅ PASS (honest error: "Instagram account not connected") |
| 12 | `/api/tenants/{id}/schedule/posts` | GET | 200 | 6.3 ms | ✅ PASS (1 scheduled post) |
| 13 | `/api/tenants/{id}/style-profile` | GET | 200 | 5.6 ms | ✅ PASS (status "built", 2816 B profile — **but contaminated, see §2.3**) |
| 14 | `/api/demo/chat` | POST | 200 | 4.9 ms | ✅ PASS — instant rule-based reply (real text + product image) |
| 15 | `/api/demo/welcome` | POST | 200 | 3.2 ms | ✅ PASS |
| 16 | `/api/test/chat` | POST | 200 | 17.3 ms | ❌ **SILENT FAIL** — no LLM key → canned apology "Sorry, I'm unable to respond at the moment…" with `tokens_used: 0`; 200 OK makes the frontend look functional |
| 17 | `/api/tenants/{id}/import/chat-history` (WhatsApp ZIP) | POST | **500** | 14.7 ms | ❌ **FAIL** — `IntegrityError: NOT NULL constraint failed: conversations.customer_id` |
| 18 | `/api/tenants/{id}/rebuild-style?use_llm=true` | POST | 200 | 16.3 ms | ⚠️ PARTIAL — rebuilds, but LLM enrichment silently skipped (no key); output identical to `use_llm=false` |
| 19 | `/api/tenants/{id}/rebuild-style?use_llm=false` | POST | 200 | 14.3 ms | ✅ PASS (heuristic profile rebuild, persisted) |
| — | `/api/tenants` (no token) | GET | 401 | 2.5 ms | ✅ PASS (auth enforced) |
| — | `/api/tenants/{bad-uuid}/stats` | GET | 404 | 5.9 ms | ✅ PASS (IDOR/ownership check works) |
| — | `/` health · `/docs` · `/openapi.json` | GET | 200 | 3.7–4.9 ms | ✅ PASS |

**Totals (19 functional endpoints): 16 pass / 3 fail (1 hard 500 + 2 silent/soft).**
Slowest: `/api/auth/login` 248–271 ms (bcrypt), `/api/tenants/{id}/customers` 20.3 ms (N+1), `/api/tenants/{id}/stats` 16.3 ms (14 queries).
Fresh daemon boot-to-first-200 measured on a scratch port: **≈ 2.0 s** (imports + lifespan DDL + Redis probe ~1 s + workers).
Rate limits verified live: login 5/min per IP (a real 429 was hit during testing), demo chat 30/min.

---

## 2. Root Causes of Failures

### 2.1 `/api/test/chat` returns canned apology — 200 but no AI (root cause: missing key)
- Backend log: `ERROR [app.ai.agent] LLM call failed: OPENROUTER_API_KEY not configured`.
- `daemon_backend.py` sets **only** `DATABASE_URL` in the daemon env (line 15); no `.env` file exists in `repos/zemest`; the running process env (`/proc/5747/environ`) contains **no** `OPENROUTER_API_KEY`, no `GEMINI_API_KEY`, no `JWT_SECRET_KEY`.
- `app/ai/agent.py:164-170` catches *every* exception and substitutes `_get_fallback_response(lang)` → handler returns 200 + apology. The customer-facing message is indistinguishable from a real reply in the dashboard.
- The no-key circuit breaker (`llm_client.py:89-94`) makes this fail in <1 ms after the first attempt (60 s cooldown), so there's **no latency penalty**, but also **no signal to the operator/frontend** beyond a log line.
- Side effect: every failed call still **persists the fallback apology as an assistant message** (agent.py:190-197), so conversations fill with "Sorry, I'm unable to respond…".

### 2.2 `/import/chat-history` → 500 (root cause: NULL FK on non-nullable column)
- `app/ai/style_learner.py:455-461` builds `Conversation(customer_id=None, status="imported")` with a comment claiming "imported conversations may not have a customer" — but `app/models/conversation.py:16` declares `customer_id: Mapped[uuid.UUID]` (NOT NULL, FK to `customers.id`). SQLite raises `IntegrityError` at `db.flush()` → unhandled → 500 for **every** chat-history import (Messenger/IG/WA alike).
- The one "imported" conversation already in the DB (customer "Late Buyer") was seeded by `scripts/seed_late_chat.py`, which creates the Customer first — the API path never does.

### 2.3 Style profile / self-training contamination (root cause: fallback replies enter the training corpus)
- Rebuilt profile vocabulary now includes `"sorry"`, `"try"`, `"i'm"`, `"unable"`, `"respond"`, `"moment"`, `"please"`, `"again"`, `"shortly"` and a sample reply `لو سمحت، مقدرش أرد دلوقتي. جرب تاني بعد شوية. 🙏` — i.e. the **agent's own failure messages** are being learned as the merchant's voice.
- Chain: agent.py saves fallback text as `Message(role="assistant")` → `collect_merchant_messages()` (style_learner.py:45) selects assistant-role messages → `build_and_persist_personality()` and the 45 s silent-trainer loop ingest them → profile + future system prompts get polluted.
- `rebuild-style?use_llm=true` cannot enrich: `llm_style_extraction()` (style_learner.py:319-357) swallows all exceptions (`except Exception: return None`), so it degrades silently to heuristics — the API reports `status: "rebuilt"` either way.

### 2.4 `insights/overview` null payload (root cause: unconnected channels indistinguishable from empty)
- `scheduling.py:339/358` only populate `facebook`/`instagram` if `fb_page_id+page_access_token` / `ig_user_id+ig_access_token` exist; here they're NULL → `{"facebook": null, "instagram": null}`. Frontend renders an "insights" page that silently shows nothing. (Best-time endpoint does it right: explicit 400 with reason.)

---

## 3. Architecture Risks (ranked by severity)

| # | Severity | Risk | Evidence |
|---|----------|------|----------|
| 1 | **CRITICAL** | **JWT signed with the compiled-in default secret.** `JWT_SECRET_KEY` unset in daemon env → `config.py:22` default `"change-me-to-a-random-secret-key"`; the boot guard in `main.py:25-34` only fires when `APP_ENV=production` (it's `development` here). Anyone with the repo default can forge valid tokens for any user. | `/proc/5747/environ` has no JWT var; `config.py:18-22` |
| 2 | **CRITICAL** | **All AI is dead in this deployment** (no `OPENROUTER_API_KEY`/`GEMINI_API_KEY`), and it fails silently with 200s + human-looking apology text. The core product promise (AI agent) is non-functional while every dashboard indicator is green. | §2.1; test #16 |
| 3 | **HIGH** | **Chat-history import endpoint is 100% broken** (500 on every call) — the primary onboarding/self-training entry point. | §2.2; test #17 |
| 4 | **HIGH** | **Self-training loop learns from failure text** — the 45 s trainer + rebuild-style ingest persisted fallback apologies as merchant style, corrupting the style profile and future replies. | §2.3 |
| 5 | **MEDIUM** | **N+1 / multi-query read paths:** `list_customers` = 1 + 3×N queries (customers.py:61-74; 151 queries at default page_size 50); `get_tenant_stats` = 14 sequential scalar queries (tenant_service.py:37-155); plus `get_tenant` dependency adds a tenant SELECT per request. Fine at 8 customers (20 ms), linear blow-up at scale. | tests #7/#4 |
| 6 | **MEDIUM** | **SQLite with NullPool** (database.py:12-13; verified pool class `NullPool`): a new SQLite connection per request, no WAL pragma → single-writer lock stalls reads during the trainer/scheduler commits every 30/45 s. Production Postgres path (pool 20+10, pre_ping) exists but is unused here. | database.py |
| 7 | **MEDIUM** | **Single uvicorn process, no workers, event-loop blockers:** bcrypt verify (242 ms) runs inline in the login handler (auth_service.py:35); Redis probe at limiter construction (1 s connect timeout, Redis not running); fallback-model ladder could hold a webhook for up to ~2 min worst case (4 models × 30 s phase timeouts + backoff) with **no global deadline** on `process_customer_message`. | auth_service.py, llm_client.py:100-112 |
| 8 | **MEDIUM** | **Per-tenant concurrency gate is dead code.** `run_with_tenant_limit` (ai/concurrency.py:30) is never called by agent.py or any webhook handler → a Messenger burst spawns unbounded concurrent LLM coroutines (soft-capped only by the httpx pool's 20 connections). | grep: zero call sites |
| 9 | **LOW** | **In-memory rate-limit state** (slowapi `memory://` after Redis probe fails) resets on every daemon restart and is per-process only; login limit 5/min per IP is tight for NAT'd demo users (a real 429 was hit during this test). | backend.log; rate_limit.py:106-118 |
| 10 | **LOW** | **Startup does ~45 sequential idempotent DDL/ALTER statements** in the lifespan (main.py:40-185) with per-statement `try/except pass` — migrations are swallow-all (though the block-level failure is logged). Boot ≈ 2 s; harmless now, grows with the list. | main.py:97-101 |
| 11 | **LOW** | **Insights/channels return nulls** instead of a reason when social channels are unconnected → silent-empty UI states. | §2.4 |

**What is actually solid (production-readiness positives):**
- State is **persisted** in SQLite (`zemest_local.db`), not in-memory dicts (except the demo-agent session store `demo_agent.py:414`, which is by design ephemeral). Style profiles, `training_state` checkpoints (crash-safe resume), tokens, sessions all live in tables.
- LLM client: **pooled httpx AsyncClient** reused across calls (connect 5 s / read 25 s / write 10 s / pool 5 s; 20 max conns), 3 fallback models with 0.2–0.6 s snappy backoff, and a 60 s no-key circuit breaker.
- Rate limiting, security headers, IP bans, bot detection middleware all wired with fail-open isolation; each middleware registration is individually guarded so one broken dep can't kill boot.
- Background work (scheduler publish loop, 30 s; silent trainer, 45 s) runs as supervised asyncio tasks with per-cycle exception isolation — no Celery/Redis dependency; state checkpoints survive restarts.
- `daemon_backend.py` is a proper double-fork daemon (pidfile, log, start/stop/restart/status) and the Next.js BFF (`src/lib/backend-health.ts`) single-flight-heals it via `fetchWithHeal` — the self-heal loop is race-safe (confirmed by Task 18-c, re-verified by code read).

---

## 4. Concrete Speed Fixes (backend only — no UI changes)

1. **Fix the broken import path (also a correctness fix):** in `style_learner.import_messages_and_build_style`, create/find a `Customer` per `thread_title` (like `seed_late_chat.py` does) and pass its id to `Conversation(...)` before flushing. Converts a guaranteed 500 into a working onboarding + training trigger. *(style_learner.py:453-463)*
2. **Surface AI-disabled instead of faking it, and stop polluting training:** (a) have `agent.py` mark fallback replies (e.g. `Message.metadata={"fallback":true}` or skip persisting them entirely) and exclude them in `collect_merchant_messages()`; (b) include a `ai_configured: bool` + `reply_source: "llm"|"fallback"` field in `/api/test/chat` response (schema already free-form JSON) so operators see the truth. *(agent.py:164-197, style_learner.py:45)*
3. **Kill the N+1 in `list_customers`:** replace the per-customer trio of COUNT/SUM queries with two GROUP BY queries (`SELECT customer_id, COUNT(*), SUM(total) FROM orders GROUP BY customer_id` + one over `conversations`) and join in Python — 151 queries → 3. Expected: customers endpoint ~20 ms → <8 ms at N=50 and stays flat. *(customers.py:59-74)*
4. **Collapse `get_tenant_stats`' 14 queries:** single aggregate pass — one `SELECT COUNT(CASE WHEN …) , SUM(CASE WHEN …)` over orders, one over token_usage with `SUM(CASE WHEN usage_type='chat')` filters, one GROUP BY for top products — 14 → 4 queries; optionally add a 30–60 s per-tenant cache. *(tenant_service.py:32-155)*
5. **Set the missing environment (zero code):** add `OPENROUTER_API_KEY` (or `GEMINI_API_KEY` + provider switch), a generated `JWT_SECRET_KEY`, and optionally `REDIS_URL=` (empty) to the daemon ENV in `daemon_backend.py`'s `ENV` dict or a `.env` file. This simultaneously restores real AI generation, kills the #1 security hole, and removes the 1 s Redis probe at startup. *(daemon_backend.py:15; config.py)*
6. **Add a global deadline to the chat pipeline:** wrap `chat_completion_with_usage` in `asyncio.wait_for(…, 15)` (or cap the model-ladder budget) in `agent.py`, so a sick OpenRouter can't hold webhook responses for ~2 min; and finally *call* `run_with_tenant_limit(tenant.id, …)` in webhook/test-chat handlers so the existing 8-per-tenant gate actually engages. *(agent.py:165, webhook.py:149/253/386/506, concurrency.py:30)*
7. **SQLite pragmas (cheap local win):** issue `PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000; PRAGMA synchronous=NORMAL;` once on connect (event listener or `connect_args`), so trainer commits stop stalling reads; keep NullPool or move to Postgres for real load. *(database.py:12-13)*
8. **Move bcrypt off the event loop:** `await anyio.to_thread.run_sync(verify_password, …)` in `login_user` — login stays ~250 ms wall-clock (by design, keep the cost) but the loop stops blocking all other requests for 242 ms per login. *(auth_service.py:35; security.py:55)*
9. **Distinguish "not connected" from "no data" in `insights/overview`:** return `{"facebook": {"connected": false, "reason": "page not linked"}}` instead of `null` — no UI change needed, the BFF already passes JSON through. *(scheduling.py:332-372)*
10. **Tighten the login rate limit UX:** keep 5/min but add `Retry-After`-aware handling server-side only (already present) and consider raising to 10/min while APP_ENV=development to avoid demo 429s. *(auth.py:39-40)*

---

## 5. Self-Training Pipeline Verdict

- `/style-profile` GET: works, returns persisted profile (built_at + JSON), 5.6 ms.
- `/rebuild-style` POST: **does trigger real work** — full re-collect, smart-sample (300), heuristic extraction, persist + `knowledge_built_at` update, 14–16 ms. The `use_llm=true` branch is a no-op today (no key; exceptions swallowed), so "training" is currently heuristic-only statistics, not model learning.
- `/import/chat-history` POST: parses correctly (WhatsApp ZIP auto-detected, 10 lines parsed) but **crashes before import** on the NULL customer_id — so today the endpoint cannot store data at all, let alone train. Verified by the traceback in backend.log.
- The 45 s inline silent trainer **is** running (log: `Silent trainer worker started (interval=45s)`), does classify conversations (commerce/junk) and rebuild profiles on change — genuinely a training loop, with crash-safe checkpoints — but it is re-learning its own failure apologies (§2.3).

**Bottom line:** the read API surface is fast and healthy (5–20 ms), the auth/authz layer works, and the daemon/self-heal design is sound; but the three "AI" pillars of the product (chat generation, history import, LLM-enriched style training) are respectively silently broken, hard-broken, and contaminated — all fixable with one env var, one FK fix, and one filter.
