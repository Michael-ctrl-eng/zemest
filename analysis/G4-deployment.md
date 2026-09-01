# G4 — Deployment Hardening Research (GitHub)

- **Agent:** G4 (github-research, read-only — no code changes, no git commands)
- **Date:** 2026-09-01 (sandbox clock)
- **Scope:** production topology for FastAPI (uvicorn) + Next.js (standalone) on a single 2–4 GB VPS behind a reverse proxy
- **Method note:** the GitHub REST API quota for this sandbox IP was already exhausted (60/60 unauthenticated calls used by other agents, reset was 40+ min out), so repo metadata was collected by direct `curl` of `github.com` repo pages (embedded JSON), `commits/HEAD.atom` + `releases.atom` feeds, `releases/latest` redirect HEAD probes, and `raw.githubusercontent.com` docs files. All numbers below were verified live from GitHub today. ~10 curl invocations total (≈40 HTTP requests, only 10 of them API calls). No repo content was modified.

---

## 0. Ground truth from the current stack (E10 + files read)

| Fact | Source | Deployment implication |
|---|---|---|
| `next.config.ts` already has `output: "standalone"` | next.config.ts | prod artifact = `.next/standalone/server.js` (lean node runtime) |
| Runtime is **Next.js 16.1.3** dev-mode, RSS 1.74 GB and climbing (Turbopack per-route compile) | E10 §1–2, F1 | dev memory ≠ prod memory; standalone prod build is the fix, but must be capped |
| uvicorn 1887, **single worker**, `--host 0.0.0.0 --port 8000`, double-fork daemon spawned by `daemon_backend.py`; PPID 1 | E10 §1, F10, F14 | replace self-daemonization with systemd; bind 127.0.0.1 |
| Scheduler + inline queue + trainer run **in-process** (`scheduling_tasks` / `inline_worker` / `training_worker` cycles in backend.log) | E10 §3 | multi-worker would duplicate them → keep 1 worker (§2.2) |
| Rate limiter (slowapi) + JWT refresh-denylist fall back to **in-memory** when `REDIS_URL=""` | E10 §4–5 | per-process state → single worker requirement #2 |
| DB = **SQLite, WAL** on disk (18 tables); no Postgres/Redis running | E10 §4 | single-writer-friendly; backup strategy needed |
| ~20 uncommitted files; 5 commits local-only | E10 F11 | commit + push + tag before first prod deploy |
| repo `docker-compose.yml` targets Postgres+Redis+Celery+Postiz (6+ containers) — **mismatch** with the running SQLite/in-process stack | docker-compose.yml | Docker path would be a different (heavier) system than what is actually tested |

---

## Ranked picks (TL;DR)

| # | Tool | Repo | Stars | License | Latest | Last commit | Role |
|---|---|---|---|---|---|---|---|
| 1 | **Caddy** | github.com/caddyserver/caddy | 75,372 | Apache-2.0 | v2.11.4 | 2026-08-31 (daily) | edge reverse proxy, auto-TLS |
| 2 | **uvicorn** (single worker) | github.com/**Kludex**/uvicorn (moved from encode/) | 10,939 | BSD-3-Clause | 0.52.4 (2026-08-19) | 2026-08-30 | ASGI app server |
| 3 | **systemd** | github.com/systemd/systemd | 16,642 | GPL-2.0 / LGPL-2.1+ (mixed) | v261.2 | always (distro) | supervisor, hardening, journald |
| 4 | **CrowdSec** | github.com/crowdsecurity/crowdsec | 14,698 | MIT | v1.8.0 | 2026-08-31 (daily) | IPS reading Caddy logs (fail2ban = lean alt) |
| 5 | **Next.js standalone runtime** | github.com/vercel/next.js | 142,037 | MIT | v16.3.4 | daily (canary) | web tier + BFF |

Also evaluated: **gunicorn** (benoitc/gunicorn — 10,664★, MIT, v26.2.0, commits 2026-08-31: alive, but not needed at 1 worker) and **Watchtower** (containrrr/watchtower — **repo ARCHIVED**, verified `isArchived:true`, last release v1.7.1 Nov 2023; active Apache-2.0 fork = nicholas-fedor/watchtower, v1.21.2, commits 2026-08-31) — Watchtower only matters if a Docker path is chosen, which is not the recommendation for this VPS.

