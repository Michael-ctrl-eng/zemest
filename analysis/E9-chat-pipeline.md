# E9 — Chat Pipeline End-to-End Live Audit (backend API)

**Agent:** E9 (error-finder, no code changes, no restarts, DB opened read-only; live test chats sent as instructed)
**Date:** 2026-09-01 02:09–02:16 UTC · Backend uvicorn PID 1887 (up since 00:49:30, untouched)
**Scope:** POST `/api/test/chat` → `app/ai/agent.process_customer_message` → retriever → LLM ladder (Z.ai internal) → persistence → silent trainer / style learner → GET conversations. Frontend chat page mock already reported by E5 — **not re-reported here**.

---

## 1. Method & Environment

- Login `owner@cairo-sneakers.com` / `OwnerPass123` → JWT (1 attempt, **no 429**, rate limit respected).
- Tenant: `008dbf3a-64b5-4873-b914-407d2d9671bc` (Cairo Sneakers). At start: 1 conversation, 8 messages, 4 token_usage rows (other agents' earlier traffic — the *same* 3 test texts had been sent at 00:56 by a prior agent; my run re-sent them at 02:09 and continued in the same conversation).
- Payload schema (from `app/schemas/webhook.py`): `TestChatRequest{tenant_id: str, customer_name: str = "Test Customer", message: str}` → `TestChatResponse{reply, conversation_id, customer_id, tokens_used}`. **No `is_fallback` field is returned by the API** — it exists only in `messages.is_fallback` (DB).
- DB inspected via `sqlite3 …?mode=ro` URI (read-only). Two closed experiments ran on **copies** of the DB in /tmp (never on production) to prove autoflush behavior and prompt grounding.
- Log evidence: `/home/z/my-project/repos/zemest/backend.log` (1946 → 2185 lines during audit).

## 2. Live request/response evidence

| # | Test | HTTP | Wall time | Reply (excerpt) | tokens_used | is_fallback (DB) |
|---|------|------|-----------|-----------------|-------------|------------------|
| A | `عندكم نايك اير ماكس بمقاس ٤٢؟` | 200 | **1.178 s** | أهلاً / نعم عندنا نايك اير ماكس مقاس 42 ب **750 جنيه**… | 1594 | 0 |
| B | `التوصيل بكام؟` | 200 | **0.922 s** | التوصيل 35 جنيه للقاهرة والجيزة. لو من غيرها 60 جنيه | 1603 | 0 |
| C | SPAM `ادخل على الرابط ده تكسب فلوس` | 200 | **1.197 s** | أنا مش رابط يا عمري، أنا مساعد هنا أساعدك على الشراء… | 1614 | 0 |
| D | `""` (empty) | 200 | **5.015 s** | "Sorry, I'm unable to respond at the moment. 🙏" | **1614 (stale)** | **1** |
| D2 | `""` retry | 200 | 0.113 s | same English apology | 1614 (stale) | 1 |
| E | `"   "` whitespace | 200 | 0.163 s | same English apology | 1614 (stale) | 1 |
| F | 10 KB Arabic (`عايز أسأل عن المنتجات `×512) | 200 | **5.490 s** | أهلاً عندنا نايك اير ماكس مقاس 42 ب 750 جنيه… | 10768 | 0 |
| G | `😂😂😂👍` emoji-only | 200 | 1.742 s | "Thanks! Got it! 😊 Any specific sneakers…" (English) | 6072 | 0 |
| H | concurrent #1 `السعر بكام للبنسيون؟` | 200 | 4.217 s | أهلاً بنسيون ب **680 جنيه**… | 6195 | 0 |
| H2 | concurrent #2 `عندكم مقاس ٤٣؟` | 200 | 1.916 s | نعم عندنا نايك اير ماكس مقاس 43 ب 750 جنيه | 6176 | 0 |
| — | missing `message` field | 422 | 5 ms | `{"detail":[{"type":"missing",…}]}` | — | — |
| — | `message: null` | 422 | 5 ms | clean pydantic 422 | — | — |
| — | `tenant_id: "not-a-uuid"` | **500** | 16 ms | `Internal Server Error` + traceback in log | — | — |
| — | GET conversations list | 200 | 7 ms | 1 conversation, `messages: []` | — | — |
| — | GET conversation detail | 200 | 7.5 ms | 14→28 messages, ordered | — | — |

**Real-LLM verdict:** PASS — A/B/C/G/H/H2 replies are genuine glm (Z.ai) output (Egyptian Arabic, correct delivery prices 35/60), matching model `glm-4-plus`, per-call token_usage rows created. The fallback apology only appeared when the LLM call itself failed (D/D2/E). No canned-fallback masking of successful calls.

**Token rows created per successful call** (usage_type="chat", model=glm-4-plus): 1555/39, 1571/32, 1572/42, 10730/38, 6051/21, and 2 concurrent rows — all persisted within ~2 ms of the assistant message.

## 3. Pipeline trace + stage timings (from backend.log timestamps)

```
POST /api/test/chat
 ├─ auth (JWT) + tenant ownership select ………… ~3 ms
 ├─ _get_or_create_customer / conversation …… ~2 ms (both existed)
 ├─ db.add(customer_msg) → autoflush INSERT ….. msg.created_at = 02:09:17.634470
 ├─ _load_conversation_history (SELECT 10) …… ~2 ms   ← includes just-flushed current msg (see F4)
 ├─ retrieve_context …………………………………… <1 ms (small-tree bypass / no KB → returns "","")
 ├─ detect_language_advanced + prompt build …… ~1 ms
 ├─ LLM ladder → _call_zai ……………………… 02:09:17.65→02:09:18.796 ≈ 1.15 s  (97% of wall time)
 ├─ order extraction (none) ……………………… <1 ms
 ├─ assistant msg + token_usage INSERT+flush ….. 02:09:18.798
 └─ get_db commit + response …………………… 02:09:18.80  → total 1.18 s
```
- Classifier (`app/ai/chat_classifier.py`) is **not** in the live reply path — it runs only inside the silent trainer cycle (per-conversation, 45 s cadence). Spam/work separation exists as `conversations.classification` (commerce/junk/mixed), written by the trainer, not at message time.
- LLM 45 s bound (`LLM_TOTAL_TIMEOUT_SECONDS`) never engaged (worst call 5.49 s).
- Trainer cadence observed: epochs 4–8 at 02:09:55, 02:11:25, 02:12:10, 02:13:40, 02:15:11 — each new batch of messages was classified + profile rebuilt **within ≤ 45 s** (16 s worst case in this run).

## 4. Persistence & history verification (read-only sqlite)

- All 9 customer messages + 9 replies persisted (28 messages total incl. prior traffic). Roles alternate customer/assistant; ordering strictly by `created_at` (microsecond precision), verified via GET detail — **ordering/roles/timestamps correct**.
- `messages.is_fallback`: 0 for all real replies, **1 for the 3 fallback apologies** (D, D2, E).
- Concurrency interleave (H/H2): `cust1 02:14:30.977976, cust2 02:14:30.978782, asst2 …32.877, asst1 …35.180` — both 200, **no "database is locked"**, WAL held up.
- Conversation-level classification after trainer epoch 8: `commerce`, score **43.55** (commerce 51.05 / junk 7.5, confidence 0.99), `classified_by=cc-2`. SPAM message itself triggered **no** junk signals (no URL in text; thread-level commerce dominates).

## 5. Style learner / silent trainer verification

- `tenants.training_state`: `st-2`, epoch 8, stage `learning`, maturity 0.33, `consecutive_errors: 0`, `next_attempt_at: null`.
- `knowledge_built_at` advanced on every rebuild (02:12:10 → 02:15:11).
- `tenants.style_profile`: full voice + buyer_persona + **exemplars (4 → 6)** + commerce_stats `{merchant_messages: 11, customer_messages: 11}` — exactly equals real (non-fallback, non-empty) messages. **The `is_fallback` filter works**: 3 canned apologies and 2 empty/whitespace customer turns were excluded from learning (14 assistant − 3 fallback = 11; 14 customer − 3 empty = 11).
- Invisible training triggers correctly: every new-message batch → `classified: 1, profiles_built: 1` in the next 45 s cycle, no errors in backend.log.

## 6. Failure modes & anomalies (detail)

1. **Bad `tenant_id` → 500** (unhandled `ValueError: badly formed hexadecimal UUID string`, `app/api/test_chat.py:28`; full ASGI traceback in backend.log — the only new ASGI exception in the audit window). Same pattern exists at `test_chat.py:119` (`/api/test/postiz-chat`).
2. **Empty/whitespace message accepted** → whole pipeline runs → Z.ai rejects (`400 {"error":{"code":"1213","message":"未正常接收到prompt参数。"}}`) → ladder falls to OpenRouter (no key) → canned apology persisted `is_fallback=1`, in **English** regardless of the Arabic conversation history.
3. **First empty-message call took 5.01 s** with an *untyped* provider failure: `Z.ai provider failed: ,` (empty exception string — likely an httpx connect-timeout; str(exc) is empty). Retry took 0.11 s (400 path). Observability gap: exception class is lost in the log line.
4. **10 KB message accepted** (no `max_length`) → prompt inflated to 10,730 tokens, 5.49 s reply latency, full 11,264-char row persisted. Cost/latency amplification is linear and unbounded.
5. **`tokens_used` attribution** — response field = *latest* `token_usage` row for the tenant, not this call's usage: stale on the fallback path (D/E reported 1614 while zero tokens were used) and racy under concurrency.
6. **Current-message duplication in LLM context (proven):** `db.add(customer_msg)` + `db.execute(history SELECT)` with `autoflush=True` (default of `async_sessionmaker`) flushes the current message *before* the history query; agent.py then appends the same message again → **the live customer message is sent to the LLM twice on every call**. Proof: (a) DB-copy experiment replicating steps 3–4 returned `DUPLICATED_CURRENT_MESSAGE_IN_HISTORY: True`; (b) token arithmetic — the 10 KB call's prompt (10,730) minus the follow-up emoji call's prompt (6,051) ≈ 4,679 ≈ exactly one extra copy of the 10 KB message.
7. **Product grounding absent → price hallucination:** `knowledge_bases` table is EMPTY, so `retrieve_context()` returns `("", "")` — the system prompt ships `## المنتجات` with an empty section (verified by rebuilding the real prompt on a DB copy). DB products: Air Max 90 White **1850**, Air Force 1 Black 1650, Running Pro V2 2200. The LLM repeatedly quoted "نايك اير ماكس **750** جنيه" and invented "بنسيون ب 680 جنيه". The prompt's "ممنوع تخترع أسعار" rule cannot work with zero catalog. (Retriever has no fallback to the `products` table.)
8. **Trainer trains on test/audit traffic:** my playground messages became style-profile exemplars within one cycle (see below) — no `test_*` PSID exclusion anywhere in the trainer.
9. **Concurrent messages cross-wire exemplar pairs:** `_extract_exemplars` pairs "previous customer msg → next merchant msg" assuming strict alternation; the interleaved H/H2 turns produced a corrupted pair — exemplar [4]: Q=`السعر بكام للبنسيون؟ اول رسالة` → A=`نعم عندنا نايك اير ماكس مقاس 43 ب 750 جنيه` (that was the reply to the *other* concurrent message).
10. **Hallucination feedback loop:** the wrong "750 جنيه" pair is now baked into `style_profile.exemplars` and is injected back into every future system prompt's few-shot section (`مشهد 1:`) — the agent is teaching itself its own hallucinated prices.
11. **Classifier lexicon false positive:** junk-family pattern `أهل` substring-matches the greeting `أهلاً` in the assistant's own replies → `family×3` junk signals fired in a purely commerce thread (each greeting adds +2.5 junk). No word boundaries in `chat_classifier._score_text`.
12. **Fallback apologies contaminate live LLM history** (not just training): the 3 English apologies are ordinary rows in the conversation, so subsequent calls include "Sorry, I'm unable to respond…" as assistant turns in the context (quality contamination; only the *trainer* filters is_fallback).

## 7. Findings register (severity · stage · issue · suggested fix — NOT implemented)

| # | Sev | Stage | Issue | Suggested fix |
|---|-----|-------|-------|---------------|
| F1 | **HIGH** | API validation | `tenant_id: "not-a-uuid"` → HTTP 500 + ASGI traceback (`test_chat.py:28`, also `:119`) | Type the field as `uuid.UUID` in `TestChatRequest` (pydantic → clean 422) |
| F2 | **HIGH** | API validation | Empty/whitespace `message` accepted → full LLM pipeline → guaranteed fallback apology persisted (English) into customer history | `message: str = Field(min_length=1)` + strip validator / 422 |
| F3 | **HIGH** | Retrieval/grounding | Zero product grounding in live prompt (no KB tree, no products-table fallback) → agent invents products & prices (750 vs 1850) | Retriever fallback: build `products_context` from `products` table when `knowledge_bases` empty (get_product_context already exists) |
| F4 | **MED** | LLM context build | Current customer message duplicated in every LLM call (autoflush before history query + explicit append) — double tokens for the newest turn, history window displaced by 1 | Load history *before* `db.add(customer_msg)` (or `db.flush()` after history load / `autoflush=False` + explicit flush ordering) |
| F5 | **MED** | API response | `tokens_used` = latest tenant token row → stale on fallback, racy under concurrency; `is_fallback` never exposed | Return the actual usage of *this* call (thread it out of `process_customer_message`) + add `is_fallback` to response |
| F6 | **MED** | Silent trainer | Test/playground traffic (PSID `test_{user.id}`) feeds merchant voice, buyer persona, exemplars — merchants pollute their own profile by testing | Filter `Customer.fb_psid LIKE 'test_%'` (or a `is_test` flag) in trainer queries |
| F7 | **MED** | Silent trainer | Concurrent/interleaved turns cross-wire exemplar Q→A pairs (proven pair [4]) | Pair by adjacency on both sides (reply must follow *its* customer msg with no other customer msg between), or skip interleaved windows |
| F8 | **MED** | Style learning | Hallucinated prices become few-shot exemplars → self-reinforcing wrong answers | Exemplar extraction only from *imported merchant* messages (source column), or validate exemplar prices against product catalog |
| F9 | **LOW-MED** | Observability | `Z.ai provider failed: ` — exception type lost (empty str, httpx timeout); 5 s failure undiagnosable from log | Log `repr(e)` / `type(e).__name__` in llm_client warnings |
| F10 | **LOW** | API validation | 10 KB message accepted → 10.7 K-token prompt, 5.5 s latency (unbounded) | `max_length` (e.g. 2–4 KB) on `message`; truncate long turns fed to history |
| F11 | **LOW** | Classifier | `أهلاً` matches junk "family" lexicon substring `أهل` (+2.5 junk per greeting) | Word-boundary regex or remove `أهل` bare token |
| F12 | **INFO** | Moderation | No per-message spam detection in the reply path (spam got a real LLM answer; classification is per-conversation, training-only) | Document/decide: moderation out of scope, or add message-level spam flag |
| F13 | **INFO** | LLM | Reported model `glm-4-plus` ≠ configured `glm-4.6` (API self-reports name) | Cosmetic — normalize if model accounting matters |
| F14 | **INFO** | Language | Emoji-only + empty messages → English reply/apology inside an Arabic conversation (detector default) | Default dialect from conversation history when detection is unsure |
| F15 | **INFO** | Test endpoint | `test_psid = test_{user.id}`: one eternal conversation/customer per owner; `customer_name` ignored after first creation (name stayed "محمود") | Intentional-ish for a playground; document |

Positive confirmations (no action): real LLM replies verified with per-call token_usage rows; classification/trainer state machine works (epochs, backoff fields clean, maturity checks honest); `is_fallback` filter + empty-content filter exclude exactly the 3 fallback apologies; conversation detail ordering/roles/timestamps correct; WAL survives concurrent writes with no lock errors; LLM 45 s bound in place; reply latency ~0.9–1.2 s nominal; GET endpoints 7 ms.

## 8. Related prior findings (referenced, not re-reported)

- E5: chat page frontend is 100 % mock (setTimeout) — excluded per instructions.
- E1 F2: `/api/test/chat` unthrottled (LLM POST cost amplification) — confirmed again by this audit (9 calls, no 429).
- E8: `token_usage` DDL drift; E2: fetchWithHeal re-POST duplication risk on slow (5 s+) chat calls — the 10 KB case (5.49 s) makes that path reachable.
