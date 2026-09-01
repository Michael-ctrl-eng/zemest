# Z2 — AI Core Part 1: Agent, LLM Client/Gateway, Concurrency, Prompts

**Task ID:** Z2 · **Scope:** `app/ai/agent.py`, `llm_client.py`, `llm_gateway.py`, `concurrency.py`, `prompts.py`, `__init__.py` (+ `RESEARCH_CONCURRENT_LLM.md` design intent) · **Mode:** research-only, no code modified.

**Repo:** `/home/z/my-project/repos/zemest` — FastAPI multi-tenant FB/IG/WhatsApp sales-agent SaaS (Egyptian market), free-tier LLMs.

---

## 0. Executive Summary — The Single Most Important Finding

The codebase contains **two parallel LLM stacks, and only the primitive one is live**:

| Stack | File | Status |
|---|---|---|
| **Live (production path)** | `app/ai/llm_client.py` — raw httpx, hand-rolled fallback loop | Imported by `agent.py`, `owner_chat.py`, `retriever.py`, `postiz_chat.py`, `style_learner.py`, `api/crawl.py`, `api/scheduling.py`, `api/postiz.py`, `tasks/crawl_tasks.py`, `knowledge/product_extractor.py` |
| **Dead (reference impl)** | `app/ai/llm_gateway.py` — LiteLLM Router + aiolimiter + Redis quota | **Imported by NOTHING** |
| **Dead (reference impl)** | `app/ai/concurrency.py` — per-tenant semaphores | **Imported by NOTHING** |

`llm_gateway.py` is moreover **unimportable as-is**: it does `from aiolimiter import AsyncLimiter` (line 27), but `aiolimiter` is **absent from `requirements.txt`** → `ModuleNotFoundError` on import. Its Ollama last-resort fallback points at `http://ollama:11434`, and **no Ollama service exists** in `docker-compose.yml`/`Dockerfile`.

**Consequence:** none of the RESEARCH_CONCURRENT_LLM.md recommendations (per-tenant rate limiting, daily quota, concurrency caps, caching, cost tracking, provider cooldowns) are active in production. The live path has **zero rate limiting, zero quotas, zero concurrency caps, zero cost tracking** — a single busy tenant can exhaust the shared OpenRouter free tier (20 RPM / 50–1000 req/day) for *all* tenants.

---

## 1. Agent Architecture (`app/ai/agent.py`, 485 lines)

### 1.1 Structure

Module-level function pipeline — **no classes**. One public entry point + 7 private helpers.

| # | Function | Signature | Returns | Lines |
|---|---|---|---|---|
| 1 | `process_customer_message` | `(db: AsyncSession, tenant: Tenant, sender_psid: str, message_text: str, fb_message_id: str \| None = None, customer_name: str \| None = None, channel: str = "messenger", media_urls: list[str] \| None = None, audio_urls: list[str] \| None = None)` | `str` (reply text, or `"duplicate"`) | 27–217 |
| 2 | `_transcribe_audio` | `(audio_urls: list[str])` | `str \| None` | 220–230 |
| 3 | `_analyze_images` | `(db: AsyncSession, tenant: Tenant, media_urls: list[str])` | `list` (vision results) | 233–270 |
| 4 | `_get_or_create_customer` | `(db, tenant_id: uuid.UUID, psid: str, name: str \| None = None, channel: str = "messenger")` | `Customer` | 273–296 |
| 5 | `_get_or_create_conversation` | `(db, tenant_id, customer_id, channel="messenger")` | `Conversation` | 299–329 |
| 6 | `_load_conversation_history` | `(db, conversation_id)` | `list[Message]` (chronological, ≤10) | 332–343 |
| 7 | `_create_order_from_data` | `(db, tenant, customer, conversation, order_data: dict)` | `bool` | 346–452 |
| 8 | `_calc_delivery` | `(tenant, governorate: str, items: list[dict], product=None)` | `Decimal` | 455–474 |
| 9 | `_get_fallback_response` | `(language: str)` | `str` | 477–484 |

Module constant: `MAX_HISTORY_MESSAGES = 10` (line 24).

### 1.2 The 14-step message pipeline (`process_customer_message`)

A customer message arrives via `app/api/webhook.py` (Messenger line 149, Instagram ~253, WhatsApp ~386, test_chat ~42) and is processed **inline in the webhook request** (not Celery):

