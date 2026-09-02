# Task 18-e — Recently-Shipped Features Audit: Channels + Scheduler + Self-Training Agent

**Commits audited:** `5d51ba0` "Real channels + real scheduler + calendar subscription" (+1,774/−23, 19 files) and `af12900` "e066c0e6…" (+1,683/−21, 14 files).
**Scope:** research only — zero code modified. Every claim below is traced to file:line or to live runtime evidence (`repos/zemest/backend.log`, task 18-b live smoke test, task 18-a E2E wiring test).
**Spec under test:**

1. REAL channel connections via real OAuth/Meta flow (token exchange, page selection, webhook subscription) — NOT mock buttons.
2. Platform-built scheduler: schedule posts, best-time suggestions, calendar subscription (Google/ICS feed).
3. INVISIBLE self-training agent: classify spam/friend-chatter vs work chats, train only on work chats, auto-resume after crash until "perfect", per-page dialect learning, zero customer-facing visibility.
4. (Bonus scope) Webhook inbound correctness: X-Hub-Signature-256 verification + replies using the trained style.

---

## 1. CHANNELS — verdict: PARTIAL (live validation is REAL; OAuth is NOT real)

### 1.1 What actually shipped (all real)

| Piece | Evidence |
|---|---|
| Live Graph validation before storing anything | `app/api/channels.py:72-96` `_graph_get()` — real `httpx` GET to `{GRAPH}/{path}` (graph.facebook.com v21.0, `config.py:41`), 12s timeout, real Graph error surfaced verbatim as HTTP 400 |
| Messenger connect | `channels.py:194-243` — resolves Page via `/me` with the page token, then `subscribe_page_to_webhook()` (REAL POST `{page_id}/subscribed_apps` with `messages,message_deliveries,message_echoes,message_reads,messaging_postbacks,standby` — `services/facebook_service.py:30-64`), persists `fb_page_id/page_access_token/messenger_meta` |
| Instagram connect | `channels.py:250-274` — validates IG user live (`username,profile_picture_url,followers_count`), stores `ig_user_id/ig_access_token` |
| WhatsApp connect | `channels.py:281-311` — validates `phone_number_id` live (`display_phone_number,verified_name,quality_rating`), stores `wa_*` columns |
| Disconnect / test | `channels.py:318-397` — real deletion of creds; test messages send through the REAL platform API (`messenger_service.send_text_message` → POST `/me/messages`; `whatsapp_service.send_whatsapp_message` → POST `/{phone_number_id}/messages`) |
| Live status w/ revocation detection | `channels.py:107-187` — every status GET re-validates all three tokens against Graph; revoked token shows `connected:false` + the real Graph error |
| Frontend | `src/app/dashboard/[tenantId]/channels/page.tsx` — 3 connect cards wired to the real endpoints (`channelsApi` in `src/lib/zemest-api.ts:398-419`), webhook URL copy card, honest failure toasts carrying Meta's own error text |

There is **no mock anywhere** in this path: an invalid token returns Meta's actual Graph error, and a valid one returns live page/IG/WA profile data. The commit message's "LIVE Graph API validation before storing anything" is accurate.

### 1.2 What did NOT ship (the OAuth half of the spec)

