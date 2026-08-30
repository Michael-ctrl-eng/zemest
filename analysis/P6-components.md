# P6 — Site Components & UI Kit Deep Analysis (zemest-platform)

**Agent:** general-purpose (components) · **Scope:** `src/components/site/` (13 target files), full `src/components/ui/` inventory (49 files), `src/app/models/page.tsx` ↔ `models.tsx` relationship.
**Method:** every target file read line-by-line; every claim cross-referenced via repo-wide grep (imports, CSS utilities, public assets, dependency usage); prior reports P1 (app shell/design system) and P2 (marketing pages) used as ground truth for shared chrome.

---

## 1. Site Component Catalog

### 1.1 Landing page composition (ground truth)

`src/app/page.tsx` renders, in order: `Navbar → Hero → Logos → UseCases → WhatIsPAL → Products → ConversationalDemo → PioneeringSection → Models → BuildWithUs → CTA → Footer`.

**Critical discovery:** `features.tsx`, `how-it-works.tsx`, `solutions.tsx`, `stats.tsx`, `testimonials.tsx` are **NOT imported anywhere** (grep-verified: zero importers in `src/`). They are orphaned Tavus-template leftovers. The live landing page is fully Zemest-branded; the dead five are 100% Tavus (AI-video) content with fabricated metrics — see §5/§6.

---

### 1.2 `logos.tsx` (39 lines, "use client" but no client features used)

- **Props:** none (hardcoded 5-logo array). **Used:** `app/page.tsx:3` (live, directly under Hero).
- **Renders:** terminal-black strip, uppercase kicker `"Powering moderation for 100,000+ sellers and the world's most ambitious brands"` (logos.tsx:18), then an infinite CSS marquee (`animate-scroll-x`, 40s linear infinite, tripled array, `mask-fade-x` edge fade).
- **Logos shipped in `/public`:** **Amazon** (`logo-amazon.png`), **Salesforce** (`logo-salesforce.svg`), **Deloitte** (`logo-deloitte.png`), **CVS Health** (`logo-cvs.svg`), **Frame** (`logo-frame.png`).
- **Animations:** CSS-only marquee (no framer-motion); hover opacity 60→100%.
- **Verdict on brand risk: SEVERE.** Real, trademarked logos of Amazon/Salesforce/Deloitte/CVS presented as customers ("Powering moderation for…") with zero evidence any of them use Zemest (pre-launch product; backend has no billing system per P2). Classic template artifact — Tavus's logo wall copied verbatim. Fabricated-endorsement / trademark-infringement exposure.
- Nit: `height={20}` + `style={{height:"auto"}}` conflict (style wins; width fixed by prop) — works but sloppy. `"use client"` unnecessary (pure static render).
- **Rating: 3/10** (functional marquee, catastrophic content/legal risk).

### 1.3 `use-cases.tsx` (229 lines, interactive)

- **Props:** none; internal `cases[]` of 5 items + `useState(0)` carousel.
- **Used:** `app/page.tsx:4` (live).
- **Content (5 cards):** WhatsApp Agent ("Replies like the buyer is talking to you", 3.2× reply rate), Instagram Agent ("Closes sales in the DMs while you sleep", +47% DM→sale lift), Messenger Agent ("Every comment, every message, answered instantly", +38% CSAT), Inventory Agent ("Knows what's in stock before you do", −41% lost sales), Rabbit v1 (Arabic, 30+ dialects).
- **Interaction:** prev/next arrow buttons (desktop only, `hidden lg:flex`), clickable side cards (`CarouselSideCard`), 5 dot buttons with `aria-label` (good a11y); `AnimatePresence mode="wait"` center-card swap (fade±16px, 0.3s).
- **Images:** all five are **Tavus marketing assets** (`/tavus-hero.avif`, `/tavus-teaching-machines.avif`, `/tavus-v2-portrait.avif`, `/tavus-cvi-eq.avif`, `/tavus-art-portrait.avif`) — AI-video-company imagery illustrating a moderation product; visual mismatch + IP risk.
- **Issues:** "See it in action" → `href="#"` (use-cases.tsx:139) dead link; inline scanline hardcodes **old green accent** `rgba(56,242,97,0.15)` (line 117) though the token `--tavus-neon-field-2` is now `#2a2a2a` (commit cfeb37f swap missed inline styles); fabricated stats (§5).
- **Rating: 7/10** (best interactive section; dead CTA + Tavus imagery + stale color).

