# R7 — GitHub Research: Realtime Layer for Live Chat (Next.js 15 + FastAPI)

**Agent:** R7 (github-research, RESEARCH ONLY — no code changes, no git commands) · **Date:** 2026-09-01 · **Method:** GitHub REST search API (25 calls; core `/repos` endpoint was hard rate-limited on the shared sandbox IP, so all metadata came through the `/search/repositories` bucket, which has a separate quota) + direct local inspection of both repos, the live running processes, the Python venv, and `package.json`.

**Mission:** live chat updates — agent-reply streaming, typing indicators, new-message push — **without heavy infra**, working in this sandbox (no external SaaS), compatible with the Next.js dev server, integrating with FastAPI, low memory, with a graceful fallback to polling.

---

## Grounding facts from the repo (not assumptions)

These change the shape of the recommendation, so they come first:

1. **There is no polling to replace yet — the chat UI is fully mocked.**
   - `src/app/dashboard/[tenantId]/chat/page.tsx` = mock messages array + `setTimeout(…, 1200)` *simulated* AI reply. Zero network calls.
   - `src/app/dashboard/[tenantId]/conversations/page.tsx` = `mockConversations` + `mockThread`, filtered locally. Zero network calls.
   - The only `setInterval` in the frontend is a typing animation in the marketing `conversational-demo.tsx`.
   - (Task 18-c already noted: 14/14 dashboard pages are `"use client"` with hand-rolled fetch hooks / mock data; no React Query or SWR usage in code.)
   → The realtime layer is **greenfield wiring**, not a poller replacement. It should be designed together with the data-fetching layer, not bolted onto it.

2. **`@tanstack/react-query` ^5.82.0 is ALREADY a dependency in `package.json`** (unused in code). The invalidation/polling half of the realtime story needs **zero new frontend packages**.

3. **`sse-starlette` 3.3.4 is ALREADY INSTALLED in the live venv** (`/home/z/.venv`, the same Python 3.12.14 the running uvicorn uses) — verified via `pip show`. Not pinned in `requirements.txt` yet. `websockets 16.0` is also present via `uvicorn[standard]`. `python-socketio` is **not** installed.

4. **Sandbox topology (verified live):** uvicorn single process on :8000 (pid 1887, no `--workers`, launched by `daemon_backend.py`), next-server dev on :3000. **No Docker, no Redis, no Postgres** — DB is SQLite (`aiosqlite`). Anything needing a broker or a second daemon loses points.

5. **Auth topology:** Next.js BFF routes (`/api/auth/*` on :3000) call FastAPI, then set **httpOnly cookie `zemest_auth`** (the JWT access token, `sameSite=lax`, `path=/`). FastAPI itself authenticates via **`Authorization: Bearer`** only (`app/dependencies.py`, HTTPBearer) — it does not read cookies, and there is **no CORSMiddleware** in `app/main.py`. `api-client.ts` defaults to talking **directly to :8000** (`NEXT_PUBLIC_API_URL || http://localhost:8000`).
   - Consequence A: cookies are host-scoped (not port-scoped), so `zemest_auth` *would* reach :8000, but FastAPI won't read it → a direct browser→:8000 SSE/WS connection needs either CORS+credentials or token-in-URL.
   - Consequence B: **WebSockets cannot be proxied through Next.js route handlers** (no WS-upgrade support without a custom server), while **SSE can** (streaming route handlers). SSE therefore fits the existing BFF cookie pattern with no CORS changes at all.
   - Consequence C: the in-process asyncio workers (`inline_worker`, `training_worker`, silent trainer) live **in the same process** as the web app — they can publish events directly to an in-process bus with zero cross-process machinery *today*.

---

## Evaluated candidates (GitHub data, this research pass)

