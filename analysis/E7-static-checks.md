# E7 — Static Health Check (TypeScript / ESLint / Dependencies)

**Agent:** E7 (error-finder, static only — no code modified)
**Scope:** `/home/z/my-project` (Next.js 16.1.3 App Router, 149 TS/TSX files in `src/`)
**Cross-refs:** E9/R9 (dead TanStack Query), R8 (Prisma unused), E2 (api-client dead), E10 (runtime Next 16.1.3)

---

## 1. Executive Summary

| Check | Result |
|---|---|
| `npx tsc --noEmit` | **8 unique errors** — 2 in shipped `src/**`, 0 in config, 6 in legacy/examples/skills/stale repo |
| `bun run lint` (eslint .) | **0 errors, 0 warnings, exit 0** — but 25+ rules disabled and 11 directories ignored (weak signal) |
| `npm ls --depth=0` | No peer conflicts, no invalid; **1 extraneous** (`immer@10.2.0`); **~20 dead dependencies** |
| `any` hotspots in `src/lib` | 6 total: 5 in dead `api-client.ts`, 1 benign generic in `utils.ts`; **zero** `as any` / `@ts-ignore` in all of `src` |

**Headline risk:** `next.config.ts` sets `typescript.ignoreBuildErrors: true`, so the **only 2 shipped type errors are silently masked in production builds** — and both carry a real functional bug (broken anchor navigation CTAs on `/careers` and `/partnerships`). There is no `typecheck` script to catch this in CI.

---

## 2. `npx tsc --noEmit` — Full Error List (grouped)

Raw output (12 lines / 8 unique errors, exit non-zero):

### (a) SHIPPED APP CODE — `src/**` (2 errors)

| # | Location | Code | Error |
|---|---|---|---|
| 1 | `src/app/careers/page.tsx:125:33` | TS2322 | `Type '{ children: Element[]; bg: "white"; id: string; }' is not assignable to type 'IntrinsicAttributes & PageSectionProps'. Property 'id' does not exist...` |
| 2 | `src/app/partnerships/page.tsx:58:33` | TS2322 | `Type '{ children: Element; bg: "grain"; id: string; }' is not assignable to type 'IntrinsicAttributes & PageSectionProps'. Property 'id' does not exist...` |

### (b) CONFIG — 0 errors
`next.config.ts`, `tsconfig.json`, `eslint.config.mjs`, `postcss.config.mjs`, `package.json` all typecheck clean.

### (c) LEGACY / EXAMPLES / SKILLS / STALE REPOS — 6 errors (all pre-existing, verified)

| # | Location | Code | Error | Class |
|---|---|---|---|---|
| 3 | `examples/websocket/frontend.tsx:4:20` | TS2307 | Cannot find module 'socket.io-client' | Example code; socket.io not installed |
| 4 | `examples/websocket/server.ts:2:24` | TS2307 | Cannot find module 'socket.io' | Same |
| 5 | `skills/image-edit/scripts/image-edit.ts:10:4` | TS2561 | `'images' does not exist in type 'CreateImageEditBody'. Did you mean 'image'?` | Skill script vs SDK type mismatch |
| 6 | `skills/stock-analysis-skill/src/analyzer.ts:253:11` | TS2322 | Multimodal content array (`{type:"image"...},{type:"text"...}`) not assignable to `string` | SDK chat-completion types model `content` as `string` only; code passes VLM array |
| 7 | `repos/zemest-platform/src/app/careers/page.tsx:125:33` | TS2322 | Identical to #1 | Stale clone — origin of the shipped bug |
| 8 | `repos/zemest-platform/src/app/partnerships/page.tsx:58:33` | TS2322 | Identical to #2 | Stale clone |

**Note on cause of group (c) noise:** root `tsconfig.json` `include: ["**/*.ts", "**/*.tsx"]` with `exclude: ["node_modules"]` only — so the root program compiles **160 non-project files** (repos 139, skills 19, examples 2) alongside the 149 shipped files (~52% of the program is non-shipped code). Errors #7/#8 are the stale-repo twins of #1/#2 (the shipped pages were copied from that repo, bug included).

