# R6 — Calendar & Scheduling Tooling Research (GitHub, research-only)

**Scope:** open-source scheduling/booking + calendar (ICS/CalDAV/Google) tooling for zemest's roadmap: (1) full in-platform scheduling/bookings for sellers, (2) Google/Apple Calendar export, (3) later 2-way sync.
**Method:** GitHub REST search API (17 successful queries, 25 API calls total incl. rate-limited attempts — shared egress IPs were saturated, so stars/license/last-commit were cross-verified via shields.io GitHub badges, raw.githubusercontent.com LICENSE files, and PyPI/npm registry metadata. Zero code changes made.)

---

## 0. Grounding — what zemest already has (read from the repos)

| Piece | State today |
|---|---|
| `app/api/calendar.py` | ✅ EXISTS & registered in `router.py`: token-authenticated public ICS feed (`GET /api/calendar/{token}/calendar.ics`), token rotate/get endpoints, `Tenant.calendar_token` (String 64, unique, indexed). Hand-rolled ICS: correct CRLF + escaping, **but no 75-octet line folding (RFC 5545 §3.1) and DTSTAMP = "now" on every render** — both are correctness gaps a real iCal library removes. |
| Frontend calendar pieces (Task 18) | ⚠️ **NOT in the current checkout**: `src/app/api/calendar/[token]/route.ts`, `zemest-api.ts`, the rewritten scheduler page and channels page are absent — `repos/zemest-platform` currently holds the OLD mock scheduler (`mockPosts`, fake heatmap) and `src/lib` has no `zemest-api.ts`. The sandbox tree appears to predate the Task-18 frontend commits. Backend calendar work survived. **Orchestrator should re-apply/re-verify the Task-18 frontend before Phase 2.** |
| Scheduler engine | `app/tasks/inline_worker.py`: hand-rolled 30s asyncio scan loop in the uvicorn process (works, E2E-proven in Task 18); Celery+Redis declared in `requirements.txt` but unwired; no APScheduler. |
| Frontend deps relevant to calendars | `react-day-picker`, `date-fns`, `@dnd-kit/*` already installed → a booking calendar UI can be built with **zero new heavy UI deps**. |
| Model | `ScheduledPost` (platform, caption, media, scheduled_at, status, retry_count…) — good base pattern for a future `Booking` model. |

---

## 1. HEADLINE FINDING — Cal.com is no longer AGPL

**calcom/cal.com — https://github.com/calcom/cal.com — ★48k, license: MIT (verified twice), pushed 2026-08/09 (daily), not archived.**

- Verified from the **current `main` branch `LICENSE` file** (fetched raw): pure 21-line MIT, "Copyright (c) 2020-present Cal.com, Inc."
- Cross-verified via GitHub license detection (shields.io `github/license` badge): **MIT**.
- Historically AGPL-3.0 (the license everyone remembers — including our own briefing). The relicense to MIT changes the legal risk calculus completely. Caveats: ecosystem pieces vary (e.g. `cosscom/coss`, "official design system of Cal.com", still shows **AGPL-3.0**), so per-file license checks remain necessary if vendoring code.

**Verdict for zemest: still DO NOT adopt the codebase.** Cal.com is a full Next.js + Prisma + tRPC + NextAuth monolith (auth, email, video, payments, multi-team). Running it next to zemest = a second app, second DB, auth bridge, double multi-tenancy — massive ops weight for a feature (booking links) that our roadmap wants *native* in-platform. The MIT relicense does make it (a) safe to **borrow UX/data-model concepts** (availability as weekday interval sets + date-specific overrides; booking statuses; reschedule/cancel flows) and (b) a legitimate **iframe-embed fallback** if we ever want hosted public booking pages fast. Keep it on the "revisit if we productize booking links" shelf.

---

## 2. TOP 5 RECOMMENDATIONS (ranked, adoptable, matched to roadmap phases)

