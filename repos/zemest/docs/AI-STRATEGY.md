# Zemest AI Strategy — 5–8 EUR/month budget, 10K+ users/day

**Decision document. Answers: which model, self-host vs API, batching, voice/image/text, and how it scales.**

---

## 1. The verdict up front

| Question | Answer |
|---|---|
| Self-host an open model on a 5–8 EUR VPS? | **No.** A 7-EUR VPS (2–4 vCPU, 4–8 GB RAM) cannot serve a 7B+ model at chat latency. One Llama-3-8B Q4 request needs ~6 GB RAM + a full CPU-second batch; under concurrency it collapses to 10–60 s per reply, exactly the "very very slow" you predicted. |
| Train/fine-tune our own model? | **No (now).** Fine-tuning does not fix tokens-per-second — inference hardware does. Style is already handled by prompt engineering (style_profile), not weights. |
| Use "Game4A4B"-style open models locally? | Same physics: any model that handles voice+image+text (multimodal, ≥8B params) needs a GPU with ≥16 GB VRAM ≈ 0.40–0.80 EUR/hour on spot ≈ **300–600 EUR/month** if always-on. 75× your budget. |
| Then what? | **Hosted inference APIs with free tiers + cheap paid fallback.** The open models (Llama, Qwen, Whisper) run on *their* GPUs; we pay per token, which at sales-agent traffic sizes is cents. |
| "Get all messages at once to the model"? | **Per-conversation batching, not global batching.** Each customer conversation keeps its own context; we batch *retrieval + prompt assembly* and cap history, so each LLM call stays ~1–2k tokens. Grouping strangers' messages into one call would leak cross-customer data and degrade replies. |

---

## 2. The numbers (measured against our real traffic shape)

A Zemest sales-agent reply averages **~1.5k input + ~200 output tokens** (10-message history, product context, system prompt — already capped by the audit fixes).

**10,000 users/day** in this product means ~10k messages/day worst case → ~15M input + 2M output tokens/day.

| Provider tier | Limit | Cost at our traffic | Verdict |
|---|---|---|---|
| **Groq free** (Llama-3.3-70B, Whisper STT) | 30 req/min, 1k–14.4k req/day, ~12k tokens/min | free | Primary text+voice; 14.4k req/day covers the whole target |
| **Gemini free tier** | ~20 req/day after 2025 cuts | free | Dead for text; **Vision is separate**: Gemini Flash vision is still usable via API key for image analysis |
| **Groq paid on-demand** | ~$0.59/$0.79 per 1M in/out (Llama-3.3-70B) | ~$9/day at full 10k load | Burst overflow |
| **GLM API (Z.ai)** | ~$1.40/$4.40 per 1M tokens | ~$23/day at full 10k load | Arabic quality fallback |
| **Self-host (any 8B+)** | 1–2 concurrent requests on 7-EUR VPS | 7 EUR + unusable latency | Rejected |

**Reality check:** "10,000 users/day" ≠ 10,000 *messages*/day. For FB/IG shop pages, 1k–3k messages/day is already a top-1% busy merchant. At 2k messages/day: **~3M tokens/day ≈ $1.80–5.40/day on paid API — within a 5–8 EUR monthly budget only if most traffic rides the free tier.**

### Budget plan (7 EUR/month)

| Slot | Choice | Why |
|---|---|---|
| Text chat (95% of calls) | Groq free → OpenRouter :free models → GLM flash-tier | Free tiers stack; the provider ladder already falls back |
| Voice notes | Groq Whisper (free, 2k req/day, ~10 s audio) | Arabic STT quality good; faster-whisper local remains offline fallback |
| Product images | Gemini Flash vision API free quota; skip analysis if exhausted | Low volume (image messages are rare in DMs) |
| VPS (7 EUR) | Hetzner CX22-class (2 vCPU/4 GB) | Runs FastAPI + Postgres + Redis + Huey — *not* the model |
| Overflow | Pay-as-you-go Groq/OpenRouter with a hard monthly cap (5 EUR alert, 8 EUR kill) | Prevents the financial-DoS the audit flagged (llm quota work) |

