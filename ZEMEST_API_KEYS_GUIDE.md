# Zemest — Production Setup: Every Key, Every Step (zero → live)

This is the **one canonical guide**. It covers every API key you need, where
to get each one, what it costs, and the exact step-by-step to go from an
empty VPS to a production deployment serving real customers on
Facebook / Instagram / WhatsApp.

Companions (read when relevant):
- `repos/zemest/docs/AI-STRATEGY.md` — which AI model, self-host vs API, batching (already answered: hosted APIs, no self-hosting, per-conversation replies)
- `repos/zemest/docs/SCALING.md` — capacity math, 10K→100K path, job correctness
- `deploy/README.md` — the tiny-pilot alternative (systemd + SQLite, 2-4 GB VPS)

---

## 0. What you are deploying (60 seconds)

```
                your-domain.com
                      │
                 Caddy (auto-TLS, rate limit)
                /        |         \
   browser /api/*   Meta+Paymob      all other pages
        │            server callbacks       │
   Next.js web (BFF:   │                    │
   cookies, CSRF)      │                    │
        │              │                    │
   FastAPI api ×2 ─────┘              Next.js web
        │
   Postgres 16 + pgbouncer + Redis
   scheduler ×1 (publish posts on time) + worker ×1 (crawls, notifications)
```

**Nothing else is required**: voice transcription runs locally (Whisper),
the LLM comes from OpenRouter's hosted models, image understanding from
Gemini's hosted vision API. You never run a model on your own box.

**Cost at your €5–8/month budget** (pilot → ~2K users): VPS ~€4–6, LLM €0
(free tier), WhatsApp €0 (customer-service conversations), email €0
(free tier), domain ~$10/year. **Total ≈ €5–7/month.**
At 10K users/day: bigger VPS (~€15) + optional paid LLM overflow — see
AI-STRATEGY.md §2 for the exact math.

---

## 1. The complete key table

| # | Key / secret | Where to get it | Cost | Required? |
|---|---|---|---|---|
| 1 | `ZEMEST_DOMAIN` | your domain registrar (Namecheap/Cloudflare) | ~$10/yr | ✅ yes |
| 2 | `POSTGRES_PASSWORD`, `JWT_SECRET_KEY`, `TOKEN_ENCRYPTION_KEY`, `FB_VERIFY_TOKEN` | generate yourself (commands below) | free | ✅ yes |
| 3 | `OPENROUTER_API_KEY` | https://openrouter.ai → Keys | free models / $5–10 credit for fallbacks | ✅ yes (AI replies) |
| 4 | `GEMINI_API_KEY` | https://aistudio.google.com/apikey | free tier | ✅ for image understanding; optional otherwise |
| 5 | `FB_APP_ID` + `FB_APP_SECRET` | https://developers.facebook.com → your app → Settings → Basic | free | ✅ for Messenger/IG/WA channels |
| 6 | Meta **Page Access Token** / WA **Phone Number ID + token** | per merchant, in the dashboard (stored Fernet-encrypted) | free | ✅ per channel you connect |
| 7 | `PAYMOB_API_KEY` + `PAYMOB_WEBHOOK_HMAC_SECRET` + `PAYMOB_INTEGRATION_IDS` | https://egypt.paymob.com → Developers | ~2.75%+3 EGP per transaction (charged to the buyer, not you monthly) | ⬜ for online payments (COD works without it) |
| 8 | `SMTP_*` + `NOTIFICATION_FROM_EMAIL` | Brevo (300/day) / Resend (100/day) / Gmail app-password | free tier | ⬜ for order-email alerts |
| 9 | `ADMIN_EMAIL` + `ADMIN_PASSWORD` | you pick them | free | ✅ first admin login |
| 10 | `POSTIZ_*` (3 vars) | your Postiz instance | free self-hosted | ⬜ optional post scheduler sidecar |
| 11 | GitHub Actions secrets | **none needed** — CI uses the built-in `GITHUB_TOKEN` | free | — |

Every one of these has a pre-filled slot in **`deploy/.env.example`** —
that file is your checklist. Copy it to `deploy/.env`, fill it, done.

---

## 2. Step-by-step deployment