### 1.4 `what-is-pal.tsx` (62 lines)

- **Props:** none; `layers[]` of 4. **Used:** `app/page.tsx:5` (live).
- **Content:** "WHAT IS AN AGENT?" — 4 capability cards: SEE ("knows a Nike from an Adidas on sight"), HEAR (voice transcription AR/EN), UNDERSTAND ("trained on your old chats… what's in stock right now"), REPLY ("They can't tell it's not you").
- **Design:** white cards, 2px terminal-black borders, 4px offset shadows, hover lift (`-translate` + shadow grow), active press-down, `bg-halftone-light` overlay at 15% opacity, serif display numerals `01–04`.
- **Animation:** staggered whileInView fade+rise (14px, delay i*0.06, once).
- **Issues:** Nike/Adidas trademark name-drop (marketing-acceptable but notable); "can't tell it's not you" is an explicit **non-disclosure claim** — risky under Meta AI-disclosure policy for automated agents.
- **Rating: 7.5/10** (clean, on-system, copy carries compliance risk).

### 1.5 `products.tsx` (174 lines)

- **Props:** none; `products[]` of 3 + internal `ProductVisual({kind})`. **Used:** `app/page.tsx:6` (live).
- **Cards:** RABBIT V1 (Arabic, blue `bubbletech-4`), RAT V1 (English, charcoal `neon-field-2`), INVENTORY CONNECT (amber `atomic-glow`, "Live inventory in every reply").
- **ProductVisual mockups (well-crafted):** rabbit = bilingual chat bubbles ("لو سمحت، عندي بمقاس 42؟" → "أيوا متوفر، 850 جنيه…" with `dir=rtl`); rat = English chat; inventory = 3 stock rows **"Air Max 90 · Size 42 / Air Force 1 · Size 42"** — Nike product trademarks + price formats ($120) mixed with EGP pricing across cards (inconsistent currency story).
- **Design:** `win-title-bar` chrome with 3 fake window buttons, halftone overlay, offset shadows, per-card CTA colors.
- **Issues:** every CTA (incl. "CONNECT SHOP") routes to `/get-started` (products.tsx:99) — label/destination mismatch; raw `<a>` instead of `Link`; "millions of Arabic commerce conversations" claim (§5).
- **Rating: 8/10** (strongest visual storytelling on the page; CTA mismatch + trademark mock data).

### 1.6 `conversational-demo.tsx` (215 lines) — full interaction analysis

- **Props:** none. **Used:** `app/page.tsx:7` (live).
- **Is the chat real? NO — 100% scripted.** A hardcoded 6-message `script` array (lines 10–17: Air Max size 10 EN, Nike size 42 AR, black pair EN). **Zero API calls, zero fetch, zero backend involvement.** `setInterval(2400ms)` increments `idx`; `visible = script.slice(0, idx)` reveals one bubble per tick; after the last message `idx` wraps to 0 via modulo `script.length + 1`, silently clearing the transcript and looping. `elapsed` drives a fake "LIVE · 00:0X" timer.
- **UI:** left copy ("What if your customer couldn't tell it's an agent?" + 4 bullets incl. "Replies in <3 seconds, 24/7"); right fake WhatsApp window: `win-title-bar` ("WHATSAPP · LIVE MODERATION"), 4:3 video area with pulsing `zemest-logo.png` avatar, **9-bar fake waveform** (framer-motion height keyframes, repeat Infinity), scanline overlay (hardcoded old-green `rgba(56,242,97,0.1)`, line 109), PiP "U" self-view box, scrollable transcript, control bar (Volume/Mic **buttons with no onClick — dead controls**), "Reply <3s" badge, start/end toggle (both the big CTA and the phone button toggle `playing`).
- **State correctness:** interval properly cleaned up; `start` resets idx/elapsed. Timer display caps at `00:09` via `Math.min` then stops advancing visually while elapsed grows — cosmetic bug.
- **Verdict:** convincing theater, competently built; but it is a fake demo of a real product whose BFF routes exist — and the "LIVE" badge asserts liveness that is false.
- **Rating: 7.5/10** (execution), with honesty flag.

