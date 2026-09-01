# G5 — Product Analytics + SEO Tooling Research (GitHub)

**Agent:** G5 · **Date:** 2026-09-01 · **Scope:** self-hostable product analytics + Next.js SEO tooling for `zemest-platform`

## 0. Current state of the platform (grounding)

- `next: ^16.1.1`, App Router, `src/app/` with ~25 marketing routes (pricing, products, solutions, blog, careers, press-kit, …).
- Root `layout.tsx` exports `Metadata` (title/description/keywords/OG/Twitter) **but**: no `metadataBase`, no canonical (`alternates`), no OG image file, no JSON-LD anywhere.
- `public/robots.txt` is **static**: allows everything, has **no `Sitemap:` directive**, and does not disallow `/dashboard`, `/admin`, `/api`.
- No `app/sitemap.ts`, no `app/robots.ts`, **zero analytics** (no `@vercel/analytics`, no self-hosted tracker) — confirmed in `package.json`.
- Prod stack note: main worklog says backend prod = PostgreSQL 16 + Docker Compose; sandbox/platform runs SQLite (Prisma). Both are relevant below.

**Method note:** GitHub REST API was rate-limited from this IP (1 attempt, no data); repo facts (stars/license/last-commit) were pulled via shields.io GitHub endpoints + `raw.githubusercontent.com` README/LICENSE files. All numbers verified 2026-09-01.

---

## 1. Analytics candidates (ranked, max 5)

### #1 · GoatCounter — `https://github.com/zgoat/goatcounter`
- **Stars:** 5.9k · **Last commit:** Aug 2026 (active) · **License:** EUPL-1.2 (slightly modified — weak copyleft; using/hosting it unmodified as SaaS infrastructure is unrestricted; only *distributing modified versions* triggers source sharing)
- **What it solves:** privacy-friendly, cookieless page analytics; ~4.5 KB JS (or **zero-JS image pixel**, or backend-to-backend API tracking), no PII stored.
- **Self-host footprint:** ⭐ smallest of all candidates — **single static Go binary** + **SQLite by default** (Postgres optional). Runs comfortably in <100 MB RAM on the cheapest VPS; trivially fits our SQLite affinity in sandbox and needs no extra DB in prod.
- **Integration sketch:** run `goatcounter serve -db sqlite:///var/lib/goatcounter/zemest.db` under systemd (Docker optional in prod); add to root layout:
  ```tsx
  <script data-goatcounter="https://analytics.zemest.com/count" async src="https://analytics.zemest.com/count.js" />
  ```
  SPA route changes supported via `goatcounter.bind`/`window.goatcounter` config. Trust story for Egyptian SMB audience: "no cookies, no personal data, hosted by us".
- **Verdict:** ✅ **Top pick.** Cheapest to run (SQLite-native, single binary, tiny script), actively maintained, permissive-enough license. UI is spartan but sufficient for page-view/top-pages/referrers/goals.

### #2 · Umami — `https://github.com/umami-software/umami`
- **Stars:** 38k · **Last commit:** Aug 2026 (active) · **License:** MIT (fully permissive)
- **What it solves:** cookieless GA alternative with the best-looking self-hosted dashboard (events, funnels-lite, retention, UTM), multi-site, shared dashboards.
- **Self-host footprint:** 1 Node.js 18.18+ service + **PostgreSQL ≥12.14 required** (current README lists Postgres only; **no SQLite support**). ~2 GB RAM VPS is fine. Docker compose image provided.
- **Integration sketch:** if prod already runs Postgres (main worklog says PostgreSQL 16 in Docker Compose), add an `umami` service reusing that Postgres with its own database; embed:
  ```tsx
  <Script defer src="https://analytics.zemest.com/script.js" data-website-id="<id>" strategy="afterInteractive" />
  ```
  Script ≈10 KB ungzipped (~3 KB gz); auto-detects SPA history navigation. Events via `umami.track()`.
