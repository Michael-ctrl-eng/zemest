# E6 — Channel Connection Audit (Facebook / Instagram / WhatsApp): REAL vs MOCK

Agent: E6 (error-finder, read-only). Date: 2026-09-01.
Scope: channel-connection flows only. Skipped per briefing: X-Hub-Signature-256 verification and outbound send paths (R2 verified: fail-closed + real httpx sends), text_plain typo + duplicated sig helpers + hardcoded v21.0 (R2 nits), dashboard-home IG/WA chip fields (E5).

Code read: `repos/zemest/app/api/{channels,facebook,webhook,tenants,auth}.py`, `app/services/{facebook_service,auth_service}.py`, `app/models/tenant.py`, `app/schemas/tenant.py`, `app/config.py`, `daemon_backend.py` (log path); frontend `src/app/dashboard/[tenantId]/channels/page.tsx`, `src/lib/zemest-api.ts`, `src/app/api/zemest/[...path]/route.ts`, `src/app/api/auth/facebook/route.ts`, `src/middleware.ts`, `next.config.ts`, `Caddyfile`.
Live: daemon :8000 untouched (never stopped/restarted); owner JWT login; 3 fake-token connects; BFF cookie chain through :3000; webhook-URL routing matrix; error-path probes. Real DB never modified (validation-before-store proved — status still `connected:false` after all tests).

---

## 1. Flow traces

### 1.1 Messenger (Facebook Page) connect — REAL, manual-token path

```
UI form (channels/page.tsx:219, token+optional page id)
 → channelsApi.connectMessenger (zemest-api.ts:406)
 → BFF /api/zemest/tenants/{id}/channels/messenger (catch-all proxy, cookie→Bearer)
 → channels.py:194 connect_messenger
 → _graph_get(page_id||"me", token, "name,followers_count,category,link")  [REAL Graph GET]
 → subscribe_page_to_webhook(resolved_id, token)  [REAL Graph POST /subscribed_apps, non-fatal]
 → tenant.fb_page_id / page_access_token / page_name / messenger_meta → commit
```
Live-proven: fake token → `HTTP 400 {"detail":"OAuthException 190: Malformed access token"}` in ~0.2 s (real Meta round-trip; backend.log:1847-1849). Nothing stored on failure. Webhook-subscribe failure is reported honestly via `webhook_subscribed:false` + `webhook_note`.
Tokens stored: `tenants.fb_page_id`, `page_access_token` (Text, plaintext), `messenger_meta` (JSON). owner_psid/ig_access_token/wa_* columns untouched by this flow.

### 1.2 Facebook OAuth authorize flow — BROKEN / dead-end (precise detail of R1's finding)

Three disconnected half-flows, none complete:

1. **Login-page FB button** (`auth-page.tsx:247` → `GET /api/auth/facebook`, route.ts:58):
   `307 → https://www.facebook.com/v18.0/dialog/oauth?client_id=demo_client_id&redirect_uri={origin}/api/auth/facebook/callback&scope=email&response_type=code`
   - `client_id=demo_client_id` fallback (`NEXT_PUBLIC_FB_APP_ID` unset) — live-verified 307.
   - **No `state` parameter at all** (CSRF-undefended).
   - **Callback route does not exist** — live `GET /api/auth/facebook/callback?code=x` → **404**.
   - Graph version v18.0 here vs backend v21.0 (R1). Also `redirect_uri` is `http://localhost:3000` in this env (Meta requires HTTPS redirect URIs).
