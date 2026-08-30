# Zemest — AI Agents for Facebook / Instagram / WhatsApp Moderation

> Premium, bitmap-effect platform for ready-made AI moderation agents. Built for
> businesses that want to moderate customer chats 24/7 across Facebook Messenger,
> Instagram Direct, and WhatsApp Business — with two specialist models, voice /
> image / text understanding, and auto-training on your existing chat history.
> No developer API to integrate — everything runs on our platform.

Zemest is an AI company that builds ready-made AI agents for moderating
Facebook, Instagram, and WhatsApp. Each tenant connects their page once, then
one of two specialist models takes over customer chats 24/7:

- **Rabbit v1** — Arabic specialist (Egyptian عامية, Arabizi, MSA).
- **Rat v1** — English specialist.

Both models understand **voice notes** (locally transcribed), **images**
(Gemini vision), and **text**, and are **auto-trained on each tenant's old
chats** across WA / FB / IG — so replies match the page's unique tone within
minutes of onboarding. There is **no developer API** to integrate; tenants
configure everything through the Zemest dashboard.

The stack is deliberately **free-only**: text generation runs on OpenRouter's
`:free` models or the Gemini free tier (≈1,000 conversations/day at <20% load),
voice notes are transcribed locally with faster-whisper (zero cost), and
product photos are analysed with Gemini 2.0 Flash vision on the same free key.
Graceful degradation is mandatory — a missing key never crashes a webhook, it
just skips that modality and keeps text chat alive.

Zemest ships production-ready: FastAPI + SQLAlchemy 2.0 async + Celery + Redis +
PostgreSQL 16, all orchestrated by Docker Compose, with an admin dashboard for
tenant management, product catalogue, order tracking, and live conversation
inspection.

---

## Features

- **Trilingual understanding** — Egyptian colloquial Arabic (عامية), Arabizi
  Latin-script shorthand, and English, all in the same conversation.
- **Voice notes** — local faster-whisper transcription (small / int8 / CPU),
  zero per-message cost, works offline after the first model download.
- **Image analysis** — customers send a product photo; Gemini 2.0 Flash vision
  identifies the item and matches it to the catalogue.
- **All 27 governorates shipping** — built-in Egyptian address model with
  governorate / city / area hierarchy, per-tenant inside-Cairo and
  outside-Cairo rates, and configurable free-shipping threshold.
- **Multi-tenant SaaS** — every page owner is an isolated tenant with their
  own customers, products, orders, style profile, and knowledge base.
- **Style learning** — Zemest ingests each tenant's chat history and builds a
  per-tenant style profile so replies match the page's unique tone.
- **Owner chat commands** — page owners can DM their own bot to update prices
  (`حدّث سعر X لـ N`), pause products, or query today's orders — all from
  Messenger.
- **Free-tier LLM stack** — OpenRouter `:free` models + Gemini free tier with
  automatic fallback chain; never requires a paid API key.
- **Web dashboard** — Jinja2-templated admin UI for tenants, products,
  orders, customers, conversations, crawl jobs, and settings.
- **Knowledge crawler** — Playwright + trafilatura crawl the tenant's website
  into a searchable knowledge base that the agent reasons over.
- **Order API bridge** — each tenant can configure an external order-receiving
  webhook with `{{placeholders}}` so Zemest drops orders into their existing
  ERP / Shopify / custom backend.
