# Zemest Production Deployment (2–4 GB VPS)

Configs from the G4 deployment research (analysis/G4-deployment.md) +
G2 backup stack (analysis/G2-backups.md). Topology: **systemd + binaries,
NOT Docker** — the repo's docker-compose.yml targets a heavier
Postgres+Redis stack that does not match the tested single-process design.

```
                    ┌──────────────────────────────┐
   :443/:80 ──────▶ │  Caddy 2.11 (auto-TLS)        │  only public listener
                    └──────┬───────────────┬───────┘
                           │               │
              127.0.0.1:3000      127.0.0.1:8000
                    ┌──────▼───────┐ ┌─────▼────────────────────┐
                    │ zemest-web   │ │ zemest-api               │
                    │ Next standalone│ │ uvicorn, 1 worker       │
                    │ (pages + BFF)│ │ APScheduler + Huey in-proc│
                    └──────────────┘ └─────┬────────────────────┘
                                            │
                                     SQLite (WAL) + huey_queue.db
                                     nightly VACUUM INTO backups
```

## Files

| File | Target on the VPS |
|---|---|
| `Caddyfile` | `/etc/caddy/Caddyfile` (edit the domain first) |
| `systemd/zemest-api.service` | `/etc/systemd/system/zemest-api.service` |
| `systemd/zemest-web.service` | `/etc/systemd/system/zemest-web.service` |
| `systemd/zemest-api.socket` | optional — socket activation for :8000 |
| `crowdsec.md` | CrowdSec edge protection install sketch |

## Deploy flow (first boot)

1. **Backend**
   - `rsync repos/zemest/ → /opt/zemest/backend/` (code + venv, or build
     the venv on the box: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`)
   - `mkdir -p /opt/zemest/backend/data /var/log/zemest`
   - Write `/etc/zemest/api.env` (mode 0640, root:zemest): `JWT_SECRET_KEY`
     (`python -c "import secrets; print(secrets.token_urlsafe(48))"`),
     `APP_ENV=production`, `DATABASE_URL=sqlite+aiosqlite:///data/custom.db`,
     FB/SMTP/PAYMOB keys, `HUEY_SQLITE_PATH=data/huey_queue.db`
   - `systemctl enable --now zemest-api`
2. **Frontend**
   - Build locally: `bun install --frozen-lockfile && bun run build`
   - Deploy three pieces to `/opt/zemest/web/`: `.next/standalone/` (contains
     `server.js` + pruned node_modules), **plus** `.next/static/` →
     `/opt/zemest/web/.next/static/` and `public/` → `/opt/zemest/web/public/`
     (standalone does not include them)
   - Write `/etc/zemest/web.env`: `BACKEND_URL=http://127.0.0.1:8000`,
     optional `NEXT_PUBLIC_GOATCOUNTER_CODE`, `NEXT_PUBLIC_SITE_URL`
   - `systemctl enable --now zemest-web`
3. **Edge**
   - Install Caddy (official apt repo), drop in the Caddyfile with the real
     domain, `systemctl reload caddy`
   - CrowdSec: see `crowdsec.md`
4. **Backups** (G2 layering)
   - Layer 1 (live): `scripts/backup_db.py` — VACUUM INTO + integrity check +
     retention. Cron it nightly:
     `17 3 * * * cd /opt/zemest/backend && .venv/bin/python ../../scripts/backup_db.py`
   - Layer 2: Litestream → S3 (1s RPO, zero app changes) — VPS day
   - Layer 3: restic to a second location — VPS day
   - Layer 4: healthchecks.io ping on backup success (`backup_db.py --ping-url`)

## Operational notes

- **One worker only.** The in-process scheduler (APScheduler), the embedded
  Huey consumer, the in-memory rate limiter and the SQLite single-writer
  contract all assume exactly one uvicorn worker. Before ever scaling to
  `--workers >1`: move APScheduler + Huey consumer out of the lifespan into
  their own units and put the rate limiter on Redis.
- **Restart behavior:** systemd `KillMode=control-group` (default) reaps the
  Huey consumer subprocess with the API — nothing orphans. Caddy upstream
  health checks + retries absorb the 1–3 s restart window.
- **Zero-downtime-ish:** Caddy `reload` is graceful; socket activation
  (optional `.socket` unit) queues :8000 connections during API restarts.
  Full blue/green is overkill at this scale.
- **Do NOT** deploy the repo's `docker-compose.yml` — it is a different,
  heavier system (Postgres + Redis + Celery + Postiz, 6+ containers).
