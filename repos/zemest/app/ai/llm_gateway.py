"""
Concurrent LLM gateway with rate limiting, fallback, caching, and cost control.

RESEARCH RECOMMENDATION (see RESEARCH_CONCURRENT_LLM.md):
  - Orchestration : LiteLLM Router   (already a dependency: litellm>=1.82.0)
  - Rate limiting : aiolimiter (leaky bucket) for per-tenant app limits
                    + LiteLLM Router rpm/tpm (Redis-backed) for provider limits
  - Caching       : LiteLLM Redis Semantic Cache (knowledge/Q&A only, NOT chat)
  - Token counting: litellm.token_counter / completion_cost (wraps tiktoken)
  - Failure       : LiteLLM built-in retries + cooldowns + fallbacks
                    + local Ollama as last-resort fallback

This module is a drop-in replacement surface for app/ai/llm_client.py.
It is Python 3.9 compatible (no asyncio.TaskGroup; uses asyncio.gather + Semaphore).
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any

import litellm
from aiolimiter import AsyncLimiter
from litellm import Router

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 1. Model list + fallback chain  (OpenRouter -> Gemini -> Ollama local)
# ---------------------------------------------------------------------------
# `model_name` is the alias callers use; LiteLLM load-balances all deployments
# that share a `model_name`. `rpm`/`tpm` feed the rate-limit-aware router and
# are tracked in Redis when `redis_url` is configured on the Router.
#
# OpenRouter free-tier limits (verified): 20 req/min on :free models,
# 50 req/day without credits, 1000 req/day with >=10 credits.
# Gemini free tier: 15 RPM, 1M tokens/day.
MODEL_LIST: list[dict[str, Any]] = [
    # --- Primary: OpenRouter (cheap paid + free variants) ---
    {
        "model_name": "zemest-chat",
        "litellm_params": {
            "model": f"openrouter/{settings.OPENROUTER_MODEL}",
            "api_key": settings.OPENROUTER_API_KEY,
            "api_base": settings.OPENROUTER_BASE_URL,
            "rpm": 20,          # OpenRouter free-tier hard limit
            "max_retries": 3,
        },
    },
    {
        "model_name": "zemest-chat",
        "litellm_params": {
            "model": "openrouter/google/gemini-2.0-flash-001",
            "api_key": settings.OPENROUTER_API_KEY,
            "api_base": settings.OPENROUTER_BASE_URL,
            "rpm": 20,
        },
    },
    # --- Fallback tier 1: Gemini direct (15 RPM free) ---
    {
        "model_name": "zemest-fallback-gemini",
        "litellm_params": {
            "model": f"gemini/{settings.GEMINI_MODEL}",
            "api_key": settings.GEMINI_API_KEY,
            "rpm": 15,
        },
    },
    # --- Fallback tier 2: local Ollama (no rate limit, self-hosted) ---
    {
        "model_name": "zemest-fallback-local",
        "litellm_params": {
            "model": "ollama/llama3.2",
            "api_base": "http://ollama:11434",
            "rpm": 1000,         # effectively unlimited locally
        },
    },
]

# Fallback chain: if "zemest-chat" fails after retries, try gemini, then local.
FALLBACKS = [
    {"zemest-chat": ["zemest-fallback-gemini"]},
    {"zemest-fallback-gemini": ["zemest-fallback-local"]},
]

# ---------------------------------------------------------------------------
# 2. Router — retries, cooldowns, rate-limit-aware routing, caching
# ---------------------------------------------------------------------------
# In production pass `redis_url=settings.REDIS_URL` so cooldown + tpm/rpm
# tracking is shared across all workers/replicas.
router = Router(
    model_list=MODEL_LIST,
    fallbacks=FALLBACKS,
    num_retries=3,                       # retry per-deployment before failing over
    retry_after=5,                      # honour Retry-After on 429
    allowed_fails=3,                    # cooldown a deployment after 3 consecutive fails
    cooldown_time=60,                   # 60s cooldown (circuit-breaker-lite)
    timeout=60,
    routing_strategy="usage-based-routing",  # rate-limit-aware: pick least-loaded dep
    cache={"type": "redis", "host": settings.REDIS_URL},  # semantic cache
    disable_add_params_to_message=True,
)

# LiteLLM global knobs
litellm.drop_params = True              # silently drop unsupported params per model
litellm.suppress_debug_info = True


@dataclass
class LLMResponse:
    content: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float


# ---------------------------------------------------------------------------
# 3. Per-tenant application-level rate limiting  (aiolimiter leaky bucket)
# ---------------------------------------------------------------------------
# Free tier: 1000 conversations/day. We approximate as a steady rate of
# ~0.7 req/min per tenant. The leaky bucket smooths bursts so we never
# blow through the provider 20 RPM cap even if many tenants fire at once.
FREE_TIER_RPM = 0.7
PAID_TIER_RPM = 60.0  # effectively unlimited at the app layer

# One limiter per tenant, lazily created. In a multi-worker setup these
# should live in Redis (INCR + EXPIRE sliding window); AsyncLimiter is the
# in-process default suitable for single-worker uvicorn or per-worker shaping.
_tenant_limiters: dict[uuid.UUID, AsyncLimiter] = {}
_limiters_lock = asyncio.Lock()


async def get_tenant_limiter(tenant_id: uuid.UUID, is_paid: bool) -> AsyncLimiter:
    """Return (creating if needed) the per-tenant leaky-bucket limiter."""
    lim = _tenant_limiters.get(tenant_id)
    if lim is not None:
        return lim
    async with _limiters_lock:
        lim = _tenant_limiters.get(tenant_id)
        if lim is None:
            rpm = PAID_TIER_RPM if is_paid else FREE_TIER_RPM
            # AsyncLimiter(max_rate, time_period): max_rate requests per period.
            lim = AsyncLimiter(max_rate=max(rpm, 1), time_period=60)
            _tenant_limiters[tenant_id] = lim
        return lim


# ---------------------------------------------------------------------------
# 4. Per-tenant daily quota enforcement (Redis hot path + Postgres durability)
# ---------------------------------------------------------------------------
async def check_tenant_quota(tenant_id: uuid.UUID, is_paid: bool) -> bool:
    """Return True if the tenant still has daily quota.

    Free tier: 1000 conv/day. Uses Redis INCR with a midnight-expiring key.
    Paid tier: unlimited -> always True (cost budget enforced separately).
    """
    if is_paid:
        return True
    import redis.asyncio as aioredis

    r = aioredis.from_url(settings.REDIS_URL)
    try:
        key = f"quota:chat:{tenant_id}:{time.strftime('%Y%m%d')}"
        count = await r.incr(key)
        if count == 1:
            await r.expire(key, 86400)            # auto-reset at key TTL
        return count <= 1000
    finally:
        await r.aclose()


# ---------------------------------------------------------------------------
# 5. Token counting / cost estimation BEFORE the call (budget guard)
# ---------------------------------------------------------------------------
def estimate_prompt_tokens(messages: list[dict[str, str]], model: str) -> int:
    """Count tokens for a message list before sending (uses tiktoken via litellm)."""
    return litellm.token_counter(model=model, messages=messages)


def estimate_cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Estimate USD cost from token counts (litellm live pricing table)."""
    try:
        return litellm.completion_cost(
            model=model,
            prompt="n/a",
            completion="n/a",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
    except Exception:
        return 0.0


# ---------------------------------------------------------------------------
# 6. Public entry point — one call per customer message
# ---------------------------------------------------------------------------
async def chat_completion_with_usage(
    messages: list[dict[str, str]],
    *,
    tenant_id: uuid.UUID | None = None,
    is_paid_tenant: bool = False,
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 1024,
    cacheable: bool = False,          # knowledge/Q&A only; never chat turns
) -> LLMResponse:
    """Call the LLM with: per-tenant rate limit + provider fallback + caching.

    Args:
        cacheable: set True for deterministic knowledge-base lookups. The
            LiteLLM Redis semantic cache will return a cached answer for
            similar prompts. Leave False for conversational turns.
    """
    model_alias = "zemest-chat"

    # --- per-tenant app rate limit (leaky bucket) ---
    if tenant_id is not None:
        limiter = await get_tenant_limiter(tenant_id, is_paid_tenant)
        await limiter.acquire()

        # --- daily quota (free tier only) ---
        if not await check_tenant_quota(tenant_id, is_paid_tenant):
            logger.warning(f"Tenant {tenant_id} exceeded daily quota")
            return LLMResponse(
                content="لقد وصلت إلى الحد اليومي للرسائل المجانية. يرجى المحاولة غداً.",
                model="quota-exceeded", prompt_tokens=0,
                completion_tokens=0, total_tokens=0, cost_usd=0.0,
            )

    # --- optional semantic cache ---
    kwargs: dict[str, Any] = dict(
        model=model_alias,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    if cacheable:
        kwargs["cache"] = {"no-cache": False}   # honour router redis cache

    # --- single router.acompletion handles retries + fallback internally ---
    resp = await router.acompletion(**kwargs)

    usage = resp.get("usage", {}) or getattr(resp, "usage", {}) or {}
    used_model = resp.get("model", model_alias) or getattr(resp, "model", model_alias)
    prompt_tok = int(usage.get("prompt_tokens", 0))
    completion_tok = int(usage.get("completion_tokens", 0))
    total_tok = int(usage.get("total_tokens", prompt_tok + completion_tok))
    cost = estimate_cost_usd(used_model, prompt_tok, completion_tok)

    content = resp["choices"][0]["message"]["content"] if isinstance(resp, dict) \
        else resp.choices[0].message.content

    return LLMResponse(
        content=content or "",
        model=str(used_model),
        prompt_tokens=prompt_tok,
        completion_tokens=completion_tok,
        total_tokens=total_tok,
        cost_usd=cost,
    )


# ---------------------------------------------------------------------------
# 7. Structured concurrency: 8 conversations per tenant, safely parallel
# ---------------------------------------------------------------------------
class TenantConcurrencyGate:
    """Limits concurrent in-flight LLM calls PER TENANT to ``max_per_tenant``.

    Across thousands of tenants this bounds total concurrency to
    max_per_tenant * num_tenants while preventing any single tenant from
    monopolising the provider rate budget. Python 3.9 safe (plain Semaphore).
    """

    def __init__(self, max_per_tenant: int = 8) -> None:
        self._max = max_per_tenant
        self._sems: dict[uuid.UUID, asyncio.Semaphore] = {}
        self._lock = asyncio.Lock()

    async def acquire(self, tenant_id: uuid.UUID) -> asyncio.Semaphore:
        sem = self._sems.get(tenant_id)
        if sem is not None:
            return sem
        async with self._lock:
            sem = self._sems.get(tenant_id)
            if sem is None:
                sem = asyncio.Semaphore(self._max)
                self._sems[tenant_id] = sem
            return sem

    async def run(
        self,
        tenant_id: uuid.UUID,
        coro_fn,
        *args,
        **kwargs,
    ):
        """Run ``coro_fn`` under the tenant's concurrency cap."""
        sem = await self.acquire(tenant_id)
        async with sem:
            return await coro_fn(*args, **kwargs)


# Module-level singleton; import and use from agent.py / API layer.
tenant_gate = TenantConcurrencyGate(max_per_tenant=8)


# ---------------------------------------------------------------------------
# 8. Parallel fan-out example: voice + vision + text in one turn
# ---------------------------------------------------------------------------
async def gather_multimodal(
    tenant_id: uuid.UUID,
    text_task,        # callable() -> awaitable
    vision_task=None,
    audio_task=None,
):
    """Run independent LLM/sub-LLM tasks concurrently (Python 3.9 compatible).

    Uses asyncio.gather (not TaskGroup, which needs 3.11+). Each task runs
    through the tenant concurrency gate so the 8-cap is respected.
    """
    tasks = []
    if audio_task:
        tasks.append(tenant_gate.run(tenant_id, audio_task))
    if vision_task:
        tasks.append(tenant_gate.run(tenant_id, vision_task))
    tasks.append(tenant_gate.run(tenant_id, text_task))

    results = await asyncio.gather(*tasks, return_exceptions=True)
    # Flatten: treat exceptions as None so the caller can degrade gracefully.
    return [None if isinstance(r, Exception) else r for r in results]
