# Research: Concurrent LLM Patterns for Multi-Tenant SaaS

**Target:** 10,000+ concurrent LLM calls across thousands of tenants, 8 concurrent
conversations per tenant, OpenRouter + Gemini + local Ollama fallback.
**Codebase context:** FastAPI + asyncpg + Redis + Celery, Python 3.9, `litellm>=1.82.0`
already in `requirements.txt` (but not yet used for calls — `llm_client.py` uses raw httpx).

A reference implementation lives in `app/ai/llm_gateway.py`.

---

## TL;DR — The 6 Recommendations

| # | Decision | Pick | Why |
|---|----------|------|-----|
| 1 | LLM orchestration | **LiteLLM Router** | Already a dependency. Unified API for OpenRouter/Gemini/Ollama; built-in retries, fallbacks, cooldowns, RPM/TPM tracking (Redis), rate-limit-aware routing, async semaphore, caching, cost tracking. 57k★, MIT. |
| 2 | Rate limiting | **aiolimiter** (leaky bucket) + LiteLLM Router `rpm`/`tpm` | Leaky bucket smooths bursty chat traffic into a steady stream → fewer 429s. aiolimiter = per-tenant app limit; Router rpm/tpm (Redis-backed) = per-provider limit. |
| 3 | Caching | **LiteLLM Redis Semantic Cache** | Same Redis you already run. Semantic (embedding) match for knowledge/Q&A lookups. Never cache live chat turns. |
| 4 | Token counting | **`litellm.token_counter` + `completion_cost`** (wraps tiktoken) | One call counts tokens *and* estimates USD cost before & after. tiktoken is the underlying engine (19k★, MIT). |
| 5 | Failure handling | **LiteLLM built-in** (retries + cooldowns + fallbacks) + **Ollama last-resort** | Router retries 3× with exp backoff per deployment, cools it down (circuit-breaker-lite), then falls over to next provider, finally local Ollama. `tenacity` only for non-LLM calls (vision/transcription). |
| 6 | Concurrency pattern | **`asyncio.Semaphore` per tenant + `asyncio.gather`** | Python 3.9 has no `TaskGroup`. Per-tenant `Semaphore(8)` caps concurrent calls; `gather` fans out multimodal tasks. |

---

## 1. Best LLM Orchestration Library → **LiteLLM**

**Repository:** https://github.com/BerriAI/litellm · **57k★** · **MIT** (core) · YC W23

### Why it wins (vs langchain / llamaindex / raw httpx)

The current `app/ai/llm_client.py` hand-rolls httpx calls with a `for model in models: try…except: sleep(1)` loop. It creates a **new `httpx.AsyncClient` per call** (no connection pooling), has **no retry backoff**, **no concurrency cap**, **no caching**, and **no provider-level rate tracking**. LiteLLM's `Router` solves all of this in one construct:

| Feature | LiteLLM Router | langchain | llamaindex | raw httpx (current) |
|---|---|---|---|---|
| Unified OpenAI-format API for 100+ LLMs | ✅ | ✅ (wrappers) | ✅ | ❌ |
| Load-balance across deployments | ✅ `routing_strategy` | ❌ | ❌ | ❌ |
| Fallback chain (429 → next provider) | ✅ `fallbacks=[…]` | partial | ❌ | manual loop |
| Retries w/ exp backoff + jitter | ✅ `num_retries` | ❌ | ❌ | `sleep(1)` |
| Cooldown / circuit-breaker-lite | ✅ `allowed_fails`+`cooldown_time` | ❌ | ❌ | ❌ |
| Per-deployment RPM/TPM (Redis-shared) | ✅ `rpm`/`tpm` | ❌ | ❌ | ❌ |
| Max parallel async calls (semaphore) | ✅ `max_parallel_requests` | ❌ | ❌ | ❌ |
| Token usage + `response_cost` on every call | ✅ | partial | partial | manual |
| `token_counter` / `cost_per_token` / `completion_cost` | ✅ | ❌ | ❌ | ❌ |
| Built-in caching (incl. **Redis semantic**) | ✅ | via GPTCache | via GPTCache | ❌ |
| Streaming | ✅ `acompletion(stream=True)` | ✅ | ✅ | manual |
| OpenRouter / Gemini / Ollama support | ✅ all three | ✅ | ✅ | OpenRouter only |

