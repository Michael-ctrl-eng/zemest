# P2 — Marketing Pages Deep Analysis (zemest-platform)

**Scope:** 26 pages under `src/app/` (blog, book-demo, brand-kit, careers, dpa, enterprise, forgot-password, get-started, models, partnerships, press-kit, pricing, privacy, products, register, research, solutions + 4 sub-pages, status, support, terms, trust, login skim) + shared chrome (`navbar.tsx`, `footer.tsx`, `page-shell.tsx`, `auth-page.tsx`), middleware, BFF auth routes, robots.txt, root layout.

**Repo:** /home/z/my-project/repos/zemest-platform — Next.js 15/16 App Router + TS + Tailwind 4 + shadcn/ui (unused on marketing pages) + framer-motion 12.

---

## 1. Page Inventory Catalog

Legend: **[REAL]** = finished content, **[PLACEHOLDER]** = "coming soon" stub, **[TAVUS]** = leftover content from the Tavus (AI-video-avatar company) template this site was forked from.

### 1.1 `/blog` — blog/page.tsx (155 L) — [TAVUS] server component
- **Purpose:** Blog index. **Sections:** PageHero → featured post card → 18-post grid → newsletter form.
- **Content:** 1 featured + 18 hardcoded posts — ALL Tavus content: "Introducing Deployments: Send Your PAL Into the World", Phoenix-4, Raven-1, Sparrow-1, "AI Humans", "RAG video agents", HIPAA AI video, video prospecting… Author "Hassaan Raza" (Tavus founder). Zero Zemest/moderation/Arabic content.
- **Key claims:** "Human Computing", PAL deployments, video agents. **Dates are all in the future** (Aug 2026).
- **Forms:** Newsletter `<form>` (line 135–148) — **no onSubmit handler, no action** → dead. Email input, SUBMIT button renders but does nothing.
- **Links:** featured + all 18 cards link to `/blog/{slug}` — **no `/blog/[slug]` route exists** (verified via Glob: only `blog/page.tsx`) → **all 19 links 404**.
- **Metadata:** title only: `"Zemest Blog: Human Computing & Conversational AI"` (line 6) — mixed Zemest brand + Tavus tagline. No description/OG.

### 1.2 `/book-demo` — book-demo/page.tsx (154 L) — [TAVUS-ish] client component
- **Purpose:** Demo request. **Sections:** PageHero → left "What you'll get" checklist + response-time card → right form in retro window chrome ("TAVUS · BOOK A DEMO" title bar, line 57).
- **Content:** "See PALs in action", "30-minute live PAL conversation", "Architecture deep-dive", "< 24 hours" response promise.
- **Form fields:** first, last, work email, company, company-size `<select>` (5 buckets), use-case `<textarea>`.
- **Submit:** `onSubmit={(e) => {e.preventDefault(); setSubmitted(true);}}` (lines 79–82) → **fake success screen; no network call, no endpoint, nothing persisted**. Pure theater.
- **Validation:** none (no `required`, no JS checks) — empty form submits "successfully".
- **Metadata:** none exported → inherits root default ("Zemest — AI Moderation Agents") — wrong title for the page.

### 1.3 `/brand-kit` — brand-kit/page.tsx (22 L) — [PLACEHOLDER]
- Literal template: `metadata = { title: "TITLE — Zemest" }` (line 5), hero `eyebrow="EYEBROW" title="TITLE italic" description="DESCRIPTION"` (line 12), body: "This page is coming soon. In the meantime, contact us at hello@zemest.ai" (line 15).

### 1.4 `/careers` — careers/page.tsx (166 L) — [TAVUS] server component
- **Purpose:** Recruiting. **Sections:** hero ("Work at Tavus") → "The Next Intelligence is Emotional" → 6 principles → 6 perks → 8 open roles.
- **Content:** 100% Tavus: "Tavus is an AI research lab reimagining the human and machine interface" (line 45), "Our HQ is in San Francisco" (line 61), SF/NY/Remote-US roles (lines 27–34), US-style benefits (medical/dental/vision, equity).
- **Interactive:** role cards are `<a href="#">` (line 140) → **dead links; no application flow**.
- **Metadata:** `"Careers | Tavus — The Human Computing Company"` (line 6) — **wrong company in the title tag**.

### 1.5 `/dpa` — dpa/page.tsx (22 L) — [PLACEHOLDER]
- Same stub as brand-kit (title "TITLE — Zemest"). Footer links here as "Data processing". GDPR story has **no DPA artifact at all** while enterprise page sells "Full GDPR compliance" (see §6).

