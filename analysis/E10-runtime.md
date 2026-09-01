# E10 — Runtime / Environment / Security Posture Audit

- **Agent:** E10 (error-finder, read-only — no code modified, no processes touched)
- **Date:** 2026-09-01 00:55–01:01 UTC (sandbox clock)
- **Scope:** processes, memory/disk, logs, env/config, security posture, ports, Next.js + FastAPI health
- **Secrets policy:** every credential redacted (`…[REDACTED]`); `.jwt_secret` existence/permissions verified **without** printing its contents.

---

## 1. Process table

| PID | PPID | User | Command | RSS | %CPU | Started | Notes |
|---|---|---|---|---|---|---|---|
| 1073→1076 | 1 | root | `sudo -u z bun run dev` (double-sudo chain) | 4MB | 0 | 00:30:46 | harness wrapper chain (pts/0→pts/1); single chain, **no duplicate dev server** |
| 1077 | 1076 | z | `bun run dev` | 1.6MB | 0 | 00:30 | — |
| 1079 | 1077 | z | `bash -c "next dev -p 3000 2>&1 \| tee dev.log"` | 2MB | 0 | 00:30 | **Next.js logs → /home/z/my-project/dev.log** |
| 1080 | 1079 | z | `node .../next dev -p 3000` | 37MB | 0 | 00:30:58 | — |
| **1093** | 1080 | z | **next-server (v16.1.3)** | **1.74 GB and climbing** | 1–3% | 00:30:58 | 1 start, **no restarts**; 26 threads; see §2 |
| 1155 | 1093 | z | `postcss.js` (Turbopack child) | 125MB | 0.2 | 00:31:02 | normal |
| 1081 | 1079 | z | `tee dev.log` | <1MB | 0 | 00:30 | — |
| **1887** | **1** | z | `uvicorn app.main:app --host 0.0.0.0 --port 8000` | 135MB | 0.9–1.1 | 00:49:30 | double-fork daemon (PPID 1, expected); `backend.pid`=1887 **matches live pid**; 6 threads |

**Sandbox infrastructure (NOT project — do not touch):** PID 1 `tini`; PID 2 `caddy` (edge proxy on :81 → :3000); PID 883 `uv`; **PID 889 `start.sh` in Z (zombie) state — parent caddy never reaped it** (harmless, 1 zombie, infra-owned); PID 924 root `/app/.venv/bin/python3 main.py` (ZAI internal LLM service).

**Duplicated/orphaned project processes:** none. One `next dev` chain, one `uvicorn` (verified via `pgrep -af`). No orphaned uvicorn from the reset (old pids 1731 etc. fully gone).

**Boot history (from backend.log):** import-crash attempts at 00:46:24 (FileNotFoundError old `.venv`) and ~00:47 (AttributeError `NoneType.limit`); server process 1731 started 00:48:19 (ran pre-bootstrap, shut down cleanly 00:49:2x); **current process 1887 started 00:49:32 and stable since — zero ERROR lines after its start**.

## 2. Memory & disk

- **RAM 3.9 GiB total, no swap.** next-server RSS trend: 880 MB @24min → 1.19 GB @27min → **1.74 GB @30min (42–44% of RAM), still climbing** as other agents' page hits trigger Turbopack per-route compiles. OOM risk for the whole stack (no swap → kernel would kill the largest process = next-server). uvicorn stable at 135 MB.
- **Disk:** `/` 9.9G, 3.1G used (33%) — healthy.
- Big dirs under my-project: `node_modules` **1.2G**, `.next` 126M, `skills` 61M, `scripts` 13M (incl. ~13M `scripts/photo-search/dl` downloaded images), `repos` 13M, `public` 4.8M, `identity-raw` 1.1M. No cleanup urgency.

## 3. Log census

### repos/zemest/backend.log (1,293 lines @ audit, growing ~13KB/10min from INFO bot_detected lines)
24 tracebacks total, all but one from the **reset window (00:46–00:49, pre-bootstrap)**:

| Exception | Count | When | Resolved? |
|---|---|---|---|
| `sqlalchemy OperationalError: no such table` (scheduled_posts ×6, tenants ×2, users ×1, orders ×1) | 10 | 00:48–00:49 (process 1731, DB wiped) | **YES** — bootstrap_local.py recreated schema; 18 tables live, 0 errors since 00:49:32 |
| `ERROR app.tasks.scheduling_tasks / inline_worker / training_worker` (stuck-recovery, requeue, cycle failed) | 8 | 00:48–00:49 | **YES** — same no-table cause; current worker cycles report `errors: 0` |
| `FileNotFoundError: repos/zemest/.venv/bin/uvicorn` | 1 | 00:46:24 | **YES** — daemon_backend.py now falls back to PATH/`/home/z/.venv` (code inspected) |
| `AttributeError: 'NoneType' object has no attribute 'limit'` (auth.py `@_limiter.limit` import crash) | 1 | ~00:47 | slowapi 0.1.10 installed → import OK **but latent fragility remains (finding F5)** |
| `ModuleNotFoundError: No module named 'sqladmin'` ("Startup migration block failed") | 1 | 00:48:19 | sqladmin 0.24.0 installed now; current boot ran the migration block clean |
| `WARNING slowapi not installed — rate limiting disabled` | 1 | 00:46:24 | transient (venv reinstall); current process has slowapi active — no such warning for 1887 |
| `passlib bcrypt __about__` (trapped) | 1/process | 00:49:42 (first login) | benign noise; passlib 1.7.4 + bcrypt 4.1.3 known incompat (finding F8) |

Current daemon (1887) log tail: clean — login 200, silent-trainer cycles `errors: 0`, LLM calls `POST https://internal-api.z.ai/v1/chat/completions → 200 OK` (real AI working), `/docs` 200.

- **/tmp/backend.log:** contains only the word `stopped` (00:34) — **stale residue from the reset**; the live daemon logs to `repos/zemest/backend.log` only. Cosmetic.
- **dev.log (Next.js, via tee):** single continuous boot, `Ready in 1142ms`, **no errors, no restarts**. Notable: `Next.js 16.1.3 (Turbopack)` (worklog says "Next.js 15" — doc mismatch, finding F12); `⚠ The "middleware" file convention is deprecated — use "proxy"` (Next 16 migration notice). Response times: first-hit compiles 2–7.5s, warm 50–350ms, `GET /` 109ms. `POST /api/auth/login` 200 in ~1s.

## 4. Env / config

| File | State |
|---|---|
| `/home/z/my-project/.env` | gitignored ✔ (check-ignore passes). Contains ONLY `DATABASE_URL=file:…[REDACTED path to db/custom.db]` (Prisma SQLite — no secret material). **Perms 755 — should be 600** (F13). |
| `repos/zemest/.env` | **ABSENT** — backend runs purely on daemon ENV + config.py defaults (fine in sandbox; all external provider keys empty → LLM ladder uses the z.ai internal provider only). |
| `repos/zemest/.env.example` | placeholders: `OPENROUTER_API_KEY=`, `GEMINI_API_KEY` (commented), `FB_APP_ID=`, `FB_APP_SECRET=`, `JWT_SECRET_KEY=` (empty), `FB_VERIFY_TOKEN=zemest-verify-token` |
| `repos/zemest/.jwt_secret` | **EXISTS, 64 chars, perms 600, owner z, gitignored ✔** (`git check-ignore` positive; contents never printed) |

**config.py placeholder defaults that would break/block production** (production env gaps to fill):
`JWT_SECRET_KEY="change-me-to-a-random-secret-key"` (mitigated in-sandbox by daemon + prod boot-guard in main.py lifespan), `DATABASE_URL=postgresql://…zemest_secret@localhost…` (dev password in default), `REDIS_URL=redis://localhost:6379/0` (unset in daemon → `""` → in-memory rate limiter/denylist), `FB_VERIFY_TOKEN="zemest-verify-token"` (**no prod guard**, F4), `OPENROUTER_API_KEY=""`, `GEMINI_API_KEY=""`, `FB_APP_ID=""`, `FB_APP_SECRET=""` (webhook signature verification fails-closed without it), `SMTP_USER/PASSWORD=""`, `POSTIZ_EMAIL/PASSWORD=""`.

