# E8 — Database Consistency Audit (zemest_local.db)

**Agent:** E8 (error-finder, read-only) · **Date:** 2026-09-01 ~01:00 UTC · **DB:** `repos/zemest/zemest_local.db` (405,504 bytes, page_count 99, `integrity_check` = ok)
**Method:** opened SQLite strictly read-only (`file:...?mode=ro`), built a *canonical* schema with `Base.metadata.create_all` into `/tmp/e8_canonical.db` (never touching the live DB) and diffed canonical vs live; compared models (`app/models/*.py`), lifespan DDL (`app/main.py`), alembic head (`alembic/versions/*`), and runtime evidence (`backend.log`, 1333 lines). No code or DB was modified.

---

## 1. Table inventory + row counts

18 tables, no extra tables, **no `alembic_version` table** (⇒ alembic has never run against this DB).

| table | rows (first pass) | rows (final pass) | notes |
|---|---|---|---|
| users | 2 | 5 | admin@zemest.ai (superadmin), owner@cairo-sneakers.com + 3 test users registered live during this audit by other agents |
| tenants | 1 | 1 | "Cairo Sneakers", owner FK valid, is_active=1 |
| products | 3 | 3 | seeded, `attributes` JSON valid |
| conversations | 0 | 1 | written by live traffic during audit |
| messages | 0 | 6 | incl. `is_fallback` column in use |
| customers | 0 | 1 | |
| token_usage | 0 | 3 | LLM usage rows written during audit |
| orders / order_items | 0 / 0 | 0 / 0 | |
| crawl_jobs, knowledge_bases, scheduled_posts, post_insights, site_users, ip_bans, user_sessions, admin_audit_log, blocked_users | 0 | 0 | |

Counts changed *while auditing* (users 2→5, conversations 0→1, messages 0→6, token_usage 0→3): the daemon (pid 1887, up since 00:49:32) is actively serving other agents' E2E tests. `PRAGMA foreign_key_check` = **no violations**; no duplicate emails; no orphaned FK values (tenants.owner_id, products.tenant_id).

---

## 2. Task-18/19 artifact verification (post-recreation)

| artifact | status | evidence |
|---|---|---|
| WAL journal mode | ✅ **present** | `PRAGMA journal_mode` → `wal` (persistent in file; set by lifespan on first boot 00:48:19). No `-wal`/`-shm` at rest (checkpointed, NullPool closes connections). |
| busy_timeout=5000 | ⚠️ **present by accident** | lifespan sets it once on a NullPool connection that is discarded; **every fresh aiosqlite connection defaults to busy_timeout=5000 anyway** (Python sqlite3 `timeout=5.0` default — verified on a scratch engine). Effective behavior matches the claim; the code mechanism is a no-op. `PRAGMA synchronous=NORMAL` likewise does not persist (connections stay FULL=2). |
| 5 hot indexes | ✅ **all present** | `idx_orders_tenant_created`, `idx_conversations_tenant_last_msg`, `idx_orders_customer`, `idx_conversations_customer` (+ `idx_messages_conversation_created`, model-declared). Created by the successful lifespan pass at the 00:49:32 restart, *not* by bootstrap. |
| UNIQUE(fb_message_id) | ✅ present | `idx_messages_fb_message_id_unique ON messages(fb_message_id) WHERE fb_message_id IS NOT NULL` (partial UNIQUE). Lifespan-only — **not declared in the Message model**. |
| `is_fallback` column | ✅ present | `messages.is_fallback BOOLEAN DEFAULT '0'` (model `Message.is_fallback`, `server_default="0"`). NB: there are **no "style tables"** — style data lives in `tenants.style_profile` JSON; is_fallback is on `messages`. |
| admin_audit_log PK | ✅ fixed variant live | Live DDL: `id INTEGER NOT NULL … PRIMARY KEY(id)` — SQLite **rowid alias**, auto-assign verified empirically (insert with NULL id → id=1). Task-19's BigInteger→Integer fix is in the model source and was recreated by `create_all`. (No `AUTOINCREMENT` keyword: only difference is potential rowid reuse after deleting the max row.) |
| live admin_audit_log rebuild | ✅ table exists | 0 rows, 8 columns, 4 idx_* + 2 model ix_* indexes (see redundancy finding). |