---

## 3. Per-Error Analysis — Shipped Code

### Error 1 — `src/app/careers/page.tsx:125` (and Error 2, same root cause)

**Root cause:** `PageSection` in `src/components/site/page-shell.tsx:84-88` declares:
```ts
interface PageSectionProps {
  children: React.ReactNode;
  bg?: "grain" | "white" | "tan" | "dark" | "periwinkle";
  className?: string;
}
```
No `id` prop, and the component (line 98-111) never forwards one to the rendered `<section>`. Two shipped pages pass `id` anyway (careers:125 `id="roles"`, partnerships:58 `id="programs"`) — the prop is type-rejected and, at runtime, **dropped**: no element with that `id` is ever rendered.

**Severity: MEDIUM — compile-breaking (masked) + functional bug.**
- *Compile impact:* would fail `next build`, but `next.config.ts:11` sets `typescript.ignoreBuildErrors: true` → silently shipped.
- *Functional impact (confirmed):* hero CTAs are broken anchor links —
  - `src/app/careers/page.tsx:46`: `ctas=[{ label: "Explore open roles", href: "#roles", ... }]` → click scrolls nowhere (no `#roles` target exists).
  - `src/app/partnerships/page.tsx:54`: `{ label: "Explore partnerships", href: "#programs" }` → same.
- *Type soundness:* prop silently dropped (unsound), no runtime crash.

**Suggested fix (NOT implemented):** add `id?: string` to `PageSectionProps` and apply it to the `<section>` element in `page-shell.tsx:100` (one-line component change fixes both pages and both stale-repo twins), or remove the `id` prop from the two pages and retarget the CTAs. Secondarily, remove `typescript.ignoreBuildErrors: true` and/or add `"typecheck": "tsc --noEmit"` script once errors are zero.

**Impact scope:** 4 tsc errors total share this single root cause (2 shipped + 2 stale-repo).

---

## 4. Lint

**Command:** `bun run lint` → `eslint .` → **exit 0, no output** (also re-verified with direct `npx eslint .`, exit 0).

**Caveats (lint is weak-signal):**
- `eslint.config.mjs` disables ~25 rules, including: `@typescript-eslint/no-explicit-any`, `@typescript-eslint/no-unused-vars`, `react-hooks/exhaustive-deps`, `react-hooks/purity`, `no-console`, `no-debugger`, `no-undef`, `no-unreachable`, `prefer-const`.
- Ignores: `node_modules, .next, out, build, next-env.d.ts, examples/**, skills/**, repos/**, scripts/**, analysis/**, tool-results/**, download/**, mini-services/**, tests/**, prisma/**`.
- `react-hooks/exhaustive-deps: off` is notable given useEffect-heavy files (`agent-chat-modal.tsx` ×5, dashboard scheduler/conversations ×3 each) — stale-closure risk is unlinted.
- Next 16 no longer runs ESLint during `next build`, so lint only runs when invoked manually — there is no CI gate evidence in repo.

**Verdict:** zero findings, but the rule set cannot catch unused vars, implicit/explicit any, hook-dep bugs, or unreachable code.

---

## 5. Dependency Health

### `npm ls --depth=0` (resolved versions)
- **No UNMET peer dependencies, no invalid, no dedupe errors.**
- **1 extraneous:** `immer@10.2.0` (present in node_modules, absent from package.json — leftover install).
- Compat matrix verified good: `next@16.1.3` + `react@19.2.3` + `react-dom@19.2.3` + `@types/react@19.2.8` + `@types/react-dom@19.2.3` (Next 16 requires React 19.2 — satisfied); `eslint-config-next@16.1.3` matches `next@16.1.3` exactly; `typescript@5.9.3` fine.
- Lockfile: `bun.lock` only (no package-lock.json — consistent with bun-based workflow; `npm ls` reads the tree fine).
- Version pinning: all ranges are caret (`^`); nothing pinned to git URLs/SHA. Installed set drifts above minimums (e.g. next 16.1.1→16.1.3, zod 4.0.2→4.3.5) — acceptable, pinned by bun.lock.

