# R3 — Durable Background Job Queue Research (FastAPI / Python)

**Agent:** R3 (github-research) · **Scope:** research only, zero code changes
**Method:** GitHub REST API + raw source inspection (repo metadata, releases, READMEs, storage implementations, key issues). ~45 API calls total.
**Context read first:** worklog.md Task 18/18-d/19 (ARQ+Tenacity recommended; celery+redis in requirements but NO Redis in sandbox; app/tasks/inline_worker.py 30s loop + training_worker.py 45s loop; silent_trainer.py has DB-persisted training_state checkpoints + CLASSIFY_BATCH_COMMIT=25 granular commits), requirements.txt, app/scheduling/, daemon_backend.py findings.

---

## 1. Constraints that drive everything

| Constraint | Status |
|---|---|
| **Sandbox runtime** | Single uvicorn process on :8000, **SQLite (aiosqlite) + WAL + busy_timeout**, NO Redis, NO Postgres, NO Docker. `celery[redis]==5.4.0` + `redis==5.2.1` sit in requirements.txt as dead weight (no reachable broker). |
| **Prod roadmap** | Postgres will be added (docker-compose already declares pg16). Redis *may* never be needed for jobs. |
| **Workload shapes** | (1) Self-training pipeline: classify new conversations (LLM) + per-tenant style profile rebuild — long, LLM-bound, must **survive crashes and resume from checkpoints**; (2) post scheduler: 30 s "publish due posts" cron; (3) webhook LLM replies currently block the request path. |
| **Existing crash-safety** | Already application-level: `tenant.training_state` checkpoints, batch commits every 25 classifications (`silent_trainer.py:67,257`), fetchWithHeal daemon restart. What's *missing* is: durable queue of pending work, retries with backoff at the job layer, and decoupling from web-process lifetime. |
| **Valued property** | "Zero new daemons" was an explicit win in prior decisions (18-e chose SSE for exactly this reason). Embedded/in-process operation is a plus in the sandbox. |

---

## 2. Ranked top 5

### #1 — Huey (`coleifer/huey`) — the only serious SQLite-native durable queue