### 1.6 `/enterprise` — enterprise/page.tsx (90 L) — [TAVUS] server component
- **Purpose:** Enterprise pitch. **Sections:** hero "Customized PALs, fully managed" → 6 feature cards → 3-step process → 6 use-case cards.
- **Claims (lines 9–15, 25, 53–55):** SOC 2 Type II ("Reports available on request"), HIPAA BAAs, GDPR + EU data residency, "Deploy **Tavus** in your own VPC / on-prem / air-gapped", 99.95% uptime SLA with financial credits, "30-minute critical incident response", dedicated CSM.
- **Use cases:** GTM agents, patient intake, screening, L&D, support — all Tavus video-agent verticals; none relate to commerce moderation.
- **CTAs:** /book-demo (dead form), /partnerships (Tavus page). **Metadata:** `"Enterprise — Zemest"` title only.

### 1.7 `/forgot-password` — forgot-password/page.tsx (87 L) — [REAL-design/Zemest] client component
- **Purpose:** Password reset request. Full-screen dark layout, "RESET" bitcount watermark, ZEMEST · RESET PASSWORD window (line 44).
- **Form:** single email field, `required` (line 63), controlled state.
- **Submit:** `onSubmit={(e) => {e.preventDefault(); setSubmitted(true);}}` (line 58) → **fake "Check your email — We sent a reset link to {email}"** (line 52). No endpoint exists anywhere (no `/api/auth/forgot` route in the repo); **the email is never sent**. This actively lies to users.

### 1.8 `/get-started` — get-started/page.tsx (10 L) — [REAL wrapper]
- `<AuthPage mode="get-started" />` + metadata (title "Get Started — Zemest", description "build your first moderation agent in less than 5 minutes"). Form behavior detailed in §3 (AuthPage).

### 1.9 `/models` — models/page.tsx (142 L) — [REAL/Zemest] server component — best page in scope
- **Purpose:** The two AI models. **Sections:** hero "Two models. One mission." → 2 model cards → 4 capability cards.
- **Content:** Rabbit v1 — "Arabic moderation · every dialect", "Speaks Egyptian, Gulf, Levantine, Maghrebi, Sudanese, and Yemeni", "Voice-note transcription built in", "Trained on millions of Arabic commerce conversations", specs: 30+ dialects / Voice Native / Arabic. Rat v1 — English, "12+ accents", "Reads images". Real Arabic sample conversation (RTL, `dir="rtl"` handling lines 105/109): "لو سمحت، عندي النايك الأبيض مقاس 42؟" → "أيوا متوفر، 2 pieces في المخزن. 850 جنيه. تحب أثبتهولك؟".
- **Capabilities:** "answers in <3 seconds", image recognition, "Checks stock live. Connects to your shop or POS."
- **Oddity:** Rabbit's icon is `Feather`, Rat's is `Bird` (lines 12, 30) — animal/icon swap (cosmetic).
- **CTA:** /get-started (dead form). **Metadata:** `"Models — Zemest"` title only.

### 1.10 `/partnerships` — partnerships/page.tsx (105 L) — [TAVUS] server component
- **Purpose:** Partner programs. **Sections:** hero "Wanna make a deal?" → 4 program cards (window chrome) → 3 stat blocks.
- **Content:** "Integrate **Tavus** into your product", "Build PALs for your clients", "Build on **Tavus**, free for 12 months… $50k in API credits", stats: "100+ Partners worldwide", "30% Revenue share" (lines 12–40, 90–92).
- **All CTAs → `/book-demo`** (the dead form). **Metadata:** `"Partnerships — Zemest"`.

### 1.11 `/press-kit` — press-kit/page.tsx (22 L) — [PLACEHOLDER] (same stub as brand-kit).

### 1.12 `/pricing` — pricing/page.tsx (165 L) — [REAL/Zemest] server component
- **Purpose:** Plans. **Sections:** hero → 3 tier cards → comparison table (8 rows) → 6 FAQ cards.
- **Tiers (lines 8–37):**
  - **STARTER $0 /14 days** — 1 channel (WhatsApp, FB, or IG), Rabbit v1 OR Rat v1, **100 conversations/month**, Inventory Connect (1 shop), "Community Discord support".
  - **GROWTH $99/mo** — 3 channels, both models, 5,000 conversations/month, 3 shops, priority email support, custom brand tone. Highlighted "MOST POPULAR".
  - **ENTERPRISE Custom** — unlimited everything, both models + custom training, dedicated CSM, "99.95% SLA + on-prem option".
