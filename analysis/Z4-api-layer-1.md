# Z4 — API Layer Part 1 (auth, conversations, customers, orders, products, webhook, test_chat, router)

**Repo:** `/home/z/my-project/repos/zemest` · **Scope:** `app/api/{router,auth,conversations,customers,orders,products,webhook,test_chat}.py` + supporting deps (`app/dependencies.py`, `app/utils/security.py`, `app/services/{auth,order,product}_service.py`, `app/middleware/rate_limit.py`, `app/main.py`, relevant schemas/models).
**Total endpoints in scope: 31** (across 7 route files; `router.py` is pure composition, 0 endpoints).

---

## 1. Complete API Endpoint Catalog

Auth model legend: **JWT** = `Authorization: Bearer <jwt>` via `get_current_user` (dependencies.py:15); **JWT+T** = `get_tenant` (dependencies.py:41) which additionally resolves `{tenant_id}` path param AND enforces `Tenant.owner_id == user.id` (404 if not owner — anti-IDOR). **Webhook-sig** = `X-Hub-Signature-256` HMAC-SHA256 with `FB_APP_SECRET`. **Rate-limited** = NO for every endpoint — the slowapi limiter middleware is installed (main.py:211-218) but **zero endpoints use `@limiter.limit` or the `@rate_limit` decorator** (grep-verified across `app/`); the limiter has no `default_limits`, so it is inert. The comment in `middleware/rate_limit.py:18-19` ("See app/api/auth.py for examples") is **false** — auth.py has no decorators.

### auth.py — prefix `/api/auth`, tag `Auth`
| # | Method | Path | Auth | Request body | Response (codes) | Rate-limited | Purpose |
|---|--------|------|------|--------------|------------------|--------------|---------|
| 1 | POST | `/api/auth/register` | none | `RegisterRequest {name: str, email: EmailStr, password: str}` (no password policy) | `TokenResponse {access_token, token_type:"bearer"}` — 200; 400 `ValueError`("Email already registered") | No | Create user (bcrypt) then auto-login (auth.py:18-25) |
| 2 | POST | `/api/auth/login` | none | `LoginRequest {email: EmailStr, password: str}` | `TokenResponse` — 200; 401 "Invalid credentials" | No | Email+password → JWT (auth.py:28-34) |
| 3 | POST | `/api/auth/facebook` | none | `FacebookLoginRequest {fb_access_token: str}` | `TokenResponse` — 200; 401 "Invalid Facebook token" | No | Exchange FB user token for JWT via Graph `/me?fields=id,name,email` (auth.py:37-43, auth_service.py:41-67) |
| 4 | GET | `/api/auth/me` | JWT | — | `UserResponse {id, name, email, fb_user_id}` — 200; 401 (missing/invalid token, user deleted) | No | Current user profile (auth.py:46-53) |

### conversations.py — prefix `/api/tenants/{tenant_id}/conversations`, tag `Conversations`
| # | Method | Path | Auth | Query/Body | Response (codes) | Rate-limited | Purpose |
|---|--------|------|------|------------|------------------|--------------|---------|
| 5 | GET | `.../conversations` | JWT+T | `page:int=1 (ge=1)`, `page_size:int=20 (ge=1,le=100)` | `ConversationListResponse {conversations:[{id, customer_name, status, started_at, last_message_at}], total}` — 200; 401; 404 (not tenant owner). **No page/page_size echoed** (schema mismatch vs other lists) | No | Paginated conversation list, `selectinload(customer)`, ordered `last_message_at DESC` (conversations.py:21-56) |
| 6 | GET | `.../conversations/{conversation_id}` | JWT+T | path `conversation_id: UUID` | `ConversationResponse` **with full `messages[]`** (no message pagination — all messages loaded via `selectinload`) — 200; 404 | No | Conversation detail + transcript (conversations.py:59-95) |