### Dead dependencies (0 imports anywhere in shipped `src/**`)
Cross-verified by import sweep (`rg -l <pkg> src`). Knowns from E9/R8/E2 **confirmed**:

| Dependency | Known | Evidence |
|---|---|---|
| `@tanstack/react-query@5.90.19` | E9/R9 | 0 imports in src |
| `prisma@6.19.2` + `@prisma/client@6.19.2` | R8 | `prisma/schema.prisma` is the **default scaffold template** (User/Post models, sqlite); `src/lib/db.ts` (the only PrismaClient import) is itself **never imported** by any route/page |
| — (`src/lib/api-client.ts` dead code) | E2 | 0 imports; duplicates `src/lib/zemest-api.ts` + BFF routes; contains 5 of the 6 `: any` in src/lib |
| `@tanstack/react-table` | | 0 imports |
| `@mdxeditor/editor@3.52.3` | | 0 imports (1.2 MB pkg + deps) |
| `react-syntax-highlighter@15.6.6` | | 0 imports (8.9 MB) |
| `@dnd-kit/core` + `sortable` + `utilities` | | 0 imports |
| `uuid@11.1.0` | | 0 imports (crypto.randomUUID available natively) |
| `date-fns@4.1.0` | | 0 imports |
| `@reactuses/core` | | 0 imports |
| `next-intl@4.7.0` | | 0 imports |
| `next-auth@4.24.13` | | 0 imports, no `[...nextauth]` route, no authConfig — pure dead weight (also a React-19-adjacent lib kept only via widened peer range) |
| `zod@4.3.5` | | 0 imports (not even in dead form.tsx) |
| `react-hook-form@7.71.1` + `@hookform/resolvers@5.2.2` | | imported ONLY by `src/components/ui/form.tsx`, which is itself imported by nobody |
| `recharts@2.15.4` | | only by dead `src/components/ui/chart.tsx` |
| `embla-carousel-react` | | only by dead `ui/carousel.tsx` |
| `react-day-picker` | | only by dead `ui/calendar.tsx` |
| `vaul` (drawer) / `cmdk` (command) / `input-otp` / `react-resizable-panels` | | respective shadcn wrappers all have 0 importers |
| `react-markdown` | | 0 imports |

- **35 of 47 shadcn `ui/*` components have 0 importers** (only accordion, button, dialog, input, label, separator, sheet, skeleton, toast, toaster, toggle, tooltip are live) — this is why so many `@radix-ui/*` packages sit unused.
- `z-ai-web-dev-sdk`: 0 imports in `src/` (used only by `skills/*` scripts outside the app bundle) — borderline: keep if skills are part of the workspace, else move to devDependencies.
- **Live & healthy:** `framer-motion` (17 files), `zustand` (3), `lucide-react` (76), `sonner` (via `<Toaster/>` in root layout), `next-themes`, `clsx`/`tailwind-merge`/`cva`, `sharp` (Next image optimization — remotePatterns configured), radix subset above.

### Scripts
- Present: `dev`, `build`, `start`, `lint`, `db:push/generate/migrate/reset`.
- **Missing:** no `typecheck` script — critical gap because `ignoreBuildErrors: true` removes the only build-time gate on the 2 shipped TS errors. (No test/format scripts either.)

---

## 6. tsconfig Strictness & `any` Hotspots

**`tsconfig.json` observations:**
- `strict: true` **but `noImplicitAny: false`** (line 13) — quietly weakens strict mode; implicit `any` params are allowed through.
- `skipLibCheck: true`, `isolatedModules: true`, `moduleResolution: "bundler"`, `target: ES2017` — standard Next defaults.
- **Include breadth problem:** `include: ["**/*.ts","**/*.tsx"]` + `exclude: ["node_modules"]` only → compiles 160 non-project files (repos/skills/examples). Recommend excluding `repos/**, skills/**, examples/**, mini-services/**, scripts/**, tests/**, download/**` to halve the program and eliminate 6 of 8 tsc errors.
- `incremental: true` present.

