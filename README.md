# Zemest — Unified Platform

**AI sales agents for Egyptian e-commerce.** One repo: Next.js 16 frontend + FastAPI backend, wired end-to-end.

> This is the merged platform: the `zemest-platform` frontend (design system) + the `zemest` FastAPI backend (business logic), finally talking to each other through a secure BFF proxy.

## Architecture

```
Browser ──(same-origin /api/zemest/*)──▶ Next.js BFF proxy ──(cookie→Bearer)──▶ FastAPI :8000
     │                                        │                                     │
     └── httpOnly cookie (zemest_auth JWT)     └── Next.js 16 + Tailwind +          └── SQLAlchemy 2 async
                                                Tavus design system                   SQLite (dev) / Postgres (prod)
```

- **Frontend** (`src/`): Next.js 16 App Router, TypeScript, Tailwind 4, shadcn/ui, Tavus design system. Marketing site + tenant dashboard (live data) + admin panel.
- **Backend** (`repos/zemest/`): FastAPI, SQLAlchemy 2.0 async, multi-tenant (SQL-level isolation), AI agent with 9-dialect Arabic engine, webhooks for Messenger/WhatsApp/Instagram, order pipeline, Egypt shipping engine.
- **Auth**: JWT in httpOnly cookie, forwarded as Bearer server-side (never exposed to JS). Rate-limited login/register. SSRF-guarded crawling.

## Quick start (development)

```bash
# 1. Backend (from repos/zemest/)
cd repos/zemest
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env  # or use the provided .env
.venv/bin/python bootstrap_local.py       # creates SQLite DB + demo data
.venv/bin/python daemon_backend.py start  # API on :8000

# 2. Frontend (from repo root)
bun install
bun run dev                               # Next.js on :3000

# 3. Login
# owner@cairo-sneakers.com / OwnerPass123 (demo tenant: Cairo Sneakers)
```

## Production

```bash
cd repos/zemest && docker compose up -d   # Postgres 16 + Redis + API
# Frontend: bun run build && bun run start  (or Vercel with ZEMEST_BACKEND_URL set)
```

Set BEFORE going live (see ZEMEST_API_KEYS_GUIDE.md):
- `OPENROUTER_API_KEY` — makes the AI reply (without it: graceful fallback)
- `JWT_SECRET_KEY` — strong random (app refuses boot with default in production)
- `FB_APP_ID` / `FB_APP_SECRET` / page token — Messenger channel
- `DATABASE_URL` (postgres) + `REDIS_URL`

## Repo layout

```
src/                        # Next.js frontend (the ONE UI)
  app/                      # marketing (30+ pages), dashboard (live data), admin
  app/api/zemest/[...path]/ # BFF proxy (cookie → Bearer)
  app/api/auth/             # login/register/logout (set httpOnly cookie)
  lib/zemest-api.ts         # typed API client
repos/zemest/               # FastAPI backend
  app/api/                  # 80 endpoints (auth, tenants, products, orders, chat, crawl, admin)
  app/ai/                   # agent, prompts (Rabbit v1 / Rat v1), LLM client (pooled)
ZEMEST_MASTER_FIX_LIST.md   # every issue found/fixed/remaining
ZEMEST_API_KEYS_GUIDE.md    # exact steps for every external service
```

## Verified (2026-08-28, live-tested)

- Login → dashboard → live tenant stats ✓
- Orders: create (was 500, now 201), list, status state machine ✓
- AI chat: browser → BFF → agent round-trip (27ms fail-fast / ~1–3s with LLM key) ✓
- Products: list + create ✓ · Customers · Conversations · Crawl jobs (SSRF-guarded) ✓
- Settings: load + save ✓ · Shipping quotes (was 500, now 200 with Arabic messages) ✓
- Security: forged-JWT rejected, brute-force 429, file:// blocked, legacy dashboard gone ✓