- **Comparison table (lines 127–135):** adds SLA row (—, 99.9%, 99.95%) and on-prem row — note **Growth SLA 99.9% appears only in the table, not on the tier card** (minor inconsistency), and the on-prem claim contradicts the "—/—" nothing offered to Starter/Growth.
- **FAQ claims (lines 40–45):** trial = 14 days + "100 conversations **per month**" (period mismatch: trial is 14 days but quota monthly), "switch models mid-conversation", "agent trains on your historical chats", "You can upgrade, downgrade, or cancel **from your dashboard**" (no billing UI exists in dashboard), dialect-matching.
- **CTAs:** tiers → /get-started, /book-demo. Uses raw `<a href>` (line 97) instead of `Link` → full page reloads.
- **Metadata:** `"Plans and Pricing - Zemest"` title only. **USD pricing** for an Egyptian-SMB product (no EGP option).

### 1.13 `/privacy` — privacy/page.tsx (29 L) — [REAL but skeletal] server component
- Ultra-thin policy: data collected (account, channel chats, usage, conversation logs "needed to train your agents"), use ("never sell your data"), rights ("export or delete your data at any time from your dashboard. Email privacy@zemest.ai"). No DPA link, no jurisdiction (Egypt PDPL / GDPR unmentioned), no retention periods, no subprocessors, no cookie policy. "Last updated: August 2026" (future-dated).

### 1.14 `/products` — products/page.tsx (106 L) — [REAL/Zemest] server component
- **Sections:** hero "Three ways to build with Zemest" → 3 product cards (Rabbit v1, Rat v1, Inventory Connect — all CTAs /get-started) → 4 capability cards.
- **Claims:** "replies in <3 seconds", "Checks stock before answering", "No API, no developer setup". Note: Rabbit headline here is "Arabic moderation, every **accent**" (line 12) vs models page "every **dialect**" — wording drift.
- Uses `Link` (proper). **Metadata:** `"Products — Zemest"`.

### 1.15 `/register` — register/page.tsx (116 L) — [REAL form UX / FAKE submit] client component
- **Form:** name, email, password (+ show/hide toggle), confirm password. Facebook → `/api/auth/facebook` (real OAuth start, line 102); Google & SSO buttons do **nothing** (lines 103–104).
- **Validation (lines 22–27):** name ≥2 chars, email regex, password ≥8 + letter + number, confirm match — the only page with real client validation. Error styling in `--tavus-bubbletech-4` (light pink) — questionable error color.
- **Submit (lines 30–32):** if valid → `window.location.href = "/dashboard"`. **Never calls `/api/auth/register`** — a fully-implemented BFF route exists (`src/app/api/auth/register/route.ts`: proxies to FastAPI `/api/auth/register`, sets httpOnly `zemest_auth`/`zemest_refresh` cookies) but is orphaned. Since no cookie is ever set, `src/middleware.ts:36-40` bounces the user from /dashboard back to `/login?redirect=/dashboard`. **The entire email/password signup funnel is broken by design.**

### 1.16 `/research` — research/page.tsx (163 L) — [TAVUS] server component
- 6 research areas (Perception/Listening/Agency/Voice/Motion/Dialogue), 3 "AI Human" trait columns ("15x faster than other solutions" RAG claim, line 29), 5 "papers" (Raven-1, Sparrow-1, "Knowledge Navigator, Reimagined… Meet Dom, our real-life take on it… from **Tavus**" line 38) — all "Read paper" CTAs → `href="#"` (line 131) dead. Ethics section references "Tavus is built on informed consent…" (line 148). Hero CTA → /get-started. **Metadata:** `"Zemest Research: Pioneering Human Computing"` — brand mashup.

### 1.17 `/solutions` — solutions/page.tsx (72 L) — [REAL/Zemest] server component
- 6 solution cards, each with a headline stat: WhatsApp Agent "3.2× reply rate", Instagram Agent "+47% DM→sale", Messenger Agent "+38% CSAT", Inventory Agent "-41% lost sales" (with EGP sample "850 EGP"), Arabic card "30+ dialects" → /models, Custom agents → /enterprise. No data source/footnote for any stat (fabricated-appearing marketing numbers).
- **Links:** 4 of 6 cards link to `/solutions/{whatsapp,instagram,messenger,inventory}` — **all four are placeholder stubs** (below). The primary conversion funnel dead-ends.
- **Metadata:** `"Solutions — Zemest"`.

### 1.18–1.21 `/solutions/{whatsapp,instagram,messenger,inventory}` — each 22 L — **ALL [PLACEHOLDER]**
- Identical stubs: `title: "TITLE — Zemest"`, "EYEBROW / TITLE / DESCRIPTION" hero, "coming soon… hello@zemest.ai". WhatsApp — the flagship channel (hero of the entire product story) — has no real landing page.

