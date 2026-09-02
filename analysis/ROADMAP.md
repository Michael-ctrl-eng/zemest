# Zemest — Tool Adoption Roadmap

Synthesis of 15 research reports (R1–R10 fleet + G1–G5 gap fleet, all in `analysis/`),
cross-checked against the 10 error-finder audits (E1–E10). One decision per line:
what to adopt, when, and what it replaces.

## Status legend

- ✅ already in the platform · 🟢 adopt now (sandbox-ready) · 🔵 at Postgres/VPS
  migration · ⚪ later / situational · ❌ rejected (with reason)

## 1. Immediate wins (zero/low cost, sandbox-ready)

| # | Pick | Replaces / fixes | Why | Source |
|---|------|------------------|-----|--------|
| 1 | `fasttext-wheel` → **`fasttext-numpy2-wheel`** | current fasttext-wheel | live numpy-2 crash in `model.predict` (ValueError copy) + 780MB default models — use `bucket=100k, dim=50` | R5 |
| 2 | **`VACUUM INTO` backup script** (`scripts/backup_db.py`, implemented) | nothing (DB was wiped twice, no backups) | stdlib-only, WAL-safe, verified 18-table snapshot | G2 |
| 3 | **GitHub-native security layer** (Settings → secret scanning + push protection + Dependabot) | nothing | 5 minutes, free, public-repo; the PAT exposure was exactly this failure mode | G3 |
| 4 | **Wire installed-but-unused TanStack Query** | hand-rolled cache in `zemest-api.ts` (593 LOC) | already in package.json; kills dashboard waterfalls, dedupes, scoped invalidation | R9/E7 |
| 5 | **`reactCompiler: true`** + `react-scan` dev overlay | manual memoization | one-line flag on Next 16 + Turbopack; auto-memoizes the all-client dashboard | R9 |
| 6 | **`PageSectionProps.id`** (implemented) | dead `#roles`/`#programs` anchors | last shipped-code tsc error → 0 | E7 |
| 7 | **sqlite-vec** | no vector store | verified live in our exact stack (SQLAlchemy async + aiosqlite); `PRAGMA foreign_keys=ON` rides free in the same connect-event | R8/E8 |
| 8 | **FTS5 + 12-line Arabic normalizer** | no Arabic search | measured: unicode61 alone fails `متجر` ↔ `المتجر`; trigram gives typo tolerance | R8 |

## 2. Core infrastructure (this quarter)

| # | Pick | Replaces | Why | Source |
|---|------|----------|-----|--------|
| 1 | **Huey (SqliteHuey)** → `PostgresHuey` at migration | 18-d's ARQ plan + dead celery/redis deps | ARQ is Redis-only (we have none) + maintenance-mode since 2025; Huey = SQLite-native, retries+backoff, crontab, embedded consumer; **delete `celery[redis]`+`redis` from requirements** | R3 |
| 2 | **APScheduler 3.11** (`AsyncIOScheduler` in lifespan) | hand-rolled 30s asyncio loop | exact-time triggers, tz-aware cron; v4 is pre-release — stay on 3.x | R3/R6 |
| 3 | **arctic (BFF) + authlib (backend)** for Meta OAuth | dead `/api/auth/facebook` GET flow | arctic: 60-line OAuth client, caller-owned state; authlib: httpx-native token exchange incl. `fb_exchange_token`; align ALL endpoints to Graph v21.0 | R1/E3/E6 |
| 4 | **llama.cpp `llama-server` + PEFT/Trainer** (Phase 1 CPU on 0.6–1.7B Qwen3) | nothing (self-training is exemplar-only today) | per-tenant LoRA via `--lora` + per-request routing; `resume_from_checkpoint` = our crash-resume contract; SQLite ledger (`ft_state`), adapters on disk | R4 |
| 5 | **sklearn `partial_fit` online classifier** + fastText cross-check | lexicon-only classifier | 0.81ms incremental update per message — true online learning; keep cc-2 lexicon for explainability | R5 |
| 6 | **SSE (sse-starlette) + TanStack invalidation** | polling/none (chat pages are mock) | sse-starlette already in venv (pin it!); in-process bus fits single uvicorn worker; `fetch-event-source` for header auth; polling as automatic fallback | R7 |
| 7 | **bore / localtunnel** for Meta webhooks in dev | unreachable localhost:8000 webhooks | everything in the channel roadmap depends on Meta reaching us | R2 |

## 3. Product surface

