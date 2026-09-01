# Z8 — Channel Services 2 (Facebook / Messenger / WhatsApp / Notifications / Transcription / Vision / Importers)

Scope: `app/services/facebook_service.py`, `messenger_service.py`, `whatsapp_service.py`, `notification_service.py`, `transcription.py`, `vision.py`, `app/services/importers/{__init__.py, messenger_dyi.py, whatsapp_export.py}` — every line read; every call site cross-verified via grep (webhook.py, agent.py, facebook.py, style_learning.py, notification_tasks.py, crawl_tasks.py, tests).

Context facts verified:
- Graph API base: `settings.FB_GRAPH_API_URL` = `https://graph.facebook.com/v21.0` (config.py:41), README:277 confirms.
- WhatsApp base: **hardcoded** `https://graph.facebook.com/v21.0` (whatsapp_service.py:9) — does NOT use the setting.
- SMTP: aiosmtplib==3.0.2 in requirements.txt:63; faster-whisper>=1.0.0 at requirements.txt:38.
- Tenant channel fields: `fb_page_id/page_access_token/owner_psid/ig_user_id/ig_access_token/wa_phone_number_id/wa_access_token/wa_waba_id` (models/tenant.py:18-34). **None of the IG/WA/owner_psid fields has any write path** (schemas/tenant.py TenantCreate:8-29 / TenantUpdate:32-44 exclude them; no API endpoint assigns them).

---

## 1. Facebook service — `app/services/facebook_service.py` (127 lines, 4 functions)

All functions: new `httpx.AsyncClient` per call (no pooling), 10s timeout, access token passed as **query parameter**, errors swallowed (return `[]`/`False` after logging).

| Function | Graph call | Behavior |
|---|---|---|
| `get_user_pages(user_access_token)` | `GET /me/accounts?fields=id,name,access_token` | Returns raw page list **including each page's page access_token**. 200→`data`, else `[]`. No pagination (`limit`/`after` cursor ignored — >~25 pages truncated). Called by `GET /api/facebook/pages` (facebook.py:17), token itself arrives as a query param on that endpoint. |
| `subscribe_page_to_webhook(page_id, page_access_token)` | `POST /{page_id}/subscribed_apps` body `{"subscribed_fields": [...]}` | Subscribes 6 fields: `messages, message_deliveries, message_echoes, message_reads, messaging_postbacks, standby` (docstring says "matching Chatwoot"). Returns bool; logs failure with body text. Called by `POST /api/facebook/connect` (facebook.py:33) before tenant creation — note: tenant row is created **even though** subscription is required to succeed first (HTTP 400 if it fails). |
| `subscribe_instagram_to_webhook(ig_user_id, access_token)` | `POST /{ig_user_id}/subscribed_apps` | IG fields: `messages, message_reactions, messaging_seen`. **DEAD CODE — zero call sites** (grep across repo). No endpoint ever subscribes an IG account, and `ig_user_id` has no write path, so the IG webhook branch (webhook.py:361) can only match a manually seeded tenant. |
| `get_page_products(page_id, page_access_token)` | `GET /{page_id}/product_catalogs` → first catalog → `GET /{catalog_id}/products?fields=id,name,description,price,image_url,availability` | Two chained calls. Only **first catalog** and **first page of results** (no pagination) — large shops silently truncated. `KeyError` on malformed catalog caught by blanket `except`. Called by `POST /api/facebook/{tenant_id}/sync-catalog` (facebook.py:64); price string parsed as `split(" ")[0]` for "100.00 EGP" format. |

Token handling: page tokens flow user→(frontend)→`/connect`→DB (plaintext Text column). No `debug_token` validation, no expiry tracking, no refresh. Auth failures on this module are silent (`[]`).

API version risk: v21.0 (Oct 2024) has a 2-year minimum lifetime → EOL ~Jan 2026; the repo's own migrations run to 2026-08 (per Z1), so this base URL is **already past guaranteed support** at the codebase's stated point in time.

---

## 2. Messenger service — `app/services/messenger_service.py` (221 lines, 10 functions)

Single Graph endpoint family: `POST {FB_GRAPH_API_URL}/me/messages` (works for both Messenger PSIDs and Instagram IGSIDs — Meta unified Send API; the IG webhook path uses `token = tenant.ig_access_token or tenant.page_access_token`, webhook.py:378).

**Sender actions**
- `send_sender_action(token, recipient_id, action)` — POST `{recipient:{id}, sender_action}`; 5s timeout; returns `bool` (status==200 only, body never inspected).
- `typing_on` / `typing_off` / `mark_seen` — one-line wrappers. All three are the live typing-indicator lifecycle used around every agent reply (webhook.py:140-141,168,382-400).

