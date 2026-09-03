from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

# Models that don't support system role — convert to user message
NO_SYSTEM_ROLE = {"google/gemma", "gemma-3"}

# Fallback models — cheap paid first, then free
FALLBACK_MODELS = [
    "google/gemini-2.0-flash-001",
    "qwen/qwen-2.5-72b-instruct",
    "arcee-ai/trinity-large-preview:free",
]

# --- SPEED FIXES ----------------------------------------------------------- #
# 1. Shared, pooled HTTP client: no per-call TCP/TLS handshake. Reused for
#    every OpenRouter call (big latency win, especially from Egypt → OR edge).
_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=5.0, read=25.0, write=10.0, pool=5.0),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )
    return _client


async def close_client() -> None:
    """Called on app shutdown to release pooled connections."""
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
    _client = None


# 2. Circuit breaker for "no API key configured": fail in <1ms instead of
#    burning 4 models × sleeps (~3-8s) on EVERY customer message.
_NO_KEY_UNTIL = 0.0
_NO_KEY_COOLDOWN = 60.0  # seconds


# 3. Z.ai internal provider (OpenAI-compatible). Works in the z.ai sandbox
#    with ZERO external keys — reads /etc/.z-ai-config once at startup.
#    Env overrides: ZAI_BASE_URL / ZAI_TOKEN / ZAI_API_KEY / ZAI_MODEL.
_ZAI_CONFIG: dict | None = None
_ZAI_LOADED = False


# --- CONCURRENT-USER HARDENING (scale to 10k users/day) -------------------- #
# 4. Per-provider key pool: OPENROUTER_API_KEYS accepts a comma-separated
#    list. Round-robin under normal load; a key that trips a 429 is cooled
#    down for 60s and the pool instantly rotates to the next one — one key's
#    rate limit never stalls the whole reply pipeline.
class _KeyPool:
    """Round-robin API-key pool with per-key 429 cooldown."""

    def __init__(self, raw: str):
        self.keys: list[str] = [k.strip() for k in (raw or "").split(",") if k.strip()]
        self._idx = 0
        self._cooldown: dict[str, float] = {}

    def __bool__(self) -> bool:
        return bool(self.keys)

    def pick(self) -> str | None:
        if not self.keys:
            return None
        now = time.monotonic()
        live = [k for k in self.keys if self._cooldown.get(k, 0.0) <= now]
        pool = live or self.keys  # all cooling -> least-bad: use anyway
        self._idx = (self._idx + 1) % len(pool)
        return pool[self._idx]

    def penalize(self, key: str, seconds: float = 60.0) -> None:
        if key:
            self._cooldown[key] = time.monotonic() + seconds


_OR_KEY_POOL: _KeyPool | None = None


def _get_or_pool() -> _KeyPool:
    """OPENROUTER_API_KEYS pool, falling back to the single key env var."""
    global _OR_KEY_POOL
    if _OR_KEY_POOL is None:
        pool = _KeyPool(getattr(settings, "OPENROUTER_API_KEYS", "") or "")
        if not pool and settings.OPENROUTER_API_KEY:
            pool = _KeyPool(settings.OPENROUTER_API_KEY)
        _OR_KEY_POOL = pool
    return _OR_KEY_POOL


# 5. Global LLM concurrency gate: at most LLM_MAX_CONCURRENCY calls in
#    flight; excess requests QUEUE instead of hammering providers into
#    429 storms during concurrent-user spikes.
_LLM_SEMAPHORE: asyncio.Semaphore | None = None


def _get_llm_semaphore() -> asyncio.Semaphore:
    global _LLM_SEMAPHORE
    if _LLM_SEMAPHORE is None:
        try:
            limit = max(1, int(getattr(settings, "LLM_MAX_CONCURRENCY", 8)))
        except (TypeError, ValueError):
            limit = 8
        _LLM_SEMAPHORE = asyncio.Semaphore(limit)
    return _LLM_SEMAPHORE