---

## 1. Caddy — `caddyserver/caddy`

- **URL:** https://github.com/caddyserver/caddy
- **Stars:** 75,372 · **License:** Apache-2.0 · **Latest release:** v2.11.4 · **Last commit:** 2026-08-31 (feed verified) · **Archived:** no · default branch `master`
- **Role in topology:** the only process bound to public :80/:443. Automatic ACME TLS (Let's Encrypt/ZeroSSL), HTTP/2+3, zstd/gzip, JSON access logs (feeds CrowdSec), reverse proxy to both loopback upstreams. Single ~40 MB Go binary, ~20–40 MB RSS, hot config reload (`caddy reload` = graceful, no dropped connections) → "zero-downtime-ish" proxy reconfig for free.
- **License verdict:** Apache-2.0 — permissive, commercial use fine, no copyleft contamination.

### Integration sketch — production Caddyfile (replaces the sandbox `:81` edge pattern)

```caddyfile
# /etc/caddy/Caddyfile — zemest production
# The site address (domain) triggers automatic HTTPS + HTTP→HTTPS redirect.
zemest.example.com {
	encode zstd gzip

	# OPTIONAL: exact-path passthrough for Meta webhook callbacks, if a
	# callback URL must hit FastAPI directly instead of the Next BFF.
	# handle /webhook/* {
	#     reverse_proxy 127.0.0.1:8000
	# }

	# Default: everything (pages + /api/zemest/* BFF proxying) → Next standalone
	handle {
		reverse_proxy 127.0.0.1:3000 {
			health_uri /            # use /healthz once added (E10 F13)
			health_interval 10s
			health_timeout 3s
			health_status 2xx
		}
	}

	header {
		Strict-Transport-Security "max-age=31536000; includeSubDomains"
		X-Content-Type-Options "nosniff"
		Referrer-Policy "strict-origin-when-cross-origin"
		-X-Powered-By              # strips Next's leak (E10 F2; also set poweredByHeader:false)
	}

	log {
		output file /var/log/caddy/zemest.access.log {
			roll_size 50MiB
			roll_keep 10
		}
		format json               # CrowdSec's caddy parser consumes this format
	}
}

# Install: official apt repo (dl.cloudsmith.io/caddy/stable) or static binary.
# uvicorn side must run with --proxy-headers --forwarded-allow-ips 127.0.0.1
# (defaults already match loopback) so FastAPI sees real client IPs.
# Keep the admin endpoint on localhost:2019 (default) — it can reload config.
```

- **Verdict:** the anchor of the topology. No certbot, no nginx+cert-symlinks, one config file, memory-trivial. Apache-2.0. Matches E10 F10's "prod should bind 127.0.0.1 behind caddy" note exactly — both app tiers bind loopback, Caddy is the only public listener.

---

## 2. uvicorn — `Kludex/uvicorn` (⚠ repo moved from `encode/uvicorn`)

- **URL:** https://github.com/Kludex/uvicorn (github.com/encode/uvicorn now 301-redirects here — verified via the `releases/latest` Location header and page fetch; docs moved to **uvicorn.dev**; repo transfer, star history intact; package on PyPI is still `uvicorn`)
- **Stars:** 10,939 · **License:** BSD-3-Clause · **Latest release:** 0.52.4 (2026-08-19, from releases.atom) · **Last commit:** 2026-08-30 · **Archived:** no · default branch `main`
- **Role:** ASGI server for `app.main:app`.
- **Flags verified from `docs/settings.md` (raw fetch):**
  - `--workers <int>` — defaults to `$WEB_CONCURRENCY` or **1**; mutually exclusive with `--reload`
  - `--proxy-headers` — **default ON**, but only trusts IPs in `--forwarded-allow-ips`, which **defaults to `127.0.0.1`** → exactly correct behind loopback Caddy with zero extra config
  - graceful SIGTERM handling (drains connections, runs lifespan shutdown → the in-process scheduler loops stop cleanly), `--limit-concurrency`, `--timeout-keep-alive`

### 2.2 The core decision: single vs multi worker (Python 3.12, asyncio, in-process scheduler + in-process queue)

**Verdict: run exactly ONE worker.** Verified reasons:

1. **In-process scheduler would multiply.** `scheduling_tasks` / `inline_worker` / `training_worker` run as asyncio loops inside the API process (E10 §3 logs their cycles from the single daemon). N workers = N schedulers → duplicate scheduled posts, duplicate training cycles, row races on `scheduled_posts`.
2. **In-memory auth/rate state would split.** With `REDIS_URL=""` the slowapi limiter and the JWT refresh-token denylist are per-process (E10 §4–5). N workers = N× effective rate limits and — worse — a token revoked on one worker stays valid on the others (a security hole, not just a nuisance).
3. **SQLite WAL tolerates one writer at a time.** Multiple worker processes each holding write-capable async sessions → `SQLITE_BUSY` under write bursts. (The Postgres+asyncpg path in docker-compose avoids this, but that's the other, heavier topology.)
4. **Memory.** 135 MB baseline per uvicorn process (E10 §1). On a 2 GB VPS every duplicate hurts; asyncio already gives I/O-bound concurrency (LLM calls, DB awaits) within one process — the GIL is irrelevant for awaited I/O.

**When multi-worker becomes right — and the migration path (in order):**
1. Set `REDIS_URL` (already plumbed through `config.py`) → limiter + denylist become shared.
2. Move the scheduler/queue out of the API process: dedicated unit running the worker loops (or Celery as the repo's compose already models), API started with `--lifespan off`… then workers can be added.
3. Either `uvicorn --workers 2` (its multiprocess supervisor supports graceful SIGHUP restarts) **or** gunicorn.

**gunicorn sub-verdict** (benoitc/gunicorn — 10,664★, MIT, **v26.2.0**, commits 2026-08-31: the "gunicorn is dead" meme is stale):
- Value = worker supervision, `HUP` rolling reloads, `--graceful-timeout`, worker-class mixing — all of which only matter at `w>1`.
- At `w=1` + systemd (Restart=always, SIGTERM draining), gunicorn adds a layer without adding a guarantee.
- **Recommendation: plain `uvicorn`, workers=1, supervised by systemd. Keep gunicorn in the back pocket for the scale-out day** (`gunicorn app.main:app -k uvicorn.workers.UvicornWorker -w 2 --bind 127.0.0.1:8000 --graceful-timeout 30`).

---

## 3. systemd — `systemd/systemd`

- **URL:** https://github.com/systemd/systemd
- **Stars:** 16,642 · **License:** GPL-2.0, LGPL-2.1+ (mixed per repo page) · **Latest release:** v261.2 · distro-provided (no install action; only unit files needed)
- **Role:** replaces **both** ad-hoc process management paths E10 flagged:
  - `daemon_backend.py`'s double-fork self-daemonization (PPID 1, PID files) → `Restart=always` + journald
  - Next.js's `fetchWithHeal` spawning the backend (`execFile python daemon_backend.py start`) — E10 F14: "unusual privilege for a web tier in prod"
- Also: `EnvironmentFile` for secrets (0640, never in git), memory caps (systemd OOM-restarts the unit instead of the kernel OOM-roulette killing the biggest process — the exact failure mode E10 F1 feared), `journald` as the CrowdSec log source for sshd.

### Integration sketch — unit files

```ini
# /etc/systemd/system/zemest-api.service
[Unit]
Description=Zemest FastAPI (uvicorn, single worker — in-process scheduler+queue)
After=network-online.target
Wants=network-online.target

[Service]
Type=exec
User=zemest
Group=zemest
WorkingDirectory=/opt/zemest/backend
EnvironmentFile=/etc/zemest/api.env        # 0640 root:zemest: JWT_SECRET_KEY, FB_*, SMTP_*, APP_ENV=production
ExecStart=/opt/zemest/backend/.venv/bin/uvicorn app.main:app \
    --host 127.0.0.1 --port 8000 \
    --proxy-headers --forwarded-allow-ips 127.0.0.1 \
    --no-server-header \
    --timeout-keep-alive 65 \
    --limit-concurrency 200
Restart=always
RestartSec=3
TimeoutStopSec=25                          # > graceful drain window; lifespan stops scheduler loops
KillSignal=SIGTERM                         # uvicorn drains on SIGTERM
MemoryHigh=700M                            # soft throttle
MemoryMax=1G                               # hard cap → systemd restart, not kernel OOM
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
ReadWritePaths=/opt/zemest/backend/data /var/log/zemest
LimitNOFILE=8192

[Install]
WantedBy=multi-user.target
```

```ini
# /etc/systemd/system/zemest-web.service
[Unit]
Description=Zemest Next.js standalone (pages + BFF)
After=network-online.target zemest-api.service
Wants=zemest-api.service

[Service]
Type=exec
User=zemest
Group=zemest
WorkingDirectory=/opt/zemest/web            # server.js + .next/static + public
EnvironmentFile=/etc/zemest/web.env         # BACKEND_URL=http://127.0.0.1:8000
Environment=NODE_ENV=production
Environment=PORT=3000
Environment=HOSTNAME=127.0.0.1
Environment=NODE_OPTIONS=--max-old-space-size=512
ExecStart=/usr/bin/node server.js
Restart=always
RestartSec=2
MemoryHigh=512M
MemoryMax=768M                              # E10 F1: dev hit 1.74GB; prod standalone is far leaner — cap anyway
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
ReadWritePaths=/opt/zemest/web/.next/cache

[Install]
WantedBy=multi-user.target
```

**Optional: hide the 1–3 s restart blip on the API port via socket activation** (connections queue in the socket while the service restarts; Caddy's upstream retries cover the rest):

```ini
# /etc/systemd/system/zemest-api.socket
[Socket]
ListenStream=127.0.0.1:8000
NoDelay=true
[Install]
WantedBy=sockets.target
# unit then uses: ExecStart=... uvicorn app.main:app --fd 3  (drop --host/--port)
```

**Zero-downtime-ish summary:** Caddy `reload` is graceful (proxy reconfigs), `caddy` upstream health checks + retries absorb a restarting app unit, socket activation queues :8000 during API restarts, systemd restarts take ~1–3 s. Full blue/green is overkill for a modest VPS and not recommended here.

---

## 4. CrowdSec — `crowdsecurity/crowdsec` (fail2ban as the lean alternative)

- **URL:** https://github.com/crowdsecurity/crowdsec
- **Stars:** 14,698 · **License:** MIT · **Latest release:** v1.8.0 · **Last commit:** 2026-08-31 (daily) · **Archived:** no
- **Role:** IPS. Agent tails Caddy's JSON access log + journald (sshd), evaluates scenarios, state in local SQLite (LAPI); remediation via a bouncer — either nftables firewall or a **Caddy-native bouncer module** (hslatman/caddy-crowdsec-bouncer, built with xcaddy) that 403s inside the proxy. Plus the community CTI blocklist (shared attacker IPs) — meaningful for a public Egyptian-market SaaS that already sees constant bot traffic (E10's `bot_detected` log flood).
- **Memory:** agent+LAPI ≈ 80–120 MB. MIT license, very active.

```bash
# sketch
sudo apt install crowdsec                       # official repo
sudo cscli collections install crowdsecurity/caddy
sudo cscli collections install crowdsecurity/sshd        # + whitelist your own IP!
sudo cscli bouncers add caddy-bouncer           # API key → Caddy module / firewall bouncer
# hub updates: systemd timer (cscli hub update && cscli hub upgrade)
```

**Alternative: fail2ban** (github.com/fail2ban/fail2ban — 18,516★, GPL-2.0+, v1.1.1, last commit 2026-08-26: maintained, slow cadence): ~40–60 MB Python daemon, journald backend works out of the box for sshd, but needs a hand-written regex filter for Caddy logs and has no shared blocklist. Choose it only if every MB counts on a 2 GB box or you want zero extra services — the app already has in-app `ip_bans` + slowapi rate limiting (defense in depth).

- **Verdict:** **CrowdSec** — better fit for Caddy (native parser), MIT, community blocklist, active daily. fail2ban acceptable as the minimal variant. Either way the app-level bans stay as the inner layer.

---

## 5. Next.js standalone runtime — `vercel/next.js`

- **URL:** https://github.com/vercel/next.js
- **Stars:** 142,037 · **License:** MIT · **Latest release:** v16.3.4 (sandbox runs 16.1.3 — patch-bump when convenient; E10 F12 also notes the middleware→proxy migration notice)
- **Role:** the web tier (marketing pages + dashboard SSR + **BFF**). The BFF route `src/app/api/zemest/[...path]/route.ts` keeps FastAPI unreachable from browsers (no CORS on FastAPI — E10 verified this is deliberate and secure). Keep that architecture in prod: point the BFF at `http://127.0.0.1:8000`.
- **Standalone pattern** (already enabled via `output: "standalone"` in next.config.ts — the single most important prod decision, already made):
  1. `bun install --frozen-lockfile && bun run build` → emits `.next/standalone/server.js` with a minimal pruned `node_modules`
  2. Deploy three pieces: `.next/standalone/` → `/opt/zemest/web/`, **plus** copy `.next/static/` → `/opt/zemest/web/.next/static/` and `public/` → `/opt/zemest/web/public/` (standalone does not include them)
  3. Run with plain Node (not bun dev, not `next start`): `NODE_ENV=production PORT=3000 HOSTNAME=127.0.0.1 node server.js`
- **Memory reality check:** E10's 1.74 GB figure is the *dev* server (Turbopack + per-route compile + dev overlays). A production standalone server typically idles at 150–300 MB RSS. Still: `MemoryMax=768M` + `--max-old-space-size=512` (see unit above) so the dev-server growth pathology can never OOM the box in prod.
- **Prod config deltas to schedule** (ties to E10 findings, not blockers): `poweredByHeader: false` + `headers()` security block (F2 — Caddy also covers it), `/healthz` route for Caddy health_uri (F13), eventually middleware→`proxy.ts` (F12), keep `skipTrailingSlashRedirect` (it exists for the sandbox edge proxy's slash quirk — verify behavior under the prod Caddy, then consider removing).

---

## Also-ran: Watchtower (docker auto-update)

- **containrrr/watchtower** (24,663★, Apache-2.0): **repository is ARCHIVED** (verified `"isArchived": true`, "Public archive" badge); last release v1.7.1 (Nov 2023), last commit 2025-12-17. **Do not adopt.**
- **nicholas-fedor/watchtower** (active fork): 4,364★, Apache-2.0, v1.21.2, commits 2026-08-31. Drop-in replacement image if ever needed.
- **However:** the recommendation for this VPS is **systemd + binaries, not Docker**. The repo's docker-compose.yml targets Postgres+Redis+Celery+Postiz (6+ containers, >1.5 GB before the app itself) — a different, heavier system than the SQLite + in-process stack that is actually running and tested. On 2–4 GB, containers buy isolation but cost RAM (daemon, per-image layers, bind conflicts) and add an update plane. **Skip Watchtower entirely in the recommended topology.** If a future containerized path is chosen (e.g., to match the compose file or isolate Postiz), use the nicholas-fedor fork with `WATCHTOWER_LABEL_ENABLE=true` (label-scoped), a `WATCHTOWER_SCHEDULE` off-peak window, and `--rolling-restart`.

---

## Recommended production topology (2–4 GB VPS, text diagram)

```
                Internet  (browsers · merchant sessions · Meta webhooks)
                                     │  :80→:443 (ACME auto-TLS: LE/ZeroSSL, HTTP/2+3)
                                     ▼
      ┌─────────────────── caddy.service (systemd) ───────────────────────┐
      │  auto-TLS · zstd · JSON access log → CrowdSec                     │
      │  default → 127.0.0.1:3000        /webhook/* (opt) → 127.0.0.1:8000│
      │  health-checked upstreams · graceful reload (caddy reload)        │
      └──────────┬────────────────────────────────────────┬───────────────┘
                 │ loopback only                          │ loopback only
                 ▼                                        ▼
   ┌──────────────────────────┐            ┌───────────────────────────────────┐
   │ zemest-web.service       │  BFF proxy │ zemest-api.service                │
   │ node .next/standalone/   │───────────▶│ uvicorn app.main:app              │
   │   server.js  (Next 16)   │ 127.0.0.1  │   --workers 1  (scheduler, inline │
   │ /api/zemest/* → :8000    │   :8000    │    queue, rate-limit + JWT deny-  │
   │ 150–300MB · MemMax 768M  │            │    list all in-process)           │
   └──────────────────────────┘            │ 135–300MB · MemMax 1G             │
                                           └───────────────┬───────────────────┘
                                                           │ SQLAlchemy 2.0 async
                                                           ▼
                                        SQLite (WAL) /opt/zemest/backend/data/
                                        nightly `sqlite3 db ".backup ..."` → offbox
   crowdsec.service (~100MB, MIT)  ← caddy access.log + journald(sshd)
     └─ bouncer: nftables or Caddy module → drop/403 for community blocklist
        + local decisions (app's own ip_bans stays the inner layer)
   sshd: key-only, no root; ufw/nftables allow only 22/80/443
   swap: 1–2 GB swapfile (cheap OOM insurance) + systemd MemoryMax per unit
```

**Memory budget (2 GB worst case):** OS+sshd ~250 MB · Caddy ~40 MB · Next standalone ~300 MB · uvicorn ~300 MB (+ LLM burst headroom) · CrowdSec ~120 MB ≈ **~1.0–1.2 GB used, ~0.8 GB headroom/page cache**. A 4 GB VPS is comfortable; 2 GB works with the caps above.

**Deploy flow (git-based, per release):**
```bash
sudo -u zemest git -C /opt/zemest/src fetch --tags && git reset --hard vX.Y.Z
# backend: sync venv (uv pip install -r requirements.txt), data dir preserved
# web:     bun install --frozen-lockfile && bun run build
rsync -a .next/standalone/ /opt/zemest/web/
rsync -a .next/static/     /opt/zemest/web/.next/static/
rsync -a public/           /opt/zemest/web/public/
sudo systemctl restart zemest-api zemest-web   # 1–3s blip; socket unit hides :8000's
```

---

## Pre-deploy hardening checklist (tied to E10 findings)

1. **Commit + push the ~20 modified files, tag a release** (F11) — prod must never run uncommitted code.
2. Bind both tiers to `127.0.0.1` (F10) — done in the unit files above; firewall confirms only 22/80/443 open.
3. Secrets via `EnvironmentFile` (0640): fill `JWT_SECRET_KEY` (already guarded), `FB_VERIFY_TOKEN` (**add it to the prod boot guard** — F4), `FB_APP_ID/SECRET`, `SMTP_*`; `REDIS_URL` stays optional in the single-worker topology.
4. Gate `/docs`, `/redoc`, `/openapi.json` on `APP_ENV` (F4) or block at Caddy.
5. Add `/healthz` on both tiers (F13) → Caddy `health_uri` + optionally `WatchdogSec` on the API unit.
6. SQLite backups: nightly `sqlite3 ".backup"`/`VACUUM INTO` + WAL checkpoint + offbox sync (rclone to object storage).
7. Frontend security headers (F2): Caddy covers it at the edge; mirror in `next.config.ts` headers() when convenient.
8. Add swap even with MemoryMax (belt+braces on 2 GB).
9. Remove/neuter `fetchWithHeal`'s backend-spawning in prod (F14) — systemd owns process lifecycle; keep the health *check*, drop the exec.

## Verdict table

| Tool | Adopt? | One-liner |
|---|---|---|
| Caddy v2.11.4 | **YES — edge** | auto-TLS single binary, Apache-2.0, daily commits, ~40MB; kills the certbot/nginx tax |
| uvicorn 0.52.4 (w=1) | **YES — app server** | proxy-headers+forwarded defaults already match loopback Caddy; single worker because scheduler/queue/limiter/denylist are in-process and SQLite wants one writer |
| gunicorn 26.2.0 | LATER | alive and fine, but at w=1 adds nothing over systemd+uvicorn; re-evaluate only after Redis + externalized scheduler |
| systemd 261.2 | **YES — supervisor** | replaces daemon double-fork + fetchWithHeal; memory caps, journald, hardening flags |
| CrowdSec 1.8.0 | **YES — IPS** | MIT, Caddy JSON parser, community blocklist, Caddy-native bouncer; fail2ban 1.1.1 (GPL-2+) = lean SSH-only alternative |
| Next.js standalone (16.x) | **YES — web tier** | already opted-in via next.config; node server.js + static/public rsync + MemoryMax; prod RSS ~10× lower than the dev figure E10 saw |
| Watchtower | NO (unless Docker) | upstream archived Nov-2023; if ever containerized, nicholas-fedor fork v1.21.2 — but the recommended topology is systemd, not Docker |