### 1.7 `pioneering-section.tsx` (82 lines)

- **Props:** none. **Used:** `app/page.tsx:8` (live).
- **Content:** framed `/tavus-shadow-portrait.avif` panel (win-title-bar "ZEMEST · AGENT & THE CUSTOMER", halftone + scanline overlays, lowercase caption chip), then centered heading "Pioneering commerce moderation **since 2024**" and a manifesto paragraph positioning Zemest as "an AI research lab" building "foundational models" for "commerce moderation" (pioneering-section.tsx:61).
- **CTA:** "Start a demo conversation" → `href="#"` (line 72) — dead link pointing at nothing (the actual demo is `#conversational` above).
- **Overclaim:** "research lab / foundational models" vs. a GPT-API-wrapper pipeline (per Z2 backend findings: thin LLM client over hosted models; no training infra anywhere in either repo).
- **Rating: 6.5/10** (beautiful, but dead CTA + positioning fiction).

### 1.8 `models.tsx` (167 lines) — model cards content

- **Props:** none; `models[]` of 2. **Used:** `app/page.tsx:9` (live).
- **Rabbit v1 (RABBIT, blue square):** role "Arabic moderation · every dialect"; desc: flagship Arabic model, "Speaks Egyptian, Gulf, Levantine, Maghrebi, and Sudanese — and replies in the same dialect the customer used. Voice-note transcription built in. **Trained on millions of Arabic commerce conversations.**" Specs: Dialects **30+**, Voice **Native**, Languages Arabic.
- **Rat v1 (RAT, charcoal square):** role "English moderation · every accent"; "Handles US, UK, Australian, Indian, and South African English… Reads images, listens to voice, replies in your brand tone." Specs: Accents **12+**, Voice Native, Languages English.
- **Research strip:** `/tavus-models-birds.avif` thumbnail + "The science behind the agents — Dialect detection · Voice transcription · Image understanding · Inventory reasoning" → button "Our Research" → `/research` (which P2 verified is a placeholder page with Tavus papers — dead-end).
- **Card anatomy:** family chip + color square + version mono label; 3 spec boxes (plastic-1 bg); "Read the model card" → `/models`; halftone overlay; full hover-lift/active-press shadow choreography.
- **"Model card" is marketing fiction:** no benchmarks, evals, context-window, pricing, or model provenance anywhere; the linked page (§1.11) is more copy, not a card.
- **Rating: 8/10** (best-executed Zemest section; unverifiable specs, raw `<a>`, /research dead-end).

### 1.9 `build-with-us.tsx` (111 lines)

- **Props:** none. **Used:** `app/page.tsx:10` (live).
- **Content:** "PARTNERSHIPS" eyebrow; huge serif headline "Wanna make a *deal?*"; agency/platform pitch; **both** CTAs ("Connect with us" and "Explore partnerships") → `/partnerships` (lines 67, 74), which P2 confirmed is a placeholder stub.
- **Visuals:** framed `/tavus-art-portrait.avif` with halftone+multiply scanlines; fake "team" avatar chips labeled **AR / EN / EG / SA / US / +** (language-market pseudo-social-proof).
- **Animation:** slide-in from left/right (x:∓20, 0.6s, staggered 0.1s).
- **Rating: 7/10** (layout good; duplicate CTAs to a stub; avatar chips misleading).

### 1.10 Dead Tavus leftovers (NOT rendered anywhere)