### #1 — APScheduler (Python job scheduler) — *Phase 1 engine*
- **URL:** https://github.com/agronholm/apscheduler — **★7.6k, MIT, pushed 2026-08-31 (yesterday)** — `pallets`-tier maintenance, async-native 4.x.
- **What it solves:** our hand-rolled 30s `inline_worker` loop is a poll loop, not a scheduler: no cron/interval/date triggers, no misfire-grace handling, no persistent jobstore, no jitter. In-platform **bookings need exact-time execution + reminders + recurring availability** — that's APScheduler's exact shape (`AsyncIOScheduler` in the FastAPI lifespan; `date` triggers per booking, `cron`/`interval` for scans and reminders; `SQLAlchemyJobStore` once we're on Postgres).
- **Integration sketch:** replace `_worker_loop()` with `AsyncIOScheduler()` started in `main.py` lifespan: one `interval(seconds=30)` job wrapping the *existing* `_publish_due_posts_async()` (zero behavior change, idempotent scan stays), plus `date` jobs for booking reminders/hold-expiry. Keep `SCHEDULER_INLINE_WORKER`-style env kill-switch; only add the persistent jobstore at the SQLite→Postgres migration (SQLite jobstore + multi-worker = our existing leader-lock concern from 18-d).
- **Verdict: ADOPT (Phase 1).** Smallest-diff, highest-leverage backend change. Complements (not replaces) the ARQ recommendation from 18-d: ARQ = durable queue for heavy/retrying work (webhook LLM replies), APScheduler = time-triggered work. Subsumes croniter-style cron parsing for "best-time" recurring posts.

### #2 — icalendar (Python RFC-5545 library) + python-dateutil — *Phase 2 core*
- **URL:** https://github.com/collective/icalendar — **★1.2k, BSD-3-Clause (license text verified from `LICENSE.rst`; GitHub shows "not identifiable" only because the file is reStructuredText), pushed 2026-08-31 (yesterday), v7.3.0, very active.** Pair with `dateutil/dateutil` (★2.6k, Apache-2.0/BSD dual, v2.9.0) whose `dateutil.rrule` is *the* RRULE engine.
- **What it solves:** bulletproof ICS generation/parsing — RRULE/EXDATE recurrences, VTIMEZONE, escaping, **75-octet line folding** (our hand-rolled feed lacks folding → strict parsers/validators can reject long Arabic captions; also our DTSTAMP regenerates every request which makes some clients re-alert). Recurring bookings ("every Sunday 6pm") become expressible; parsing external ICS is the read-side of 2-way sync.
- **Integration sketch:** in `calendar.py`, build `Calendar()/Event()` objects (UID = existing `{post.id}@zemest`, status→`TRANSPARENT`/`CONFIRMED`/`CANCELLED` mapping preserved), serialize with `to_ical()` — ~30 lines replacing the string builder; feed route/mime type/token auth untouched. Add `icalendar + python-dateutil` to `requirements.txt` (~1MB pure-Python).
- **Verdict: ADOPT (Phase 2, first PR of the calendar track).** Correctness hardening of an already-live feature; also the parsing foundation for Phase 3.

### #3 — google-api-python-client (Google Calendar v3) — *Phase 2→3 primary external integration*
- **URL:** https://github.com/googleapis/google-api-python-client — **★8.9k, Apache-2.0, pushed yesterday** — official Google client, `calendar v3` incl. `events.watch` push channels, `syncToken` incremental sync, extendedProperties (perfect for `source=zemest:booking:<uid>` mapping), `conferenceData`.
- **What it solves:** real Google 2-way sync (our current "Add to Google" is a *read-only subscription* via the ICS URL — fine, but roadmap says 2-way later).
- **Integration sketch:** tenant-scoped OAuth (we already run this pattern for Meta in `channels.py`): store refresh token in `tenant.*_meta` JSON → background sync job (APScheduler) does `events.list(syncToken=…)` pull + `events.insert/update` push with an `external_event(uid, etag, calendar_id, last_synced_at)` mapping table; optional `events.watch` → public webhook endpoint (we already run HMAC-verified webhooks for Meta, so the ops pattern exists). Google sync beats CalDAV for Google accounts (free-busy, patch semantics, push).
- **Verdict: ADOPT when Phase 3 starts.** Standard, zero license risk. (Alternative shape: keep Google read-only via the existing ICS URL and only push outward — cheaper, acceptable v1 of "2-way".)

### #4 — python-caldav (CalDAV client) — *Phase 3 for Apple/iCloud/Nextcloud/self-hosted*
- **URL:** https://github.com/python-caldav/caldav — **★411, Apache-2.0, pushed last week (active), v3.2.1** — the maintained Python CalDAV client (PROPFIND/REPORT/calendar-query, etag-based updates).
- **What it solves:** 2-way sync with **any CalDAV server**: Apple iCloud (app-specific passwords), Nextcloud, Fastmail, **Google also exposes CalDAV**, and self-hosted servers. This is the Apple write-back path — Apple Calendar subscribes to our ICS (already works) but can't write back without CalDAV.
- **Integration sketch:** per-tenant "external calendar" settings (URL + credentials in `tenant.*_meta`), APScheduler job: pull VEVENTs → `icalendar` parse → map to bookings via UID; push ours with etag conflict detection (last-write-wins + audit). Run in a worker (the lib is requests-based → wrap in `asyncio.to_thread`).
- **Sister option:** **Kozea/Radicale** (★4.9k, GPL-3.0, active, https://github.com/Kozea/Radicale) — minimal Python CalDAV *server*: running it as a sidecar would make **zemest itself a 2-way CalDAV source** (Apple/Thunderbird sync natively, no Google dependency). GPL is fine as a separate process (no code mixing). Keep for Phase 3+.
- **Verdict: ADOPT at Phase 3** (client first; Radicale sidecar only if users demand non-Google 2-way).

### #5 — someday (embeddable MIT availability picker) — *Phase 1 UI accelerant*
- **URL:** https://github.com/rbbydotdev/someday — **★1.1k, MIT, pushed 2026-07 (active)** — "free-to-host calendar availability picker — open-source cal.com/calendly alternative built on [its own engine]".
- **What it solves:** the *hardest UI part* of in-platform bookings (timezone-correct availability grid + slot picking) as an **embeddable, MIT, self-hostable widget** — without adopting a whole booking platform and without adding a fullcalendar-sized JS dep (we already have react-day-picker + dnd-kit for the dashboard side).
- **Integration sketch:** embed on the merchant's public booking page (Next route under `/b/[slug]`) pointing at our own `/api/public/availability` + `/api/public/bookings` endpoints; bookings land in our DB and get published to the merchant's ICS feed automatically.
- **Verdict: SPIKE (Phase 1).** Young project — evaluate API shape/timezone handling before committing; fallback is a react-day-picker grid, which is fine.

---

## 3. Evaluated and skipped (with reasons)

| Tool | Stars / License / Status | Why skipped for zemest |
|---|---|---|
| **calcom/cal.com** | 48k / **MIT now** (was AGPL) / daily pushes | Full monolith; see §1 — concepts + embed-only. `cosscom/coss` design system is AGPL-3.0. |
| **alextselegidis/easyappointments** | 4.3k / GPL-3.0 / active | Excellent self-hosted booking app but **PHP/MySQL** — wrong stack; separate service + auth; GPL. |
| **fullcalendar/fullcalendar** | 20.6k / MIT / active | We explicitly avoid heavy UI deps; react-day-picker+date-fns+dnd-kit already cover us. If we ever need a real month/week grid: **schedule-x/schedule-x** (★2.5k, MIT, active) is the lighter modern pick. |
| **nylas (SaaS)** | nylas/nylas-mail 24.7k / MIT / **archived** | Nylas API is proprietary now; OSS mail client is dead. Not self-hostable — skip. |
| **zcal** | — / no maintained repo found (searched; only unrelated zCalc repos) | Not verifiable as OSS anymore. |
| **cronit / croniter** | pallets-eco/croniter ★562 / MIT / active | "cronit" isn't a notable OSS project; croniter (cron-string→datetime) is subsumed by APScheduler's CronTrigger. |
| **ical.tools** | hosted service | Not an OSS GitHub library — commercial ICS tooling/validator site. Useful *manually* to validate our feed. |
| **C4ptainCrunch/ics.py** | 721 / Apache-2.0 / **dormant since Dec 2024** | Simpler ICS writer, less active than icalendar; no RRULE depth. |
| **jkbrzt/rrule** (rrule.js) | 3.7k / BSD-3 (npm) / **dormant since Nov 2023** | Only needed if the *frontend* expands recurrences; we'll expand server-side with dateutil. |
| **jens-maus/node-ical** | 170 / Apache-2.0 / active | Node ICS parser w/ RRULE — only if BFF parses ICS; backend path uses icalendar. |
| **kewisch/ical.js** | 1.2k / MPL-2.0 / active | Canonical JS RFC-5545 engine (Thunderbird) — same reason as node-ical. |
| **natelindev/tsdav** | 354 / MIT / active | TS CalDAV client — noted as the BFF-side alternative if sync ever moves to Next; Python owns integrations today. |
| **niccokunzmann/open-web-calendar** | 329 / GPL-2.0 / active | Renders ICS feeds into an embeddable calendar UI — cute iframe option for merchant public pages; not needed for dashboard. |
| **lucafaggianelli/plombery** | 661 / MIT / active | Python task scheduler with web UI — admin nice-to-have, not core to bookings. |

---

## 4. 2-way sync feasibility (the Phase-3 architecture, condensed)

1. **Canonical store = zemest DB.** Booking/post is truth; UID `<uuid>@zemest` (already our ICS UID scheme).
2. **Outbound (read-only) already live:** token ICS feed — keep forever; add bookings as VEVENTs; add RRULE for recurring.
3. **Google 2-way:** OAuth per tenant → `events.list(syncToken)` incremental pull + `events.insert/update` push; map with `extendedProperties` + local etag table; optional `watch` channel to our existing webhook infra. Conflict policy: last-write-wins + `STATUS:CANCELLED` tombstones.
4. **Apple/iCloud 2-way:** CalDAV via `python-caldav` (iCloud app-specific passwords) or, server-side play, run **Radicale** so zemest *is* a CalDAV calendar (native Apple 2-way without any cloud).
5. **Everything else:** ICS/webcal subscription (works today, Outlook/Fastmail included).

## 5. Recommended roadmap mapping (our exact sequence)

- **Phase 1 — in-platform bookings (now):** new `Booking` + `Availability` models (Cal.com-style interval sets), APScheduler `AsyncIOScheduler` in lifespan (date triggers for reminders/holds; keep the idempotent 30s scan as an interval job), public booking page (`/b/[slug]`) — spike **someday** for the picker, else react-day-picker. No fullcalendar.
- **Phase 2 — export hardening (next):** swap hand-rolled ICS for **icalendar+dateutil** (folding/escaping/RRULE/VTIMEZONE, stable DTSTAMP); re-land the Task-18 frontend calendar card (currently missing from the checkout — see §0); optionally ical.tools to validate the feed.
- **Phase 3 — 2-way sync (later):** **google-api-python-client** for Google tenants; **python-caldav** for CalDAV; Radicale sidecar considered only on demand. ARQ (18-d) as the durable queue under the sync jobs.

**Bottom line:** the license wall we feared (Cal.com AGPL) has actually fallen (MIT, verified) — but the correct move is still to *build native in-platform scheduling with APScheduler + icalendar*, and reach Google/Apple with the two official-ish clients (google-api-python-client, python-caldav) rather than running a second platform. Total new deps for Phases 1–2: `apscheduler`, `icalendar`, `python-dateutil` — all small, MIT/BSD/Apache, active.