- **Verdict:** ✅ **Co-pick with GoatCounter.** Best reporting UX and MIT license; choose this if prod Postgres is guaranteed (it is, per backend compose). Pick GoatCounter if you want zero extra DB and an even tinier footprint.

### #3 · Plausible Analytics CE — `https://github.com/plausible/analytics`
- **Stars:** 29k · **Last commit:** Sep 2026 (yesterday — very active) · **License:** AGPL-3.0 (tracker script is MIT). AGPL is fine as long as we run it unmodified and don't redistribute; linking the tracker imposes nothing.
- **What it solves:** privacy-first, cookieless analytics, <1 KB tracker (smallest script of all), excellent dashboard; strongest "trust" marketing story (EU-made, GDPR-beyond).
- **Self-host footprint:** Elixir app + **PostgreSQL + ClickHouse** (community-edition docker compose). ~4 GB RAM realistic. CE omits cloud-only features (funnels, some integrations).
- **Integration sketch:** deploy `plausible/community-edition` compose on a subdomain; `<script defer data-domain="zemest.com" src="https://plausible.zemest.com/js/script.js" />`, or npm `plausible-tracker` for router-aware tracking in a client component.
- **Verdict:** ⚠️ Good but **over-provisioned for our needs** (ClickHouse for a marketing site) and the AGPL + CE feature split adds friction. Prefer #1/#2.

### #4 · PostHog — `https://github.com/posthog/posthog`
- **Stars:** 40k · **Last commit:** Sep 2026 (today) · **License:** MIT core, `ee/` directory has a separate commercial license (feature flags premium bits, fine for self-host community)
- **What it solves:** full product analytics — funnels, cohorts, feature flags, A/B tests, session replay (add-on), autocapture. This is *product* analytics for the dashboard app, not just page stats.
- **Self-host footprint:** heavy — Django + **ClickHouse + Postgres + Redis + Kafka**; hobby one-line Docker deploy wants **4 GB+ RAM**; official docs actively discourage small self-host. Autocapture `posthog-js` is ~50 KB+ (lazy-loadable) — too heavy for marketing pages.
- **Integration sketch (if ever):** `posthog-js` init in a client `<PostHogProvider>` with `capture_pageview` + Next router integration; disable autocapture on marketing routes.
- **Verdict:** ⚠️ **Not now.** Revisit when we need funnels/cohorts/flags on the tenant dashboard. Overkill for a marketing site, and the smallest viable VPS is 2× GoatCounter's.

### #5 · highlight.io — `https://github.com/highlight/highlight`
- **Stars:** 9.4k · **Last commit:** Aug 2026 · **License:** core Apache-2.0-style with portions under a separate `ee` license
- **What it solves:** session replay + error monitoring (Sentry + FullStory replacement).
- **Self-host footprint:** ⚠️ hobby self-host floor = **8 GB RAM / 4 CPU / 64 GB disk** (ClickHouse, Kafka, Redis, Postgres, OpenSearch, object storage). Good only for <10k sessions/month at that size.
- **Verdict:** ❌ **Rejected** — as suspected, far too heavy for our small VPS. If replay is ever needed, PostHog's replay add-on or a hosted free tier (Sentry) is cheaper than self-hosting this.

### Vercel Analytics alternative note
`@vercel/analytics` is closed-source, sends events to Vercel, no self-host, and no raw-data access — fails our "self-hostable, trust" axis. GoatCounter/Umami replace it fully with one `<script>`/`next/script` tag. Vercel Speed Insights equally unnecessary.

---

## 2. SEO tooling candidates