| # | Pick | Why | Source |
|---|------|-----|--------|
| 1 | **Paymob Intention API (hand-rolled httpx, ~150 LOC)** + official MIT integration skill as vendored spec | no maintained Python SDK exists; official skill = authoritative spec (HMAC-SHA512 webhook field orders, piaster amounts); COD stays default, add deposit-to-confirm (عربون) via wallet/Fawury kiosk | G1 |
| 2 | **icalendar + python-dateutil** for the ICS feed | our hand-rolled ICS lacks RFC-5545 folding, RRULE, VTIMEZONE | R6 |
| 3 | **GoatCounter** (SQLite-native, single Go binary) — or **Umami** if the prod Compose with Postgres lands first | cookieless, <100MB RAM, 4.5KB script; Plausible/PostHog rejected (ClickHouse/Kafka weight) | G5 |
| 4 | **google/schema-dts** (dev-only) + native Metadata API | typed JSON-LD; robots.txt must add Sitemap + disallow /dashboard /admin /api | G5 |
| 5 | **someday** availability picker (spike; react-day-picker fallback — already installed) | embeddable merchant booking pages | R6 |

## 4. Production migration (VPS + Postgres day)

| # | Pick | Why | Source |
|---|------|-----|--------|
| 1 | **Caddy 2.11** (auto-TLS, the ONLY public listener) + **systemd** units (MemoryMax caps, EnvironmentFile secrets) + uvicorn **single worker** on loopback | matches single-process design (in-process scheduler, in-memory rate limiter, SQLite single-writer); docker-compose in repo targets the wrong stack | G4 |
| 2 | **CrowdSec** (Caddy-native parser + blocklists) over fail2ban | app already has in-app ip_bans + slowapi; CrowdSec covers the edge | G4 |
| 3 | **Litestream → S3** (1s RPO, zero app changes) + **restic** second location + **healthchecks** watchdog | layers 2–4 of the backup stack; layer 1 (VACUUM INTO) already live | G2 |
| 4 | **PostgresHuey** (drop-in) or **Procrastinate** (`FOR UPDATE SKIP LOCKED`) | durable queue survives migration; DELETE celery/redis deps either way | R3 |
| 5 | **pgvector** | dialect-guarded counterpart of sqlite-vec; asyncpg already pinned | R8 |
| 6 | **CI: security.yml + codeql.yml + dependabot + pre-commit** (gitleaks, pip-audit, npm-audit bridge, zizmor, bandit) | free while repo is public; **38 known CVEs today** (python-jose 3.3.0 → 3.4.0 is the urgent one); fix PAT rotation first | G3 |
| 7 | **vLLM multi-LoRA hot-swap** (rented GPU node) | Phase 3 of the fine-tuning plan; unsloth bursts for training | R4 |

## 5. Explicitly rejected

| Tool | Reason |
|------|--------|
| NextAuth/Auth.js v5 | 2yr beta; wrong shape (user-login, not page-tokens); replaces our audited JWT stack |
| Lucia | deprecated (README-confirmed, Mar 2025) |
| Celery + Redis | no Redis in sandbox; heavyweight; single-process design makes it dead weight |
| ARQ | Redis-only + official maintenance-mode (issue #510) |
| Cal.com embedding | AGPL concerns gone (now MIT) but it's a second monolith — steal its data model instead |
| Ollama | no per-request LoRA routing; would duplicate the base GGUF per tenant |
| wa-automate-nodejs / WPPConnect / instagrapi | unofficial APIs — account-ban/ToS risk, never for production SaaS |
| Stripe | cannot onboard Egyptian-registered merchants |
| Watchtower (`containrrr`) | **archived 2023** — use `nicholas-fedor/watchtower` fork if ever containerized |
| PostHog / Plausible / highlight.io self-host | 4–8GB RAM floors — overkill for a marketing-site analytics need |
| Prisma client | untouched demo scaffold in this repo — remove; drizzle only if Next.js ever owns tables |

## Sequence (what actually happens next)

1. **Security/billing fixes** — DONE this session (XFF bypass, governorate
   mischarging, hallucination grounding, dead register form, fetchWithHeal
   duplicate-POST, 422 validation, PageSection anchors).
2. Wire the three mock frontend pages (chat, conversations, style) to the
   real endpoints already shipping behind them (E5/R7) — TanStack Query at
   the same time.
3. Huey + APScheduler land with the silent-trainer move off request threads.
4. Real Meta OAuth (arctic + authlib + callback + state) once FB_APP_ID exists;
   bore tunnel first for webhook E2E.
5. G3's CI files + dependency upgrade batch (jose 3.4.0!) after PAT rotation.
6. Everything in §4 on VPS day.