- **URL:** https://github.com/coleifer/huey
- **Stars:** 6,023 · **Last push:** 2026-08-31 (commits *today* — very active) · **Latest release:** 3.3.4 (2026-08-05) · **License:** MIT
- **What it solves:** full task queue — retries with backoff, retry delay, periodic tasks (crontab), scheduling at a datetime or after a delay, priority, locking, rate-limits, result storage, pipelines/chords — with **pluggable storage: Redis, Postgres, SQLite, file-system, in-memory** (`huey/api.py:1519` `SqliteHuey`, `:1526` `PostgresHuey`). Zero dependencies for the SQLite path.
- **SQLite/no-Redis compat:** **First-class.** `SqliteStorage` (`storage.py:882`) defaults to `journal_mode='wal'`, autocommit (`isolation_level=None`), deliberately short write transactions, optional `cysqlite` accelerated variant, `timeout=5` on connect. The old "database is locked" complaint (issue #445, 2019, closed) was diagnosed by coleifer as inherent single-writer SQLite with multi-*worker* configs and fixed via WAL + timeout kwargs — and our repo already runs WAL + busy_timeout (Task 18 fixes), so we're aligned.
- **Crash-safety / resume:** queue itself is a SQLite table — enqueue is durable across process death; `retries=N, retry_delay=X, retry_backoff=2` gives automatic retry with exponential backoff; periodic tasks are re-registered by the consumer at startup. A crash *mid-execution* loses that one job instance (dequeue-then-execute, like most queues without acks) — but our app-level checkpoints (`training_state`, 25-row batch commits) mean the next cycle resumes exactly where it stopped. **Huey's retries + our checkpoints = the exact resilience contract the roadmap asks for.**
- **Cron:** `@huey.periodic_task(crontab(minute='*/1'))` — replaces celery beat (whose only 2 beat entries were weekly personality + every-minute publish, and one was never even dispatched).
- **Footprint:** tiny pure-Python lib, no broker process, no Redis. Consumer can run as a **separate process (`huey_consumer`) or embedded in-process** (Consumer class / threads/greenlets) — so we can keep "zero new daemons" in the sandbox and split it out in prod with no code change.
- **Caveat:** sync API (thread/greenlet/process worker models), not asyncio-native → async trainer functions need an `asyncio.run()` wrapper inside the task body. One extra `queue.db` file (keep it **separate** from the app DB to avoid single-writer contention).
- **Integration sketch:**
  ```python
  # app/tasks/huey_app.py
  from huey import SqliteHuey, crontab
  huey = SqliteHuey("zemest", filename="data/queue.db")  # separate file from app DB

  @huey.task(retries=3, retry_delay=60, retry_backoff=2)
  def train_tenant(tenant_id: str):
      import asyncio
      from app.tasks.jobs import _train_tenant_async
      asyncio.run(_train_tenant_async(tenant_id))  # opens own session, resumes from training_state

  @huey.periodic_task(crontab(minute="*/1"))
  def publish_due_posts():
      import asyncio
      from app.tasks.scheduling_tasks import _publish_due_posts_async
      asyncio.run(_publish_due_posts_async())
  ```
  Run the consumer embedded in the FastAPI lifespan today (mirroring how inline_worker starts), or `huey_consumer app.tasks.huey_app.huey -k thread -w 2` in prod. **Migration path is the killer feature: swap `SqliteHuey` → `PostgresHuey` (same class API, different storage) the day Postgres lands — no Redis ever required.**
- **Verdict:** **ADOPT NOW (sandbox + prod).** The only candidate that is simultaneously (a) runnable today with zero new daemons, (b) durable and retrying at the job layer, (c) cron-capable, (d) has a clean SQLite→Postgres upgrade path matching our roadmap.

### #2 — APScheduler 3.x (`agronholm/apscheduler`) — persistent scheduler, not a job queue

- **URL:** https://github.com/agronholm/apscheduler
- **Stars:** 7,619 · **Last push:** 2026-08-31 · **Latest stable release:** 3.11.3 (2026-06-28) · **License:** MIT
- **What it solves:** cron/interval/date/interval-combined **triggers** with persistent jobstores. v3 datastores: **Memory, MongoDB, and SQLAlchemy (→ SQLite, MySQL, PostgreSQL)**; event brokers (v4): Postgres/Redis/MQTT. Misfire handling + coalescing, max concurrent instances per job, jitter.
- **SQLite/no-Redis compat:** **Yes** — `SQLAlchemyJobStore(url="sqlite:///…/schedule.db")` persists scheduled jobs across restarts.
- **Crash-safety / resume:** schedules survive restarts (jobstore is a table); **but no job-level retries, no acks, no result persistence** — a job that raises is logged and gone. Resume semantics must come from our app checkpoints (which exist). It upgrades *when things run*, not *whether work is guaranteed*.
- **Cron:** best-in-class (CronTrigger, interval, date, combining triggers, timezone-aware — matches the Africa/Cairo beat tz we already use).
- **Footprint:** pure Python, in-process `AsyncIOScheduler` in the FastAPI lifespan — literally a drop-in replacement for the two `while True: sleep(30/45)` loops, plus real cron for the never-dispatched weekly `rebuild_tenant_personality`.
- **Caveat:** v4 (which adds queueing semantics, workers, HA) is **explicitly pre-release — README warns "do NOT use this release in production"**. Stick to 3.11.x.
- **Integration sketch:**
  ```python
  # app/main.py lifespan
  scheduler = AsyncIOScheduler(jobstores={"default": SQLAlchemyJobStore(url="sqlite:///data/schedule.db")})
  scheduler.add_job(_publish_due_posts_async, "interval", seconds=30, id="publish-due", max_instances=1, coalesce=True)
  scheduler.add_job(run_training_cycle_once, "interval", seconds=45, id="silent-trainer", max_instances=1)
  scheduler.add_job(rebuild_all_personalities, "cron", day_of_week="sun", hour=3, timezone="Africa/Cairo", id="weekly-personality")
  scheduler.start()
  ```
- **Verdict:** **ADOPT for scheduling; do not rely on it for durable job semantics.** Pairs well with Huey (Huey = durable jobs + worker, APScheduler = cron triggers) — or alone if you want the smallest possible change. Honest limitation: it does not give you retries or off-process execution.

### #3 — Procrastinate (`procrastinate-org/procrastinate`) — the Postgres-day winner, sandbox-blocked

- **URL:** https://github.com/procrastinate-org/procrastinate
- **Stars:** 1,374 · **Last push:** 2026-08-31 (active) · **Latest release:** 3.9.0 (2026-06-20) · **License:** MIT
- **What it solves:** jobs as **rows in PostgreSQL 13+** — `FOR UPDATE SKIP LOCKED` dequeue (exactly the fix our publish-claim lacks), retries, periodic tasks, arbitrary locks (per-tenant serialization!), async + sync, Django and ASGI-friendly. Designed for "your DB is your queue".
- **SQLite/no-Redis compat:** **None — PostgreSQL 13+ only.** Cannot run in the sandbox at all. This is precisely 18-d's "re-evaluate at migration" call, confirmed.
- **Crash-safety / resume:** excellent — job state machine in the DB (todo/doing/succeeded/failed), a crashed worker leaves jobs `doing` which are retriable; retries with attempts; locks. Arguably the cleanest crash semantics of everything surveyed *if you have Postgres*.
- **Cron:** periodic tasks via its own scheduler.
- **Footprint:** psycopg connector, separate worker command (`procrastinate worker`).
- **Caveats:** bus-factor warning — README banner "**Procrastinate is looking for additional maintainers**" (discussion #748). Sync/async dual API adds conceptual surface.
- **Integration sketch (migration day):**
  ```python
  app = procrastinate.App(connector=procrastinate.AsyncPsycopgConnector(host=…))
  @app.task(queue="training", pass_context=True, retry=True)
  async def train_tenant(context, tenant_id: str): …  # reuse training_state checkpoints
  # run: procrastinate worker -q training,publish
  ```
- **Verdict:** **PLAN for prod (Postgres).** When Postgres lands, it beats ARQ for us on crash semantics and removes Redis from the architecture entirely. Not runnable today — hence #3, not #1.

### #4 — Taskiq (`taskiq-python/taskiq`) — async-native, FastAPI-friendly, but no SQLite broker exists

- **URL:** https://github.com/taskiq-python/taskiq
- **Stars:** 2,311 · **Last push:** 2026-08-31 · **Latest release:** 0.12.6 (2026-08-29) · **License:** MIT
- **What it solves:** Celery/Dramatiq-inspired **async-first** distributed task queue; sync+async tasks, type-hinted, FastAPI dependency injection integration (`taskiq-python/taskiq-fastapi`, 71★), built-in scheduler/cron labels (`taskiq/scheduler/`), pluggable middlewares.
- **SQLite/no-Redis compat:** **No.** Enumerated the entire org (21 repos): brokers exist for Redis (92★), NATS, RabbitMQ/aio-pika, Kafka, SQS, Valkey, Memphis — **no SQLite/file/disk broker**. `InMemoryBroker` is test-only; in the sandbox it would give the *same crash-blindness we have today* plus a new daemon in prod.
- **Crash-safety / resume:** depends entirely on broker (Redis/NATS JetStream etc. give durability). Cron via scheduler + label-based schedules.
- **Footprint:** core + broker package + worker process.
- **Verdict:** **SKIP for now, revisit only if we adopt NATS/Redis as strategic infra.** Technically the nicest *async* DX of the survey (our code is async), but it cannot run durably in this sandbox, and it would add a broker dependency we don't otherwise need.

### #5 — ARQ (`python-arq/arq`) — 18-d's pick; I disagree *for this deployment*, and it's now in maintenance mode

- **URL:** https://github.com/python-arq/arq
- **Stars:** 3,008 · **Last push:** 2026-04-16 (last commit of any kind; v0.28.0 same day) · **License:** MIT
- **What it solves:** asyncio job queue + RPC on Redis; cron support (`arq/cron.py`), job results, retries (max_tries + retry_delay), very lightweight, pydantic-family code quality.
- **SQLite/no-Redis compat:** **None — Redis-only.** Cannot run in the sandbox (18-d's "Redis already in stack" premise is true in *requirements.txt and docker-compose* but **false at runtime**: sandbox Redis is down, slowapi already fell back to memory://).
- **Crash-safety / resume:** jobs persist in Redis; retries supported; cron via `cron` param on functions.
- **Critical new fact 18-d did not have:** **issue #510 (Oct 2025): "Maintenance only mode" — the maintainer states the pydantic team will only fix critical security issues; expect no new work.** For *durable infrastructure* chosen for a multi-year roadmap, onboarding a maintenance-only dependency in 2026 is a bad trade when Postgres-native (Procrastinate) or SQLite-native (Huey) alternatives are actively maintained.
- **Verdict:** **SKIP as the strategic pick.** Still a *fine* library if a Redis fleet already exists and you need an async queue tomorrow — but we don't have Redis running, and we do have a Postgres roadmap. Supersede 18-d's #4 recommendation with: Huey now → Procrastinate at Postgres migration.

---

## 3. Evaluated and rejected (with reasons)

| Tool | URL | Stars | Last push | License | Why rejected for us |
|---|---|---|---|---|---|
| Celery 5 | github.com/celery/celery | 28,845 | 2026-08-31 | BSD (NOASSERTION) | v5.6.3 healthy, but Redis/RabbitMQ-only, heavyweight (beat + worker + broker = 2 new daemons), zero SQLite story, and in *this repo* it is unwired dead weight (18-d: "remove from requirements"). No SQLite compat. |
| RQ | github.com/rq/rq | 10,678 | 2026-08-31 | NOASSERTION | README: "requires Redis ≥ 5 or Valkey ≥ 7.2" — hard dependency, sync-oriented, no SQLite. |
| Dramatiq | github.com/Bogdanp/dramatiq | 5,311 | 2026-08-13 | LGPL-3.0 | RabbitMQ/Redis only; LGPL-3.0 licensing is a (soft) negative for a commercial SaaS embed; no SQLite. |
| LiteQueue-style SQLite queues | litestack/litequeue (404 / Go), sidequestjs/sidequest 1,011★ (Node), bunqueue 544★ (Bun), backlite 153★ (TS), karakeep-app/liteque 78★ (TS) | — | — | — | Searched specifically for Python SQLite-backed queues: **no viable Python library exists**. The SQLite-queue ecosystem is entirely Node/Bun/Go. Rolling our own queue table is exactly what we'd be doing with Huey — but tested and maintained by someone else. |
| Repid | github.com/aleksul/repid | 134 | 2026-08-31 | MIT | Async, extensible, AsyncAPI schemas — but 134★ and single-maintainer maturity; not infrastructure-grade for our crash-resume contract. |

---

## 4. Comparison table

| | **Huey** | **APScheduler 3.x** | **Procrastinate** | **Taskiq** | **ARQ** |
|---|---|---|---|---|---|
| Stars | 6,023 | 7,619 | 1,374 | 2,311 | 3,008 |
| Last push / release | 2026-08-31 / 3.3.4 (Aug 2026) | 2026-08-31 / 3.11.3 (Jun 2026) | 2026-08-31 / 3.9.0 (Jun 2026) | 2026-08-31 / 0.12.6 (Aug 2026) | **2026-04-16 / v0.28.0 — maintenance-only (#510)** |
| License | MIT | MIT | MIT | MIT | MIT |
| Runs in sandbox (SQLite, no Redis) | ✅ SqliteHuey (WAL) | ✅ SQLAlchemyJobStore(sqlite) | ❌ Postgres 13+ only | ❌ no SQLite broker | ❌ Redis only |
| Durable queue (survives process death) | ✅ queue table | ⚠️ schedules only, not jobs | ✅ jobs as rows (SKIP LOCKED) | broker-dependent | ✅ (in Redis) |
| Job retries + backoff | ✅ retries/retry_delay/retry_backoff | ❌ (misfire grace only) | ✅ attempts/retry | ✅ | ✅ |
| Cron / periodic | ✅ crontab periodic_task | ✅✅ best triggers (cron/interval/date, tz-aware) | ✅ periodic tasks | ✅ scheduler + labels | ✅ cron param |
| Asyncio-native | ❌ (threads/greenlets; wrap with asyncio.run) | ✅ AsyncIOScheduler | ✅ async + sync | ✅ | ✅ |
| Fits our training checkpoints | ✅ retries + checkpoint resume | ⚠️ checkpoint resume only | ✅✅ + per-tenant locks | ✅ (if broker) | ✅ (if Redis) |
| Postgres migration path | ✅ PostgresHuey — same API, drop-in | ✅ SQLAlchemy URL swap | — (already PG) | ✅ via broker swap | n/a (Redis-bound) |
| New daemon required | optional (can embed in-process) | no | worker cmd (prod) | worker cmd | worker + Redis |
| Footprint | tiny, zero deps | small | psycopg | core + broker | redis-py |
| **Verdict** | **#1 adopt now** | **#2 adopt for cron** | **#3 adopt at PG migration** | #4 skip | #5 skip (maintenance mode) |

---

## 5. Agreement / disagreement with 18-d's ARQ pick

**Where I agree with 18-d:**
- The *problem* ARQ was chosen to solve is real and correctly diagnosed: LLM + training work tied to the web process, no durable queue, failed posts never retried. "Structural fix for LLM-in-request-path" is the right framing.
- Celery as currently shipped (unwired, no queues/routes, dead max_retries, dispatch-before-commit races) is dead weight — agreed, remove or actually wire it.
- Procrastinate deferred to Postgres migration day — agreed and confirmed by my research.

**Where I disagree:**
1. **"Redis already in stack" is false at runtime.** It's in requirements.txt and docker-compose, but the sandbox has no Redis running (slowapi already pings and falls back to memory://). An ARQ adoption would mean *adding a Redis daemon to the sandbox* just to get the queue running — directly contradicting the "zero new daemons" property that Task 18-e's SSE decision deliberately preserved.
2. **ARQ entered maintenance-only mode** (issue #510, Oct 2025 — after 18-d's research window). For durable infrastructure on a multi-year roadmap, that's disqualifying when actively-maintained alternatives exist.
3. **Huey dominates ARQ on our constraint set:** same "queue + retries + cron" capability, but runs on SQLite today (embedded, no daemon), and migrates to Postgres (PostgresHuey) with a one-line storage swap — meaning **we never need Redis for jobs at all**, which removes an entire service from the production topology (7-service compose → smaller blast radius, less memory on the 1-VPS target).
4. 18-d's "Huey-sqlite documented locking #445" skip-reason is stale: #445 is from 2019, closed, and reflects multi-worker SQLite *without* WAL/timeout — the current storage defaults WAL, our app already sets WAL+busy_timeout, and a dedicated `queue.db` file sidesteps app-DB contention entirely.

**Net:** 18-d's ARQ pick should be superseded by **Huey (now) → Procrastinate (Postgres day)**. Tenacity (18-d's #1) remains fully complementary and unaffected — apply it *inside* queue task bodies for LLM/Graph call backoff.

---

## 6. Recommended adoption path (no code written — research only)

1. **Sandbox now:** add `huey` (~tiny, MIT) to requirements; create `app/tasks/huey_app.py` with `SqliteHuey("zemest", filename="data/queue.db")`; wrap `run_training_cycle_once` and `_publish_due_posts_async` as tasks (`retries=3, retry_delay=60, retry_backoff=2`); run the consumer embedded in the FastAPI lifespan (mirroring `start_inline_scheduler`'s pattern) so we keep zero new daemons. Keep `SCHEDULER_INLINE_WORKER` / `SILENT_TRAINER_INLINE_WORKER` flags as fallbacks.
2. **Immediately after:** move webhook LLM reply generation off the request path by enqueuing `train_tenant` / `classify_conversation` style jobs at dispatch time (after commit — avoids the existing dispatch-before-commit race Z11 found in the Celery paths).
3. **Prod, Postgres day:** `SqliteHuey` → `PostgresHuey` (one line), or graduate to Procrastinate if we want per-tenant locks and DB-native job state machines; either way delete `celery[redis]` + `redis` from requirements.txt unless Redis earns a role elsewhere (rate limiting, pub/sub for SSE fan-out per 18-e).
4. **Optional parallel:** APScheduler 3.11 if we want real cron (weekly personality rebuild with Africa/Cairo tz) without waiting for the queue rollout — its interval trigger is a strict upgrade over the two hand-rolled `while True: sleep()` loops.
5. **Everywhere:** Tenacity decorators inside task bodies for LLM/Graph HTTP resilience (per 18-d #1) — queue retries cover job-level failure, tenacity covers call-level failure.