def _load_zai_config() -> dict | None:
    """Load Z.ai credentials from /etc/.z-ai-config (cached, best-effort).

    Returns None when unavailable → provider is skipped in the ladder.
    """
    global _ZAI_CONFIG, _ZAI_LOADED
    if _ZAI_LOADED:
        return _ZAI_CONFIG
    _ZAI_LOADED = True
    base = settings.ZAI_BASE_URL if hasattr(settings, "ZAI_BASE_URL") else ""
    token = ""
    api_key = ""
    chat_id = ""
    user_id = ""
    if base and (settings.ZAI_TOKEN if hasattr(settings, "ZAI_TOKEN") else ""):
        token = settings.ZAI_TOKEN
    else:
        try:
            raw = json.loads(Path("/etc/.z-ai-config").read_text("utf-8"))
            base = raw.get("baseUrl", "")
            api_key = raw.get("apiKey", "")
            token = raw.get("token", "")
            chat_id = raw.get("chatId", "")
            user_id = raw.get("userId", "")
        except Exception:
            return None
    if not (base and token):
        return None
    _ZAI_CONFIG = {
        "base_url": base.rstrip("/"),
        "api_key": api_key,
        "token": token,
        "chat_id": chat_id,
        "user_id": user_id,
        "model": getattr(settings, "ZAI_MODEL", "") or "glm-4.6",
    }
    return _ZAI_CONFIG


def zai_available() -> bool:
    """True when the internal Z.ai provider is usable."""
    return _load_zai_config() is not None


@dataclass
class LLMResponse:
    content: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


async def chat_completion(
    messages: list[dict[str, str]],
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 1024,
) -> str:
    """Call OpenRouter chat completion API with fallback models. Returns content string."""
    result = await chat_completion_with_usage(messages, model, temperature, max_tokens)
    return result.content


async def chat_completion_with_usage(
    messages: list[dict[str, str]],
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 1024,
) -> LLMResponse:
    """Call the best available LLM provider and return content + token usage.

    Provider ladder (first available wins, failures fall through):
    1. Z.ai internal API (sandbox/production z.ai infra — no external key)
    2. OpenRouter (OPENROUTER_API_KEY) with fallback models

    Only 1 API call per message in the normal case.
    Fallbacks only trigger on failure (rate limit, error).
    """
    global _NO_KEY_UNTIL

    # Provider 1: Z.ai internal (OpenAI-compatible). Skipped when the caller
    # explicitly requested a different model (OpenRouter model id).
    zai_cfg = _load_zai_config()
    if zai_cfg is not None and (model is None or model == settings.OPENROUTER_MODEL):
        try:
            async with _get_llm_semaphore():
                return await _call_zai(messages, temperature, max_tokens, zai_cfg)
        except Exception as e:
            logger.warning(f"Z.ai provider failed: {e}, falling through to OpenRouter...")

    # Provider 2: OpenRouter (multi-key pool + concurrency gate).
    # Fail fast: no key configured (or breaker open) → single instant error.
    pool = _get_or_pool()
    if not pool:
        if time.monotonic() < _NO_KEY_UNTIL:
            raise RuntimeError("No LLM provider available (Z.ai down, OPENROUTER_API_KEY unset)")
        _NO_KEY_UNTIL = time.monotonic() + _NO_KEY_COOLDOWN
        raise RuntimeError("No LLM provider available (Z.ai down, OPENROUTER_API_KEY unset)")
    _NO_KEY_UNTIL = 0.0

    primary = model or settings.OPENROUTER_MODEL
    models_to_try = [primary] + [m for m in FALLBACK_MODELS if m != primary]

    last_error = None
    for i, current_model in enumerate(models_to_try):
        api_key = pool.pick()
        try:
            async with _get_llm_semaphore():
                return await _call_openrouter(
                    messages, current_model, temperature, max_tokens, api_key
                )
        except Exception as e:
            last_error = e
            if "Rate limited" in str(e):
                pool.penalize(api_key)  # rotate off this key for 60s
            logger.warning(f"Model {current_model} failed: {e}, trying next...")
            # 3. Snappy backoff (was 1s flat → 4s+ wasted per message on failure)
            if i < len(models_to_try) - 1:
                await asyncio.sleep(min(0.2 * (i + 1), 0.6))

    raise RuntimeError(f"All models failed. Last error: {last_error}")