- **Social media scheduling** — schedule FB + IG posts (feed, photos, Reels,
  Stories) with AI-generated captions, best-time-to-post insights, and
  per-post engagement analytics. Powered by [Postiz](https://github.com/gitroomhq/postiz-app)
  running as a sidecar.
- **Style learning agent** — upload your chat history (FB DYI export / WhatsApp
  Export) and Zemest learns your tone, greeting patterns, emoji usage, and
  conversation flow in <40 seconds — zero ban risk (we parse locally, no API
  calls to Meta during analysis).
- **Webhook-safe** — every Meta webhook returns `200 EVENT_RECEIVED` in under
  a second; heavy work is offloaded to a Celery worker. Echo events are
  skipped to prevent feedback loops.
- **JWT dashboard auth** — bcrypt-hashed credentials, 24-hour access tokens.

---

## Tech Stack

| Layer            | Technology                                            |
|------------------|-------------------------------------------------------|
| Web framework    | FastAPI 0.115 + Uvicorn                               |
| ORM              | SQLAlchemy 2.0 async (asyncpg driver)                |
| Migrations       | Alembic 1.14                                          |
| Database         | PostgreSQL 16 (Alpine)                                |
| Task queue       | Celery 5.4 + Redis 7                                  |
| Auth             | python-jose (JWT) + passlib/bcrypt                    |
| Text LLM         | OpenRouter (`:free` models) with Gemini fallback      |
| Vision LLM       | Google Gemini 2.0 Flash (free tier)                   |
| Voice            | faster-whisper (local, CPU, int8)                     |
| Headless browser | Playwright 1.58 (Chromium)                            |
| LLM routing      | LiteLLM                                               |
| Templating       | Jinja2 (dashboard)                                    |
| Email            | aiosmtplib (async SMTP)                               |
| Containerisation | Docker (python:3.12-slim) + Docker Compose            |
| Testing          | pytest + pytest-asyncio + aiosqlite (in-memory)       |

---

## Architecture

```
                       ┌────────────────────────────────────────────┐
                       │                  Meta Platform              │
                       │  Facebook Messenger · Instagram · WhatsApp  │
                       └───────────────┬────────────────────────────┘
                                       │  HTTPS webhooks
                                       ▼
┌──────────────────────────────────────────────────────────────────────┐
│                        FastAPI app  (uvicorn)                         │
│                                                                      │
│   /api/webhook/{messenger,instagram,whatsapp}   (verify + dispatch)  │
│   /api/auth  /api/tenants  /api/products  /api/orders  /api/chat ...  │
│   /dashboard  (Jinja2 admin UI, JWT-protected)                       │
└───────┬───────────────────────────────┬──────────────────────────────┘
        │  enqueue tasks                │  async DB sessions
        ▼                               ▼
┌──────────────────┐         ┌────────────────────────────────────────┐
│   Celery worker  │         │          PostgreSQL 16                  │
│  (Redis broker)  │         │  tenants · customers · products ·       │
│                  │         │  orders · conversations · messages ·    │
│  - transcription │         │  crawl_jobs · token_usage · users       │
│  - notifications │         └────────────────────────────────────────┘
│  - crawl jobs    │
└────────┬─────────┘
         │  outbound calls
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       External services                              │
│   OpenRouter (text) · Gemini (text + vision) · Meta Graph API       │
│   (send replies) · SMTP (owner emails) · tenant ERP webhook         │
└─────────────────────────────────────────────────────────────────────┘
```

Webhook flow: Meta POSTs an event → FastAPI verifies the X-Hub-Signature-256
hmac, returns `200 EVENT_RECEIVED` immediately, and enqueues a Celery task.
The worker resolves the tenant, transcribes any voice note, runs any image
through Gemini vision, builds the agent prompt, calls the LLM provider chain
(OpenRouter → Gemini → localized fallback), persists the message and any
resulting order, and POSTs the reply back through the appropriate Meta Graph
API endpoint.

---

## Quick Start

### Prerequisites

- **Python 3.12+**
- **PostgreSQL 16** (or use the bundled Docker service)
- **Redis 7** (or use the bundled Docker service)
- **Docker** + **Docker Compose** (for the one-command path)

### Option A — Docker Compose (recommended)

```bash
# 1. Copy the environment template and fill in secrets
cp .env.example .env
#    → at minimum set OPENROUTER_API_KEY or GEMINI_API_KEY,
#      and change JWT_SECRET_KEY.

# 2. Boot the full stack (db, redis, app, celery_worker)
docker-compose up -d

# 3. Run database migrations
docker-compose exec app alembic upgrade head

# 4. (optional) Seed demo data — admin user + Egyptian Fashion Store tenant
docker-compose exec app python seed.py

# 5. Open the app
#    Interactive API docs : http://localhost:8000/docs
#    ReDoc                 : http://localhost:8000/redoc
#    Admin dashboard       : http://localhost:8000/dashboard
```

### Option B — Local development

```bash
# 1. Create a virtual environment
python -m venv .venv && source .venv/bin/activate

# 2. Install dependencies (includes Playwright; run `playwright install chromium` once)
pip install -r requirements.txt
playwright install chromium

# 3. Start Postgres + Redis (either install natively or via Docker)
docker run -d --name zemest-pg -e POSTGRES_USER=zemest -e POSTGRES_PASSWORD=zemest_secret \
    -e POSTGRES_DB=zemest -p 5432:5432 postgres:16-alpine
docker run -d --name zemest-redis -p 6379:6379 redis:7-alpine

# 4. Configure environment
cp .env.example .env

# 5. Run migrations + seed
alembic upgrade head
python seed.py

# 6. Start the API (in one terminal)
uvicorn app.main:app --reload

# 7. Start the Celery worker (in a second terminal)
celery -A app.tasks.celery_app worker --loglevel=info
```

### Option C — Production

See the [Deployment](#deployment) section below. The Dockerfile is
production-ready; pair it with a reverse proxy (Caddy / Nginx) that
terminates TLS and forwards to the container on port 8000.

---

## Configuration

All settings are loaded from environment variables (or a `.env` file) by
`app/config.py` using `pydantic-settings`. The full reference:

### App

| Variable      | Description                                              | Default     | Required |
|---------------|----------------------------------------------------------|-------------|----------|
| `APP_NAME`    | Friendly name shown in the FastAPI title and dashboard. | `Zemest` | no       |
| `APP_ENV`     | Runtime environment: `development` / `staging` / `production`. | `development` | no   |
| `APP_DEBUG`   | Enables verbose errors and the `/docs` + `/redoc` routes. **Always `False` in production.** | `False` | no |
| `APP_HOST`    | Host the uvicorn process binds to.                       | `0.0.0.0`   | no       |
| `APP_PORT`    | Port the uvicorn process binds to.                       | `8000`      | no       |

### Database

| Variable            | Description                                          | Default                                                          | Required |
|---------------------|------------------------------------------------------|------------------------------------------------------------------|----------|
| `DATABASE_URL`      | Async SQLAlchemy URL used by the FastAPI app.        | `postgresql+asyncpg://zemest:zemest_secret@localhost:5432/zemest` | yes      |
| `DATABASE_URL_SYNC` | Sync SQLAlchemy URL used by Alembic + Celery.        | `postgresql://zemest:zemest_secret@localhost:5432/zemest`        | yes      |

### Redis

| Variable    | Description                                                | Default                       | Required |
|-------------|------------------------------------------------------------|-------------------------------|----------|
| `REDIS_URL` | Redis connection used as Celery broker + result backend.   | `redis://localhost:6379/0`    | yes      |

### JWT

| Variable                       | Description                                              | Default                              | Required |
|--------------------------------|----------------------------------------------------------|--------------------------------------|----------|
| `JWT_SECRET_KEY`               | Secret used to sign access tokens. **Generate a strong random string.** | `change-me-to-a-random-secret-key` | yes      |
| `JWT_ALGORITHM`                | JWT signing algorithm.                                   | `HS256`                              | no       |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | Access-token lifetime in minutes.                     | `1440` (24 hours)                    | no       |

### OpenRouter

| Variable              | Description                                                | Default                                            | Required |
|-----------------------|------------------------------------------------------------|----------------------------------------------------|----------|
| `OPENROUTER_API_KEY`  | OpenRouter API key. Blank disables OpenRouter.             | `""`                                               | no\*     |
| `OPENROUTER_BASE_URL` | OpenRouter REST base URL.                                  | `https://openrouter.ai/api/v1`                     | no       |
| `OPENROUTER_MODEL`    | Default model. The `:free` suffix pins to the free tier.   | `meta-llama/llama-4-maverick:free`                 | no       |

### Gemini

| Variable          | Description                                                              | Default              | Required |
|-------------------|--------------------------------------------------------------------------|----------------------|----------|
| `GEMINI_API_KEY`  | Google AI Studio API key. Blank disables Gemini (voice + vision skipped).| `""`                 | no\*     |
| `GEMINI_MODEL`    | Gemini model name. `gemini-2.0-flash` covers text + vision on free tier. | `gemini-2.0-flash`   | no       |
| `LLM_PROVIDER`    | Provider preference: `auto` / `openrouter` / `gemini` / `ollama`.        | `auto`               | no       |

\*At least one of `OPENROUTER_API_KEY` or `GEMINI_API_KEY` must be set for
LLM-driven replies. If both are blank, Zemest falls back to a localized polite
reply and logs a warning.

### Facebook / Meta

| Variable             | Description                                                                | Default                              | Required |
|----------------------|----------------------------------------------------------------------------|--------------------------------------|----------|
| `FB_APP_ID`          | Facebook App ID (numeric).                                                 | `""`                                 | yes      |
| `FB_APP_SECRET`      | Facebook App Secret (used for X-Hub-Signature-256 verification).           | `""`                                 | yes      |
| `FB_VERIFY_TOKEN`    | Arbitrary string; must match the Verify Token in the Meta webhook config.  | `zemest-verify-token`                 | yes      |
| `FB_GRAPH_API_URL`   | Meta Graph API base URL (versioned).                                       | `https://graph.facebook.com/v21.0`   | no       |

### Whisper (voice transcription)

| Variable                | Description                                                       | Default  | Required |
|-------------------------|-------------------------------------------------------------------|----------|----------|
| `WHISPER_MODEL`         | Model size: `tiny` / `base` / `small` / `medium` / `large-v3`.   | `small`  | no       |
| `WHISPER_DEVICE`        | Device: `cpu` / `cuda`.                                           | `cpu`    | no       |
| `WHISPER_COMPUTE_TYPE`  | Compute type: `int8` / `int8_float16` / `float16` / `float32`.   | `int8`   | no       |

### Shipping defaults

| Variable                        | Description                                              | Default | Required |
|---------------------------------|----------------------------------------------------------|---------|----------|
| `DEFAULT_DELIVERY_INSIDE_CAIRO` | Default shipping fee inside Cairo (EGP).                 | `35`    | no       |
| `DEFAULT_DELIVERY_OUTSIDE_CAIRO`| Default shipping fee outside Cairo (EGP).                | `60`    | no       |
| `DEFAULT_FREE_DELIVERY_ABOVE`   | Free-shipping threshold (EGP). `0` disables.             | `300`   | no       |

### SMTP (owner notifications)

| Variable                  | Description                                              | Default              | Required |
|---------------------------|----------------------------------------------------------|----------------------|----------|
| `SMTP_HOST`               | SMTP server hostname.                                    | `smtp.gmail.com`     | no       |
| `SMTP_PORT`               | SMTP port (`587` = STARTTLS, `465` = implicit TLS).      | `587`                | no       |
| `SMTP_USER`               | SMTP username (usually the sender email).                | `""`                 | no\*     |
| `SMTP_PASSWORD`           | SMTP password / App Password. Blank disables owner emails. | `""`               | no\*     |
| `NOTIFICATION_FROM_EMAIL` | `From:` address on outgoing order-notification emails.   | `noreply@zemest.ai`  | no       |

\*SMTP_USER + SMTP_PASSWORD must both be set to enable owner email notifications.

---

## Meta App Setup

Zemest receives customer messages through Meta webhooks. You need a Facebook
Business App with three products enabled: **Messenger**, **Instagram**, and
**WhatsApp**. The same App ID / App Secret / Verify Token is reused across all
three channels; each channel gets its own webhook URL on Zemest's side.

### 1. Facebook Messenger

1. Go to <https://developers.facebook.com/> → **My Apps** → **Create App**.
   Choose **Business** as the type, name it (e.g. "Zemest"), and submit.
2. In the left sidebar, **Add Product** → **Messenger** → **Set Up**.
3. Scroll to **Access Tokens** → **Add or Remove Pages** → select your Facebook
   Page → copy the generated **Page Access Token**. Paste it into the tenant
   settings in the Zemest dashboard (`/dashboard/settings`).
4. Scroll to **Webhooks** → **Add Callback URL** and enter:
   ```
   https://yourdomain.com/api/webhook/messenger
   ```
   Set **Verify Token** to the same value as `FB_VERIFY_TOKEN` in your `.env`
   (default `zemest-verify-token`). Click **Verify and Save** — Meta will issue
   a `GET` challenge; Zemest responds `200` with the `hub.challenge` only if the
   token matches.
5. Under **Webhook Fields**, subscribe to: `messages`, `messaging_postbacks`,
   `message_deliveries`, `message_reads`.
6. Required permissions / scopes: `pages_messaging`, `pages_show_list`,
   `pages_manage_metadata`.

### 2. Instagram

1. In the same Facebook App, **Add Product** → **Instagram** → **Set Up**.
2. Convert your Instagram account to a **Business** account and link it to the
   Facebook Page from step 1 above (Meta Business Suite → Settings → Instagram).
3. In the tenant settings page on Zemest, paste the **Instagram Business User
   ID** and a long-lived **Instagram access token**. (Graph API:
   `GET /{ig-user-id}?fields=id,followers_count&access_token=...`.)
4. Webhooks → **Add Callback URL**:
   ```
   https://yourdomain.com/api/webhook/instagram
   ```
   Use the **same Verify Token** as Messenger. Subscribe to:
   `messages`, `messaging_postbacks`.
5. Required permissions: `instagram_manage_messages`,
   `instagram_basic`, `pages_show_list`.

### 3. WhatsApp Cloud API

1. In the same Facebook App, **Add Product** → **WhatsApp** → **Set Up**.
2. From the WhatsApp → **API Setup** tab, copy the **Phone Number ID** and a
   permanent **Access Token**. Paste both into the tenant settings on Zemest.
3. Note the **WhatsApp Business Account ID (WABA ID)** shown under
   WhatsApp → **Quickstart**; paste it into the tenant settings too.
4. Webhooks → **Add Callback URL**:
   ```
   https://yourdomain.com/api/webhook/whatsapp
   ```
   Same Verify Token as above. Subscribe to: `messages`, `message_status`.
5. Required permissions: `whatsapp_business_messaging`,
   `whatsapp_business_management`.

### Local testing with ngrok

Meta cannot reach `http://localhost`. Expose your local Zemest instance with:

```bash
ngrok http 8000
# → forwards https://abcd-1-2-3-4.ngrok-free.app → http://localhost:8000
```

Then use `https://abcd-1-2-3-4.ngrok-free.app/api/webhook/messenger` (etc.) as
the Callback URL in each Meta webhook subscription.

---

## Postiz (Social Media Scheduler)

Zemest integrates with [Postiz](https://github.com/gitroomhq/postiz-app)
(35k★, AGPL-3.0) as a sidecar service for social media scheduling and
insights. Postiz handles:

- **FB Page publishing** — feed posts, photos, videos, Stories
- **Instagram publishing** — feed posts, Reels (with audio), Stories,
  carousels (up to 10 images)
- **Scheduling** — durable Temporal workflows ensure posts go out on time
- **Insights** — reach, impressions, engagement, follower_count,
  best-time-to-post heatmap
- **AI caption generation** — Postiz's built-in LangChain + OpenAI integration

### Architecture

```
┌──────────────────────┐     ┌──────────────────────────┐
│  Zemest (FastAPI)    │────▶│  Postiz (NestJS, :4007)  │
│  app/scheduling/      │ API │  - FB/IG publishing       │
│  postiz_client.py     │◀────│  - Insights/analytics    │
└──────────────────────┘     │  - Best-time-to-post      │
                             │  - AI captions            │
                             └──────────────────────────┘
```

### Quick Start

1. **Postiz is already in `docker-compose.yml`** — just run:
   ```bash
   docker-compose up -d
   ```

2. **Access Postiz dashboard** at `http://localhost:4007`

3. **Create a Postiz account** (first run only):
   - Visit `http://localhost:4007` → register an admin account
   - Or use the API: `POST /api/tenants/{id}/postiz/login`

4. **Connect your Facebook Page + Instagram** in the Postiz dashboard
   (Settings → Integrations → Connect)

5. **Use our API** to schedule posts:
   ```bash
   # List connected accounts
   curl -H "Authorization: Bearer $JWT" \
     http://localhost:8000/api/tenants/$TENANT_ID/postiz/integrations

   # Schedule a post
   curl -X POST -H "Authorization: Bearer $JWT" \
     -H "Content-Type: application/json" \
     -d '{"integration_id":"...","caption":"Hello!","schedule_at":"2026-01-01T10:00:00Z"}' \
     http://localhost:8000/api/tenants/$TENANT_ID/postiz/posts
   ```

### Postiz API Endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/tenants/{id}/postiz/health` | GET | Check if Postiz is running |
| `/api/tenants/{id}/postiz/login` | POST | Login to Postiz |
| `/api/tenants/{id}/postiz/integrations` | GET | List connected social accounts |
| `/api/tenants/{id}/postiz/connect/{provider}` | POST | Get OAuth URL |
| `/api/tenants/{id}/postiz/posts` | POST | Create/schedule a post |
| `/api/tenants/{id}/postiz/posts` | GET | List posts |
| `/api/tenants/{id}/postiz/posts/{id}/stats` | GET | Get post insights |
| `/api/tenants/{id}/postiz/posts/{id}/reschedule` | PUT | Reschedule a post |
| `/api/tenants/{id}/postiz/posts/{group_id}` | DELETE | Delete a post |
| `/api/tenants/{id}/postiz/best-time` | GET | Find next free posting slot |
| `/api/tenants/{id}/postiz/generate` | POST | AI caption generation |

### Configuration

Postiz-specific env vars (in `.env`):

```env
POSTIZ_URL=http://localhost:4007
POSTIZ_EMAIL=admin@zemest.ai
POSTIZ_PASSWORD=your-postiz-password
POSTIZ_JWT_SECRET=change-me-to-random-string-postiz
FACEBOOK_APP_ID=your-fb-app-id
FACEBOOK_APP_SECRET=your-fb-app-secret
```

> **Note:** Postiz runs its own Postgres + Redis + Temporal stack. These are
> separate from Zemest's DB/Redis and are managed by the `postiz-postgres`
> and `postiz-redis` services in docker-compose.

> **AGPL-3.0 License:** Postiz is licensed under AGPL-3.0. If you modify
> Postiz's source code and host it as a service, you must open-source your
> modifications. Running it unmodified as a sidecar does not trigger this
> requirement.

---

## Database Migrations

Alembic manages the schema. The migration chain lives in `alembic/versions/`
and is idempotent — `app/main.py` also runs an idempotent `ALTER TABLE ADD
COLUMN` batch on startup so missing columns are auto-added.

```bash
# Apply all pending migrations
alembic upgrade head

# Inspect current revision
alembic current

# Roll back one revision
alembic downgrade -1

# Generate a new migration after model changes
alembic revision --autogenerate -m "describe your change"
```

> **Note:** `alembic.ini` ships with a placeholder `sqlalchemy.url` for
> local-only use. Production should rely on the `DATABASE_URL_SYNC`
> environment variable (already wired through `app/config.py`).

---

## Testing

The test suite uses **SQLite in-memory** via `aiosqlite`, so you do **not**
need PostgreSQL or Redis installed to run it.

```bash
pytest                       # full suite, ~120+ tests
pytest -v                    # verbose
pytest tests/test_orders.py  # single file
pytest --cov=app             # with coverage
```

The suite covers: auth flow, tenant CRUD, products, orders + shipping math,
phone validation, Egyptian address normalisation, language detection, webhook
signature verification (good + bad token + bad signature), the order collector
state machine, and the full simulated chat flow via `/api/test/chat`.

---

## Deployment

### Production checklist

- [ ] Set `APP_ENV=production` and `APP_DEBUG=False`.
- [ ] Generate a strong random `JWT_SECRET_KEY`
      (`python -c "import secrets; print(secrets.token_urlsafe(48))"`).
- [ ] Rotate `FB_VERIFY_TOKEN` away from the default `zemest-verify-token`.
- [ ] Use a managed Postgres 16 instance; rotate the `zemest_secret` DB password
      and update `DATABASE_URL` + `DATABASE_URL_SYNC` accordingly.
- [ ] Use a managed Redis 7 instance (or a Redis container with persistence
      and a `requirepass`); update `REDIS_URL`.
- [ ] Configure SMTP (`SMTP_HOST` / `SMTP_USER` / `SMTP_PASSWORD`) so order
      notifications actually reach page owners.
- [ ] Put the app behind a TLS-terminating reverse proxy (Caddy / Nginx /
      Cloudflare). Meta **requires** HTTPS webhook URLs.
- [ ] Set at least one of `OPENROUTER_API_KEY` or `GEMINI_API_KEY`.
- [ ] Run `alembic upgrade head` before starting the app container.
- [ ] Run the Celery worker as a separate container / process — without it,
      voice transcription, owner notifications, and crawl jobs will not fire.
- [ ] Set up health checks on `/docs` (200 = alive) and the Docker Compose
      healthchecks for `db` and `redis`.

### Minimal production Docker invocation

```bash
# Build once
docker build -t zemest:latest .

# Run the API
docker run -d --name zemest-api \
    --env-file .env \
    -p 8000:8000 \
    zemest:latest \
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4

# Run the Celery worker (same image, different command)
docker run -d --name zemest-worker \
    --env-file .env \
    zemest:latest \
    celery -A app.tasks.celery_app worker --loglevel=info
```

### Scaling notes

- The FastAPI app is stateless — scale horizontally behind a load balancer.
- Run one Celery worker per CPU core for voice transcription (CPU-bound).
- Gemini's free tier is capped at **15 RPM / 1M tokens per day**. At sustained
  load, supplement with OpenRouter `:free` models and set `LLM_PROVIDER=auto`.
- The `token_usage` table tracks per-tenant LLM spend; query it to monitor
  free-tier burn rate.

---

## API Documentation

Once the app is running, the full OpenAPI schema is auto-generated:

- **Swagger UI** — <http://localhost:8000/docs>
- **ReDoc** — <http://localhost:8000/redoc>
- **OpenAPI JSON** — <http://localhost:8000/openapi.json>

Top-level route groups (all prefixed `/api`):

| Prefix                | Module                          | Purpose                                         |
|-----------------------|---------------------------------|-------------------------------------------------|
| `/api/auth`           | `app/api/auth.py`               | Login, JWT issuance, current user.              |
| `/api/tenants`        | `app/api/tenants.py`            | Tenant CRUD + per-tenant settings.              |
| `/api/products`       | `app/api/products.py`           | Product catalogue CRUD.                         |
| `/api/orders`         | `app/api/orders.py`             | Order list / detail / status updates.           |
| `/api/conversations`  | `app/api/conversations.py`      | Conversation + message history.                 |
| `/api/customers`      | `app/api/customers.py`          | Customer directory.                             |
| `/api/address`        | `app/api/address.py`            | Egyptian governorate / city / area lookups.     |
| `/api/crawl`          | `app/api/crawl.py`              | Trigger website knowledge-base crawls.          |
| `/api/webhook`        | `app/api/webhook.py`            | Meta webhooks (messenger / instagram / whatsapp).|
| `/api/facebook`       | `app/api/facebook.py`           | OAuth + page-subscription helpers.              |
| `/api/test/chat`      | `app/api/test_chat.py`          | Simulated chat for end-to-end testing.          |
| `/dashboard`          | `app/api/dashboard.py`          | Jinja2 admin UI (JWT-protected).                |

---

## License

Released under the **MIT License**. See `LICENSE` for the full text.

---

## Contributing

Contributions are welcome. The short version:

1. Fork the repo and create a feature branch (`git checkout -b feat/...`).
2. Run `pytest` before pushing — every PR must keep the suite green.
3. Follow the existing code style (Black-compatible, 4-space indent).
4. If you touch models, regenerate an Alembic migration
   (`alembic revision --autogenerate -m "..."`) and verify both `upgrade` and
   `downgrade` apply cleanly.
5. Do not introduce paid-only dependencies — the free-tier constraint is a
   hard requirement (see Section 0 of `MASTER_PROMPT.md`).
6. Open a PR with a clear description of what changed and why.

For major changes, please open an issue first to discuss scope.