### 1.22 `/status` — status/page.tsx (22 L) — [PLACEHOLDER]
- A status page that is "coming soon" — while pricing/enterprise pages sell 99.9–99.95% SLAs. No uptime feed, no incident history, no components table.

### 1.23 `/support` — support/page.tsx (22 L) — [PLACEHOLDER]
- No knowledge base, no ticketing, no channels — while pricing promises "Community Discord support" / "Priority email support" / enterprise "24/7 Slack channel + dedicated phone line" (enterprise/page.tsx:14).

### 1.24 `/terms` — terms/page.tsx (27 L) — [REAL but skeletal]
- 3 paragraphs: lawful use, acceptable use ("Agents must clearly indicate they are automated where required by local regulation" — notable compliance-adjacent claim), accounts & billing ("month-to-month… refunds at our discretion within 14 days"). No governing law, no liability/warranty/indemnity sections, no dispute resolution. Future-dated "August 2026".

### 1.25 `/trust` — trust/page.tsx (22 L) — [PLACEHOLDER]
- The trust center that would substantiate SOC 2/HIPAA/GDPR claims on /enterprise does not exist.

### 1.26 `/login` — login/page.tsx (10 L) — skim (full auth analysis is P4)
- `<AuthPage mode="login" />` + metadata. Form = AuthPage (below): **no submit logic at all** (`onSubmit={(e) => e.preventDefault()}`, auth-page.tsx:116); Facebook works via redirect; Google/SSO dead.

### Shared chrome
- **navbar.tsx (152 L, client):** Zemest logo + 6 links (PRODUCTS/SOLUTIONS/MODELS/ENTERPRISE/RESEARCH/PRICING), LOGIN + GET STARTED, mobile framer-motion drawer, dismissible announcement bar "Rabbit v1 is now live: Arabic moderation with every accent" (line 137 — again "accent" vs "dialect").
- **footer.tsx (176 L, client):** 7 columns × 4 links. SOCIALS: LinkedIn/X/Discord → `href="#"` **dead** (lines 46–48); Email → `mailto:hello@zemest.ai`. RESEARCH column: 3 of 4 links duplicate `/research` (lines 37–41) — padding, not navigation. LEGAL includes /acceptable-use (placeholder). Wordmark "© 2026 ZEMEST | THE COMMERCE MODERATION COMPANY". Comment on line 5: "Real footer columns — all links go to real Zemest pages" — **false**: 4 `#` links + 11 placeholder targets.
- **page-shell.tsx (169 L, client):** PageHero / PageSection / RetroCard / PageShell. Entire file is `"use client"` although none of the three exported components uses state/effects — forces every marketing page's hero/sections through the client boundary (bundle + hydration cost for zero benefit).
- **not-found.tsx:** proper branded 404 with Navbar/Footer.

---

## 2. Marketing Site Content Map — the story being told

**Intended story (Zemest pages):** Egyptian SMBs sell via WhatsApp/Facebook/Instagram DMs; can't keep up; connect your channels + shop; Zemest trains on your historical chats; Rabbit v1 (Arabic, 30+ dialects, same-dialect replies, voice transcription) and Rat v1 (English, 12+ accents, image reading) answer in <3s, check live inventory (Inventory Connect), close sales in your brand tone; start free 14 days → $99/mo Growth → custom Enterprise (SOC 2/HIPAA/GDPR/SLA/on-prem); bespoke agents via Enterprise.

**Products:** Rabbit v1 (Arabic), Rat v1 (English), Inventory Connect (POS/shop stock sync). **Channels:** WhatsApp, Instagram (DMs), Facebook Messenger (+ "comments"). **Differentiators:** dialect matching vs "textbook MSA", voice + image understanding, no-API/no-dev-setup, "trained on your old chats".

**Actual content split (26 pages in scope):**
| Category | Pages |
|---|---|
| Real Zemest content | models, pricing, products, solutions, privacy (thin), terms (thin), get-started/register/login/forgot-password (Zemest-branded shells) |
| Tavus leftover content | blog, careers, enterprise, partnerships, research |
| Placeholder stubs (11) | brand-kit, press-kit, dpa, trust, status, support, acceptable-use, solutions/whatsapp, solutions/instagram, solutions/messenger, solutions/inventory |

**Pricing (exact):** Starter $0/14 days (1 channel, 1 model, 100 conv/mo, 1 shop, Discord community); Growth $99/mo (3 channels, both models, 5,000 conv/mo, 3 shops, priority email, brand tone, 99.9% SLA per table); Enterprise custom (unlimited, custom training, CSM, 99.95% SLA, on-prem).