| File | Tavus content summary | Key fabricated claims |
|---|---|---|
| `features.tsx` (151L) | "The platform" bento: **Phoenix-3 model**, real-time rendering <1s, personalized video at scale, 30+ languages, developer-first API; code sample literally calling **`tavus.videos.create`** (line 118) | Lip-sync 98.4%, render 2.4s, SOC 2 Type II, GDPR & HIPAA ready, 99.95% uptime SLA |
| `how-it-works.tsx` (88L) | 4 steps: "Train your replica" (2-min video → studio-grade replica in 10 min), script, "Render with Phoenix-3" (4K/60fps), ship via HubSpot/Braze/Salesforce | Replica training, per-shoot cost claims |
| `solutions.tsx` (258L) | Interactive 5-tab "PAL" solutions: Sales/Healthcare/Interview/L&D/Custom **video agents**; "4K · 60fps" LIVE mockup, `href="#"` CTAs | 3.2× reply rate, +24pt patient CSAT, −38% intake time, 10× throughput, +18pt diversity, −54% time-to-competency, SLA "guaranteed" |
| `stats.tsx` (42L) | 4 stat tiles | **10M+ videos generated monthly / 70+ countries, 2.4s avg render, 30+ languages, 500+ enterprise customers incl. 12 of the F500** |
| `testimonials.tsx` (115L) | 6 masonry testimonials, all quoting **Tavus** by name ("with Tavus in their stack" headline) | Fabricated people/companies (Daniela Reyes/NorthPeak, Marcus Lindqvist/Lumen Retail, Priya Iyer/Cadence Health, Jonas Berger/Helio SaaS, Aisha Karim/Forge Labs, Tomás Oliveira/Beacon Cloud) |

**Bonus proof they're broken orphans:** these five reference CSS classes **`text-gradient`, `bg-radial-purple`, `bg-grid`, `animate-breathe` that are defined nowhere** (grep across all CSS = 0 hits; deleted during the globals.css rebrand). If anyone re-imports them they render with missing gradients/backgrounds. Delete them.

### 1.11 `app/models/page.tsx` (143 lines, server component) ↔ `models.tsx`

- **Relationship: near-duplicate copy, not reuse.** The page re-implements the model cards inline (same structure, border-[3px] instead of 2px, no framer-motion, adds a `SAMPLE CONVERSATION` block per card and a 4-card "What every agent can do" grid via `RetroCard`), rather than importing `Models`.
- **Content drift between the two copies** (both shipped, both crawled):
  - Rabbit dialects: models.tsx:14 lists **5** (Egyptian, Gulf, Levantine, Maghrebi, Sudanese); page.tsx:14 lists **6** (+ **Yemeni**).
  - Rat accents: models.tsx:28 lists 5 (US/UK/AUS/Indian/South African); page.tsx:32 adds **Irish** (6).
  - Page claims again: "answers in <3 seconds" (page.tsx:129), "Trained on millions of Arabic commerce conversations".
- PageHero CTAs: "Try an agent" → `/get-started`. No back-links, no actual model documentation.
- **Rating: page 7.5/10** (richest marketing page per P2; duplication is the defect).

---

## 2. Design System Usage (tavus-* tokens & bitmap effects)

All live sections share a coherent neo-brutalist grammar, driven entirely by `globals.css` (Tailwind v4 CSS-first; `tailwind.config.ts` is dead per P1):

