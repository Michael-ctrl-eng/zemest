# P5 — BFF API & Data Layer Analysis (zemest-platform)

**Task ID:** P5 | **Agent:** general-purpose (BFF & data) | **Mode:** research-only, no code modified
**Scope:** `src/app/api/**`, `src/lib/db.ts`, `src/lib/utils.ts`, `prisma/`, `db/`, `mini-services/`, `examples/websocket/`, `tests/`, `.zscripts/` (8 scripts), `components.json`, plus cross-references into the FastAPI backend (`repos/zemest/app/api/auth.py`, `app/services/auth_service.py`, `app/schemas/auth.py`, `app/utils/security.py`, `app/config.py`) and platform consumers (`middleware.ts`, `api-client.ts`, `auth-store.ts`, `auth-page.tsx`) needed to trace the auth/data flows end-to-end.

---

## 1. BFF API Routes

The platform exposes exactly **5 route files** (verified via `find src/app/api`):

### 1.1 `src/app/api/route.ts` — `GET /api`
- 4 lines. Returns `{ message: "Hello, world!" }`. Pure scaffold health-check; no backend call, no auth, no caching headers. Leftover from the Next.js template.

### 1.2 `src/app/api/auth/login/route.ts` — `POST /api/auth/login`
- **Backend URL:** `BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"` (line 3) — a `NEXT_PUBLIC_*` var consumed server-side (see §9).
- **Request parsing:** `await request.json()` (line 7), destructures `{ email, password, remember }` (line 8) with **no validation** (no zod despite `zod@4` being a dependency; undefined fields are silently dropped by `JSON.stringify`).
- **Backend call:** `POST ${BACKEND_URL}/api/auth/login` with `Content-Type: application/json`, body `{email, password}` (lines 11–15). **No timeout / AbortController**, no retry. The BFF does **not** forward any cookies or Authorization header — it is a stateless pass-through for credentials only.
- **Error handling:** non-OK → parses backend JSON error (`{detail}` fallback "Invalid email or password") and re-emits it **with the backend's status code** (lines 17–20). Exceptions (invalid JSON body, network failure) → generic 500 `"Network error — check your connection"` (lines 48–50). Backend errors are thus surfaced verbatim (FastAPI `detail` shape is compatible with the frontend's error rendering).
- **Response shaping:** success → `{ success: true }` only. The backend's `access_token` / `token_type` are **never returned to the browser in the body** — token goes only into cookies (BFF pattern, comment on line 25: "JWT never exposed to JS").
- **Cookie management** (lines 29–45):
  - `zemest_auth` = access_token: `httpOnly: true`, `secure: NODE_ENV === "production"`, `sameSite: "lax"`, `path: "/"`, `maxAge = remember ? 30d : 24h` (line 27).
  - `zemest_refresh` = refresh_token, set **only if the backend returned one** (line 37): `httpOnly`, `secure` prod-only, `lax`, 7d.
  - ⚠️ The backend `TokenResponse` schema (zemest `app/schemas/auth.py:27-29`) contains **only `access_token` + `token_type`** — `refresh_token` is always `undefined`, so **the refresh cookie is dead code and is never set** (see §9).
- **Security:** no CSRF token, no Origin/Referer check, no rate limiting, no body size guard. `sameSite=lax` provides partial CSRF protection for cookie-authenticated endpoints but login itself is credential-based, so risk is low. No secrets logged.

### 1.3 `src/app/api/auth/register/route.ts` — `POST /api/auth/register`
- Identical structure to login: parses `{name, email, password}` (line 8, unvalidated), forwards to `POST ${BACKEND_URL}/api/auth/register` (lines 10–14), passes backend errors through (422/400 detail), and on success **auto-logs the user in** by setting the same `zemest_auth` (24h fixed — no `remember` handling here) and `zemest_refresh` (7d, never fires) cookies (lines 26–42). Comment line 24: "Auto-login: set httpOnly cookies". Same catch → 500 pattern.
- Note: backend register (`zemest app/api/auth.py:18-25`) returns only `access_token`; it also immediately re-logs in via `login_user` (double password verification server-side — backend concern, out of scope).

### 1.4 `src/app/api/auth/logout/route.ts` — `POST /api/auth/logout`
- 11 lines, no backend call. Deletes `zemest_auth` and `zemest_refresh` cookies via `response.cookies.delete()` (lines 7–8) and returns `{success:true}`.
- ⚠️ **Purely local logout**: the backend has **no logout/revoke endpoint**, so the JWT itself remains valid until expiry (24h). Stolen tokens are un-revocable. Also CSRF-able (any site can POST-trigger logout via form — nuisance-level).