**Enterprise offering:** bespoke fully-managed "PAL deployments", 3-step process (Discovery → Build → Deploy), dedicated CSM, 24/7 support, 30-min incident response.

**Trust/legal posture claimed vs artifact:** enterprise claims SOC 2 II, HIPAA BAA, GDPR + EU residency; the site's actual trust surface = 29-line privacy policy, 27-line terms, and placeholder DPA/trust/status pages. **No compliance artifact exists on the site.**

**Status page mechanics:** none — placeholder. **Support channels:** none on /support (placeholder); footer "Support center" → placeholder; "Contact" → /book-demo dead form; pricing promises Discord community + priority email; enterprise promises 24/7 Slack + phone. No support email/phone is published anywhere except `hello@zemest.ai` (placeholder stubs + footer mailto) and `privacy@zemest.ai` (privacy page).

**Backend reality cross-check (from repo + prior Z-agent findings):**
- No billing/plan/quota system in FastAPI backend (grep: zero trial/subscription/Stripe logic; only a string "upgrading your plan" in notification_service.py:110) → pricing tiers are entirely unenforced fiction.
- WhatsApp backend = one `send_whatsapp_message()` Graph-API sender with tenant token (app/services/whatsapp_service.py) — no WhatsApp webhook ingest pipeline; yet WhatsApp is the hero channel of the marketing story and even the announcement bar.
- 99.9/99.95% SLA claims vs a platform whose own admin/analytics read permanently-empty tables and whose security middleware is unwired (Z10 findings) — unsupported.
- "Trained on millions of Arabic commerce conversations" / "30+ dialects" / "<3s replies" — no evidence in backend (LLM is a free-tier fallback chain per Z2; no dialect-count data).

---

## 3. Forms & Integrations (where do submissions go?)

**Verdict: 6 of 6 forms in scope are dead or fake. Zero marketing submissions reach any server.**

| Form | File:line | Fields | Handler | Destination | Status |
|---|---|---|---|---|---|
| Book a demo | book-demo/page.tsx:77–119 | first, last, email, company, size select, message textarea | `setSubmitted(true)` (79–82) | **nowhere** | DEAD (fake success) |
| Newsletter | blog/page.tsx:135–148 | email | none (no onSubmit) | **nowhere** | DEAD (no-op form) |
| Forgot password | forgot-password/page.tsx:58–76 | email (required) | `setSubmitted(true)` | **nowhere** (no route exists) | DEAD + **deceptive "email sent" claim** |
| Get-started/signup | components/site/auth-page.tsx:116–150 | name, email, password, ToS checkbox | `onSubmit={(e) => e.preventDefault()}` (116) | **nowhere** | DEAD |
| Login | same AuthPage | email, password, remember | preventDefault | **nowhere** (real `/api/auth/login` BFF route exists, orphaned) | DEAD |
| Register | register/page.tsx:12–33 | name, email, password, confirm | real validation then `window.location.href="/dashboard"` (31) | **client-side redirect only**; ignores real `/api/auth/register` route | FAKE (bounces to /login via middleware) |

- **Only working integration:** Facebook OAuth buttons (auth-page.tsx:168, register/page.tsx:102) → `window.location.href = "/api/auth/facebook"` → real BFF route (src/app/api/auth/facebook/route.ts) → FastAPI `/api/auth/facebook` OAuth flow with callback `/api/auth/facebook/callback`.
- **Dead buttons:** Google + SSO on both auth pages (no onClick); all 8 careers "APPLY" links (`href="#"`); all 5 research "Read paper" links (`href="#"`); footer LinkedIn/X/Discord (`#`).
- **Validation approach:** no react-hook-form, no zod — despite both being installed dependencies (package.json:59, 80). Register hand-rolls regex/length checks; book-demo/AuthPage have none (not even `required` on AuthPage fields; book-demo fields have no `required` either — only forgot-password uses `required`).
- **mailto:** `hello@zemest.ai` (footer + 11 stubs), `privacy@zemest.ai` (privacy page) — the only "live" contact channels.
- **BFF routes present but unused by marketing pages:** `/api/auth/login`, `/api/auth/register` (both fully implemented with httpOnly cookie auto-login, register/route.ts:26–42). The wiring gap is purely in the page components.

---

## 4. Content Quality Assessment

**Placeholder/boilerplate:**
- 11/26 in-scope pages (42%) are the same 22-line stub with literal `"TITLE — Zemest"` metadata and `EYEBROW/TITLE/DESCRIPTION` hero text — these ship to production and are indexed (robots.txt allows all).
- Templates shipped: brand-kit, press-kit, dpa, trust, status, support, acceptable-use, solutions/{whatsapp,instagram,messenger,inventory}.

