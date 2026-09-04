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
| 11 | `TELEGRAM_BOT_TOKEN` + `TELEGRAM_ADMIN_CHAT_ID` | @BotFather on Telegram → /newbot, then getUpdates for your chat id | free | ⬜ for instant report/alert notifications to your phone |
| 13 | `PAYONEER_API_TOKEN` + `PAYONEER_WEBHOOK_SECRET` (opt. `PAYONEER_PARTNER_ID`/`PAYONEER_PROGRAM_ID`) | Payoneer Checkout partner portal | per-market processing fee | ⬜ PRIMARY subscription rail (cards / wallet) |
| 14 | `USDC_TREASURY_WALLET` (opt. `SOLANA_RPC_URL` + `SOLANA_RPC_API_TOKEN`) | a wallet YOU control — the app is read-only on-chain | $0 monitoring | ⬜ crypto rail: USDC on Solana for wallet users |
| 15 | Paymob billing webhook — reuses the row-7 Paymob keys | — | — | ⬜ BACKUP subscription rail (Egypt EGP) |
| 12 | `VAULT_MASTER_KEY` | `python -c "import secrets; print(secrets.token_hex(32))"` (generate once, BACK IT UP) | free | ⬜ for the encrypted chat/profile vault (AES-256-GCM + zstd). Without it the vault panel shows "disabled" and everything else works |
| 13 | GitHub Actions secrets | **none needed** — CI uses the built-in `GITHUB_TOKEN` | free | — |
## 7. Billing payment rails — Payoneer (PRIMARY) / Paymob (BACKUP) / USDC-Solana (crypto)

The subscription stack runs on three rails with NO third-party subscription
service. Each rail is optional — `/api/billing/rails` (and the checkout
buttons) only shows the ones you configure. Plans are seeded automatically
(Starter 750 EGP / Growth 1,850 EGP / Pro 3,900 EGP per month, each with a
USDC price).

### 7a. Payoneer Checkout — the primary card rail (~30 min + approval)

1. Go to **https://www.payoneer.com** → Business account → apply for
   **Payoneer Checkout** (card acceptance for your market)
2. Once approved, open the partner/developer settings → generate a
   **server-to-server API token**
3. Configure the webhook: point it at
   `https://your-domain.com/api/payments/webhook/payoneer` and copy the
   signing secret the portal gives you
4. Put in `repos/zemest/.env`:
   ```
   PAYONEER_API_TOKEN=your-server-token
   PAYONEER_WEBHOOK_SECRET=whsec-from-the-portal
   PAYONEER_PARTNER_ID=optional
   PAYONEER_PROGRAM_ID=optional
   ```
   Optional header tweaks (only if your portal differs from the default):
   `PAYONEER_WEBHOOK_ALGO=sha256|sha512`, `PAYONEER_SIG_HEADER=X-Payoneer-Signature`

### 7b. Paymob — the backup rail for Egypt (EGP) (~1 hour)

Reuses the existing audited Paymob integration (Intention API).

1. Go to **https://egypt.paymob.com** → merchant dashboard → Developers
2. Create a **server-side secret key** (Token auth) and note your
   **integration ids** (card, wallet, installments…)
3. Dashboard → Webhooks → set the secret and point callbacks at
   `https://your-domain.com/api/payments/webhook/paymob` (billing) — buyer
   order payments keep using `/api/payments/webhook`
4. Put in `repos/zemest/.env`:
   ```
   PAYMOB_API_KEY=egy_sk_live_...
   PAYMOB_INTEGRATION_IDS=12345,6789
   PAYMOB_WEBHOOK_HMAC_SECRET=your-hmac-secret
   ```

### 7c. USDC on Solana — the crypto rail (~15 min, no approval)

For wallet users. The backend talks DIRECTLY to a Solana RPC node — there
is no sidecar service and no custody: the platform only watches the
treasury wallet.

1. Create a dedicated **treasury wallet** (hardware or hot wallet you
   control — NEVER paste its private key anywhere, the app does not sign)
