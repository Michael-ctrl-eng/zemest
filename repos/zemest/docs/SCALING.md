# Zemest Scaling Playbook — 10K → 100K users/day

Budget-first: the whole stack runs comfortably on a single 4-8 GB VPS
(Hetzner CX32-class, ~€10/mo; CX22 fits the first 1-2K tenants). The model
never runs locally — see `docs/AI-STRATEGY.md` for the provider plan.
Canonical deployment: `deploy/docker-compose.prod.yml`.

## Architecture lessons applied from Postiz

We studied the reference scheduling platform (gitroomhq/postiz-app) and
adopted the patterns that make it reliable, adapted to our FastAPI +
Postgres stack:

| Postiz pattern | What it solves | Our implementation |
|---|---|---|
| Durable workflow per post (Temporal) | a restart must never lose or double-publish a scheduled post | CAS-guarded `scheduled_posts` + 30 s coalescing sweep (`max_instances=1`) + per-job advisory locks across replicas |
| Heartbeat classification ("never started" vs "timed out") | retrying an unknown-outcome action duplicates posts | `api_status`/`payment_status` compare-and-set transitions — terminal states never regress |
| Hourly missing-posts sweep (self-healing) | dead workflows leave posts stuck in QUEUE | publish sweep re-picks any post whose due time passed and state is still `pending` |
| One worker role runs cron (`RUN_CRON`) | N replicas × cron = N duplicate jobs | compose-enforced role split (below) + `app/services/leader_election.py` per-job `pg_try_advisory_lock` as second guard |
| Versioned workflows | deploy-time changes to in-flight work | job ids + schema migrations, `revises` chains, backward-compatible columns |

## Traffic model (the honest numbers)

A "user" here is a **message-bearing customer interaction**, not a page
view. 10,000 registered merchants ≠ 10,000 concurrent requests:

| Tier | Messages/day | DB rows/day | What holds |
|---|---|---|---|
| 10K users | ~10K messages | ~30K (messages+orders+usage) | single Postgres, 2 api replicas, pgbouncer (40 conns) |
| 50K | ~50K | ~150K | + read replica, Redis-cached tenant stats, worker x2 |
| 100K | ~100K | ~300K | + partitioned `messages` by month, per-tenant pgbouncer pools |

| Signal | Value | Basis |
|---|---|---|
| Peak sustained API load | ~50 rps + spikes to ~120 rps | DAU 40% × evening peak × dashboard polling |
| Webhook traffic | ~30 rps peak | Meta message events; trainer batches |
| LLM chat turns | ~15 rps peak | ~1/2 of webhooks trigger an agent reply |

Key throughput facts from the codebase:
- Webhook ack path is signature-verify → persist → enqueue: <10 ms; the LLM
  work happens in background tasks, so webhook capacity ≈ 500+ req/s per
  replica (I/O-bound only).
- The silent trainer batches ≤400 conversations/tenant/cycle (45 s) —
  Postgres CPU is the ceiling, not the LLM.
- Rate limiting is Redis-backed (in-memory fallback per replica).

## Deployment shape (why `deploy/docker-compose.prod.yml` fits)

- **api x2** — FastAPI, 2 uvicorn workers each. I/O-bound work (DB, Graph,
  LLM round-trips) on 8 vCPU ≈ 25× headroom over the 50 rps peak.
- **web** — Next.js standalone + BFF. Owns httpOnly cookies, CSRF/Origin
  checks, and Cookie→Bearer translation; Caddy sends browser `/api/*`
  here, server callbacks (Meta/Paymob) go straight to the api replicas.
- **postgres:16 tuned** (`shared_buffers=1GB`, `effective_cache_size=3GB`,
  `max_connections=300`) fronted by **pgbouncer** transaction pooling —
  asyncpg churn under burst traffic never exhausts backend connections.
- **redis:7** AOF + LRU 512 MB — rate-limit counters and the JWT denylist
  survive restarts.
- Every hot path is indexed (WAL + `idx_messages_conversation_created`,
  `idx_products_tenant_active`, unique `fb_message_id` dedup, unique
  `users.email`, refresh-token ledger indexes — see migrations).

## Job correctness at any replica count (role split)

The load-bearing rule: **the api replicas run with
`SCHEDULER_INLINE_WORKER=false`, `SILENT_TRAINER_INLINE_WORKER=false`,
`HUEY_INLINE_CONSUMER=false`, `HUEY_EXTERNAL_WORKER=true`; exactly ONE
`scheduler` service and ONE `worker` service run them.** The compose file
hard-codes the split so it cannot be misconfigured:

- N api replicas × 45 s trainer cycle would mean N× duplicate LLM spend and
  N× duplicate order notifications; N replicas × 30 s publish cycle would
  mean **the same Facebook post published N times**.
