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
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_MODEL: str = "meta-llama/llama-4-maverick:free"

    # Gemini (free: 15 RPM, 1M tokens/day)
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.0-flash"

    # LLM provider selection: auto | openrouter | gemini | ollama
    LLM_PROVIDER: str = "auto"

    # Facebook
    FB_APP_ID: str = ""
    FB_APP_SECRET: str = ""
    FB_VERIFY_TOKEN: str = "zemest-verify-token"
    FB_GRAPH_API_URL: str = "https://graph.facebook.com/v21.0"

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

    # Periodic publish job (APScheduler; publishes due posts inside uvicorn).
    # Set false when an external `huey_consumer`/beat-style deployment owns it.
    SCHEDULER_INLINE_WORKER: bool = True

    # In-process silent trainer (APScheduler interval job that classifies
    # junk vs commerce chats and builds the page's style profile with zero
    # user interaction; set false when training moves to an external worker)
    SILENT_TRAINER_INLINE_WORKER: bool = True

    # Paymob online payments (Intention API — see analysis/G1-payments.md).
    # COD stays the default rail; Paymob powers the deposit-to-confirm
    # (عربون) flow and full online payments. All values are env-overridable
    # and empty by default (no real keys in code).
    PAYMOB_API_KEY: str = ""  # server-side secret key (Token auth)
    PAYMOB_INTEGRATION_IDS: str = ""  # comma-separated payment-method ids, e.g. "12345,6789"
    PAYMOB_WEBHOOK_HMAC_SECRET: str = ""  # HMAC-SHA512 webhook signing secret
    PAYMOB_BASE_URL: str = "https://egypt.paymob.com"  # Egypt region Intention API base
    PAYMOB_CURRENCY: str = "EGP"

    # ------------------------------------------------------------------
    # Billing — post-legacy payment rails (billing/ subscription stack).
    #   payoneer (PRIMARY) | paymob (BACKUP) | usdc_solana (crypto rail).
    # No settings exist for the removed legacy card rail. All secrets are env-injected; defaults are inert.
    # ------------------------------------------------------------------
    # Rails availability switch (the /api/billing/rails endpoint reports
    # only rails whose credentials are configured).
    BILLING_ENABLED: bool = True

    # Fixed public webhook base — the ONLY source for webhook/callback URLs
    # handed to providers. When set it overrides request.base_url, killing
    # Host-header notification_url hijacks (audit D5 finding :301).
    BILLING_WEBHOOK_PUBLIC_URL: str = ""

    # EGP-per-USD rate used by the fiat rails when converting a plan's USD
    # list price to EGP (Payoneer charges USD; Paymob charges EGP). The
    # USDC rail always uses the plan's price_usdc directly.
    BILLING_USD_TO_EGP_RATE: float = 48.0

    # Dunning schedule: max retry attempts before past_due → canceled, and
    # the retry backoff base (retry N happens after base * 2^(N-1) days).
    BILLING_DUNNING_MAX_ATTEMPTS: int = 4
    BILLING_DUNNING_RETRY_BASE_DAYS: float = 1.0

    # --- Payoneer (PRIMARY rail — Payoneer Checkout) -------------------
    # API token from the Payoneer partner portal (server-to-server).
    PAYONEER_API_TOKEN: str = ""
    # Checkout API base. Default: production; sandbox available for tests.
    PAYONEER_API_BASE_URL: str = "https://api.payoneer.com"
    # Partner/program identifiers echoed in checkout requests.
    PAYONEER_PARTNER_ID: str = ""
    PAYONEER_PROGRAM_ID: str = ""
    # HMAC-SHA256 webhook signing secret (fail-closed when unset).
    PAYONEER_WEBHOOK_SECRET: str = ""
    # Webhook HMAC algorithm: sha256 (default) or sha512, and the header
    # Payoneer delivers the signature in (override if the portal differs).
    PAYONEER_WEBHOOK_ALGO: str = "sha256"
    PAYONEER_SIG_HEADER: str = "X-Payoneer-Signature"
    PAYONEER_CURRENCY: str = "USD"
    # Payout (withdrawal) API scope — read/poll payout status by payout id.
    PAYONEER_PAYOUT_API_BASE_URL: str = "https://api.payoneer.com/v4"

    # --- USDC over Solana (crypto rail — direct JSON-RPC, NO sidecar) --
    # Public RPC endpoint (mainnet-beta default; point to a paid RPC with
    # auth token for production volume).
    SOLANA_RPC_URL: str = "https://api.mainnet-beta.solana.com"
    SOLANA_RPC_API_TOKEN: str = ""  # appended as ?api-token= for paid RPCs
    # USDC (SPL) mint — mainnet default; override for devnet testing:
    #   devnet: 4zMMC9srt5Ri5X14GAgXhaHii3GnPAEAEDd9UXpYvNRL
    USDC_MINT_ADDRESS: str = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
    # Platform treasury wallet (base58) — receives subscription payments,
    # funds merchant payouts. Deposit monitoring scans this address.
    USDC_TREASURY_WALLET: str = ""
    # Number of confirmations before an on-chain credit is final.
    USDC_CONFIRMATIONS_REQUIRED: int = 32
    # Polling: how many recent signatures the USDC check pulls per sweep.
    USDC_SCAN_LIMIT: int = 40
    # Micro-USDC tolerance when matching an on-chain amount to an invoice
    # (payers sometimes send with 6-decimal rounding).
    USDC_AMOUNT_TOLERANCE: int = 100  # 0.0001 USDC

    # --- Treasury withdrawals (admin, 2-approval workflow) -------------
    # Minimum USDC treasury balance that must REMAIN after a withdrawal.
    TREASURY_MIN_RESERVE_USDC: float = 10.0
    # Operator-facing bank destination summary shown in the admin UI (no
    # account numbers here — those live in the operator's bank portal).
    TREASURY_BANK_LABEL: str = "Operator bank account (configured offline)"

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
