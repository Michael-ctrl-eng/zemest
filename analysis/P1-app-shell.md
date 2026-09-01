# P1 — Platform App Shell Analysis (zemest-platform)

**Task ID:** P1 · **Agent:** general-purpose · **Scope:** root layout, landing page, 404, middleware, site navigation/shell components, design system, deployment config.
**Repo:** `/home/z/my-project/repos/zemest-platform` (Next.js 16/App Router — package.json pins `next: ^16.1.1`, despite repo being described as Next 15; React 19, Tailwind v4, Bun).

---

## 1. App Shell Architecture

### Root layout (`src/app/layout.tsx`, 79 lines)
- **Fonts (3, via `next/font/google`, all self-hosted at build):**
  - `Inter` → CSS var `--font-geist-sans` (weights 400–900) — body/sans.
  - `Instrument_Serif` → `--font-serif-display` (400, normal+italic) — the display headline font (Tavus-style serif italic accents).
  - `JetBrains_Mono` → `--font-geist-mono` (400/500/700) — mono.
  - ⚠️ Two *additional* display fonts (`Jersey 15`, `Bitcount Grid Double Ink`) are loaded via a **render-blocking Google Fonts `@import` at the top of globals.css:2** instead of `next/font` — inconsistent, slower, privacy-leaking.
- **Metadata:** full `Metadata` export — title "Zemest — AI Moderation Agents", 12 SEO keywords, authors, favicon (`/zemest-logo.png`), OpenGraph + Twitter card (`summary_large_image`). No `metadataBase`, no canonical URL — OG images/urls will be relative (minor SEO gap).
- **Providers:** **none.** No `QueryClientProvider` (React Query), no theme provider (`next-themes` is in package.json but unused), no auth provider, no i18n provider (`next-intl` installed but unused — no locale layout). The BFF/session model means the shell stays provider-free; dashboard pages presumably create their own React Query context (out of P1 scope).
- **Global overlays mounted in root layout:** `<Toaster />` (shadcn toast, `src/components/ui/toaster.tsx`) and `<ToastContainer />` (custom Zustand toast, `src/components/site/toast.tsx`). **Two parallel toast systems mounted globally** (see §7/§9).
- `<html lang="en" suppressHydrationWarning>`, body applies font vars + `antialiased bg-background text-foreground`.

### Landing page composition (`src/app/page.tsx`, 33 lines)
Pure server component orchestrating 11 client sections in order:
`Navbar → Hero → Logos → UseCases → WhatIsPAL → Products → ConversationalDemo → PioneeringSection → Models → BuildWithUs → CTA → Footer` (footer outside `<main>`). Wrapper: `div.relative.min-h-screen.flex.flex-col` with `main.flex-1`.
- **Client/server split:** `page.tsx`, `layout.tsx`, `not-found.tsx` are server components; **every** section component in `src/components/site/*` begins with `"use client"` (framer-motion + hover state). There is zero server data-fetching on the landing page — it is a fully static marketing page whose interactivity is 100% client-side.

### 404 (`src/app/not-found.tsx`, 39 lines)
Server component reusing `Navbar`/`Footer` + inline "ERROR 404" eyebrow (black square bullets), giant serif "Not found" (7xl/9xl), playful copy, and a hard-shadow "Back to home" button. Background `bg-tavus-header-bg` (defined as a CSS utility in globals.css:229). Uses `PageSection`-style idioms inline rather than the shared `PageHero` (acceptable duplication).

---

## 2. Middleware Deep-Dive (`src/middleware.ts`, 55 lines)

### Line-by-line trace
- **`publicRoutes` (L4):** 24 exact paths — `/`, `/login`, `/register`, `/get-started`, `/forgot-password`, `/pricing`, `/enterprise`, `/research`, `/careers`, `/blog`, `/book-demo`, `/partnerships`, `/solutions`, `/products`, `/models`, `/privacy`, `/terms`, `/acceptable-use`, `/dpa`, `/support`, `/trust`, `/status`, `/brand-kit`, `/press-kit`. This is essentially the full marketing sitemap.
- **`isPublicRoute(pathname)` (L7–16):**
  1. exact match in the array;
  2. `startsWith("/solutions/")` → whitelists the 4 solution sub-pages (`/solutions/{whatsapp,instagram,messenger,inventory}`);
  3. `startsWith("/_next/")` **or `/api/`** → all BFF API routes bypass middleware (they enforce their own auth);
  4. regex `\.(svg|png|jpg|jpeg|webp|avif|ico|webmanifest)$` → static asset extensions public.
