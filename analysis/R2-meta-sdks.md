# R2 — Meta Graph API / WhatsApp / Instagram SDK & Tooling Research

**Task ID:** R2 · **Agent:** R2 (github-research) · **Scope:** GitHub research only (no code changes)
**Method:** `curl api.github.com` — 20 calls total (searches + direct lookups; rate limit hit on final lookups, fallback to lineage/search evidence as instructed).
**Repos analyzed for context:** `repos/zemest/app/api/webhook.py`, `app/utils/security.py`, `app/services/{whatsapp,messenger}_service.py`, `app/api/channels.py` (read-only).

---

## 0. Verified current state in zemest (read-only audit)

- **X-Hub-Signature-256 validation is IMPLEMENTED on all 3 channels**, contrary to the briefing's "check status yourself":
  - Messenger: `verify_fb_signature()` in `app/utils/security.py` (L254–270).
  - Instagram + WhatsApp: `_verify_meta_signature()` in `webhook.py` (L531–548).
  - Both: HMAC-SHA256 over the **raw body**, `hmac.compare_digest` (constant-time), compare `"sha256=" + hexdigest`, **fail-closed** when `FB_APP_SECRET` is unset → 403. This is best-practice correct.
- **Outbound sends are real, not stubs** (briefing outdated): `whatsapp_service.py` posts to `graph.facebook.com/v21.0/{phone_number_id}/messages` via httpx; `messenger_service.py` has real `send_text_message / send_quick_replies / send_attachment / get_user_profile`. Gap is *feature coverage*, not stubbing: no WhatsApp templates/interactive/media-download, no IG-specific send path beyond `messenger_service` reuse.
- **Minor bug found (not fixed, report only):** `webhook.py` L280 `verify_instagram_webhook` returns `media_type="text_plain"` (should be `"text/plain"`) — Instagram GET challenge response is mislabeled.
- **Version pin risk:** `WHATSAPP_API_URL = "https://graph.facebook.com/v21.0"` is hard-coded (v21.0 is ~2y old and past Meta's deprecation window by 2026). Should be a setting (`config.py`) shared by all services.

**Headline conclusion:** For a Python/FastAPI backend talking to the **official** Meta platforms, **no third-party SDK is compelling as a dependency** — Meta archived its own official WhatsApp Node SDK (see §2), and the Python SDK ecosystem is either dead, marketing-oriented, or unofficial/ToS-violating. The winning strategy for the roadmap is: **keep the clean raw-`httpx` Graph layer, extend feature coverage using official sample patterns, and add a self-hostable tunnel for sandbox webhook testing.** Top 5 picks below are ranked by usefulness to that plan.

---

## 1. Ranked Top 5

### #1 — fbsamples/whatsapp-api-examples (Meta official samples)
| | |
|---|---|
| URL | https://github.com/fbsamples/whatsapp-api-examples |
| Stars / Forks | 290 ★ |
| Last push | 2026-07-23 (active) |
| License | NOASSERTION (Meta sample/license — reference, check before vendoring) |
| Maintenance | **Official Meta** (fbsamples org) |

**What it solves:** Canonical, current implementations of the WhatsApp Cloud API patterns the roadmap needs: webhook GET verify + `X-Hub-Signature-256` POST handling, sending text/media/templates/interactive messages, and media-id → URL resolution. It is the de-facto reference Meta points developers at (their official Node SDK is archived; see §2).

**Integration sketch (files touched):**
- `app/services/whatsapp_service.py` — add `send_template()`, `send_interactive()` (buttons/lists), `mark_message_read()` (POST `{phone_number_id}/messages` with `status: read`), `download_media(media_id)` (GET `graph…/v{V}/{media_id}` → `url`, then fetch bytes with Bearer token — needed because webhook only delivers media **ids**).
- `app/api/webhook.py` — `_process_whatsapp_message()` currently stores media ids directly into `media_urls`; resolve ids → URLs via the new service call before passing to `process_customer_message`.
- `app/config.py` — `GRAPH_API_VERSION` setting; replace hard-coded `v21.0` in `whatsapp_service.py` / `messenger_service.py` / `channels.py`.

**Verdict:** ✅ **ADOPT AS REFERENCE** (copy patterns, don't add as dependency). Zero risk, keeps the architecture official-HTTP-only. Immediate value for Task 18's WhatsApp roadmap.

---

### #2 — facebook/facebook-python-business-sdk (official Meta Python SDK)
| | |
|---|---|
| URL | https://github.com/facebook/facebook-python-business-sdk |
| Stars / Forks | 1,589 ★ / 672 forks, 100 open issues |
| Last push | **2026-08-25 (actively maintained by Meta)** |
| License | NOASSERTION (Meta Platforms custom license — not OSI-standard; review before commercial vendoring) |
| Maintenance | Official (Meta "incubator") |

**What it solves:** The only **actively maintained official** Python client for the Graph API. Primary focus is Marketing/Ads APIs, but its `FacebookAdsApi`/`FacebookRequest` core does authenticated GET/POST against *any* Graph endpoint, with typed error classes, retries, batching, and `debug_token`/`oauth/access_token` (short→long-lived page token exchange) support — exactly the token lifecycle logic `channels.py` re-implements by hand.

**Integration sketch:** `requirements.txt` (+ `facebook-business`), `app/api/channels.py` (replace hand-rolled `/oauth/access_token` + `debug_token` httpx calls with SDK session), `app/services/messenger_service.py` (optional shared Graph session). Do **not** use it for webhook parsing (it doesn't do that).

**Verdict:** ⚠️ **OPTIONAL**. Real benefits (token exchange, typed errors, versioned Graph calls) but heavy dep + non-OSI license + marketing-API baggage. Only adopt if channels.py token lifecycle grows; otherwise raw httpx (current approach) stays cleaner. Second choice only because it's official and alive.

---

### #3 — ekzhang/bore (self-hostable webhook tunnel) — with smee-client & localtunnel as alternatives
| | |
|---|---|
| URL | https://github.com/ekzhang/bore |
| Stars / Forks | 11,477 ★ / 523 forks |
| Last push | 2026-02-04 |
| License | MIT |
| Alternatives | **probot/smee-client** — 556 ★, ISC, pushed 2026-08-31 (hosted at smee.io, GitHub-owned org) · **localtunnel/localtunnel** — 22,466 ★, MIT, pushed 2025-08-29 (hosted, `lt --port 8000`, 166 open issues) |

**What it solves:** The sandbox blocker for the roadmap: Meta must reach a **public HTTPS** webhook URL, but FastAPI runs on `localhost:8000`. `bore` is a tiny Rust TCP tunnel you can self-host on the same VPS that will run production (`bore server` + `bore local 8000 --to <vps>`), keeping customer webhook traffic inside infra you control (relevant for the Egyptian-market deployment + no third party seeing signed payloads). smee.io/localtunnel are zero-setup hosted options for pure dev.

**Integration sketch:** `scripts/dev-tunnel.sh` (`npx localtunnel --port 8000` or `bore local 8000 --to $VPS`), `.env` `WEBHOOK_PUBLIC_URL` consumed by `channels.py` when subscribing the page (`POST /{page-id}/subscribed_apps`), `docker-compose.override.yml` optional service; document the 3 Meta webhook callbacks (`/api/webhook/{messenger,instagram,whatsapp}`) to paste into App Dashboard.

**Verdict:** ✅ **ADOPT** (bore for stable/self-hosted; localtunnel for quick dev; smee.io fine for throwaway). Highest immediate dev-unblock value of any tool researched.

---

### #4 — Neurotech-HQ/heyoo (Python WhatsApp Cloud API wrapper)
| | |
|---|---|
| URL | https://github.com/Neurotech-HQ/heyoo |
| Stars / Forks | 513 ★ |
| Last push | 2025-01-17 (~1.7y quiet — semi-stale) |
| License | MIT |
| Maintenance | Community, single-org; dormant |

**What it solves:** The most-starred *official Cloud API* Python wrapper: one-class client for send text/media/location/templates, and webhook validation. Mirrors exactly the surface `whatsapp_service.py` needs to grow.

**Integration sketch:** Read its `WhatsApp.send_*` methods and copy the payload shapes into `app/services/whatsapp_service.py` (template, media, interactive, creation of message status read). Optionally `pip install heyoo` behind a feature flag — but see verdict.

**Verdict:** ⚠️ **REFERENCE, NOT DEPENDENCY.** MIT + correct API, but ~20 months without a push and Meta bumps Graph versions ~every quarter → stale wrappers rot. Copy patterns; prefer own httpx layer + fbsamples (#1) for version upgrades.

---

### #5 — mobolic/facebook-sdk (community Python Graph API SDK)
| | |
|---|---|
| URL | https://github.com/mobolic/facebook-sdk |
| Stars / Forks | 2,797 ★ / 934 forks, 38 open issues |
| Last push | 2024-08-02 (~2y quiet but stable) |
| License | **Apache-2.0** |
| Maintenance | Community continuation of Facebook's original `facebook-sdk` (PyPI `facebook-sdk`) |

**What it solves:** Dead-simple generic Graph client (`graph = facebook.GraphAPI(access_token); graph.get_object("me")`, `graph.request(path, post_args=…)`) — the "connect flow" token validation `channels.py` already hand-rolls.

**Integration sketch:** `requirements.txt`; optional unified `app/services/graph_client.py` wrapping token introspection (`/me`, `/debug_token`) for `channels.py` across all three platforms.

**Verdict:** ⚠️ **SKIP / nice-to-have.** Clean license and famous, but 2y quiet, and it adds nothing the existing httpx code doesn't already do. Listed for completeness — it's the default search hit and teams often adopt it reflexively.

---

## 2. Flagged — DO NOT USE (ToS / ban risk) — researched per brief

| Tool | Stars | Pushed | Why flagged |
|---|---|---|---|
| **negebauer/wa-automate-nodejs** (wa-automate) | n/a — direct lookup 404/rate-limited this session; lineage lives on in **wppconnect-team/wppconnect** (3,411 ★, NOASSERTION, pushed 2026-09-01, very active) | 2026-09 | ⛔ **UNOFFICIAL** — automates WhatsApp **Web** via reverse-engineered protocol. Violates WhatsApp Terms of Service; accounts get **banned** (meta's anti-automation is aggressive on unofficial clients). No Cloud API, no templates, no pricing tier parity. Direct lookups for `negebauer/wa-automate-nodejs` and `wppconnect-team/wa-automate-nodejs` returned 404 this session — the family's current canonical repo is WPPConnect. **Never for a production SaaS like zemest.** |
| subzeroid/instagrapi | 6,731 ★ | 2026-08-31 | ⛔ Instagram **Private API** (reverse-engineered), not the Graph API. ToS violation + ban risk; NOASSERTION license. Tempting for "everything IG", but it is exactly what gets business accounts disabled. |
| clairton/unoapi-cloud | 255 ★ | 2026-08-17 | ⛔ Self-described *unofficial* Cloud API clone "without spend" — i.e. bypasses Meta billing. ToS + payment-terms violation, GPL-3.0. |
| fbchat-dev/fbchat / m008v/fbchat-v2 | 1,215 ★ / 122 ★ | 2024-02 / 2026-08 | ⛔ Unofficial Messenger via private endpoints (fbchat is effectively dead; v2 forks it for E2EE). Ban risk, no official send path. |
| sciyoshi/pyfacebook | 570 ★ | 2019-10 | Dead (7y), no license. |
| **WhatsApp/WhatsApp-Nodejs-SDK** (official!) | 273 ★ | 2023-06, **ARCHIVED** | ℹ️ Not a ban risk — an *omen*: Meta **archived its own official WhatsApp SDK** and points devs at raw Graph HTTP + `fbsamples`. Strong architectural confirmation that raw httpx (zemest's current approach) is the intended integration style. |

**Instagram-specific finding:** searches for Python Instagram Graph API clients return nothing mature (best hits: 9★ `paperfoot/clinstagram`, 4★ `python-sage-meta`). There is **no maintained community Python SDK for Instagram Messaging** — official docs push raw Graph calls (`/me/messages` with an IG-scoped page token, exactly what `webhook.py`/`messenger_service.py` already do). Conclusion: don't hunt for an IG SDK; the current direct-Graph design is the correct one.

---

## 3. X-Hub-Signature-256 — best practice + zemest audit

**Best practice (per Meta docs + ecosystem):**
1. Read the **raw request body** and verify **before** `json()` parsing (✅ zemest does this — body → verify → parse).
2. HMAC-SHA256 with the **App Secret** (not page token / not verify token) over raw bytes; header is `sha256=<hexdigest>` (✅ both implementations format-compare `"sha256=" + expected`).
3. Use **constant-time comparison** — `hmac.compare_digest`, never `==` (✅ both).
4. **Fail closed** if the secret is unconfigured (✅ both log + return 403 — good posture; misconfigured prod rejects traffic loudly instead of accepting forgeries).
5. Return **403 on bad signature**, `200 EVENT_RECEIVED` fast on success (Meta retries on non-200 → duplicate-processing storms; zemest already dedups via the `"duplicate"` reply marker).
6. GET verify: `hub.mode=="subscribe"` + `hub.verify_token` equality + echo `hub.challenge` (✅ all three endpoints).

**Ecosystem finding:** GitHub has **no maintained dedicated Python X-Hub-Signature library** (searches surface only tiny Node middlewares: `alexcurtis/express-x-hub` 35★/2020, `compwright/x-hub-signature` 12★/2026). The standard is 10 lines of stdlib `hmac`. **zemest's hand-rolled implementation is the best practice — keep it; do not add a dependency for this.**

**Two real gaps found (report-only, no changes made):**
- `webhook.py` L280: `media_type="text_plain"` typo in `verify_instagram_webhook` (should be `text/plain`).
- Duplicated logic: `verify_fb_signature()` (security.py) and `_verify_meta_signature()` (webhook.py) are the same function twice — consolidate into `security.py` on the next refactor (single audit surface).
- Hardening ideas (optional): cap accepted body size (e.g. 1 MB) before HMAC, and metric/log on signature rejects to detect probing.

---

## 4. Recommended next actions (for the roadmap owner)

1. **Tunnel first** (`bore`/localtunnel): unblocks real Meta webhook registration against `localhost:8000` — every subsequent channel test depends on it.
2. **Upgrade WhatsApp feature coverage** in `whatsapp_service.py` + `webhook.py` using `fbsamples/whatsapp-api-examples` patterns (media-id resolution, templates, interactive, read receipts).
3. **Centralize Graph version** in `config.py` (kill the hard-coded `v21.0`) and bump to a current version before Meta 4xx's the pinned one.
4. Fix the two webhook nits (text_plain typo, dedupe signature helpers) in a cleanup PR.
5. Skip all unofficial libraries (wa-automate/WPPConnect/instagrapi/unoapi) — ban risk is existential for a multi-tenant messaging SaaS.