1. **Voice transcription** (lines 46–49): if `audio_urls`, `_transcribe_audio` runs faster-whisper locally on the **first URL only** (`audio_urls[:1]`); on success replaces `message_text`.
2. **Image analysis** (lines 52–58): if `media_urls`, `_analyze_images` calls Gemini Vision on up to **3 URLs** (`media_urls[:3]`), writes a `TokenUsage` row (`usage_type="vision"`, model hardcoded `"gemini-2.0-flash"`) per success. If images but empty text, synthesizes an Arabic question about the recognized products. **Runs sequentially before the LLM call** — the research doc's parallel fan-out is not wired.
3. **Customer upsert** (lines 60–63): lookup by `(tenant_id, fb_psid)`; creates `Customer` with default name `"عميل"` if absent.
4. **Meta retry dedup** (lines 65–73): `SELECT` on `Message.fb_message_id`; returns sentinel `"duplicate"` if seen (webhook then skips sending).
5. **Conversation get/create** (line 75): latest conversation for customer (any age — **no session-timeout window**); a non-`active` conversation is force-reactivated.
6. **Persist customer message** (lines 78–87): `db.add(customer_msg)` (not flushed yet; `fb_message_id`, `media_urls` recorded).
7. **Load history** (line 90): last 10 messages by `created_at DESC`, reversed to chronological. ⚠️ **Autoflush bug — see §7.1.**
8. **RAG retrieval** (lines 93–95): `retrieve_context(db, tenant.id, message_text, max_nodes=3)` → `(products_context, knowledge_context)` from PageIndex knowledge graph.
9. **Language detection** (lines 97–122): `detect_language_advanced` → multi-dialect detection. Arabizi input is transliterated to Arabic script (`detection.normalized_text`) for the LLM. Prompt dialect selected: `english` / detected Arabic dialect / default `egyptian`.
10. **System prompt build** (lines 124–137): `get_system_prompt(...)` with tenant business name, RAG contexts, delivery fees (defaults 35/60 EGP), free-delivery threshold, payment methods, `style_profile` (learned per-page persona), dialect.
11. **LLM message assembly** (lines 139–160): `[system]` + up-to-10 history turns (customer→`user`, assistant→`assistant`) + final `user` message. Image context is appended to user content either as parsed vision text (`[العميل بعت صور. تحليل الصور:]...`) or raw URLs (`[العميل بعت صور: url1, url2, url3]`).
12. **LLM call** (lines 162–170): `chat_completion_with_usage(llm_messages)` from **llm_client** (no tenant/quota context passed). On total failure → `_get_fallback_response(lang)` static per-language apology (arabic / arabizi / english).
13. **Order extraction** (lines 172–184): `extract_order_from_response(raw_response)` parses an embedded `{"action":"create_order","order_data":{...}}` JSON block out of the model's reply. If found → `_create_order_from_data`: fuzzy product match (`Product.name.ilike(%name%)`), builds items, updates customer profile fields, calculates delivery, calls `create_order`, sets `conversation.status = "order_placed"`, dispatches Celery `send_order_notification` with sync fallback. On order failure the reply is **overridden** with an honest Arabic error message so the customer isn't lied to.
14. **Post-processing & persistence** (lines 186–217): `clean_response_for_customer` strips the JSON block; assistant `Message` saved; `TokenUsage` row (`usage_type="chat"`) saved with actual model + token counts; `conversation.last_message_at = datetime.utcnow()`; `db.flush()`. Commit happens in the **webhook** (`await db.commit()`), not here.

### 1.3 "Tool" invocation model

There are **no function-calling tools**. Capabilities are invoked by convention:
- **Order creation** = prompt-engineered JSON contract (§5): the model is told to emit a fenced `json` block with `action:"create_order"`; the agent regex/JSON-extracts it post-hoc (`order_collector.extract_order_from_response`) and executes as a side effect.
- **Vision** = pre-call Gemini Vision enrichment injected into the user message.
- **ASR** = pre-call faster-whisper transcription replacing message text.
- **RAG** = pre-call knowledge-graph retrieval injected into the *system* prompt (not the user turn).

This "JSON-in-band" tool protocol is simple and model-agnostic (works on free models without tool-calling support) but has correctness risks (§7.4).

---

## 2. LLM Client (`app/ai/llm_client.py`, 155 lines) — THE LIVE STACK

### 2.1 Functions

| Function | Signature | Returns | Lines | Purpose |
|---|---|---|---|---|
| `chat_completion` | `(messages: list[dict[str,str]], model: str \| None = None, temperature: float = 0.7, max_tokens: int = 1024)` | `str` | 34–42 | Thin wrapper — delegates to `chat_completion_with_usage`, returns `.content`. Used by `crawl_tasks.py`, `product_extractor.py`. |
| `chat_completion_with_usage` | `(messages, model=None, temperature=0.7, max_tokens=1024)` | `LLMResponse` | 45–70 | **Core entry.** Builds fallback chain, iterates models, 1 s sleep between attempts, raises `RuntimeError` if all fail. |
| `_prepare_messages` | `(messages: list[dict[str,str]], model: str)` | `list[dict[str,str]]` | 73–92 | For models whose name contains `google/gemma` or `gemma-3` (`NO_SYSTEM_ROLE` set, line 15): converts each `system` msg → `user` msg wrapped in `[INSTRUCTIONS]...[/INSTRUCTIONS]` + a synthetic `assistant` ack ("Understood. I will follow these instructions."). |
| `_call_openrouter` | `(messages, model: str, temperature: float, max_tokens: int)` | `LLMResponse` | 95–154 | Single POST to `{OPENROUTER_BASE_URL}/chat/completions`. |

**Dataclass:** `LLMResponse(content: str, model: str, prompt_tokens: int, completion_tokens: int, total_tokens: int)` — lines 25–31. **No cost field.**

### 2.2 Model selection & fallback chain (exact order)