| Tool | Repo | Stars | Last push | License | Sandbox feasible? | Verdict |
|---|---|---|---|---|---|---|
| sse-starlette | sysid/sse-starlette | 849 | 2026-08-14 | BSD-3-Clause | ✅ **already installed** | **#1 — primary transport** |
| Azure/fetch-event-source | Azure/fetch-event-source | 2,869 | 2026-02-28 | MIT | ✅ (npm) | **#4 — SSE client primitive** |
| python-socketio | miguelgrinberg/python-socketio | 4,367 | 2026-08-29 | MIT | ✅ pip install, single-proc OK | **#2 — bidirectional upgrade path** |
| socket.io (JS) | socketio/socket.io | 63,211 | 2026-07-24 | MIT | ✅ | (pairs with #2) |
| TanStack Query | TanStack/query | 50,241 | 2026-08-31 | MIT | ✅ **already in package.json** | **#3 — invalidation + polling fallback** |
| vercel/swr | vercel/swr | 32,476 | 2026-08-23 | MIT | ✅ | lighter alternative to #3 — skip (TanStack already declared) |
| Centrifugo | centrifugal/centrifugo | 10,686 | 2026-08-31 | Apache-2.0 | ⚠️ binary runs, but 2nd daemon + HMAC tokens | **#5 — scale-out only** |
| centrifuge-js | centrifugal/centrifuge-js | 502 | 2026-08-30 | MIT | ✅ | (pairs with #5) |
| supabase/realtime | supabase/realtime | 7,626 | 2026-08-31 | Apache-2.0 | ❌ needs Postgres + Elixir service (sandbox = SQLite) | SKIP |
| partykit | partykit/partykit | 5,698 | 2026-01-29 | MIT | ❌ Cloudflare-Workers-shaped; slowing since CF acquisition | SKIP |
| soketi | soketi/soketi | 5,634 | **2025-03-03 (stale ~18 mo)** | AGPL-3.0 | ⚠️ separate Node service | SKIP (stale + AGPL) |
| uWebSockets.js | uNetworking/uWebSockets.js | 9,149 | 2026-07-11 | Apache-2.0 | build-your-own Node WS server | N/A (building block) |
| react-use-websocket | robtaussig/react-use-websocket | 1,886 | 2025-02-04 (stable, slowing) | MIT | ✅ | only needed if WS route chosen |
| permitio/fastapi_websocket_pubsub | permitio/fastapi_websocket_pubsub | 594 | 2025-07-15 | MIT | ✅ in-proc WS pub/sub | SKIP — SSE covers it with less |
| aaugustin/websockets | aaugustin/websockets | ~11k (not re-verified — search quota exhausted) | active | BSD-3 | ✅ transitive dep of `uvicorn[standard]`, already 16.0 | base layer for any WS route |
| "litefury" | — | — | — | — | — | **DOES NOT EXIST** as a realtime tool — all GitHub hits are FPGA boards (RHSResearchLLC/NiteFury-and-LiteFury etc.). Disproved. |
| Ably / Pusher | — | — | — | — | external SaaS | excluded by requirement |

Notes on the two "obvious" alternatives that lose here:
- **socket.io ↔ python-socketio** is the default reflex, but it buys bidirectionality we don't need yet (typing client→server can be a plain POST like every other mutation in this codebase), costs a new server-side dependency + a ~40 kB client bundle, and its multi-worker story needs a Redis message queue we don't have running. It stays as the documented upgrade path, not the default.
- **Centrifugo** is genuinely excellent (self-hosted Ably/Pusher alternative, actively shipped, memory engine works without Redis) — but it's a second always-on daemon with HMAC token minting for a problem one in-process asyncio bus already solves at our scale (1 tenant, a handful of tabs).

---

## ⭐ Top 5, ranked

### 1. sse-starlette — SSE transport on the existing FastAPI process (PRIMARY)
- **URL:** https://github.com/sysid/sse-starlette · **Stars:** 849 · **Last push:** 2026-08-14 · **License:** BSD-3-Clause · **Version installed:** 3.3.4
- **Sandbox feasibility:** perfect — zero new services, zero new daemons, works with SQLite + the single uvicorn worker; the package is *already importable by the live server* (verified: `pip show sse-starlette` in `/home/z/.venv`, the interpreter uvicorn runs on). One action item: pin `sse-starlette==3.3.4` in `requirements.txt` so a venv rebuild doesn't silently lose it.
- **Why it wins on the axes:** server-push of new messages + agent deltas + typing events; one `asyncio.Queue` per open tab (a few KB — memory is a non-issue at our scale); automatic reconnect is a client concern and is solved by #4; **Next.js dev-server compatible both ways** — browser can hit :8000 directly (matches the `api-client.ts` default) or stream through a Next.js route handler (SSE pass-through works in dev, unlike WS); degrades to #3 polling in ~10 lines.
- **Integration sketch (server):**
  ```python
  # app/realtime/bus.py — in-process pub/sub. Single uvicorn worker today ⇒ safe.
  # (When multi-worker/ARQ/Redis lands: swap the dict-of-queues for redis.asyncio pub/sub
  #  behind the same publish()/subscribe() signatures — the callers never change.)
  import asyncio, json
  from collections import defaultdict
  _subs: dict[str, set[asyncio.Queue]] = defaultdict(set)
  def publish(channel: str, event_type: str, data: dict) -> None:
      for q in list(_subs.get(channel, ())):
          q.put_nowait((event_type, data))

  # app/realtime/routes.py
  from sse_starlette.sse import EventSourceResponse
  @router.get("/api/tenants/{tenant_id}/events")
  async def tenant_events(tenant_id: uuid.UUID, user=Depends(get_current_user)):
      async def gen():
          q: asyncio.Queue = bus.subscribe(f"tenant:{tenant_id}")
          try:
              while True:
                  etype, data = await q.get()
                  yield {"event": etype, "data": json.dumps(data, ensure_ascii=False)}
          finally:
              bus.unsubscribe(f"tenant:{tenant_id}", q)
      return EventSourceResponse(gen(), ping=15)
  ```
  Publish hook points (all in this repo, no new infra): after `process_customer_message` in `app/api/test_chat.py` and `app/api/webhook.py` → `message.new`; before the LLM call → `agent.typing`; inside a streaming `llm_client` variant (`httpx stream=True` / LiteLLM `stream=True`) → `agent.delta` chunks; the silent trainer / inline workers can publish `conversation.updated` directly since they share the process.
- **Verdict:** **ADOPT (primary).** The lowest-infra option that delivers all three roadmap features (agent streaming, typing indicators, new-message push) on a dependency that is already installed.

### 2. python-socketio ↔ socket.io-client — bidirectional upgrade path
- **URLs:** https://github.com/miguelgrinberg/python-socketio (4,367★, MIT, pushed 2026-08-29 — very active) · https://github.com/socketio/socket.io (63,211★, MIT, pushed 2026-07-24)
- **Sandbox feasibility:** good — `pip install python-socketio`, mount `socketio.ASGIApp(app, socketio_server)` in `main.py`; the default in-memory manager is fine for the current single-process daemon; JS side adds `socket.io-client` (~40 kB gzip) with reconnect/rooms built in.
- **Integration sketch:** `sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins=["http://localhost:3000"])`; `@sio.on("connect")` verifies the JWT passed in `AUTH` payload (Bearer won't be in headers by default); `await sio.emit("message.new", payload, room=f"tenant:{id}")`; backend emit-points identical to #1.
- **Why it's #2 and not #1:** we need server→client push, and typing client→server is trivially a REST POST here; meanwhile socket.io costs a new backend dep + client bundle, needs explicit connect-auth wiring (HTTPBearer won't carry over), and its horizontal scale-out needs the Redis message queue that this sandbox doesn't run. **Choose it only if** we later want server-confirmed typing/presence over the same channel, or the WS multiplexing of many conversations.
- **Verdict:** HOLD — documented upgrade path, not the default.

### 3. TanStack Query — cache invalidation + the polling fallback (ALREADY IN package.json)
- **URL:** https://github.com/TanStack/query · **Stars:** 50,241 · **Last push:** 2026-08-31 · **License:** MIT · **Declared in repo:** `@tanstack/react-query` ^5.82.0 (unused in code)
- **Sandbox feasibility:** perfect — it's already a dependency; add `QueryClientProvider` in the dashboard layout and go.
- **Why it matters for realtime:** the pattern is *event → invalidate → refetch*. The SSE stream (or the WS room) never carries message payloads; it just says "conversation X changed", then `queryClient.invalidateQueries({ queryKey: ["conversations", tenantId] })` refetches through the existing REST endpoints. Payload stays cached, canonical, and typed. **Fallback mode:** the same hook sets `refetchInterval: 10_000` whenever the stream is down (SSE `onerror` after N retries) — polling becomes a degraded mode of the same component, not a separate code path. `revalidateIfStale`-style SWR behavior (32k★ vercel/swr, also MIT/active) is a lighter alternative, but adding SWR when TanStack is already declared would be a second data layer for no gain — **skip SWR**.
- **Verdict:** **ADOPT (client half of the primary design).**

### 4. Azure/fetch-event-source — authenticated, retryable SSE client
- **URL:** https://github.com/Azure/fetch-event-source · **Stars:** 2,869 · **Last push:** 2026-02-28 · **License:** MIT
- **Why it's needed:** native `EventSource` cannot send an `Authorization` header (our FastAPI expects Bearer), can't do POST, and gives no control over retry backoff. This lib wraps `fetch()` streaming, keeps a custom `AbortController`, and gives `onopen/onmessage/onerror` with full header control — one small package (no deps) that solves exactly the auth + fallback-control problems in our topology.
- **Integration sketch (client hook):**
  ```ts
  // src/hooks/use-tenant-events.ts (sketch)
  import { fetchEventSource } from "@microsoft/fetch-event-source";
  // BFF variant (recommended): same-origin route /api/tenants/[id]/events on :3000
  // streams from :8000, reading the httpOnly zemest_auth cookie server-side →
  // no CORS, no token in JS. Direct variant: headers: { Authorization: `Bearer …` }.
  useEffect(() => {
    const ctrl = new AbortController();
    let failures = 0;
    fetchEventSource(url, {
      signal: ctrl.signal,
      async onopen(res) { failures = 0; if (!res.ok) throw new Error(); },
      onmessage(ev) {
        if (ev.event === "message.new" || ev.event === "agent.delta")
          queryClient.invalidateQueries({ queryKey: ["conversations"] });
        if (ev.event === "agent.typing") setTyping(true);
      },
      onerror(err) {
        if (++failures >= 5) { setPollingFallback(true); throw err; } // stop retrying → poll via TanStack
        return Math.min(1000 * 2 ** failures, 15000);                 // exp backoff, else retry
      },
    });
    return () => ctrl.abort();
  }, [tenantId]);
  ```
- **Next.js dev-server compatibility notes (the BFF variant):** a route handler at `src/app/api/tenants/[tenantId]/events/route.ts` with `export const dynamic = "force-dynamic"`, `fetch(BACKEND/events, { cache: "no-store" })`, then returning `new Response(upstream.body, { headers: { "content-type": "text/event-stream", "cache-control": "no-cache" } })` — streaming pass-through works on the dev server (Node runtime); avoid any middleware that buffers. This also fixes Consequence A: no CORS middleware needed on FastAPI at all, cookie auth stays httpOnly end-to-end.
- **Verdict:** **ADOPT (with #1).** If the team insists on zero new npm deps, native `EventSource` + a one-time `?token=` query param works, but tokens-in-URLs land in logs — not worth it for one 3 kB library.

### 5. Centrifugo + centrifuge-js — self-hosted pub/sub for the multi-worker future
- **URLs:** https://github.com/centrifugal/centrifugo (10,686★, Apache-2.0, pushed 2026-08-31 — the canonical self-hosted Pusher/Ably/socket.io alternative) · https://github.com/centrifugal/centrifuge-js (502★, MIT, pushed 2026-08-30; WS + EventSource + HTTP-streaming fallbacks, auto-reconnect, presence)
- **Sandbox feasibility:** partial — it's a single Go binary (no Docker needed; a tarball runs directly, memory engine works without Redis/NATS), but it is a **second always-on daemon** (~30–80 MB RSS), needs HMAC connection-token minting added to FastAPI, and publishing switches from in-process function calls to HTTP API calls. That's "heavy infra" relative to the problem we actually have (one tenant, a few tabs, one process).
- **When it becomes right:** the day the backend goes multi-worker (granian/`--workers`, per Task 18-d) or multi-instance, the in-process bus in #1 stops being correct. At that point either (a) swap the bus's internals to `redis.asyncio` pub/sub (Redis is already in `requirements.txt` and is the ARQ recommendation from 18-d), or (b) stand up Centrifugo once and let it own fan-out, presence, and reconnect. Choose (a) if Redis is already being adopted for ARQ anyway; (b) if fan-out grows beyond chat (post scheduling pushes, admin dashboards).
- **Verdict:** HOLD — right tool, wrong scale today. Re-evaluate at the multi-worker/Postgres milestone.

---

## Recommendation

**Primary: FastAPI SSE via sse-starlette (already installed) + a Next.js BFF streaming route (same-origin, cookie-auth) + Azure/fetch-event-source on the client + TanStack Query (already in package.json) for invalidate-on-event, with `refetchInterval` polling as degraded mode.**
- Covers all three roadmap features: `agent.delta` streaming, `agent.typing` indicator, `message.new` push.
- Zero new backend packages (pin the one already in the venv), zero new daemons, zero Redis, zero CORS changes, works identically on the Next.js dev server and in prod, and every piece degrades to plain REST + polling.

**Fallback: TanStack Query polling** (`refetchInterval: 10s`, `refetchIntervalInBackground: false`) — it is the same query cache, so "realtime down" just means the invalidation signal stops arriving and the interval keeps data fresh. No separate fallback stack to build or maintain.

**Upgrade paths (in order of trigger):** bidirectional needs → #2 python-socketio; multi-worker/multi-instance → Redis pub/sub behind the same bus interface, or #5 Centrifugo.

**Explicitly rejected for this stack:** supabase/realtime (needs Postgres + Elixir service; sandbox runs SQLite), partykit (Cloudflare-shaped, activity declining since the acquisition), soketi (stale 18 months, AGPL, extra Node daemon), uWebSockets.js (build-your-own), fastapi_websocket_pubsub (nice but redundant vs SSE), "litefury" (**does not exist** — GitHub hits are FPGA development boards), Ably/Pusher (external SaaS, excluded by requirement).

**Sequencing note (matches 18-c's finding that dashboard pages are still mock):** wire TanStack Query + real REST fetching into the conversations/chat pages *first*, then add the SSE layer as an invalidation signal on top — otherwise the stream arrives with nothing to invalidate.

---

## Research provenance
- GitHub API: 25 calls total (`/search/repositories` bucket; the unauthenticated core `/repos` endpoint was exhausted by the shared sandbox IP — retried twice, then worked around via search). Search-rate-limited twice (secondary limit); both retries honored ≥45 s backoff.
- Stars/push dates/licenses in the table are from this pass (2026-09-01). `aaugustin/websockets` figures are from prior knowledge and marked unverified (quota exhausted before its lookup succeeded); it is a transitive dependency of `uvicorn[standard]` (v16.0 installed) and requires no adoption decision.
- Local verification (no code changed): chat/conversations page sources, `api-client.ts`, BFF auth routes, `app/dependencies.py` (HTTPBearer), absence of CORSMiddleware, live process table (uvicorn :8000 / next :3000, no Redis/Postgres/Docker listeners), `pip show sse-starlette`, `websockets.__version__`, `@tanstack/react-query` in `package.json`, `daemon_backend.py` launch line, `test_chat.py` reply path.