### 1.5 `src/app/api/auth/facebook/route.ts` — `POST/GET /api/auth/facebook`
- **POST branch** (lines 8–54): expects `{ fb_access_token }` in body (line 11). If absent, falls into the redirect branch (lines 13–19). Otherwise forwards the token verbatim to `POST ${BACKEND_URL}/api/auth/facebook` (lines 21–25) and sets the same two cookies on success (24h/7d). Errors pass through with backend status.
- **Redirect branch** (lines 13–19, and the whole GET handler lines 61–66): constructs
  `https://www.facebook.com/v18.0/dialog/oauth?client_id=${fbClientId}&redirect_uri=${origin}/api/auth/facebook/callback&scope=email&response_type=code`
  and `NextResponse.redirect()`s (307). In POST, `fbClientId = process.env.NEXT_PUBLIC_FB_APP_ID` with **no fallback → literal `undefined`** in the URL if unset (line 15). In GET, fallback is the string `"demo_client_id"` (line 62) — which would send users to Meta with a bogus client id.
- **GET handler** (lines 61–66): always redirects to the Meta dialog. This is the path the login UI actually triggers (`auth-page.tsx:168` → `window.location.href = "/api/auth/facebook"`).
- ⚠️ **No `state` parameter and no PKCE** — the OAuth redirect is CSRF-open (an attacker can initiate a login-CSRF / session-fixation-style flow). ⚠️ **The `redirect_uri` (`/api/auth/facebook/callback`) has no corresponding route handler** — the code-exchange leg of the flow does not exist anywhere (see §2).
- Graph API version pinned to `v18.0` (hardcoded, lines 17 and 64) — old but functional.

### 1.6 Cross-cutting observations
- All three proxy routes repeat the cookie-setting block verbatim (≈18 lines × 3) — no shared `setAuthCookies()` helper. Drift already visible: login honors `remember` (30d), register/facebook always 24h.
- The BFF **never proxies authenticated data calls**: there are no `/api/tenants`, `/api/admin/*`, `/api/auth/me` BFF routes, even though `middleware.ts:47` claims "real check happens client-side via GET /api/auth/me" and `api-client.ts` defines the whole surface. The browser is expected to talk to `localhost:8000` directly (see §9 — broken).
- **No open proxying**: backend URLs are fixed-path concatenations; user input never influences host or path. SSRF surface is nil.
- Route handlers use Node runtime (default), fine for Prisma/fetch usage.

---

## 2. Facebook OAuth Flow (full trace)

**Intended flow (what the code implies):**
1. User clicks "Facebook" on `/login` → `window.location.href = "/api/auth/facebook"` (`auth-page.tsx:168`).
2. BFF GET handler → 307 to `https://www.facebook.com/v18.0/dialog/oauth?client_id=…&redirect_uri={origin}/api/auth/facebook/callback&scope=email&response_type=code` (`facebook/route.ts:61-66`).
3. User consents at Meta → Meta redirects to `{origin}/api/auth/facebook/callback?code=…&state=…`.
4. **DEAD END — step 3 route does not exist.** `src/app/api/auth/facebook/callback/` is absent (verified: only 5 route files). The authorization **code is never exchanged** for a token. There is also no code-exchange endpoint on the FastAPI side (`rg "facebook" zemest/app/api` shows only `POST /api/auth/facebook` taking an access token). **The OAuth code flow is architecturally incomplete.**
5. Alternative **POST branch** (token-in-body flow, as if the FB JS SDK had produced a token): BFF forwards `{fb_access_token}` → backend `POST /api/auth/facebook` (`zemest/app/api/auth.py:37-43`).
6. Backend `login_with_facebook` (`zemest/app/services/auth_service.py:41-67`): GET `{FB_GRAPH_API_URL}/me?access_token=…&fields=id,name,email`; non-200 → `ValueError("Invalid Facebook token")` → 401. Then looks up `User.fb_user_id == fb_data["id"]`; if not found **creates a new user** (`id=uuid4, fb_user_id, name, email` — no password, nullable email). Returns `create_access_token({"sub": user.id})`.
   - **Linkage policy:** match by `fb_user_id` only. A user who registered with email+password and later logs in with Facebook (same email) gets a **second, separate account** — no email-based linking/merge. `db.flush()` without commit visible here (commit presumably in get_db teardown).
   - Backend does **not** verify the token against `FB_APP_SECRET` (appsecret_proof) — trusts Graph `/me` response alone (acceptable but worth noting; the backend *does* have a signature-verify helper used for webhooks).
7. Backend returns `TokenResponse(access_token, token_type)` — **no refresh_token**, no user object.
8. BFF sets `zemest_auth` cookie (24h) → browser redirected nowhere (POST branch is an XHR-style call) → user considered logged in.

**Error paths:** invalid/expired FB token → backend 401 `{detail:"Invalid Facebook token"}` → BFF passes 401 through; backend down / body not JSON → BFF 500 "Network error"; missing `NEXT_PUBLIC_FB_APP_ID` in GET → redirect with `client_id=demo_client_id` → Meta error page; missing env in POST-redirect branch → `client_id=undefined` in URL.

**Actual usage:** the UI only ever triggers the GET redirect (step 1–4) → **every real Facebook login attempt ends at a 404 callback**. The POST branch has no caller in the codebase (no FB SDK integration).

---

## 3. Prisma Data Layer

