# Zemest Scaling Playbook — 10K → 100K users/day

Budget-first: the whole stack runs comfortably on a single 4-8 GB VPS
(Hetzner CX32-class, ~€10/mo; CX22 fits the first 1-2K tenants). The model
never runs locally — see `docs/AI-STRATEGY.md` for the provider plan.

## Architecture lessons applied from Postiz

We studied the reference scheduling platform (gitroomhq/postiz-app) and
adopted the patterns that make it reliable, adapted to our FastAPI +
Postgres stack:

| Postiz pattern | What it solves | Our implementation |
|---|---|---|
| Durable workflow per post (Temporal) | a restart must never lose or double-publish a scheduled post | CAS-guarded `scheduled_posts` + 30 s coalescing sweep (`max_instances=1`) + per-job advisory locks across replicas |
| Heartbeat classification ("never started" vs "timed out") | retrying an unknown-outcome action duplicates posts | `api_status`/`payment_status` compare-and-set transitions — terminal states never regress |
| Hourly missing-posts sweep (self-healing) | dead workflows leave posts stuck in QUEUE | publish sweep re-picks any post whose due time passed and state is still `pending` |
| One worker role runs cron (`RUN_CRON`) | N replicas × cron = N duplicate jobs | `app/services/leader_election.py`: per-job `pg_try_advisory_lock` — one replica wins each tick, others skip; no central coordinator |
| Versioned workflows | deploy-time changes to in-flight work | job ids + schema migrations, `revises` chains, backward-compatible columns |

## Capacity math (the honest numbers)

A "user" here is a **message-bearing customer interaction**, not a page view:

| Tier | Messages/day | DB rows/day | What holds |
|---|---|---|---|
| 10K users | ~10K messages | ~30K (messages+orders+usage) | single Postgres, 2 web replicas, pgbouncer (40 conns) |
| 50K | ~50K | ~150K | + read replica, Redis-cached tenant stats, worker x2 |
| 100K | ~100K | ~300K | + partitioned `messages` by month, per-tenant pgbouncer pools |

Key throughput facts from the codebase:
- Webhook ack path is signature-verify → persist → enqueue: <10 ms; the LLM
  work happens in background tasks, so webhook capacity ≈ 500+ req/s per
  replica (I/O-bound only).
- The silent trainer batches ≤400 conversations/tenant/cycle (45 s) —
  Postgres CPU is the ceiling, not the LLM.
- Rate limiting is Redis-backed (in-memory fallback per replica).

## Vertical-first scaling path

1. **One box (≤10K/day)** — `docker-compose.prod.yml` as-is: 2 web
   replicas + worker + postgres + pgbouncer + redis + postiz on one VPS.
   Postgres: `max_connections=200`, pgbouncer `transaction` mode — the
   async pool never starves.
2. **Split the DB (10-30K)** — move Postgres to a dedicated instance (same
   provider, private network). Add `pg_dump` + WAL archiving nightly.
   Nothing else changes — pgbouncer just points at the new host.
3. **Read replica (30-60K)** — analytics-heavy endpoints (stats, customers
   list, calendar) move to the replica via a `DATABASE_REPLICA_URL` in
   `get_tenant_stats`. Writes stay primary.
4. **Horizontal web (60K+)** — replicas are stateless (JWT auth, Redis
   rate limits, advisory-lock job election). Raise `deploy.replicas`.
   Turn off in-process Huey on web (`HUEY_INLINE_CONSUMER=false`) and run
   dedicated worker replicas.
5. **Queue tier (100K)** — swap Huey's SQLite file for the Redis broker
   (`huey_redis.py` already supported by Huey). Crawls/media import move
   to a crawl-worker pool with per-tenant queue keys.

## Scheduler correctness at any replica count

- `publish-due-posts` (30 s), `silent-trainer` (45 s), weekly rebuild:
  each execution grabs `pg_try_advisory_lock(job_key)`. One replica runs
  the tick; the others log `skipped — another replica holds the advisory
  lock`. Locks die with the session — a crashed replica never wedges the
  job for more than one tick.
- `max_instances=1` + `coalesce=True` still deduplicates inside each
  process (slow-cycle stacking impossible).
- The publish sweep is idempotent even without the lock: the post UPDATE
  is `WHERE status = 'pending' AND due_at <= now()` (CAS), so a double
  sweep can never double-post.

## Known ceilings (and their levers)

| Ceiling | Symptom | Lever |
|---|---|---|
| Postgres write IOPS | message inserts lag | faster disk (NVMe), then partitioning |
| Postgres connections | `too many clients` | pgbouncer pools (already in compose) |
| LLM provider RPM | 429s, fallback replies | provider ladder + per-tenant daily budget (plans module); add provider keys |
| Meta webhook floods | CPU on signature checks | nginx rate limit per source IP; slowapi already Redis-backed |
| Style-trainer CPU | 45 s cycles overrun | reduce conversations/cycle; move trainer to the worker role |

## What we deliberately do NOT do

- No self-hosted LLM (see AI-STRATEGY.md — a 7-8B model on CPU is
  10-60 s/reply; the hosted free tiers are faster AND free).
- No Kubernetes before ~50K/day — 2 replicas + compose is operationally
  simpler and cheaper than a control plane.
- No multi-region before Egyptian-latency data shows it matters (all
  traffic is Meta-webhook-origin; one region is fine).