**Total: 0 EUR model cost at free-tier traffic; 5–8 EUR total with VPS.** The provider ladder in `app/ai/llm_client.py` already implements the fallback chain — the missing piece (per-tenant daily quota + budget kill-switch) is scheduled in the limits/plan work.

---

## 3. Why not one giant batched call ("all messages to the model at once")

Your instinct ("get all messages once, model replies, we route replies") is how *support desks with 1 ticket queue* work. For conversational sales agents it breaks:

1. **Cross-customer privacy**: batching strangers into one context means customer A's address can influence customer B's reply. One leak = one GDPR/EU-AI-Act problem.
2. **Context interference**: sales personas are per-tenant (different style_profiles, catalogs, delivery prices). A merged context averages them; replies drift.
3. **Tokens/second does not improve**: API cost is per *token*, not per *call* — merging calls saves nothing, but destroys per-conversation history.
4. **Latency couples all customers**: one slow conversation blocks the batch.

**What we DO batch (already designed):**
- **Silent trainer** (style learning) already batches: 45-second cycles, ≤400 conversations/tenant, 50-message LLM samples — one LLM call per tenant per cycle, not per message.
- **Blog/article generation** (new module) is naturally one-shot batched generation.
- **Webhook ingestion** batches persistence, then enqueues per-conversation LLM jobs through Huey — webhook ack stays <1 s.

So: **batch the background analytics, keep per-conversation realtime replies.** This is the same shape Postiz uses (durable per-post workflows, not one global job).

---

## 4. Voice + image + text on one model?

No single free-tier model does all three well. Our architecture already splits:

- **Text**: LLM router (Groq Llama / OpenRouter / GLM) — `app/ai/llm_client.py`
- **Voice**: Whisper (Groq hosted or faster-whisper local) — `app/services/transcription.py`
- **Image**: Gemini Flash vision — `app/services/vision.py`

This is correct and cheap. A single multimodal endpoint (GPT-4o-mini class) would cost 5–10× more per image than Gemini's free quota.

---

## 5. What we're building to make this real (wiring plan)

| Piece | Status |
|---|---|
| Provider fallback ladder + 45 s budget | done (F1/F2) |
| Prompt-size caps (history 10, products ≤50, learned-string sanitizers) | done (F2) |
| Token usage ledger per tenant (`token_usage`) | exists; **quota enforcement next** |
| Per-tenant daily LLM quota + plan-based caps + global budget kill-switch | scheduled with Plans module |
| Whisper-on-Groq (replace local faster-whisper default) | scheduled (channel wave) |
| Rate-limit-aware retry (honor Retry-After, exponential backoff) | scheduled with quota work |
| `SCALING.md` (10K→100K path: read replicas, Redis, pgbouncer) | scheduled (F8) |

---

## 6. Sources (checked 2026-09)

- Groq rate limits & spend limits: console.groq.com docs + CloudZero/eSell pricing surveys (free tier ~30 RPM / 14.4k RPD / 12k TPM Llama-3.3-70B)
- Gemini API free-tier cuts (Flash ≈ 20 RPD): ai.google.dev rate-limits page + community reports
- GLM API pricing ($1.40/$4.40 per 1M in/out, flash-tier discounts): docs.z.ai pricing + OpenRouter listings
- Hetzner Cloud pricing (shared vCPU from ~€4.5–5.5/mo; CX22-class fits FastAPI+PG+Redis): hetzner.com/cloud + costgoat calculator
- Postiz (gitroomhq/postiz-app): Temporal workflow-per-post, heartbeat-timeout classification, hourly missing-post sweep, versioned workflows — architecture lessons applied to our scheduler (see SCALING.md, scheduled)