### #1 · Next.js native Metadata API (app router) — no dependency
- Next ≥13.3 (we're on **16.1.1**) supports `app/sitemap.ts`, `app/robots.ts`, `generateMetadata`, `alternates.canonical` natively, zero runtime cost, zero script weight.
- **Verdict:** ✅ **Use this.** Built-in, framework-maintained, beats any lib for a 25–50 URL marketing site.

### #2 · `google/schema-dts` — `https://github.com/google/schema-dts`
- **Stars:** 1.2k · **Last commit:** Mar 2026 (stable/slow — it's a generated-types project) · **License:** Apache-2.0
- **What it solves:** official Google-maintained TypeScript types for schema.org JSON-LD → typed `Organization`, `WebSite`, `SoftwareApplication`, `BreadcrumbList`, `BlogPosting` objects with compile-time validation.
- **Verdict:** ✅ Recommended as the *only* SEO dependency. Dev-time only — **0 KB on marketing pages**.

### #3 · `iamvishnusankar/next-sitemap` — `https://github.com/iamvishnusankar/next-sitemap`
- **Stars:** 3.7k · **Last commit:** Mar 2026 (~6 mo stale) · **License:** MIT
- Post-build sitemap/robots generator; was the standard for pages router. On Next 16 app router it duplicates native `sitemap.ts`/`robots.ts` and adds a build step.
- **Verdict:** ❌ Skip — maintenance is slowing and native support supersedes it. (Same conclusion for the `@niftory` forks.) Only edge case: >50k-URL split sitemaps (not us).

### #4 · `garmeeh/next-seo` — `https://github.com/garmeeh/next-seo`
- **Stars:** 8.5k · **Last commit:** Jul 2026 · **License:** MIT
- `<NextSeo>` component + JSON-LD helpers, pages-router era; app router has native `Metadata`. Adding it now would be regression.
- **Verdict:** ❌ Skip on app router.

---

## 3. Final ranking (max 5, analytics + SEO combined)

| # | Tool | Role | Why |
|---|------|------|-----|
| 1 | **GoatCounter** (zgoat/goatcounter) | analytics | SQLite-native single binary, ~0 script weight, tiny VPS |
| 2 | **Umami** (umami-software/umami) | analytics (alternative #1) | MIT, best dashboard, reuses prod Postgres |
| 3 | **Next.js native sitemap.ts/robots.ts/Metadata** | SEO core | zero-dep, framework-supported on Next 16 |
| 4 | **google/schema-dts** | SEO structured data | typed JSON-LD, Apache-2.0, 0 KB runtime |
| 5 | **Plausible CE** (plausible/analytics) | analytics (fallback) | if we outgrow GoatCounter and want polished reports; AGPL/ClickHouse overhead |

PostHog and highlight.io: deferred/rejected (footprint).

---

## 4. Minimal SEO checklist for zemest marketing pages

1. **`app/robots.ts`** (replace `public/robots.txt`): add `Sitemap: https://zemest.com/sitemap.xml`, `Disallow: /dashboard, /admin, /api` (keep `/login`, `/pricing` crawlable — brand queries).
2. **`app/sitemap.ts`**: enumerate static marketing routes (products, solutions, pricing, careers, press-kit, …) + dynamic `/blog/[slug]` posts with `lastModified`; single file is fine <50k URLs.
3. **Root layout metadata**: add `metadataBase: new URL("https://zemest.com")`, `alternates.canonical` per page, and a real `openGraph.images` file (currently absent while Twitter card claims `summary_large_image` — mismatch likely suppresses rich cards).
4. **Per-page `generateMetadata`** for every marketing route (unique title/description; only root metadata exists today).
5. **JSON-LD** via server-component `<script type="application/ld+json">`: `Organization` + `WebSite` in root layout; `SoftwareApplication`/`Product` (offers → pricing page); `BreadcrumbList` on 2nd-level pages; `BlogPosting` on blog posts. Type them with `schema-dts`.
6. **Bilingual (EN/AR) SEO** — Egyptian SMB audience: if Arabic versions exist or are planned, `alternates.languages` + `hreflang` from day one; Arabic keyword research for title/description.
7. **Analytics tag** (GoatCounter or Umami) in root layout via `next/script` `strategy="afterInteractive"`; document the no-cookie policy on the `/privacy` page (trust signal).
8. **Validation**: Google Rich Results Test + Search Console → submit `sitemap.xml`; monitor robots via `curl /robots.txt`.