### Step 1 — VPS + DNS (10 min)

1. Buy a VPS. At your budget: **Hetzner CX22** (2 vCPU / 4 GB, ~€4–6/mo,
   EU locations — Nuremberg/Falkenstein have good Cairo latency).
   For the full 10K-users/day shape later: 8 vCPU / 16 GB (see SCALING.md).
2. Buy the domain, create an **A record** pointing at the VPS IPv4
   *before first boot* (Caddy gets its TLS certificate at boot and Let's
   Encrypt validates the DNS).
3. Baseline firewall (Ubuntu/Debian):
   ```bash
   apt update && apt -y upgrade
   apt -y install docker.io docker-compose-v2 git ufw
   ufw allow OpenSSH && ufw allow 80,443/tcp && ufw --force enable
   ```

### Step 2 — Boot the stack (10 min)

```bash
git clone https://github.com/Michael-ctrl-eng/zemest.git /opt/zemest
cd /opt/zemest

cp deploy/.env.example deploy/.env
chmod 600 deploy/.env
nano deploy/.env        # fill everything (next steps explain each key)
```

Generate the four self-made secrets (paste into `deploy/.env`):

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(24))"   # POSTGRES_PASSWORD
python3 -c "import secrets; print(secrets.token_urlsafe(48))"   # JWT_SECRET_KEY
python3 -c "import secrets; print(secrets.token_urlsafe(24))"   # FB_VERIFY_TOKEN
docker run --rm python:3.12-slim python -c \
  "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"  # TOKEN_ENCRYPTION_KEY
```

> ⚠️ Save `TOKEN_ENCRYPTION_KEY` in a password manager — it encrypts every
> merchant's channel tokens at rest. Lose it = every connected channel
> must be re-connected.

Set in the same file: `ZEMEST_DOMAIN=your-domain.com`,
`PUBLIC_BASE_URL=https://your-domain.com`,
`FB_OAUTH_REDIRECT_ORIGIN=https://your-domain.com`,
`ADMIN_EMAIL=you@your-domain.com`, `ADMIN_PASSWORD=<strong password>`,
`POSTGRES_DB=zemest`, `POSTGRES_USER=zemest`.

Then:

```bash
cd /opt/zemest
docker compose -f deploy/docker-compose.prod.yml up -d
docker compose -f deploy/docker-compose.prod.yml ps   # everything "healthy"
```

What the first boot does automatically: creates the full database schema,
applies all column/index patches idempotently, creates your superadmin
from `ADMIN_EMAIL`/`ADMIN_PASSWORD` (only if no admin exists), obtains the
TLS certificate, and starts 2 API replicas + scheduler + worker.

Verify:
```bash
curl -s https://your-domain.com/          # {"status":"ok",...}
curl -s https://your-domain.com/healthz   # {"status":"ok","db":"up"}  ← deep check
```

### Step 3 — AI keys (5 min) → the agent can talk

**OpenRouter (text — 95% of AI traffic)**
1. https://openrouter.ai → sign up → avatar → **Keys** → Create key
   (`zemest`), copy `sk-or-...`
2. Add $5–10 credit (Credit tab) — covers the paid fallback models for
   months; the **default model is free** (`meta-llama/llama-4-maverick:free`).
3. `deploy/.env`: `OPENROUTER_API_KEY=sk-or-...`,
   `OPENROUTER_MODEL=meta-llama/llama-4-maverick:free`
4. `docker compose -f deploy/docker-compose.prod.yml up -d` (recreate)

**Gemini (images — customers sending product photos)**
1. https://aistudio.google.com/apikey → Create API key
2. `GEMINI_API_KEY=AIza...` in `deploy/.env`, recreate.

Voice notes need **no key** — transcription runs locally with Whisper.

### Step 4 — Meta app (30 min + review time) → real customer messages

One Meta app powers Messenger + Instagram + WhatsApp.

1. https://developers.facebook.com → **My Apps** → **Create App** → type
   *Business*. Copy **App ID / App Secret** → `FB_APP_ID`, `FB_APP_SECRET`.