**Brand contamination (Tavus clone residue):** careers title tag literally says "Tavus"; blog is 100% Tavus posts; enterprise says "Deploy Tavus in your own VPC"; partnerships says "Integrate Tavus into your product" ×3; research says "…from Tavus that powers him". All design tokens are `--tavus-*` (globals.css:58+), fonts/texture classes `tavus-*`, public assets `tavus-*` (≈40 files). The homepage imports `WhatIsPAL` (src/app/page.tsx:5). A visitor reading /careers → /research → /enterprise would reasonably believe this is Tavus.

**Cross-page inconsistencies:**
- "every dialect" (models, solutions, FAQ) vs "every accent" for Arabic (products:12, navbar:137, layout description:29) — dialect is the correct claim for Arabic.
- Growth SLA 99.9% (pricing table:133) never stated on the tier card (which omits SLA); Enterprise card says 99.95%.
- Trial described as "14 days" but quota "100 conversations per month" (pricing:12 vs :40).
- Register redirects to /dashboard (register:31) — dashboard requires auth cookie (middleware:36–40) that register never sets.
- AuthPage login-mode footer links to `/register` ("Get started") while signup-mode links to `/login` — but navbar's GET STARTED → `/get-started`; three different signup entry points with two different forms (AuthPage vs register page) and divergent validation.
- Footer comment claims "all links go to real Zemest pages" (footer.tsx:5) — false (4×`#` + 11 stubs).

**Dead links inventory:** 19 blog post links (404), 8 careers apply (`#`), 5 research papers (`#`), 3 socials (`#`), ToS/Privacy links in AuthPage checkbox (`href="#"`, auth-page.tsx:128–129), Google/SSO buttons ×2.

**Claims vs backend reality (mismatch register):**
1. "Community **Discord** support" — no Discord exists (footer link `#`).
2. "cancel from your dashboard" — no billing UI in dashboard.
3. WhatsApp-first story — backend WA = single send function, no ingest.
4. SOC 2/HIPAA/GDPR/EU-residency/on-prem/air-gapped — no evidence; DPA/trust placeholders.
5. 99.9/99.95% SLA + "30-minute critical incident response" — status page is a placeholder.
6. "Trained on millions of Arabic commerce conversations" — unverifiable; backend trains per-tenant on imported chats.
7. "answers in <3 seconds" — backend LLM is a free-tier fallback chain (Z2), latency unmeasured.
8. "export or delete your data at any time from your dashboard" (privacy:21) — no such dashboard capability.
9. "100+ Partners worldwide", "$50k startup credits", "30% revenue share" — no partner program backend.
10. Footer "© 2026", "Last updated: August 2026", blog dates Aug 2026 — systematically future-dated.

---

## 5. Code Patterns