**Text**
- `send_text_message(token, recipient_id, text, messaging_type="RESPONSE", tag=None)` — POST with `message.text`; supports `MESSAGE_TAG` + `tag` for the >24h window (only caller passes defaults, so the 24h-window escape hatch is wired but unused). Error handling is the best in the codebase: parses `error.code`; codes **190** (invalid/expired OAuth token) and **10** (permission denied / not the page) → `logger.error("AUTH ERROR…")` and injects `data["_auth_error"]=True`, which webhook.py:162 checks to log page-token expiry. Maps `message_id` → `data["_source_id"]` (never consumed by any caller — dead convenience). `httpx.TimeoutException` → `{}`; other exceptions → `{}`. Returns the full Meta response dict.
- Rate-limit awareness: none (no code 4/6130/6141 handling, no retry/backoff).

**Quick replies**
- `send_quick_replies(token, recipient_id, text, options)` — builds `quick_replies` `content_type:text`, `title == payload == option`, hard cap 13 (`options[:13]`, matches Meta's limit). `messaging_type` fixed "RESPONSE". **Dead code — no callers** (grep: only self-references). No error-code analysis (raw json returned), no timeout specialization.

**Attachments**
- `send_attachment(token, recipient_id, attachment_type, url)` — **URL-based only** (no multipart file upload API). Type whitelist `{image, audio, video, file}`, anything else silently coerced to `"file"`. Same 190/10 auth-error detection as text. `send_image` / `send_audio` thin wrappers — **both dead code** (no callers).

**Profile**
- `get_user_profile(token, psid)` — `GET /{psid}?fields=first_name,last_name,profile_pic`. **Dead code** — customer names in the live pipeline come from the webhook payload (`contacts[].profile.name` for WA) or default "عميل" (agent.py:290); the Messenger path never enriches customer names.

**Attachment downloads**: this module does NOT download inbound attachments. Inbound Messenger attachment URLs are taken verbatim from the webhook payload (webhook.py:108) and fed to transcription/vision. There is no Messenger attachment-download-with-token helper (CDN URLs are pre-signed, so it works).

Live call graph (Messenger): `mark_seen → typing_on → process_customer_message → send_text_message → typing_off`; postbacks (webhook.py:251-261) reuse `send_text_message`. Instagram: same trio + text send (webhook.py:374-398).

---

## 3. WhatsApp service — `app/services/whatsapp_service.py` (38 lines, 1 function)

- `send_whatsapp_message(tenant, recipient_id, text) -> bool` — WhatsApp Cloud API `POST {WHATSAPP_API_URL}/{tenant.wa_phone_number_id}/messages` with `Authorization: Bearer {tenant.wa_access_token}` (correctly a header — the only channel service that does NOT leak the token in the URL). Body: `{"messaging_product":"whatsapp","to":recipient_id,"type":"text","text":{"body":text}}`.
- **Version hardcoded** `v21.0` (line 9), independent of `settings.FB_GRAPH_API_URL` → version drift risk (config change fixes FB/WA for other modules, this stays stale; and vice-versa).
- Guards: missing `wa_access_token` → warn + False. Non-200 → warn with body + False. Exception → error + False.
- Recipient/phone handling: `recipient_id` is the raw MSISDN digits from the webhook `from` field (e.g. `201001234567`), passed through verbatim — correct for Cloud API, no Egyptian normalization needed on send (Egyptian-number validation for *orders* lives in `ai/phone.py`, not here). `to` is never validated as digits.
- What's missing for a real WA channel: media/template/interactive sends, `type` other than text, marking messages read, the 24h customer-service window + template fallback, error-code handling (e.g. 131047 re-engagement), retrieval of sent message IDs (returns only `bool`, so the bot's own WA messages can't be deduped/echo-tracked), and **any media download** (`GET /{media_id}?phone_number_id=…` is implemented nowhere).
- Integration gap (verified): `wa_phone_number_id` / `wa_access_token` are never written by any endpoint or schema → the WA webhook lookup `Tenant.wa_phone_number_id == phone_number_id` (webhook.py:496) can only succeed for manually seeded tenants. The channel is effectively unreachable via the product UI.

---

## 4. Notification service — `app/services/notification_service.py` (220 lines, 6 functions)

Uniform pattern per notifier: public dispatch → if `tenant.notification_pref == "email" and tenant.business_email` → private email sender; else log-only. Private senders bail out with a warning if `settings.SMTP_USER` empty; every SMTP failure is caught, logged and swallowed (never propagates to the caller — deliberate graceful degradation).

| Function | Trigger | Content |
|---|---|---|
| `notify_new_order(tenant, order)` | Called by Celery task `send_order_notification` (notification_tasks.py:35) and synchronously as fallback in agent.py:444 | → `_send_email_notification` |
| `_send_email_notification(tenant, order)` | — | Bilingual subject `[page] New Order <num> - <total> EGP`; plain-text body listing customer name/phone/address (`address_detail, area, city, governorate`), payment method uppercased, item lines `name xqty = total EGP`, subtotal/delivery/total. `MIMEMultipart` + `MIMEText(body,"plain","utf-8")`. Sent via `aiosmtplib.send(hostname=SMTP_HOST, port=SMTP_PORT, username, password, use_tls=False, start_tls=True)` — STARTTLS assumed (587 default, gmail). |
| `notify_low_quota(tenant, usage_percent)` | **DEAD CODE — no callers anywhere** (the only quota system lives in the never-imported `llm_gateway.py`; the 80% trigger documented in the docstring is not implemented) | → `_send_low_quota_email` |
| `_send_low_quota_email` | — | Bilingual warning at `usage_percent:.1f%` of daily token quota with upgrade advice. |
| `notify_crawl_complete(tenant, job)` | **DEAD CODE — no callers** (crawl_tasks.py:69-76 completes the job with only a log line; the email is never sent) | → `_send_crawl_complete_email` |
| `_send_crawl_complete_email` | — | Bilingual summary: URL, status, pages found, products extracted, duration (`completed_at - started_at`). |

Templates: inline f-strings (no Jinja2 despite it being a dependency), plain text only, EN+AR mixed, fixed `---\nZemest` footer, `From: settings.NOTIFICATION_FROM_EMAIL` (default `noreply@zemest.ai`).

Celery integration (`app/tasks/notification_tasks.py`): `@celery_app.task send_order_notification(tenant_id, order_id)` — spins a fresh `asyncio` event loop per task, loads Tenant and Order (with `selectinload(Order.items)` — correctly avoids the lazy-load trap), then calls `notify_new_order`. Dispatch site (agent.py:435-446): `.delay()` first, and on ANY dispatch exception falls back to inline `await notify_new_order(...)` — good resilience to Redis outages.

**Race condition**: `.delay()` is fired (agent.py:437) while the creating session has only *flushed*; the commit happens later (webhook.py:521 or `get_db` teardown). A fast worker can fetch before commit → `order is None` → task exits silently with no error and **no email ever sent** (no retry configured on the task). Same commit-vs-dispatch class of bug Z5 found in the crawl pipeline.

Minor: subject headers interpolate `tenant.page_name` — CRLF header injection is theoretically possible via page name containing newlines (MIME lib usually rejects; unvalidated input either way). No retry queue for failed sends.

---

## 5. Transcription — `app/services/transcription.py` (62 lines, 2 functions)

- Module state: `_model = None` global (lazy, process-lifetime cache) and `_model_lock = asyncio.Lock()` — the lock is **defined but never acquired anywhere** (dead; the lazy load at line 46-47 is unprotected).
- `transcribe_url(url: str) -> str | None`:
  - Downloads the voice note with `httpx.AsyncClient(follow_redirects=True, timeout=30.0)`; **no content-length/size cap**; `resp.content` fully buffered in RAM before writing to `tempfile.mkstemp(suffix=".ogg")`.
  - Runs `_transcribe_file` via `asyncio.to_thread` (correctly keeps the CPU-bound decode off the event loop); `finally: tmp.unlink(missing_ok=True)` — clean temp hygiene.
  - Any exception → `logger.warning` + `None` (graceful degradation end-to-end: agent falls back to "(voice note)" text).
- `_transcribe_file(path: str) -> str | None`:
  - `from faster_whisper import WhisperModel` inside the function; `ImportError` → warning + `None` (**graceful degradation when missing** — though `faster-whisper>=1.0.0` IS in requirements.txt:38, so this is only a dev-environment path).
  - Model config: `WhisperModel("small", device="cpu", compute_type="int8")` — small model, CPU, int8 quantization. First call downloads ~464MB from HuggingFace **inside the webhook background task** (no pre-warm, nothing in Dockerfile) → first-ever voice note pays a multi-minute cold start; model then stays resident (~500MB+ RAM per worker process, never evicted).
  - `transcribe(path, language=None, vad_filter=True, beam_size=1)`: **no language hint** (auto-detect every call — slower/less accurate for Egyptian Arabic; `language="ar"` would halve latency), VAD filter on, greedy beam for speed. Segments joined with spaces; empty → None.
  - **No ffmpeg subprocess and no format conversion code** — faster-whisper's bundled PyAV decodes the Messenger `.ogg`/Opus natively (correct design).
  - **No caching** (same media re-downloaded + re-transcribed on Meta webhook retries), no duration cap, no concurrency cap (unbounded `to_thread` → N simultaneous Whisper runs; combined with the unprotected lazy init, concurrent first-calls can load the model twice).
- Caller: `agent._transcribe_audio` (agent.py:220-230) — first URL only (`audio_urls[:1]`), runs **before** the `fb_message_id` dedup check (agent.py:65).
- **Broken for WhatsApp**: the WA webhook handler puts media **IDs** (e.g. `msg.audio.id`) into `audio_urls` (webhook.py:470); `httpx.get("1234567890")` fails immediately → caught → None. No `GET /{media_id}` retrieval exists, so WA voice transcription is silently dead.

---

## 6. Vision — `app/services/vision.py` (144 lines, 1 function + dataclass)

- Constant: `GEMINI_VISION_URL = ".../v1beta/models/gemini-2.0-flash:generateContent"` — **hardcoded model, ignores `settings.GEMINI_MODEL`** (config.py:32), unlike the rest of the LLM stack.
- `ImageAnalysis` dataclass: `product_name, category, color, details, price_hint` + `prompt_tokens, completion_tokens` (token usage is persisted by the caller into a `TokenUsage` row with `usage_type="vision"`, agent.py:253-267 — nice cost-accounting).
- `analyze_product_image(image_url, api_key, product_context="") -> ImageAnalysis | None`:
  1. Empty `api_key` → None (clean skip when `GEMINI_API_KEY` blank — README's "voice + images skipped, text still works").
  2. Downloads the image (15s timeout); **10MB cap** after full buffering; mime from `Content-Type` header (falls back `image/jpeg`; note: a non-image response e.g. `text/html` is not rejected — it would be base64'd and sent to Gemini).
  3. Base64 `inline_data` + Arabic prompt demanding strict JSON `{"product_name","category","color","details","price_hint"}` with anti-hallucination instruction ("ممنوع تختلق معلومات. لو مش واضح حاجة اكتب غير واضح") and "Return ONLY the JSON". If `product_context` given, it's appended ("معلومات إضافية عن منتجات الصفحة").
  4. `generationConfig: temperature=0.1, maxOutputTokens=256`; POST with `x-goog-api-key` header, 30s timeout; `raise_for_status`.
  5. Extracts the **first** text part only; reads `usageMetadata.promptTokenCount/candidatesTokenCount`.
  6. JSON parsing: strips ```` ```json ```` fences; on `JSONDecodeError` falls back to regex `\{.*\}` DOTALL then `json.loads` (which can itself raise → outer except → None). Robust-ish.
  7. All failures → warning + None.
- **Product matching against catalog: not implemented in the live path.** The `product_context` parameter exists precisely to ground the model in the tenant's catalog, but the sole caller (agent.py:250) calls `analyze_product_image(url, api_key)` with **no context** — so Gemini names products blind. The analysis text is then injected into the chat prompt (agent.py:150-158: `[العميل بعت صور. تحليل الصور:…]`) and actual catalog matching happens far downstream via `Product.name.ilike(f"%{name}%")` in order creation (agent.py:368) — the hallucinated-name→free-item-at-price-0 risk Z2 flagged. If vision fails, fallback is raw URLs in the prompt (agent.py:158) — i.e., no local fallback analysis.
- Latency: sequential loop over ≤3 images (agent.py:248), each up to 30s download + 30s API → up to ~90-180s added to reply latency; runs **before** dedup → Meta retries re-bill Gemini.
- Also silently broken for WhatsApp: `media_urls` there are media IDs (webhook.py:468), so `client.get(image_id)` fails → None for every WA image.

---

## 7. Importers — `app/services/importers/`

`__init__.py` is **empty** (no re-exports; consumers import from submodules directly).

### 7.1 `messenger_dyi.py` (228 lines, 4 functions) — Messenger/IG "Download Your Information" JSON

Format handled (docstring lines 6-27): `messages/inbox/<thread>/message_1.json` (+`message_2.json…` for large threads), each file `{title, participants[], messages[{sender_name, timestamp_ms, content, type, reactions, sticker, photos, share, …}]}`.

- `parse_messenger_dyi_zip(zip_bytes, page_owner_names=None) -> list[dict]` — the core parser, **two passes**:
  - Pass 1: opens every ZIP entry matching `*.json` + `"message_" in name` (`json.JSONDecodeError`/`OSError` per-file → skipped with warning), collects `parsed_threads` (whole JSON dicts held in RAM) and `sender_counts`. `BadZipFile` → `ValueError` (mapped to HTTP 400 by style_learning.py:106).
  - Owner detection: if `page_owner_names is None`, the **most frequent sender across all threads** becomes the merchant (heuristic; `participants` array is documented but never used for detection — e.g. "thread title == the other party" or "participants minus owner" would be more reliable).
  - Pass 2: per message — mojibake repair `sender/content/title .encode("latin-1").decode("utf-8", errors="replace")` (lines 105,109,138; classic Meta DYI double-encoding fix; `errors="replace"` silently mangles genuinely-latin1 text); skips `type in ("Call","Subscription","Payment")`; content fallbacks for media messages: `photos→"(photo)"`, `share.link→the link`, `sticker→"(sticker)"`, `gifs→"(gif)"`, `videos→"(video)"`, `audio_files→"(audio)"`, else skip; **messages without `timestamp_ms` are skipped**; timestamp = `datetime.fromtimestamp(ms/1000, tz=utc)` (aware UTC — good); reactions extracted as list; `role = merchant if sender in owner_names else customer`; output sorted by timestamp. **Media binaries in `photos/` are ignored entirely.**
- `parse_instagram_dyi_zip(...)` — calls the FB parser then relabels `channel="instagram"` (Meta unified export format).
- `stream_parse_messenger_zip(zip_bytes, batch_size=1000)` — **fake streaming**: calls the full in-memory parser, then re-yields batches (docstring's "memory-efficient for millions of messages" is false; it's *worse* — full list + batch copies). Dead code (no callers).
- `get_zip_stats(zip_bytes)` — docstring says "without fully parsing" but it `json.load`s **every** message file (full parse, ~2× total work with the subsequent parse call at style_learning.py:76+105). Returns `{thread_count, estimated_message_count, file_count}` (+`error` key on bad ZIP). Bug: `thread_name` computed at line 211 and never used; `file_count` counts message JSONs but isn't exposed per-thread.

**DB mapping** (style_learner.py:425-490, the only consumer): messages grouped by `thread_title` → one `Conversation` per thread (`channel`, `status="imported"`, **`customer_id=None`**), then `Message(role=merchant|customer, content, channel, created_at=timestamp)`. **No Customer rows are ever created** for imported history, and `Conversation.customer_id` is NOT NULL → the import endpoint is expected to raise IntegrityError (Z3 CRITICAL, confirmed here from the importer side). Role vocabulary also diverges from live traffic ("merchant" vs "assistant" — Message.role comment says `customer, assistant, system`, message.py:19; agent's history mapper treats everything non-"customer" as assistant, so imports still work as context, but dashboards/filters keyed on "assistant" miss imported merchant turns).

### 7.2 `whatsapp_export.py` (163 lines, 3 functions) — WhatsApp "Export Chat" `.txt`

- `WA_LINE_RE = ^\[(\d{1,2}/\d{1,2}/\d{2,4}),\s*(\d{1,2}:\d{2}(?::\d{2})?\s*[APap]?[Mm]?)\]\s*([^:]+):\s*(.*)$` (line 30-32) — bracketed timestamp, optional seconds, optional AM/PM marker, sender = anything-but-colon (Arabic names fine; a sender containing ":" breaks the split), content rest-of-line. Multi-line messages = continuation lines without the prefix, appended with `\n` (lines 116-119).
- `_parse_wa_timestamp(date_str, time_str)` — tries **12 strptime formats, US `M/D` first, then `D/M`** (lines 41-54). Ambiguous dates (day ≤ 12) are systematically parsed as US format → Egyptian exports (D/M default in en-EG/WhatsApp regional formats) get **day/month transposed** for ~half of all dates. Returns **naive** datetimes — Egypt local time (UTC+2/+3) is stored directly as `Message.created_at` while the rest of the app writes naive-UTC (message.py:24) → 2-3h skew vs webhook messages.
- `parse_whatsapp_export_zip(zip_bytes, page_owner_name=None)`:
  - Finds the **first `.txt`** in the ZIP (`_chat.txt` normally); decodes utf-8 `errors="replace"`; **no BOM stripping** — a `\ufeff` on line 1 makes the first line fail the regex → first message silently dropped.
  - Two passes over the in-memory line list: parse + count senders, then normalize. Owner auto-detect = most frequent non-system sender (`WA_SYSTEM_SENDERS = {"System","WhatsApp","Messages and calls are end-to-end encrypted"}` — note the third entry can never match a sender, it's a message-body string).
  - Media placeholders normalized: `<Media omitted>`, `<media omitted>`, `image omitted`, `video omitted` → `"(media)"`. **Actual media files in the export ZIP are never extracted** — only the txt is read; when exported "without media" this is all that exists anyway.
  - Output: `channel="whatsapp"`, `thread_title="WhatsApp Chat"` (hardcoded — **all participants lumped into one conversation**, unlike per-thread Messenger import), role by sender==owner, `message_type="Generic"`, `reactions=[]`.
- `stream_parse_whatsapp_zip(zip_bytes, batch_size=500)` — same fake-streaming pattern (full parse, then slice); dead code.

**DB mapping**: identical `import_messages_and_build_style` path; single conversation per export file; timestamps naive-local (skew); no Customer rows; same `customer_id=None` IntegrityError exposure.

### 7.3 Upstream intake (style_learning.py:45-131, for reference)
Reads whole upload into RAM (`await file.read()` — up to 500MB cap checked *after* full read), runs `get_zip_stats` (full parse #1), auto-detects channel (filename contains "whatsapp" → WA; else `stats.thread_count>0` → messenger; else presence of any `.txt` → WA; else messenger), parses (full parse #2), imports, builds style profile (LLM call, `use_llm` default True on rebuild path).

---

## 8. Function inventory table (31 functions)

| File | Function | Params | Returns | Purpose |
|---|---|---|---|---|
| facebook_service.py | `get_user_pages` | `user_access_token: str` | `list[dict]` (pages incl. tokens) | List FB pages user manages via `/me/accounts`; no pagination |
| facebook_service.py | `subscribe_page_to_webhook` | `page_id, page_access_token: str` | `bool` | Subscribe page to 6 webhook fields via `/subscribed_apps` |
| facebook_service.py | `subscribe_instagram_to_webhook` | `ig_user_id, access_token: str` | `bool` | Subscribe IG account (3 fields) — **DEAD, never called** |
| facebook_service.py | `get_page_products` | `page_id, page_access_token: str` | `list[dict]` | First catalog → first page of products; used by sync-catalog |
| messenger_service.py | `send_sender_action` | `token, recipient_id, action: str` | `bool` | POST `/me/messages` sender_action (typing/seen) |
| messenger_service.py | `typing_on` | `token, recipient_id` | `bool` | Wrapper → "typing_on" |
| messenger_service.py | `typing_off` | `token, recipient_id` | `bool` | Wrapper → "typing_off" |
| messenger_service.py | `mark_seen` | `token, recipient_id` | `bool` | Wrapper → "mark_seen" |
| messenger_service.py | `send_text_message` | `token, recipient_id, text, messaging_type="RESPONSE", tag=None` | `dict` (Meta response, may carry `_auth_error`/`_source_id`; `{}` on error) | Send text; 190/10 auth-error detection; MESSAGE_TAG support |
| messenger_service.py | `send_quick_replies` | `token, recipient_id, text, options: list[str]` | `dict` | ≤13 text quick replies — **DEAD** |
| messenger_service.py | `send_attachment` | `token, recipient_id, attachment_type, url` | `dict` | URL-based attachment send (image/audio/video/file) — live path unused |
| messenger_service.py | `send_image` | `token, recipient_id, image_url` | `dict` | Wrapper — **DEAD** |
| messenger_service.py | `send_audio` | `token, recipient_id, audio_url` | `dict` | Wrapper — **DEAD** |
| messenger_service.py | `get_user_profile` | `token, psid` | `dict` (first/last name, pic) | `GET /{psid}` profile — **DEAD** |
| whatsapp_service.py | `send_whatsapp_message` | `tenant: Tenant, recipient_id, text: str` | `bool` | Cloud API text send; Bearer auth; hardcoded v21.0 |
| notification_service.py | `notify_new_order` | `tenant: Tenant, order: Order` | `None` | Dispatch on pref=email+business_email; else log |
| notification_service.py | `_send_email_notification` | `tenant, order` | `None` | Bilingual plain-text order email via aiosmtplib STARTTLS; errors swallowed |
| notification_service.py | `notify_low_quota` | `tenant, usage_percent: float` | `None` | Quota warning dispatch — **DEAD (no callers)** |
| notification_service.py | `_send_low_quota_email` | `tenant, usage_percent` | `None` | Bilingual quota email — dead with its dispatcher |
| notification_service.py | `notify_crawl_complete` | `tenant, job: CrawlJob` | `None` | Crawl summary dispatch — **DEAD (crawl_tasks never calls)** |
| notification_service.py | `_send_crawl_complete_email` | `tenant, job` | `None` | Bilingual crawl email w/ duration |
| transcription.py | `transcribe_url` | `url: str` | `str \| None` | Download audio (30s, unbounded size) → temp .ogg → to_thread transcribe → cleanup |
| transcription.py | `_transcribe_file` | `path: str` | `str \| None` | Lazy WhisperModel("small", cpu, int8); language=None, vad_filter=True, beam_size=1; ImportError→None |
| vision.py | `analyze_product_image` | `image_url, api_key: str, product_context=""` | `ImageAnalysis \| None` | Download ≤10MB → base64 → Gemini 2.0 Flash (temp 0.1, 256 tok) → strict-JSON parse; token counts included |
| vision.py | `ImageAnalysis` (dataclass) | — | — | product_name/category/color/details/price_hint + prompt/completion tokens |
| importers/messenger_dyi.py | `parse_messenger_dyi_zip` | `zip_bytes: bytes, page_owner_names: set[str] \| None = None` | `list[dict]` (channel/thread_title/sender/role/content/timestamp/message_type/reactions) | 2-pass DYI parse; mojibake fix; media placeholders; owner auto-detect by frequency |
| importers/messenger_dyi.py | `parse_instagram_dyi_zip` | `zip_bytes, page_owner_names=None` | `list[dict]` | FB parser + channel="instagram" relabel |
| importers/messenger_dyi.py | `stream_parse_messenger_zip` | `zip_bytes, batch_size=1000` | `Iterator[list[dict]]` | Fake streaming (full parse + re-batch) — **DEAD** |
| importers/messenger_dyi.py | `get_zip_stats` | `zip_bytes: bytes` | `dict` (thread/message/file counts, error?) | Stats via full json.load of every file; unused `thread_name` var |
| importers/whatsapp_export.py | `_parse_wa_timestamp` | `date_str, time_str: str` | `datetime \| None` | 12 formats, US-first, naive local time |
| importers/whatsapp_export.py | `parse_whatsapp_export_zip` | `zip_bytes, page_owner_name=None` | `list[dict]` | Regex line parse, multiline continuation, system-sender filter, media placeholder, owner auto-detect |
| importers/whatsapp_export.py | `stream_parse_whatsapp_zip` | `zip_bytes, batch_size=500` | `Iterator[list[dict]]` | Fake streaming — **DEAD** |

Supporting (context, not in scope): `send_order_notification` (Celery task), `import_messages_and_build_style` (DB mapping).

---

## 9. Issues / risks (prioritized, with file:line)

1. **CRITICAL — WhatsApp media AI is silently broken**: webhook collects WA media **IDs** into `media_urls`/`audio_urls` (webhook.py:468,470) but `transcribe_url` (transcription.py:19-21) and `analyze_product_image` (vision.py:42-44) require HTTP URLs; no `GET /{media_id}` retrieval exists anywhere (whatsapp_service.py has only the 38-line sender). Every WA voice note and image → exception → swallowed → None. Voice/vision features are Messenger/IG-only in practice.
2. **CRITICAL — WA + IG channels have no onboarding path**: `wa_phone_number_id`, `wa_access_token`, `wa_waba_id`, `ig_user_id`, `ig_access_token`, `owner_psid` appear in no schema (schemas/tenant.py:8-44) and are assigned by no endpoint — only `main.py:47-49` DDL creates the columns. Webhook lookups (webhook.py:361,496) can only match manually seeded rows; `subscribe_instagram_to_webhook` (facebook_service.py:67) is never called.
3. **HIGH — Celery notification race**: `send_order_notification.delay()` (agent.py:437) fires before the creating session commits (commit at webhook.py:521 / get_db teardown); a fast worker sees no Order → task no-ops silently (notification_tasks.py:32-35 guard) → order email lost, no retry. (Same class as Z5's crawl race.)
4. **HIGH — Graph API v21.0 EOL + version drift**: v21.0 base (config.py:41) is past Meta's 2-year minimum guarantee given the repo's 2026 timeline; `WHATSAPP_API_URL` is separately hardcoded to v21.0 (whatsapp_service.py:9), so a config bump fixes FB but silently strands WA.
5. **HIGH — Access tokens in query strings**: every facebook_service/messenger_service call passes `access_token` as a URL param (facebook_service.py:19,54,86,104,119; messenger_service.py:31,78,131,169,211) — leaks via proxy/access logs; contrast whatsapp_service.py:23 (Bearer header). Also `GET /api/facebook/pages` takes the user token as a query param and returns page tokens to the client (facebook.py:13-18).
6. **HIGH — Whisper resource risks**: `_model_lock` defined but never used (transcription.py:13) → concurrent first-loads can instantiate the model twice; unbounded `asyncio.to_thread` concurrency → N simultaneous CPU-bound transcriptions; ~464MB model downloaded on first use inside the webhook request path (transcription.py:47) with no pre-warm; no audio size cap before full RAM buffering (transcription.py:20-24); no transcript caching → Meta retries re-transcribe.
7. **MEDIUM — Vision runs before dedup & without catalog**: `_analyze_images` executes before the `fb_message_id` duplicate check (agent.py:53-58 vs 65-72) → Meta webhook retries re-bill Gemini (≤3 images ×N retries); `product_context` never passed (agent.py:250) so Gemini names products blind, deferring matching to the risky `ilike` order path (agent.py:368); model hardcoded (vision.py:12) ignoring `GEMINI_MODEL`; sequential ≤3×30s adds up to ~90s+ reply latency; non-image content-types not rejected (vision.py:52).
8. **MEDIUM — Dead notification paths**: `notify_low_quota` (notification_service.py:76) and `notify_crawl_complete` (notification_service.py:144) have zero callers — quota alerting is unwired (quota logic itself only in dead llm_gateway), and crawls complete without notifying the owner (crawl_tasks.py:69-76).
9. **MEDIUM — Importer memory/CPU**: upload fully read into RAM before the 500MB check (style_learning.py:65-70); `get_zip_stats` fully parses every JSON (messenger_dyi.py:214-217) then the real parse re-parses (style_learning.py:101-105) → 2× work, all `parsed_threads` held in memory (messenger_dyi.py:70-82) → multi-GB spike on big exports; `stream_parse_*` fake-streaming misrepresents itself (messenger_dyi.py:180-194; whatsapp_export.py:158-162) and is dead anyway.
10. **MEDIUM — WA timestamp correctness**: US-first format list (whatsapp_export.py:41-54) transposes day/month for ambiguous dates in D/M (Egyptian) exports; naive local-time datetimes (whatsapp_export.py:58) stored as `created_at` against a naive-UTC convention (message.py:24) → 2-3h skew vs live messages.
11. **MEDIUM — Importer→model mapping defects**: `Conversation(customer_id=None)` vs NOT NULL column → IntegrityError on the import endpoint (style_learner.py:455-461; Z3 confirmed); no Customer rows created for imported history; role vocabulary mismatch "merchant" vs "customer/assistant/system" (messenger_dyi.py:41-42 vs message.py:19); WA imports lump all participants into one "WhatsApp Chat" conversation (whatsapp_export.py:146).
12. **LOW — Graph pagination**: `get_user_pages` (facebook_service.py:14-27) and `get_page_products` (facebook_service.py:114-123) read only the first page → silent truncation for >25 pages/products.
13. **LOW — Dead functions**: `send_quick_replies`, `send_image`, `send_audio`, `get_user_profile` (messenger_service.py:111,191,195,203), `subscribe_instagram_to_webhook`, both stream parsers, `_source_id` mapping (messenger_service.py:95-96) never consumed. `get_zip_stats` unused var `thread_name` (messenger_dyi.py:211).
14. **LOW — WA sender limitations**: returns bool only (no message ID → no WA-side dedup/echo handling, no delivery status consumption); no 24h-window/template fallback; no error-code handling (whatsapp_service.py:12-37).
15. **LOW — Email robustness/hygiene**: SMTP failures swallowed with no retry/queue (notification_service.py:72-73,140-141,218-219); subject header built from unvalidated `tenant.page_name` (notification_service.py:58) — theoretical CRLF header injection; inline templates, no i18n abstraction; `use_tls=False, start_tls=True` fixed — port 465 (implicit TLS) config would silently break.
16. **LOW — DYI mojibake repair is lossy** (`errors="replace"`, messenger_dyi.py:105,109,138) and the owner-frequency heuristic misfires on threads where a single chatty customer out-messages the merchant (their messages become the merchant persona for style learning).

---

## 10. Quality ratings (1-10)

| File | Rating | Justification |
|---|---|---|
| facebook_service.py | **5** | Clean, consistent, Chatwoot-matched subscription fields; but dead IG function, no pagination, query-string tokens, blanket error swallowing, no token lifecycle. |
| messenger_service.py | **6.5** | Correct unified Messenger/IG send surface, best-in-repo auth-error (190/10) surfacing, MESSAGE_TAG support; minus 4 dead functions, `_source_id` dead feature, no pooling/retry/rate-limit handling. |
| whatsapp_service.py | **3** | 38-line stub: text-only, hardcoded API version, bool return (no message IDs), no media send, no error codes, no window handling, no media download; Bearer header is the lone bright spot. |
| notification_service.py | **6.5** | Uniform, well-documented graceful degradation; bilingual templates; token/usage cost awareness absent but not needed; minus 2 of 3 notifiers dead, no retry queue, subject-injection nit, Celery dispatch race lives at the caller. |
| transcription.py | **5** | Correct to_thread offload + temp-file hygiene + ImportError degradation; but unused lock (race), no size/duration/concurrency caps, no language hint, no caching, cold-start 464MB download in request path, broken for WA input. |
| vision.py | **7** | Robust strict-JSON parsing chain, token usage extraction, graceful None everywhere, anti-hallucination prompt; minus hardcoded model, unused `product_context` (no catalog grounding in live path), runs pre-dedup, no mime validation, sequential. |
| importers/messenger_dyi.py | **7** | Genuinely good DYI format coverage (mojibake, media placeholders, system types, reactions) with real tests; minus double-parse stats, fake streaming, participants array unused, OOM exposure. |
| importers/whatsapp_export.py | **6** | Solid line-regex + multiline continuation + system filtering, tested; minus US-first timestamps, naive local datetimes, BOM edge, single-conversation lumping, fake streaming. |
| importers/__init__.py | **N/A** | Empty file (no package facade). |

**Layer average ≈ 5.7/10.** The channel layer is a well-patterned prototype: consistent error swallowing, good graceful degradation, but the WhatsApp channel is a facade (no onboarding, no media, no IDs), a third of the surface is dead code, and three systemic risks (WA media IDs as URLs, pre-commit Celery dispatch, Graph v21.0 EOL) sit on the critical reply path.
