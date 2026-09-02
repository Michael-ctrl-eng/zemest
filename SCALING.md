# Scaling Zemest to 10,000 Users

Capacity math, deployment shape, and the ceilings of the single-host
design. Companion to `deploy/docker-compose.prod.yml`.

## 1. Traffic model

10,000 registered merchant users does **not** mean 10,000 concurrent
requests. The workload is chat-commerce:

| Signal | Value | Basis |
|---|---|---|
| Registered users | 10,000 | target |
| DAU (B2B SaaS norm) | 40% → 4,000 | merchants check dashboards 2–5×/day |
| Peak-hour concentration | ~25% of DAU → 1,000 | evening commerce peak (Cairo time) |
| Dashboard/API requests per active user | ~6/min burst, ~0.5/min sustained | TanStack Query 10s polling × list views |
| **Peak sustained API load** | **~50 rps** + spikes to **~120 rps** | 1,000 × 0.05 + burst factor |
| Webhook traffic | ~30 rps peak | Meta delivers message events; 45s trainer batches |
| LLM chat turns | ~15 rps peak | ~1/2 of webhooks trigger an agent reply |

## 2. Why the shape in docker-compose.prod.yml fits

### API tier — 2 replicas × 2 uvicorn workers
FastAPI on a 2.8 GHz vCPU sustains ~500–800 rps for I/O-bound routes
(postgres + redis round-trips dominate). The *real* API work here is
I/O-bound (DB queries, Graph calls, LLM streaming), so 4 worker
processes on 8 vCPU with p99.9 latency < 300 ms is roughly 25× headroom
over the 50 rps peak. The binding constraint is **not** the API tier.

### Database — postgres:16 tuned + pgbouncer (transaction mode)
- `shared_buffers=1GB`, `effective_cache_size=3GB` (box has 16 GB).
- `max_connections=300` on postgres; **pgbouncer fronts it with
  `default_pool_size=40`**. asyncpg opens a connection pool per uvicorn
  worker (4 workers × 2 services + scheduler = 5 pools × ~10 conns).
  Without pooling that's fine; with burst traffic + Huey jobs it spikes —
  pgbouncer absorbs the churn and caps concurrent backend connections so
  postgres never hits `max_connections` lockouts.
- Every hot path is indexed (WAL + `idx_messages_conversation_created`,
  `idx_products_tenant_active`, unique `fb_message_id` dedup, unique
  `users.email`, refresh-token ledger indexes — see migrations).

### Redis — rate limits + JWT denylist + session cache
`allkeys-lru` at 512 MB: the denylist and rate-limit counters survive
restarts (AOF). Webhook signature verification is pure CPU (no I/O), so
webhooks stay cheap.

### Background jobs — 1 scheduler + 1 Huey worker (the leader-election rule)
This is the load-bearing design decision: **`SCHEDULER_ENABLED=false`
on every API replica; exactly one `scheduler` service runs with it
`true`.** Without this, N replicas × 45 s silent-trainer cycle = N×
duplicate LLM spend and N× duplicate order notifications; N replicas ×
30 s publish cycle = **the same Facebook post published N times**. The
compose file hard-codes the split (api: false, scheduler: true) so it
cannot be misconfigured by accident.

The Huey queue is SQLite-file-backed and the dedicated `worker` service
is the ONLY consumer — crawl jobs and order notifications execute
exactly once regardless of replica count.

## 3. Where this design's ceiling is (~40k users)

| Component | Ceiling | What gives out |
|---|---|---|
| API tier | ~40k users | CPU on TLS + JSON parsing (scale replicas to 4) |
| Postgres | ~60k users | connection pool saturation → read replica |
| Redis | ~100k users | memory for counters (tiny) — not binding |
| SQLite Huey queue | **~15k users** | single-file queue, no cross-host sharing |
| Scheduler | ~25k users | trainer cycle time exceeds 45 s interval |

**Next step at ~15k users** (documented so the decision is pre-made):
move Huey from SQLite to the existing Postgres (`PostgresHuey` with
psycopg ≥ 3.2), then split the trainer into per-tenant shards. Both are
code changes, not architecture changes — no new infra.

## 4. Failover posture

- API replicas: Caddy health-checks `/` every 10 s; a dead replica
  leaves rotation in ≤ 20 s.
- Postgres: single instance — **the SPOF**. Mitigations in place: AOF on
  Redis, `restart: unless-stopped`, WAL archiving ready (wal_level=
  replica). Add streaming standby when revenue justifies it.
- Scheduler: if it dies, posts/training pause (no data loss — scheduled
  posts are DB rows picked up on restart; coalesce catches up).
- Zero-downtime deploys: `docker compose up -d --no-deps api` rolls one
  replica at a time behind Caddy.

## 5. Observability (what to watch)

- `GET /` — liveness (compose + Caddy healthchecks).
- postgres: `pg_stat_activity` connection count (pgbouncer saturation
  alarm at > 80% of pool).
- Huey queue depth: log line `Huey dedicated worker started` + scheduled
  task latency (a growing crawl backlog = scale worker `replicas: 2`).
- LLM spend: `TokenUsage` rows per hour — the silent trainer is the
  dominant consumer at scale.

## 6. Load verification

The repo ships a Locust suite (`tests/load/`). Validate before
production traffic:

```bash
cd repos/zemest
locust -f tests/load/locustfile.py --headless \
  -u 200 -r 20 -t 5m --host https://your-domain
```

Target: p95 < 500 ms on `/api/auth/login`, p95 < 200 ms on product
list endpoints, 0 5xx.
