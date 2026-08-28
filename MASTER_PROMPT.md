# ═══════════════════════════════════════════════════════════════
# MASTER PROMPT: BUILD "ZEMEST" v1.0
# AI salesperson for Egyptian Facebook pages — Messenger + Instagram + WhatsApp
# Multi-tenant SaaS · 100% FREE stack · Production-ready
# ═══════════════════════════════════════════════════════════════

You are a senior full-stack engineer. Build the COMPLETE repository described
below. Every file must exist, parse cleanly, and work together. No TODOs, no
placeholders, no skipped sections. Follow every spec EXACTLY.

---

## SECTION 0 — MISSION & HARD CONSTRAINTS

Zemest lets an Egyptian page owner connect Facebook/Instagram/WhatsApp
once, then an AI takes over customer chats 24/7. It understands:
- عامية مصرية (Egyptian colloquial Arabic)
- Arabizi ("ana 3ayez el 3aba da", "3andek maqas 42?")
- English
- VOICE NOTES (transcribed locally — free)
- PRODUCT PHOTOS (Gemini vision — free)

It sells like a real Egyptian seller (warm, direct, pushy-but-polite),
collects complete orders (name, phone 01XXXXXXXXX, governorate/city/area/
address detail, payment method), auto-computes shipping across all 27
governorates, saves orders, emails the owner, and learns each page's unique
tone from its own chat history.

**FREE-ONLY STACK (never require payment):**
- Text LLM: OpenRouter with fallback chain ending in `:free` models, OR
  Gemini free tier (15 RPM / 1M tokens/day ≈ 1000 conversations/day at <20% load)
- Voice: faster-whisper LOCAL (small model, int8, CPU). Zero cost.
- Images: Gemini 2.0 Flash vision on the same free key.

**GRACEFUL DEGRADATION IS MANDATORY:**
- No GEMINI_API_KEY → voice/images skipped, text still works
- All LLM models fail → localized polite fallback reply
- A missing key or dead API must NEVER crash a webhook handler
- Every webhook returns 200 EVENT_RECEIVED fast; processing is background

---

## SECTION 1 — USER JOURNEYS (how it must feel)

### OWNER JOURNEY
1. Register/login at `/dashboard/login` (JWT sessions).
2. "Connect Page" → Facebook OAuth → pick page → backend stores
   page_access_token AND calls `subscribe_page_to_webhook()` immediately
   with the exact field list from Section 5.
3. Settings tab: paste Instagram Business ID + token, WhatsApp
   phone_number_id + token. Each channel gets its own webhook URL,
   same verify token.
4. Fill catalog 4 ways: manual form | CSV upload | import-from-URL
   (crawler) | FB Commerce catalog sync. Product attributes = flexible JSON
   (any keys: name_ar, sizes, color, sku, discount_price...).
5. Settings: delivery_inside_cairo=35, delivery_outside_cairo=60,
   free_delivery_above=300, payment numbers (vodafone_cash/instapay/fawry),
   optional external order-receiving webhook template with {{placeholders}}.
6. Daily life: dashboard shows revenue/orders/conversations/stats. OR he
   DMs his own page: "حدّث سعر التيشيرت لـ 250 جنيه" → owner-command parser
   updates DB, confirms in Arabic. Same for stock, add/delete product,
   shipping prices.