### Verified production signals
- **OSS adopters listed in README:** Stripe, Netflix, Google ADK, OpenHands, OpenAI Agents SDK, Greptile.
- **Benchmarks:** 8 ms P95 latency at 1k RPS (docs.litellm.ai/docs/benchmarks).
- **Multi-tenant:** dedicated "Multi-Tenant Architecture" + per-user/team/key budgets & RPM/TPM/$ limits (Postgres-backed) docs.
- One known caveat: GitHub issue #18730 reported concurrent requests could bypass TPM isolation between orgs (Jan 2026) — **this is why we add our own per-tenant `aiolimiter` + Redis quota counter on top**, not relying solely on Router RPM/TPM.

### Integration (drop-in for `llm_client.py`)
```python
from litellm import Router
router = Router(
    model_list=[{ "model_name":"zemest-chat",
                  "litellm_params":{"model":"openrouter/meta-llama/llama-4-maverick:free",
                                    "api_key":..., "rpm":20}}, ...],
    fallbacks=[{"zemest-chat":["zemest-fallback-gemini"]}],
    num_retries=3, retry_after=5, allowed_fails=3, cooldown_time=60,
    routing_strategy="usage-based-routing",
    cache={"type":"redis","host":settings.REDIS_URL},
    redis_url=settings.REDIS_URL,        # share cooldown/rpm across workers
)
resp = await router.acompletion(model="zemest-chat", messages=messages, ...)
```
See `app/ai/llm_gateway.py` for the full, commented implementation.

---

## 2. Best Rate Limiting → **aiolimiter** (leaky bucket) + LiteLLM Router RPM/TPM

**Repository:** https://github.com/mjpieters/aiolimiter · **777★** · **MIT** · asyncio-native

### Algorithm choice: Leaky Bucket
LLM providers (OpenRouter: 20 RPM free; Gemini: 15 RPM free) enforce **both** RPM and TPM.
Chat traffic is bursty — a customer sends 3 quick messages, then nothing for minutes.

| Algorithm | Behaviour | Fit for LLM |
|---|---|---|
| **Token bucket** | Allows bursts up to bucket size | OK, but bursts can trip provider RPM caps |
| **Leaky bucket** (chosen) | Smooths bursts into steady drip | ✅ Best — keeps you under the steady RPM ceiling |
| Sliding window | Precise per-window counts | Good for *counting* quotas, not *pacing* |
| Fixed window | Simple, jagged at boundaries | ❌ Thundering herd at window reset |

**Two layers, two purposes:**
1. **Per-tenant app limit** — `aiolimiter.AsyncLimiter(rpm, 60)`: free tier 0.7 RPM (≈1000/day), paid 60 RPM. Prevents one tenant from saturating the shared provider budget.
2. **Per-provider limit** — LiteLLM Router `rpm`/`tpm` (Redis-shared across workers): enforces OpenRouter's 20 RPM / Gemini's 15 RPM at the deployment level with rate-limit-aware routing.

```python
from aiolimiter import AsyncLimiter
limiter = AsyncLimiter(max_rate=0.7, time_period=60)   # free tier
await limiter.acquire()
resp = await router.acompletion(...)
```

> **Note on aiometer:** `aiometer` (a sibling concurrency-scheduling lib) is less mature and its GitHub repo could not be located for star count. `aiolimiter` is the established choice (recommended by Simon Willison, used widely).

---

## 3. Best Caching → **LiteLLM Redis Semantic Cache**