- **Server vs client:** Static marketing pages are server components with `export const metadata` (blog, careers, enterprise, models, partnerships, pricing, privacy, products, research, solutions×5, stubs) — good for SEO. Client pages only where state needed (book-demo, forgot-password, register) + auth wrappers. **Smell:** `page-shell.tsx` is wholly `"use client"` (line 1) though PageHero/PageSection/RetroCard are stateless presentational components — every marketing page drags them into the client bundle.
- **Reuse:** Uniform composition — Navbar + PageHero + PageSection(bg="grain"/"white") + RetroCard + Footer across all pages; `win-title-bar` window chrome motif; consistent neo-brutalist design language (3px black borders, hard offset shadows, halftone overlays, Instrument Serif italic accents, JetBrains Mono meta labels). Strong visual consistency.
- **Content management:** 100% hardcoded const arrays in each page (blog: 19 posts, careers: 20 items, models: 2 objects…). No CMS/MDX despite `@mdxeditor/editor` and `react-markdown` in deps. No i18n despite `next-intl` installed — notable for an Arabic-market product (the only Arabic on the site is one sample conversation on /models).
- **Linking:** Inconsistent — products/solutions use `next/link`, pricing/partnerships/blog use raw `<a>` (pricing:97, partnerships:77, blog:53) → full document reloads, losing SPA nav.
- **Animation:** Minimal and CSS-based (hover translate/shadow transitions everywhere); framer-motion only in navbar mobile drawer (AnimatePresence, navbar:102–126). No scroll animations on marketing pages. Auth pages use giant `font-bitcount` watermark typography.
- **Accessibility:**
  - Good: semantic `<main>`, `<section>`, h1→h3 hierarchy, `aria-label` on icon buttons (navbar:93,145), decorative layers `aria-hidden` (auth-page:50, forgot-password:18), `<th>` scope in pricing table, `dir="rtl"` on Arabic samples (models:105,109).
  - Bad: book-demo/FormFields labels lack `htmlFor`+`id` association (book-demo:85–89,130–152; auth Field has `htmlFor` but book-demo doesn't); placeholder-as-label antipattern everywhere; very small type (`text-[9px]`/`text-[10px]`/`text-[11px]` ubiquitously); error text in light pink `--tavus-bubbletech-4` (register:74,79,87,92) — low contrast on white; `text-white/40` copyright on dark bg (auth-page:203) fails contrast; careers role links have no accessible name beyond heading text and no `href` value; pricing badge class conflict `relative absolute` (pricing:73).
- **SEO:** root layout has title/description/keywords/OG/Twitter (layout:26–61) but **no `metadataBase`, no canonical URLs, no OG image URL** (twitter card `summary_large_image` with no image). Per-page metadata: 22/26 export title-only (stubs export literal "TITLE — Zemest"); none set description/OG. robots.txt allows all crawlers, **references no sitemap; no sitemap.xml/app/sitemap.ts exists**. No JSON-LD anywhere. Arabic content without `lang="ar"` on those elements (dir only).
- **Middleware:** all 26 marketing routes correctly listed public (middleware.ts:4) + `/solutions/*` prefix match (line 11).

---

## 6. Issues / Risks (prioritized, with file:line)

**CRITICAL (trust/legal/business):**
1. **Registration funnel broken end-to-end:** register/page.tsx:30–32 redirects to /dashboard without calling the implemented `/api/auth/register` (api/auth/register/route.ts:5–48); middleware.ts:36–40 then bounces user to /login. Nobody can sign up except via Facebook OAuth.
2. **Deceptive fake success states:** forgot-password/page.tsx:52 claims "We sent a reset link" (no backend route exists); book-demo/page.tsx:64–75 "Got it! We'll reach out within 24 hours" (nothing submitted). Both mislead users into waiting for emails that never come — consumer-protection-adjacent risk in any market, fatal for enterprise trust.
3. **Compliance claims without artifacts:** enterprise/page.tsx:9–15 (SOC 2 II, HIPAA BAA, GDPR, EU residency) + pricing 99.9/99.95% SLAs vs placeholder dpa/trust/status pages (11 stubs). Marketing promising audits/SLAs the company demonstrably lacks = misrepresentation exposure.
4. **Competitor-brand leakage:** careers/page.tsx:6 title "…Tavus — The Human Computing Company"; enterprise/page.tsx:11 "Deploy Tavus in your own VPC"; partnerships/page.tsx:13 "Integrate Tavus"; research/page.tsx:38,148; blog passim. Presenting another company's product/roles/research as your own (entire blog + research page) is IP/credibility risk.

**HIGH:**
5. **Primary funnel dead-ends:** solutions/page.tsx:10–13 links to 4 placeholder solution pages; footer advertises 7 stub/`#` destinations. Paid traffic → "coming soon".
6. **19 blog links 404** (blog/page.tsx:53,100; no `/blog/[slug]` route exists).
7. **No lead capture anywhere:** every marketing form (§3) discards data. Zero conversion instrumentation/analytics on all pages.
8. **Pricing fiction:** tiers/quota/SLA (pricing/page.tsx:8–37) have no backend enforcement (no billing code in zemest backend); "cancel from your dashboard" (pricing:44) false; Discord support nonexistent.
9. **Placeholder pages in prod index:** 11 pages with literal "TITLE — Zemest" metadata are crawlable (robots.txt allows *) → SEO poisoning of own domain.

**MEDIUM:**
10. AuthPage (get-started/login) has zero validation and dead Google/SSO buttons (auth-page.tsx:116,173–181); ToS/Privacy links `#` (128–129) — legally the consent checkbox binds to nothing.
11. `page-shell.tsx:1` unnecessary `"use client"` — bundle bloat across all marketing pages.
12. Raw `<a>` vs `Link` inconsistency (pricing:97, partnerships:77, blog:53/100).
13. Label/input association missing in book-demo (130–152) — a11y.
14. No sitemap/canonical/metadataBase/OG image (layout.tsx:26–61; public/robots.txt) — weak SEO for a content-heavy marketing site.
15. Future-dated content everywhere (© 2026, "Last updated: August 2026", blog Aug 2026) — looks fabricated.
16. Unverifiable headline stats (solutions/page.tsx:10–13: 3.2×, +47%, +38%, −41%) with no footnote/source.
17. Footer dead links (footer.tsx:46–48) + 3 duplicate /research links (37–41) + false "all links go to real Zemest pages" comment (5).
18. Register error messages in low-contrast pink (register:74–92); `relative absolute` conflict (pricing:73).
19. Icon/animal mismatch Rabbit=Feather, Rat=Bird (models/page.tsx:12,30) — brand polish.

**LOW:** USD-only pricing for Egyptian SMBs; "accent" vs "dialect" drift (products:12, navbar:137 vs models:14); Growth SLA only in table; nav lacks Blog/Support links.

---

## 7. Quality Ratings (1–10) & Overall Assessment

| Page | Rating | Justification |
|---|---|---|
| /models | **8** | Best in class: real product content, Arabic sample w/ RTL, specs, capabilities; minor: dead CTA, icon oddity, title-only meta |
| /pricing | **7** | Real tiers + comparison table + 6 FAQs; docked: USD-only, fictional backend, dead CTAs, `<a>` links, minor SLA inconsistency |
| /products | **7** | Clean, real, correct `Link` usage; thin (3 cards), duplicate of /models content, dead CTAs |
| /solutions | **6.5** | Good channel map + stats; but 4/6 CTAs dead-end into placeholders; stats unsourced |
| /register | **5.5** | Only page with real validation + working Facebook OAuth; but submit is fake, ignores real API, dead Google/SSO |
| /get-started | **4** | Clean wrapper; underlying form completely inert (preventDefault), no validation, ToS links `#` |
| /login | **4** | Same inert AuthPage; real login BFF route orphaned |
| /forgot-password | **3** | Polished UI but a functional lie — fakes an email that is never sent |
| /privacy | **4** | Zemest-real but 3-paragraph toy policy: no jurisdiction, subprocessors, retention, DPA link; claims dashboard export/delete that doesn't exist |
| /terms | **4** | Real but skeletal; no governing law/liability; billing terms describe nonexistent billing |
| /enterprise | **3** | Full Tavus content; unsubstantiated compliance/SLA claims; wrong product vocabulary (PALs) |
| /book-demo | **3** | Tavus framing + form that silently discards all leads (the page's entire purpose) |
| /research | **2.5** | 100% Tavus research narrative (Raven/Sparrow/Dom/"human computing"); 5 dead paper links |
| /partnerships | **2.5** | Tavus programs + fabricated stats (100+ partners, $50k credits, 30% rev share); all CTAs → dead demo form |
| /careers | **2** | Wrong company in title tag; SF/US roles for an Egyptian startup; 8 dead apply links |
| /blog | **2** | 19 hardcoded Tavus posts, all links 404, dead newsletter, future dates |
| 11 placeholder pages (brand-kit, press-kit, dpa, trust, status, support, acceptable-use, solutions×4) | **1** | Literal template stubs with "TITLE — Zemest" metadata shipped to production |

**Overall marketing site assessment: 3.5/10.**
The design system is genuinely strong — a coherent, distinctive neo-brutalist identity applied with unusual discipline across every page, correct server-component/SEO structure for static pages, and good semantic/a11y foundations in places. But the site is a **half-completed rebrand of a Tavus template**: 5 pages still sell another company's product, 11 pages are literal placeholder stubs (including the entire solutions funnel and the trust/DPA/status surface that the enterprise and pricing pages depend on), **every single form is dead or actively deceptive**, the email signup funnel is functionally broken despite a fully-implemented register API sitting unused one directory away, and the pricing/SLA/compliance claims have no backend or legal artifacts behind them. As a marketing asset, the site can generate zero leads and actively damages credibility (fake emails, competitor branding, 404 blog) — it needs a content-and-wiring sprint (forms → existing BFF routes, de-Tavus pass, real solutions/legal pages) more than a code rewrite. The one bright spot: the core Zemest pages (models/pricing/products/solutions) prove the team can produce on-brand, on-message content quickly.

---

## Appendix A — Page count & classification
- **Total pages analyzed:** 26 in-scope (+ shared navbar/footer/page-shell/auth-page, not-found, middleware, 3 BFF auth routes, robots.txt, root layout).
- Real content: 10 (models, pricing, products, solutions, privacy, terms, get-started, register, login, forgot-password — last 4 functional shells)
- Tavus leftovers: 5 (blog, careers, enterprise, partnerships, research)
- Placeholders: 11
- Forms: 6 (all dead/fake); working integrations: 1 (Facebook OAuth); orphaned-but-implemented BFF routes: 2 (/api/auth/login, /api/auth/register).
