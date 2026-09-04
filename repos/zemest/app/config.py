from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Zemest"
    APP_ENV: str = "development"
    APP_DEBUG: bool = False
    # Loopback by default (bandit B104 / G4 deployment posture): the BFF proxy
    # reaches the backend over localhost; set explicitly when containerizing.
    APP_HOST: str = "127.0.0.1"
    APP_PORT: int = 8000

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://zemest:zemest_secret@localhost:5432/zemest"
    DATABASE_URL_SYNC: str = "postgresql://zemest:zemest_secret@localhost:5432/zemest"

    # Redis (optional — LLM gateway semantic cache / rate-limit backend;
    # the task queue no longer uses it: Huey is SQLite-native)
    REDIS_URL: str = "redis://localhost:6379/0"

    # Rate limiting master switch (slowapi). Set RATELIMIT_ENABLED=false in
    # tests — the in-memory limiter is a process-wide singleton whose
    # counters accumulate across the whole pytest run and 429 late tests.
    RATELIMIT_ENABLED: bool = True

    # JWT
    JWT_SECRET_KEY: str = "change-me-to-a-random-secret-key"
    JWT_ALGORITHM: str = "HS256"
    # Short-lived access tokens (30 min). Long sessions are sustained by
    # refresh-token rotation on /api/auth/refresh — a stolen access token
    # is only useful for half an hour, and a stolen REFRESH token is
    # detected on reuse (all sessions revoked).
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # OpenRouter (free models)
    OPENROUTER_API_KEY: str = ""
    # Multi-key rotation for concurrent load: comma-separated list; a key
    # that trips a 429 is cooled down 60s and the next key is used.
    OPENROUTER_API_KEYS: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_MODEL: str = "meta-llama/llama-4-maverick:free"
    # Max in-flight LLM calls (queues excess instead of 429-storming).
    LLM_MAX_CONCURRENCY: int = 8

    # Gemini (free: 15 RPM, 1M tokens/day)
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.0-flash"

    # LLM provider selection: auto | openrouter | gemini | ollama
    LLM_PROVIDER: str = "auto"

    # At-rest encryption key for channel tokens (Fernet). Empty → derived
    # from JWT_SECRET_KEY via SHA-256 (zero-config still encrypted).
    # Rotate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    TOKEN_ENCRYPTION_KEY: str = ""

    # Facebook
    FB_APP_ID: str = ""
    FB_APP_SECRET: str = ""
    FB_VERIFY_TOKEN: str = "zemest-verify-token"
    # Graph version bump: v21.0 → v22.0 (Meta deprecates old versions ~2 yrs;
    # v21 entered deprecation 2025). All Graph calls go through
    # app/services/graph_client.py (Bearer-only) — one place to bump again.
    FB_GRAPH_API_URL: str = "https://graph.facebook.com/v22.0"
    # Origin used to build the OAuth redirect_uri in the callback (must match
    # the /channels/oauth-url origin). Set to your public frontend origin.
    FB_OAUTH_REDIRECT_ORIGIN: str = "https://localhost:3000"

    # Voice transcription (faster-whisper, local, free)
    WHISPER_MODEL: str = "small"
    WHISPER_DEVICE: str = "cpu"
    WHISPER_COMPUTE_TYPE: str = "int8"

    # Shipping defaults (Egyptian governorates)
    DEFAULT_DELIVERY_INSIDE_CAIRO: float = 35
    DEFAULT_DELIVERY_OUTSIDE_CAIRO: float = 60
    DEFAULT_FREE_DELIVERY_ABOVE: float = 300

    # Notifications
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    NOTIFICATION_FROM_EMAIL: str = "noreply@zemest.ai"

    # Telegram admin alerts (optional — reports/abuse notifications).
    # Empty = fully inert; see app/services/telegram_notify.py for the
    # one-time BotFather setup steps.
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_ADMIN_CHAT_ID: str = ""

    # --- Encrypted data vault (AES-256-GCM + zstd/gzip) --------------------
    # Archives chat histories, customer profiles and user profiles as
    # compressed+encrypted files under VAULT_DIR (app/services/vault.py).
    # Master key: 32-byte hex (64 chars) or base64 — generate with:
    #   python -c "import secrets; print(secrets.token_hex(32))"
    VAULT_MASTER_KEY: str = ""
    VAULT_DIR: str = "data/vault"

    # Postiz (social media scheduler sidecar)
    POSTIZ_URL: str = "http://localhost:4007"
    POSTIZ_EMAIL: str = ""
    POSTIZ_PASSWORD: str = ""

    # Task queue — Huey (SqliteHuey): durable retries without Redis.
    # HUEY_INLINE_CONSUMER: start the embedded 1-worker consumer in this
    # process (single-process deployment). Set False + run the
    # `huey_consumer` CLI separately when scaling out.
    HUEY_ENABLED: bool = True
    HUEY_INLINE_CONSUMER: bool = True
    HUEY_SQLITE_PATH: str = "huey_queue.db"
    # Multi-service deployments (docker-compose.prod.yml): the dedicated
    # worker container owns the consumer. API replicas set this True so
    # call sites ENQUEUE (durable, exactly-once) instead of checking for a
    # local consumer and falling back to inline execution on the API loop.
    # Requires HUEY_SQLITE_PATH to point at a file ALL services share
    # (same docker volume). No effect in single-process mode.
    HUEY_EXTERNAL_WORKER: bool = False

    # Periodic publish job (APScheduler; publishes due posts inside uvicorn).
    # Set false when an external `huey_consumer`/beat-style deployment owns it.
    SCHEDULER_INLINE_WORKER: bool = True

    # In-process silent trainer (APScheduler interval job that classifies
    # junk vs commerce chats and builds the page's style profile with zero
    # user interaction; set false when training moves to an external worker)
    SILENT_TRAINER_INLINE_WORKER: bool = True

    # Paymob online payments (Intention API — see docs/PAYMENTS.md (content folded into the module docstrings)).
    # COD stays the default rail; Paymob powers the deposit-to-confirm
    # (عربون) flow and full online payments. All values are env-overridable
    # and empty by default (no real keys in code).
    PAYMOB_API_KEY: str = ""  # server-side secret key (Token auth)
    PAYMOB_INTEGRATION_IDS: str = ""  # comma-separated payment-method ids, e.g. "12345,6789"
    PAYMOB_WEBHOOK_HMAC_SECRET: str = ""  # HMAC-SHA512 webhook signing secret
    PAYMOB_BASE_URL: str = "https://egypt.paymob.com"  # Egypt region Intention API base
    PAYMOB_CURRENCY: str = "EGP"
    # Minimum deposit accepted for a payment intention (audit A4-L4: a
    # 1-piaster "deposit" previously confirmed an order).
    PAYMOB_MIN_DEPOSIT_EGP: float = 1.0
    # Canonical public origin for outbound webhook URLs (audit A4-M3: the
    # notification_url was built from the request Host header — a poisoned
    # request redirected genuine Paymob callbacks to an attacker host).
    PUBLIC_BASE_URL: str = ""

    # ------------------------------------------------------------------ #
    # Billing & subscriptions platform (Stripe-grade + Payoneer + SKALE)
    # ------------------------------------------------------------------ #
    # Stripe: international cards + Apple Pay + Google Pay. Server-side
    # secret only; the browser sees nothing but a publishable token via
    # hosted Checkout (the publishable key is public by design and carries
    # zero charge power). Empty = rail disabled (falls back to Paymob).
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""   # whsec_... (from `stripe listen` / dashboard)
    STRIPE_API_BASE: str = "https://api.stripe.com"
    # Recurring Price object ids (stripe prices carry currency + amount).
    # Create once:  stripe prices create -p growth -u ...
    # or in the Dashboard; paste the price_xxx ids here.
    STRIPE_PRICE_GROWTH: str = ""
    STRIPE_PRICE_PRO: str = ""

    # Payoneer: checkout + payouts (to Egypt bank / Payoneer balance in any
    # country). Payoneer "for platforms" partner credentials; sandbox default.
    # Field names/paths below match the partner program docs; when the
    # concrete integration link is provided, app/services/billing/providers/
    # payoneer.py is the single adapter to adjust (skills: payoneer analyzer).
    PAYONEER_API_BASE: str = "https://api.sandbox.payoneer.com"
    PAYONEER_PROGRAM_ID: str = ""
    PAYONEER_CLIENT_ID: str = ""
    PAYONEER_CLIENT_SECRET: str = ""
    PAYONEER_WEBHOOK_SECRET: str = ""   # HMAC key over the raw callback body
    PAYONEER_WEBHOOK_ALGO: str = "sha256"  # sha256 | sha512 (program-configured)

    # SKALE Network payouts (USDC / native token) via the ethers.js sidecar
    # mini-services/skale-payout. SKALE Europa is gas-free, EVM-compatible.
    SKALE_PAYOUT_URL: str = "http://localhost:4010"
    SKALE_PAYOUT_HMAC_SECRET: str = ""  # shared secret with the sidecar
    # Defaults for the sidecar itself (documented in its .env.example):
    #   SKALE_RPC_URL=https://mainnet.skalenodes.com/v1/green-giddoni  (Europa)
    #   SKALE_CHAIN_ID=2046398127
    #   SKALE_USDC_CONTRACT=<USDC token address from SKALE bridge docs>
    #   SKALE_PAYOUT_PRIVATE_KEY=<funded wallet key — SERVER SIDE ONLY>

    # Payout policy
    PAYOUT_CURRENCY: str = "USD"
    # Auto-approve payouts at or below this amount (smallest unit) when the
    # account has no open fraud flags; above → admin approval queue.
    PAYOUT_AUTO_APPROVE_MAX: int = 20000  # = $200.00
    PAYOUT_MIN_AMOUNT: int = 1000         # = $10.00
    PLATFORM_FEE_PCT: float = 0.0         # % kept from merchant payouts
    # Max payout requests per user per day (fraud velocity)
    PAYOUT_MAX_PER_DAY: int = 3
    # EGP → USD conversion for payout rails (Payoneer/SKALE settle in USD)
    EGP_TO_USD_RATE: float = 48.5

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