**Reset residue check:** repo venv fully removed (no `.venv`, no stray `__pycache__` dirs found); deps live in `/home/z/.venv` (python 3.12.14); `daemon_backend.py` and `src/lib/backend-health.ts` both try repo-venv-first then fall back to `/home/z/.venv`/PATH — **resilient to future resets**. DB re-bootstrapped: 18 tables, WAL journal active, demo data present (users=4, tenants=1, products=3, conversations=1, messages=6, token_usage=3; `user_sessions`/`admin_audit_log`/`ip_bans`/`site_users` = 0 — UserSession-write gap already documented in Task 19).

## 5. Security posture

**Clean bill on secrets:** no `sk-`/`ghp_`/`AKIA`/`AIza`/`xoxb-`/long-Bearer patterns anywhere in `src/**` or `repos/zemest/app/**`; only test fixtures (`"test-token"`, `"TestPass123!"`) and the two known *default* JWT strings inside verification scripts. The z.ai internal token is read from `/etc/.z-ai-config` at runtime and **never logged** (checked llm_client.py logging calls).

**Verified good:**
- JWT: HS256 **pinned on decode** (blocks `alg=none`/algorithm confusion), `exp` **required**, persistent random 64-char secret (600, gitignored), production boot guard refuses default secrets. Refresh tokens: 7d, `jti` + denylist (in-memory fallback when Redis absent).
- Cookies (Next BFF): `httpOnly` always; `Secure`+`SameSite=None`+`Partitioned` only when HTTPS, `Lax` on HTTP (documented iframe/preview tradeoff); BFF converts cookie→`Authorization: Bearer` server-side and **strips `set-cookie` from backend responses**; login/register/logout all use `authCookieAttributes()`.
- Backend security headers (verified live on :8000): CSP, `X-Frame-Options: DENY`, `nosniff`, `X-XSS-Protection`, `Referrer-Policy`, `Permissions-Policy`, COOP, CORP — excellent.
- **No CORS middleware at all** on FastAPI (BFF is server-to-server; browsers get no cross-origin read access — secure default).
- Bot-detection middleware: **log-only by design** (documented rationale: Meta webhooks + merchant SDK clients use agent UAs); tags `request.state.is_likely_bot` for downstream policy. Currently just floods INFO `bot_detected` lines for every curl from test agents.
- Rate limiting: slowapi active (register 3/min, login 5/min), per-IP **or** per-tenant key (JWT-aware, fail-open design). In-memory store (single-process) since `REDIS_URL=""`.
- Admin API: `require_superadmin` dependency on all mutating admin endpoints (verified in `app/admin/api.py`); superadmin gate re-verified via Task 19 E2E.
- No `debug=True` / `reload=True` anywhere in app code; `APP_DEBUG=False` default.

**Findings (severity-ordered, fixes suggested but NOT implemented):**