**`any` hotspots in `src/lib` (grep `: any`):**

| File | Count | Assessment |
|---|---|---|
| `src/lib/api-client.ts` | 5 | All in **dead code** (`request<T = any>` default + 4× `data: any` params) — E2 confirmed; deleting the file removes all 5 |
| `src/lib/utils.ts` | 1 | Line 77: `debounce<T extends (...args: any[]) => void>` — idiomatic generic constraint, **benign** |

- `as any` / `@ts-ignore` / `@ts-expect-error` / `@ts-nocheck` in all of `src/`: **0 occurrences** — clean.
- Caveat: with `noImplicitAny: false`, untyped function params pass silently, so true `any` surface is larger than the explicit count; eslint's `no-explicit-any` is also off.

---

## 7. Findings Register (numbered, severity, suggested fixes — NOT implemented)

1. **MED — src/app/careers/page.tsx:125 & src/app/partnerships/page.tsx:58 (TS2322):** `id` prop not in `PageSectionProps` (src/components/site/page-shell.tsx:84). Masked by `ignoreBuildErrors`. **Functional bug:** hero CTAs `#roles` (careers:46) and `#programs` (partnerships:54) anchor to ids never rendered → dead buttons. Fix: add `id?: string` to PageSectionProps + forward to `<section>`.
2. **HIGH (process) — next.config.ts:11 `typescript.ignoreBuildErrors: true`:** the only safety net for type errors is disabled and no `typecheck` script/CI gate exists. Fix: add `"typecheck": "tsc --noEmit"` script; remove flag once errors are fixed.
3. **MED — tsconfig.json include breadth:** compiles 160 non-project files (repos/skills/examples) → 6 spurious errors, slower checks. Fix: extend `exclude`.
4. **MED — tsconfig.json `noImplicitAny: false`:** weakens `strict: true`. Fix: remove override (currently low-cost: only 6 explicit `any` in src, all benign/dead).
5. **INFO — eslint rule set neutered:** ~25 rules off (incl. `no-unused-vars`, `no-explicit-any`, `exhaustive-deps`) + 11 dirs ignored → clean lint is weak signal. Fix: re-enable incrementally (start with `no-unused-vars` and `exhaustive-deps`).
6. **INFO — ~20 dead runtime deps** (see table §5): incl. E9-known TanStack Query, R8-known Prisma pair (schema is untouched scaffold), plus @mdxeditor, react-syntax-highlighter, @dnd-kit×3, uuid, date-fns, next-auth, next-intl, zod, react-hook-form+resolvers, recharts, embla, vaul, cmdk, input-otp, react-day-picker, react-resizable-panels, @reactuses, react-markdown. ~10 MB+ install weight + audit surface. Fix: prune after confirming ui/* dead components aren't planned (35/47 unused).
7. **LOW — immer@10.2.0 extraneous** in node_modules (not in package.json). Fix: `bun pm remove`/manual prune.
8. **LOW — dead code files:** `src/lib/api-client.ts` (E2, 5× `any`), `src/lib/db.ts` (R8), `src/components/ui/{form,chart,carousel,calendar,drawer,command,input-otp,resizable,...}.tsx` ×35 — all 0 importers.
9. **INFO — legacy groups unchanged (pre-existing, verified only):** examples/websocket ×2 TS2307 (socket.io uninstalled); skills/image-edit TS2561 (`images` vs SDK's `image` field — script would likely 400 at runtime if called); skills/stock-analysis TS2322 (SDK types don't model multimodal content arrays); repos/zemest-platform ×2 (stale twins of finding 1).

**Compat verdict:** react@19.2.3 + next@16.1.3 + @types/react@19.2.8 + eslint-config-next@16.1.3 — consistent, no peer conflicts; E10's runtime version confirmed.

---

*Generated by E7 — static analysis only. No files modified, no fixes applied, no daemon touched.*
