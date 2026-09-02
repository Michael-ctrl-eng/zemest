# G1 — Payment Gateways for Egypt + OSS Payment Tooling

**Task ID:** G1 · **Agent:** G1 (github-research) · **Scope:** GitHub only, no code changes.
**Context:** zemest = FastAPI (:8000) + Next.js/BFF (:3000), SQLite→Postgres. Orders already model COD, `payment_method` (cod / vodafone_cash / instapay / fawry), `payment_phone_last2`, `payment_trx_id` (manual wallet-transfer verification), shipping by governorate. **No online gateway wired.** Payments were the one gap in R1–R10.
**Method:** GitHub search API + raw file fetches (official Paymob skill's `AGENTS.md`/`universal-prompt.md` read in full). ~11 API calls, ≤20 budget honored.

---

## 1. Egypt payment landscape — the reality before the code

- **COD dominates** (est. 60–90% of Egyptian e-commerce by most industry counts). Any gateway work must *augment* COD, not replace it.
- **Paymob ("Accept")** is Egypt's leading online gateway: cards, **mobile wallets (Vodafone Cash, Orange Cash, e& money, WePay)**, BNPL (valU, Sympl, Souhoola, Tabby, Tamara…), **kiosk/retail cash (Aman, Masary)**, bank installments. Regions: EG/UAE/KSA/OMN.
- **Kashier** — strong #2 in Egypt, merchant-friendly, hosted iframe checkout + `x-kashier-signature` webhooks.
- **Fawry** — the retail cash network: customers pay a reference code at 250k+ Fawry/ATM/retail points (`PAYATFAWRY`). Also full EGP gateway.
- **Geidea** — KSA-origin, growing in Egypt; on GitHub only mobile SDKs + WooCommerce/Odoo/OpenCart/PrestaShop plugins. **No Python/Node OSS SDK of substance.**
- **Consolg** — nothing on GitHub (zero relevant repos). Ignore.
- **Stripe** — `stripe/stripe-python` (2,040★, MIT, pushed 2026-08, pristine OSS) but **Stripe does not onboard Egyptian-registered merchants** (Egypt absent from supported business countries; workarounds = US LLC via Stripe Atlas — heavy for our SMB sellers). Stripe can *charge some* Egyptian cards as a foreign merchant, but that's not a valid path for multi-tenant Egyptian sellers.

**Key OSS fact:** there is **no maintained official Paymob Python SDK** (`PaymobAccept/paymob-python` = 1★, last push 2021-12, abandoned) and **no maintained community Python SDK** (best: `muhammedattif/Paymob-Solutions`, 35★, last push 2023-07 — stale ~3y). The maintained official surface is the **Intention REST API + AI Integration Skill + Postman collections**. The "stripe of MENA" OSS abstraction does not exist for Python; the closest unified abstraction is `wpdynamo/egypt-pay` (TypeScript).

---

## 2. Ranked top 5 (verdicts)

| # | Repo | Stars | Last push | License | Verdict |
|---|------|-------|-----------|---------|---------|
| 1 | [PaymobAccept/Paymob-AI-Integration-Skill](https://github.com/PaymobAccept/Paymob-AI-Integration-Skill) | 29 | 2026-08-15 (active, v3.3.0) | MIT | **ADOPT NOW** |
| 2 | [wpdynamo/egypt-pay](https://github.com/wpdynamo/egypt-pay) | 11 | 2026-05-22 | MIT | **ADOPT NOW (TS side) / reference for Python port** |
| 3 | [PaymobAccept/API-Postman-Collections](https://github.com/PaymobAccept/API-Postman-Collections) | 4 | 2026-07-30 (active) | none (docs) | **ADOPT NOW (spec reference)** |
| 4 | [fawry-api/fawry](https://github.com/fawry-api/fawry) | 73 | 2026-07-16 (active) | MIT | **NEXT (pattern reference only — Ruby)** |
| 5 | [stripe/stripe-python](https://github.com/stripe/stripe-python) | 2,040 | 2026-08-31 (very active) | MIT | **SKIP (Egypt merchants unsupported)** |

### #1 — PaymobAccept/Paymob-AI-Integration-Skill — the single best find
- **What it is:** Paymob's *official* portable skill (plain Markdown) that makes any AI coding agent an expert at Paymob integration across Egypt/UAE/KSA/Oman. Ships as Claude Code/Codex plugin, Cursor/Windsurf rules (`AGENTS.md`), universal prompt, plus an official Paymob MCP server (`https://mcp.paymob.com/mcp`).
- **What it solves for us:** zemest is an AI-platform — we can vendor this repo into our agent's knowledge and generate correct Paymob integration code for merchant checkouts. It is the authoritative, maintained spec for:
  - **Intention API only** (`POST {base}/v1/intention/`, `Authorization: Token {secret_key}`); the legacy 3-step flow (auth token → order → payment key) is deprecated — most stale blog SDKs still teach the old flow.
  - **HMAC-SHA512 webhook verification, 3 types** with exact field orders (see §3).
  - Amounts in **piasters** (100.00 EGP = `10000`); test-mode keys + test-mode integration IDs against the production base URL (`https://accept.paymob.com`).
  - Env contract: `PAYMOB_SECRET_KEY` (server), `PAYMOB_PUBLIC_KEY` (frontend-safe), `PAYMOB_HMAC_SECRET`, `PAYMOB_API_KEY` (inquiry only), `PAYMOB_INTEGRATION_ID_*` (one per method).
  - Multi-agent guardrails (rule 8/9: never auto-retry ambiguous financial writes; read remote state first) — maps 1:1 onto our future payments agent.
- **Egypt/COD fit:** excellent — mobile wallets, kiosk (Aman/Masary) cash, BNPL all via the same Intention API; per-method integration IDs let us expose "pay deposit with Vodafone Cash" while the order stays COD.
- **Integration sketch (FastAPI, direct REST — no SDK needed):**
  ```python
  # POST /v1/intention/ → {client_secret, redirection_url/checkout url}
  r = await httpx.post(f"{PAYMOB_BASE}/v1/intention/", headers={"Authorization": f"Token {SECRET}"},
      json={"amount": int(amount_egp*100), "currency": "EGP", "payment_methods": [WALLET_INT_ID],
            "items": [{"name": p.name, "amount": int(p.price*100), "quantity": q, "description": sku}],
            "customer": {"first_name": c.name, "phone": c.phone},
            "special_reference": f"zst-{order.uid}",          # order correlation
            "notification_url": f"{PUBLIC}/api/payments/paymob/webhook"})
  # Webhook: verify HMAC-SHA512 over the 20-field string (see §3), then in ONE transaction:
  # dedup on obj.id (unique), compare-and-set order.payment_status → paid, insert outbox row, return 200.
  ```
- **Verdict: ADOPT NOW.** Vendor it into the repo as the payments knowledge base; it's MIT, current, and official.

### #2 — wpdynamo/egypt-pay — the only unified Egyptian gateway abstraction
- **What:** unified TS library for **Kashier + Paymob**, one `createGateway()` interface (`createSession`, `verifyWebhook`), **zero dependencies** (Web Crypto), runs on Node 18+/Bun/Deno/Cloudflare Workers. `npm i egypt-pay`, v1.0.1, MIT.
- **What it solves:** the "stripe of MENA" problem, at least for the two gateways that matter to us, in exactly the runtime our Next.js BFF uses. Handles Kashier `x-kashier-signature` and Paymob query-`hmac` verification behind one interface.
- **Egypt/COD fit:** both providers are Egypt-first; sessions carry customer phone → wallet flows work.
- **Risks:** 11★, single small publisher — treat as either (a) a thin BFF-side dependency (zero-dep keeps blast radius tiny), or (b) a **reference implementation to port into FastAPI** (~200 lines: session create + webhook verify per gateway). Given our money path and multi-tenancy, I'd port the Paymob/Kashier verify logic into our own `app/services/payments/` guided by #1, and keep egypt-pay for the BFF checkout redirect if we ever create sessions from Node.
- **Verdict: ADOPT NOW as reference/BFF-side; own the Python path.**

### #3 — PaymobAccept/API-Postman-Collections — official living API docs
- Official Postman collections for the current Paymob API (pushed 2026-07). Not a library; it's the ground truth for endpoint shapes when the skill and reality drift (the skill itself says live docs win). Verdict: **ADOPT NOW** (free, keeps us off stale StackOverflow flows).

### #4 — fawry-api/fawry — Fawry gateway patterns, Ruby
- 73★, MIT, actively maintained, **unofficial** (stated in README). Ruby gem covering Fawry **charge (incl. `PAYATFAWRY` / `CARD` / wallet), refund, and status**, with signature = secure-key hash over a documented param list; returns `reference_number` the customer pays at any Fawry kiosk/ATM.
- **Why it matters to us:** it codifies the Fawry signature formula and the **charge → poll/reference-number → refund** lifecycle cleanly, and `PAYATFAWRY` is the natural engine for **COD deposits** (customer pays a small amount at a kiosk to confirm the order; no card or wallet needed).
- **Fit:** Ruby ≠ our stack → not a dependency, but a pattern donor when we add Fawry. Verdict: **NEXT** (when we add Fawry after Paymob; port the formulas).

### #5 — stripe/stripe-python — best OSS, wrong geography
- 2,040★, MIT, pushed 2026-08-31; the gold standard of payment SDK design (idempotency keys, typed events, webhook signature classes). **But Stripe cannot onboard Egyptian-registered businesses** → our merchants can't get accounts. Only path is Stripe Atlas (US LLC) — absurd for Cairo Instagram sellers. Verdict: **SKIP** (revisit only if Stripe adds EG; steal its API design idioms for our own gateway service: idempotency keys, event dedup, signature header).

**Also considered (rejected):** `Nafezly/payments` (491★, MIT, active — the popular "PayPal-Paymob-Fawry-Kashier helper" but **Laravel/PHP-only**); `peter-tharwat/Payment-helper` (same, PHP, 2022-stale); `muhammedattif/Paymob-Solutions` (35★ Python, dead since 2023-07, uses deprecated pre-Intention flow); `GeideaSolutions/*` (mobile SDKs + CMS plugins only, no server SDK); `Consolg` (no GitHub footprint); `Kashier-payments/*` (WooCommerce/Odoo plugins only — Kashier integration will be hand-rolled REST per egypt-pay's implementation).

---

## 3. Webhook signature verification patterns (the security core)

Lessons extracted from the official skill + egypt-pay + fawry gem — these apply to **every** gateway we add:

1. **Server webhook = source of truth.** Browser `redirection_url` params and SDK results are UX-only, unauthenticated. Never mutate order state from them (the skill's non-negotiable rule 3).
2. **Paymob — HMAC-SHA512, 3 distinct types; verify the right one or it silently fails:**
   - **Transaction (POST callback):** 20 fields concatenated in exact order, no separator: `amount_cents, created_at, currency, error_occured, has_parent_transaction, id, integration_id, is_3d_secure, is_auth, is_capture, is_refunded, is_standalone_payment, is_voided, order.id, owner, pending, source_data.pan, source_data.sub_type, source_data.type, success` — booleans as lowercase `true/false`, `hmac` arrives as **query param**; hex-lowercase, **timing-safe compare** (`hmac.compare_digest`).
   - **Card token (saved cards):** 8 fields: `card_subtype, created_at, email, id, masked_pan, merchant_id, order_id, token`.
   - **Subscription:** string `"{trigger_type}for{subscription_data.id}"`, hmac in **body**.
   - Same 20 fields for the GET redirect (`id`, `order_id` renamed).
3. **Kashier:** HMAC signature in `x-kashier-signature` header (egypt-pay verifies body+path+method hash).
4. **Fawry:** request hash over sorted param list + `fawry_secure_key` (SHA-256); refund uses the same formula with `reference_number` + `refund_amount`.
5. **Universal rules:** verify → dedup on gateway transaction/event id (unique constraint — remember our `fb_message_id` dedup race, don't repeat it) → **one DB transaction** compare-and-set + outbox insert → only then return 2xx → never auto-retry ambiguous financial writes, re-query the gateway instead.

---

## 4. COD-first + deposit workflows for Egyptian sellers (design note)

Zemest's order state machine should stay **COD-first** and treat the gateway as a *risk-management* tool, not the default rail:

- **Keep COD the default** in the demo agent's copy and checkout (already true: "pay when it arrives 💵") — matches buyer trust norms and requires zero gateway for the core loop.
- **Deposit-to-confirm ("عربون") flow — the highest-value online-payment feature for EG sellers:** generate a Paymob **Intention for a partial amount** (shipping fee, or 10–25% of order) via `special_reference = zst-{order.uid}`; buyer pays with **Vodafone Cash/wallet** (or Fawry `PAYATFAWRY` at any kiosk, or Aman/Masary cash — no card needed). Webhook flips order to `deposit_paid`, which (a) massively cuts fake COD orders / RTO returns, (b) justifies priority dispatch. Merchant sets deposit policy per-governorate (high-RTO governorates → deposit required) — we already have governorate shipping rates to hook this to.
- **Manual wallet-transfer verification we already have** (`payment_phone_last2`, `payment_trx_id` in settings/orders UI) is the zero-gateway MVP of the same idea — keep it; the gateway automates it.
- **Full online payment** = same Intention with the full amount (cards, wallets, BNPL for higher tickets). **Refunds** via the gateway API (or Fawry refund) map onto the existing returns handling.
- **Status machine:** `pending → (deposit link sent) → deposit_paid | deposit_expired → shipped → cod_collected | deposit_captured+cod_balance | returned (RTO)`. All state changes driven **only** by HMAC-verified webhooks (or the Fawry status-poll job we already know how to schedule — APScheduler from R6).

**Sequencing recommendation:** (1) vendor the Paymob AI skill + Postman collection now (knowledge only); (2) build `app/services/payments/paymob.py` with Intention create + 3-type HMAC verify + webhook route on FastAPI, test-mode keys, in sandbox against :8000; (3) port Kashier from egypt-pay's implementation when sellers ask for it; (4) add Fawry PAYATFAWRY deposits from the Ruby gem's patterns.

---

## 5. Sources (all verified live this session)

- Search queries: `paymob`, `kashier`, `fawry`, `geidea`, `paymob+language:python`, `org:PaymobAccept`, `consolg`, `stripe-python in:name`, `fawry+language:python`, `paymob+fastapi`.
- Raw-read in full: `PaymobAccept/Paymob-AI-Integration-Skill/{AGENTS.md, universal-prompt.md}`, READMEs of `fawry-api/fawry`, `wpdynamo/egypt-pay`, `muhammedattif/Paymob-Solutions`; `wpdynamo/egypt-pay/package.json` (MIT confirmed); `Nafezly/payments/composer.json` (Laravel-only confirmed).