| # | Sev | Area | Issue | Suggested fix |
|---|---|---|---|---|
| F1 | **HIGH** (runtime) | Memory | `next-server` RSS 880MB→**1.74GB in 30 min (42%+ of 3.9GB, no swap)** — OOM would kill the dev server and break all agents' live tests | Monitor for plateau; if it keeps growing, plan a scheduled dev-server restart in a quiet window (needs orchestrator approval — none taken by E10); prod build (`output: "standalone"`) will behave differently |
| F2 | MED | Frontend headers | Next.js public surface sends **no security headers** (no XFO/CSP/nosniff/referrer-policy) and leaks `X-Powered-By: Next.js` — backend has full headers, frontend (the public site) has none | Add `headers()` + `poweredByHeader:false` in `next.config.ts` |
| F3 | MED | AuthZ (edge) | `src/middleware.ts`: `/admin` superadmin check is a **stub** ("For now, allow if cookie exists — real check happens client-side"); `/dashboard` gate only checks cookie **presence** (any garbage value passes the edge). Real enforcement relies on admin layout RSC `/auth/me` check + backend 401/403 (both verified working — defense in depth holds today) | Verify JWT in middleware (or drop the stub comment and document the layout+backend gate as the single source of truth) |
| F4 | MED | Config | `FB_VERIFY_TOKEN` default `"zemest-verify-token"` ships with **no production guard** (unlike the JWT guard in main.py lifespan) → webhook spoofing if deployed as-is; `/docs`, `/redoc`, `/openapi.json` exposed unconditionally | Add FB_VERIFY_TOKEN to the production boot guard; gate docs URLs on `APP_ENV` |
| F5 | MED | Fragility | `app/api/auth.py` `@_limiter.limit(...)` decorators execute at import; if slowapi is ever missing again, **the whole app fails to import** (`NoneType.limit`) — defeats rate_limit.py's graceful-degradation design | Make the decorator conditional (no-op wrapper when `_limiter is None`) |
| F6 | MED | Token lifetime | Access JWT 24h (`JWT_ACCESS_TOKEN_EXPIRE_MINUTES=1440`) with no access-token revocation path (denylist only covers refresh `jti`); login cookie `maxAge` 24h/30d(remember) outlives/mismatches token exp | Shorten access-token life (15–60m), add refresh-rotation on the BFF |
| F7 | LOW | Residue | `/tmp/backend.log` = stale `stopped`; backend.log still carries the whole reset-window traceback noise (confusing for future log audits) | Truncate/rotate backend.log after a stable boot; delete stale /tmp/backend.log |
| F8 | LOW | Deps noise | passlib 1.7.4 + bcrypt 4.1.3 `__about__` version warning (trapped traceback on first hash per process) | Pin `bcrypt<4.1` or migrate off passlib |
| F9 | LOW | Config hygiene | `/home/z/my-project/.env` perms **755** (world-readable; only a SQLite path inside — low impact) | `chmod 600 .env` |
| F10 | INFO | Ports | 3000 (`*:3000`) and 8000 (`0.0.0.0:8000`, hardcoded in daemon_backend.py) bound on all interfaces — fine in sandbox, **bind 127.0.0.1 in prod** behind caddy/ingress. Other listeners = infra only: :81 caddy edge, :19005/:19006/:12600/:19001 (ZAI service), :323/udp chrony. Nothing unexpected; **no 5432/6379** (no Postgres/Redis — matches SQLite + REDIS_URL="" design) |
| F11 | INFO | Git | Working tree has ~20+ **uncommitted modified files** (incl. daemon_backend.py, workers, .env.example) — the running daemon executes uncommitted code; 5 commits local-only, push blocked on PAT rotation (Task 18 note) | Commit the current diff; rotate the exposed PAT and push |
| F12 | INFO | Docs | Runtime is **Next.js 16.1.3** (worklog/context say "Next.js 15"); `middleware` file convention deprecated in favor of `proxy.ts` (warning in dev.log) | Update docs; migrate middleware→proxy when convenient |
| F13 | INFO | Health | No `/healthz` (root `/` is the probe: `{"status":"ok"}` 200 in 1.9ms; `HEAD /` → 405). Probe scripts hitting `/healthz`/`/api/ping` got 404s | Standardize a `/healthz` alias |
| F14 | INFO | Architecture | `fetchWithHeal`: the Next.js server **spawns the backend daemon** (`execFile python daemon_backend.py start`) on connection failure — deliberate sandbox self-healing; unusual privilege for a web tier in prod | In prod, replace with a supervisor/systemd unit |

## 6. Health checks (live, read-only)

| Probe | Result | Time |
|---|---|---|
| `GET :3000/` | 200, 112KB | 109ms (warm) |
| `GET :3000/dashboard` (no cookie) | 307 → `/login` (auth gate works) | 5ms |
| `GET :3000/api/zemest/auth/me` (no cookie) | 401 via BFF | 0.97s (first compile) |
| `GET :8000/` | 200 `{"status":"ok","service":"zemest-api"}` | 1.9ms |
| `GET :8000/docs` | 200 | 1.4ms |
| next-server 1093 | single start 00:30:58, no restarts, 26 threads, VmRSS 1.74GB | — |
| uvicorn 1887 | single start 00:49:30 (PPID 1), no restarts, stable, 0 errors since start | — |
| LLM | `internal-api.z.ai/v1/chat/completions → 200` (real replies, glm-4.6) | — |

**Verdict:** the stack is **healthy post-reset** — all reset-window errors (missing venv, missing tables, missing slowapi/sqladmin) were transient and are resolved in the *current* processes; the only live operational risk is F1 (next-server memory growth) plus the listed hardening gaps for production.