**Why they exist after the wipe (timeline from backend.log):**
1. 00:48:19 — daemon (pid 1731) booted on the *empty* DB. Lifespan created `token_usage` via raw SQL (line 41), all `ALTER TABLE` attempts failed silently, WAL pragmas ran, then `CREATE INDEX idx_orders_tenant_created ON orders…` raised **"no such table: main.orders"** → whole migration block aborted (`Startup migration block failed`, backend.log:129) → hot indexes + UNIQUE fb index + admin tables skipped on that boot. Workers error-looped `no such table: scheduled_posts/tenants/users` every 30–45 s.
2. bootstrap_local.py ran `create_all` → created the other 17 tables (it skips `token_usage`, which already existed) + seeded 2 users/1 tenant/3 products.
3. 00:49:32 — daemon restarted (pid 1887) → lifespan migration block now succeeded → all hot/unique/admin indexes created. This restart is the *only* reason the Task-18 index artifacts exist.

---

## 3. Models vs live tables

**Tables:** 18 model tables = 18 live tables. **No missing tables, no missing columns** on 17 of 18 tables (verified via canonical create_all diff, incl. defaults & nullability). Bootstrap imports the full `app.models` registry (`bootstrap_local.py:22-26`), so `create_all` covers everything: token_usage ✅, admin tables ✅, crawl_jobs ✅, knowledge_base ✅, scheduled_posts/post_insights ✅.