- **Tokens:** `--tavus-terminal-black` (#140206) for 2px/3px borders + hard offset shadows (`shadow-[Npx_Npx_0_0_var(--tavus-terminal-black)]`, e.g. models.tsx:65, products.tsx:70, use-cases.tsx:93); `--tavus-plastic-1` (#f7f4ef) card insets; `--tavus-hardware-gray-8` body text; accent squares from `bubbletech-4` (blue), `neon-field-2` (now charcoal #2a2a2a), `atomic-glow-*` (ambers), `floppy-fog-*`, `frost-*`.
- **Bitmap effects:** `bg-grain` / `bg-grain-tan` section backgrounds (radial dot grid, 18px); `bg-halftone` / `bg-halftone-light` card overlays at 10–15% opacity (products.tsx:73, models.tsx:68, what-is-pal.tsx:42, use-cases.tsx:96); **scanlines via inline `repeating-linear-gradient`** in use-cases/conversational-demo/hero/build-with-us/pioneering (not a utility class — 5 hand-copied inline styles, 3 of them with the stale green, see §6); `mix-blend-multiply` for print feel (build-with-us.tsx:38-41, pioneering-section.tsx:34-37).
- **OS-window motif:** `win-title-bar` (white bar, bottom border, 10px bold uppercase, color-square chip + 3 fake buttons) reused in products, use-cases, conversational-demo, build-with-us, pioneering — strong, consistent signature.
- **Press choreography:** uniform `hover:-translate-x-0.5 -translate-y-0.5 + shadow grow; active:translate + shadow shrink` on every bordered card/CTA — applied consistently across all 8 live sections (verbose: ~60-80 chars of repeated Tailwind per element; no `btn-retro`/`shadow-retro` utility adoption despite them existing in globals.css).
- **Typography:** `font-[var(--font-serif-display)]` (Instrument Serif) display headlines with `serif-italic` accent words ("Two models. *One mission.*"); JetBrains Mono for labels; 9–11px uppercase micro-labels everywhere (matches P2's a11y note).
- **Responsive:** `grid-cols-1 md:grid-cols-2/3 lg:grid-cols-4/5`, `py-16 sm:py-24`, carousel arrows `hidden lg:flex` with dot fallback, `max-w-[1400px]` containers on brutalist sections vs `max-w-7xl` on the dead Tavus ones (two container conventions = two generations of code).
- **Consistency verdict:** the 8 live Zemest sections are remarkably consistent; the 5 dead Tavus sections use an entirely different aesthetic (dark, `border-border/60`, `rounded-2xl`, `backdrop-blur`, `text-gradient`, purple gradients) that matches **nothing** currently shipped — including the dark `Hero`? No: live Hero is light brutalist. The dark aesthetic survives only inside dead files.

---

## 3. shadcn/ui Inventory (49 files, 5,397 LOC)

**Verdict up front: the kit is 100% stock shadcn/ui (new-york style, Tailwind v4 generation — `data-slot` attributes, cva, function components), with ZERO tavus/brutalist customization.** Grep for `tavus|halftone|win-title|terminal-black|shadow-[` across `ui/` returns exactly one hit — sidebar.tsx:483, which is itself stock shadcn's `shadow-[0_0_0_1px_hsl(...)]`. Full-read confirmation: `button.tsx` (59L), `card.tsx` (92L), `input.tsx` (21L), `dialog.tsx` (143L, incl. stock `showCloseButton` prop), `tabs.tsx` (66L), `table.tsx` (116L), `sonner.tsx` (25L), `toast.tsx` (129L, old forwardRef generation), `toaster.tsx` (34L) — all byte-stock.

**Usage cross-reference (grep of every `@/components/ui/<name>` import outside `ui/`):**

| Component | Stock? | External importers | Status |
|---|---|---|---|
| toast.tsx | stock (old API) | `hooks/use-toast.ts`, `ui/toaster.tsx` | **MOUNTED** (layout.tsx:4) but never triggered by any feature |
| toaster.tsx | stock | `app/layout.tsx` | mounted, orphaned |
| button.tsx | stock | 0 (only ui-internal: form/calendar/carousel/pagination/sidebar) | **DEAD** |
| card / input / dialog / tabs / table / select / badge / … (other 46) | stock | 0 | **DEAD** |

- **47 of 49 ui components have zero external usage.** Dashboard/admin pages import *nothing* from `@/components` except `site/navbar`, `site/footer`, `site/mobile-sidebar` — every dashboard table/button/badge is hand-rolled inline JSX instead of the kit. The entire design investment lives in `site/` + globals.css; the shadcn layer is scaffolding ballast.
- **Two parallel toast systems, both unused by features** (confirms P1): shadcn `Toaster` (layout) + custom Zustand `ToastContainer` (site/toast.tsx, also in layout). `use-toast.ts` has the stock `TOAST_REMOVE_DELAY = 1000000` quirk.
- **Dead hooks:** `use-debounce.ts` (0 importers), `use-mobile.ts` (only consumed by dead `ui/sidebar.tsx`).
- **Dead dependencies pulled in only by dead ui files:** `recharts` (chart), `embla-carousel-react` (carousel), `react-day-picker` (calendar), `input-otp`, `react-resizable-panels` (resizable), `vaul` (drawer), `cmdk` (command), `sonner`+`next-themes` (sonner.tsx — next-themes is also imported by a component that's never mounted, and there's no ThemeProvider anywhere).
- **Fully unused deps:** `@dnd-kit/*` (3 pkgs), `react-syntax-highlighter`, `next-auth`, `next-intl`, `@mdxeditor/editor`, `react-markdown`, `uuid`, `date-fns`, `z-ai-web-dev-sdk`.
- **Kit quality as code: 8/10** (current-generation, consistent, a11y-aware stock). **Kit integration value: 1/10** (dead weight; 5.4K LOC + ~15 npm deps for zero rendered UI).

---

## 4. Animation & Interaction Patterns (framer-motion v12)

All 16 framer-motion consumers are in `components/site/` (grep-verified; no dashboard/admin usage).

| Component | Pattern | Details |
|---|---|---|
| models.tsx | scroll-reveal | cards fade+y16, delay i*0.08; strip y12; `viewport:{once:true, margin:"-60px"}` |
| products.tsx | scroll-reveal | h2 y12; cards y16 stagger 0.08 |
| use-cases.tsx | reveal + swap | h2 reveal; `AnimatePresence mode="wait"` card swap y±16/0.3s |
| what-is-pal.tsx | scroll-reveal | y14, delay i*0.06 |
| conversational-demo.tsx | loop + list | `AnimatePresence initial={false}` chat bubbles y8; **9 infinite-repeating waveform bars** (height keyframes, 0.6+i*0.05s); `animate-pulse` avatar |
| build-with-us.tsx | slide-in | x∓20, 0.6s, 0.1s stagger |
| pioneering-section.tsx | reveal cascade | y20/y12 ×3, delays 0.1/0.16/0.22 |
| logos.tsx | CSS only | 40s infinite marquee |
| dead five | scroll-reveal | same fade-rise idiom (features y16/-80px; stats y12; testimonials y12 stagger (i%3)*0.05; solutions AnimatePresence tab swap + `animate-breathe`; how-it-works y14) |

- **Reduced-motion: NONE.** Zero `useReducedMotion` and zero `prefers-reduced-motion` in the entire repo. Infinite marquee + 9 infinite keyframe bars + pulse dots run regardless of user preference — an a11y gap (WCAG 2.3.3) and the only real perf concern; scroll-reveals are cheap (`once:true` everywhere, transform+opacity only).
- Bundle note: shipping framer-motion for marketing fade-ins is heavy; the interactive sections (solutions carousel pattern, AnimatePresence) justify it more, but solutions is dead.
- Interaction states beyond motion: consistent hover-lift/active-press (CSS), tab/carousel state via useState, no focus-visible styles on the brutalist buttons (contrast with shadcn kit which has them — but the kit is unused).

---

## 5. Content Claims Audit (live-page claims flagged)

| Claim | Location | Backend support |
|---|---|---|
| "Powering moderation for **100,000+ sellers** and the world's most ambitious brands" (+ Amazon/Salesforce/Deloitte/CVS logos) | logos.tsx:18 | **None.** No seller-count data anywhere; enterprise logos fabricated (template artifact) |
| "**3.2× reply rate**, **+47% DM→sale lift**, **+38% CSAT**, **−41% lost sales**" | use-cases.tsx:15,23,31,39 | **None.** No analytics/metrics pipeline in either repo; no customer deployments (no billing) |
| "**30+ dialects**" (Rabbit) / "**12+ accents**" (Rat) | models.tsx:16,30; use-cases.tsx:47; products | **Unverifiable.** No dialect-classification model, eval set, or language-detection code in backend; agent is a single GPT prompt pipeline (Z2) |
| "Trained on **millions of Arabic commerce conversations**" | models.tsx:14; products.tsx:12; app/models/page.tsx:14 | **False as stated.** No training/fine-tuning infrastructure exists; backend consumes a hosted LLM API |
| "Replies in **<3 seconds**, 24/7" (×3) + "Reply <3s" badge + "LIVE" demo | conversational-demo.tsx:53,58,195 | **None.** No latency measurement/SLA machinery; webhook processing is synchronous inline (Z2/Z4); demo is a hardcoded script, not live |
| "Voice: **Native**" / voice-note transcription built in | models.tsx:17,31 | **Partial/unverified.** No transcription service found in backend scope reports (Z1–Z9); WhatsApp ingest itself absent (P2) |
| "Reads images… knows a Nike from an Adidas on sight" | what-is-pal.tsx:7 | **Unverified** — no vision tooling found in backend analyses |
| "Live inventory check before every reply" / Inventory Connect | products.tsx:34; conversational-demo.tsx:61 | **Backend exists partially** (products/orders models, Z6) but no live POS integration; demo values hardcoded |
| "They can't tell it's not you" | what-is-pal.tsx:10 | Deception positioning; no AI-disclosure feature; Meta-platform policy risk |
| "Zemest is an **AI research lab**… **foundational models**… pioneering since 2024" | pioneering-section.tsx:61 | **Overclaim.** API-wrapper architecture; no research artifacts (see /research stub) |
| "Read the model card" / "explore the research" | models.tsx:119,155 | Destinations contain no cards/research (P2: /research = Tavus papers placeholder) |
| Dead-file claims (not user-visible but in repo): 10M+ videos/mo, 500+ enterprise customers, 12 of F500, 98.4% lip-sync, SOC 2 Type II, HIPAA, 99.95% SLA, 6 named testimonials | features/stats/testimonials | **All fabricated Tavus-template content** — liability if ever re-imported; SOC 2/HIPAA/SLA also appear in live enterprise page (P2) |

---

## 6. Issues / Risks (prioritized, with file:line)

1. **CRITICAL (legal):** Fabricated customer logo wall — Amazon, Salesforce, Deloitte, CVS Health, Frame shipped in `/public` and rendered as "Powering moderation for…" (`logos.tsx:5-11,18`). Trademark/false-endorsement exposure; remove or replace.
2. **CRITICAL (brand/IP):** 5 orphaned full-Tavus components in the repo (`features.tsx`, `how-it-works.tsx`, `solutions.tsx`, `stats.tsx`, `testimonials.tsx`) containing "Phoenix-3", `tavus.videos.create` (features.tsx:118), Tavus testimonials, F500 claims — plus ~20 `tavus-*.avif` assets still used by live sections (use-cases.tsx:14-46, models.tsx:137, build-with-us.tsx:32, pioneering-section.tsx:28) and `tavus-logo.svg` in `/public`. Confirms P2's "rebrand of Tavus template" at component level.
3. **HIGH (truthfulness):** Fake "LIVE" demo (`conversational-demo.tsx:146`) — scripted setInterval chat presented as live moderation; all product metrics fabricated (§5); "model card" links to copy pages.
4. **HIGH (dead code / bundle hygiene):** 47/49 shadcn components + 2 hooks + ~16 npm deps unused; both toast systems mounted but never called; `z-ai-web-dev-sdk`, `next-auth`, `next-intl`, `@dnd-kit`, `react-markdown`, `uuid`, `date-fns`, `react-syntax-highlighter`, `@mdxeditor` fully unused.
5. **MEDIUM (consistency bug):** Accent swap commit cfeb37f (#38f261→#2a2a2a) missed inline scanlines — stale green `rgba(56,242,97,…)` hardcodes at `use-cases.tsx:117`, `conversational-demo.tsx:109`, `hero.tsx:144`. Should reference a token (or the scanline should have become charcoal — currently invisible-on-dark intent unclear).
6. **MEDIUM (content drift):** models.tsx vs app/models/page.tsx diverge (Yemeni/Irish added on page only; 5 vs 6 dialects) — duplicated data sources with no shared module.
7. **MEDIUM (a11y/UX):** No `prefers-reduced-motion` support repo-wide; infinite marquee/waveform ignore it. Dead controls: mic/volume buttons (`conversational-demo.tsx:188-192`), `href="#"` CTAs (use-cases.tsx:139, pioneering-section.tsx:72, solutions.tsx:195). All internal nav uses raw `<a>` (models.tsx:115, products.tsx:99, build-with-us.tsx:67,74) → full page reloads instead of `Link`.
8. **LOW:** CTA/destination mismatches ("CONNECT SHOP"→/get-started, products.tsx:99; "Start a demo conversation"→"#", pioneering-section.tsx:72); both build-with-us CTAs identical target; `logo.tsx` unnecessary "use client"; timer cosmetic bug (conversational-demo.tsx:146 caps at 00:09); 9–11px micro-type throughout (P2 echo); Nike trademarks in mock data (products.tsx:121-141, use-cases inventory rows 154-156).
9. **LOW (perf):** framer-motion in client bundle for pure fade-ins; `Models` section could be server-rendered except motion wrappers.

---

## 7. Quality Ratings

| Group | Rating | Justification |
|---|---|---|
| models.tsx | **8/10** | Best on-brand execution (win-chrome, halftone, spec boxes, press choreography); docked for unverifiable specs, raw `<a>`, /research dead-end, duplication drift with /models page |
| products.tsx | **8/10** | Strongest storytelling (ProductVisual chat/stock mockups); CTA mismatch, trademark mock data |
| conversational-demo.tsx | **7.5/10** | Polished fake demo, clean state/timer handling, RTL support; dead mic/volume buttons, "LIVE" dishonesty, stale green |
| what-is-pal.tsx | **7.5/10** | Tight 4-card grid, perfectly on-system; copy risk (trademarks, non-disclosure boast) |
| use-cases.tsx | **7/10** | Real carousel with side-card affordance + dots a11y; "#" CTA, Tavus imagery, stale green, fabricated stats |
| build-with-us.tsx | **7/10** | Good asymmetric layout + avatar chips idea; duplicate CTAs to a stub page |
| pioneering-section.tsx | **6.5/10** | Gorgeous framing; dead "#" CTA, research-lab overclaim |
| logos.tsx | **3/10** | Technically fine marquee; content is a legal liability |
| app/models/page.tsx | **7.5/10** | Richest marketing page; duplicated card code + drift |
| Dead Tavus five (features/how-it-works/solutions/stats/testimonials) | **1.5–2/10** | Not rendered (mercy), but full Tavus brand content + fabricated claims + references to deleted CSS classes; pure liability |
| shadcn/ui kit (49 files) | **Code 8/10 · Value 1/10** | Pristine stock, current gen, zero customization; 96% dead including 16 deps |
| **Overall site-components layer** | **6/10** | A genuinely excellent, consistent brutalist design system for the 8 live sections, undermined by fabricated-everything content (logos, stats, "live" demo), leftover Tavus contamination, and a completely unused UI kit |

---

## 8. Recommended next actions (for synthesis agent)

1. Delete the 5 dead Tavus components + `tavus-*` assets + real-brand logos; replace logo strip with Egyptian-market placeholder or remove.
2. Extract model data to one shared module consumed by both `models.tsx` and `/models` page.
3. Either wire conversational-demo to the existing BFF/agent API or relabel it "Example conversation" (remove LIVE badge, <3s claims).
4. Purge unused ui components + 16 deps (or actually adopt the kit in dashboard instead of hand-rolled JSX).
5. Add `prefers-reduced-motion` guards for marquee/waveform; convert raw `<a>` to `Link`; fix stale-green inline scanlines to tokens.
