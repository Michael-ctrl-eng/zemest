# Zemest — API Keys & Services Guide (exact steps for everything you need)

The platform runs fully once you add these keys. **Priority order: get #1 first — it makes your AI agent actually talk.** Everything else connects channels.

---

## 1. OpenRouter (LLM brain) — REQUIRED, 5 minutes, has FREE models

Your agent's intelligence comes from here. Without it the agent replies with an apology (fallback mode).

1. Go to **https://openrouter.ai** → Sign up (email or Google)
2. Click your avatar → **Keys** → **Create key** → name it `zemest` → copy it (starts with `sk-or-`)
3. Add **$5–10 credit** (Credit tab) — OR use free models only (see below)
4. Put the key in `repos/zemest/.env`:
   ```
   OPENROUTER_API_KEY=sk-or-v1-your-key-here
   OPENROUTER_MODEL=meta-llama/llama-4-maverick:free
   ```
5. Restart the backend — chat playground will show **"LLM CONNECTED"** (green dot)

**Free models** (already your default): `meta-llama/llama-4-maverick:free`. Your backend auto-falls-back to `google/gemini-2.0-flash-001` and `qwen/qwen-2.5-72b-instruct` — **note: the fallbacks are PAID** (Gemini Flash ~$0.10/1M in-tokens, Qwen similar). If you want 100% free: set `OPENROUTER_MODEL=meta-llama/llama-4-maverick:free` and I can remove paid fallbacks for you. Rough cost: ~$0.002–0.01 per 100 customer messages on paid models.

## 2. Facebook App (Messenger + Instagram) — for the flagship channel, ~30 min + Meta review

This is how REAL customer messages reach your agent.

1. Go to **https://developers.facebook.com** → Log in → **My Apps** → **Create App** → type "Business"
2. Add products: **Messenger** (+ **Instagram** later if wanted)
3. **Messenger → Settings**: connect the Facebook PAGE you sell through (you must be its admin) → generate **Page Access Token** (never expires — save it)
4. **Webhooks**: add callback URL `https://your-domain.com/api/webhook/messenger` + verify token = the `FB_VERIFY_TOKEN` from your backend `.env` → subscribe to `messages`, `messaging_postbacks`
5. **App Review → Permissions**: request `pages_messaging` (needed to reply to real users). Until approved, only your app admins/testers can chat
6. Get **App ID + App Secret** (Settings → Basic) → put in `.env`:
   ```
   FB_APP_ID=your-app-id
   FB_APP_SECRET=your-app-secret
   ```
7. In the dashboard → Settings → Connect Facebook: paste the Page Access Token

⚠️ Your backend uses Graph API v21.0 (fine). Also still needs the OAuth callback route (F14 in fix list) before "Login with Facebook" works — the token-paste flow in Settings works TODAY without it.

## 3. WhatsApp Business API — the big Egyptian market channel, ~1 hour

NOT the free WhatsApp app — this is the Cloud API (free tier: 1000 conversations/month, then per-message ~$0.004–0.03 for Egypt).

1. Go to **https://business.facebook.com** → create a **Business Portfolio** if you don't have one
2. In Meta App (from step 2 above) add product: **WhatsApp** → follow the quickstart
3. It creates a **Test Number** instantly — you can start TODAY with it (send to max 5 numbers)
4. Get **Phone Number ID** + permanent **Access Token** (System User token with whatsapp_business_messaging permission)
5. Webhook: `https://your-domain.com/api/webhook/whatsapp` + same verify token
6. Put in `.env` / Settings:
   ```
   WA_PHONE_NUMBER_ID=...
   WA_ACCESS_TOKEN=...
   WA_WABA_ID=...
   ```
7. For a real number: register a number you own in the WhatsApp Manager → your customers can message it (requires a verified business)

## 4. PostgreSQL + Redis (production database) — REQUIRED before real customers, 15 min

Your backend ships with `docker-compose.yml` that creates everything:

1. Install Docker on your server: `curl -fsSL https://get.docker.com | sh`
2. On the server: `cd zemest && docker compose up -d` → creates Postgres 16 + Redis + the API
3. Set in `.env`:
   ```
   DATABASE_URL=postgresql+asyncpg://zemest:CHANGE_THIS_PASSWORD@db:5432/zemest
   REDIS_URL=redis://redis:6379/0
   JWT_SECRET_KEY=(run: python -c "import secrets;print(secrets.token_urlsafe(48))")
   APP_ENV=production
   ```
4. `docker compose up -d` again. The app auto-creates all tables on boot.

⚠️ **SQLite is for testing only** — single-writer, no concurrent webhooks.

## 5. Optional: Postiz (social media scheduling)

Only if you want the auto-posting/scheduler features. Self-hosted:

1. Follow **https://docs.postiz.com** (their docker-compose) — deploy on the same server
2. Create your Postiz login, then in zemest `.env`:
   ```
   POSTIZ_URL=http://postiz:4007
   POSTIZ_EMAIL=you@yourbusiness.com
   POSTIZ_PASSWORD=your-postiz-password
   ```
⚠️ SECURITY: current backend shares ONE Postiz session across tenants — **do not enable for multiple sellers until fixed** (S10 in fix list).

## 6. Optional: Email notifications (new order alerts)

Backend supports SMTP (aiosmtplib already installed):

1. Create a Gmail account → enable 2FA → create **App Password** (Google Account → Security → App passwords)
2. `.env`:
   ```
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USER=alerts@yourbusiness.com
   SMTP_PASSWORD=your-16-char-app-password
   NOTIFICATION_FROM_EMAIL=noreply@yourdomain.com
   ```

---

## What you DON'T need (already free/built-in)

- **Voice transcription** — local faster-whisper, zero cost, no key
- **Dialect detection** — regex fallback built-in; `camel-tools` install upgrades to 26-dialect detection (optional)
- **Product extraction** — trafilatura + JSON-LD/OG parsing, no key
- **Web crawling** — built-in (now SSRF-guarded)
- **Hosting to test** — the platform runs right here in preview

## Total monthly cost for first pilot (realistic)

| Service | Cost |
|---------|------|
| OpenRouter LLM | $0 (free model) – $10 |
| Server (Hetzner CPX21 / DigitalOcean $12–15) | ~$12 |
| WhatsApp Cloud API (≤1000 convos) | $0 |
| Postgres + Redis (self-hosted on server) | $0 |
| Domain | ~$10/year |
| **Total** | **~$12–25/month** |
