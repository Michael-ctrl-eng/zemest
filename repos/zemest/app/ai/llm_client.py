from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass

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
    """Call OpenRouter and return content + token usage.

    Only 1 API call per message in the normal case.
    Fallbacks only trigger on failure (rate limit, error).
    """
    global _NO_KEY_UNTIL

    # Fail fast: no key configured (or breaker open) → single instant error.
    if not settings.OPENROUTER_API_KEY:
        if time.monotonic() < _NO_KEY_UNTIL:
            raise RuntimeError("OPENROUTER_API_KEY not configured")
        _NO_KEY_UNTIL = time.monotonic() + _NO_KEY_COOLDOWN
        raise RuntimeError("OPENROUTER_API_KEY not configured")
    _NO_KEY_UNTIL = 0.0

    primary = model or settings.OPENROUTER_MODEL
    models_to_try = [primary] + [m for m in FALLBACK_MODELS if m != primary]

    last_error = None
    for i, current_model in enumerate(models_to_try):
        try:
            return await _call_openrouter(
                messages, current_model, temperature, max_tokens
            )
        except Exception as e:
            last_error = e
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
) -> LLMResponse:
    """Make a single API call to OpenRouter using the pooled client."""
    prepared_messages = _prepare_messages(messages, model)

    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
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