| Missing piece | Evidence |
|---|---|
| **Token exchange endpoint** | Repo-wide grep for `oauth/access_token`, `fb_exchange_token`, `exchange.*code` → **zero matches**. No code→token exchange exists anywhere (backend or BFF). |
| **OAuth callback route** | `channels.py:404-436` builds a consent URL whose `redirect_uri` is `{frontend}/api/zemest/facebook/oauth/callback` — **that route does not exist** (BFF catch-all would proxy to backend `/api/facebook/oauth/callback`, which also doesn't exist → 404). Task 18-a E2E-confirmed the sibling `/api/auth/facebook/callback` also 404s. |
| **Frontend use of OAuth** | `channelsApi` (zemest-api.ts:398-419) has no `oauth-url` call; grep for `oauth-url|oauth_url` in `src/` → **zero matches**. The channels page only renders manual token+ID forms (`page.tsx:362-387`). The `GET /api/tenants/{id}/channels/oauth-url` endpoint is dead code. |
| **Page selection** | No page picker. Connect resolves the page from the token via `/me` or a manually typed Page ID. `GET /api/facebook/pages` (real `/me/accounts` call, `api/facebook.py:11-18`) exists but has **zero frontend callers** and takes the user token in a query string (log-leak vector, Z5). |
| **Token lifecycle** | No long-lived exchange, no refresh, no proactive expiry handling — tokens are stored exactly as pasted; expiry only *detected* on the next status read. |
| **IG/WA webhook subscription at connect** | `subscribe_instagram_to_webhook()` exists (`facebook_service.py:67-95`) but is **never called** anywhere — `connect_instagram()` does not subscribe. WA connect stores `waba_id` but never uses it to subscribe the WABA. Users must wire webhooks manually in the Meta dashboard (the channels page's webhook card does document this). |
| **Token storage hygiene** | `page_access_token/ig_access_token/wa_access_token` stored **plaintext** in `tenants` (models/tenant.py:20,29,33). |

**Net:** connect = *manual paste of a Page/IG/WA token, validated live*. That is a real, working, non-mock integration — but it is NOT the "real OAuth/Meta flow (token exchange, page selection)" the spec demanded. The OAuth scaffolding that does exist (consent-URL builder with proper scopes incl. `pages_messaging`, `instagram_manage_messages`) is unwired on both ends.

### 1.3 Old `/api/facebook/*` endpoints (pre-existing, untouched by 5d51ba0)

`repos/zemest/daemon_backend.py` is only the double-fork uvicorn launcher (no API logic — the task brief's "daemon_backend.py /api/facebook/connect" actually lives in `app/api/facebook.py`): `GET /api/facebook/pages` (real, unused), `POST /api/facebook/connect` (real webhook subscribe + tenant creation, but takes credentials as **query params** and does NOT live-validate the token before subscribing — inferior to the new channels.py flow), `POST /{tenant_id}/sync-catalog` (real catalog import). The new unified channels API supersedes it; the old route remains mounted (router.py) — a redundancy to clean up.

---

## 2. SCHEDULER — verdict: REAL (in-process worker, DB-persisted, real publishing) with crash-safety gaps

### 2.1 Dispatch mechanism

- `app/tasks/inline_worker.py` — an **asyncio background task inside the uvicorn process**, 30s cycle, started in `app/main.py:287-292` at import time, stopped cleanly on shutdown (`main.py:196-199`). Enabled by `SCHEDULER_INLINE_WORKER` (default on, `config.py:67`).
- Each cycle calls `_publish_due_posts_async()` (`app/tasks/scheduling_tasks.py:30-84`) — the *exact same code path* as the Celery beat task, so inline vs Celery deployments behave identically (Celery wiring exists but is unused here; docstring warns to disable inline if Celery beat is deployed).
- Publishing is **real Graph API**: `app/scheduling/facebook_publisher.py` (`publish_feed_post/publish_photo/publish_video`) and `instagram_publisher.py` (`publish_image/publish_reel/publish_story`), dispatched per `media_type` in `scheduling_tasks.py:87-190`.
- **Runtime evidence** (backend.log): `"Scheduler worker: {'published': 0, 'failed': 1, 'total': 1}"` + `"Failed to publish post 5bef59b7…: Facebook Page not connected"` — the worker runs, finds due posts, attempts real publishes, and records genuine Graph-side/credential errors on the post row.

### 2.2 Persistence across restart

Pending jobs are rows in `scheduled_posts` (`status='scheduled'`, `scheduled_at`), so **everything survives a restart** — the worker re-scans on boot (5s boot delay to let migrations finish). No in-memory queue is authoritative. ✔

### 2.3 Scheduling API

`app/api/scheduling.py` — schedule/list/cancel/delete + AI caption generation (`/schedule/generate-caption`, uses tenant style profile) + insights. The 5d51ba0 fix normalizes offset-aware ISO → naive UTC (`scheduling.py:80-84`) — the advertised 500-fix is real and correctly placed before the future-time check.

### 2.4 Best-time suggestions

`GET /insights/best-time` (`scheduling.py:375-396` → `instagram_publisher.get_best_time_to_post`, lines 275-320) is a **real** IG `online_followers` heatmap + top-5 slots computation. **But:** it is IG-only (no Facebook equivalent), and the scheduler frontend never calls it (grep of scheduler page for `best|insights|suggest` → zero; `schedulerApi` has no best-time method). Suggestions exist in the backend, absent in the product.

### 2.5 Calendar subscription

- `app/api/calendar.py` — real token-authenticated ICS: `GET /api/calendar/{token}/calendar.ics` returns `text/calendar; charset=utf-8`, CRLF line endings, escaped text, VEVENTs with UID/DTSTART/DTEND/STATUS, per-tenant `X-WR-CALNAME`; token creation + rotation (`POST …/calendar/token`) with `secrets.token_urlsafe(24)`; `tenants.calendar_token` column (unique, indexed) + idempotent startup migration (`main.py:75`).
- Public BFF proxy `src/app/api/calendar/[token]/route.ts` (token-format validated, `no-store`, passes through Content-Type) — task 18-a E2E-verified 200 on a real token / 404 on bad.
- Frontend scheduler page: ICS copy link, **Add to Google** (`calendar.google.com/calendar/render?cid=`), **Apple webcal://**, rotate token. ✔ REAL end-to-end.

### 2.6 Scheduler gaps

1. **Stuck `publishing` state has no recovery.** The due-query only selects `status='scheduled'` (`scheduling_tasks.py:36-39`); a crash after the `status='publishing'` commit (line 51-52) but before the result commit leaves the post **stuck in `publishing` forever** — invisible to every subsequent cycle and shown as "publishing" in the UI eternally.
2. **Failed posts never retry.** `retry_count` is incremented (`scheduling_tasks.py:74`) but no code path ever requeues a `failed` post — single-shot, terminal.
3. 30s cadence → publishes up to ~30s late (acceptable, by design).
4. Worker startup uses `asyncio.get_event_loop().create_task()` **at module import time** (`inline_worker.py:59`, `training_worker.py:71`). It works under `uvicorn app.main:app` (uvicorn imports the app *inside* its running loop — verified by backend.log) but is fragile/deprecated (Python 3.12) and would break or duplicate under gunicorn multi-worker; double-publish risk vs Celery beat is only a docstring warning, not a lock.
5. ICS feed has no time window (past events included, 500-post cap, `STATUS:CANCELLED` branch is dead code since cancelled posts are excluded from the query).
6. Rate-limit fix shipped in the same commit is real: `_build_limiter()` probes Redis **once** with a 1s timeout and permanently falls back to `memory://` (`middleware/rate_limit.py:96-119`) — the login-500 fix is genuine.

---

## 3. SELF-TRAINING AGENT — verdict: REAL (surprisingly complete), with a broken import on-ramp and one contamination bug

Files: `app/ai/silent_trainer.py` (597L), `app/ai/chat_classifier.py` (251L), `app/tasks/training_worker.py`, `app/ai/prompts.py`, `app/models/{tenant,conversation}.py`, `tests/test_silent_trainer.py` (336L).

### (a) Spam vs work classification — IMPLEMENTED (heuristics, not LLM)

`chat_classifier.py` — pure-CPU regex/lexicon scorer, microseconds per thread:
- COMMERCE lexicon (price/availability/delivery/address/payment/size/order-intent/confirmation/product — Egyptian Arabic + Arabizi + English, weighted 1.0–3.0), JUNK lexicon (family/social plans/football/check-ins/forwarded memes).
- Structural signals: Egyptian phone regex `01[0125]\d{8}`, currency amounts, laughter-only regex, link-only messages, merchant participation multiplier (1.3×), meme-thread and short-no-commerce adjustments.
- Decision: `margin = commerce − junk`; `≥2.5 → commerce`, `≤−2.5 → junk`, else `mixed`. Explainable signal list persisted on the conversation row (`classification_signals`).
- Training-set rule `is_commerce()` (`chat_classifier.py:239-251`): `mixed` included when `score ≥ −1.0` (Egyptian threads mix small-talk with real orders).

**No LLM is used for classification** (deliberate: "cheap by design"). LLM appears only as *optional* style enrichment (`silent_trainer.py:327-334`, silently skipped without OPENROUTER_API_KEY). Tests (`tests/test_silent_trainer.py`) cover commerce/junk/mixed/franco threads with Arabic fixtures. Egyptian-Arabic-tuned — English/other locales rely on a much thinner lexicon.

### (b) Crash-resume — IMPLEMENTED (checkpoints + backoff + platform-level revival)

- **Granular commits:** every 25 classifications (`CLASSIFY_BATCH_COMMIT`, `silent_trainer.py:256-258`) — a crash loses at most a handful.
- **Watermark:** `classified_at = max(now, last_message_at)` + `classified_by` version (`silent_trainer.py:242-249`); the pending query re-processes only new/changed/older-classifier-version threads (`silent_trainer.py:215-225`).
- **State machine in DB:** `tenants.training_state` JSON (version, stage, maturity, epochs, profile_signature, consecutive_errors, next_attempt_at, stats) — committed on every cycle; survives process death.
- **Self-heal:** per-tenant exponential backoff (5min → 240min, auto-reset on first success, `_record_error`, `silent_trainer.py:559-580`); the worker loop itself is wrapped so one bad cycle never kills it (`training_worker.py:44-58`); whole-backend death is covered by the platform's `fetchWithHeal` daemon revival.
- **"Until perfect":** maturity = 6 weighted checks (conversations≥5, commerce≥2, merchant msgs≥25, customer msgs≥20, exemplars≥4, epoch) / `MATURE_THRESHOLD=0.75` → stage `warming → learning → mature` (`_finalize`, lines 514-548); mature tenants throttle to a 10-min maintenance cadence but still ingest every new message.
- **Runtime evidence:** backend.log — `"Silent trainer: tenant 1f8c6249… epoch 6 — 8 convs (6 commerce / 2 junk), maturity 0.83, stage mature"`. It runs, classifies, and converges in production.

### (c) Triggering — AUTOMATIC (interval), not import-hooked

- `training_worker.py`: asyncio loop, **every 45s**, started at app import (`main.py:296-301`), own DB session per cycle, `SILENT_TRAINER_INLINE_WORKER` toggle.
- No direct hook on chat import — but the interval covers any import/webhook message within ~45s. (The import endpoint itself currently 500s — see gaps.)
- A *separate, older* manual path also exists: `POST /rebuild-style` (`api/style_learning.py:153-169`, legacy style_learner). The spec's "never manual-only" bar is cleared — the trainer is fully automatic.

### (d) Per-page dialect/style learning — IMPLEMENTED

Per-tenant `tenants.style_profile` rebuilt from **commerce-only** conversations:
- **Merchant voice:** greeting/signoff patterns, tone, formality 1-10, emoji frequency+inventory, avg length chars, language mix, vocabulary (reuses `style_learner.extract_heuristic_features`), drift-resistant smoothing 0.7/0.3 on numerics across epochs (`silent_trainer.py:475-511`).
- **Buyer persona** (`_extract_buyer_persona`, lines 358-402): language mix + **Arabic dialect distribution** (via `detect_language_advanced`), arabizi/franco ratio, avg message length, question rate, top opening lines, emoji inventory — i.e. the page's *buyers'* dialect is learned per page.
- **Exemplar pairs:** real (customer question → page reply) few-shot anchors, scored, deduped, capped at 6 (`_extract_exemplars`, lines 405-442).
- **Cold start for low-volume pages:** seeded Egyptian-seller voice + empty persona until ≥6 merchant messages (`_seed_voice`/`_seed_profile`).
- **It reaches the live reply path:** `agent.py:125-136` passes `tenant.style_profile` into `get_system_prompt`, and `prompts.py:113-193` renders style lines, buyer persona ("عملاء الصفحة"), and exemplar few-shots into the system prompt. `scripts/verify_live_prompt.py` asserts end-to-end that the learned greeting/exemplars/persona appear in the real prompt built from the live DB tenant.
- Webhook replies therefore DO use the trained style (see §4).

### (e) Invisibility — MOSTLY HELD

- No dashboard page, no nav item, no API route added for the trainer; `conversations.py` does **not** expose classification fields; `training_state` is only written by the background loop. The only traces are backend log lines (operator-facing).
- Two leaks: (1) `GET /style-profile` returns the full profile **including the `silent_training` block (stage/maturity/epochs)** — no frontend caller today (style page is "Coming soon" per 18-a), but the machinery is one fetch away from user eyes. (2) The marketing **pricing FAQ still says "upload your chat history. The agent trains on your phrasing, slang, emoji use, and response patterns"** (`src/app/pricing/page.tsx:381`) — commit b25c9f9 ("drop trained-on-chats copy") cleaned hero/CTA/use-cases/solutions but missed pricing. (The models page's "Trained on millions of Arabic commerce conversations" is a base-model claim, not the self-trainer — acceptable.)

### 3.1 Self-training gaps

1. **The import on-ramp is broken:** `POST /import/chat-history` → 500 — `style_learner.py:455-458` creates `Conversation(customer_id=None)` against a NOT-NULL FK. Live-verified by task 18-b. So "reads dashboard chat history" currently only works for chats that arrive via webhooks/test-chat/seeds; the DYI/WhatsApp-upload path (the richest source) cannot even land in the DB.
2. **Self-contamination:** when the LLM key is absent/failing, the agent's canned apologies ("Sorry, I'm unable to respond…") are **persisted as `assistant` messages**, and both `style_learner.collect_merchant_messages` (`role IN ('assistant','merchant')`, style_learner.py:63) and the silent trainer (`role in ('merchant','assistant')`, silent_trainer.py:309) treat them as the page's voice. Task 18-b found the live profile vocabulary polluted with "sorry/try/unable/moment". This directly violates "trains ONLY on work chats" in spirit — it trains on its own failure noise.
3. **Dual style pipelines with different filtering rules:** the import/manual path (`style_learner.build_and_persist_personality`) builds from ALL merchant messages (no junk filter), the silent trainer rebuilds commerce-only up to 45s later. Between import and the next trainer epoch, replies can use a junk-contaminated profile; and `rebuild-style` can regress the profile the trainer just fixed.
4. Classification is heuristic-only, Egyptian-Arabic-tuned; borderline/English threads score on a thin lexicon; no confidence gate for "leave unclassified" (empty threads default to junk, fine).
5. `MAX_CONVS_PER_CYCLE=400` and `MAX_MSGS_FOR_PROFILE=4000` caps — large histories converge over multiple epochs (signature-change detection), acceptable, but no metric exposes backlog.

---

## 4. WEBHOOKS — verdict: REAL (fail-closed HMAC + real trained-style replies)

`app/api/webhook.py` + `app/utils/security.py:254-270`:

- **X-Hub-Signature-256 verified on all three POST routes** (`/api/webhook/messenger|instagram|whatsapp`), HMAC-SHA256 with `FB_APP_SECRET`, `hmac.compare_digest`, **fail-closed** when the secret or signature is missing (logged, 403). ✔
- **GET verification challenge** handled on all three (`hub.mode/hub.verify_token/hub.challenge` → echoes challenge). Uses `FB_VERIFY_TOKEN`, whose default is the shipped constant `"zemest-verify-token"` (`config.py:40`) — works, but guessable if never changed.
- **Inbound messages are actually processed and answered:** each event → background task → tenant lookup (by fb_page_id / ig_user_id / wa_phone_number_id) → `mark_seen`/`typing_on` → `agent.process_customer_message(...)` (which loads the trained `style_profile` and dialect) → **real send** via Graph `/me/messages` (Messenger/IG) or WA Cloud `/messages`. Echo events skipped; Meta retry dedup via the `"duplicate"` reply sentinel; owner messages routed to the owner-chat flow; postbacks handled; IG story-reply/media/audio and WA text/image/audio/video/document/interactive parsed.
- Instagram lookup falls back to `fb_page_id` if `ig_user_id` misses; IG token falls back to page token — pragmatic.
- Minor: IG verify endpoint returns `media_type="text_plain"` (typo, should be `text/plain`) — `webhook.py:280`. WA media: only Graph **media IDs** are captured, never resolved to URLs (no `GET /{media_id}` call) — the agent receives placeholder text, no real image/voice understanding on WA. Dedup relies on SELECT-then-insert (no unique constraint on `fb_message_id` — Z2) → duplicate replies/orders under Meta's retry race.

---

## 5. GAP TABLE — SPEC vs IMPLEMENTATION

| # | Feature | Spec item | Implementation reality | Severity |
|---|---|---|---|---|
| 1 | Channels | OAuth token exchange (code→token) | No exchange endpoint anywhere (grep: 0 hits); connect = manual token paste w/ live validation | **CRITICAL** (spec-level: the "real OAuth/Meta flow" does not exist; the rest of the connect flow is genuinely real) |
| 2 | Channels | OAuth callback + page selection | `oauth-url` endpoint dead: frontend never calls it; `/api/zemest/facebook/oauth/callback` route doesn't exist (404); no page picker; `/api/facebook/pages` unused (token in query string) | **CRITICAL** (same flow) |
| 3 | Self-training | Reads dashboard/imported chat history | `POST /import/chat-history` 500s (`customer_id=None` vs NOT-NULL FK, style_learner.py:455) — the biggest data source can't even be ingested | **CRITICAL** (live-verified) |
| 4 | Self-training | Trains only on work chats | Canned LLM-fallback apologies persisted as `assistant` msgs are trained on as the page's voice — profile contamination observed live | **HIGH** |
| 5 | Webhooks | Correct inbound handling | fb_message_id dedup is SELECT-then-insert, no unique constraint → Meta retry race duplicates replies/orders | **HIGH** (pre-existing, Z2) |
| 6 | Scheduler | Dispatch survives crashes | Posts stuck in `publishing` after a mid-publish crash are never requeued (query only scans `scheduled`); failed posts never retried (`retry_count` unused) | **HIGH** |
| 7 | Channels | Webhook subscription on connect | IG connect never calls `subscribe_instagram_to_webhook()` (dead code); WA never subscribes WABA (manual Meta-dashboard step) | **HIGH** (IG DMs won't flow despite "connected") |
| 8 | Channels | Token security | Page/IG/WA tokens stored plaintext in `tenants`; old `/api/facebook/*` passes tokens in query strings; no refresh/expiry handling beyond detect-on-read | MED |
| 9 | Scheduler | Best-time suggestions | Backend real (IG `online_followers` heatmap, `/insights/best-time`) but IG-only and zero frontend callers — invisible to users | MED |
| 10 | Scheduler | Worker robustness | `asyncio.get_event_loop().create_task()` at import time — works under uvicorn (log-verified) but deprecated/fragile; no leader lock (double-publish risk if Celery beat also enabled) | MED |
| 11 | Self-training | Single silent pipeline | Two style pipelines (manual `style_learner` vs silent trainer) with different junk-filtering rules; `rebuild-style` can regress trainer output; import briefly trains on ALL msgs | MED |
| 12 | Self-training | Invisibility | `/style-profile` API exposes `silent_training` (stage/maturity); pricing FAQ still advertises "trains on your phrasing…" (b25c9f9 missed pricing) | MED |
| 13 | Channels | Status performance | 3 sequential live Graph calls per status refresh, new httpx client each, zero cache (18-c) | MED |
| 14 | Webhooks | WA media | WA inbound media captured as Graph media IDs only — never resolved/downloaded; agent sees placeholders | MED |
| 15 | Webhooks | Verify-token hygiene | Default `FB_VERIFY_TOKEN="zemest-verify-token"` shipped; no prod guard (unlike JWT secret guard in main.py) | MED |
| 16 | Self-training | Classifier scope | Heuristic-only, Egyptian-Arabic lexicon; thin for English/other locales; no LLM assist for borderline | MED (by design for cost) |
| 17 | Scheduler | ICS polish | No time window (past events included), 500-cap, dead CANCELLED branch | LOW |
| 18 | Channels | OAuth URL details | `oauth-url` default `request_url="https://localhost:3000"`; `state` unsigned (moot until callback exists) | LOW |
| 19 | Webhooks | IG verify response | `media_type="text_plain"` typo | LOW |
| 20 | Ops | Env docs | `.env.example` documents `SCHEDULER_INLINE_WORKER` but not `SILENT_TRAINER_INLINE_WORKER` | LOW |
| 21 | Channels | Legacy duplication | Old `/api/facebook/connect|pages` still mounted alongside the superior channels API | LOW |

**What is genuinely, verifiably REAL:** live Graph validation on every connect/status; real Messenger webhook subscription at connect; real test messages through all three platforms; real publishing via Graph at the scheduled minute (log-proven); DB-persisted pending posts; real ICS feed + rotation + Google/Apple links; fail-closed HMAC on all webhook POSTs; a complete, crash-resumable, invisible-per-tensor self-training loop (classifier → commerce-only profile → per-page dialect/buyer persona/exemplars → live reply prompt) proven running in backend.log with maturity 0.83/stage mature.

---

## 6. RANKED FIX PLAN (backend-focused, no UI/design changes)

1. **Finish the OAuth loop (backend, ~150 LOC):** add `GET /api/facebook/oauth/callback` — validate `state` (tenant binding, signed), exchange `code` via `POST {GRAPH}/v21.0/oauth/access_token` (client_id, redirect_uri, client_secret, code), upgrade short→long-lived token, `GET /me/accounts?fields=id,name,access_token` for **page selection** (return list; store chosen page token via the existing channels connect). Add the BFF pass-through (already structurally possible via `/api/zemest/[...path]`). Then wire the frontend Connect button to the existing `oauth-url` endpoint when `ready:true` (currently manual-paste fallback is correct behavior when FB_APP_ID is unset). Kill the legacy `/api/facebook/connect` (query-string credentials) afterwards.
2. **Fix the import 500 (one-line-ish, unblocks the trainer's main data source):** create a `Customer` per thread before inserting the `Conversation` (or make `customer_id` nullable) — `style_learner.py:445-470`. Re-run task 18-b's ZIP import test to confirm.
3. **Stop training on the agent's own fallback noise:** (a) don't persist canned apology replies as `assistant` messages (or tag them `system`/`fallback`), and (b) exclude fallback-marker messages from merchant-voice extraction in both `style_learner.collect_merchant_messages` and `silent_trainer._rebuild_profile`. This restores the "trains ONLY on work chats" contract under LLM outages.
4. **Webhook idempotency:** unique index on `messages.fb_message_id` + insert-ignore (SQLite `OR IGNORE` / PG `ON CONFLICT DO NOTHING`); keep the `"duplicate"` sentinel as a second layer. Kills the Meta-retry duplicate-reply/order race.
5. **Scheduler crash-safety:** on each cycle (and at startup), requeue posts stuck in `publishing` for >5 min (verify against `platform_post_id` first to avoid double-publish); add bounded retry (≤3 attempts, backoff via the already-existing `retry_count` column) before terminal `failed`.
6. **Subscribe on connect for IG/WA:** call the already-written `subscribe_instagram_to_webhook()` in `connect_instagram`; subscribe the WABA (`/{waba_id}/subscribed_apps`) in `connect_whatsapp` when `waba_id` is supplied. Report the result honestly like Messenger does (`webhook_subscribed` field).
7. **Token hygiene:** encrypt channel tokens at rest (Fernet, key from env), never echo them in responses, add a scheduled expiry probe (code 190 detection already exists in `messenger_service`) → mark channel errored + notify owner instead of waiting for the next status read.
8. **Harden worker startup:** move `start_inline_scheduler`/`start_inline_trainer` into the FastAPI `lifespan` using `asyncio.get_running_loop()`; add a DB- or Redis-based leader lock so multi-worker deployments can't double-publish/double-train; document the Celery-vs-inline interplay in `.env.example` (also add the missing `SILENT_TRAINER_INLINE_WORKER` line).
9. **Close the classifier/contamination seam:** make `import_messages_and_build_style` either skip profile building entirely (let the 45s trainer own it) or apply `is_commerce()` filtering — one source of truth for `style_profile`; strip `silent_training` from the public `/style-profile` response.
10. **WA media resolution + small webhook fixes:** resolve WA media IDs to URLs (`GET /{media_id}?access_token=…`) before handing to the agent; fix the `text_plain` typo; require a non-default `FB_VERIFY_TOKEN` when `APP_ENV=production` (mirror the JWT-secret guard).
11. **Best-time (backend part):** add a Facebook best-time derivation (page post engagement insights) alongside the IG heatmap so the endpoint is useful for FB-only tenants — surfacing it in the composer is a frontend task for another workstream.
12. **Copy leak:** delete/reword the pricing FAQ "agent trains on your phrasing…" sentence (one line; keeps the invisibility contract airtight).

Items 2, 3, 4, 5, 6 are small, surgical backend changes with immediate correctness payoff; item 1 is the only substantial build and is the one that closes the last CRITICAL gap between spec and shipped product.