```
settings.OPENROUTER_MODEL  (default "meta-llama/llama-4-maverick:free")   ← primary
  ↓ on ANY exception (incl. 429, 5xx, null content)
"google/gemini-2.0-flash-001"            ← paid/cheap tier (no :free suffix!)
  ↓
"qwen/qwen-2.5-72b-instruct"             ← paid
  ↓
"arcee-ai/trinity-large-preview:free"    ← free
  ↓
RuntimeError("All models failed. Last error: ...")
```
`FALLBACK_MODELS` (lines 18–22) — filtered to exclude the primary if it coincides (line 57). Note the comment on line 17 says "cheap paid first, then free" — **but the comment claims free-tier philosophy while 2 of 3 fallbacks are paid models**; if the account has no credits, those fallbacks will fail with 402/insufficient-credits and burn 1 s each before reaching the free Arcee model. No "paid" guard exists.

### 2.3 Retry/timeout/error handling characteristics

- **Retry policy:** exactly one attempt per model (no backoff, no Retry-After honoring, no jitter) + fixed `asyncio.sleep(1)` between models. Worst case ≈ 3×(60 s timeout) + 3 s ≈ 183 s inside a webhook request.
- **Timeout:** single global `httpx.AsyncClient(timeout=60.0)` (line 120) — applies to connect+read+write+pool.
- **Connection pooling:** **NONE** — a new `httpx.AsyncClient` is created and torn down per attempt (line 120). TLS handshake per call, no keep-alive reuse. Explicitly called out as a deficiency in the research doc §1.
- **Error taxonomy:** 429 → `RuntimeError("Rate limited on {model}")`; non-200 → `RuntimeError` with first 300 chars of body; empty `choices` → "No choices"; `content is None` → "null content". All exceptions treated identically by the fallback loop — **no distinction between retryable (429/5xx) and fatal (401/400)**.
- **Token tracking:** reads `usage` dict from the response; `model` field from response (may differ from requested — e.g., OpenRouter routing). Defaults 0 when absent. Persisted by agent step 13.
- **Degradation when key missing:** `OPENROUTER_API_KEY` empty → immediate `RuntimeError` per attempt → agent catches → static fallback reply. No Gemini-direct path exists in the live client despite `GEMINI_API_KEY`/`GEMINI_MODEL`/`LLM_PROVIDER` settings existing in config (`LLM_PROVIDER: "auto|openrouter|gemini|ollama"` at `config.py:35` is **read by nothing** — dead setting).
- **Headers:** `HTTP-Referer: https://zemest.local`, `X-Title: "Zemest"` (OpenRouter attribution).

---

## 3. LLM Gateway (`app/ai/llm_gateway.py`, 338 lines) — DEAD REFERENCE IMPLEMENTATION

Implements the research doc's 6 recommendations. Layout (8 sections):

### 3.1 Model list & fallback chain (lines 45–90)

LiteLLM `Router` deployments, aliases as routing keys:

| Alias | Deployment | rpm | Notes |
|---|---|---|---|
| `zemest-chat` | `openrouter/{OPENROUTER_MODEL}` | 20 | OpenRouter free-tier cap; `max_retries: 3` |
| `zemest-chat` | `openrouter/google/gemini-2.0-flash-001` | 20 | second deployment under same alias → load-balanced |
| `zemest-fallback-gemini` | `gemini/{GEMINI_MODEL}` | 15 | Gemini direct (free tier 15 RPM) |
| `zemest-fallback-local` | `ollama/llama3.2` @ `http://ollama:11434` | 1000 | **no such service in compose** |

`FALLBACKS = [{"zemest-chat": ["zemest-fallback-gemini"]}, {"zemest-fallback-gemini": ["zemest-fallback-local"]}]` — chat → Gemini → Ollama chain.

### 3.2 Router construction (lines 97–108, module import time)