2. Add products: **Messenger**, **Instagram**, **WhatsApp**.
3. **Webhooks** (App Dashboard → Webhooks, per product):

   | Product | Callback URL | Verify token |
   |---|---|---|
   | Messenger | `https://your-domain.com/api/webhook/messenger` | your `FB_VERIFY_TOKEN` |
   | Instagram | `https://your-domain.com/api/webhook/instagram` | same |
   | WhatsApp | `https://your-domain.com/api/webhook/whatsapp` | same |

   Subscribe to `messages` + `messaging_postbacks` (Messenger/IG) and
   `messages` (WhatsApp). "Verify and save" must succeed — the app answers
   Meta's challenge instantly (fast lane, no auth needed).
4. **OAuth login for merchants** (App Dashboard → Facebook Login →
   Settings → Valid OAuth Redirect URIs): add exactly
   `https://your-domain.com/api/facebook/oauth/callback`.
5. **App Review → Permissions**: request
   `pages_messaging` (Messenger), `instagram_manage_messages` (IG DMs),
   `whatsapp_business_messaging` (WA). Until approved, only app
   admins/testers can chat with the agents — invite your beta merchants as
   testers to start immediately.
6. Restart the stack (`up -d`) so the new `FB_*` values load.

**Per-merchant connection (in the Zemest dashboard, not env vars):**
each merchant registers, then Dashboard → Settings → **Connect
Facebook/Instagram/WhatsApp** — either the OAuth button (Meta consent →
page picker → token stored Fernet-encrypted) or paste a Page Access Token
/ WA `Phone Number ID` + `Access Token` / IG business account id + token.
WhatsApp: start with Meta's free **test number** (sends to 5 verified
numbers), then register a real number in the WhatsApp Manager once your
business is verified.

WhatsApp pricing reality (2025/26): conversations a customer *starts*
(service conversations) are **free**; only template *marketing* messages
are billed per-conversation (~$0.004–0.03 for Egypt) — check Meta's
current pricing page when you scale.

### Step 5 — Paymob (15 min) → online payments (optional; COD works without)

1. https://egypt.paymob.com → create a merchant account (Egypti business
   documents required) → portal → **Developers**:
   - **API key** → `PAYMOB_API_KEY`
   - **Webhooks/Settings → HMAC secret** → `PAYMOB_WEBHOOK_HMAC_SECRET`
   - Payment integration IDs (card/wallet) → `PAYMOB_INTEGRATION_IDS`
     (comma-separated, e.g. `12345,6789`)
2. The callback URL is automatic: Paymob posts to
   `https://your-domain.com/api/payments/webhook` (built from
   `PUBLIC_BASE_URL`, HMAC-verified, Host-header-proof).
3. Recreate the stack. Deposits (عربون) and full online payments now work;
   COD remains the default rail.

### Step 6 — Email alerts (5 min, optional)

Brevo (free 300/day): signup → SMTP & API → create an SMTP key.
`deploy/.env`: `SMTP_HOST=smtp-relay.brevo.com`, `SMTP_PORT=587`,
`SMTP_USER=...`, `SMTP_PASSWORD=...`, `NOTIFICATION_FROM_EMAIL=noreply@your-domain.com`.
(Gmail also works: 2FA → App Password.)

### Step 7 — Postiz sidecar (optional, social scheduling UI)

```bash
docker compose -f deploy/docker-compose.prod.yml --profile postiz up -d
```
Fill `POSTIZ_JWT_SECRET` (generate) + `POSTIZ_POSTGRES_PASSWORD` first.
Per-tenant Postiz sessions are isolated by the backend — merchants never
share a login. Reach it by adding a `postiz.your-domain.com` reverse-proxy
site to the Caddyfile when you want it public.

### Step 8 — Go-live verification (10 min)

Run every line; all must pass:

```bash
curl -s https://your-domain.com/                          # {"status":"ok"...}
curl -s https://your-domain.com/healthz                   # db":"up"
# webhook verification answers Meta's challenge (replace token):
curl -s "https://your-domain.com/api/webhook/messenger?hub.mode=subscribe&hub.verify_token=YOUR_FB_VERIFY_TOKEN&hub.challenge=ping123"
# → must echo: ping123
```