def _prepare_messages(messages: list[dict[str, str]], model: str) -> list[dict[str, str]]:
    """Convert system messages to user messages for models that don't support system role."""
    needs_conversion = any(fragment in model for fragment in NO_SYSTEM_ROLE)
    if not needs_conversion:
        return messages

    converted = []
    for msg in messages:
        if msg["role"] == "system":
            converted.append({
                "role": "user",
                "content": f"[INSTRUCTIONS]\n{msg['content']}\n[/INSTRUCTIONS]\n\nFollow these instructions for all subsequent messages."
            })
            converted.append({
                "role": "assistant",
                "content": "Understood. I will follow these instructions."
            })
        else:
            converted.append(msg)
    return converted


async def _call_openrouter(
    messages: list[dict[str, str]],
    model: str,
    temperature: float,
    max_tokens: int,
    api_key: str | None = None,
) -> LLMResponse:
    """Make a single API call to OpenRouter using the pooled client.

    ``api_key`` comes from the rotation pool (see _KeyPool)."""
    if not api_key:
        raise RuntimeError("No OpenRouter key available")
    prepared_messages = _prepare_messages(messages, model)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://zemest.local",
        "X-Title": "Zemest",
    }
    payload = {
        "model": model,
        "messages": prepared_messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    response = await _get_client().post(
        f"{settings.OPENROUTER_BASE_URL}/chat/completions",
        headers=headers,
        json=payload,
    )

    if response.status_code == 429:
        raise RuntimeError(f"Rate limited on {model}")

    if response.status_code != 200:
        raise RuntimeError(
            f"OpenRouter error {response.status_code}: {response.text[:300]}"
        )

    data = response.json()
    choices = data.get("choices", [])
    if not choices:
        raise RuntimeError("No choices in response")

    content = choices[0]["message"]["content"]
    if content is None:
        raise RuntimeError(f"Model {model} returned null content")

    # Extract token usage
    usage = data.get("usage", {})
    used_model = data.get("model", model)

    return LLMResponse(
        content=content,
        model=used_model,
        prompt_tokens=usage.get("prompt_tokens", 0),
        completion_tokens=usage.get("completion_tokens", 0),
        total_tokens=usage.get("total_tokens", 0),
    )


# --- Provider 1: Z.ai internal API (OpenAI-compatible) ---------------------- #

async def _call_zai(
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
    cfg: dict,
) -> LLMResponse:
    """Call the internal Z.ai chat-completions API.

    Uses the sandbox's own GLM inference (no external key required) via the
    shared pooled client. Non-200 responses raise so the provider ladder can
    fall through to OpenRouter.
    """
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {cfg['api_key']}",
        "X-Z-AI-From": "Z",
        "X-Token": cfg["token"],
    }
    if cfg.get("chat_id"):
        headers["X-Chat-Id"] = cfg["chat_id"]
    if cfg.get("user_id"):
        headers["X-User-Id"] = cfg["user_id"]

    payload = {
        "model": cfg["model"],
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        # Keep latency low: no chain-of-thought for agent replies.
        "thinking": {"type": "disabled"},
    }

    response = await _get_client().post(
        f"{cfg['base_url']}/chat/completions",
        headers=headers,
        json=payload,
    )

    if response.status_code != 200:
        raise RuntimeError(f"Z.ai error {response.status_code}: {response.text[:300]}")

    data = response.json()
    choices = data.get("choices", [])
    if not choices:
        raise RuntimeError("No choices in Z.ai response")

    content = choices[0]["message"]["content"]
    if content is None:
        raise RuntimeError("Z.ai returned null content")

    usage = data.get("usage", {})
    return LLMResponse(
        content=content,
        model=data.get("model", cfg["model"]),
        prompt_tokens=usage.get("prompt_tokens", 0),
        completion_tokens=usage.get("completion_tokens", 0),
        total_tokens=usage.get("total_tokens", 0),
    )