- **`middleware()` (L18–51):**
  1. Public → `NextResponse.next()` immediately.
  2. `isProtected = startsWith("/dashboard") || startsWith("/admin")` (L27). Anything else non-public (e.g. a typo'd route) → `next()` (falls through to not-found).
  3. **Auth check (L34):** `request.cookies.get("zemest_auth") || request.cookies.get("sb-access-token")` — presence-only check of either cookie. `zemest_auth` is the httpOnly JWT set by the BFF login route (`src/app/api/auth/login/route.ts:29`); `sb-access-token` is a **Supabase legacy name — no Supabase in this stack, so it's a dead check that nonetheless widens the bypass surface** (any client-set `sb-access-token=1` non-httpOnly cookie passes).
  4. Missing → redirect to `/login?redirect=<pathname>` (L38–40).
  5. **Admin gate (L44–48) is a NO-OP:** empty block with comments admitting the JWT `is_superadmin` decode is not performed; "real check happens client-side via GET /api/auth/me".
  6. Returns `next()`.
- **Header manipulation:** none. No `x-user-id` injection, no path rewrites, no CSP/security headers, no locale negotiation.
- **Matcher (L53–55):** `/((?!_next/static|_next/image|favicon.ico).*)` — runs on every route including `/api/*` (short-circuited public) and all document requests.

### Auth-flow reality check (cross-file trace)
1. Unauthenticated user hits `/dashboard/x` → middleware 307 → `/login?redirect=/dashboard/x`.
2. `/login` renders `AuthPage mode="login"` — **whose form is `onSubmit={(e) => e.preventDefault()}` (auth-page.tsx:116) and never calls `/api/auth/login`.** The BFF login route (which correctly sets httpOnly `zemest_auth` + `zemest_refresh` cookies, `secure` in prod, `sameSite=lax`, 24h/30d access + 7d refresh) is **dead code from the UI's perspective** — only the Facebook button (`window.location.href = "/api/auth/facebook"`, auth-page.tsx:168) actually engages the BFF.
3. **The `?redirect=` query param is never read anywhere** (grep: zero consumers). Post-login return-to-page is unimplemented.
4. Therefore the entire middleware auth flow is scaffolding: cookie presence ⇒ pass; no JWT signature/expiry/role validation server-side at the edge.

---

## 3. Navigation Components

### Navbar (`src/components/site/navbar.tsx`, 153 lines, client)
- **AnnouncementBar (L132–152):** light-blue (`bubbletech-1`) strip, "Rabbit v1 is now live: Arabic moderation with every accent — trained on your chats" + "Learn more" → `/models`. Close button sets local state — **not persisted (localStorage/sessionStorage)**, so it reappears on every reload/navigation.
- **Sticky shell:** `div.sticky.top-0.z-50`; inner `max-w-[1400px]` with `py-3`; nav row `h-[60px]`.
- **Nav items (L9–16):** PRODUCTS `/products` ●, SOLUTIONS `/solutions` ●, MODELS `/models` ●, ENTERPRISE `/enterprise` ●, RESEARCH `/research` ●, PRICING `/pricing` (no bullet). Rendered as boxed "chips" (`border-[3px]`, hard 3px shadow, hover lifts, active presses) — the Tavus neo-brutalist button idiom. Bullets scale + turn blue on hover. No dropdowns/mega-menus (unlike real tavus.io).
- **Auth-aware states: NONE.** Static `LOGIN → /login` (hidden below `sm`) and `GET STARTED → /get-started` (always visible) — the marketing navbar is identical for logged-in users; no avatar/user menu (the dashboard uses its own separate header instead).
- **Scroll behavior:** `useEffect` scroll listener (passive) toggles `scrolled` past 60px — **but `scrolled` is dead state: assigned, never read** (grep confirms only L19). The comment "Sticky transparent navbar" implies an unimplemented restyle-on-scroll.
- **Mobile:** hamburger (lg:hidden) toggles a framer-motion `AnimatePresence` drawer (opacity+height, 200ms) with a 2-col grid of the same 6 items; links close the drawer. No backdrop, no body-scroll lock, no `aria-expanded` on the toggle (only `aria-label`).
- **Logo:** boxed ZEMEST chip w/ `next/image` logo (priority, 32×32).

### MobileSidebar (`src/components/site/mobile-sidebar.tsx`, 122 lines, client)
Dashboard-side drawer for `/dashboard/[tenantId]/*` (mounted by `dashboard/[tenantId]/layout.tsx:83`).
- **Toggle:** fixed bottom-right FAB (`md:hidden`, z-50) — floating action button pattern instead of top hamburger.
- **Drawer:** framer-motion slide-in from `x:-100%` (tween 250ms, z-70, w-64, white, 3px right border), backdrop fade at z-60 (50% terminal-black).
- **11 items (L24–36):** Overview `''`, Chat `/chat`, Products `/products`, Orders `/orders`, Customers `/customers`, Conversations `/conversations`, Crawl & Knowledge `/crawl`, Style Learning `/style`, Scheduler `/scheduler`, Insights `/insights`, Settings `/settings` — all relative to `basePath = /dashboard/${tenantId}`, each with a lucide icon.
- Header: "MENU" title + X; "ALL BUSINESSES → /dashboard" back-link. Active state: exact `pathname === fullPath` match (ⓘ trailing-slash routes won't match; index works since `href: ""`). Drawer auto-closes on every link click. Uses `scrollbar-thin`.
- ⚠️ **Duplication:** the same 11-item `sidebarItems` array is defined **twice** (mobile-sidebar.tsx:24 and dashboard/[tenantId]/layout.tsx:21) — drift risk.

### Footer (`src/components/site/footer.tsx`, 177 lines, client)
- **7 link groups (L6–70), 27 links total:**
  - COMPANY: Pricing, Enterprise, Careers, Partnerships
  - RESOURCES: Blog, Brand kit, Press kit, Book a demo
  - PRODUCT: Rabbit v1 → `/models`, Rat v1 → `/models`, Inventory Connect → `/products`, Solutions
  - RESEARCH: Overview/Dialect Detection/Voice Transcription/Image Understanding — **all 4 point to `/research`** (placeholder anchors)
  - SOCIALS: LinkedIn/X/Discord → **`#` dead links**; Email → `mailto:hello@zemest.ai`
  - LEGAL: Privacy, Terms, Acceptable use, DPA
  - SUPPORT: Support center, Trust center, Status, Contact → `/book-demo`
  - Each group header is a black "chip" with a white square bullet.
- **Bottom band:** pink `bubbletech-4` section with **two inline bitmap dot-pattern overlays** (10px white dots @40%, 6px dark dots @20% `mix-blend-overlay`) — hand-rolled, duplicating the `.bg-halftone-*` utilities.
- "EXPLORE WITH AI:" row: accessibility person icon + decorative Z/@/#/* squares (no links). Copyright "© 2026 ZEMEST | THE COMMERCE MODERATION COMPANY | ALL RIGHTS RESERVED". **Giant 40%-opacity `zemest` wordmark** at `clamp(80px, 16vw, 200px)`.
- `"use client"` on the footer is unnecessary (no hooks) — needless JS bundle.

---

## 4. Hero + CTA

### Hero (`src/components/site/hero.tsx`, 217 lines, client)
- **Layout:** full-bleed section pulled under the sticky navbar via `-mt-[80px] pt-[80px]` (nav actual height ≈ 84px → ~4px gap; minor). 12-col grid: copy (5) / window stack (7).
- **Visual layers:** `cta-bg.webp` full-bleed `<Image fill priority>` (LCP) → 55% terminal-black scrim → **bitmap dot-grain overlay** (inline radial-gradient 8px grid, `mix-blend-overlay`, 20% — the "premium bitmap effect" from the branding) → floating hand illustrations `tavus-hand-left/right.avif` (`animate-float-soft[-2]`, hidden < lg) → 3px bottom rule.
- **Copy:** H1 in Instrument Serif, 44→76px: "Commerce just got an agent." in **`font-jersey` (Jersey 15 handwritten font) colored `--tavus-neon-field-2` (#2a2a2a charcoal — was bright green `#38f261` before commit cfeb37f)**, then "Your customers won't know it's *not you*." (serif italic + blue `bubbletech-1`), ending with an animated blinking caret (`animate-pulse` block cursor — note: globals.css defines a fancier `.animate-caret` utility that hero does **not** use).
- **Sub-copy:** "Ready-made AI agents that **moderate** your **WhatsApp**, **Facebook**, and **Instagram** chats — trained on your old conversations… They read text, voice, and images, check inventory, and close the sale." (blue emphasis spans).
- **CTA:** "Start building" → `/get-started` (blue `bubbletech-4` box button, ArrowRight).
- **Right column `HeroWindows` (L111–216):** two overlapping retro OS windows (`.win-title-bar` with fake min/max/close dots):
  - Back: "WHATSAPP CHAT" window, rotated −1.5°, `tavus-teaching-machines.avif`, green scanline texture, caption "agent & the customer".
  - Front: "LIVE MODERATION" window, rotated +2°, `tavus-hero.avif`, LIVE badge (pulsing dot), "AR · EN" chip, **"TALK TO AGENT" button → `href="#"` (dead)**.
  - Floating stat card: "Reply >3s · Real-time" (`animate-float-soft`).
- **Animation:** framer-motion throughout — h1 fade-up (0.6s), p (delay .08), CTA (delay .14), back window (delay .2, rotate-in), front window (delay .3), stat card (delay .7). Entrance-only; no scroll-triggered effects in hero.

### CTA (`src/components/site/cta.tsx`, 84 lines, client)
- `section#pricing` on `bg-periwinkle-cloud`; card: white, 2px border, 8px hard shadow, 4 colored corner squares (blue / **#2a2a2a charcoal** / orange / lilac).
- **framer-motion `whileInView`** (once, −60px margin, 0.6s fade-up).
- Copy: eyebrow "START BUILDING"; H2 "Configure your first agent in *less than 5 minutes*"; sub "Create an account, connect your WhatsApp / Facebook / Instagram, train your agent on your old chats, and ship your first reply before your coffee gets cold. No API, no developer setup…"
- **CTAs:** "Get started" → `/get-started` (primary blue) and "Talk to sales" → `/book-demo` (white). Plain `<a>` (not `next/link`) → full page navigations.
- Trust row: 14-day free trial · SOC 2 Type II · Cancel anytime · 24/7 support (charcoal square bullets).

---

## 5. Design System

### Token architecture (`src/app/globals.css`, 511 lines — the real design system)
CSS-first Tailwind **v4**: `@import "tailwindcss"` + `@theme inline` block mapping ~40 CSS vars into TW utilities (colors, fonts `--font-sans/mono/serif`, radius). `@custom-variant dark` defined.

**Tavus primitives (globals.css:51–95), 45+ tokens in 10 families:**
- `plastic-1..4` `#f7f4ef → #d9d0c2` (warm paper/cream backgrounds)
- `terminal-black` **`#140206`** (near-black w/ purple cast — the ink for every border/shadow)
- `hardware-gray-8/9` `#484748/#28292a` (secondary text)
- `bubbletech-1..4` `#b8deff → #4aa8ff` (**primary blue**; 4 = CTA blue)
- **`neon-field-1..4` — the "#2a2a2a accent" (commit `cfeb37f`, latest): was green `#7cff98/#38f261/#1bd944/#0cb531`, now charcoal `#4a4a4a/#2a2a2a/#1f1f1f/#141414`.** `neon-field-2` (#2a2a2a) is the main accent: hero kicker, "TALK TO AGENT" button, LIVE dots, CTA bullets/corner, toast success icon, all "success/delivered/in_stock" status colors in `lib/utils.ts`. The commit also flipped text-on-dark-bg to white across 28 files.
- `atomic-glow-0..6,00` (orange/amber family), `floppy-fog-1..8` (lilac), `keyboard-tan-1..4` (peach), `frost-1..5` (ice blue), `retrograde-lilac-0/1/3`, `beige-800`.

**shadcn mapping (globals.css:97–128):** `--background: plastic-1`, `--primary: bubbletech-4`, `--border: terminal-black`, `--destructive: bubbletech-4` (**destructive == primary blue — semantic collision**), `--radius: 0` (**everything is sharp-cornered**), charts 1–5 from tavus families. **`.dark` block (L131–158) is a verbatim copy of `:root` — dark mode exists structurally but is visually identical to light; no dark palette is actually designed**, and no theme toggle exists anywhere.

**Signature utilities (`@layer utilities`, L179–511):**
- `shadow-retro[-sm/-lg/-xl/-2xl]`: hard offset shadows (no blur), 2–10px.
- Bitmap/halftone family: `bg-grain`, `bg-grain-tan`, `bg-grain-dark`, `bg-periwinkle-cloud`, `bg-tavus-header-bg`, `bg-halftone[-light/-white/-fade/-poster]`, `bg-crosshatch`, `bg-pixel-grid`, `bg-bitmap-noise`, `bg-dither`, `bg-scanlines-thick`, `scanlines`, `img-glitch` — this is the **"premium bitmap effect"**: dotted/dithered print-style textures built purely from layered radial/repeating gradients (no image assets).
- `win-frame` / `win-title-bar` — retro OS window chrome; `btn-retro` (lift-on-hover, press-on-active); `bullet-square`; `serif-italic`; `font-jersey` / `font-bitcount` (Google-imported display fonts); `animate-caret`, `animate-float-soft[-2]`, `animate-scroll-x` (40s marquee) + `mask-fade-x`; custom webkit scrollbars (12px chunky / 6px `scrollbar-thin`).
- Base: `scroll-behavior: smooth`, body font-feature `ss01, cv11`, −0.005em tracking, blue text selection.

### Tailwind config (`tailwind.config.ts`, 64 lines) — **DEAD FILE**
Tailwind v4 (postcss `@tailwindcss/postcss`) **does not read `tailwind.config.ts` unless a `@config` directive exists — and globals.css has none.** So the file's `darkMode: "class"`, shadcn HSL color mapping, radius scale, `tailwindcss-animate` plugin, and content globs (`./pages`, `./components`, `./app` — which **don't even match the `src/` layout**) are all inert. Real config lives 100% in globals.css. The file is misleading dead weight (kept for shadcn CLI compatibility at best).

### Responsive breakpoints
Standard TW defaults only (sm/md/lg/xl) — no custom screens. Observed patterns: nav items `lg` (≥1024), login button `sm`, mobile drawer `lg`, dashboard sidebar `md`, hero grid `lg`, footer grid `2/4/7 cols`.

### Tavus relationship
The design is an **unapologetic clone of tavus.io's "Human Computing Company" neo-brutalist rebrand**: identical token naming (`tavus-*`), terminal-black 3px borders + hard offset shadows, retro OS window frames with striped title bars, square bullets, periwinkle-cloud/halftone textures, serif-italic display accents, boxed navbar chips, giant low-opacity footer wordmark. The repo even vendors tavus reference assets: ~80 screenshot PNGs in `download/` + `tavus-*.avif` hero/hand/portrait art and `tavus-logo.svg` in `public/`. Zemest differentiators: Jersey-15 handwritten hero accent + Bitcount pixel auth watermark, WhatsApp/AR·EN product framing. (`tavus.io` cloning is a **brand/legal risk** worth flagging: assets and token names are copied verbatim.)

---

## 6. Utilities

### `page-shell.tsx` (170 lines, client)
- **`PageHero`** — reusable sub-page masthead: eyebrow w/ square bullets, giant serif title, description, boxed back-link, CTA array (primary = blue, secondary/first-default = white, `variant` prop with quirk: `i > 0 && variant !== "primary"` also renders white), `bg-tavus-header-bg` + `bg-halftone-fade`/`bg-bitmap-noise` overlays.
- **`PageSection`** — section wrapper w/ `bg` prop mapped via `bgMap` (grain | white | tan | dark | periwinkle), 3px bottom border, conditional halftone overlay for dark/white, `max-w-[1280px]` container, `py-16/24`.
- **`RetroCard`** — hard-shadow card w/ optional OS-window title bar (fake window dots), serif title, description, CTA link, `bg` prop (raw CSS color string injected into inline style — ⚠️ accepts arbitrary values, fine internally), halftone overlay.
- **`PageShell`** — **a no-op passthrough** (`return <>{children}</>`); vestigial (comment admits "navbar-less page wrapper").

### `toast.tsx` (87 lines, client)
Zustand store `useToastStore` (`toasts[]`, `addToast` w/ random base-36 id, `removeToast`) + imperative `toast.{success,error,info,warning}()` helpers callable outside React. `ToastContainer` fixed bottom-right z-[100]; `ToastItem` = white 3px-bordered hard-shadow box, lucide icon per type, 4s default auto-dismiss via `useEffect` timer, manual X close, halftone overlay. **Type→color map is semantically broken:** success=charcoal #2a2a2a, error=primary blue, warning=cream `atomic-glow-5`, info=ice blue `frost-4` (none are conventional green/red). ⚠️ **Currently orphaned**: only import is the layout mount — no feature code calls `toast.*` (and the parallel shadcn `Toaster`/`useToast` system is likewise never invoked by pages).

### `skeleton.tsx` (53 lines)
`Skeleton` (pulse, plastic-2 bg, faint border) + `TableSkeleton(rows, cols)`, `StatCardSkeleton`, `CardSkeleton` — all pre-wrapped in the retro card chrome (3px borders + hard shadows), consistent with loaded states.

### `empty-state.tsx` (54 lines)
Generic `EmptyState(icon, title, description, action)` with 56px boxed icon tile + serif title; preconfigured `NoProducts` (w/ ADD PRODUCT action callback), `NoOrders`, `NoCustomers`, `NoSearchResults(query)`. Clean, well-designed pattern.

---

## 7. Deployment Config

### `next.config.ts` (19 lines)
- `output: "standalone"` — matches `package.json` build script which copies `.next/static` + `public` into `.next/standalone` and runs `bun .next/standalone/server.js` (Bun as production runtime).
- **`typescript.ignoreBuildErrors: true`** and **`reactStrictMode: false`** — both production-quality red flags (type errors ship silently; double-render safety net disabled).
- `images.formats: ["image/avif", "image/webp"]`, `remotePatterns` for `cdn.prod.website-files.com` and `cdn.jsdelivr.net` (external image hosts, likely reference assets). No `env` exposure block, no headers/CSP, no redirects/rewrites.

### `.env` (redacted summary)
**One variable only: `DATABASE_URL`** — a `file:`-scheme SQLite URL (36 chars, points at local `db/custom.db`), **no credentials, no secrets, no API keys**. Notably `NEXT_PUBLIC_API_URL` is absent, so every BFF route falls back to `http://localhost:8000` (the FastAPI backend) — in a deployed standalone build this would fail unless the env var is provided at runtime. No `.env.local`/`.env.production` present.

### `Caddyfile` (23 lines)
- Single site block on **`:81`** (non-standard port, plain HTTP — sandbox-style).
- **`@transform_port_query`**: any request with `?XTransformPort=N` is reverse-proxied to `localhost:N` — an **arbitrary localhost port forwarder (open-proxy/SSRF pattern)**; clearly a dev-sandbox convenience that must never ship to production.
- Default handler: `reverse_proxy localhost:3000` (the Next standalone server) with `Host`, `X-Forwarded-For`, `X-Forwarded-Proto`, `X-Real-IP` passed correctly.
- No TLS/ACME, no gzip/zstd, no cache directives, no security headers, no admin-panel path restrictions.

---

## 8. Component / Function Inventory

| File | Export | Purpose |
|---|---|---|
| `app/layout.tsx` | `RootLayout` (default), `metadata`, font consts `inter/instrumentSerif/jetbrains` | HTML shell, 3 next/font families, global metadata/SEO, mounts both toast systems |
| `app/page.tsx` | `Home` (default) | Landing composition — 11 sections in order |
| `app/not-found.tsx` | `NotFound` (default) | Branded 404 w/ navbar/footer |
| `middleware.ts` | `middleware`, `isPublicRoute`, `config` | Route protection (cookie presence), login redirect, matcher |
| `site/navbar.tsx` | `Navbar`, `AnnouncementBar` (private), `nav` const | Sticky marketing navbar, 6 chip nav items, login/get-started, announcement bar, mobile drawer, dead `scrolled` state |
| `site/mobile-sidebar.tsx` | `MobileSidebar`, `sidebarItems` const | Dashboard mobile drawer (FAB toggle, 11 tenant nav items, active state, backdrop) |
| `site/footer.tsx` | `Footer`, `groups` const | 7-column footer (27 links), bitmap-textured band, giant wordmark |
| `site/page-shell.tsx` | `PageHero`, `PageSection` (+`bgMap`), `RetroCard`, `PageShell` | Reusable page masthead / section / card primitives; `PageShell` = no-op |
| `site/hero.tsx` | `Hero`, `HeroWindows` (private) | Hero: bg image + bitmap grain + floating hands + copy + 2 retro OS windows + stat card, framer-motion entrance |
| `site/cta.tsx` | `CTA` | Final CTA card, whileInView animation, 2 CTAs, trust bullets |
| `site/toast.tsx` | `useToastStore`, `toast` helpers, `ToastContainer`, `ToastItem` (private), `icons`/`colors` consts | Zustand global toast system |
| `site/skeleton.tsx` | `Skeleton`, `TableSkeleton`, `StatCardSkeleton`, `CardSkeleton` | Loading placeholders |
| `site/empty-state.tsx` | `EmptyState`, `NoProducts`, `NoOrders`, `NoCustomers`, `NoSearchResults` | Empty-state pattern + entity presets |
| `tailwind.config.ts` | `config` (default) | **Dead** TW v3-style config (not loaded by TW v4) |
| `next.config.ts` | `nextConfig` (default) | standalone output, image config, TS/strict-mode suppressions |
| `Caddyfile` | — | Reverse proxy :81 → :3000 + port-transform dev rule |

Supporting (read for trace): `api/auth/login/route.ts` (`POST` → backend login, sets httpOnly cookies), `api/auth/logout/route.ts` (`POST` → deletes cookies), `components/ui/toaster.tsx` (shadcn toast mount), `components/site/auth-page.tsx` (mock login/register UI), `dashboard/[tenantId]/layout.tsx` (desktop sidebar + duplicated nav array), `lib/utils.ts` (`cn`, `formatCurrency/Number/Date/RelativeTime`, `truncate`, `debounce`, `generateOrderNumber`, `validateEgyptianPhone`, `getStatusColor` — status colors reference tavus tokens incl. #2a2a2a for "success").

---

## 9. Issues / Risks (file:line)

**Security (highest severity)**
1. **middleware.ts:44–48 — admin gate is a no-op.** `/admin/*` pages are served to any request bearing *any* `zemest_auth`-named cookie. RBAC (`is_superadmin` JWT decode) is explicitly deferred to the client.
2. **middleware.ts:34 — presence-only cookie check, no JWT validation** (signature/expiry). A user-crafted `zemest_auth=x` or `sb-access-token=x` cookie bypasses the redirect. Edge protection is cosmetic; true enforcement must live in every BFF route (P5's scope to verify).
3. **middleware.ts:34 — legacy `sb-access-token` cookie accepted** though the stack has no Supabase; widens bypass surface and hints at copied auth code.
4. **Caddyfile:2–13 — `XTransformPort` query rule = open proxy** to arbitrary localhost ports; SSRF/lateral-movement risk if this Caddyfile ships.
5. **middleware.ts:39 — `?redirect=` is an unvalidated pathname**; benign today because **nothing consumes it** (dead feature), but becomes an open-redirect the moment login reads it naively.
6. **next.config.ts:5–7 — `ignoreBuildErrors: true` + `reactStrictMode: false`**: type errors masked in prod builds; Next 16 defaults defeated.

**Functional gaps**
7. **auth-page.tsx:116 — login/register forms are `preventDefault()` stubs**; `/api/auth/login|register` BFF routes are never invoked (only Facebook works). Auth is unusable end-to-end today.
8. **middleware's `redirect` param has zero consumers** (grep-verified) — post-login return-to is unimplemented.
9. **Two orphaned toast systems mounted globally** (layout.tsx:74–75): shadcn `Toaster` (never called via `useToast` outside ui/toaster.tsx) and custom `ToastContainer` (never called via `toast.*`). Dead code + wasted bundle; also `Toaster` is shadcn/Radix → bundle cost for zero usage.
10. **navbar.tsx:19,23–28 — dead `scrolled` state** with an always-on scroll listener; intended scrolled-navbar restyle never implemented.
11. **navbar.tsx:21 / 33 — announcement bar dismiss is not persisted** → reappears on every page load.
12. **mobile-sidebar.tsx:24–36 vs dashboard/[tenantId]/layout.tsx:21–33 — duplicated 11-item nav arrays** (drift risk).
13. **footer.tsx:46–48 — dead social links (`#`)**; research column L37–40 is 4 links to the same page.
14. **hero.tsx:187–189 — "TALK TO AGENT" is `href="#"`** (dead CTA); also uses `<a>` not `<Link>` (hero.tsx:89, cta.tsx:45–57 → full reloads).
15. **toast.tsx:68–71 — timer resets on store change**: `onClose` identity changes every `ToastContainer` render, so adding a toast resets other toasts' timers (dep-array bug).
16. **toast.tsx:46–51 — semantic color collision**: error/destructive use primary CTA blue (`bubbletech-4`); success uses charcoal. Confusing UX (also `--destructive: bubbletech-4` in globals.css:112).

**Design-system / a11y / polish**
17. **globals.css:2 — render-blocking Google Fonts `@import`** for Jersey 15 + Bitcount (should be `next/font`); also a third-party font request per load.
18. **tailwind.config.ts is dead** (no `@config` in TW v4 setup) and its content globs don't match `src/` — misleading for contributors/IDE tooling.
19. **globals.css:131–158 — `.dark` theme is a copy of `:root`** — dark mode is structural fiction; `darkMode: "class"` in the dead config suggests an abandoned plan.
20. **Tavus.io cloning**: verbatim token names, `tavus-*` vendored assets (~80 reference PNGs + avif art in `public/`), near-identical layout idioms — brand/IP risk.
21. **not-found.tsx:20, page-shell.tsx:51, hero.tsx:58 — `font-[var(--font-serif-display)]` arbitrary font-family syntax** is ambiguous in Tailwind (weight vs family); canonical form is `font-[family-name:var(--x)]`. Works in current TW v4 resolution but fragile across upgrades.
22. **a11y gaps:** mobile drawer lacks focus trap/ESC close/body-scroll lock (mobile-sidebar.tsx:55–118); navbar toggle lacks `aria-expanded` (navbar.tsx:90–96); toast container has no `role="status"`/`aria-live` (toast.tsx:57); announcement close has no `aria-hidden` decorative treatment (minor).
23. **hero.tsx:9 — `-mt-[80px]` vs 84px actual navbar height** (60px row + 24px py-3) → 4px seam; also hero uses `border-b-2` (2px) vs the 3px border language everywhere else (hero.tsx:9, cta.tsx:10).
24. **.env lacks `NEXT_PUBLIC_API_URL`** → BFF defaults to `http://localhost:8000` (api/auth/login/route.ts:3) — production deployment will silently target localhost unless the env is injected at runtime.
25. **layout.tsx:26–61 — no `metadataBase`** → relative OG/Twitter URLs; icons use a PNG only (no favicon.ico/apple-touch).

---

## 10. Quality Ratings (1–10)

| File | Score | Justification |
|---|---|---|
| `src/app/layout.tsx` | **7** | Clean, correct font wiring + rich metadata; but dual toast systems, no `metadataBase`, extra fonts via CSS import elsewhere. |
| `src/app/page.tsx` | **9** | Ideal App Router composition: tiny server component, clear section order, no logic leakage. |
| `src/app/not-found.tsx` | **8** | On-brand, complete, server-rendered; duplicated hero idioms + fragile font utility syntax. |
| `src/middleware.ts` | **4** | Correct structure & matcher, but presence-only auth, no-op admin gate, dead `redirect` param, legacy Supabase cookie — security theater. |
| `src/components/site/navbar.tsx` | **7** | Visually excellent, accessible labels, cheap scroll listener; dead `scrolled` state, non-persistent announcement, minor a11y gaps. |
| `src/components/site/mobile-sidebar.tsx` | **7.5** | Nice drawer w/ backdrop + active states + auto-close; no focus trap/scroll-lock/ESC, duplicated nav data. |
| `src/components/site/footer.tsx` | **7** | Comprehensive real links + gorgeous bitmap band; dead `#` socials, 4→1 research links, needless `"use client"`. |
| `src/components/site/page-shell.tsx` | **8** | Solid reusable primitives powering all sub-pages; `PageShell` no-op + variant-quirk in CTAs. |
| `src/components/site/hero.tsx` | **8** | Striking, well-layered, tasteful motion; dead `#` CTA, border/overlap inconsistencies, heavy above-fold media. |
| `src/components/site/cta.tsx` | **8.5** | Cleanest file: good whileInView usage, complete content, correct routing; plain `<a>` navigations, misleading `id="pricing"`. |
| `src/components/site/toast.tsx` | **6.5** | Correct Zustand API design; broken semantic colors, timer-reset bug, no aria-live, currently unused. |
| `src/components/site/skeleton.tsx` | **8** | Small, consistent, on-theme. Nothing wrong. |
| `src/components/site/empty-state.tsx` | **8.5** | Exemplary micro-pattern library with entity presets. |
| `tailwind.config.ts` | **3** | Dead config in a TW v4 repo; wrong content globs; actively misleading. (Harmless at runtime.) |
| `next.config.ts` | **5** | Right output mode + image setup; `ignoreBuildErrors` and `strictMode: false` are unacceptable production flags. |
| `src/app/globals.css` | **9** | The crown jewel: 45+ coherent tokens, rich bitmap utility library, disciplined layering; −1 for render-blocking Google import and fake dark mode. |
| `Caddyfile` | **5** | Correct default proxy + forwarded headers; open port-forward rule, no TLS/compression/security headers. |

**Overall app-shell quality: 7/10** — the design system and marketing shell are genuinely strong (globals.css is portfolio-grade), but the auth/middleware layer is scaffolding-grade and several "finished" surfaces (login form, toasts, admin gate, redirect flow) are unwired stubs.