### 3.1 `src/lib/db.ts` (13 lines)
Standard Next.js singleton pattern:
```ts
const globalForPrisma = globalThis as unknown as { prisma: PrismaClient | undefined }
export const db = globalForPrisma.prisma ?? new PrismaClient({ log: ['query'] })
if (process.env.NODE_ENV !== 'production') globalForPrisma.prisma = db
```
- Caches the client on `globalThis` to survive HMR in dev — correct pattern.
- ⚠️ `log: ['query']` is **unconditional** (line 10): every SQL statement is logged **in production too** — noise + potential PII leakage into logs.
- ⚠️ The client is **never used**: `rg "lib/db" src/` → zero imports. Entirely dead code.

### 3.2 `prisma/schema.prisma`
- Generator: `prisma-client-js`; datasource: **SQLite**, `url = env("DATABASE_URL")`.
- **Model `User`** (lines 16–22): `id String @id @default(cuid())`, `email String @unique`, `name String?`, `createdAt DateTime @default(now())`, `updatedAt DateTime @updatedAt`.
- **Model `Post`** (lines 24–32): `id @id cuid`, `title String`, `content String?`, `published Boolean @default(false)`, `authorId String`, `createdAt`, `updatedAt`.
- ⚠️ `Post.authorId` has **no `@relation` to `User`** — no FK, no referential integrity. This is the untouched `nextjs_prisma` template schema (demo blog), not a Zemest domain model.
- **No migrations directory** — `prisma/` contains only `schema.prisma`. Schema is applied via `db:push` (`package.json:10` → `prisma db push --accept-data-loss`), i.e. **destructive sync**, no migration history, no versioning.

### 3.3 `db/custom.db` (24,576 bytes, git-tracked)
SQLite file containing exactly two tables — `User` and `Post` matching the schema — **both with 0 rows** (inspected via sqlite3). It is an empty scaffold DB shipped in the repo (and committed: `git ls-files` includes `db/custom.db`). `.env` is also committed (`.gitignore` lists `.env` but it was added anyway) with `DATABASE_URL=file:/home/z/my-project/db/custom.db` — an **absolute sandbox path**, non-portable; in this clone the file lives at `repos/zemest-platform/db/custom.db`.

### 3.4 What the platform DB stores vs. what's delegated
- **Platform's own DB stores: nothing.** Zero imports of `db`, zero rows, template models only.
- **Everything is delegated to the FastAPI backend's PostgreSQL** (users with `hashed_password`/`fb_user_id`/`is_superadmin`/`is_blocked`, tenants, products, orders, conversations, knowledge, admin analytics — per `api-client.ts` surface and the Z-series analyses).
- **Drift / two-sources-of-truth verdict:** there is no *runtime* drift because the Prisma layer is inert. But there is **latent schema drift**: the platform `User` model (cuid id, email-unique, name) conceptually overlaps the backend `users` table (uuid id, hashed_password, fb_user_id, superadmin flags) with incompatible id types and field sets. If anyone wires `lib/db.ts` in, they'd create a divergent user identity store. Additionally, the dashboard/admin UIs run on **hardcoded mock data** (`src/app/dashboard/page.tsx:7-40` etc.) with **zero `fetch()` calls** in `src/app/dashboard|admin` (verified) — so today the platform has *no live data path at all*; the "data layer" is (a) dead Prisma scaffold and (b) an unused `api-client.ts`.

---

## 4. Mini-Services

**What they are:** a z.ai sandbox deployment convention for running **extra Bun processes alongside the Next.js app** in one container. Each subdirectory of `mini-services/` with a `package.json` (and an entry file) is treated as an independent service: installed with `bun install`, built with `bun build --target bun --minify` into a single bundled `mini-service-<name>.js`, and run with `bun` in production — routed from the outside via Caddy's `XTransformPort` query-param proxy (see §5/§6).

**Current state in this repo:** `mini-services/` contains **only `.gitkeep`** — zero services. The install/build/start scripts all no-op gracefully ("目录不存在，跳过").