2. **Backend oauth-url** (`channels.py:404`): builds a proper consent URL with real page+IG scopes, but
   - `state = f"tenant:{tenant.id}"` (channels.py:432) — guessable (tenant UUID is public in the dashboard URL), never stored, never validated anywhere;
   - `redirect_uri = {request_url}/api/zemest/facebook/oauth/callback` where `request_url` is a **client-controlled query param** (default `https://localhost:3000`);
   - target route live-probed → **404** (BFF proxies it to backend `/api/facebook/oauth/callback`, which doesn't exist; facebook.py has only /pages, /connect, /{tenant_id}/sync-catalog);
   - currently returns `{"ready": false}` (FB_APP_ID unset) — **dead code: the frontend never calls it** (no `oauth` method in channelsApi, page never references `status.oauth.ready`).
3. **Token exchange: DOES NOT EXIST.** Repo-wide grep for `fb_exchange_token|oauth/access_token|dialog/oauth` → only the 3 URL-builders; zero code→token exchange anywhere. The only real "exchange" is `POST /api/auth/facebook` (backend) which validates an already-obtained user token live (Graph /me, auth_service.py:45) and issues our JWT — a token→JWT login, not OAuth.

**Verdict: browser OAuth is a mock-shaped dead end; the ONLY working Facebook connect is manual token paste (1.1).**

### 1.3 Instagram connect — REAL validation, PARTIAL setup

`channels.py:250` → `_graph_get(ig_user_id, token, "username,profile_picture_url,followers_count")` before storing `ig_user_id`, `ig_access_token`, `instagram_meta`. Live-proven 400 on fake token (backend.log:1851). Stored only after validation.
GAP: no webhook subscription on connect — `subscribe_instagram_to_webhook` (facebook_service.py:67) has **zero call sites** (18-e flagged; still unfixed). IG DMs will not flow until the merchant manually configures the Meta App dashboard (which is precisely the flow broken by F1 below).

### 1.4 WhatsApp connect — REAL validation, PARTIAL setup

`channels.py:281` → `_graph_get(phone_number_id, token, "display_phone_number,verified_name,quality_rating")` before storing `wa_phone_number_id`, `wa_access_token`, `wa_waba_id`, `whatsapp_meta`. Live-proven 400. No WABA/phone-number subscription call on connect either.

### 1.5 Channel status — REAL live re-validation

`GET /channels` re-validates every stored token against Graph (Messenger/IG/WA) and sets `connected:false` + real `error` on rejection (code: 119-173). Honest. (Perf note — 3 sequential external calls per GET, no cache — already 18-c, not re-reported.)

### 1.6 Fabricated "connected" 200 without a Meta call

Grepped every `"connected": True` in `app/` — only the 3 in channels.py, **all after a real `_graph_get`**. The channels family itself contains NO canned success. Adjacent honesty gaps found elsewhere: F5 (tenant PATCH/POST bypass) and F8 (facebook pages swallows Meta errors → 200 `{"pages":[]}`).

### 1.7 BFF channels routes

`src/app/api/channels/**` **does not exist**. All channel traffic flows through the universal `/api/zemest/[...path]` proxy — live-verified end-to-end with cookie (status 200 + fake IG connect → real Meta 400 passthrough).

---

## 2. Token handling security

- **NOT returned to frontend (good)**: `TenantResponse` is built via explicit whitelist (tenants.py:14-30) — no tokens, no meta. Channel status/connect/test responses contain IDs and display info only (live payloads inspected).
- **Returned unmasked (bad, F8)**: `GET /api/facebook/pages` → `get_user_pages` requests `fields=id,name,access_token` and returns Graph's raw rows → **per-page access tokens in the JSON body** (auth-required, currently frontend-unused).
- **Logged in plaintext (bad, F2)**: httpx INFO logging prints the full URL incl. `access_token` query param on EVERY Graph call — live-proven 3× in backend.log (lines 1853, 1856, 1910 with fake tokens). Real page/user tokens would be persisted in `repos/zemest/backend.log`.
- **Tokens in query strings of OUR API (bad, F2b)**: `/api/facebook/pages?fb_access_token=…` (GET) and `/api/facebook/connect?page_access_token=…` (POST scalar params default to query) → uvicorn access log prints them (live-proven lines 1855, 1858).
- **Storage**: plaintext `Text` columns on `tenants` (18-e flagged encryption-at-rest — cross-ref).
- **FB_VERIFY_TOKEN** default `"zemest-verify-token"` (config.py:40), no prod guard (E10 cross-ref). Live webhook verify: correct token → challenge echo 200; wrong token → 403 (through :8000 and through BFF path).
- **OAuth state**: `tenant:{id}` guessable + never validated (dead flow, F3/F10).

---

## 3. Live-test evidence (all safe, read-only or validation-only)

| Test | Result |
|---|---|
| POST messenger/instagram/whatsapp connect w/ fake token (:8000, JWT) | 400 `OAuthException 190: Malformed access token` ×3; nothing persisted (status unchanged) |
| backend.log outbound Meta attempts | 3 httpx GETs to graph.facebook.com/v21.0 logged (full URLs w/ tokens) |
| Same fake IG connect through BFF (:3000, cookie) | 400 passthrough, Graph attempt logged |
| GET /channels status (JWT + via BFF cookie) | 200, all `connected:false`, honest |
| GET /channels/oauth-url | `{"ready": false, "FB_APP_ID not configured…"}` |
| GET :3000/api/webhook/messenger (URL the UI tells merchants to paste) | **404** |
| GET :3000/api/zemest/webhook/messenger?hub.verify_token=zemest-verify-token | 200 `42` (challenge echo); wrong token → 403 |
| GET :3000/api/auth/facebook | 307 → `…v18.0/dialog/oauth?client_id=demo_client_id&redirect_uri=http://localhost:3000/api/auth/facebook/callback&scope=email&response_type=code` (no state) |
| GET :3000/api/auth/facebook/callback & /api/zemest/facebook/oauth/callback | 404 / 404 (no callback route, no backend exchange) |
| GET /api/facebook/pages?fb_access_token=FAKE | 200 `{"pages":[]}` (Meta rejection hidden); token in uvicorn access log |
| POST /api/facebook/connect?page_access_token=FAKE | 400 `Failed to subscribe page to webhook` (real Graph 400); token in access log |
| POST /channels/{platform}/test while unconnected | 400 ×3 with clean messages |
| DELETE /channels/messenger (idempotent, unconnected) | 200 `{"connected": false}` |
| DELETE /channels/telegram | 404 `Unknown platform` |

---

## 4. Disconnect / reconnect / expired-token

- **Disconnect** (`channels.py:318`): clears the platform's columns + meta, commits. Live: idempotent 200; unknown platform 404. Does NOT unsubscribe the page at Graph (F9) — after disconnect, Meta keeps delivering events; webhook finds no tenant (`fb_page_id=None`) → warning logged, events silently dropped, merchant gets no signal.
- **Reconnect**: identical POST path → re-validated live, overwrites columns — works (by design).
- **Expired/revoked token**: status endpoint re-validates → `connected:false` + real Graph error surfaced in the UI red banner (`channels/page.tsx:327-334`) — honest. Webhook send path logs `AUTH ERROR … token may be expired/revoked` (webhook.py:162-163) but nothing notifies the merchant or flags the channel state. **No refresh path exists** (no fb_exchange_token anywhere — R1) → the only remedy is manual re-paste; page tokens are permanent per R1, but IG/WA system-user tokens do expire.

---

## 5. Findings (severity, location, issue, suggested fix — NOT implemented)

| # | Sev | Location / flow | Issue | Suggested fix |
|---|---|---|---|---|
| F1 | **HIGH** | channels/page.tsx:160-176 + channels.py:178-182 webhook_urls | The copy-able webhook callback URL shown to merchants (`{origin}/api/webhook/messenger`) is **404 on the Next origin** (live-proven). Backend returns backend-relative paths; frontend prefixes `window.location.origin`. Meta webhook setup following the UI ALWAYS fails. Working public URL is `/api/zemest/webhook/messenger` (challenge echo verified through BFF). | Return full public URLs (host-aware) or add a BFF rewrite `/api/webhook/* → :8000/api/webhook/*`; update `webhook_urls` payload + UI to the same source of truth. |
| F2 | **HIGH** | httpx INFO logs (every Graph call, e.g. backend.log:1853/1856/1910) + uvicorn access log for query-param APIs (facebook.py:12,21) | **Access tokens persisted in plaintext in logs**: httpx logs full URL incl. `?access_token=…`; `/api/facebook/pages` & `/connect` take tokens as QUERY params which uvicorn prints. | Move Graph auth to POST bodies/headers where possible (Meta supports `GET` with token in body only for some endpoints — at minimum disable httpx INFO logs or redact `access_token`); change `/api/facebook/pages|connect` to JSON-body request models. |
| F3 | **HIGH** | OAuth flow (BFF auth/facebook/route.ts:58-63; channels.py:404-436; facebook.py) | Browser OAuth is a dead end: no callback route (404 live), no code-exchange endpoint (grep-proof), login button uses `demo_client_id` + **no state** + v18.0; oauth-url's `state="tenant:{id}"` is guessable and never validated; `request_url` is client-controlled. Even with FB_APP_ID set, consent → 404. | Implement callback route + server-side code exchange (+ `fb_exchange_token` for long-lived/page tokens, page picker via `/me/accounts`), random single-use state bound to session, fixed server-side redirect_uri; align Graph version. (R1's arctic/authlib design applies.) |
| F4 | **MED** | owner_psid (models/tenant.py:25; channels.py:359-377; webhook.py:146; schemas/tenant.py TenantUpdate) | **`owner_psid` is never writable**: zero writes repo-wide; TenantUpdate lacks the field; error text tells merchants to "set your PSID in Settings" (no such field) and claims it's "captured automatically" (webhook never writes it). Consequences: Messenger/IG **Send-test-message button always 400s** (frontend never sends `recipient`), and the owner-chat bypass (webhook.py:146) is unreachable → the page owner's own DMs are answered as a customer by the agent. | Add `owner_psid` to TenantUpdate + settings UI; capture PSID on first owner→page message in webhook; or pass `recipient` in the test form. |
| F5 | **MED** | tenants.py:59-70 PATCH + TenantCreate (schemas/tenant.py:11) | `PATCH /api/tenants/{id}` and `POST /api/tenants` accept `page_access_token` / `fb_page_id` with **no Graph validation** — bypasses the "validated before stored" guarantee; webhook/sends would then use an unvalidated token. | Strip token fields from TenantCreate/TenantUpdate; route all token writes through the channel connect endpoints. |
| F6 | **MED** | channels.py:250-311 (connect_instagram / connect_whatsapp); facebook_service.py:67 | IG/WA connect never subscribes webhooks (`subscribe_instagram_to_webhook` = 0 call sites; no WABA subscribe) — connected accounts won't receive events until manual Meta-app setup (which itself hits F1). (18-e flagged; still unfixed.) | Call subscribe_instagram_to_webhook on IG connect (non-fatal, reported like Messenger's) + WABA/phone subscription for WA. |
| F7 | **MED** | channels.py:206-211 connect_messenger (code-trace) | With an explicit `page_id` + a **user** token, Graph `GET /{page_id}` returns public page data 200 → connect "succeeds", stores a user token as the page token (subscribe fails but is non-fatal) → `connected:true` while messaging later fails. | Require `GET /me` (page-token proof) always, or verify `subscribed_apps` success / `perms` before storing; reject when subscribe fails with an auth error. |
| F8 | **MED-LOW** | facebook.py:11-18 + facebook_service.py:12-27 | `GET /api/facebook/pages` returns per-page `access_token` unmasked in JSON, and swallows Meta rejections → `200 {"pages":[]}` (invalid token indistinguishable from "no pages" — a fabricated-success shape). Frontend-unused today. | Mask tokens (last 4) or drop the field; surface Graph errors as 4xx instead of []. |
| F9 | **LOW** | channels.py:318-341 disconnect | Disconnect only clears DB columns; page stays subscribed at Meta → events keep arriving and are silently dropped (webhook "No tenant for page" warnings), no signal to merchant; no deauthorization of the token. | Best-effort `DELETE /{page-id}/subscribed_apps` on disconnect; log/notify subscription residue. |
| F10 | **LOW** | channels.py:429-436 oauth-url | `state` = `tenant:{id}` guessable + unvalidated; `request_url` query param controls `redirect_uri` (open-redirect-shaped once FB_APP_ID exists). Latent (endpoint dead while FB_APP_ID unset). | Random server-generated state persisted server-side; derive redirect_uri from settings, not client input. |
| F11 | INFO (cross-refs) | config.py:40; tenants columns; channels status | FB_VERIFY_TOKEN default + no prod guard (E10); tokens plaintext at rest (18-e); 3 sequential Graph calls per status GET, no cache (18-c); v18.0/v21.0 mismatch (R1). Listed for completeness — owned by prior agents. | See prior reports. |

## 6. Verdicts

| Flow | Verdict |
|---|---|
| Messenger connect (manual token) | **REAL** — live Graph validation + real webhook subscribe attempt, honest failures |
| Instagram connect | **REAL validation** / PARTIAL setup (no webhook subscribe) |
| WhatsApp connect | **REAL validation** / PARTIAL setup (no WABA subscribe) |
| Facebook OAuth (browser) | **BROKEN / dead end** — no callback, no exchange, demo client-id, no state |
| Channel status | **REAL** live re-validation, honest revoked-token errors |
| Disconnect | **REAL** (DB-only; Graph-side residue) |
| Test message | **REAL send path, unusable default** (owner_psid never settable) |
| Canned "connected" without Meta call | **NONE in channels.py**; bypass exists via tenant PATCH (F5) |
