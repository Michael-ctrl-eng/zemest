from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Zemest"
    APP_ENV: str = "development"
    APP_DEBUG: bool = False
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://zemest:zemest_secret@localhost:5432/zemest"
    DATABASE_URL_SYNC: str = "postgresql://zemest:zemest_secret@localhost:5432/zemest"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT
    JWT_SECRET_KEY: str = "change-me-to-a-random-secret-key"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

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

    # In-process scheduler worker (true = publish due posts inside uvicorn;
    # set false when Celery+Redis beat is deployed to avoid double publishing)
    SCHEDULER_INLINE_WORKER: bool = True

    # In-process silent trainer (true = background self-training loop that
    # classifies junk vs commerce chats and builds the page's style profile
    # with zero user interaction; set false when training moves to Celery)
    SILENT_TRAINER_INLINE_WORKER: bool = True

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