**Support machinery (how they'd be built/deployed):**
- `dev.sh:31-81 start_mini_services()` — iterates `$PROJECT_DIR/mini-services/*`, requires `package.json` + a `"dev"` script, runs `bun install && exec bun run dev` per service in background, logs to `.zscripts/mini-service-<name>.log`, disowns.
- `mini-services-install.sh` — loops `/home/z/my-project/mini-services/*` (ROOT_DIR **hardcoded**, line 4), `bun install` per project, success/fail tally.
- `mini-services-build.sh` — same hardcoded ROOT_DIR; finds entry by priority `src/index.ts` → `index.ts` → `src/index.js` → `index.js` (lines 31-35); `bun build <entry> --outfile $DIST_DIR/mini-service-<name>.js --target bun --minify` (lines 49-52); `DIST_DIR=/tmp/build_fullstack_$BUILD_ID/mini-services-dist`; copies `mini-services-start.sh` next to the bundles.
- `mini-services-start.sh` (production runner, plain `sh`) — globs `mini-service-*.js`, launches each with `bun <file> &`, tracks PIDs, graceful shutdown: SIGTERM → 1s wait → up to 4s poll → SIGKILL (lines 10-42, 80-102).
- `build.sh:100-114` — orchestrates install+build **only if `$NEXTJS_PROJECT_DIR/mini-services` exists**, then copies the start script into `$BUILD_DIR`.
- `start.sh:111-131` — production entrypoint runs `./mini-services-start.sh` in background alongside Next.js, before Caddy becomes the foreground process.
- The **intended exemplar** is `examples/websocket/server.ts` (a socket.io service on :3003 that would be reached through `/?XTransformPort=3003`), but it is *not* placed inside `mini-services/`, so it is never built or started by the pipeline.

**Portability note:** `mini-services-install.sh`/`-build.sh` hardcode `/home/z/my-project/mini-services` while `dev.sh`/`build.sh` derive the path from `$PROJECT_DIR`/`$NEXTJS_PROJECT_DIR`. They coincide only because the sandbox project root is `/home/z/my-project`. Fragile if the repo is ever built from another location.

---

## 5. WebSocket Example (`examples/websocket/`)

**`server.ts` (138 lines):** standalone Node HTTP server + `socket.io` `Server`, `path: '/'` (comment lines 6-7: "DO NOT change the path, it is used by Caddy to forward the request to the correct port"), **`cors: { origin: "*" }`** (line 9 — any origin may connect; demo-grade), `pingTimeout: 60000`, `pingInterval: 25000`. In-memory `users: Map<socketId, User>`; events: `test` (echo), `join` (registers user, broadcasts `user-joined` system message, emits `users-list` to the joiner), `message` (broadcasts only if username matches the socket's registered user — trivial anti-spoof), `disconnect` (broadcasts `user-left`). Listens on **port 3003** (line 118). Graceful SIGTERM/SIGINT shutdown. 9-char random message ids.

**`frontend.tsx` (196 lines):** `'use client'` React chat UI (shadcn Card/Input/Button/ScrollArea) that connects with `io('/?XTransformPort=3003', { transports: ['websocket','polling'], reconnection: 5×/1s, timeout: 10s })` (lines 33-43, with comments "Never use PORT in the URL, always use XTransformPort"). The query param is the magic that makes Caddy (§6) reverse-proxy the same-origin request to `localhost:3003`.

**Is it used in production?** **No.** (1) `SocketDemo` is imported nowhere (`rg "SocketDemo|examples/websocket"` → 0 hits); (2) **`socket.io` and `socket.io-client` are not in `package.json`/`bun.lock`** — the files wouldn't even compile/resolve if imported today. It is **reference documentation** for the mini-service + Caddy `XTransformPort` routing pattern, showing future developers how a sidecar service is exposed. Its `cors: "*"` and unauthenticated chat would be unacceptable in production.

---

## 6. Build/Deploy Scripts (`.zscripts/`, 8 scripts + `dev.pid`)

These implement the **z.ai sandbox "fullstack deploy" pipeline** (Chinese log messages, `BUILD_ID` env, runner image `z-ai-python-deploy-runner:test`): build a tar.gz containing Next.js standalone + Python runtime + SQLite DB + mini-services + Caddyfile + start script, to be run by a container runner with Caddy as the front door on `:81`.

### `build.sh` (176 lines) — production build orchestrator
- `exec 2>&1`; `set -e` (no `-u`/`-o pipefail` unlike others). `NEXTJS_PROJECT_DIR=/home/z/my-project` **hardcoded** (line 13). `BUILD_DIR=/tmp/build_fullstack_$BUILD_ID` (line 30).
- `bun install` (line 36) → `bun run build` (line 40) (`next build` + copy `static`/`public` into standalone, per `package.json:7`).
- **Standalone self-heal guard** (lines 50-98): if `.next/standalone/server.js` is missing, inspects `next.config.*`:
  - already `output:"standalone"` but no server.js → hard fail (real build error);
  - `output:"export"` or other value → hard fail (incompatible with the deploy model);
  - no `output` key → backs up config, **perl-injects `output: "standalone",`** after the first object literal opener (line 80), rebuilds, verifies server.js exists, else restores backup and fails. Comments explain this prevents the production `warmup_412 / FunctionNotStarted` failures. (zemest-platform's `next.config.ts:4` already sets standalone, so this path is dormant.)
- **mini-services stage** (lines 100-114): only if `mini-services/` dir exists → runs `mini-services-install.sh` + `mini-services-build.sh`, copies `mini-services-start.sh` into `$BUILD_DIR`. (Skipped in this repo — empty dir exists with `.gitkeep`... note: `-d` is true because the dir exists with `.gitkeep`, so install/build *do* run and simply find zero `package.json` projects.)
- **Artifact collection** (lines 116-136): `.next/standalone` → `$BUILD_DIR/next-service-dist/`, `.next/static` → `next-service-dist/.next/`, `public/` → `next-service-dist/`.
- **Python runtime** (lines 138-141): `PROJECT_DIR=… BUILD_DIR=… bash python-runtime-build.sh` (see below).
- **Database runtime** (lines 143-146): `bash database-runtime-build.sh`.
- **Caddyfile** copy if present (line 149-154; present here → `:81` config).
- Copies `start.sh` into `$BUILD_DIR` (lines 156-159), then `tar -czf $BUILD_DIR.tar.gz` the whole tree (lines 161-167). Cleanup of temp dir commented out (lines 169-170).

### `python-runtime-build.sh` (121 lines) — vendored Python runtime
- Skips (exit 0) when the project has **no `.py/.pyi` sources** (excluding `.git/.next/.venv/node_modules/__pycache__/mini-services/upload/download`) **and** no `requirements.txt`/`pyproject.toml` (lines 12-31). → **For zemest-platform this script is a no-op** (no Python files at repo root).
- Requires `uv` if Python is detected (fails otherwise). Target: `PYTHON_VERSION=3.12` default; deps land in `$BUILD_DIR/python-runtime/site-packages`.
- Dependency strategies: `pyproject.toml`+`uv.lock` → `uv export --frozen --no-dev` → install; bare `requirements.txt` → `uv pip install --target`; bare `pyproject.toml` → `uv pip compile` → install; sources without manifest → stdlib-only warning.
- Rewrites console-script shebangs to `#!/usr/bin/env python` with perl (lines 55-62) so the runner's Python resolves.
- Copies **all `.py`/`.pyi` files preserving relative paths** into `next-service-dist/` via `find | tar` (lines 101-118) — so Python code rides inside the Next service dir and is importable via `PYTHONPATH=/app/next-service-dist`.

### `database-runtime-build.sh` (34 lines) — SQLite artifact
- `PROJECT_DIR` default `/home/z/my-project`, `BUILD_DIR` required. Source: `$PROJECT_DIR/db/custom.db`.
- If the preview DB exists → `cp -a db/. → $BUILD_DIR/db/` ("复制 Preview 数据库到构建产物" — the developer's preview data ships to production); else it will be initialized empty by the `db:push` below.
- Then runs `DATABASE_URL="file:$TARGET_DB_PATH" bun run db:push` **from the project dir** (lines 21-25) — i.e. `prisma db push --accept-data-loss` against the *artifact copy* to sync schema. Fails if `custom.db` wasn't produced (lines 27-30). `set -euo pipefail` enforced.
- ⚠️ Design implication: production DB = **a copy of the developer's SQLite file at build time**; every deploy resets/walks forward from the packaged snapshot. No real DB story (no Postgres), consistent with the inert Prisma layer.

### `mini-services-install.sh` / `mini-services-build.sh` / `mini-services-start.sh`
- Covered in §4. Install: per-subdir `bun install`. Build: entry-file discovery + `bun build --target bun --minify` → `mini-service-<name>.js` in `/tmp/build_fullstack_$BUILD_ID/mini-services-dist/`; Start (sh): launch all bundles with `bun`, PID tracking, TERM→KILL escalation.

### `start.sh` (146 lines) — production entrypoint (runs in the deploy container)
- `BUILD_DIR = script dir`; PID list; cleanup trap (TERM→1s→4s→KILL).
- **Python env** (lines 59-67): if `/app/python-runtime/site-packages` exists → `PYTHONPATH=/app/python-runtime/site-packages:/app/next-service-dist`, `PATH+=…/bin`, `PYTHONDONTWRITEBYTECODE=1`, `PYTHONUNBUFFERED=1`.
- **Next.js** (lines 69-109): `cd next-service-dist`; `NODE_ENV=production`, `PORT=${PORT:-3000}`, `HOSTNAME=0.0.0.0`, `DATABASE_URL=${DATABASE_URL:-file:/app/db/custom.db}`; if using the packaged default it **hard-fails when the DB file is missing** (lines 80-85) to avoid booting on an empty DB. Starts `bun server.js &`, liveness check after 1s.
- **mini-services** (lines 111-131): runs `mini-services-start.sh` in background (non-fatal if it dies).
- **Caddy** (line 145): `exec caddy run --config Caddyfile --adapter caddyfile` as PID 1 / foreground.
- ⚠️ Note: `NODE_ENV=production` here means the BFF cookie `secure: true` — combined with the Caddyfile serving **plain HTTP on :81 (no TLS)**, browsers will **refuse the secure cookie over http://** → production login cookies silently dropped (see §9 R1).

### `dev.sh` (155 lines) — dev orchestrator
- Derives `PROJECT_DIR` from script location (unlike the hardcoded paths elsewhere). Requires `bun`. Steps with timestamped step logging: `bun install` → `bun run db:push` (creates/syncs SQLite from `.env`'s `DATABASE_URL`) → `bun run dev` (Next dev on :3000, PID captured) → `wait_for_service` (curl loop, 60 attempts × 1s) → health check `curl -fsS localhost:3000` → `start_mini_services` (per-service `bun install` + `bun run dev`, background, logs in `.zscripts/mini-service-<name>.log`) → disowns the dev server so the script can exit; `cleanup` trap kills `$DEV_PID` on EXIT/INT/TERM.

### `dev.pid`
- Contains `3413` — the recorded PID of the last dev server started by `dev.sh` (used by the `cleanup` trap context; trivial file).

### `tests/` (3 scripts — sandbox-pipeline self-tests, not app tests)
- `database-runtime-build.sh` (76 lines): stubs `bun` with a fake binary that only accepts `run db:push`, asserts an absolute `file:` `DATABASE_URL`, and records calls. Scenario 1: no preview DB → artifact DB initialized, project dir untouched. Scenario 2: existing preview DB + sidecar file → data and sidecar preserved, `db:push` invoked exactly twice with the right URLs. Pure bash test, runs green.
- `python-runtime-build.sh` (65 lines): requirements.txt project → `report.py` copied into `next-service-dist`, `.venv` excluded; pyproject-only project → sources copied + requirements.txt generated; node-only project whose Python lives under `mini-services/` → **no python-runtime produced** (mini-services are excluded from the Python copy). Verifies exclusion rules.
- `python-runtime-container.sh` (32 lines): builds a project requiring `idna==3.10`, then `docker run` against image `z-ai-python-deploy-runner:test` mounting the build dir and runs `check_runtime.py` with the production `PYTHONPATH` — an end-to-end container smoke test of the vendored runtime.
- These are the only "tests" in the repo; **there are zero tests for the app itself** (no unit/component/e2e for routes, auth, or UI).

---

## 7. `src/lib/utils.ts` (137 lines)

- **`cn(...inputs)`** (lines 1-6): `twMerge(clsx(inputs))` — the canonical shadcn/ui class merger; wired via `components.json:16` (`"utils": "@/lib/utils"`); used across every ui component.
- **`formatCurrency(amount, locale='en-US')`** (14-21): `Intl.NumberFormat` with `currency: "EGP"`, 0-2 fraction digits — Egypt-first pricing (supports `ar-EG`).
- **`formatNumber(num, locale)`** (26-28): locale thousand separators.
- **`formatDate(date, locale)`** (34-44): forces `timeZone: "Africa/Cairo"` display of UTC-stored dates, `year/month(short)/day + HH:mm`.
- **`formatRelativeTime(date)`** (49-63): "just now" / "N min ago" / "N hour(s) ago" / "N day(s) ago", falls back to `formatDate` past 30 days.
- **`truncate(text, maxLen=50)`** (68-71): appends "…".
- **`debounce(fn, delay=300)`** (77-86): trailing-edge debounce; doc comment "300ms per PDF spec" (search inputs).
- **`generateOrderNumber()`** (91-98): `ORD-YYMMDD-###` with 3-digit **`Math.random()`** suffix — ⚠️ collision-prone (1/1000 per day) and not cryptographically random; used by mock UI only (backend presumably owns real order numbers).
- **`validateEgyptianPhone(phone)`** (104-106): regex `^01[0125][0-9]{8}$` — Egyptian mobile prefixes (010/011/012/015), 11 digits.
- **`getStatusColor(status)`** (111-137): maps ~18 statuses across domains (order: pending/confirmed/shipped/delivered/cancelled; API: not_configured/success/failed; conversation: active/imported/order_placed; stock: in_stock/out_stock/limited; crawl: crawling/indexing/completed) to the Tavus design-system CSS variables, fallback `--tavus-plastic-2`.
- Overall: clean, locale-aware, Egypt-localized presentation helpers; no server logic; no imports beyond clsx/tailwind-merge. Quality is good; the only nit is the random order-number generator.

---

## 8. Auth Token Flow Diagram (as-implemented)

```
 BROWSER                     NEXT.JS BFF (zemest-platform)              FASTAPI BACKEND (zemest)         META / FACEBOOK
 ───────                     ────────────────────────────              ──────────────────────────         ───────────────
 │ login page (/login)       src/app/api/auth/*  src/middleware.ts    app/api/auth.py                   graph.facebook.com
 │
 │ [A] PASSWORD LOGIN — UI DOES NOT CALL IT (form is onSubmit=preventDefault, auth-page.tsx:116)
 │ POST /api/auth/login ────► login/route.ts
 │  {email,password,remember}  │ forward {email,password}
 │                            ├──────────────────────────────────────► POST /api/auth/login
 │                            │                                       │ verify pw (argon/bcrypt), issue JWT
 │                            │◄──────────────────────────────────────┤ 200 {access_token(24h), token_type}
 │                            │ (refresh_token always undefined →
 │                            │  zemest_refresh cookie NEVER set)
 │◄─── Set-Cookie: zemest_auth=JWT ◄─ {success:true}  (httpOnly, lax, secure(prod), 24h|30d)
 │
 │ [B] REGISTER — same shape, auto-login, 24h cookie (also unwired in UI)
 │
 │ [C] FACEBOOK OAUTH — the ONLY wired path (auth-page.tsx:168)
 │ GET /api/auth/facebook ───► facebook/route.ts (GET)
 │                            │ build dialog URL (client_id=NEXT_PUBLIC_FB_APP_ID||"demo_client_id",
 │                            │                 redirect_uri={origin}/api/auth/facebook/callback,
 │                            │                 scope=email, response_type=code)   [no state, no PKCE]
 │◄══════════════ 307 redirect ══════════════════════════════════════════════════════════════► │ user consents
 │                            │                                       │                              │
 │◄═══════════════════════════════════ redirect {origin}/api/auth/facebook/callback?code=… ════╝
 │  └─► 404 — CALLBACK ROUTE DOES NOT EXIST → FLOW DEAD-ENDS. CODE IS NEVER EXCHANGED.
 │
 │ [C'] FACEBOOK TOKEN-IN-BODY (POST branch — no caller in UI; hypothetical FB-JS-SDK flow)
 │ POST /api/auth/facebook ───► facebook/route.ts (POST {fb_access_token})
 │                            ├──────────────────────────────────────► POST /api/auth/facebook
 │                            │                                       ├─ GET /me?access_token=… ──────► Graph API v?
 │                            │                                       │◄─ {id,name,email}
 │                            │                                       │ find User by fb_user_id
 │                            │                                       │ (create if absent — NO email
 │                            │                                       │  linkage to password accounts)
 │                            │◄──────────────────────────────────────┤ 200 {access_token(24h)}
 │◄─── Set-Cookie: zemest_auth=JWT ◄─ {success:true}
 │
 │ [D] PAGE GUARDS & SESSION USE
 │ GET /dashboard/* ─────────► middleware.ts: cookie zemest_auth (or legacy "sb-access-token")
 │                            │ present? → next() : 302 /login?redirect=…
 │                            │ (no JWT verification server-side; admin gate is a TODO comment)
 │ dashboard/admin pages: NO fetch at all — 100% mock data (api-client.ts unused)
 │ auth-store.logout(): POST /api/auth/logout ─► deletes cookies locally; JWT stays valid 24h (no revoke)
 │
 │ [E] HYPOTHETICAL DATA CALLS (api-client.ts — dead code): browser → localhost:8000 DIRECTLY
 │ fetch(BACKEND_URL/api/..., {credentials:"include"})  → cookies are backend-origin, NOT zemest_auth → 401
```

---

## 9. Issues / Risks (file:line)

**R1 — Production login is broken by secure-cookie-over-HTTP (deploy-blocking).**
`login/route.ts:31` (`secure: NODE_ENV === "production"`) + `.zscripts/start.sh:75` (`export NODE_ENV=production`) + `Caddyfile:1` (`:81` — plain HTTP, no TLS). Browsers reject `Secure` cookies on non-HTTPS origins → `zemest_auth` never persists in the deployed sandbox → users can never stay logged in. Same for register/facebook routes.

**R2 — Facebook OAuth code flow is incomplete (dead-end 404).**
`facebook/route.ts:16,63` set `redirect_uri={origin}/api/auth/facebook/callback`, but no callback route exists (`src/app/api/` has only 5 files). No code↔token exchange anywhere in BFF or backend (`zemest/app/api/auth.py` has no exchange endpoint). Every UI-initiated FB login (the only wired auth path, `auth-page.tsx:168`) fails.

**R3 — Refresh-token machinery is dead code; sessions hard-expire at 24h.**
Backend `TokenResponse` has no refresh field (`zemest/app/schemas/auth.py:27-29`); backend even ships `create_refresh_token` (`app/utils/security.py:111-124`) that is never exposed. BFF `login/route.ts:37`, `register/route.ts:34`, `facebook/route.ts:44` guard `if (refresh_token)` — never true → `zemest_refresh` never set. No refresh proxy route, no rotation, no revocation on logout (`logout/route.ts` deletes cookies only; backend has no revoke endpoint). With `remember=true`, the 30-day cookie (`login/route.ts:27`) wraps a 24h JWT (`zemest/app/config.py:23 JWT_ACCESS_TOKEN_EXPIRE_MINUTES=1440`) → guaranteed broken "remember me".

**R4 — OAuth lacks `state`/PKCE.**
`facebook/route.ts:17,64` — login-CSRF / session-fixation vector on the redirect flow (moot today only because the flow 404s).

**R5 — The BFF is only half-adopted: no data-plane proxying, dead api-client.**
`src/lib/api-client.ts:27` sends `credentials:"include"` **directly to `localhost:8000`** from the browser — those cookies belong to the backend origin, not the platform origin where `zemest_auth` lives → every authenticated call would 401. Meanwhile zero `fetch()` in `src/app/dashboard|admin` (mock data), and `api-client.ts` exports are imported nowhere. The httpOnly-cookie BFF pattern is architecturally correct but **unwired end-to-end**; there is no `/api/auth/me` BFF route that `middleware.ts:47`'s comment promises.

**R6 — No request validation or schema on BFF routes.**
`login/route.ts:7-8`, `register/route.ts:7-8`, `facebook/route.ts:10-11` — raw destructuring; `zod` is a dependency (`package.json:80`) but unused; malformed bodies degrade to backend 422s or generic 500s; no body-size/type guards; no rate limiting at the BFF (backend has its own limiter per Z10, but the BFF adds none).

**R7 — Prisma layer is dead, template-shaped, and destructively synced.**
`lib/db.ts` never imported; `schema.prisma:16-32` is the demo User/Post scaffold (no `@relation` between them); `package.json:10` `db:push` = `prisma db push --accept-data-loss` (destructive, no migrations dir); `lib/db.ts:10` logs every query in production. Latent two-sources-of-truth risk vs. backend PG `users` (different id types: cuid vs uuid).

**R8 — Committed artifacts & non-portable env.**
`.env` is git-tracked (`git ls-files` line 1) with an absolute path `DATABASE_URL=file:/home/z/my-project/db/custom.db`; `db/custom.db` binary also committed (empty). No `.env.example`; only env vars referenced anywhere are `DATABASE_URL`, `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_FB_APP_ID` — **none validated at boot**; `NEXT_PUBLIC_FB_APP_ID` unset → GET redirect uses literal `"demo_client_id"` (`facebook/route.ts:62`) and POST branch uses `undefined` (`facebook/route.ts:15`).

**R9 — `NEXT_PUBLIC_API_URL` used server-side.**
`login/route.ts:3` etc. — the backend URL is treated as a *public* var (inlined into the client bundle for `api-client.ts:9`); semantically wrong for a server-side secret-adjacent config and encourages pointing the browser directly at the backend (R5). No timeout on outbound `fetch` to the backend (slow backend = hung BFF requests).

**R10 — Misc security hygiene.**
- `middleware.ts:34` accepts legacy `sb-access-token` (Supabase scaffold leftover) as an auth cookie — a stale/foreign cookie name grants dashboard page access (page-level only; no data behind it since mock).
- `middleware.ts:44-48` admin gate is an empty stub ("allow if cookie exists").
- `examples/websocket/server.ts:9` `cors:"*"` + unauthenticated chat (demo only, unused).
- `logout` CSRF-able (no origin check) — nuisance-level.
- No CSRF tokens anywhere; mitigated only by `sameSite:"lax"` and the fact that no cookie-authenticated mutating BFF endpoints exist yet.
- `utils.ts:96` order numbers via `Math.random()` (collisions).
- Script portability: `.zscripts/mini-services-install.sh:4` & `-build.sh:4` hardcode `/home/z/my-project`; `build.sh:13` hardcodes project dir; `python-runtime-container.sh:5` expects a local docker image `z-ai-python-deploy-runner:test`.

**Positives worth noting:** httpOnly+sameSite cookie design, no token in response bodies, no open proxy (fixed backend paths), error passthrough with status preservation, standard Prisma singleton, sane utils, genuinely well-engineered deploy pipeline with self-healing standalone guard and meaningful bash tests for the pipeline itself.

---

## 10. Quality Ratings

| Area | Score | Justification |
|---|---|---|
| BFF API routes (auth proxies) | **5/10** | Correct cookie-based BFF *shape* and clean error passthrough, but: unwired to the UI, duplicated cookie logic, no validation, no timeouts, refresh dead code, and R1 makes prod login impossible. |
| Facebook OAuth flow | **2/10** | Redirect leg works syntactically; callback/exchange missing entirely (404 dead-end), no state/PKCE, no email linkage, no FB SDK integration, bogus fallback client ids. |
| Prisma data layer | **2/10** | Correct singleton pattern, but 100% dead code, template schema (User/Post demo, no relations), destructive db-push with no migrations, empty committed DB, query-logging in prod. |
| Mini-services | **5/10** | Well-thought-out convention with install/build/start/lifecycle handling and graceful degradation when absent — but zero actual services, path hardcoding inconsistency, and the only exemplar lives outside the directory. |
| WebSocket example | **6/10** | Clear, functional demo of the Caddy XTransformPort pattern with lifecycle handling and useful comments; unused in prod, missing deps in package.json, `cors:*`, no auth. |
| Build/deploy scripts (.zscripts) | **7/10** | Impressive engineering: standalone self-heal guard, vendored Python runtime with shebang fixups, DB artifact strategy, graceful shutdowns, plus real bash tests (tests/). Docked for hardcoded paths, zh-only messages, no `pipefail` in build.sh, and baked-in dev-data-to-prod DB semantics. |
| utils.ts | **8/10** | Clean, typed, locale/Egypt-aware helpers, good JSDoc; minor: `Math.random()` order ids, relative-time thresholds hardcoded. |
| Overall BFF & data layer | **4/10** | The architecture on paper (BFF + httpOnly cookies + backend JWT) is right, but the implementation is an unwired façade: UI never calls it, OAuth dead-ends, refresh never happens, Prisma is inert, dashboards are mock. Solid deploy tooling is the strongest part. |
