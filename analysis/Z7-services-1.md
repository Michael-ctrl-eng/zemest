# Z7 — Business Services Layer 1: Deep Analysis
**Scope:** `app/services/auth_service.py`, `tenant_service.py`, `owner_chat.py`, `order_service.py`, `order_api_service.py`, `product_service.py`, `__init__.py` (1,132 LOC total)
**Method:** every line of all 7 files read; all call sites traced and verified by grep across the repo (webhook.py, agent.py, api/{auth,tenants,orders,products,facebook,crawl}.py, tasks/{crawl_tasks,notification_tasks}.py, knowledge/{tree_sync,retriever}.py, utils/security.py, models/*, schemas/*, config.py, requirements.txt, MASTER_PROMPT.md).

**Architecture note:** `services/__init__.py` is empty (0 lines) — services are imported as modules (`from app.services import order_service`). All services follow the same contract: accept `AsyncSession`, **`flush()` but never `commit()`** — commits live in `get_db` teardown (API layer), explicit `db.commit()` in webhook (webhook.py:170) and crawl paths. Consistent, but mixes transaction responsibility across layers.

---

## 1. Auth Service (`auth_service.py`, 67 lines, 3 functions)

### `register_user(db, name, email, password) -> User` (lines 14–27)
- SELECT user by email → raise `ValueError("Email already registered")` if found.
- Creates `User(id=uuid4(), name, email, hashed_password=hash_password(password))`, `flush()`, returns ORM object.
- **Password hashing:** `hash_password` = `passlib.context.CryptContext(schemes=["bcrypt"]).hash()` (utils/security.py:34,51-52) — **default bcrypt cost = 12 rounds**, no explicit round override; deps: `passlib[bcrypt]==1.7.4` + `bcrypt==4.1.3` (requirements.txt:15-16) — the unmaintained-passlib/bcrypt-4 combo (version-probe warning, still functional).
- **No password policy** — `RegisterRequest.password: str` (schemas/auth.py:9) has no min_length/complexity; bcrypt silently truncates >72 bytes.

### `login_user(db, email, password) -> str` (lines 30–38)
- SELECT by email; `if not user or not user.hashed_password` → ValueError (correctly blocks FB-only accounts with NULL hash from password login).
- `verify_password` (bcrypt `CryptContext.verify`) → ValueError("Invalid credentials") — same message for unknown-email and wrong-password (no message-based enumeration), though **timing enumeration exists** (bcrypt verify runs only when user exists).
- Returns `create_access_token({"sub": str(user.id)})` — HS256 JWT, `exp`+`iat` embedded, 24h lifetime (`JWT_ACCESS_TOKEN_EXPIRE_MINUTES=1440`, config.py:23), secret default `"change-me-to-a-random-secret-key"` (config.py:21). **No `type` claim** — access tokens and (unused) refresh tokens share a secret/alg.

### `login_with_facebook(db, fb_access_token) -> str` (lines 41–67)
- GET `{FB_GRAPH_API_URL}/me` (v21.0) with `fields=id,name,email`, token in query params (standard Graph pattern).
- Non-200 → ValueError("Invalid Facebook token").
- Match user by `User.fb_user_id` (unique, indexed — models/user.py:15); if absent, **auto-provision** user with `email=fb_data.get("email")` (may be None — `email` is nullable).
- Returns same 24h access token.
- **No token provenance verification:** no `debug_token`, no `app_id` check, no `appsecret_proof` — any valid FB user token from *any* app is accepted (Z4 flagged this; confirmed here).
- **No email linkage:** a user registered by email, then logging in via FB, gets a *second* account (lookup is by fb_user_id only, never by email).

### Session management
**None.** No refresh-token issuance (the full refresh/revocation machinery in utils/security.py:111-248 — `create_refresh_token`, `verify_refresh_token`, Redis denylist — is never called by any route, confirmed by Z4 grep). No logout, no token revocation, no per-session state. One 24h bearer token per login.

---

## 2. Tenant Service (`tenant_service.py`, 173 lines, 4 functions)

### `create_tenant(db, owner: User, **kwargs) -> Tenant` (lines 10–14)
- `Tenant(id=uuid4(), owner_id=owner.id, **kwargs)`, flush, return.
- Pure passthrough — field validation is entirely the API schema's job (`TenantCreate`: page_name, fb_page_id, page_access_token, website_url, business_phone, business_email, notification_pref — schemas/tenant.py:8-15).
- Called from POST /api/tenants (tenants.py:39) and FB page-connect flow (facebook.py:41-47). **No tenant-count limit per owner**; duplicate `fb_page_id` hits the DB unique constraint (models/tenant.py:18) → unhandled IntegrityError → 500 (not 409).

### `get_user_tenants(db, user) -> list[Tenant]` (lines 17–21)
- All tenants where `owner_id == user.id AND is_active == True`. No pagination (acceptable — few tenants/user).

### `update_tenant(db, tenant, **kwargs) -> Tenant` (lines 24–29)
- `for key, value in kwargs.items(): if value is not None and hasattr(tenant, key): setattr(...)`; flush.
- **`hasattr`-guarded mass assignment:** any ORM attribute (incl. `owner_id`, `is_active`, `id`) can be set if a caller passes it — the only real guard is the `TenantUpdate` schema at the API edge (tenants.py:66, exclude_none). Internal callers get no protection.
- **Cannot clear fields:** `value is not None` + API `exclude_none=True` means nullable fields (e.g. `free_delivery_above`, `business_email`) can never be unset.
- `fb_page_id`/`page_access_token` are updatable without re-verification (unique constraint partially protects cross-page hijack; violation → 500).

### `get_tenant_stats(db, tenant_id) -> dict` (lines 32–173)
One function, **10 sequential DB roundtrips** + 2 more result queries:
1. `products_count` (active products)
2. `orders_count` (all)
3. `pending_orders` (status='pending')
4. `active_conversations` (status='active')
5. `total_revenue` — `sum(Order.total)` where status ∈ {confirmed, shipped, delivered}
6. `total_tokens_used` (TokenUsage sum)
7. `chat_tokens` (usage_type='chat')
8. `crawl_tokens` (usage_type='crawl') — note: `owner_chat` and `retrieval` usage types are written by other modules but NOT broken out here
9. `llm_calls` (count of TokenUsage rows)
10. `today_orders` / `today_revenue` / `month_revenue` — `Order.created_at >= today_start` where `today_start = datetime.utcnow().replace(h=0,...)` (line 91) — **naive UTC, not Africa/Cairo**: the "today" boundary is off by 2–3h for all Egyptian tenants.
11. `customers_count`
12. Top-5 products: `GROUP BY OrderItem.product_name` ordered by `sum(quantity)` — same-named items merge; soft-deleted products still counted (no `is_active` join filter); includes ALL order statuses (cancelled orders count toward top-seller revenue).
13. Recent 5 orders (order_number, customer_name, total, status, created_at as str).

**Shipping config** is NOT managed here — delivery fees live on the tenant row (`delivery_inside_cairo` default 35, `delivery_outside_cairo` default 60, `free_delivery_above`; models/tenant.py:43-45) and are updated via `update_tenant` or the owner-chat `update_shipping` action. Actual fee calculation lives in `agent._calc_delivery` (agent.py:455+), not in this service.

Lazy imports inside the function (models imported at line 33-35, 63, 87-89) — circular-import avoidance pattern, repeated 3 times.

---

## 3. Owner Chat (`owner_chat.py`, 208 lines, 3 functions)

Purpose: the page owner messages their own bot on Messenger; natural-language Egyptian-Arabic commands are parsed by an LLM into JSON actions and executed directly against the DB. There are **NO hardcoded command regexes** — parsing is 100% LLM-driven; the only regexes are JSON-extraction fallbacks.

### Command catalogue (defined in `OWNER_SYSTEM_PROMPT`, lines 12–36, Egyptian Arabic)
| Action | JSON shape | Executor behavior (execute_owner_action) |
|---|---|---|
| `update_price` | `{action, product_name, new_price}` | ilike `%name%` first match → `product.price = new_price`; reply "تم تحديث سعر X إلى Y جنيه ✅" |
| `update_stock` | `{action, product_name, stock_status: in_stock\|out_of_stock\|limited}` | first match → `product.attributes["stock_status"] = stock`; Arabic label map متوفر/نفذ/محدود |
| `add_product` | `{action, name, price, description?}` | creates Product(source="owner", is_active=True); description → `attributes["description"]` |
| `delete_product` | `{action, product_name}` | first match → **soft delete** `is_active=False` |
| `update_shipping` | `{action, inside_cairo?, outside_cairo?, free_above?}` | writes `tenant.delivery_inside_cairo/outside_cairo/free_delivery_above` |
| `info_request` | `{action, query}` | **STUB** — returns canned "تمام، بسألك... (محتاج توضيح)" (line 204-205). **No order/stock querying exists** despite MASTER_PROMPT.md §7 advertising it and the task brief expecting "query today's orders". |
| unknown | — | "مش فاهم الأمر ده. جرب قول like: 'حدّث سعر المنتج X لـ 123 جنيه'" |

### `parse_owner_instruction(text, products=None) -> (action|None, token_info|None)` (lines 39–82)
- Builds grounding list: up to 20 products as `- name: price ج.م` appended to the system prompt (lines 48–52).
- Calls `chat_completion_with_usage([system, user])` (llm_client.py:45) — OpenRouter primary model with fallback chain to 2 PAID models (Z2 finding applies to owner commands too).
- JSON parsing: strip ```` ```json ```` fences via `re.sub(r"^```(?:json)?\s*|\s*```$", "", raw)` (line 70); then `json.loads`; on failure `re.search(r"\{.*\}", raw, re.DOTALL)` greedy first-`{`-to-last-`}` rescue (line 75) — the **rescue `json.loads` is unwrapped** (line 77): a malformed rescue match raises, caught by the outer `except Exception` (line 80) → returns `(None, None)` **losing token_info** → the LLM spend for that call is never recorded.
- Returns `(action_dict, token_info)` tuple — usage-tracked design.

### `_track_usage(db, tenant, token_info) -> None` (lines 85–102)
- Best-effort `TokenUsage(usage_type="owner_chat", model, prompt/completion/total tokens)`; `db.add` only (no flush — committed by webhook's `db.commit()`); swallows all exceptions with warning.

### `execute_owner_action(db, tenant, action) -> str` (lines 105–208)
- Product matching in update_price/update_stock/delete_product: `select(Product).where(tenant_id==tenant.id, name.ilike(f"%{product_name}%")).limit(1)` — **substring first-match, no user disambiguation** ("تشيكن" matches whichever of "تشيكن برجر"/"صوص تشيكن" comes first); `%`/`_` in the LLM-extracted name are unescaped.
- update_price: `new_price` used verbatim from LLM JSON — **no validation** (negative, zero, or non-numeric string accepted; no Decimal conversion — Numeric(12,2) column will error or coerce at flush).
- add_product: **bypasses `product_service.create_product`** — no duplicate/similarity check, no price validation (defaults 0), no tree sync (`_sync_product_tree` never invoked → PageIndex tree drifts out of sync with owner-added products until next manual edit).
- update_shipping: `if action.get("inside_cairo")` (line 195) — **falsy-zero bug**: setting a fee to 0 (free shipping) is silently ignored; negative fees accepted; no range validation.
- All replies in Egyptian Arabic with ✅ emoji — consistent product voice.

### Auth: owner PSID verification (webhook.py:146)
- Routing happens in the webhook, not here: `if tenant.owner_psid and sender_id == tenant.owner_psid` → `_handle_owner_message` (webhook.py:176-214); otherwise normal customer agent.
- **CRITICAL: `owner_psid` is never written anywhere in the codebase.** Repo-wide grep shows only the model column (models/tenant.py:25), the startup DDL (main.py:50), the webhook read (webhook.py:146), and MASTER_PROMPT.md:446. No API endpoint, no service function, no admin panel, no seed sets it. **The entire owner-chat feature is unreachable** unless someone hand-edits the DB. (Verified: `update_tenant`'s schema `TenantUpdate` doesn't include `owner_psid` either.)
- Even if set: single-factor PSID equality (opaque Meta ID, not guessable — acceptable), but LLM-parsed commands mutate prices/inventory with **no confirmation step**, and product names (which can originate from web crawls / CSVs — attacker-influenced) are injected raw into the system prompt (owner_chat.py:50-56) → second-order prompt-injection surface into a privileged mutation path.
- Grounding snapshot limited to 20 most-recent products (webhook.py:193-201) — parse accuracy degrades on bigger catalogs; only name+price provided (no category/SKU context).

---

## 4. Order Service (`order_service.py`, 131 lines, 5 functions)

### `_generate_order_number() -> str` (lines 14–17)
- `ORD-{YYMMDD}-{random.randint(100,999)}` — **900 combinations per day** against a **UNIQUE constraint** (models/order.py:22). Birthday math: ~35 orders/day → >50% chance of collision → IntegrityError at flush. AI-chat orders then silently fail (`agent.py:448-450` catches and returns False); dashboard manual orders → 500. **No retry loop, no sequence.**

### `create_order(db, tenant_id, customer_id, conversation_id, customer_name, customer_phone, governorate, city, area, address_detail, payment_method, items, delivery_charge=0, notes=None) -> Order` (lines 20–75)
- **Totals:** `subtotal = Σ Decimal(str(unit_price)) × quantity`; `total = subtotal + delivery_charge`. Decimal math throughout (good — no float money).
- Creates Order (uuid4, `status` defaults to "pending" via model default), `flush()`, then loops items → `OrderItem(product_id (optional UUID), product_name, quantity, unit_price, total_price)`, `flush()`.
- **Payment handling:** `payment_method` is free-text stored as-is (default "cod"); Vodafone Cash/InstaPay verification fields (`payment_phone_last2`, `payment_trx_id`) are NOT set here — only via dashboard PATCH (orders.py:198-216); no payment verification state machine.
- **Trust boundary problems:** unit_price comes wholly from the caller — the AI agent passes 0 for unmatched products (agent.py:377, Z2's "free hallucinated items" bug) and manual orders accept any price; **quantity is never validated** (0/negative accepted); delivery_charge is caller-computed (agent `_calc_delivery` or dashboard input), never re-derived server-side.
- **No stock interaction:** ordering does not check or decrement `stock_status`; out-of-stock products remain orderable (is_active is the only gate, checked in the agent, not here).
- `api_status` left NULL on creation (migration a89fe0001 backfilled existing rows to 'not_configured' — new rows inconsistent with that convention).
- Items loop uses per-item `db.add` + one final flush — fine; no `bulk_save_objects` (acceptable at typical cart sizes).

### `get_orders(db, tenant_id, page=1, page_size=20, status=None) -> (list[Order], int)` (lines 78–99)
- Count query + page query, both tenant-scoped; optional status filter; `selectinload(Order.items)` — **no N+1** (well done); `ORDER BY created_at DESC` with offset/limit. Default ordering column has no composite index (only `idx_orders_tenant_status`) — fine at current scale.

### `get_order_by_id(db, tenant_id, order_id) -> Order|None` (lines 102–110)
- Single select, `id + tenant_id` scoped, `selectinload(items)`. Used by every order route via `get_tenant`-checked tenant — **no IDOR** (tests/security/test_idor.py exercises this).

### `update_order_status(db, order, new_status) -> Order` (lines 113–131)
- **Explicit state machine** (identical to MASTER_PROMPT.md §7):
  - `pending → confirmed | cancelled`
  - `confirmed → shipped | cancelled`
  - `shipped → delivered`
  - `delivered → []`, `cancelled → []` (terminal)
- Illegal transition → `ValueError` with allowed list → API maps to 400 (orders.py:154-157).
- No row lock (SELECT … FOR UPDATE absent): two concurrent PATCHes race last-write-wins (low practical risk — both must pass the map read from the same stale state).
- No side effects on cancel (no stock return — consistent with "no stock exists").

---

## 5. Order API Service (`order_api_service.py`, 190 lines, 4 functions)

Outbound bridge that pushes orders to a tenant-configured external endpoint (their fulfillment/ERP system). Config lives in `tenant.order_api_config` JSON (models/tenant.py:57): `{enabled, url, method, auth_type, auth_key, auth_value, auth_user, auth_pass, request_template}` — set via PATCH /api/tenants/{id} (`TenantUpdate.order_api_config`).

### `call_order_api(db, tenant, order) -> dict` (lines 21–117)
- **Config check:** `not config or not enabled or not url` → sets `order.api_status="not_configured"`, flush, return.
- **Auth (3 modes, lines 37–45):** `api_key` → custom header (default `X-API-Key`); `bearer` → `Authorization: Bearer <value>`; `basic` → b64 `user:pass`. Secrets stored **plaintext in the tenant JSON column** and echoed back in TenantResponse (tenants.py:27).
- **HTTP:** new `httpx.AsyncClient(timeout=30.0)` per call; GET passes the filled dict as `params`; any other method (default POST) sends `json=body`. Method comes from config, upper-cased, **not validated** against a whitelist (e.g. "DELETE" would be sent).
- **Success path (2xx):** extracts external ID; then **error-in-2xx detection** — parses response JSON; if `_is_error_response` → `api_status="failed"` + error message from body; else `api_status="success"`, `api_response=text[:2000]`, `api_status_code`, `api_called_at=utcnow()`, `api_external_id`.
- **Failure path:** non-2xx → failed with `response_text[:200]` in the return dict; `httpx.TimeoutException` → failed, code 0, "Request timed out after 30 seconds"; generic Exception → failed, `str(e)[:500]`.
- **Status tracking model:** `api_status ∈ {success, failed, pending, not_configured}` (models/order.py:33) — "pending" is never actually used; `api_response` capped at 2000 chars (good hygiene).
- **No automatic retries, no backoff** — despite the task brief mentioning "retries", there are none in code; the only retry is the human-driven endpoint.
- **⚠️ Never auto-invoked:** the docstring says "Call external order placement API after order is created" (lines 1-5), but the ONLY call site in the entire repo is the manual dashboard endpoint POST /orders/{id}/retry-api (api/orders.py:193-194). Orders created via AI chat (`agent._create_order_from_data`) or the manual dashboard POST never trigger it. The external-bridge feature is **manual-only / effectively dormant**. (Verified: agent.py and notification_tasks.py only call `notify_new_order`.)
- **Retry endpoint has no idempotency guard** (orders.py:182-195): re-submits orders whose `api_status` is already "success" → duplicate real orders at the merchant (Z4 finding, confirmed at service level — no `api_status` check anywhere in `call_order_api`).
- **SSRF:** `url` is tenant-owner-supplied with **no scheme/host validation** (line 32) → an owner (or anyone who can PATCH tenant settings) can target `http://redis:6379`, `http://localhost:8000/admin/...`, cloud metadata, etc.; the response body is stored in `order.api_response` and returned by GET /orders → read-back SSRF.

### `_fill_template(template_str, order) -> dict` (lines 120–158)
- Builds `items_json` (name/qty/price/total, `ensure_ascii=False`) from `order.items`.
- **Naive `str.replace` substitution** of 15 placeholders: customer_name/phone, governorate, city, area, address_detail, payment_method, payment_phone_last2, payment_trx_id, subtotal, delivery_charge, total (as `str(float(...))` — **float conversion of Decimal money** for the wire format), order_number, notes, items_json.
- **No escaping:** customer-controlled values (name, address, notes) are substituted raw into a JSON template — a name containing `"`/`\` breaks the JSON; a crafted name can **inject arbitrary fields into the outbound payload** (template injection).
- Parse failure → logs warning, returns `{}` → **POSTs an empty object** to the merchant API (silent functional failure; order marked success if 2xx).
- Non-JSON templates (XML/form) unsupported by design; GET with a non-dict body sends no params.

### `_extract_order_id(response_text) -> str|None` (lines 161–177)
- json.loads; checks keys `order_id, id, orderId, order_number, orderNumber, reference` at top level, then inside `data.{order_id,id,orderId}`. Misses other nestings (`result.id`, arrays) — minor coverage gap.

### `_is_error_response(data) -> bool` (lines 180–190)
- Heuristics: truthy `error` (except literal `True` — quirk: `{"error": true}` treated as NOT an error), `success is False`, `status ∈ {error, failed, failure}`. Reasonable industry-pattern coverage.

---

## 6. Product Service (`product_service.py`, 363 lines, 11 functions)

### `create_product(db, tenant_id, name, price, source="manual", source_ref=None, attributes=None) -> Product` (lines 14–43)
- Duplicate check (`_check_duplicate`), then `Product(uuid4, tenant_id, name, price, source, source_ref, attributes or {})`, flush, then **`_sync_product_tree`** (rebuild PageIndex product tree, "zero LLM cost"), return product.
- **Signature is strict (no **kwargs)** → **breaks its own caller:** `api/facebook.py:77-89` (sync-catalog) calls it with `description=`, `image_url=`, `stock_status=` kwargs that don't exist → **TypeError on the first product** → 500; the surrounding `except ValueError` doesn't catch TypeError. The FB catalog sync endpoint is dead code in practice (drifted against this service's signature).
- `price` type not validated (Decimal expected; crawl callers pass Decimal, FB caller passes str).

### `_check_duplicate(db, tenant_id, name, sku=None)` (lines 46–93) — raises ValueError
- **SKU check:** SELECT **ALL active products for the tenant**, then Python-loop comparing `p.attributes.get("sku") == sku` — O(n) full scan per create (attributes is JSON, unindexable here).
- **Fuzzy name check:** raw SQL `similarity(name, :name) > 0.7` via **pg_trgm** (PostgreSQL-only); >0.7 → ValueError with similarity %. Fallback: on exception whose text contains "similarity"/"no such function" → exact-name match only; other exceptions re-raised. Fragile error-string sniffing, but pragmatic portability (SQLite tests).
- TOCTOU: two concurrent identical creates both pass the check → duplicates (no DB constraint on name).

### `get_products(db, tenant_id, page=1, page_size=50, search=None) -> (list, int)` (lines 96–118)
- Tenant + is_active scoped; optional `name.ilike(f"%{search}%")` — **wildcards unescaped** (user `%`/`_` alter semantics); count + page queries; `ORDER BY created_at DESC`. No search over attributes/description/sku — name only.

### `update_product(db, product, **kwargs) -> Product` (lines 121–142)
- Fixed fields `{name, price, is_active, source, source_ref}` set via setattr; `attributes` dict merges shallowly; **any other key silently becomes a new attribute** (typo "prcie" → junk attribute, no warning). None values skipped → can't null out attributes. Tree re-sync after update.

### `delete_product(db, product) -> None` (lines 145–150)
- **Soft delete** (`is_active=False`), flush, tree sync. No hard delete path anywhere in the service; unique constraint `uq_product_source(tenant_id, source, source_ref)` therefore blocks re-importing a soft-deleted product with the same source_ref → **ValueError path via IntegrityError (500)** on re-crawl of the same URL (crawl callers catch broadly, so rows get skipped with warnings).

### `import_csv(db, tenant_id, file_content) -> dict` (lines 153–234)
- **Any-format CSV:** `csv.DictReader`; requires header row.
- **Column auto-detection** (`_find_column`): name ∈ {name, product_name, product, title, item, item_name}; price ∈ {price, cost, amount, rate, mrp, unit_price} — exact lowercase match only (no fuzzy header matching despite the docstring's "ANY CSV format" claim).
- Per row (numbered from 2, matching spreadsheet row numbers): strip name; price string cleaned of `,`, `EGP`, `ج.م`, `$` → `Decimal` (rejects ≤0 and invalid); **every other non-empty column becomes an attribute** via `_parse_value`.
- Duplicates → ValueError from create_product → counted in `skipped` + error string.
- Returns `{imported, skipped, errors (unbounded list), detected_columns}`.
- **Perf cliff:** each row → `create_product` → `_sync_product_tree` which SELECTs **all** tenant products + the whole KB tree and rewrites `tree_json`. N-row CSV = N full scans + N full JSON rewrites = **O(n²)**. A 500-row import runs ~500 tree rebuilds inside one request. Also each create flushes (autoflush amplification).
- No file-size/row cap; `errors` list unbounded (a 50k-row bad CSV → 50k error strings in the response); utf-8 strict decode (UnicodeDecodeError → 500); comma-delimiter only.
- **No stock management on import** — a stock column lands as a plain attribute; nothing maps to `stock_status` unless the header is literally `stock_status`.

### `_find_column(lower_columns, original_columns, candidates) -> str|None` (lines 237–243)
- Double loop candidate×column, exact equality; returns original-cased header. O(c×n), trivial.

### `_parse_value(val)` (lines 246–257)
- `true/yes/نعم/أيوه` → True; `false/no/لا` → False; `.` → float; int; else str. Egyptian-Arabic booleans are a nice localization touch; Arabic-Indic digits (٠-٩) unhandled.

### `get_all_products_for_context(db, tenant_id) -> list[dict]` (lines 260–270)
- All active products → `to_dict()` (model flattens attributes into the dict, models/product.py:43-55). **DEAD CODE** — zero call sites repo-wide (the agent uses `knowledge/retriever.retrieve_context`, the PageIndex-tree LLM navigator, instead).

### `search_relevant_products(db, tenant_id, query, max_results=8) -> list[dict]` (lines 273–353)
- Loads **ALL** active products into RAM per call; ≤max_results → return all.
- Scoring: query word-set minus a hardcoded **Egyptian-Arabic + English stopword list** (~45 words incl. arabizi "3ayz/3awz/enta/enti"); `score = overlap×3 + name_match(3) + SequenceMatcher(query, name).ratio()`.
- Generic queries → diverse sample across `category` attribute (with `if pd not in diverse` — **dict equality comparison**, O(n²)-ish and semantically sloppy).
- **DEAD CODE** — zero call sites repo-wide (verified). ~80 LOC of bespoke scoring superseded by retriever.py. If ever revived: full-table load per message is a per-message O(n) scan.

### `_sync_product_tree(db, tenant_id) -> None` (lines 356–363)
- Delegates to `knowledge/tree_sync.rebuild_product_tree` (SELECT all products, group by category attribute, build nodes with stock icons ✅/❌/⚠️, price, discount, description, url; merge into KB tree preserving knowledge nodes; reassign sequential node IDs; flush). Failure → warning only (best-effort, acceptable — next successful mutation rebuilds).
- Note: `rebuild_product_tree` itself issues another full product SELECT — so each create/update/delete = 2 extra queries + JSON rewrite.

### `__init__.py` (0 lines)
- Empty package marker; all consumers use module imports. No re-export surface, no service registry — consistent with codebase style.

---

## 7. Function Inventory Table

| file | function | params | returns | purpose |
|---|---|---|---|---|
| auth_service | `register_user` | db, name, email, password | User | Email/password signup; bcrypt(12) hash; duplicate-email ValueError |
| auth_service | `login_user` | db, email, password | str (JWT) | Credential check; returns 24h HS256 access token |
| auth_service | `login_with_facebook` | db, fb_access_token | str (JWT) | Graph /me lookup; find-or-create by fb_user_id; issue JWT |
| tenant_service | `create_tenant` | db, owner, **kwargs | Tenant | Tenant creation passthrough (uuid4, owner_id) |
| tenant_service | `get_user_tenants` | db, user | list[Tenant] | Owner's active tenants |
| tenant_service | `update_tenant` | db, tenant, **kwargs | Tenant | hasattr-guarded setattr update; flush |
| tenant_service | `get_tenant_stats` | db, tenant_id | dict | 12-metric dashboard aggregation (counts, revenue, tokens, top-5, recent-5) |
| owner_chat | `parse_owner_instruction` | text, products=None | (dict\|None, dict\|None) | LLM parse of Egyptian-Arabic command → action JSON + token usage |
| owner_chat | `_track_usage` | db, tenant, token_info | None | Best-effort TokenUsage row (usage_type="owner_chat") |
| owner_chat | `execute_owner_action` | db, tenant, action | str (Arabic reply) | Dispatch 6 action types; mutate products/tenant; confirmation text |
| order_service | `_generate_order_number` | — | str | ORD-YYMMDD-rand(100-999) |
| order_service | `create_order` | db, tenant_id, customer_id, conversation_id, customer_name, customer_phone, governorate, city, area, address_detail, payment_method, items, delivery_charge=0, notes=None | Order | Order + items creation; Decimal subtotal/total |
| order_service | `get_orders` | db, tenant_id, page=1, page_size=20, status=None | (list[Order], int) | Paginated tenant orders with items (selectinload) |
| order_service | `get_order_by_id` | db, tenant_id, order_id | Order\|None | Single tenant-scoped fetch with items |
| order_service | `update_order_status` | db, order, new_status | Order | State machine pending→confirmed→shipped→delivered (+cancelled) |
| order_api_service | `call_order_api` | db, tenant, order | dict {status, code, error?, external_id?} | Outbound HTTP to tenant endpoint; persists api_* fields |
| order_api_service | `_fill_template` | template_str, order | dict | {{placeholder}} replace; items_json; JSON parse ({} on failure) |
| order_api_service | `_extract_order_id` | response_text | str\|None | Pull external ID from common keys (top-level + data.*) |
| order_api_service | `_is_error_response` | data (dict) | bool | Detect error-in-2xx ({error}/{success:false}/{status:error…}) |
| product_service | `create_product` | db, tenant_id, name, price, source="manual", source_ref=None, attributes=None | Product | Create + duplicate check + tree sync |
| product_service | `_check_duplicate` | db, tenant_id, name, sku=None | None (raises ValueError) | SKU full-scan + pg_trgm similarity>0.7 name check |
| product_service | `get_products` | db, tenant_id, page=1, page_size=50, search=None | (list[Product], int) | Paginated active-product list; ilike name search |
| product_service | `update_product` | db, product, **kwargs | Product | Fixed fields + unknown-key→attributes merge; tree sync |
| product_service | `delete_product` | db, product | None | Soft delete (is_active=False) + tree sync |
| product_service | `import_csv` | db, tenant_id, file_content | dict {imported, skipped, errors, detected_columns} | Any-header CSV import; auto name/price column detect |
| product_service | `_find_column` | lower_columns, original_columns, candidates | str\|None | Exact-match header detection |
| product_service | `_parse_value` | val (str) | bool\|int\|float\|str | Natural-type coercion incl. Arabic booleans |
| product_service | `get_all_products_for_context` | db, tenant_id | list[dict] | Flat dicts for AI context — **DEAD CODE** |
| product_service | `search_relevant_products` | db, tenant_id, query, max_results=8 | list[dict] | Word-overlap + SequenceMatcher ranking — **DEAD CODE** |
| product_service | `_sync_product_tree` | db, tenant_id | None | Delegate to tree_sync.rebuild_product_tree; warn-only |
| services/__init__ | — | — | — | Empty package marker |

---

## 8. Cross-Cutting Analysis

**Transaction boundaries.** Uniform service contract (flush-only) is genuinely good for composability: webhook handler, agent flow, and API routes each own their commit. But: (a) webhook commits at line 170 *after* `send_text_message` — an outbound-API failure mid-flow leaves partial state; (b) agent dispatches Celery `send_order_notification.delay()` after flush but before any commit — the Z5-identified worker race (worker may not see the order row); (c) `call_order_api` flushes per branch — retried through the API route whose commit happens in `get_db` teardown — a crash between external call and teardown loses the api_* audit trail (order exists at merchant, shows "never called" locally).

**Tenant scoping.** Exemplary consistency: every Product/Order/Conversation/TokenUsage query filters `tenant_id`, and object-passing (`tenant` ORM instance) is used where possible. No IDOR surface at the service layer (backed by tests/security/test_idor.py). The one weak spot is `update_tenant`'s hasattr-setattr (schema is the only guard) and the order-api URL (tenant-owned config can target infra).

**N+1 / query-shape risks.** `get_orders`/`get_order_by_id` use selectinload — clean. `get_tenant_stats` = 12 sequential roundtrips per dashboard load (chatty, not N+1; trivially mergeable into 2-3 queries). The real N+1-shaped problem is **write amplification**: every product create/update/delete runs `_check_duplicate` SKU full-scan + `rebuild_product_tree` (another full product SELECT + full KB JSON rewrite) → CSV import is O(n²); FB sync and crawl extraction paths inherit this too.

**Race conditions.**
1. Order-number collision (unique vs random, no retry) — will fire at ~35 orders/day.
2. Registration duplicate email (no DB unique; then `scalar_one_or_none` on 2 rows raises MultipleResultsFound → login 500s for that email forever).
3. `_check_duplicate` TOCTOU → duplicate products on concurrent creates.
4. `update_order_status` without row lock — benign last-write-wins.
5. `call_order_api` retry without api_status guard → duplicate external orders; concurrent retries double that.
6. Webhook dedup (fb_message_id SELECT-then-insert, no unique constraint) → Meta retry duplicates → duplicate owner actions/price changes (Z2).

**Datetime/naivety.** `datetime.utcnow()` naive everywhere (stats day boundary, order_number date, api_called_at) — Egypt (UTC+2/+3) gets wrong "today" aggregates and order-number dates after 22:00/21:00 local.

**Money handling.** Decimal end-to-end in order creation (correct); float leakage only at display/API-template boundaries (stats, `_fill_template` `str(float(...))` — wire-format only; tolerable).

---

## 9. Issues / Risks (prioritized, with file:line)

**Critical**
1. **Owner-chat feature unreachable:** `tenant.owner_psid` is never settable by any code path — webhook.py:146 routing can never fire; owner_chat.py is effectively dead in production. (models/tenant.py:25, webhook.py:146; verified repo-wide.)
2. **External order API never auto-invoked:** docstring promises post-creation dispatch; sole call site is manual retry endpoint — orders are never pushed to tenants' fulfillment systems automatically. (order_api_service.py:1-5, api/orders.py:193-194.)
3. **SSRF in order API bridge:** tenant-configurable `url`, no scheme/private-IP validation, response body stored & returned → internal-network read-back (Redis/PG/admin endpoints in the Docker network). (order_api_service.py:32,53-57; config writable via PATCH /api/tenants/{id}, tenants.py:65-67.)
4. **Order-number collision:** ORD-YYMMDD-rand(100-999) vs UNIQUE → ~50% IntegrityError/day at 35 orders; AI-flow orders fail silently (agent returns False), dashboard orders 500. (order_service.py:14-17, models/order.py:22, agent.py:448-450.)

**High**
5. **Retry endpoint duplicate-submits successful orders** (no api_status guard). (api/orders.py:182-195; order_api_service.py has none either.)
6. **Template injection / broken JSON in `_fill_template`:** customer data substituted unescaped into JSON template; malformed result → `{}` silently POSTed. (order_api_service.py:120-158.)
7. **Facebook sync-catalog TypeError:** caller passes nonexistent kwargs (`description`, `image_url`, `stock_status`) to `create_product` → 500 on first product; except-ValueError doesn't catch. (api/facebook.py:77-92 vs product_service.py:14-22.)
8. **No email uniqueness on users + `scalar_one_or_none` fragility:** registration race → duplicate rows → subsequent logins raise MultipleResultsFound (500), never the clean "Invalid credentials". (auth_service.py:15-17,31-32; models/user.py:17.)
9. **FB login accepts any-app tokens, no email linkage** → cross-app token acceptance & duplicate accounts. (auth_service.py:41-67.)
10. **CSV import O(n²) write amplification** (per-row `_check_duplicate` scan + full tree rebuild); unbounded error list; no row/size cap. (product_service.py:153-234, 41, 356-363.)

**Medium**
11. Owner `update_price`/`add_product` accept unvalidated LLM-derived prices (negative/string). (owner_chat.py:112-130, 155-173.)
12. Owner `update_shipping` falsy-zero bug — cannot set a fee to 0. (owner_chat.py:195-200.)
13. `info_request` stub — no order/stats querying despite documented capability. (owner_chat.py:204-205; MASTER_PROMPT.md §7.)
14. Second-order prompt injection: crawled/CSV product names injected into owner-command system prompt — privileged mutation path. (owner_chat.py:50-56.)
15. Owner product matching: unescaped ilike substring first-match, no disambiguation → wrong-product mutations. (owner_chat.py:118-124, 138-144, 180-186.)
16. Agent passes unit_price=0 for unmatched products; create_order trusts caller prices/quantities (0/negative). (agent.py:373-389; order_service.py:36-38, 62-71.)
17. `update_tenant` hasattr mass-assignment (schema-only guard); cannot clear nullable fields. (tenant_service.py:24-29.)
18. Owner-chat add_product bypasses duplicate-check + tree-sync → catalog/tree drift. (owner_chat.py:155-173.)
19. Stats: naive-UTC day boundary; 12 sequential queries; top-products merges same names & counts cancelled orders. (tenant_service.py:91, 32-173, 122-133.)
20. `parse_owner_instruction` rescue `json.loads` unwrapped → loses token_info on malformed rescue. (owner_chat.py:75-78.)
21. Unescaped ilike wildcards in product search & owner matching. (product_service.py:111-112; owner_chat.py:121.)
22. No rate limiting / lockout on login; no password policy; bcrypt 72-byte silent truncation. (auth_service.py:30-38; schemas/auth.py:9.)
23. Soft-deleted product + `uq_product_source` blocks re-import of same source_ref → skipped rows on re-crawl. (product_service.py:145-150; models/product.py:15.)
24. Dead code: `get_all_products_for_context`, `search_relevant_products` (~95 LOC, zero callers — superseded by knowledge/retriever.py). (product_service.py:260-353.)
25. API secrets (order API auth_value/pass, page tokens) stored plaintext in tenant JSON, echoed in TenantResponse. (models/tenant.py:57; api/tenants.py:27.)

**Low**
26. `call_order_api` method not whitelisted (arbitrary verbs from config). (order_api_service.py:33,54-57.)
27. `_extract_order_id` misses non-`data` nests. (order_api_service.py:161-177.)
28. `create_order` leaves api_status NULL (vs migration's 'not_configured' convention). (order_service.py:41-58.)
29. CSV import: strict utf-8, comma-only, no delimiter sniffing; Arabic-Indic digits unhandled. (product_service.py:163, 188-190, 246-257.)
30. Login timing side-channel (bcrypt only runs for existing users). (auth_service.py:31-36.)

---

## 10. Quality Ratings

| File | Score | Justification |
|---|---|---|
| auth_service.py | **6/10** | Clean, minimal, correct bcrypt/JWT usage; but no email uniqueness, no FB token provenance check, no session/refresh wiring, no policy enforcement — the service is only as good as the (missing) systemic guards around it. |
| tenant_service.py | **7/10** | Simple, correct, consistently scoped CRUD; comprehensive stats with good revenue-status filtering. Docked for 12 sequential queries, naive-UTC day boundaries, hasattr mass-assignment, and unhandled unique-violation 500s. Best file of the set. |
| owner_chat.py | **5/10** | Genuinely delightful product concept with on-brand Egyptian-Arabic confirmations and token tracking; but the feature is unreachable (owner_psid never set), info_request is a stub, prices/fees unvalidated, falsy-zero shipping bug, injection-prone grounding, and first-match mutations can hit the wrong product. |
| order_service.py | **6.5/10** | Solid Decimal money math, real state machine, eager-loaded pagination, clean scoping. Docked for the order-number collision time bomb, trust-the-caller pricing/quantities, no stock integration, and no row locking. |
| order_api_service.py | **6/10** | Thoughtful bridge design (templating, 3 auth modes, error-in-2xx detection, response caps, external-ID extraction); but it's never wired to order creation, has an SSRF hole, unescaped template substitution, no retry policy, and a duplicate-submit retry endpoint. |
| product_service.py | **6/10** | The flexible-attributes + any-CSV design is the most clever data modeling in the repo; duplicate detection (pg_trgm + fallback) is a real feature. Docked for O(n²) import via per-row tree rebuilds, SKU full-scans, ~95 LOC dead code, unescaped ilike, and the signature drift that breaks its FB caller. |
| services/__init__.py | **n/a** | Empty package marker — appropriate. |

**Layer average ≈ 6/10** — clean, consistently tenant-scoped service functions with correct money math and a genuine eye for product UX (Egyptian-Arabic owner commands, any-CSV import), undermined by two unreachable/dormant flagship features (owner chat, auto order dispatch), a handful of production time bombs (order-number collision, registration race), missing input validation at privileged mutation points, and O(n²) write amplification in the import path.