Then the human end-to-end test (as a tester, before app review):
register a merchant account → connect the FB test page → send it a
message as a page visitor → agent replies within seconds → place an order
in chat → order appears in dashboard → (if Paymob on) pay the deposit →
status flips to paid.

### Step 9 — Backups + monitoring (15 min, once)

```bash
# nightly DB backup (cron on the VPS):
crontab -e
# 3:30 every night: dump + keep 14 days
30 3 * * * docker exec $(docker ps -qf name=db) pg_dump -U zemest zemest | gzip > /var/backups/zemest-$(date +\%F).sql.gz && find /var/backups -name 'zemest-*.sql.gz' -mtime +14 -delete
```

- Restore drill (do it once, on a copy):
  `gunzip < backup.sql.gz | docker exec -i $(docker ps -qf name=db) psql -U zemest zemest`
- Uptime: point a free monitor (UptimeRobot/BetterStack) at
  `https://your-domain.com/healthz` — the deep probe (503 = DB down, not
  just "process alive").
- Google Search Console: add your domain, submit
  `https://your-domain.com/sitemap.xml` (blog SEO indexing).
- Optional analytics: GoatCounter (free, no cookies) — put your site code
  in `NEXT_PUBLIC_GOATCOUNTER_CODE` at frontend build time.

---

## 3. Ops runbook (day-2+)

| Task | Command |
|---|---|
| Logs (API) | `docker compose -f deploy/docker-compose.prod.yml logs -f api` |
| Logs (scheduler/worker) | `... logs -f scheduler` / `... logs -f worker` |
| Restart everything | `docker compose -f deploy/docker-compose.prod.yml restart` |
| Deploy an update | `cd /opt/zemest && git pull && docker compose -f deploy/docker-compose.prod.yml up -d --build` |
| Roll one API replica (zero downtime) | `docker compose -f deploy/docker-compose.prod.yml up -d --no-deps api` |
| DB shell | `docker exec -it $(docker ps -qf name=db) psql -U zemest` |
| Queue backlog | `... logs worker \| grep -i huey` (growing backlog → raise worker `replicas: 2`) |
| Rotating JWT secret | set new `JWT_SECRET_KEY` + `up -d` (sessions re-login) |
| Rotating Fernet key | set new `TOKEN_ENCRYPTION_KEY` + merchants re-connect channels |

TLS certificates renew automatically (Caddy). Postgres is the single
point of failure on one host — the nightly dump is your safety net until
a streaming replica is worth it (SCALING.md §failover).

---

## 4. What you do NOT need (already built-in, zero keys)

- **Voice transcription** — local faster-whisper (CPU, free, offline-capable)
- **Dialect detection** — built-in regex + optional CAMeL upgrade
- **Product extraction / web crawl** — built-in (SSRF-guarded)
- **CI/CD secrets** — GitHub Actions uses the automatic `GITHUB_TOKEN`
  (gitleaks, CodeQL, zizmor, audits all run keyless)
- **A model server** — never self-host on this budget (AI-STRATEGY.md §1)
- **Postiz for basic scheduling** — the native scheduler publishes due
  posts every 30 s with CAS guards; Postiz is the optional UI sidecar

---

## 5. Go-live checklist

- [ ] DNS A record → VPS; `curl https://your-domain.com/healthz` = `db:up`
- [ ] `deploy/.env` chmod 600; secrets generated (not defaults)
- [ ] `ADMIN_EMAIL` login works; demo accounts from dev are NOT in prod DB
- [ ] OpenRouter key set → demo chat on the site replies
- [ ] Gemini key set (if image flow wanted)
- [ ] Meta app: 3 webhooks verified; OAuth redirect URI whitelisted;
      app review submitted (`pages_messaging` etc.)
- [ ] One merchant connected per channel; test message answered
- [ ] Order → dashboard → (Paymob → paid) end-to-end
- [ ] Nightly `pg_dump` cron + one restore drill
- [ ] Uptime monitor on `/healthz`
- [ ] Search Console + sitemap submitted
- [ ] `docker compose ... ps` all healthy; disk >20% free

Fail something? `docker compose -f deploy/docker-compose.prod.yml logs
api` first — every failure mode above logs its cause (the app never fails
silently on boot).