2. Fund it with a little SOL for rent/fees if you will send from it
   (sending is done offline; the app only reads)
3. Put in `repos/zemest/.env`:
   ```
   USDC_TREASURY_WALLET=YourBase58TreasuryAddress
   SOLANA_RPC_URL=https://api.mainnet-beta.solana.com   # or your paid RPC
   # optional: SOLANA_RPC_API_TOKEN=... USDC_CONFIRMATIONS_REQUIRED=32
   ```
   The USDC mint is already the mainnet one; override `USDC_MINT_ADDRESS`
   for devnet testing.
4. Deposits are matched automatically by the hourly billing sweep (memo
   reference first, exact amount always required, confirmations gated)

### 7d. Shared billing settings (all rails)

```
BILLING_ENABLED=true
BILLING_WEBHOOK_PUBLIC_URL=https://your-domain.com
BILLING_USD_TO_EGP_RATE=48.0
BILLING_DUNNING_MAX_ATTEMPTS=4
USDC_AMOUNT_TOLERANCE=100            # micro-USDC (0.0001)
TREASURY_MIN_RESERVE_USDC=10.0
TREASURY_BANK_LABEL=Operator bank account (configured offline)
```

`BILLING_WEBHOOK_PUBLIC_URL` matters: it pins the callback origin so a
Host-header spoof cannot hijack notification URLs.

---

## What you DON'T need (already free/built-in)

- **Voice transcription** — local faster-whisper, zero cost, no key
- **Dialect detection** — regex fallback built-in; `camel-tools` install upgrades to 26-dialect detection (optional)
- **Product extraction** — trafilatura + JSON-LD/OG parsing, no key
- **Web crawling** — built-in (now SSRF-guarded)
- **Hosting to test** — the platform runs right here in preview
- **Crypto custody service** — the USDC rail is direct JSON-RPC against Solana: no sidecar, no signer, no key custody

**No analytics key exists and none is needed**: page-view/click analytics is
first-party (own backend, zstd+Fernet at rest) — no third-party script, no
GoatCounter account required anymore.

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

### Step 5b — Billing rails: Payoneer + Paymob + USDC-Solana (20 min, optional)

Full setup walkthroughs for the three subscription rails live in section 7
above: Payoneer Checkout (primary card rail), Paymob (Egypt backup rail —
reuses the step-5 Paymob keys) and USDC on Solana (crypto rail — just set
`USDC_TREASURY_WALLET` to a wallet you control; the platform watches the
chain directly with no sidecar and never holds private keys). Plans seed
themselves; `/api/billing/rails` shows exactly which rails are live, and
the dashboard billing page renders a checkout button for each one.

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
- **Any analytics vendor** — first-party click/view tracking ships with the
  app: events land in your own Postgres (zstd-compressed + Fernet-encrypted
  batches), dashboards + admin drill-down included. No key, no third-party
  script, no client-side PII.
- **Any AI key in the browser** — every AI call (chat/vision/voice) runs in
  FastAPI with server-side keys; the browser only ever talks to your own
  domain through the Next.js BFF (httpOnly cookie → Bearer). Regression
  test: `tests/security/test_no_client_secrets.py`.

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
- [ ] Browse the site once → admin dashboard shows the visit in
      "Recent Visitors" (first-party analytics live)
- [ ] Billing: subscribe with a real card on the hosted checkout →
      plan flips automatically (check /admin/billing → invoice paid)
- [ ] Billing: subscribe with a test card (Payoneer) → plan activates; USDC: send a micro test transfer → sweep settles it; withdrawal request flows through 2 approvals
- [ ] File a test report from a merchant dashboard → admin panel "Support
      Reports" + (if configured) the Telegram alert arrives with the code
- [ ] Register a second account from the same IP → it must start WITHOUT
      the 7-day trial (abuse prevention live)
- [ ] `docker compose ... ps` all healthy; disk >20% free

Fail something? `docker compose -f deploy/docker-compose.prod.yml logs
api` first — every failure mode above logs its cause (the app never fails
silently on boot).