`num_retries=3`, `retry_after=5` (honors 429 Retry-After), `allowed_fails=3` + `cooldown_time=60` (circuit-breaker-lite), `timeout=60`, `routing_strategy="usage-based-routing"`, `cache={"type":"redis","host": settings.REDIS_URL}` (semantic cache; `host` given a full `redis://` URL — dubious), `disable_add_params_to_message=True`. Globals: `litellm.drop_params=True`, `suppress_debug_info=True`. **No `redis_url=` param** → cooldown/RPM state is per-process only (the module's own comment admits production must add it).

### 3.3 Functions

| Function | Signature | Returns | Lines | Purpose |
|---|---|---|---|---|
| `get_tenant_limiter` | `async (tenant_id: uuid.UUID, is_paid: bool)` | `AsyncLimiter` | 141–153 | Lazy per-tenant leaky bucket under `_limiters_lock` (double-checked). FREE_TIER_RPM=0.7, PAID=60. Bug: `AsyncLimiter(max_rate=max(rpm,1), 60)` rounds 0.7 → **1.0 RPM** (free tenants get +43% rate). |
| `check_tenant_quota` | `async (tenant_id, is_paid)` | `bool` | 159–177 | Free tier: Redis `INCR quota:chat:{tenant}:{YYYYMMDD}`, `EXPIRE 86400` on first hit, allow ≤1000/day. Paid: always True. **Creates a new Redis connection per call** (`aioredis.from_url` + `aclose`) — no pooling. TTL is 24 h from *first message*, not midnight-aligned, contradicting the docstring. |
| `estimate_prompt_tokens` | `(messages, model)` | `int` | 183–185 | `litellm.token_counter` pre-call budget guard. **Never called anywhere** (not even internally — the budget guard is not wired into `chat_completion_with_usage`). |
| `estimate_cost_usd` | `(model, prompt_tokens, completion_tokens)` | `float` | 188–199 | `litellm.completion_cost`; returns 0.0 on any exception (silent under-reporting). |
| `chat_completion_with_usage` | `async (messages, *, tenant_id=None, is_paid_tenant=False, model=None, temperature=0.7, max_tokens=1024, cacheable=False)` | `LLMResponse` (+`cost_usd`) | 205–268 | Public entry: tenant limiter acquire → quota check (returns Arabic quota-exceeded message as a fake LLMResponse, `model="quota-exceeded"`) → `router.acompletion` (retries/cooldowns/fallbacks internal) → usage + cost extraction. `model` param **silently ignored** (always alias `zemest-chat`). `cacheable=True` opts into Redis semantic cache for deterministic KB Q&A only. |
| `TenantConcurrencyGate.acquire` | `async (tenant_id)` | `asyncio.Semaphore` | 287–296 | Lazy per-tenant semaphore (default 8) under lock. |
| `TenantConcurrencyGate.run` | `async (tenant_id, coro_fn, *args, **kwargs)` | Any | 298–308 | Executes `coro_fn` under the tenant's semaphore. |
| `gather_multimodal` | `async (tenant_id, text_task, vision_task=None, audio_task=None)` | `list` (Exceptions→None) | 318–338 | Parallel voice+vision+text fan-out through the gate via `asyncio.gather(return_exceptions=True)`; Python 3.9-safe (no TaskGroup). Expects **callables returning awaitables** (per research doc example), unlike `concurrency.gather_multimodal` which expects raw coroutines — API drift between the two modules. |

Singleton: `tenant_gate = TenantConcurrencyGate(max_per_tenant=8)` (line 312).

### 3.4 Routing/degradation summary (as designed, not as running)

Request → per-tenant leaky bucket → daily Redis quota → LiteLLM Router picks least-loaded healthy deployment of `zemest-chat` (retries 3× exp-backoff, honors Retry-After, 60 s cooldown after 3 consecutive fails) → fallback alias `zemest-fallback-gemini` → fallback `zemest-fallback-local` (Ollama) → (caller-side) agent static reply. Missing keys: OpenRouter key absent → Router deployment errors → cooldown → Gemini direct → Ollama. Cost: `completion_cost` per call; quotas enforce the free-tier budget.

**Critical defect cluster:** module import fails outright without `aiolimiter` (not in requirements); `resp.get("usage", {})` (line 251) assumes dict-style access on the Router response (modern LiteLLM returns a pydantic `ModelResponse` — dict-compat methods exist in most versions but this is fragile; line 258's `isinstance(resp, dict)` hedge shows the uncertainty); Ollama endpoint unresolvable; cache `host` misconfigured; Router built at import time (settings snapshot, side effects).

---

## 4. Concurrency (`app/ai/concurrency.py`, 95 lines) — ALSO DEAD

| Function | Signature | Returns | Lines | Purpose |
|---|---|---|---|---|
| `_get_gate` | `(tenant_id: str)` | `asyncio.Semaphore` | 22–27 | Lazy get/create `Semaphore(8)` (`MAX_CONCURRENT_PER_TENANT=8`) keyed by `str(tenant_id)` in module dict `_tenant_semaphores`. Sync, no lock — safe in single-threaded asyncio (no await between check/set), **not** thread-safe. |
| `run_with_tenant_limit` | `async (tenant_id: str, coro: Coroutine)` | `T` | 30–40 | `async with gate: await coro` — 9th concurrent conversation for a tenant waits. |
| `gather_multimodal` | `async (*coros: Coroutine)` | `list[T \| Exception]` | 43–58 | `asyncio.gather(return_exceptions=True)`; logs each failure; callers check `isinstance(r, Exception)`. Takes **coroutines** (vs gateway's callables). |
| `gather_with_limit` | `async (limit: int, *coros)` | `list[T \| Exception]` | 61–79 | Global-bounded parallelism via one shared `Semaphore(limit)`; inner `_run` catches exceptions → returned as values. If gather is cancelled, un-started wrapped coroutines are never awaited ("coroutine never awaited" warnings). |
| `get_tenant_active_count` | `(tenant_id: str)` | `int` | 82–88 | `8 - sem._value` — reads CPython **private** `_value` (fragile across versions; ignores queued waiters when value is 0). |
| `reset_tenant_gate` | `(tenant_id: str)` | `None` | 91–95 | Test helper — deletes the tenant's semaphore entry. |

**Design notes vs research doc:** this module *is* research recommendation #6 (`Semaphore` per tenant + `gather`, no TaskGroup — Python 3.9). Backpressure: the semaphore *blocks* (no queue depth cap, no timeout — a stuck LLM call holds a slot for up to 60 s×N). No batching, no connection pooling (irrelevant here — it's pure asyncio orchestration). `_tenant_semaphores` grows unboundedly with tenant count (semaphores never evicted; ~100 bytes each — negligible but unbounded). **Duplication:** `TenantConcurrencyGate` in llm_gateway.py re-implements this module with uuid keys; the two have drifted (str vs UUID keys, coroutine vs callable conventions, lock-protected vs lock-free lazy init).

---

## 5. Prompt Engineering (`app/ai/prompts.py`, 287 lines)

### 5.1 `DIALECT_PERSONA` (lines 13–50)

Dict of 9 personas — keys: `egyptian`, `gulf`, `levantine`, `maghrebi`, `iraqi`, `sudanese`, `yemeni`, `msa`, `english`. Each provides `intro_line` (appended to the "professional sales agent" preamble — Arabic script for Arabic dialects) and `lang_rule` (replaces the first strict-rules bullet). All Arabic variants share the framing "تتكلم مع العميل كأنك صاحب المكان — ودود ومباشر ومحترم" ("talk like you're the owner — friendly, direct, professional"). The `english` persona is fully English.

### 5.2 `get_system_prompt(...)` (lines 53–191) — the main template

**Params:** `business_name: str`, `products_context: str`, `knowledge_context: str = ""`, `language_hint: str = "auto"` (**accepted but never used in the body — dead param**), `delivery_inside_cairo: float = 35`, `delivery_outside_cairo: float = 60`, `free_delivery_above: float | None = None`, `payment_methods: dict | None = None`, `style_profile: dict | None = None`, `dialect: str = "egyptian"`. Returns `str`.

**Template structure (f-string, Arabic-dominant):**
1. **Role preamble:** "You are a professional, smart salesperson for page `{business_name}` on Facebook" + dialect `intro_line`.
2. **Identity line (model branding):** Arabic → "Rabbit v1" (Arabic-dialect specialist); English → "Rat v1" (English specialist) — with the instruction "reply so naturally the customer can't tell they're talking to an AI." **This is a deceptive-AI directive** (undisclosed bot identity — compliance risk, e.g., Meta platform policy & Egypt consumer-protection norms).
3. **`## شخصيتك` (Personality):** style_profile injection — tone (friendly/formal/neutral), greeting/signoff patterns (quoted verbatim), emoji if `emoji_use > 0.2`; default "friendly & respectful tone".
4. **`## القواعد الصارمة` (Strict rules):** dialect lang_rule; never say "sorry/can't"; treat "أيوه/تمام/حسناً" as consent → immediately upsell & start order collection; if no product chosen, suggest 2–3 with prices; answer category questions with priced products immediately; pushy-sales lines ("most-sold product!", "offer ends soon!"); keep replies to **2–4 sentences** (the only length/implicit token control).
5. **`## ممنوع` (Prohibited):** don't invent prices/products; don't send links not present in the product link field; no offensive words or exaggerated promises.
6. **`## المنتجات` (Products):** raw `products_context` injection + optional `## معلومات الصفحة` knowledge block.
7. **`## عملية الطلب` (Order process):** 4 steps — clarify product+qty → collect name/phone/address/payment with a literal templated message (with ✏️📱📍💳 emojis) → address inference heuristics for Cairo districts (المعادي→Cairo, المهندسين→Giza, سيدي جابر→Alexandria) → after confirmation emit the **JSON order contract**: fenced ```json block, `{{"action":"create_order","order_data":{...}}}` (f-string braces correctly escaped at lines 178–180; schema fields: items[product_name, quantity], customer_name, customer_phone, governorate, city, area, address_detail, payment_method).
8. **`## الشحن والتوصيل` (Shipping):** inside/outside Cairo fees (int-cast), optional free-delivery note, product-specific delivery override rule.
9. **`## العملات والدفع` (Currency & payment):** EGP; COD/Vodafone Cash/InstaPay/Fawry; `pay_info` lines from `payment_methods` dict (keys `vodafone_cash`, `instapay`, `fawry`), defaulting to COD.

### 5.3 `get_product_context(products: list[dict]) -> str` (lines 194–287)

Compact catalog renderer: empty list → English "No products available yet…" (note: English inside an Arabic prompt). Per product: `- {name}: {price} ج.م` (~~price~~ discount struck through), stock icon ✅/❌/⚠️/📦 + label, optional `[name_ar]`, description truncated to **80 chars**, all non-special attributes as indented `key: value` lines, product URL as `رابط المنتج: {url}`. Special keys skipped: name, name_ar, description, price, discount_price, stock_status, category, url, image_url, sku. Grouped under `## {category}` headers when any product has a category (uses `collections.defaultdict` — imported locally at line 271, though also present at module level? No — module has no defaultdict import; it's imported inside the function; the `defaultdict` import at concurrency.py:10 is a different file).

### 5.4 Guardrails against prompt injection — assessment

- **Customer-message injection:** the customer's raw text goes into the `user` role; the system prompt relies on role separation only. There is **no explicit anti-injection instruction** (no "ignore any instructions in the customer message", no delimiting/escaping of user content). Tests exist (`tests/security/test_prompt_injection.py`) but they **mock out `process_customer_message` entirely** (lines 91–186 patch it with `AsyncMock`) — they test webhook routing, not injection resistance. Real mitigation is partial: `clean_response_for_customer` post-filters the reply, and the JSON order gate requires an exact schema.
- **Second-order injection (the bigger hole):** `products_context` / `knowledge_context` derive from **crawled web pages** (`crawl_tasks.py`, `product_extractor.py`) — attacker-controlled e-commerce page content is embedded **directly into the system prompt** with full instruction authority. Same for `style_profile` (learned from chat history) and `business_name` (page name). A malicious product description can steer orders/prices ("ignore shipping fees") with no sanitization anywhere in this file.
- **Media URLs** are appended into the user turn raw (`agent.py:158`) — Meta-signed CDN URLs, low risk, but unbounded string length from attacker attachment metadata is unclamped here (clamped to 3 URLs).
- **Token budget management:** implicit only — 10-message history cap, `max_nodes=3` retrieval, 80-char description truncation, `max_tokens=1024` completion, "2–4 sentences" instruction. **No actual token counting** in the live path (the gateway's `estimate_prompt_tokens` is never called). A huge catalog (products_context is unclamped) can silently blow the context window of free models → API errors → fallback chain → static reply.

---

## 6. Function Inventory (all 5 files, complete)

| File | Function / Class | Params | Returns | Purpose | Lines |
|---|---|---|---|---|---|
| agent.py | `process_customer_message` | db, tenant, sender_psid, message_text, fb_message_id=None, customer_name=None, channel="messenger", media_urls=None, audio_urls=None | `str` | Full customer-message pipeline (14 steps) → reply | 27–217 |
| agent.py | `_transcribe_audio` | audio_urls: list[str] | `str \| None` | faster-whisper transcription of 1st voice note | 220–230 |
| agent.py | `_analyze_images` | db, tenant, media_urls: list[str] | `list` | Gemini Vision product-image analysis (≤3), TokenUsage rows | 233–270 |
| agent.py | `_get_or_create_customer` | db, tenant_id, psid, name=None, channel="messenger" | `Customer` | Idempotent customer upsert by (tenant, psid) | 273–296 |
| agent.py | `_get_or_create_conversation` | db, tenant_id, customer_id, channel="messenger" | `Conversation` | Reuse latest conversation (reactivate) or create | 299–329 |
| agent.py | `_load_conversation_history` | db, conversation_id | `list[Message]` | Last 10 messages, chronological | 332–343 |
| agent.py | `_create_order_from_data` | db, tenant, customer, conversation, order_data: dict | `bool` | Fuzzy product match, order creation, Celery notify | 346–452 |
| agent.py | `_calc_delivery` | tenant, governorate, items, product=None | `Decimal` | Delivery fee: product override → free threshold → Cairo/Giza vs rest | 455–474 |
| agent.py | `_get_fallback_response` | language: str | `str` | Static apology in arabic/arabizi/english | 477–484 |
| llm_client.py | `LLMResponse` *(dataclass)* | content, model, prompt_tokens, completion_tokens, total_tokens | — | LLM call result container | 25–31 |
| llm_client.py | `chat_completion` | messages, model=None, temperature=0.7, max_tokens=1024 | `str` | Content-only convenience wrapper | 34–42 |
| llm_client.py | `chat_completion_with_usage` | messages, model=None, temperature=0.7, max_tokens=1024 | `LLMResponse` | Fallback-chain chat completion with usage | 45–70 |
| llm_client.py | `_prepare_messages` | messages, model | `list[dict]` | system→user conversion for Gemma models | 73–92 |
| llm_client.py | `_call_openrouter` | messages, model, temperature, max_tokens | `LLMResponse` | Single httpx POST to OpenRouter | 95–154 |
| llm_gateway.py | `LLMResponse` *(dataclass)* | content, model, prompt_tokens, completion_tokens, total_tokens, **cost_usd** | — | Gateway result container (+cost) | 115–122 |
| llm_gateway.py | `get_tenant_limiter` | tenant_id: uuid, is_paid: bool | `AsyncLimiter` | Per-tenant leaky-bucket rate limiter | 141–153 |
| llm_gateway.py | `check_tenant_quota` | tenant_id: uuid, is_paid: bool | `bool` | Redis INCR daily quota (free ≤1000/day) | 159–177 |
| llm_gateway.py | `estimate_prompt_tokens` | messages, model | `int` | Pre-call token count (litellm) — never used | 183–185 |
| llm_gateway.py | `estimate_cost_usd` | model, prompt_tokens, completion_tokens | `float` | USD cost estimate; 0.0 on error | 188–199 |
| llm_gateway.py | `chat_completion_with_usage` | messages, *, tenant_id=None, is_paid_tenant=False, model=None, temperature=0.7, max_tokens=1024, cacheable=False | `LLMResponse` | Limited+quota'd+cached router call | 205–268 |
| llm_gateway.py | `TenantConcurrencyGate.__init__` | max_per_tenant=8 | — | Per-tenant semaphore registry init | 282–285 |
| llm_gateway.py | `TenantConcurrencyGate.acquire` | tenant_id | `asyncio.Semaphore` | Lazy semaphore creation under lock | 287–296 |
| llm_gateway.py | `TenantConcurrencyGate.run` | tenant_id, coro_fn, *args, **kwargs | Any | Run callable under tenant's semaphore | 298–308 |
| llm_gateway.py | `gather_multimodal` | tenant_id, text_task, vision_task=None, audio_task=None | `list` (exc→None) | Parallel multimodal fan-out through gate | 318–338 |
| concurrency.py | `_get_gate` | tenant_id: str | `asyncio.Semaphore` | Lazy Semaphore(8) per tenant | 22–27 |
| concurrency.py | `run_with_tenant_limit` | tenant_id: str, coro: Coroutine | `T` | Execute under tenant concurrency cap | 30–40 |
| concurrency.py | `gather_multimodal` | *coros: Coroutine | `list[T \| Exception]` | Parallel fan-out, exceptions as values | 43–58 |
| concurrency.py | `gather_with_limit` | limit: int, *coros | `list[T \| Exception]` | Globally-bounded parallel gather | 61–79 |
| concurrency.py | `get_tenant_active_count` | tenant_id: str | `int` | In-flight count via private `sem._value` | 82–88 |
| concurrency.py | `reset_tenant_gate` | tenant_id: str | `None` | Remove tenant semaphore (tests) | 91–95 |
| prompts.py | `get_system_prompt` | business_name, products_context, knowledge_context="", language_hint="auto", delivery_inside_cairo=35, delivery_outside_cairo=60, free_delivery_above=None, payment_methods=None, style_profile=None, dialect="egyptian" | `str` | Dialect-aware sales-agent system prompt | 53–191 |
| prompts.py | `get_product_context` | products: list[dict] | `str` | Compact catalog renderer (grouped, truncated) | 194–287 |
| __init__.py | — | — | — | **Empty file** (package marker only) | 0 |

Module-level singletons/objects: `llm_gateway.router` (line 97), `llm_gateway.tenant_gate` (312), `llm_gateway._tenant_limiters` (137), `concurrency._tenant_semaphores` (19), `prompts.DIALECT_PERSONA` (13–50), `agent.MAX_HISTORY_MESSAGES` (24), `llm_client.NO_SYSTEM_ROLE` (15), `llm_client.FALLBACK_MODELS` (18–22), `llm_gateway.MODEL_LIST`/`FALLBACKS`/`FREE_TIER_RPM`/`PAID_TIER_RPM` (45–132), `concurrency.MAX_CONCURRENT_PER_TENANT` (18).

---

## 7. Issues / Risks (with file:line references)

### Critical

1. **No production rate limiting / quota / concurrency control.** `agent.py:165` calls `llm_client.chat_completion_with_usage` with no tenant context; the entire gateway/concurrency apparatus (§3–4) is unimported dead code. Under load, one tenant exhausts the shared OpenRouter free tier (20 RPM) for every tenant; webhook latency spikes as the 4-model fallback loop + `sleep(1)` serializes per message (`llm_client.py:60–68`). *Cost risk:* 2 of 3 fallback models are **paid** (`llm_client.py:19–20`) — a free-tier outage cascades into paid spend with no budget guard.
2. **Autoflush duplicates the current user message in the LLM context.** `agent.py:87` adds `customer_msg` to the session; `agent.py:90`'s `db.execute` triggers SQLAlchemy autoflush (session factory `app/database.py:15` leaves default `autoflush=True`), so the SELECT at `agent.py:335–340` includes the just-flushed message. It is then re-appended at `agent.py:160` → the customer's message appears **twice** in every LLM call. Wastes tokens, skews the model, and inflates `prompt_tokens` billing rows.
3. **Dedup race on Meta retries.** `agent.py:67–73` is SELECT-then-insert with no unique constraint on `Message.fb_message_id` (`app/models/message.py:23` — plain `String(128)` column, no `unique=True`). Two concurrent webhook deliveries of the same `mid` both pass the check → duplicate AI replies/orders. (Query is also not tenant-scoped, though Meta mids are globally unique.)
4. **Second-order prompt injection via RAG context.** `prompts.py:158–159` embeds `products_context`/`knowledge_context` — sourced from crawled, third-party-controlled pages — verbatim into the system prompt with no sanitization. A poisoned catalog entry can override pricing/shipping rules or exfiltrate the order JSON schema to force fake orders. First-order customer-message injection is likewise unmitigated by any explicit instruction (§5.4); the dedicated tests mock the agent away (`tests/security/test_prompt_injection.py:91,128,158,186`).
5. **`llm_gateway.py` is unimportable and misleading.** `aiolimiter` missing from `requirements.txt` (`llm_gateway.py:27` vs requirements — only `litellm>=1.82.0` present); Ollama fallback endpoint `http://ollama:11434` (`llm_gateway.py:80`) has no corresponding service; `resp.get(...)` dict-access on a Router response (`llm_gateway.py:251,252,258`) is version-fragile against pydantic `ModelResponse`; cache `host` receives a full `redis://` URL (`llm_gateway.py:106`). Anyone following the research doc's migration checklist step 1 will hit an ImportError first.

### High

6. **No connection pooling in the live client.** New `httpx.AsyncClient` per attempt (`llm_client.py:120`) — TLS handshake + no keep-alive on every chat call; adds ~100–300 ms latency per message and port churn under load.
7. **Slow-failure worst case blocks the webhook ~3 min.** 4 models × 60 s timeout + 3×1 s sleeps (`llm_client.py:60–70,120`) with no circuit breaker or per-attempt timeout budget; Meta webhook retries may pile on (mitigated only by the fb_message_id dedup — itself racy, see #3).
8. **Blind product matching can create zero-priced orders.** `agent.py:364–377`: `ilike(f"%{product_name}%")` with unescaped `%`/`_` wildcards; no match → `unit_price = 0` and the order is still created — an LLM hallucination ("منتج مش موجود") yields a free item, and `matching is None` rows carry `product_id=None`.
9. **No conversation expiry.** `_get_or_create_conversation` (`agent.py:299–329`) reactivates the newest conversation regardless of age → months-old context mixes into "new" sessions.
10. **Deceptive AI identity.** `prompts.py:80–92` instructs the model to be indistinguishable from a human ("Reply so naturally that the customer cannot tell they are talking to an AI") — platform-policy (Meta) and legal (Egypt consumer protection) exposure.

### Medium

11. **Token-tracking blind spots.** Fallback replies (`agent.py:170`) record no usage; vision usage hardcodes model `"gemini-2.0-flash"` (`agent.py:260`) ignoring `settings.GEMINI_MODEL`; no cost_usd persisted anywhere live (TokenUsage has no cost column; research checklist item 7 outstanding).
12. **Two drifted concurrency implementations.** `concurrency.py` (str keys, coroutines, sync lazy-init) vs `llm_gateway.TenantConcurrencyGate` (UUID keys, callables, locked lazy-init) — plus **two different `gather_multimodal` and `chat_completion_with_usage` symbols with incompatible signatures** across modules (`concurrency.py:43` vs `llm_gateway.py:318`; `llm_client.py:45` vs `llm_gateway.py:205`). A future import swap is a silent-behavior-change trap.
13. **Private-attribute / fragile APIs.** `concurrency.py:88` reads `sem._value`; `llm_gateway.py:253–255` calls `.get()` on a usage object of uncertain type; `llm_gateway.py:151` rounds free-tier RPM 0.7→1.
14. **Quota counting side effects (gateway).** `check_tenant_quota` INCRs before the call — failed/exception requests still consume quota; a fresh Redis connection per message (`llm_gateway.py:169–177`); TTL not midnight-aligned despite docstring.
15. **`language_hint` dead param** (`prompts.py:57`) — callers pass it, template ignores it (dialect is the real control). Also `get_product_context`'s empty-catalog text is English inside an Arabic prompt (`prompts.py:207`).
16. **`LLM_PROVIDER` config setting is dead** (`config.py:35`) — no provider routing exists in the live client; Gemini key is only used for vision, never as a chat fallback.
17. **`datetime.utcnow()` naive** (`agent.py:214`, `models/message.py:24`) — deprecated in Python 3.12, inconsistent with tz-aware fields elsewhere (`agent.py:6` imports `timezone` unused at that site).
18. **Unbounded system prompt.** `products_context` has no size cap in `prompts.py` (only 80-char per-description truncation); large catalogs can exceed free-model context windows; the pre-flight token guard (`llm_gateway.py:183`) is never invoked.

### Low

19. Sequential voice→vision→LLM processing (`agent.py:46–58`) adds latency; the parallel fan-out exists in dead code only.
20. `_tenant_semaphores`/`_tenant_limiters` never evicted (unbounded dict growth, ~negligible).
21. Order-failure override message (`agent.py:181–184`) is Arabic-only even for English customers.

---

## 8. Quality Ratings

| File | Score | Justification |
|---|---|---|
| `agent.py` | **7/10** | Clear 14-step pipeline, good docstrings, honest order-failure handling, Meta dedup awareness, thoughtful Arabizi transliteration. Loses points for: autoflush duplication bug (#2), racy dedup (#3), zero-priced order path (#8), no conversation expiry (#9), sequential multimodal (#19). |
| `llm_client.py` | **5/10** | Correct and minimal for what it does — usage extraction, Gemma system-role handling, null-content guard. But: no pooling (#6), no backoff/Retry-After, no retryable-vs-fatal distinction, paid fallbacks in a "free-first" design (#1), ~3-min worst case (#7), no rate awareness at all. Adequate prototype, not production. |
| `llm_gateway.py` | **4/10** | Well-commented, faithful to the research doc, sound architecture (limiter→quota→router→fallback, cost tracking). But it's dead, unimportable code (#5) with config bugs (cache host, missing redis_url admission, fake Ollama endpoint, dead `model` param, RPM rounding) — it has never run; its correctness is unproven. |
| `concurrency.py` | **6/10** | Small, clean, Python-3.9-correct asyncio patterns; exception-as-value convention is pragmatic. Deducted for private `_value` access, no eviction, unbounded blocking without timeout, and being dead + duplicated by the gateway. |
| `prompts.py` | **7.5/10** | Genuinely strong dialect engineering (9 personas), compact catalog format, correct JSON-contract escaping, sensible defaults, good test coverage in `test_prompts.py`. Deducted for: no injection defenses (#4), dead `language_hint`, unbounded size (#18), deceptive-identity directive (#10), mixed-language artifacts. |

**Overall AI-core (part 1): 5.5/10** — a competent single-tenant prototype wearing a multi-tenant costume. The architecture *design* (research doc + gateway) is solid; the *implementation actually serving traffic* is the weakest link, and the gap between them is the project's biggest engineering debt in this layer.

---

*Z2 — analysis complete. Related files for downstream agents: `order_collector.py`, `language_engine.py`, `style_learner.py`, `knowledge/retriever.py`, `services/vision.py`, `services/transcription.py`, `api/webhook.py`.*