### CUSTOMER JOURNEY (the magic)
Customer messages the page at 2am — text, voice note, or product photo:
1. Webhook fires → agent replies within seconds in perfect عامية.
2. Voice note → faster-whisper transcribes locally BEFORE the LLM sees it.
3. Photo → Gemini vision describes it → matches to catalog ("ده كوتشي أبيض
   رياضي، عندنا شبهه بـ 850 جنيه").
4. Customer says "أيوه عايزه"? → agent IMMEDIATELY collects:
   ✏️ الاسم 📱 التليفون (01XXXXXXXXX) 📍 العنوان (منطقة+محافظة — infers
   "المعادي"=القاهرة) 💳 الدفع (COD/فودافون كاش/انستاباي/فوري).
5. Agent emits hidden ```json order block (stripped from customer view) →
   order saved + shipping computed → owner emailed → conversation marked
   order_placed.
6. Replies stay short (2–4 sentences), emoji-natural, never say آسف/مقدرش.

---

## SECTION 2 — TECH STACK (non-negotiable)

Python 3.12 · FastAPI · SQLAlchemy 2.0 async (Mapped[] style) + asyncpg +
PostgreSQL 16 (pg_trgm extension) + Alembic · Redis 7 · Celery 5 · httpx
for ALL outbound HTTP (always with timeout=) · Jinja2 + Pico CSS dashboard ·
pytest + pytest-asyncio (asyncio_mode=auto) + aiosqlite (tests need NO
Postgres) · faster-whisper · Playwright(chromium) crawl fallback ·
trafilatura + BeautifulSoup4 · python-Levenshtein (product fuzzy dedup) ·
python-jose + passlib/bcrypt · aiosmtplib · structlog · Docker Compose
(services: db, redis, app, celery_worker).

Celery timezone = **Africa/Cairo** (NOT Asia/Dhaka).

---

## SECTION 3 — REPOSITORY LAYOUT & FILE SPECS

```
zemest/
├── app/
│   ├── main.py                  # FastAPI + lifespan startup migrations
│   ├── config.py                # pydantic-settings (.env)
│   ├── database.py              # async engine + session factory
│   ├── dependencies.py          # JWT auth deps
│   ├── ai/
│   │   ├── agent.py             # orchestrator (Section 6)
│   │   ├── language.py          # arabic/arabizi/english detection
│   │   ├── prompts.py           # Egyptian Arabic system prompt builder
│   │   ├── llm_client.py        # OpenRouter/Gemini + fallback chain
│   │   └── order_collector.py   # extract/validate/clean order JSON
│   ├── api/
│   │   ├── router.py            # aggregates sub-routers
│   │   ├── webhook.py           # ⭐ Messenger/Instagram/WhatsApp (Section 5)
│   │   ├── auth.py              # register/login/facebook/me
│   │   ├── tenants.py           # page CRUD + stats
│   │   ├── facebook.py          # pages/connect/sync-catalog
│   │   ├── products.py          # CRUD + CSV + import-from-URL
│   │   ├── orders.py            # CRUD + status machine + retry-api + payment
│   │   ├── customers.py         # CRUD + lifetime value
│   │   ├── conversations.py     # history viewer
│   │   ├── address.py           # governorates/cities/shipping endpoints
│   │   ├── crawl.py             # trigger/status crawler
│   │   ├── test_chat.py         # simulate customer without Facebook
│   │   └── dashboard.py         # Jinja2 admin routes
│   ├── services/
│   │   ├── messenger_service.py # ⭐ Graph API sends (Section 5.4)
│   │   ├── facebook_service.py  # ⭐ subscriptions (Section 5.3)
│   │   ├── whatsapp_service.py  # WA Cloud API sender
│   │   ├── transcription.py     # faster-whisper local
│   │   ├── vision.py            # Gemini Vision
│   │   ├── style_builder.py     # per-page personality learner
│   │   ├── owner_chat.py        # Arabic command parser/executor
│   │   ├── order_service.py     # creation + state machine
│   │   ├── order_api_service.py # external webhook w/ {{template}}
│   │   ├── product_service.py   # CRUD + Levenshtein dedup + CSV
│   │   ├── notification_service.py  # email owner on new order
│   │   ├── tenant_service.py    # CRUD + revenue stats
│   │   └── auth_service.py      # register/login/JWT/FB-OAuth
│   ├── knowledge/
│   │   ├── crawler.py           # httpx → Playwright fallback
│   │   ├── product_extractor.py # JSON-LD/OG/regex prices (EGP patterns!)
│   │   ├── indexer.py           # PageIndex-style tree builder
│   │   ├── retriever.py         # ⭐ LLM reads TOC (~100 tokens), picks nodes
│   │   └── tree_sync.py         # DB products → tree rebuild (zero LLM cost)
│   ├── models/                  # user, tenant, product, customer,
│   │                            # conversation, message, order(+items),
│   │                            # knowledge_base, crawl_job, token_usage
│   ├── schemas/                 # pydantic request/response models
│   ├── tasks/
│   │   ├── celery_app.py        # timezone="Africa/Cairo"
│   │   ├── crawl_tasks.py       # async crawl pipeline
│   │   └── notification_tasks.py
│   └── utils/
│       ├── security.py          # JWT + bcrypt + X-Hub-Signature-256 verify
│       ├── phone.py             # Egyptian phone validate/normalize
│       └── egypt_address.py     # 27 governorates + shipping calculator
├── dashboard/templates/         # login/dashboard/chat/products/orders/
│                                # conversations/settings/customers/crawl
├── tests/                       # ≥120 pytest tests (Section 11)
├── alembic/versions/            # migrations (historical = NEVER edit)
├── Dockerfile                   # python:3.12-slim + chromium libs
├── docker-compose.yml           # db+redis+app+celery_worker
├── requirements.txt             # pinned deps incl. structlog
├── .env.example                 # ALL vars from config.py
├── init.sql                     # CREATE EXTENSION pg_trgm;
├── seed.py                      # demo user + EGYPTIAN products
└── readme.md
```

---

## SECTION 4 — DATA MODEL (exact fields)

```
users(id uuid pk, name, email uidx, hashed_password)

tenants(id pk, owner_id fk→users, page_name, fb_page_id uidx idx,
  page_access_token text, ig_user_id idx, ig_access_token text,
  wa_phone_number_id idx, wa_access_token text, wa_waba_id,
  website_url, business_phone, business_email,
  notification_pref default 'email',
  delivery_inside_cairo NUMERIC(10,2) default 35,
  delivery_outside_cairo NUMERIC(10,2) default 60,
  free_delivery_above NUMERIC(10,2),
  payment_methods JSONB,      -- {"vodafone_cash":"01...","instapay":"...","fawry":"..."}
  style_profile JSONB,        -- built by style_builder
  knowledge_base JSONB, knowledge_built_at,
  order_api_config JSONB,     -- {enabled,url,method,auth_type,request_template}
  is_active bool, created_at, updated_at)

products(id pk, tenant_id fk idx, name, price NUMERIC(12,2),
  is_active bool, source manual|crawl|csv|facebook|owner, source_ref,
  attributes JSONB,           -- ANY keys: name_ar, description, discount_price,
                              -- category, sku, stock_status, sizes, color, url...
  created_at)                 -- pg_trgm GIN index on lower(name)

customers(id pk, tenant_id fk idx, fb_psid, UNIQUE(tenant_id,fb_psid),
  channel messenger|instagram|whatsapp default 'messenger',
  name, phone,
  governorate, city, area, address_detail,    -- EGYPTIAN terms only!
  created_at, updated_at)

conversations(id pk, tenant_id fk, customer_id fk,
  channel messenger|instagram|whatsapp,
  status active|order_placed|closed default 'active',
  started_at, last_message_at)

messages(id pk, conversation_id fk idx, role customer|assistant,
  content text, fb_message_id, channel, media_urls JSON, created_at)

orders(id pk, tenant_id fk idx, customer_id fk, conversation_id fk?,
  order_number uidx 'ORD-yymmdd-nnn',
  customer_name, customer_phone,
  governorate, city, area?, address_detail,   -- NOT division/district/upazila
  payment_method cod|vodafone_cash|instapay|fawry default 'cod',
  payment_phone_last2?, payment_trx_id?,
  api_status? success|failed|pending|not_configured,
  api_response? text, api_status_code? int, api_called_at?, api_external_id?,
  subtotal NUMERIC(12,2), delivery_charge NUMERIC(12,2) default 0,
  total NUMERIC(12,2),
  status pending→confirmed→shipped→delivered, pending|confirmed→cancelled,
  notes? text, created_at, updated_at)
  Index(tenant_id,status)

order_items(id pk, order_id fk idx, product_id fk?, product_name,
  quantity int, unit_price NUMERIC(12,2), total_price NUMERIC(12,2))

knowledge_bases(id pk, tenant_id uidx fk, tree_json JSONB,
  source_documents JSONB, last_indexed_at)

token_usage(id pk, tenant_id fk idx, usage_type, model,
  prompt_tokens, completion_tokens, total_tokens, created_at)
```

### Egyptian geography (`app/utils/egypt_address.py`)
Dict GOVERNORATES: all 27 (cairo, giza, alexandria, port_said, suez,
luxor, aswan, asyut, beheira, beni_suef, dakahlia, damietta, faiyum,
gharbia, ismailia, kafr_el_shikh, matrouh, minya, monufia, new_valley,
north_sinai, qalyubia, qena, red_sea, sharqia, sohag, south_sinair).
Each maps to major cities/areas lists. Helpers:
`get_governorates()`, `get_cities(gov)`, `get_areas_for_governorate(gov)`,
`validate_egyptian_address(gov, city=None)`,
`calculate_shipping(governorate, subtotal, inside=35, outside=60,
free_above=None)` where cairo & giza = inside zone.

### Egyptian phones (`app/utils/phone.py`)
`validate_egyptian_phone`: strip spaces/dashes/parens/+ then match
`^01[0125]\d{8}$` OR `^201[0125]\d{8}$`. Carriers: 010 Vodafone, 011 Etisalat,
012 Orange, 015 WE.
`normalize_egyptian_phone`: if starts "20" → prepend "0", strip rest.
NO Bangladeshi patterns anywhere (01[3-9] is WRONG here).

---

## SECTION 5 — WEBHOOKS (match Chatwoot quality exactly)

One router `app/api/webhook.py`, prefix `/api/webhook`, FastAPI
BackgroundTasks for processing (return 200 instantly).

### 5.1 MESSENGER (/messenger)
```
GET  verify: hub.mode==subscribe && hub.verify_token==settings.FB_VERIFY_TOKEN
     → return challenge as text/plain; else 403 Forbidden.
POST receive:
  - read raw body ONCE (bytes) BEFORE json parse (signature needs raw bytes)
  - unless APP_DEBUG: verify X-Hub-Signature-256 =
    "sha256=" + HMAC-SHA256(body, FB_APP_SECRET) hexdigest, constant-time compare
  - object != "page" → 404
  - per entry: events = entry.messaging OR entry.standby
  - classify each event (_classify_messenger_event):
      message.is_echo==true       → message_echo → SKIP ENTIRELY (prevents loops)
      has delivery                → _handle_delivery (log watermark)
      has read                    → _handle_read_receipt (log watermark)
      has postback                → _handle_postback (title/payload as text
                                    through full agent flow)
      has referral                → log (future)
      has message                 → _process_messenger_message
```

`_process_messenger_message(page_id, event)`:
1. sender_id = event.sender.id; skip if none.
2. Extract attachments: type image/video/file → media_urls[];
   type audio → audio_urls[].
3. Skip if no text AND no media AND no audio.
4. Empty text placeholder: media→"(صورة)" audio→"(رسالة صوتية)".
5. async with async_session(): find Tenant by fb_page_id (warn+return if none).
6. Flow control (Chatwoot-grade UX):
   ```
   await mark_seen(token, sender_id)      # instant blue ticks
   await typing_on(token, sender_id)      # "..." bubble while AI thinks
   try:
       reply = process_customer_message(...)
       result = send_text_message(token, sender_id, reply)
       if result.get("_auth_error"): log CRITICAL token expired/revoked
       if result.get("_source_id"): available for dedup/tracking
   finally:
       await typing_off(token, sender_id)  # ALWAYS stop typing, even on crash
   ```
7. commit. Wrap everything in try/except logging exc_info=True — webhook
   handlers must NEVER raise.

### 5.2 INSTAGRAM (/instagram)
Same GET verify pattern. POST: same signature verification.
- Tenant lookup ORDER: ig_user_id == entry.id FIRST, fallback fb_page_id
  (IG business accounts linked to FB pages deliver under either ID).
- Handle attachment types: image, ig_reel, ig_post → media_urls; audio → audio_urls.
- Story replies: message.reply_to.story.url exists → text "(story reply)".
- Token = ig_access_token or page_access_token (skip send if neither).
- mark_seen/typing_on/off identical to Messenger.
- read events: log watermark.
- reaction events: classified, logged, not acted on (same as Chatwoot).

### 5.3 WHATSAPP (/whatsapp)
GET verify (same challenge pattern — Meta requires GET handshake too).
POST: signature via X-Hub-Signature-256.
Parse: entry[].changes[].value.messages[] with contacts[] alongside.
Message type mapping:
```
text        → text.body
image       → media_urls (image.id)
audio       → audio_urls (audio.id)
video       → media_urls (video.id)
document    → media_urls (document.id)
interactive → button_reply.id OR list_reply.id as text
sticker/system → ignore
```
Tenant by wa_phone_number_id. Customer name from contacts[].profile.name.
Reply via whatsapp_service.send_whatsapp_message.

### 5.4 SUBSCRIPTIONS (`app/services/facebook_service.py`)
```python
subscribe_page_to_webhook(page_id, token):
    POST /v21.0/{page_id}/subscribed_apps
    subscribed_fields = [
        "messages", "message_deliveries", "message_echoes",
        "message_reads", "messaging_postbacks", "standby"
    ]                                        # exact Chatwoot set + postbacks

subscribe_instagram_to_webhook(ig_user_id, token):
    POST /v21.0/{ig_user_id}/subscribed_apps
    subscribed_fields = ["messages", "message_reactions", "messaging_seen"]
```
Also: get_user_pages (GET me/accounts id,name,access_token),
get_page_products (catalogs→products sync).

### 5.5 SENDER LAYER (`app/services/messenger_service.py`)
All functions: httpx timeout=10 (sender actions timeout=5), catch
httpx.TimeoutException separately, generic except logs error returns {}.
- `send_sender_action(token, recipient, action)` → {recipient:{id},
  sender_action} — no "message" key allowed alongside.
- `typing_on/typing_off/mark_seen` wrappers.
- `send_text_message(token, recipient, text, messaging_type="RESPONSE",
  tag=None)`: payload {recipient, message:{text}, messaging_type}; if tag
  && type=="MESSAGE_TAG": add tag (for >24h windows use tag HUMAN_AGENT).
  On non-200: parse error.code; code in (190,10) → log "AUTH ERROR token
  expired/revoked", set data["_auth_error"]=True. Capture
  data["message_id"] → data["_source_id"] (dedup/tracking hook).
- `send_quick_replies`: ≤13 options, content_type text.
- `send_attachment(type,url)`: coerce invalid types → "file"; same auth
  error handling.
- `send_image/send_audio` wrappers.
- `get_user_profile(psid)`: first_name,last_name,profile_pic; {} on fail.

WhatsApp service: POST /v21.0/{wa_phone_number_id}/messages
Authorization Bearer, body {messaging_product:"whatsapp", to, type:"text",
text:{body}}. Log failures with resp.status_code+resp.text[:200].

---

## SECTION 6 — AGENT ORCHESTRATOR (`app/ai/agent.py`)

```python
process_customer_message(db, tenant, sender_psid, message_text,
                         fb_message_id=None, customer_name=None,
                         channel='messenger', media_urls=[],
                         audio_urls=[]) -> str
```
STEPS IN ORDER:
1. **Voice**: if audio_urls → transcribe_url(audio_urls[0]) → replace text.
   try/except log — failure falls through to original text.
2. **Vision**: if media_urls AND settings.GEMINI_API_KEY → analyze ≤3 imgs.
   If results and text still empty → synthesize
   f"إيه المنتج ده؟ {', '.join(names)}" or "عايز أعرف عن المنتج ده".
3. **Customer**: get_or_create by (tenant_id, fb_psid); set channel + name.
4. **Conversation**: latest for customer else new(channel); reactivate if
   status != active.
5. **Persist inbound**: Message(role=customer, content=text, channel,
   media_urls, fb_message_id).
6. **History**: last 10 messages ascending.
7. **Retrieval**: retrieve_context(db, tenant.id, text) →
   (products_context, knowledge_context).
8. **Language**: detect_language(text).
9. **System prompt**: get_system_prompt(business_name=tenant.page_name,
   products_context, knowledge_context, language_hint=lang,
   delivery_inside_cairo=float(tenant.delivery_inside_cairo or 35),
   delivery_outside_cairo=float(tenant.delivery_outside_cairo or 60),
   free_delivery_above=..., payment_methods=tenant.payment_methods,
   style_profile=tenant.style_profile or {}).
10. **LLM call**: build [{system}, *history mapped customer↔user,
    assistant↔assistant, final user]. Append image context block if any:
    "[العميل بعت صور. تحليل الصور:] - صورة: name (cat) color — details".
    chat_completion_with_usage(...) → content; total failure →
    _get_fallback_response(lang): arabic/arabizi/english sorry-lines 🙏.
11. **Order extraction**: extract_order_from_response(raw) → if valid:
    - resolve items ilike against active Products; unit_price =
      attrs.discount_price or price, else 0
    - update customer identity/address fields from order_data
    - delivery = _calc_delivery priority:
      ① product attrs.delivery_charge override
      ② product attrs.free_delivery → 0
      ③ subtotal >= tenant.free_delivery_above → 0
      ④ governorate in (cairo,giza,القاهرة,الجيزة) → inside rate
      ⑤ else outside rate
    - create_order via order_service (state machine §7)
    - notify_new_order(tenant, order) in its own try/except
    - conversation.status = "order_placed"
12. **Reply**: clean_response_for_customer(raw) strips the JSON block.
13. **Persist assistant Message** + TokenUsage row (if usage present).
14. conversation.last_message_at = utcnow; flush; return reply.

---

## SECTION 7 — BUSINESS SERVICES

**order_service.create_order(...)**: generate ORD-yymmdd-nnn, subtotal=
Σ unit×qty, total=subtotal+delivery, insert order + items, flush.
`update_order_status` state machine:
```
pending  → [confirmed, cancelled]
confirmed→ [shipped, cancelled]
shipped  → [delivered]
delivered/cancelled → []   (ValueError otherwise)
```

**notification_service.notify_new_order**: if pref=email && business_email
&& SMTP configured → aiosmtplib STARTTLS email. Body bilingual header
"New Order Received! (تم استلام طلب جديد!)" items lines
"- name xN = TOTAL ج.م", address line uses governorate/city/area terms,
subject "[page] New Order ORD... - TOTAL EGP". Never raises.

**style_builder** (per-page personality): periodically sample recent
assistant messages of tenant → LLM extracts JSON {tone: friendly|formal|
direct, greeting_pattern, signoff_pattern, emoji_use: float 0-1,
avg_length} → save tenants.style_profile. Injected into every future
prompt (§8).

**owner_chat**: incoming message whose sender == tenant.owner_psid bypasses
normal flow. LLM parses instruction against current products into action
JSON:
```
update_price   {product_name,new_price}
update_stock   {product_name,stock_status: in_stock|out_of_stock|limited}
add_product    {name,price,description?}
delete_product {product_name}
update_shipping{inside_cairo,outside_cairo,free_above}
info_request   {query}
```
Execute directly (ilike match, soft-delete via is_active=False), confirm in
Egyptian Arabic ("تم تحديث سعر X إلى Y جنيه ✅"). Unknown → ask for
clarification. Never invents.

**order_api_service.call_order_api**: if tenant.order_api_config.enabled →
fill {{customer_name}},{{governorate}},{{city}},{{area}},
{{address_detail}},{{payment_method}},{{subtotal}},{{delivery_charge}},
{{total}},{{order_number}},{{items_json}} in request_template; auth
none|api_key|bearer|basic; POST/GET; detect error-in-200-body
({error}|success:false|status:error) → api_status failed; store
api_response[:2000], api_external_id extracted from common id keys.

---

## SECTION 8 — PROMPT ENGINEERING (`app/ai/prompts.py`)

`get_system_prompt(business_name, products_context, knowledge_context,
language_hint, delivery_inside_cairo, delivery_outside_cairo,
free_delivery_above, payment_methods, style_profile) -> str`

Entire prompt IN EGYPTIAN ARABIC. Structure:
1. Identity: "أنت بائع محترف لصفحة {business_name}... بتتكلم بالعامية
   المصرية (مش فصحى)... كأنك صاحب المكان".
2. Persona block from style_profile (fallback "- نبرة ودودة ومحترمة").
3. HARD RULES:
   - عامية مصرية ONLY
   - NEVER "آسف"/"مقدرش"/"مش عارف" — always offer alternative
   - أيوه|تمام|حسناً = AGREEMENT → start collecting order NOW, don't re-ask
   - category question → show best 2–3 products WITH prices immediately
   - upsell: "ده أكتر منتج بيتباع!" / "العرض ده قبل ما يخلص!"
   - 2–4 sentences max
4. FORBIDDEN: inventing prices/products/links not listed below.
5. Products context block.
6. Knowledge block (if any): "استخدمها للأسئلة عن السياسات والشحن".
7. Order protocol (verbatim collection template with emojis, city-inference
   examples المعادي→القاهرة المهندسين→الجيزة سيدي جابر→الإسكندرية) +
   exact ```json emission schema (§6 step 11 shape).
8. Shipping section: القاهرة/الجيزة {inside} جنيه ١-٢ يوم؛ باقي
   المحافظات {outside} جنيه ٣-٥ أيام؛ free-above line if set.
9. Currency/payment: العملة جنيه مصري (ج.م); methods from
   payment_methods dict else COD default.

⚠️ WRITE THE ARABIC YOURSELF CAREFULLY. NO Chinese characters (a previous
version shipped "最后一次" inside the Arabic sales rules — catastrophic bug).

`get_product_context(products)`: empty → "مفيش منتجات حالياً..." else per
product: `- Name: ~~price~~ sale ج.م ✅|❌|⚠️ — desc[:80]` +
optional "  رابط المنتج: {url}".

---

## SECTION 9 — LLM CLIENT (`app/ai/llm_client.py`)

```python
@dataclass LLMResponse: content, model, prompt_tokens, completion_tokens,
total_tokens

chat_completion(messages,...)->str  # wraps _with_usage
chat_completion_with_usage(messages, model=None, temperature=0.7,
                           max_tokens=1024)->LLMResponse
```
- primary = arg or settings.OPENROUTER_MODEL
- chain = [primary] + FALLBACK_MODELS minus dup:
  ["google/gemini-2.0-flash-001","qwen/qwen-2.5-72b-instruct",
   "arcee-ai/trinity-large-preview:free"]
- loop: try _call_openrouter → on ANY exception sleep(1) next model;
  exhaust → RuntimeError.
- gemma-family (model contains "google/gemma"|"gemma-"): NO system role —
  convert each system msg → user "[INSTRUCTIONS]\n...\n[/INSTRUCTIONS]" +
  assistant "Understood."
- OpenRouter headers include HTTP-Referer + X-Title. 429→raise(fallback).
  null content → raise. Parse usage{} + returned model.
- Optional Gemini path when provider=gemini: generativelanguage REST
  v1beta generateContent, x-goog-api-key header.

---

## SECTION 10 — KNOWLEDGE PIPELINE

crawler: strategy1 httpx+trafilatura (fast); JS-heavy → Playwright chromium
render then extract. Store crawl_jobs rows (pages crawled, products found,
status).

product_extractor: JSON-LD blocks → OG meta → regex fallback. PRICE
PATTERNS FOR EGYPT ONLY: `(?:EGP|E£|ج\.م)\s*([\d,]+\.?\d*)` and reversed
position. NO ৳ / BDT / Tk patterns (Bangladesh leftovers caused bugs).

indexer/tree structure node: {node_id zfill(4), title, text, summary,
line_num, nodes[], _type: product|product_category|(knowledge)}.

tree_sync.rebuild_product_tree: group active products by attrs.category →
category nodes with children; product child title
"{name} — {price} EGP {✅|❌|⚠️}"; rich text includes Arabic name
(attrs.name_ar — NOT name_bn), price EGP, discount, stock, description,
PRODUCT LINK line; merge preserving knowledge nodes; reassign ids; ZERO
LLM calls.

retriever.retrieve_context(db,tenant_id,query,max_nodes=3) →
(products_text, knowledge_text): build compact TOC "[P/K] [id] title —
summary[:100]" (~200 tokens) → LLM pick ≤3 node IDs as JSON array →
expand selected categories' children → split extracted texts by _type.
Failures → ("","") silently.

---

## SECTION 11 — TESTS (pytest, sqlite+aiosqlite, asyncio_mode=auto)

conftest: session event_loop; autouse setup_db create_all/drop_all;
fixtures: db_session, client(ASGITransport+dependency_overrides[get_db]),
test_user, auth_headers(JWT), test_tenant(EGYPTIAN phone 01012345678),
test_products (EGYPTIAN: Cotton Galabiya جلابية قطن etc. — attributes use
name_ar NOT name_bn), test_customer(governorate='cairo',city='Cairo'),
test_conversation.

Suites (≥120 tests):
- test_auth(9): register dup-email, login bad-pass, /me, JWT tamper...
- test_tenants(9): CRUD, ownership isolation, stats
- test_products(10): CRUD, flexible attributes (arabic attrs!), CSV import,
  fuzzy dedup, search
- test_orders(9): create manual, list/filter/pagination, detail, FULL
  lifecycle transitions, invalid-transition 400, cancel, modify-delivered
  400, 404
- test_conversations(3)
- test_webhook(6): verify-challenge ok/bad-token, bad-signature 403,
  echo-skip (no reply generated), postback routed, unknown-object 404
- test_crawl(4)
- test_language(10): arabic/arabizi/english/mixed cases
- test_phone(17): valid 010/011/012/015, +20/20 prefixes, spaces/dashes,
  too-short/long, letters, normalize forms
- test_egypt_address(13): 27 governorates count, cairo cities, invalid gov,
  areas, validate combos, shipping zones (cairo inside vs alexandria
  outside, free above threshold → 0)
- test_order_collector(7): fenced-json extract, missing-required → None,
  bad-phone → None, no-order plain text → None, clean strips json, legacy
  single-item coercion, defaults applied
- test_prompts(6): business name present, Arabic-script language markers
  (assert "عامية" or "المصرية" — NOT English words), governorate/COD in
  protocol, product-context formats (electronics/food/no-category/out-of-
  stock), currency "ج.م"
- test_security(6): hash/verify, JWT encode/decode/expiry
- test_system(7 e2e): register→tenant→products(manual+CSV)→stats→
  order-lifecycle→payment-update

⚠️ PITFALLS ALREADY HIT — DO NOT REPEAT (encode as self-check before finishing):
1. conftest dict literal `description:` missing quotes → SyntaxError kills
   whole suite. ast.parse every test file at the end.
2. Foreign characters inside Arabic strings (Chinese slipped into prompt).
3. Test assertions expecting ENGLISH substrings ("Arabic") in ARABIC-script
   prompts — assert Arabic tokens instead.
4. Any leftover BD vocabulary: division/district/upazila/Dhaka/taka symbol/
   bKash/Nagad/Rocket/name_bn/Asia-Dhaka-timezone/BDT — grep the finished
   tree; ZERO hits allowed in app/, tests/, dashboard/, seed.py (alembic
   historical files are the ONLY permitted exception — never edit them).
5. media_type="text_plain" typo → must be "text/plain".
6. Missing structlog in requirements while importing it elsewhere.
7. DB name drift between config.py default, docker-compose env,
   .env.example → pick ONE name everywhere (zemest).
8. Forgetting playwright install-deps after install chromium in Dockerfile.
9. hmac.compare_digest for signature compare (timing-safe), and read raw
   body BEFORE request.json().
10. Skipping echo events is MANDATORY — replying to own echoes = infinite
    feedback loop that burns API quota.

---

## SECTION 12 — CONFIG (.env.example ships complete)

```
DATABASE_URL=postgresql+asyncpg://zemest:zemest_secret@localhost:5432/zemest
DATABASE_URL_SYNC=postgresql://zemest:zemest_secret@localhost:5432/zemest
REDIS_URL=redis://localhost:6379/0
JWT_SECRET_KEY=change-me-to-a-random-secret-key
OPENROUTER_API_KEY= OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL=meta-llama/llama-4-maverick:free
GEMINI_API_KEY= GEMINI_MODEL=gemini-2.0-flash LLM_PROVIDER=auto
FB_APP_ID= FB_APP_SECRET= FB_VERIFY_TOKEN=zemest-verify-token
FB_GRAPH_API_URL=https://graph.facebook.com/v21.0
WHISPER_MODEL=small WHISPER_DEVICE=cpu WHISPER_COMPUTE_TYPE=int8
DEFAULT_DELIVERY_INSIDE_CAIRO=35 DEFAULT_DELIVERY_OUTSIDE_CAIRO=60
DEFAULT_FREE_DELIVERY_ABOVE=300
SMTP_HOST=smtp.gmail.com SMTP_PORT=587 SMTP_USER= SMTP_PASSWORD=
NOTIFICATION_FROM_EMAIL=noreply@zemest.ai
APP_NAME=Zemest APP_ENV=development APP_DEBUG=true APP_HOST=0.0.0.0
APP_PORT=8000
```

---

## SECTION 13 — DEPLOYMENT

Dockerfile: FROM python:3.12-slim; apt-get chromium runtime libs
(libnss3 libnspr4 libdbus-1-3 libatk1.0-0 libatk-bridge2.0-0 libcups2
libdrm2 libxkbcommon0 libatspi2.0-0 libxcomposite1 libxdamage1 libxfixes3
libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2 libwayland-client0);
pip install -r requirements.txt; RUN playwright install chromium &&
RUN playwright install-deps; COPY .; EXPOSE 8000; CMD uvicorn.

docker-compose.yml services:
- db: postgres:16-alpine, POSTGRES_DB zemest, init.sql volume
  (CREATE EXTENSION IF NOT EXISTS pg_trgm;), healthcheck pg_isready -d zemest
- redis: redis:7-alpine + healthcheck
- app: build ., ports 8000:8000, env_file .env, overrides DATABASE_URL(S)/REDIS_URL
  to service hostnames, depends_on healthy both, uvicorn --reload dev cmd
- celery_worker: same image/env, command celery -A app.tasks.celery_app worker

main.py lifespan startup: idempotent ALTER TABLE ADD COLUMN batch (list in
Section 4 deltas) wrapped per-statement try/except; whisper prewarm thread.

seed.py: admin@zemest.ai/test123 + tenant "Egyptian Fashion Store" + 6
EGYPTIAN products (galabiya, khayamiya, papyrus, silver cartouche, leather
bag, copper finjan set) with name_ar attributes.

---

## SECTION 14 — ACCEPTANCE CHECKLIST (self-verify before declaring done)

□ `python -m compileall app tests` zero errors
□ grep proves ZERO Bangladesh artifacts in app/tests/dashboard/seed
  (alembic versions excluded)
□ pytest green ≥120 tests WITHOUT Postgres installed
□ docker-compose up → /docs loads, /dashboard redirects to login
□ POST /api/webhook/messenger with wrong verify token → 403
□ Echo-only payload → zero DB writes, zero outbound sends
□ Full simulated flow via /api/test/chat: arabic greeting → product Q →
  agreement → collected data → order row created with correct shipping
  (cairo vs aswan vs free-above)
□ Voice-note path works end-to-end with a local wav (no network needed
  after first model download)
□ Vision path skips cleanly when GEMINI_API_KEY=""
□ Owner command "حدّث سعر X لـ N" updates product price
□ Style profile JSON appears on tenant after enough history
□ No webhook handler can raise unhandled (audit every handler has
  try/except with logger.exception)

DELIVER: complete repo + passing tests + README documenting setup,
Facebook/Meta app configuration steps (webhook URLs /api/webhook/{messenger,
instagram,whatsapp}, required permissions pages_messaging,
instagram_manage_messages, ngrok testing instructions), and the .env table.
```