- The `pg_try_advisory_lock(job_key)` election remains as a second guard —
  locks die with the session, so a crashed replica never wedges a job for
  more than one tick, and `max_instances=1` + `coalesce=True` dedup inside
  each process.
- The publish sweep is idempotent even without the lock: the post UPDATE
  is `WHERE status='pending' AND due_at <= now()` (CAS), so a double sweep
  can never double-post.

## Queue correctness (Huey over a shared SQLite file)

- The queue file lives on the shared `huey_data` volume
  (`HUEY_SQLITE_PATH=/huey/huey_queue.db`) mounted into **api, scheduler,
  and worker**. Huey's SQLite storage runs WAL mode with a 5 s busy
  timeout — multi-process safe on one host.
- Api replicas only *enqueue* (`HUEY_EXTERNAL_WORKER=true`) — crawls and
  order notifications execute exactly once in the worker, never inline on
  the api event loop (which would freeze request handling for a 45 s
  crawl).
- Single-process deployments (systemd, sandbox) keep
  `HUEY_INLINE_CONSUMER=true` and the embedded 1-thread consumer — one
  env var flips the shape, no code change.

## Vertical-first scaling path

1. **One box (≤10K/day)** — `deploy/docker-compose.prod.yml` as-is.
2. **Split the DB (10-30K)** — move Postgres to a dedicated instance (same
   provider, private network). Add `pg_dump` + WAL archiving nightly.
   Nothing else changes — pgbouncer just points at the new host.
3. **Read replica (30-60K)** — analytics-heavy endpoints (stats, customers
   list, calendar) move to the replica via a `DATABASE_REPLICA_URL` in
   `get_tenant_stats`. Writes stay primary.
4. **Horizontal api (60K+)** — replicas are stateless (JWT auth, Redis
   rate limits, role-split jobs). Raise `deploy.replicas`.
5. **Queue tier (100K)** — swap Huey's SQLite file for the Redis broker
   (`huey_redis.py` already supported by Huey). Crawls/media import move
   to a crawl-worker pool with per-tenant queue keys.

## Known ceilings (and their levers)

| Component | Ceiling | What gives out | Lever |
|---|---|---|---|
| api tier | ~40k users | CPU on TLS + JSON parsing | scale replicas to 4 |
| Postgres | ~60k users | connection pool saturation | read replica |
| SQLite Huey queue | ~15k users | single-file queue, no cross-host sharing | PostgresHuey (psycopg ≥ 3.2) |
| Scheduler | ~25k users | trainer cycle exceeds 45 s interval | per-tenant shards |
| LLM provider RPM | 429s, fallback replies | provider ladder + per-tenant daily budget (plans module) | add provider keys |
| Meta webhook floods | CPU on signature checks | Caddy rate limit per source IP | slowapi already Redis-backed |

## Failover posture

- api replicas: Caddy health-checks `/` every 10 s; a dead replica leaves
  rotation in ≤ 20 s. Zero-downtime deploys:
  `docker compose -f deploy/docker-compose.prod.yml up -d --no-deps api`
  rolls one replica at a time.
- Postgres: single instance — **the SPOF**. Mitigations: AOF on Redis,
  `restart: unless-stopped`, WAL archiving ready (`wal_level=replica`).
  Add a streaming standby when revenue justifies it.
- Scheduler/worker: if either dies, posts/training pause (no data loss —
  scheduled posts are DB rows picked up on restart; coalesce catches up).
  Postgres advisory locks die with the session — no wedged jobs.

## Observability (what to watch)

- `GET /` — liveness (compose + Caddy healthchecks).
- postgres: `pg_stat_activity` connection count (pgbouncer saturation
  alarm at > 80% of pool).
- Huey queue depth: `Huey dedicated worker started` log line + task
  latency (a growing crawl backlog = raise worker `replicas: 2`).
- LLM spend: `TokenUsage` rows per hour — the silent trainer is the
  dominant consumer at scale.

## What we deliberately do NOT do

- No self-hosted LLM (see AI-STRATEGY.md — a 7-8B model on CPU is
  10-60 s/reply; the hosted free tiers are faster AND free).
- No Kubernetes before ~50K/day — 2 replicas + compose is operationally
  simpler and cheaper than a control plane.
- No multi-region before Egyptian-latency data shows it matters (all
  traffic is Meta-webhook-origin; one region is fine).

## Load verification

The repo ships a Locust suite (`tests/load/`). Validate before production
traffic:

```bash
cd repos/zemest
locust -f tests/load/locustfile.py --headless \
  -u 200 -r 20 -t 5m --host https://your-domain
```

Target: p95 < 500 ms on `/api/auth/login`, p95 < 200 ms on product list
endpoints, 0 5xx.