### Why not GPTCache?
GPTCache (https://github.com/zilliztech/GPTCache · 8.2k★ · MIT) is the well-known semantic cache, but its README now states: *"we no longer add support for new API or models"* — it is in **maintenance mode**. It would add a second vector store (Milvus/FAISS) alongside your existing Redis. Since LiteLLM already ships a **Redis Semantic Cache** that uses your existing Redis, there is no reason to add GPTCache.

### LiteLLM cache backends (verified from docs.litellm.ai/docs/proxy/caching)
In-Memory · Disk · **Redis** · **Qdrant Semantic** · **Redis Semantic** · Valkey Semantic · S3 · GCS.

### When to cache (critical rule)
| Use case | Cache? | Why |
|---|---|---|
| Knowledge-base / product-info Q&A | ✅ semantic | Same question phrased differently → same answer |
| FAQ / static info ("ما هي ساعات العمل؟") | ✅ exact | Deterministic |
| Conversational chat turns | ❌ NEVER | Each turn depends on history; caching returns stale/wrong replies |
| Order extraction from free text | ❌ | Must be live; correctness > cost |

```python
router = Router(..., cache={"type":"redis","host":REDIS_URL})
# cacheable lookups:
resp = await router.acompletion(..., cache={"no-cache": False})
# conversational turns:
resp = await router.acompletion(...)   # cache bypassed by default for chat
```

---

## 4. Best Token Counting → **`litellm.token_counter` + `completion_cost`** (tiktoken inside)

**tiktoken:** https://github.com/openai/tiktoken · **19k★** · MIT — the OpenAI BPE tokenizer.

LiteLLM wraps tiktoken and adds **cost calculation**, so you get one API for both:

| Function | Purpose | When |
|---|---|---|
| `litellm.token_counter(model, messages)` | Count prompt tokens **before** sending | Budget guard, context-window check |
| `litellm.completion_cost(model, prompt_tokens, completion_tokens)` | USD cost estimate | Pre-flight cost gate |
| `response._hidden_params["response_cost"]` | Actual cost of a completed call | Billing (post-call) |
| `response["usage"]` | Actual prompt/completion/total tokens | Billing (you already persist this to `TokenUsage`) |

```python
import litellm
pre = litellm.token_counter(model="openrouter/...", messages=messages)
if pre > 8000:
    raise BudgetExceeded("prompt too long, compress or truncate")
# ... after the call:
cost = litellm.completion_cost(model, pre, completion_tokens)
```

Your existing `app/models/token_usage.py` (Postgres `TokenUsage` table) is the **durability layer**. The recommended hybrid:
- **Redis hot path:** `INCR quota:chat:{tenant}:{date}` for sub-ms quota checks (auto-expiring key).
- **Postgres durability:** `TokenUsage` rows for billing/audit (already implemented in `agent.py` step 13).

---

## 5. Best Failure Handling → **LiteLLM retries + cooldowns + fallback chain → Ollama**

**tenacity:** https://github.com/jd/tenacity · **8.8k★** · Apache 2.0 — the standard Python retry lib. **But you don't need it for LLM calls**: LiteLLM Router already does `num_retries` with exponential backoff + jitter + `Retry-After` honouring, *plus* cooldowns (circuit-breaker-lite) and provider failover that tenacity alone cannot do. Use tenacity only for non-LLM calls (Gemini Vision, faster-whisper transcription).

### The layered failure strategy

```
router.acompletion("zemest-chat")        # OpenRouter (primary)
   │  429 / 5xx / timeout
   ├─ retry 3× (exp backoff, jitter)     # LiteLLM built-in
   │  still failing?
   ├─ cooldown 60s on this deployment    # circuit-breaker-lite
   ├─ fallback → "zemest-fallback-gemini" # Gemini direct (15 RPM)
   │  still failing?
   └─ fallback → "zemest-fallback-local"  # local Ollama (always up)
```

### Dead-letter / graceful degradation (already in your codebase)
`agent.py` already catches the final exception and returns `_get_fallback_response(lang)` — a static localized "try again later" message. To add a dead-letter queue, push the failed `{tenant, messages, error}` onto a Celery queue for later replay; Celery + Redis are already wired up (`app/tasks/`).

### Circuit-breaker caveat (verified from discuss.python.org)
tenacity (retries) and pybreaker (circuit breaker) **do not share state** — a known gap. LiteLLM's `allowed_fails` + `cooldown_time` sidesteps this by combining both inside the Router, so retries stop automatically when a deployment is cooled down.

---

## 6. Concrete Code Pattern — "8 concurrent conversations per tenant"

**Constraint:** Python 3.9 → **no `asyncio.TaskGroup`** (requires 3.11+). Use `asyncio.Semaphore` + `asyncio.gather`.

Full implementation in **`app/ai/llm_gateway.py`**. Key pieces:

### Per-tenant concurrency cap
```python
class TenantConcurrencyGate:
    def __init__(self, max_per_tenant=8): ...
    async def run(self, tenant_id, coro_fn, *a, **kw):
        sem = await self.acquire(tenant_id)   # Semaphore(8) per tenant
        async with sem:
            return await coro_fn(*a, **kw)

tenant_gate = TenantConcurrencyGate(max_per_tenant=8)
```

### The call (rate limit + quota + fallback + cache + cost)
```python
async def chat_completion_with_usage(messages, *, tenant_id, is_paid_tenant,
                                     cacheable=False, ...):
    # 1. per-tenant leaky-bucket (aiolimiter)
    await (await get_tenant_limiter(tenant_id, is_paid_tenant)).acquire()
    # 2. daily quota (Redis INCR, free tier 1000/day)
    if not await check_tenant_quota(tenant_id, is_paid_tenant):
        return quota_exceeded_response()
    # 3. router.acompletion → retries + cooldown + fallback + cache internally
    resp = await router.acompletion(model="zemest-chat", messages=messages, ...)
    # 4. token + cost tracking
    return LLMResponse(content, model, prompt_tok, completion_tok, total_tok, cost_usd)
```

### Multimodal fan-out (voice + vision + text in one turn)
`agent.py` already does `_transcribe_audio` then `_analyze_images` sequentially. With the gate + gather they run **concurrently** while respecting the 8-cap:
```python
results = await gather_multimodal(
    tenant_id,
    text_task=lambda: chat_completion_with_usage(...),
    vision_task=lambda: analyze_product_image(...),
    audio_task=lambda: transcribe_url(...),
)
```

### Wiring into the existing agent
`agent.py` step 9 currently calls `chat_completion_with_usage(llm_messages)`.
Minimal change: pass tenant context and route through the gate:
```python
llm_result = await tenant_gate.run(
    tenant.id,
    chat_completion_with_usage, llm_messages,
    tenant_id=tenant.id, is_paid_tenant=tenant.is_paid,
)
```
The `LLMResponse` dataclass is backward-compatible (adds `cost_usd`).

---

## Cost-Optimization Add-ons

| Technique | Tool | Recommendation |
|---|---|---|
| **Prompt compression** | LLMLingua (Microsoft, 6.6k★, up to 20× compression) | Use for long RAG context / knowledge indexing (non-real-time). Adds latency (runs a small GPT2/LLaMA) — **not** for real-time chat turns. |
| **Prompt caching** | OpenRouter supports prompt caching (verified in pricing docs) | LiteLLM passes `cache_control` through automatically for supported providers. Free cost win on repeated system prompts. |
| **Model routing** | LiteLLM `routing_strategy="cost-based-routing"` | Route simple queries to `:free` models, complex ones to paid. The Router can pick the cheapest healthy deployment. |
| **Batch processing** | LiteLLM `/batches` endpoint | Use for crawl/indexing jobs (your `app/tasks/crawl_tasks.py`) — 50% cheaper, non-real-time. |

---

## Migration Checklist (next actions)

1. **Replace `llm_client.py` internals with `llm_gateway.py`** — keep the same `chat_completion_with_usage` signature so `agent.py` needs only the `tenant_id`/`is_paid_tenant` kwargs added.
2. **Add `aiolimiter` to `requirements.txt`** (`aiolimiter>=1.2.0`).
3. **Add `ollama` deployment** to docker-compose for the local fallback tier.
4. **Add Redis semantic cache** — already have Redis; just pass `cache={"type":"redis",...}` to the Router. Verify with a cached knowledge-base query.
5. **Add `is_paid` column** to the `Tenant` model (if not present) to drive free/paid rate limits.
6. **Wire `tenant_gate.run(...)`** around the LLM call in `agent.py` step 9.
7. **Backfill cost tracking**: persist `LLMResponse.cost_usd` into `TokenUsage` (add a `cost_usd` column).
8. **Load test**: simulate 8×N tenants hitting the webhook to confirm the 20 RPM OpenRouter ceiling holds with the leaky-bucket smoothing.

---

## Appendix: Verified Library Facts

| Library | URL | Stars | License | Role |
|---|---|---|---|---|
| LiteLLM | github.com/BerriAI/litellm | 57k | MIT | Orchestration + cache + cost |
| aiolimiter | github.com/mjpieters/aiolimiter | 777 | MIT | Per-tenant leaky-bucket rate limit |
| tiktoken | github.com/openai/tiktoken | 19k | MIT | Token counting (via litellm) |
| tenacity | github.com/jd/tenacity | 8.8k | Apache 2.0 | Retries for non-LLM calls only |
| GPTCache | github.com/zilliztech/GPTCache | 8.2k | MIT | *Not recommended* (maintenance mode; use LiteLLM cache) |
| LLMLingua | github.com/microsoft/llmlingua | 6.6k | MIT | Prompt compression for offline jobs |

### OpenRouter limits (verified openrouter.ai/docs)
- `:free` models: **20 req/min**, 50 req/day (or 1000/day with ≥10 credits purchased).
- Prompt caching supported.
- Pay-as-you-go / Enterprise tiers remove free limits.