**The one divergent table: `token_usage`** (created by lifespan raw SQL *before* bootstrap could create the model's version):

| column | create_all (model) | live (raw lifespan DDL) |
|---|---|---|
| id | `CHAR(32) NOT NULL`, PK | `UUID` **nullable** PK (SQLite permits NULL in non-INTEGER PKs — verified) |
| tenant_id | `CHAR(32) NOT NULL` | `UUID NOT NULL` (NUMERIC affinity) |
| prompt/completion/total_tokens | `INTEGER NOT NULL` | `INTEGER` nullable, DEFAULT 0 |
| created_at | `DATETIME NOT NULL` | `TIMESTAMP` nullable DEFAULT CURRENT_TIMESTAMP |
| index | `ix_token_usage_tenant_id` | `idx_token_usage_tenant` (raw name) |

SQLite type affinity makes this *functionally* tolerated (ORM inserts uuid hex strings fine — 3 live rows prove it), but it is the only table whose DDL is not model-derived, its `id` can be NULL for raw inserts, and alembic's `op.create_table("token_usage")` would collide with it.

**Other checks:**
- `customers.uq_customer_psid UNIQUE(tenant_id, fb_psid)` ✅ present (table constraint; hidden `sqlite_autoindex`), `orders UNIQUE(order_number)` ✅, `tenants` unique `fb_page_id`/`calendar_token` ✅, `users.fb_user_id` unique ✅.
- **`users.email`: no UNIQUE constraint, nullable** (model `user.py:17`), while `auth_service.register` does racy SELECT-then-INSERT and `login_user` uses `scalar_one_or_none()` (raises `MultipleResultsFound` → 500 if duplicates ever occur).
- JSON columns are plain `JSON` everywhere in live DDL (lifespan's `JSONB`/`DOUBLE PRECISION`/`BIGSERIAL` strings never landed — create_all won; they remain latent for future ALTER paths).
- **Redundant duplicate indexes** — 11 exact pairs (one model `ix_*` + one lifespan `idx_*` on the same column): `admin_audit_log(admin_id, created_at)`, `conversations(customer_id)`, `ip_bans(ip_or_cidr)` *(unique + non-unique!)*, `site_users(user_id, is_blocked, last_country, last_seen)` *(user_id unique + non-unique)*, `user_sessions(user_id, ip_address, login_at)`. Plus prefix-redundant pairs: `ix_orders_tenant_id` ⊂ `idx_orders_tenant_created`, `ix_conversations_tenant_id` ⊂ `idx_conversations_tenant_last_msg`, `ix_messages_conversation_id` ⊂ `idx_messages_conversation_created`, `ix_products_tenant_id` ⊂ `idx_products_tenant_active`. ~17 indexes where ~10 would do → write amplification on hot tables (messages, orders, conversations).

---

## 4. Alembic

- **`alembic_version` table: ABSENT** from zemest_local.db. The DB was built by `create_all` + lifespan DDL, never by migrations; alembic.ini's URL points at Postgres (`postgresql://zemest:…@localhost:5432/zemest`).
- Chain: `5179285ae0ae` (initial) → `927179233531` (flexible products) → **head `a89fe0001_egypt_pivot`**. Single head, no branches.
- **Drift head-vs-models (all confirmed in files):**
  - **7 tables missing from alembic head**: `blocked_users`, `site_users`, `ip_bans`, `user_sessions`, `admin_audit_log`, `scheduled_posts`, `post_insights` (initial creates 10 tables, a89fe0001 adds token_usage → 11 vs 18).
  - **Columns missing from alembic head**: `users.is_superadmin`; `messages.is_fallback`; `tenants.owner_psid`, `calendar_token`, `messenger_meta`, `instagram_meta`, `whatsapp_meta`, `training_state`; `conversations.classification/_score/_signals/_at/_by`.
  - **Index drift**: head creates NON-unique `idx_messages_fb_message_id` although its docstring claims "Makes messages.fb_message_id unique"; head's `ix_tenants_owner_id`, `ix_order_items_product_id`, `idx_conversations_tenant_status_lastmsg`, `ix_token_usage_tenant_id/tenant_created` do **not** exist in live; live's `idx_messages_fb_message_id_unique` (partial unique), `idx_orders_customer`, `idx_conversations_customer`, `idx_conversations_tenant_last_msg`, `idx_token_usage_tenant`, admin `idx_*` are not in alembic.
  - `927179233531` uses `postgresql.JSON`/`op.drop_constraint` (PG-only patterns).
- Consequence: a Postgres deployment via `alembic upgrade head` yields a schema the running app cannot use (missing `is_superadmin`/scheduler/admin tables → immediate 500s). Running alembic against the live SQLite DB would fail outright (`op.create_table token_usage` → "table already exists"; no version to stamp from). **Drift is currently invisible because nothing tracks it.**

---

## 5. FK integrity

- 23 FK relationships declared in live DDL (every child table) — good coverage.
- `PRAGMA foreign_key_check` → **no violations** (only users/tenants/products/customers/conversations/messages/token_usage populated; all FK values resolve).
- **But `PRAGMA foreign_keys` is never enabled**: no connect-event listener in `app/database.py`, nothing in lifespan (only `journal_mode`/`busy_timeout`/`synchronous`), verified fresh aiosqlite connection → `foreign_keys=0`. All 23 constraints are **unenforced at runtime**; orphans can be inserted silently (e.g., `messages.conversation_id`, `orders.customer_id`, `token_usage.tenant_id`).

---

## 6. Lifespan migrations & backend.log

- Confirmed live error: `backend.log:129` (2026-09-01 00:48:19) `ERROR [app.main] Startup migration block failed — sqlite3.OperationalError: no such table: main.orders` raised by `app/main.py:113` (`CREATE INDEX IF NOT EXISTS idx_orders_tenant_created ON orders(...)`). The 4 hot-index statements (main.py:113-120) are **not individually try/except-ed** (only the UNIQUE fb index is), so the first failure aborts the rest of the block — the admin-table creation (main.py:131-216) was skipped on that boot.
- Worker error-loop while tables were missing (00:48→00:49:32): repeated `no such table: scheduled_posts` (inline scheduler, 30 s), `no such table: tenants` (silent trainer, 45 s), `no such table: users`, plus "Stuck-publish recovery failed".
- `daemon_backend.py` (edited 00:50, after the current daemon started) now auto-bootstraps before uvicorn (`_db_needs_bootstrap`, lines 66-100) — a real mitigation for the ordering problem, **but** bootstrap failures are swallowed (`capture_output=True`, "bootstrap failed (continuing)") and uvicorn boots anyway → same partial-migration abort can recur.
- Historical boot failures earlier in the log (not DB issues): missing repo `.venv` symlink (`FileNotFoundError … .venv/bin/uvicorn`), `slowapi`/`sqladmin` ModuleNotFoundError, `auth.py` limiter-None AttributeError. The repo `.venv` **still does not exist** — daemon_backend falls back to `/home/z/.venv/bin/uvicorn` (running pid 1887 confirms).

---

## 7. bootstrap_local.py completeness

Imports the full `app.models` registry → `create_all` creates **all 18** model tables. Verified: no model table is missing from the DB. The import list in `bootstrap_local.py:23-26` matches `app/models/__init__.py`. The only schema anomaly (token_usage) is *not* bootstrap's fault — the daemon's lifespan created that table first (ordering). Bootstrap seeds are idempotent and currently correct (2 seeded users + 1 tenant + 3 products; final 5 users includes live test registrations).

---

## 8. Findings

| # | severity | finding |
|---|---|---|
| F1 | **HIGH** | Alembic fully drifted: no `alembic_version` in the DB; head migration chain covers only 11/18 tables and lacks `users.is_superadmin`, `messages.is_fallback`, 6 tenant columns, 5 conversation columns; its fb_message_id index is non-unique despite the docstring. Alembic.ini targets Postgres. Any PG deploy via alembic breaks the app; the live SQLite DB is untracked/invisible to migrations. |
| F2 | **HIGH** | Lifespan migration block aborts on a fresh/empty DB: unguarded `CREATE INDEX … ON orders` (app/main.py:113) raised "no such table: main.orders" (backend.log:129, 00:48:19), skipping the UNIQUE fb_message_id index + admin-table DDL for that boot; workers then error-looped for ~73 s. Mitigated only by daemon_backend's new pre-boot bootstrap, whose own failures are swallowed. |
| F3 | **MEDIUM** | `token_usage` is the only table whose live DDL is not model-derived (raw lifespan SQL): nullable `UUID` PK (NULL insert allowed — verified), nullable token columns, `TIMESTAMP DEFAULT CURRENT_TIMESTAMP`, missing model index `ix_token_usage_tenant_id`. Collides with alembic's `op.create_table` if migrations are ever pointed at this DB. |
| F4 | **MEDIUM** | FK constraints declared (23) but **never enforced** — no `PRAGMA foreign_keys=ON` on any connection (verified `foreign_keys=0` on fresh aiosqlite connections; no event listener in app/database.py). Silent orphan risk on all child tables. |
| F5 | **MEDIUM** | `users.email` nullable with **no UNIQUE constraint** while auth assumes uniqueness (register = racy SELECT-then-INSERT; login `scalar_one_or_none()` → 500 `MultipleResultsFound` if a duplicate ever lands). |
| F6 | **MEDIUM** | 11 exact duplicate index pairs (model `ix_*` + lifespan `idx_*`) + 4 prefix-redundant pairs → ~7 unnecessary indexes on hot tables (messages/orders/conversations/site_users/user_sessions) — pure write amplification. Notably `ip_bans.ip_or_cidr` and `site_users.user_id` each carry BOTH a unique and a non-unique index on the same column. |
| F7 | **LOW** | Task-18 hot indexes + UNIQUE(fb_message_id) are lifespan-only, not model `__table_args__` — bootstrap `create_all` alone would NOT recreate `idx_orders_tenant_created`, `idx_conversations_tenant_last_msg`, `idx_orders_customer`, `idx_conversations_customer`, `idx_messages_fb_message_id_unique`, `idx_token_usage_tenant` (they exist today only because the daemon restarted after bootstrap). |
| F8 | **LOW** | Lifespan pragmas are one-shot on a discarded NullPool connection: `busy_timeout=5000` holds only because aiosqlite's Python default is also 5000 ms (lucky coincidence); `synchronous=NORMAL` never sticks (connections stay FULL). Correct fix is a connect-event listener. |
| F9 | **INFO** | admin_audit_log live PK is `INTEGER … PRIMARY KEY(id)` (rowid alias — auto-assign verified) without `AUTOINCREMENT`; functionally correct, only max-rowid-reuse semantics differ from Task-19's description. |
| F10 | **INFO** | DB is being live-written during the audit (users 2→5, messages 0→6, token_usage 0→3 by other agents' E2E tests); integrity_check ok, no FK violations, no duplicate emails at final pass. Row counts in any report are a snapshot. |

**Positive results (verified, not findings):** all 18 model tables exist; 17/18 tables byte-match the canonical create_all schema (columns, types, nullability, defaults, constraints); WAL active; all Task-18/19 artifacts present in the live DB; seed rows valid; FK check clean; bootstrap covers the full model registry; daemon healthy (pid 1887, login/test-chat/trainer working, real LLM calls logged).

---

## 9. Suggested fixes (NOT implemented — error-finding only)

1. **F1:** regenerate alembic from current models (`alembic revision --autogenerate` squash) and `alembic stamp head` on the SQLite DB, or formally retire alembic for local SQLite and document create_all+lifespan as the schema source; align `alembic.ini` URL.
2. **F2/F8:** wrap each index DDL in `app/main.py` in try/except (or move the whole block after a `Base.metadata.create_all` call in lifespan); move pragmas to a `@event.listens_for(engine.sync_engine, "connect")` hook that sets `PRAGMA busy_timeout=5000; PRAGMA foreign_keys=ON; PRAGMA synchronous=NORMAL` per connection.
3. **F3:** rebuild `token_usage` from the model while it's empty (drop + create_all), and delete the divergent raw DDL from lifespan.
4. **F5:** `email: Mapped[str] = mapped_column(String(255), unique=True, index=True)` + dedup migration.
5. **F6/F7:** drop the redundant lifespan `idx_*` statements that duplicate model `ix_*`, and move the surviving hot indexes (`idx_orders_tenant_created`, `idx_conversations_tenant_last_msg`, `idx_orders_customer`, `idx_conversations_customer`, `idx_messages_fb_message_id_unique`, `idx_token_usage_tenant`) into model `__table_args__` so bootstrap recreates them; add a one-time `DROP INDEX IF EXISTS` cleanup for the 11 duplicates.
