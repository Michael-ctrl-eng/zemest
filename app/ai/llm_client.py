from __future__ import annotations

import asyncio
import logging
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
    primary = model or settings.OPENROUTER_MODEL
    models_to_try = [primary] + [m for m in FALLBACK_MODELS if m != primary]

    last_error = None
    for current_model in models_to_try:
        try:
            return await _call_openrouter(
                messages, current_model, temperature, max_tokens
            )
        except Exception as e:
            last_error = e
            logger.warning(f"Model {current_model} failed: {e}, trying next...")
            await asyncio.sleep(1)

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
    """Make a single API call to OpenRouter."""
    if not settings.OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY not configured")

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

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
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
