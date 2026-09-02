# R9 — Next.js Performance Tooling Research (GitHub research-only, no code changes)

**Agent:** R9 · **Date:** 2026-08/09 (data pulled live from GitHub API + npm registry) · **Scope:** dev-mode latency, client data-fetch waterfalls/caching, image optimization, bundle analysis, profiling.

## 0. Ground truth found first (changes the whole ranking)

The briefing said "Next.js 15" — **the project is actually on Next 16**:

| Fact | Evidence (local, free) |
|---|---|
| `next` **16.1.3** installed & running | `node_modules/next/package.json`; `dev.log` line 1: `▲ Next.js 16.1.3 (Turbopack)` |
| **Turbopack is ALREADY the default dev bundler** | dev.log banner; Next 16 made Turbopack default for `dev` **and** `build` (webpack is now opt-in) |
| `@tanstack/react-query` **5.90.19 installed but never imported** (dead dep, confirmed by 18-c audit) | `node_modules/@tanstack/react-query/package.json` exists; zero imports in `src/` |
| `sharp` **0.34.5 already installed** as a runtime dep | `node_modules/sharp/package.json` |
| `swr`, `@next/bundle-analyzer`, `babel-plugin-react-compiler` NOT installed | node_modules check |
| Dashboard is 100% client components doing load-time fetches; hand-rolled SWR-lite (inflight dedupe + sessionStorage + hover prefetch) in `src/lib/zemest-api.ts` (593 LOC); admin pages use raw fetch + loading flag + full refetch | 18-c / 19 worklog entries |
| Images unoptimized in dev is **by design** (Next never runs the sharp optimizer in `next dev`); `images.formats: [avif, webp]` + 2 remotePatterns already configured | `next.config.ts` |
| Prod runs `output: "standalone"` via bun (`npm start`) | package.json scripts |
| React Compiler config key exists as a **top-level** `reactCompiler` option in this exact next version (works with Turbopack's built-in Babel — `turbopackUseBuiltinBabel` interplay documented in the types) | `node_modules/next/dist/server/config-shared.d.ts` |

So "Turbopack status in Next 15" is moot for this repo — the answer is "you already have it; keep it". And "no TanStack Query yet" is half-true: **the dependency is installed, just dead** — wiring it is a 0-new-dependency change.

## 1. Method & budget

- GitHub REST `search/repositories` (repo: + in:name qualifiers): ~17 successful lookups (core /repos exhausted at 60/hr for the sandbox's rotating egress IPs; several `repo:` lookups throttled → retried via name search).
- npm registry (registry.npmjs.org, not rate-limited): latest versions, publish dates, licenses, repository URLs for 10 packages + `next` dist-tags.
- Local reads: package.json, next.config.ts, dev.log, node_modules, config-shared.d.ts.
- All star counts / push dates as returned by the API on the day of research.

## 2. Tool-by-tool scorecard

| Tool | Repo (GitHub) | Stars | License | Last push | Status | Dev benefit | Prod benefit |
|---|---|---|---|---|---|---|---|
| **Turbopack** (in vercel/next.js) | github.com/vercel/next.js | 142,038 | MIT | 2026-09-01 | default bundler in 16.x; latest `next` = 16.3.4 (2026-08-31) | ✅✅ compile latency | ✅ builds |
| **TanStack Query v5** | github.com/TanStack/query | 50,241 | MIT | 2026-08-31 | very active; `@tanstack/react-query` 5.102.8 (2026-08-27) | ✅ instant cache paint, dedupe | ✅✅ kills waterfalls, fewer refetches |
| **sharp** | github.com/lovell/sharp | 32,623 | Apache-2.0 | 2026-08-30 | very active; 0.35.4 latest (project has 0.34.5) | ➖ (dev skips optimizer by design) | ✅✅ image resize/AVIF/WebP |
| **SWR 2** | github.com/vercel/swr | 32,476 | MIT | 2026-08-23 | active; 2.5.1 (2026-08-12) | ✅ | ✅ |
| **react-scan** | github.com/aidenybai/react-scan | 21,817 | MIT | 2026-08-16 | very active; 0.5.7 (2026-05-27) | ✅✅ render profiling | ➖ dev-only |
| **why-did-you-render** | github.com/welldone-software/why-did-you-render | 12,514 | MIT | 2026-04-15 | npm 1.0.1 = **2020-05-17**; effectively unmaintained | ✅ | ➖ |
| **workbox** | github.com/GoogleChrome/workbox | 12,995 | MIT | 2026-08-04 | active | ➖ | ✅ (PWA SW runtime) |
| **@next/bundle-analyzer** | package in vercel/next.js | — | MIT | 2026-08-31 | versioned lockstep w/ next (16.3.4) | ➖ | ⚠ webpack builds only |
| **next-pwa** | github.com/shadowwalker/next-pwa | 4,088 | MIT | 2024-07-27 | npm 5.6.0 = **2022** → dead | ➖ | ⚠ stale |
| **serwist** | github.com/serwist/serwist | 1,472 | MIT | 2026-07-22 | active; 9.5.12 | ➖ | ✅ (modern PWA) |
| **next-ws** | github.com/k0d13/next-ws | 325 | MIT | 2026-08-30 | active; 2.2.13 | ⚠ patch-based | ✅ websockets |
| **React Compiler 1.0** | package in facebook/react (≈236k★) | — | MIT | babel-plugin-react-compiler **1.0.0 stable 2025-10-07** | stable since React 19.1 era | ✅ | ✅✅ auto-memoization |
| next-optimized-images | github.com/cyrilwanner/next-optimized-images | 2,233 | MIT | 2023-01-04 | dead; superseded by `next/image` | — | skip |
| next-export-optimize-images / next-image-export-optimizer | dc7290 (475★, 2026-05) / Niels-IO (539★, 2025-12) | — | MIT | active | static-**export** only — this repo uses `standalone`, not export | — | N/A |

## 3. DEV-MODE LATENCY section

### 3.1 Turbopack — *already on; nothing to add* ✅ KEEP (rank #4)
- **What it speeds up:** HMR + cold route compile in `next dev`, and (Next 16) production builds. Up to ~10x faster local compiles vs webpack; large dev memory win vs webpack caching.
- **Status in the wild:** dev stable since Next 15.0 (Turb 15 line ended at 15.5.25); **Next 16 = default for dev + build**; webpack is opt-in. This repo's `next dev -p 3000` already logs `▲ Next.js 16.1.3 (Turbopack)`.
- **Integration sketch:** none needed — do NOT add `--webpack`, do not add webpack-only plugins (next-pwa, next-ws patching, `@next/bundle-analyzer` are webpack-era). Optional: bump `next`/`eslint-config-next` 16.1.3 → 16.3.4 for two months of Turbopack fixes (patch-level within 16.x).
- **License:** MIT. **Verdict: keep; cheap upgrade path 16.1.3→16.3.4.**

### 3.2 react-scan — adopt now (rank #2)
- github.com/aidenybai/react-scan · 21,817★ · MIT · pushed 2026-08-16 · npm 0.5.7 (2026-05-27).
- **What it speeds up (indirectly):** finds wasted re-renders with per-component render counts/flame overlays — exactly what the 22 client pages (14 dashboard + 8 admin) need diagnosed. 18-c found 0 server components in the dashboard subtree; every keystroke/route change re-renders big trees.
- **App-router compat:** framework-agnostic React devtool; works in client components of app router; zero prod impact if loaded dev-only.
- **Integration sketch (dev-only, ~2 lines):**
  ```ts
  // app/layout.tsx — guarded, stripped in prod builds
  {process.env.NODE_ENV === 'development' && <ReactScan component={ReactScanComponent} />}
  ```
  or just run the bookmarklet/CDN build against localhost:3000 — zero code change.
- **Bundle impact:** 0 in prod (dev-only import or external script). **License:** MIT.
- **Verdict: ADOPT — the profiling layer this codebase has never had; zero risk.**

### 3.3 React Compiler 1.0 — trial behind a flag (rank #3)
- Lives in facebook/react (≈236k★, MIT, very active). `babel-plugin-react-compiler` + `react-compiler-runtime` **1.0.0, published 2025-10-07** → graduated from RC to stable.
- **What it speeds up:** auto-memoization (memo/useMemo/useCallback for free) → fewer re-renders on the heavily-client dashboard (recharts, tables, chat inbox). React core now assumes compiler usage for re-render scaling.
- **App-router + Turbopack compat:** **verified against the installed next 16.1.3 types**: top-level `reactCompiler?: boolean | ReactCompilerOptions` in `config-shared.d.ts`, with `turbopackUseBuiltinBabel` (default on) — i.e. the compiler runs through Turbopack's built-in Babel, no webpack needed. (In 15.x it was `experimental.reactCompiler` + SWC-external Babel; the 16 key is top-level.)
- **Integration sketch:**
  ```ts
  // next.config.ts
  const nextConfig: NextConfig = {
    reactCompiler: true,           // verified key in next 16.1.3
    // add devDeps: babel-plugin-react-compiler@^1.0.0, react-compiler-runtime@^1.0.0
  };
  ```
  Also remove the few hand `useMemo/useCallback` wrappers that fight the compiler later (it subsumes them).
- **Bundle impact:** build-time plugin + tiny runtime (~1–2KB); no client bloat. **License:** MIT.
- **Verdict: TRIAL — one-line flag, revertible; validate with react-scan before/after render counts.**

### 3.4 why-did-you-render — skip (superseded)
- 12,514★ / MIT but npm 1.0.1 dates to 2020; repo quiet. Monkey-patches React internals (friend-of) — friction with React 19 internals; react-scan (same community, modern) covers the same need with less setup. **Verdict: skip.**

### 3.5 next-ws (k0d13) — hold
- github.com/k0d13/next-ws (repo moved from alexcrist) · 325★ · MIT · pushed 2026-08-30 · npm 2.2.13.
- **What it would speed up:** real-time inbox/live chat updates without polling — a *latency* win for a messaging product, not a compile/render win.
- **Caveats:** works by patching Next internals (`next-ws patch`); with Turbopack now the default bundler, patch-based wrappers are the first thing to break on upgrades; small community (325★). App-router route handlers are supported, but Turbopack compat must be verified per version.
- **Verdict: HOLD — revisit when the chat inbox needs push updates; until then the 30s AbortSignal + polling flow already works.** (Alternative when needed: standalone ws server beside Next, or SSE route handler — no patching.)

## 4. PROD-BUILD SIZE / RUNTIME section

### 4.1 TanStack Query v5 — #1 overall pick (rank #1)
- github.com/TanStack/query · 50,241★ · MIT · pushed 2026-08-31 · `@tanstack/react-query` 5.102.8 (project has **5.90.19 already in node_modules, unused**).
- **What it speeds up:**
  - Kills the dashboard **waterfalls**: parallel `useQuery` per endpoint (stats + customers + orders + conversations render independently) instead of sequential `useEffect` chains.
  - **Cross-page cache**: navigating dashboard↔admin↔sub-pages repaints instantly from cache; today every admin page refetches from zero with a loading flag (Task 19 pattern) and the hand-rolled layer nukes the ENTIRE cache on any mutation (`invalidateCache()` clears all keys).
  - **Dedup** of concurrent identical requests (today: inflight map, hand-rolled).
  - **Precise invalidation** per query key after mutations; optimistic updates for order status/channel toggles; background refetch on focus with `staleTime` windows; built-in retry/AbortSignal semantics (their 30s AbortSignal fix maps to `signal` per query).
- **App-router compat:** full — `QueryClientProvider` in a `"use client"` providers component; optional server-side prefetch/dehydration for the marketing shell; devtools (`@tanstack/react-query-devtools`) dev-only.
- **Bundle impact:** ~13KB gzipped (core+react) — **zero *new* dependency weight here since 5.90.19 is already shipped in package.json**; it replaces ~200 lines of hand-rolled cache code in `zemest-api.ts` (the BFF `api.get/post` transport stays).
- **Integration sketch:**
  ```tsx
  // src/app/providers.tsx ("use client")
  const [client] = useState(() => new QueryClient({
    defaultOptions: { queries: { staleTime: 30_000, gcTime: 5*60_000,
      refetchOnWindowFocus: true, retry: 1 } }
  }));
  <QueryClientProvider client={client}>{children}</QueryClientProvider>
  // page-level:
  const stats = useQuery({ queryKey:['tenant', id, 'stats'],
    queryFn: () => api.get<Stats>(`/tenants/${id}/stats`) });
  // hover prefetch they hand-rolled today:
  qc.prefetchQuery({ queryKey: ['customers'], queryFn: fetchCustomers });
  // after mutations: qc.invalidateQueries({ queryKey:['tenant', id] }) // scoped, not global
  ```
  Wrap in root layout; migrate the 12 merchant pages + 8 admin pages page-by-page (each is independent — low-risk incremental rollout); keep sessionStorage "peek" as `placeholderData` if the instant-paint behavior must be preserved.
- **License:** MIT. **Verdict: ADOPT — highest impact per unit of effort in this whole report; zero new deps.**

### 4.2 SWR 2.5.1 — skip (redundant here)
- github.com/vercel/swr · 32,476★ · MIT · active (2.5.1, 2026-08-12). Vercel-native, ~4.5KB gz, app-router friendly, solid stale-while-revalidate + suspense streaming.
- **Why not:** TanStack Query is *already installed*, is strictly more capable for this app (typed mutations, scoped invalidation, offline/devtools), and 18-a already flagged SWR/react-query as the "two dead deps" conversation. Adding SWR would introduce a second data layer for ~8KB savings. **Verdict: skip — SWR wins the greenfield tiebreak, loses the "already installed" tiebreak.**

### 4.3 sharp — keep, verify, (optional) upgrade (rank #5)
- github.com/lovell/sharp · 32,623★ · Apache-2.0 (npm also Apache-2.0) · pushed 2026-08-30 · 0.35.4 latest; **0.34.5 already installed**.
- **What it speeds up:** `next/image` prod optimization (resize + AVIF/WebP, both already enabled in next.config.ts) — the 397KB-favicon class of problems stays fixed at the framework level, and channel/product images from CDNs get resized/converted on demand.
- **Key fact for the "images unoptimized in dev" concern:** Next deliberately skips the optimizer in `next dev` (serves originals for fast HMR). **Nothing to fix in dev** — the fix already landed (Task 18 favicon 397KB→10KB); remaining work is prod verification:
- **Integration sketch (verification only):**
  ```bash
  next build && ls .next/standalone/node_modules | grep -c sharp   # must be ≥1
  # if missing (standalone tracing gap), pin it:
  # next.config.ts → outputFileTracingIncludes: { '/**': ['./node_modules/sharp/**'] }
  ```
  Their build script already copies `static/` + `public/` into standalone; it does NOT assert sharp made it into the trace — one grep after `next build` closes that hole. Optional: `sharp@^0.35` bump (0.34→0.35 is a routine libvips refresh).
- **Bundle impact:** server-only; ~25–30MB in the standalone trace (native binaries) — irrelevant to client JS. **License:** Apache-2.0. **Verdict: KEEP + verify standalone trace; upgrade optional.**

### 4.4 @next/bundle-analyzer — conditional/defer
- Published from vercel/next.js, MIT, versioned with next (16.3.4, 2026-08-31). `withBundleAnalyzer()` HOC wrapping webpack-bundle-analyzer.
- **Caveat that matters here:** it is a **webpack plugin**. Since this repo builds with Turbopack by default in Next 16, `ANALYZE=true next build` won't instrument anything unless they opt back into webpack (`next build --webpack`), which defeats the point. Turbopack builds have no equivalent analyzer plugin API yet.
- **When it becomes useful:** if a webpack build is ever needed (legacy loader), or for a one-off audit: `bun add -d @next/bundle-analyzer@16.3.4 && ANALYZE=true next build --webpack`.
- **What to use instead today:** the build output size table (`Route (app)` first-load JS per route) from plain `next build` + react-scan for runtime. **Verdict: DEFER — not usable on the default Turbopack pipeline.**

### 4.5 PWA tooling (next-pwa / workbox / serwist) — defer
- **next-pwa** (shadowwalker): 4,088★, MIT, last push 2024-07-27, npm 5.6.0 from 2022 — **dead**; also webpack-era (breaks Turbopack default builds). Avoid.
- **serwist** (serwist/serwist): 1,472★, MIT, active (9.5.12, 2026-07-22) — the modern successor; `withSerwist()` init, app-router + Turbopack friendly, wraps **workbox** (GoogleChrome, 12,995★, MIT, active 2026-08-04) for the SW runtime.
- **Why defer:** the dashboard is auth'd BFF data; service-worker caching of `/api/zemest/*` creates staleness/invalidation complexity with no offline requirement today. The cache-pain is already better solved client-side by TanStack Query. **Verdict: DEFER — if PWA/offline ever becomes a product ask, use serwist (never next-pwa).**

### 4.6 Image-optimizer alternatives — N/A
- `next-optimized-images` (2,233★, dead 2023) — superseded by `next/image` itself. `next-export-optimize-images` (475★, active) / `next-image-export-optimizer` (539★) — both exist for **static export** builds; this repo uses `output: "standalone"` + a running server, where built-in `next/image` + sharp is strictly better. `terraform-aws-next-js-image-optimization` (110★) — AWS/serverless variant, N/A. **Verdict: N/A — stock next/image + sharp is the right architecture for standalone.**

## 5. Final ranking (max 5, this repo)

| # | Tool | Effort | Impact | Risk | Why |
|---|---|---|---|---|---|
| **1** | **TanStack Query v5** (wire existing dep) | M (incremental, page-by-page) | HIGH — breaks waterfalls, cross-page cache, scoped invalidation, dedupe across 20 pages | low (dep already vetted/installed) | biggest user-perceived latency win; replaces 593-LOC hand-rolled cache |
| **2** | **react-scan** (dev-only) | XS | HIGH (diagnostic) | none | render-count overlay on the 100%-client dashboard; validates every other change |
| **3** | **React Compiler 1.0** (`reactCompiler: true`) | XS to enable, M to validate | MED-HIGH (re-render reduction) | low-med (flag revert) | stable 1.0; verified top-level key + Turbopack Babel path in installed next 16.1.3 |
| **4** | **Turbopack** (keep + 16.1.3→16.3.4 bump) | XS | already banked; incremental fixes | low | already default; don't reintroduce webpack plugins |
| **5** | **sharp** (verify standalone trace) | XS (one grep post-build) | MED (prod image bytes) | none | already installed; close the standalone-trace gap; avif/webp already on |

**Explicit skips:** SWR (redundant), why-did-you-render (unmaintained, superseded by react-scan), @next/bundle-analyzer (webpack-only vs default Turbopack builds), next-pwa (dead), serwist/workbox (defer, no offline requirement), next-ws (hold until realtime inbox is a real ask), export-image optimizers (N/A for standalone).

## 6. Caveats
- Data timestamps: stars/push dates captured live 2026-08/09 via GitHub API; some `repo:` lookups were throttled by per-IP search quotas → `facebook/react` stars quoted from prior knowledge (≈236k), and `vercel/turbopack` repo direct lookup failed (Turbopack is developed in vercel/next.js `crates/turbo-*` — repo identity is vercel/next.js for all practical purposes).
- Bundle sizes (≈13KB gz react-query, ≈4.5KB gz SWR) are community-measured approximations, not measured in this sandbox.
- This was research-only: no files in `src/`, `next.config.ts`, or `package.json` were modified.