### customers.py — prefix `/api/tenants/{tenant_id}/customers`, tag `Customers`
| # | Method | Path | Auth | Query/Body | Response (codes) | Rate-limited | Purpose |
|---|--------|------|------|------------|------------------|--------------|---------|
| 7 | GET | `.../customers` | JWT+T | `page=1`, `page_size=50 (le=100)`, `search?: str` (ILIKE %…% on name OR phone) | `CustomerListResponse {customers:[CustomerResponse + orders_count, conversations_count, total_spent], total, page, page_size}` — 200; 401; 404 | No | List customers; per-customer aggregates computed in a **Python loop of 3 COUNT/SUM queries each** (customers.py:60-74 — N+1: 3×50=150 queries/page) |
| 8 | GET | `.../customers/{customer_id}` | JWT+T | path UUID | **Raw dict** (no response_model): profile + last 20 orders + last 10 conversations + `total_spent` (SUM of orders with status in confirmed/shipped/delivered) — 200; 404 | No | Customer 360° detail (customers.py:81-145) |
| 9 | PATCH | `.../customers/{customer_id}` | JWT+T | `CustomerUpdate {name?, phone?, governorate?, city?, area?, address_detail?}` (all optional; `exclude_none=True` so fields can't be nulled) | `{"status":"updated","id":...}` — 200; 404; 422 (validation) | No | Partial update via `setattr` loop (customers.py:148-168) |

### orders.py — prefix `/api/tenants/{tenant_id}/orders`, tag `Orders`
| # | Method | Path | Auth | Query/Body | Response (codes) | Rate-limited | Purpose |
|---|--------|------|------|------------|------------------|--------------|---------|
| 10 | POST | `.../orders` | JWT+T | `ManualOrderCreate {customer_name, customer_phone, governorate, city, area?, address_detail, payment_method="cod", delivery_charge=0, notes?, items:[{product_name, quantity=1, unit_price: Decimal}]}` | `OrderResponse` — **201**; 401; 404; **500 risk: order_number unique collision** | No | Find-or-create customer by (tenant, phone), then `order_service.create_order` (orders.py:46-112) |
| 11 | GET | `.../orders` | JWT+T | `page=1`, `page_size=20 (le=100)`, `status?: str` (exact match, free-form) | `OrderListResponse {orders:[OrderResponse incl. items], total, page, page_size}` — 200 | No | Paginated order list (order_service.get_orders) |
| 12 | GET | `.../orders/{order_id}` | JWT+T | path UUID | `OrderResponse` — 200; 404 | No | Order detail with items (`selectinload(Order.items)`) |
| 13 | PATCH | `.../orders/{order_id}/status` | JWT+T | `OrderStatusUpdate {status: str, notes?}` | `OrderResponse` — 200; **400** invalid transition (state machine: pending→confirmed/cancelled; confirmed→shipped/cancelled; shipped→delivered; delivered/cancelled terminal — order_service.py:113-131); 404 | No | Status transition + optional appended note `[status] note` (orders.py:144-164) |
| 14 | PATCH | `.../orders/{order_id}/notes` | JWT+T | `OrderNotesUpdate {notes: str}` | `{"status":"updated"}` — 200; 404 | No | **Overwrite** notes wholesale (no history) (orders.py:167-179) |
| 15 | POST | `.../orders/{order_id}/retry-api` | JWT+T | — | `{status: success|failed|not_configured, code?, external_id?, error?}` — 200; 404 | No | Re-call tenant's external order API (`order_api_service.call_order_api`) synchronously in request path (orders.py:182-195) |
| 16 | PATCH | `.../orders/{order_id}/payment` | JWT+T | **raw `dict`** (untyped): `payment_phone_last2?`, `payment_trx_id?`, `payment_method?` | `{"status":"updated"}` — 200; 404 | No | Update Vodafone Cash/Instapay verification info (orders.py:198-216) |

### products.py — prefix `/api/tenants/{tenant_id}/products`, tag `Products`
| # | Method | Path | Auth | Query/Body | Response (codes) | Rate-limited | Purpose |
|---|--------|------|------|------------|------------------|--------------|---------|
| 17 | GET | `.../products` | JWT+T | `page=1`, `page_size=50 (le=100)`, `search?` (ILIKE name) | `ProductListResponse {products, total, page, page_size}` — 200. **Active products only** (`is_active == True`) | No | List products (product_service.get_products) |
| 18 | POST | `.../products` | JWT+T | `ProductCreate {name: str, price: Decimal}` + **`extra="allow"`** — every extra field becomes a flexible attribute | `ProductResponse` — **201**; **409** duplicate (SKU exact match or pg_trgm `similarity>0.7` fuzzy name match, SQLite fallback to exact name) | No | Create product; rebuilds knowledge product tree (products.py:54-80) |
| 19 | POST | `.../products/upload-csv` | JWT+T | multipart `file: UploadFile` (decoded as UTF-8, no size/type limit) | `{imported, skipped, errors[], detected_columns{name_column, price_column, attribute_columns[]}}` — 200 (even when 0 imported); 500 on non-UTF-8 bytes | No | Auto-detect name/price columns (name/product_name/product/title/item/item_name; price/cost/amount/rate/mrp/unit_price); strips `EGP`/`ج.م`/`$`/`,` from prices; type-infers attributes (products.py:83-99, product_service.import_csv) |
| 20 | POST | `.../products/import-url` | JWT+T | **raw `dict`** `{url: str}` — no scheme/host validation | `ProductResponse` — 201; 400 "URL is required"; 422 extraction failed; 409 duplicate (products.py:102-144) | No | Crawl URL → extract product (JSON-LD → OG → regex → LLM fallback via `knowledge/product_extractor`, uses httpx + Playwright). **SSRF surface** |
| 21 | GET | `.../products/{product_id}` | JWT+T | path UUID | `ProductResponse` — 200 (returns **inactive** products too — inconsistent with list); 404 | No | Product detail (products.py:147-161) |
| 22 | PATCH | `.../products/{product_id}` | JWT+T | `ProductUpdate {name?, price?, is_active?}` + `extra="allow"` (extras merge into attributes) | `ProductResponse` — 200; 404 | No | Partial update; fixed fields set directly, extras merged into `attributes` JSON (products.py:164-183) |
| 23 | DELETE | `.../products/{product_id}` | JWT+T | — | **204** (soft delete: `is_active=False`); 404 | No | Soft-delete + product tree resync (products.py:186-200) |

### webhook.py — prefix `/api/webhook`, tag `Webhook`
| # | Method | Path | Auth | Query/Body | Response (codes) | Rate-limited | Purpose |
|---|--------|------|------|------------|------------------|--------------|---------|
| 24 | GET | `/api/webhook/messenger` | `hub.verify_token` == shared `FB_VERIFY_TOKEN` | query: `hub.mode`, `hub.verify_token`, `hub.challenge` | 200 `text/plain` challenge body; 403 "Forbidden" (webhook.py:30-43) | No | Meta webhook verification handshake |
| 25 | POST | `/api/webhook/messenger` | Webhook-sig (`verify_fb_signature`, fail-closed) | Meta page webhook JSON (`object=="page"`, `entry[].messaging[]` or `standby[]`) | 200 "EVENT_RECEIVED"; 403 invalid signature; 404 "Not a page event" (webhook.py:46-79) | No | Messenger events: message / delivery / read / postback dispatched to BackgroundTasks; echo skipped; referral & unknown silently dropped |
| 26 | GET | `/api/webhook/instagram` | same | same | 200 challenge — **BUG: `media_type="text_plain"` (invalid MIME, should be `text/plain`) — webhook.py:280**; 403 | No | Instagram webhook verification |
| 27 | POST | `/api/webhook/instagram` | Webhook-sig (`_verify_meta_signature`) | Meta IG webhook JSON (`entry[].messaging[]`/`standby[]`); **no `object=="instagram"` check** | 200 "EVENT_RECEIVED"; 403 (webhook.py:284-312) | No | IG messages (+ story replies, reels/posts attachments) and read receipts; reactions classified but unhandled; echo skipped |
| 28 | GET | `/api/webhook/whatsapp` | same | same | 200 `text/plain`; 403 (webhook.py:418-429) | No | WhatsApp verification (same shared token) |
| 29 | POST | `/api/webhook/whatsapp` | Webhook-sig | WhatsApp Cloud API JSON (`entry[].changes[].value.{messages, contacts}`) | 200 "EVENT_RECEIVED"; 403 (webhook.py:432-455) | No | WA messages: text/image/audio/video/document/interactive (button_reply & list_reply); media passed as **media IDs, not URLs** |

### test_chat.py — prefix `/api/test`, tag `Testing`
| # | Method | Path | Auth | Request body | Response (codes) | Rate-limited | Purpose |
|---|--------|------|------|--------------|------------------|--------------|---------|
| 30 | POST | `/api/test/chat` | JWT + tenant ownership check inline (test_chat.py:26-35) | `TestChatRequest {tenant_id: str, customer_name="Test Customer", message: str}` | `TestChatResponse {reply, conversation_id, customer_id, tokens_used}` — 200; 401; 404; **500 if `tenant_id` not a UUID** (`uuid.UUID(req.tenant_id)` raises ValueError, test_chat.py:28) | No | Simulate customer message through real `process_customer_message` AI pipeline with synthetic PSID `test_{user.id}` — **writes real Customer/Conversation/Message rows + consumes LLM tokens in prod DB** |
| 31 | POST | `/api/test/postiz-chat` | JWT + inline tenant ownership (test_chat.py:117-126) | `TestChatRequest` | `{reply, action, data}` — 200; 401; 404; 500 on bad UUID | No | Postiz social-scheduling AI chat (delegates to `ai/postiz_chat.handle_postiz_chat_request`) |

**Count check:** auth 4 + conversations 2 + customers 3 + orders 7 + products 7 + webhook 6 + test 2 = **31 endpoints**. Plus `router.py` composes 14 sub-routers (7 more files out of Z4 scope: tenants, address, crawl, facebook, style_learning, scheduling, postiz — handled by other agents).

---

## 2. Router Architecture (`app/api/router.py`, 22 lines)

- Single `api_router = APIRouter()` with **no global prefix/tags/dependencies**; each sub-router carries its own `prefix=` and `tags=` (auth.py:15, conversations.py:18, customers.py:14, orders.py:16, products.py:20, webhook.py:23, test_chat.py:12).
- 14 flat `include_router` calls (router.py:8-21): `auth, tenants, products, orders, conversations, customers, address, crawl, webhook, facebook, test_chat, style_learning, scheduling, postiz`.
- Mounted in `main.py:232-234` via `app.include_router(api_router)` — final paths are `/api/...` because prefixes are baked into sub-routers, not the mount.
- **Dependency chains** (two patterns):
  1. `/api/auth/*` → `get_current_user` only (HTTPBearer `auto_error=False` → manual 401s).
  2. `/api/tenants/{tenant_id}/*` → `get_tenant(tenant_id, db, user=Depends(get_current_user))` — path param + JWT + ownership assertion in ONE dependency (dependencies.py:41-57). This is the **only tenancy gate** and it is consistently applied in all 4 tenant-scoped files (verified every route).
  3. `/api/webhook/*` → no FastAPI auth dependency; raw `Request` + manual HMAC verification before JSON parse.
  4. `/api/test/*` → `get_current_user` + inline `Tenant.owner_id == user.id` select (duplicated logic instead of reusing `get_tenant`).
- Route ordering hazards: none within these files (UUID path segments are distinguishable); `products` `/upload-csv` & `/import-url` are declared **before** `/{product_id}` (products.py:83,102 vs 147) so they aren't shadowed — correct, but fragile (a new `/something` route appended after `/{product_id}` would be captured as a UUID 422).
- Also registered in main.py but outside scope: `admin/api` router, `admin/dashboard` router, sqladmin mount at `/_admin`, `api/dashboard` router, `/` redirect.

---

## 3. Auth Endpoints Deep-Dive (`auth.py` + `auth_service.py` + `utils/security.py`)

**Flows**
- **Register** (auth.py:18-25): `register_user` checks `User.email` uniqueness via SELECT (auth_service.py:15-17) — **no DB unique constraint on `users.email`** (models/user.py:17) → race condition can create duplicate emails; bcrypt hash (`passlib CryptContext`, security.py:34); then immediately calls `login_user` (re-verifies the just-hashed password — wasted bcrypt op) and returns a token. Non-atomic: register flushes, login re-SELECTs. Error mapping: any `ValueError` → 400 (only "Email already registered").
- **Login** (auth.py:28-34): SELECT by email → `verify_password` → `create_access_token({"sub": str(user.id)})`. Generic "Invalid credentials" 401 (no user enumeration on login). Both no-password users (FB-only) and unknown emails return the same 401.
- **Facebook login** (auth.py:37-43 → auth_service.py:41-67): GET `{FB_GRAPH_API_URL}/me?access_token=…&fields=id,name,email`; non-200 → 401. Looks up `User.fb_user_id` (unique, indexed); creates user if absent (no `hashed_password`). **Weaknesses:** (a) token is never checked against our app — no `debug_token`/`app_id` verification, so a valid user token minted for *any* Facebook app logs into Zemest (account creation on impersonation-adjacent trust); (b) `FB_APP_ID` config exists but is unused here; (c) no `appsecret_proof`; (d) FB-provided email can duplicate an email-registered user (email not unique → second account, no linking).
- **/me** (auth.py:46-53): JWT → user row; returns id/name/email/fb_user_id.

**JWT handling**
- HS256, secret from `settings.JWT_SECRET_KEY` (config.py:21 — default `"change-me-to-a-random-secret-key"`), access token TTL **1440 minutes = 24h** (config.py:23).
- `decode_token` (security.py:78-105): algorithms pinned to `[settings.JWT_ALGORITHM]` (blocks `alg=none`/RS256 confusion), `options={"require": ["exp"]}`, returns `None` on any error — never raises. Solid.
- `get_current_user` (dependencies.py:15-38): `HTTPBearer(auto_error=False)` → explicit 401 "Not authenticated"; decodes; `db.get(User, uuid.UUID(payload["sub"]))` → 401 "Invalid token"/"User not found". **`uuid.UUID()` on an attacker-controlled `sub` can raise ValueError → unhandled 500** (only for forged-but-signature-valid tokens, so low severity).
- Claims are minimal: `sub` only — no `tenant_id`, `role`, `jti`, or `type` in access tokens. (The rate-limit key function looks for `tenant_id` in the payload and always falls back to `user:{sub}` — middleware/rate_limit.py:78-84.)

**Refresh logic — defined but DEAD**
- `utils/security.py` implements a full refresh-token system: `create_refresh_token` (jti + `type=refresh` + 7-day exp, security.py:111-124), `verify_refresh_token` (security.py:127-145), Redis-backed revocation denylist `revoke_token`/`is_token_revoked_async` (self-cleaning TTL, fail-open on Redis outage, security.py:151-248), in-memory fallback denylist.
- **Grep-verified: NO API endpoint calls any of these.** There is no `/refresh`, no `/logout`, no token revocation route anywhere in `app/api/`. The whole apparatus is unused; the "hardening summary" docstring (security.py:1-16) describes a system that is not wired in. Users get a single 24h access token with no rotation or revocation path.
- Password hashing: bcrypt via passlib (`hash_password`/`verify_password`). No password strength/length validation on `RegisterRequest` (schemas/auth.py:6-9 — `password: str` bare).

---

## 4. Conversations & Chat (`conversations.py`)

- **List** (conversations.py:21-56): COUNT + page query both filtered by `tenant.id`; `selectinload(Conversation.customer)` avoids N+1 for customer_name; order `last_message_at DESC`; offset/limit pagination (`page/page_size` with `ge=1`, `le=100`). Response includes `total` but **not `page`/`page_size`** (ConversationListResponse, schemas/conversation.py:27-29 — inconsistent with the customers/orders/products list envelopes which do echo them). No filters (status/channel/date), no search, no cursor option — offset pagination degrades on large tenants.
- **Detail** (conversations.py:59-95): composite WHERE `(id == conversation_id AND tenant_id == tenant.id)` — correct tenant scoping; 404 when absent. `selectinload(messages)` + `selectinload(customer)`; **loads the ENTIRE message history in one response** — no message pagination, no limit, no since/until cursor. For long-running support threads this is an unbounded payload and memory spike.
- **Read-only**: this file has no write endpoints — no close/reopen, no agent-handoff, no send-message-to-customer API (outbound messaging happens only via webhooks/AI agent; the `facebook.py` router, out of scope, handles manual sends).
- No N+1 in this file; both endpoints hit DB exactly twice (count + page) / once (detail).

---

## 5. Orders / Products / Customers CRUD

### Tenant isolation (IDOR protection) — GOOD
Every tenant-scoped route resolves the tenant via `get_tenant`, which requires `Tenant.owner_id == current_user.id` and returns **404 (not 403)** for foreign tenants (dependencies.py:48-57). Every subsequent object query additionally filters `tenant_id == tenant.id` (customers.py:89, 156; products.py:154, 172, 194; orders via `order_service.get_order_by_id` order_service.py:105-110). No IDOR path found in these files. Note: 404-instead-of-403 avoids existence leaks but also hides "you lack access" semantics; single-owner-per-tenant model (no staff/agent roles) — a tenant cannot have multiple dashboard users.

### Orders (`orders.py` + `order_service.py`)
- **Create manual order** (orders.py:46-112): find-or-create customer keyed on `(tenant_id, phone)` — phone has **no unique constraint** (models/customer.py:22) so concurrent creates can duplicate customers; existing customer gets name/address **overwritten** by the request (orders.py:80-84 — silent data overwrite). New customer gets synthetic `fb_psid=f"manual-{uuid4()}"` (uniqueness satisfied). Order number `ORD-YYMMDD-{random 100-999}` (order_service.py:14-17) — **only 900 values/day globally** against `order_number UNIQUE` (models/order.py:22): birthday-paradox collision → IntegrityError → 500 at ~30+ orders/day system-wide. Subtotal/total computed server-side from items (order_service.py:36-39); **no price validation against the products table** (dashboard users can enter arbitrary unit_price — acceptable for manual orders, but no cross-check offered); `quantity` unvalidated (can be 0/negative — `ManualOrderItemCreate.quantity: int = 1` has no `gt=0`). No idempotency key — double-submit duplicates orders.
- **List** (orders.py:115-129): pagination + exact `status` filter (free-form string — typo'd status silently returns empty list); `selectinload(Order.items)`.
- **Status patch** (orders.py:144-164): enforced state machine (order_service.py:116-122) with 400 on illegal transition — the strongest validation in the layer. Notes are **appended** with `[status]` prefix here (contrast: notes endpoint overwrites).
- **Notes patch** (orders.py:167-179): wholesale replacement; loses history (the status endpoint's append convention is bypassed).
- **retry-api** (orders.py:182-195): calls `call_order_api` **synchronously in the request** (external HTTP with timeout per service, good) but `call_order_api` does **not check `order.api_status == "success"` before resubmitting** (order_api_service.py:21-30 only checks config) → **retrying a successful order re-submits it to the merchant's API = duplicate real-world order** (idempotency failure). Also updates `api_*` fields but the route returns the raw result dict without re-serializing the order.
- **Payment patch** (orders.py:198-216): body is an untyped `dict` — no length/format validation (`payment_phone_last2` column is VARCHAR(10); a longer string → DB error 500), no enum check on `payment_method`.

### Products (`products.py` + `product_service.py`)
- **Schema design**: `ProductCreate/ProductUpdate` use `extra="allow"` — arbitrary JSON attributes are a first-class feature (flexible catalog for Egyptian SMEs). `ProductResponse` flattens `attributes` dict.
- **Create** (products.py:54-80): duplicate guard = SKU exact scan across tenant's active products (**loads ALL tenant products then matches in Python** — product_service.py:51-61, O(n) per insert; CSV import makes this O(n²)) + pg_trgm `similarity(name,:name) > 0.7` raw SQL with graceful SQLite fallback to exact-name match (product_service.py:63-93). 409 on duplicate. After every create/update/delete, `_sync_product_tree` rebuilds the knowledge-tree product section (product_service.py:356-364) — on CSV import this runs **per row**.
- **CSV upload** (products.py:83-99): no size cap, no content-type check, `.decode("utf-8")` raises `UnicodeDecodeError` → 500 on binary/latin-1 files; BOM in first header would break name-column detection. Per-row errors collected; duplicates counted as `skipped`. Price normalization handles `EGP`, `ج.م`, `$`, thousands-commas (product_service.py:188). Type inference for booleans incl. Arabic "نعم/أيوه/لا" (product_service.py:246-257).
- **import-url** (products.py:102-144): untyped `dict` body; `url` taken verbatim — **no scheme allowlist, no private-IP/localhost blocking** → classic SSRF (httpx fetch, plus Playwright `page.goto` for JS-rendered pages — headless browser driven to attacker URLs). 400/422/409 handling is otherwise clean.
- **Read/Update/Delete**: get-by-id ignores `is_active` (returns soft-deleted products — inconsistent with list which hides them); update merges extras into attributes and resyncs tree; delete is soft (204, `is_active=False`).
- **Pagination**: consistent offset/limit with echo; search ILIKE name only.

### Customers (`customers.py`)
- **List**: search ILIKE on name OR phone; **severe N+1** — per customer in the page, 3 scalar queries (orders count, conversations count, SUM total of confirmed/shipped/delivered) (customers.py:61-74) → 1 + 3×page_size queries (151 at page_size=50). Should be 3 GROUP BY joins.
- **Detail** (customers.py:81-145): no response_model (untyped dict, `created_at`/`last_message_at` stringified manually — inconsistent datetime serialization vs the rest of the API); last 20 orders + last 10 conversations; `total_spent` uses the same 3-status whitelist — statuses are **hardcoded string lists duplicated** at customers.py:71 and 113 (magic values, no shared constant).
- **Update**: `exclude_none=True` semantics make it impossible to clear a field; no phone format validation (Egyptian numbers unvalidated); `setattr` loop is mass-assignment-safe only because `CustomerUpdate` whitelists 6 fields (good).

---

## 6. Webhook Processing (`webhook.py`)

**Platforms:** Meta trio — Messenger (`/messenger`), Instagram (`/instagram`), WhatsApp Cloud API (`/whatsapp`). All use the Meta handshake and `X-Hub-Signature-256`.

**Verification (GET)** — all three: `hub.mode == "subscribe" AND hub.verify_token == settings.FB_VERIFY_TOKEN` → echo `hub.challenge`; else 403. One **shared global** `FB_VERIFY_TOKEN` (default `"zemest-verify-token"`, config.py:40) for all tenants/platforms — fine for Meta (app-level), but the default value is a known string; if unset in prod, anyone can pass verification. Instagram's response uses `media_type="text_plain"` — **invalid MIME type** (webhook.py:280; should be `text/plain`); most clients tolerate it, but it's a latent bug.

**Signature validation (POST)** — Messenger uses `app.utils.security.verify_fb_signature`; Instagram/WhatsApp use a **local duplicate** `_verify_meta_signature` (webhook.py:531-548) with identical logic (DRY violation). Both are correct: `hmac.new(FB_APP_SECRET, body, sha256).hexdigest()` + `hmac.compare_digest(f"sha256={expected}", signature)` (constant-time). Both **fail closed** when signature empty or `FB_APP_SECRET` missing (403). Signature is verified on the raw bytes BEFORE `request.json()` — correct ordering (no parsing-before-auth).

**Dispatch pipeline (Messenger POST)**: `object != "page"` → 404; else per `entry` → `messaging` (fallback `standby`) → classify (webhook.py:82-96: message_echo/message/delivery/read/postback/referral/unknown) → `BackgroundTasks.add_task(...)` → immediately 200 `EVENT_RECEIVED` (fast ack, Meta happy). Echo skipped (own replies not re-processed). Delivery/read receipts only logged (webhook.py:217-227 — no persistence; read-state never shown in dashboard). Referral/unknown silently dropped. Postbacks are fed into the AI as `title or payload` (webhook.py:230-265).

**Message processing (`_process_messenger_message`, webhook.py:99-173)**: extracts text + image/video/file vs audio attachment URLs; empty-content guard; placeholder text `"(image)"` / `"(voice note)"`. Opens its **own** `async_session()` (not the request's), resolves tenant by `Tenant.fb_page_id == page_id` (404-style log+return if no tenant), then: `mark_seen` → `typing_on` → **owner bypass**: if `sender_id == tenant.owner_psid` route to `_handle_owner_message` (owner-chat command parser with a 20-product grounding snapshot; Arabic fallback strings) else `process_customer_message(...)` (the AI agent) → send reply via Graph API (skipped when reply == `"duplicate"`) → `typing_off` in `finally` → `db.commit()`. Auth-error flag from `send_text_message` (`_auth_error`) is logged for expired page tokens. Whole body wrapped in try/except with `exc_info=True` — **message loss on failure** (already ACKed 200; no retry/DLQ).

**Deduplication**: two layers — (1) webhook-level sentinel: `process_customer_message` returns literal string `"duplicate"` when `Message.fb_message_id` already exists (ai/agent.py:66-72); handlers check `reply != "duplicate"` before sending (webhook.py:160, 260, 397, 519). This guards Meta's webhook retries. Caveat: dedup happens **before** insert inside the same task; two concurrent deliveries of the same mid could race (SELECT-then-INSERT, no unique constraint mentioned on `fb_message_id` → check Z-models agent). (2) No dedup at the HTTP layer (no mid-level cache) — relies purely on the DB check.

**Instagram** (webhook.py:284-411): echo skip inline; classify message/read/reaction (reaction unhandled); attachments include `ig_reel`/`ig_post`; story replies detected via `message.reply_to.story.url` → `"(story reply)"`. Tenant lookup: `ig_user_id` first, **falls back to `fb_page_id`** (webhook.py:361-368) — cross-channel tenant mapping; token preference `ig_access_token or page_access_token`; missing token → silent return (message dropped without log-worthy error). No `object == "instagram"` verification (accepts any signed payload shape).

**WhatsApp** (webhook.py:432-524): parses `changes[].value.{messages, contacts}`; types: text, image, audio, video, document (media passed as **IDs**, not resolved to URLs — downstream must fetch via Graph API), interactive button_reply/list_reply (uses reply **id** as message text — the user-visible title is discarded, the AI sees only the opaque id). Tenant by `wa_phone_number_id`. No mark_seen/typing indicator (WA has no typing API parity). Same duplicate-sentinel and commit pattern.

**Error recovery**: none beyond logging — no retries, no DLQ, no per-tenant circuit breaker, no alerting hook. A transient DB/LLM failure = lost customer message (Meta sees 200). Conversely `BackgroundTasks` runs in-process after the response — an app crash/redeploy kills queued tasks.

---

## 7. `test_chat.py` — Production Safety Assessment

- Two endpoints, both **JWT-authenticated** and **ownership-checked** (inline `Tenant.owner_id == user.id`, not via `get_tenant` — duplicated code).
- **NOT production-safe despite auth**: `/api/test/chat` runs the full production AI pipeline (`process_customer_message`) and **persists real Customer (`fb_psid=test_{user.id}`), Conversation, and Message rows in the production DB**, plus consumes paid LLM tokens and writes `token_usage` rows. There is no environment guard (no `if settings.APP_DEBUG` / staging flag), no route exclusion in prod, no test-data tagging beyond the psid prefix. Dashboard junk data and billing noise are the practical consequences.
- `tokens_used` is computed by fetching the tenant's **latest** TokenUsage row (test_chat.py:78-90) — under concurrency this reports the wrong request's usage; wrapped in a bare `except Exception: pass`.
- `uuid.UUID(req.tenant_id)` (test_chat.py:28, 119) raises `ValueError` for non-UUID input → **500 instead of 422** (FastAPI can't coerce since `tenant_id` is `str` in the schema, not UUID). Same latent issue in both endpoints.
- `postiz-chat` is a thin delegate to `handle_postiz_chat_request` returning an untyped dict.

---

## 8. Function Inventory (every helper, signature + purpose)

### `app/api/router.py`
| Function | Signature | Purpose |
|---|---|---|
| — (module) | `api_router = APIRouter()` + 14×`include_router` | Compose all sub-routers under one root router (router.py:6-21) |

### `app/api/auth.py`
| Function | Signature | Purpose |
|---|---|---|
| `register` | `async (req: RegisterRequest, db=Depends(get_db)) -> TokenResponse` | Create user + auto-login; 400 on duplicate email (auth.py:18) |
| `login` | `async (req: LoginRequest, db) -> TokenResponse` | Credential check → JWT; 401 (auth.py:28) |
| `facebook_login` | `async (req: FacebookLoginRequest, db) -> TokenResponse` | FB token → Graph /me → find-or-create user → JWT (auth.py:37) |
| `get_me` | `async (user=Depends(get_current_user)) -> UserResponse` | Current profile (auth.py:46) |

### `app/api/conversations.py`
| Function | Signature | Purpose |
|---|---|---|
| `list_conversations` | `async (page:int=1, page_size:int=20, tenant=Depends(get_tenant), db) -> ConversationListResponse` | Count+page query, `selectinload(customer)`, `last_message_at DESC` (conversations.py:22) |
| `get_conversation` | `async (conversation_id: uuid.UUID, tenant, db) -> ConversationResponse` | Detail + ALL messages + customer (conversations.py:60) |

### `app/api/customers.py`
| Function | Signature | Purpose |
|---|---|---|
| `_customer_response` | `(c: Customer, orders_count=0, conversations_count=0, total_spent=0.0) -> CustomerResponse` | Model→DTO mapper with aggregates (customers.py:17) |
| `list_customers` | `async (page=1, page_size=50, search: str|None, tenant, db) -> CustomerListResponse` | Search (name/phone ILIKE) + per-row aggregate N+1 loop (customers.py:34) |
| `get_customer_detail` | `async (customer_id: uuid.UUID, tenant, db) -> dict` | 360° view: 20 orders, 10 conversations, total_spent (customers.py:82) |
| `update_customer` | `async (customer_id, req: CustomerUpdate, tenant, db) -> dict` | Partial update via setattr(exclude_none) (customers.py:149) |

### `app/api/orders.py`
| Function | Signature | Purpose |
|---|---|---|
| `_order_response` | `(o: Order) -> OrderResponse` | Model→DTO incl. items (orders.py:19) |
| `create_manual_order` | `async (req: ManualOrderCreate, tenant, db) -> OrderResponse` (201) | Find-or-create customer by phone; create order + items (orders.py:47) |
| `list_orders` | `async (page=1, page_size=20, status: str|None, tenant, db) -> OrderListResponse` | Paginate+filter via order_service (orders.py:116) |
| `get_order` | `async (order_id: uuid.UUID, tenant, db) -> OrderResponse` | Detail or 404 (orders.py:133) |
| `update_status` | `async (order_id, req: OrderStatusUpdate, tenant, db) -> OrderResponse` | State-machine transition + note append (orders.py:145) |
| `update_notes` | `async (order_id, req: OrderNotesUpdate, tenant, db) -> dict` | Overwrite notes (orders.py:168) |
| `retry_api_call` | `async (order_id, tenant, db) -> dict` | Re-call external order API (orders.py:183) |
| `update_payment_info` | `async (order_id, req: dict, tenant, db) -> dict` | Untyped payment field patch (orders.py:199) |

### `app/api/products.py`
| Function | Signature | Purpose |
|---|---|---|
| `_product_to_response` | `(p: Product) -> ProductResponse` | Model→DTO, `attributes or {}` (products.py:23) |
| `list_products` | `async (page=1, page_size=50, search, tenant, db) -> ProductListResponse` | Active-only paginate+search (products.py:36) |
| `create_product` | `async (req: ProductCreate, tenant, db) -> ProductResponse` (201) | Fixed fields + extra→attributes; 409 dup (products.py:55) |
| `upload_csv` | `async (file: UploadFile, tenant, db) -> dict` | CSV import w/ column autodetect (products.py:84) |
| `import_from_url` | `async (req: dict, tenant, db) -> ProductResponse` (201) | URL crawl→extract→create (products.py:103) |
| `get_product` | `async (product_id: uuid.UUID, tenant, db) -> ProductResponse` | Detail (inactive included) (products.py:148) |
| `update_product` | `async (product_id, req: ProductUpdate, tenant, db) -> ProductResponse` | Partial update, extras merge into attributes (products.py:165) |
| `delete_product` | `async (product_id, tenant, db) -> 204` | Soft delete (products.py:187) |

### `app/api/webhook.py`
| Function | Signature | Purpose |
|---|---|---|
| `verify_webhook` | `async (request: Request) -> Response` | Messenger GET hub.challenge (webhook.py:31) |
| `receive_messenger_event` | `async (request, background_tasks) -> Response` | Sig check → classify → dispatch BG tasks → 200 (webhook.py:47) |
| `_classify_messenger_event` | `(event: dict) -> str` | message_echo/message/delivery/read/postback/referral/unknown (webhook.py:82) |
| `_process_messenger_message` | `async (page_id: str, event: dict) -> None` | Tenant lookup, seen/typing, owner-bypass or AI agent, send reply, commit (webhook.py:99) |
| `_handle_owner_message` | `async (db, tenant, message_text: str) -> str` | Owner command parse+execute via owner_chat; Arabic fallbacks (webhook.py:176) |
| `_handle_delivery` | `async (page_id: str, event: dict) -> None` | Log-only delivery receipt (webhook.py:217) |
| `_handle_read_receipt` | `async (page_id: str, event: dict) -> None` | Log-only read receipt (webhook.py:224) |
| `_handle_postback` | `async (page_id: str, event: dict) -> None` | Feed postback title/payload into AI agent (webhook.py:230) |
| `verify_instagram_webhook` | `async (request) -> Response` | IG GET challenge (buggy media_type) (webhook.py:273) |
| `receive_instagram_event` | `async (request, background_tasks) -> Response` | Sig check → echo-skip → dispatch message/read (webhook.py:285) |
| `_classify_instagram_event` | `(event: dict) -> str` | message/read/reaction/unknown (webhook.py:315) |
| `_process_instagram_message` | `async (page_id: str, event: dict) -> None` | IG tenant (ig_user_id→fb_page_id fallback), story/reel attachments, send via IG/page token (webhook.py:325) |
| `_handle_ig_read` | `async (page_id: str, event: dict) -> None` | Log-only IG read receipt (webhook.py:408) |
| `verify_whatsapp_webhook` | `async (request) -> Response` | WA GET challenge (webhook.py:419) |
| `receive_whatsapp_event` | `async (request, background_tasks) -> Response` | Sig check → dispatch per message in changes (webhook.py:433) |
| `_process_whatsapp_message` | `async (phone_number_id: str, msg: dict, contacts: list) -> None` | WA type parsing (text/media/interactive), tenant by wa_phone_number_id, send via whatsapp_service (webhook.py:458) |
| `_verify_meta_signature` | `(body: bytes, signature: str) -> bool` | HMAC-SHA256 fail-closed check (duplicate of utils version) (webhook.py:531) |

### `app/api/test_chat.py`
| Function | Signature | Purpose |
|---|---|---|
| `test_chat` | `async (req: TestChatRequest, db, user=Depends(get_current_user)) -> TestChatResponse` | Simulate customer message via real AI pipeline w/ synthetic PSID (test_chat.py:16) |
| `postiz_chat` | `async (req: TestChatRequest, db, user) -> dict` | Postiz scheduling assistant delegate (test_chat.py:101) |

### Supporting (read for context, owned by other tasks)
`dependencies.get_current_user`, `dependencies.get_tenant`; `security.hash_password/verify_password/create_access_token/decode_token/create_refresh_token/verify_refresh_token/is_token_revoked(_async)/revoke_token/verify_fb_signature`; `auth_service.register_user/login_user/login_with_facebook`; `order_service.create_order/get_orders/get_order_by_id/update_order_status/_generate_order_number`; `product_service.create_product/_check_duplicate/get_products/update_product/delete_product/import_csv/_find_column/_parse_value/get_all_products_for_context/search_relevant_products/_sync_product_tree`; `rate_limit.get_rate_limit_key/_build_limiter/get_limiter/_rate_limit_handler/setup_rate_limiting`; `security(middleware).SimpleRateLimiter/rate_limit decorator`.

---

## 9. Issues / Risks (prioritized, with file:line)

**CRITICAL / HIGH**
1. **No rate limiting on any endpoint** — `rate_limit.py` docstring claims auth.py has examples (rate_limit.py:18-19) but grep shows zero `@limiter.limit`/`@rate_limit` usages; slowapi middleware installed without `default_limits` = inert. `/api/auth/login` and `/register` are brute-force/credential-stuffing open (auth.py:28). Webhook POSTs unthrottled (a flooded signed webhook = unbounded AI spend).
2. **`POST /orders/{id}/retry-api` lacks idempotency guard** — `call_order_api` never checks `order.api_status == "success"` before re-submitting (order_api_service.py:21-30; orders.py:182-195) → duplicate orders at the merchant's external API on double-click/retry of a successful order.
3. **SSRF via `POST /products/import-url`** — raw `dict` body, `url` used verbatim by httpx and Playwright `page.goto` (products.py:113, 120; knowledge/product_extractor.py:71, 99). No scheme/host/private-range validation → internal network & cloud-metadata probing from the server (and a headless browser at attacker direction).
4. **JWT default secret + 24h access token + dead refresh/revocation system** — `JWT_SECRET_KEY` default `"change-me-to-a-random-secret-key"` (config.py:21); access TTL 1440 min (config.py:23); the entire refresh-token + Redis denylist apparatus (security.py:111-248) is never called by any endpoint — no logout, no rotation, no revocation. A leaked token is valid for a day with no kill switch.
5. **Facebook login does not validate the token belongs to this app** — no `debug_token`/`app_id` check, no `appsecret_proof` (auth_service.py:41-49); `FB_APP_ID` config unused. Any valid FB user token (from any app) provisions/logs into a Zemest account; FB-supplied email can also silently duplicate an email-registered user (users.email has no unique constraint, models/user.py:17).

**MEDIUM**
6. **`order_number` collision → 500** — `ORD-YYMMDD-{rand 100-999}` (order_service.py:14-17) vs `unique=True` (models/order.py:22): ~50% collision probability around ~35 orders/day **system-wide** (not per-tenant).
7. **N+1 queries in customer list** — 3 aggregate queries per row in a Python loop (customers.py:61-74): 151 queries/page at default size; O(n²) duplicate-SKU scan per CSV row (product_service.py:51-61) plus product-tree rebuild per row (product_service.py:41).
8. **`/api/test/*` pollutes production data** — real Customer/Conversation/Message + TokenUsage rows, real LLM spend, no environment guard (test_chat.py:15-97); `tokens_used` reads the tenant's latest usage row (wrong under concurrency, test_chat.py:78-90).
9. **500 instead of 422 for bad `tenant_id`** — `uuid.UUID(req.tenant_id)` unguarded in both test endpoints (test_chat.py:28, 119).
10. **No message pagination on conversation detail** — `selectinload(Conversation.messages)` unbounded (conversations.py:71-72, 86-94).
11. **Untyped request bodies** — `orders.update_payment_info` `req: dict` (orders.py:201), `products.import_from_url` `req: dict` (products.py:104), plus untyped response of `get_customer_detail` (customers.py:117) and `retry_api_call`/`postiz_chat`: no schema validation, Swagger docs are empty for these, VARCHAR overflow → 500.
12. **Webhook message loss on processing failure** — 200 ACK is sent before processing; background task errors are only logged (webhook.py:172-173, 264-265, 404-405, 523-524); no retry/DLQ; BackgroundTasks die with the process on redeploy. Meta read/delivery receipts discarded (webhook.py:217-227).
13. **CSV upload** — no size limit, no content-type check, `UnicodeDecodeError` → 500 (products.py:97); BOM breaks column detection.
14. **Register race** — email uniqueness only via SELECT-then-INSERT (auth_service.py:15-17) with no DB constraint; concurrent registers → duplicate accounts. `password` has zero policy (schemas/auth.py:9). Register endpoint double-hashes (register+login, auth.py:21-22 — 2 bcrypt ops).
15. **WhatsApp interactive replies use opaque IDs** — `button_reply.id`/`list_reply.id` become the message text; the human-readable title is dropped (webhook.py:477-480) → the AI may receive meaningless identifiers.

**LOW / POLISH**
16. `media_type="text_plain"` invalid MIME on Instagram verification (webhook.py:280).
17. Duplicated HMAC verification logic (`verify_fb_signature` in utils/security.py:254 vs `_verify_meta_signature` webhook.py:531) and duplicated tenant-ownership checks in test_chat.py (vs `get_tenant`).
18. Inconsistencies: ConversationListResponse omits page echo (schemas/conversation.py:27); product GET-by-id returns inactive items while list hides them (products.py:153-157 vs product_service.py:103-104); `total_spent` status whitelist hardcoded twice (customers.py:71, 113); notes endpoint overwrites while status endpoint appends (orders.py:159-161 vs 177).
19. IG webhook lacks `object == "instagram"` check (webhook.py:294-295); referral events silently dropped (webhook.py:94-95, messenger dispatch has no referral branch).
20. `uuid.UUID(payload["sub"])` in `get_current_user` can raise on forged token (dependencies.py:32); `status` filter on order list is free-form (silent empty results on typo) (orders.py:119).
21. Manual order create overwrites existing customer's name/address silently (orders.py:80-84); `quantity` allows 0/negative (schemas/order.py:66); no phone-format validation anywhere (Egypt-specific E.164/01x validation absent).
22. Shared single `FB_VERIFY_TOKEN` default `"zemest-verify-token"` for all 3 platforms (config.py:40) — must be overridden in prod; a leaked app-level token verifies all tenants' webhooks.

**POSITIVE (for balance)**: consistent `get_tenant` ownership gate on every tenant route (no IDOR found); fail-closed webhook signatures with constant-time compare; JWT decode with pinned algorithm + mandatory exp; order state machine; per-row CSV error reporting; `selectinload` used where it matters (conversations, orders); server-side price computation; soft deletes for products.

---

## 10. Quality Rating per File (1-10)

| File | Score | Justification |
|---|---|---|
| `router.py` | **8** | Clean, minimal, correct composition of 14 routers; would be 9-10 with an explicit dependency/prefix policy and a guard against path-shadowing ordering. No logic to get wrong. |
| `auth.py` | **5** | Correct and minimal, but: no rate limiting (docstring-mismatch), no refresh/logout endpoints despite full machinery existing, register double-hash + duplicate-email race, FB login trust gap (no app_id check), no password policy, register leaks email existence (acceptable trade-off, still). |
| `conversations.py` | **7** | Tight, correct tenant scoping, eager loads done right, proper pagination bounds; loses points for unbounded message loading, no filters/search, non-standard list envelope (no page echo), read-only surface. |
| `customers.py` | **5.5** | Functional with search + 360° view, but the N+1 aggregate loop is a serious scale defect, untyped detail response, duplicated status whitelist, no-null-update semantics, no phone validation. |
| `orders.py` | **6** | Good state machine and consistent service delegation; docked for retry-api idempotency hole (dup external orders), untyped payment dict, order-number collision 500s (service-side but surfaced here), notes overwrite-vs-append inconsistency, synchronous external API call in request path. |
| `products.py` | **6.5** | Genuinely nice flexible-attribute design and CSV UX; docked for SSRF surface on import-url, untyped dict body, CSV decode 500s, no upload size cap, inactive-product inconsistency, per-row tree rebuild cost. |
| `webhook.py` | **7** | Best file of the set: fail-closed constant-time signatures, fast-ACK + background processing, owner-bypass routing, dedup sentinel, all three platforms handled; docked for duplicated sig code, no retry/DLQ (silent message loss), log-only receipts, invalid IG media_type, missing object check, no rate limiting. |
| `test_chat.py` | **4** | Auth+ownership is right, but it's a test surface shipped to prod with real DB writes and real LLM cost, duplicated ownership logic, 500-on-bad-UUID, racy token reporting, bare `except: pass`. Should be feature-flagged or removed. |

**Overall API-layer-1 grade: ~6/10** — consistent and secure tenancy enforcement (the hardest part to retrofit) is done right, but production-hardening basics (rate limiting actually applied, refresh/revocation wired in, idempotency on retry-api, SSRF guard, N+1 fixes) are missing or half-built.
