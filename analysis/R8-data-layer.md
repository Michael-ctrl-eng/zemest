# R8 — Data Layer Evolution Research (vector store, Arabic search, ORM, dataset versioning)

**Agent:** R8 (github-research) · **Date:** 2026-09-01 (fresh re-verification run) · **Scope:** /home/z/my-project (zemest backend + platform)
**Method:** GitHub search API in batched `repo:` queries (6 calls — core /repos was exhausted on the shared IP; numbers cross-checked via releases.atom + raw.githubusercontent, which are free), **plus empirical verification in this sandbox**: SQLite 3.53.1 / Python 3.12.14 (uv venv), SQLAlchemy 2.0.36 + aiosqlite 0.20.0 (the backend's exact stack), sqlite-vec 0.1.9 installed into an isolated `/tmp` target (project venv untouched). No project code modified, no git commands.

---

## 1. Ground truth — the data layer today (re-verified this run)

| Fact | Evidence |
|---|---|
| Backend DB = one SQLite file, WAL ON | `repos/zemest/zemest_local.db` (~405 KB, **18 tables**, `journal_mode=wal`), aiosqlite async driver; `app/database.py` already branches: SQLite → default engine, else Postgres pool (pool_size 20, pre_ping) |
| Alembic drifted, unused at runtime | 3 revisions (`5179285ae0ae` → `927179233531` → `a89fe0001`); **11 `create_table` calls total vs 18 live tables** (matches E8's 11/18); **no `alembic_version` table in the live DB**; alembic.ini's sync URL works, but head ≠ reality |
| **No vector store, no FTS anywhere** | zero matches for `embedding\|vector\|cosine\|fts5\|vec0\|pgvector` across `repos/zemest/app/`; `knowledge_bases` table exists but is empty; retrieval = `app/knowledge/retriever.py` LLM-navigated PageIndex tree (TOC → node pick, `SMALL_TREE_MAX_NODES=14` bypass, 10-min selection cache) |
| Prisma on the Next.js side = **dead scaffold** | `/home/z/my-project/prisma/schema.prisma` = untouched User/Post demo template; `src/lib/db.ts` exports PrismaClient but **zero imports of `lib/db` in `src/`**; `package.json` still carries `@prisma/client ^6.11.1` + `db:push/generate/migrate/reset` scripts (pure weight) |
| Arabic NLP already present (pre-search layer) | `app/ai/language_engine.py` (camel-tools/fasttext dialect ID), `app/ai/arabizi_map.py` (Arabizi→Arabic), python-Levenshtein fuzzy |
| Stack pins | requirements.txt: `sqlalchemy[asyncio]==2.0.36`, `aiosqlite==0.20.0`, `alembic==1.14.1`, `asyncpg==0.30.0`, `psycopg2-binary==2.9.11` (Postgres drivers already declared → prod path is real) |

---

## 2. Empirical verification (executed in this sandbox, not read from docs)

1. **sqlite-vec v0.1.9 runs here** (`pip install --target /tmp/r8-vec sqlite-vec`, ~15 KB wheel): `vec_version()` → v0.1.9; plain KNN ✓; **tenant-filtered KNN** (`WHERE embedding MATCH ? AND tenant_id = ? AND k = 1`) ✓ — multi-tenancy via vec0 metadata columns, no app-level filtering needed.
2. **sqlite-vec under the backend's exact stack — verified end-to-end**: SQLAlchemy 2.0.36 `create_async_engine("sqlite+aiosqlite:///…")` + `event.listens_for(engine.sync_engine, "connect")` loading the extension through the aiosqlite adapter (`dbapi_conn.await_(inner.load_extension(...))`) → async `text()` KNN with metadata filter returned correct rows through pooled connections (sketch in §3.1).
3. **FTS5 + trigram tokenizer present** in sandbox SQLite 3.53.1 (`CREATE VIRTUAL TABLE … USING fts5(x)` / `tokenize='trigram'` both OK; `enable_load_extension` available).
4. **Arabic behavior of stock FTS5 unicode61 (measured)**:
   - Diacritics handled: query `أهلا` matched `أهلاً` ✓
   - Hamza/alef variants **not** unified (`اهلا` ✗ `أهلا`); `ة/ه`, `ى/ي` not unified; article `ال` + clitics (`للـ`,`و`,`بـ`) not stripped (`قاهرة` ✗ `للقاهره`, `متجر` ✗ `المتجر`)
   - Prefix queries work (`متجر*` ✓); **trigram tokenizer enables substring/typo tolerance** (`رياض` → `رياضي` ✓)
   - A **12-line Python pre-normalizer** (NFKC → strip diacritics+tatweel → `أإآٱ→ا` → `ة→ه` → `ى→ي`) verified: `أهلاً`↔`اهلا` now match; article/clitics still need `*` prefix terms or light stemming
5. **Live DB**: 18 tables, 0 FTS/vec virtual tables, WAL, `alembic_version` absent, `PRAGMA foreign_keys` off on fresh connections (E8's FK finding reproduced).

---

## 3. Ranked picks (max 5)

### #1 — sqlite-vec — vector search inside the SQLite file you already run
- **URL:** https://github.com/asg017/sqlite-vec
- **Stars:** 8,062 · **Last push:** 2026-05-18 (release v0.1.9 same day; v0.1.10-alpha.4 2026-04-01; **pre-v1, README warns "expect breaking changes"**) · **License:** Apache-2.0 (C, zero deps)
- **SQLite-compat:** 100% — it *is* a loadable SQLite extension (float/int8/binary vectors; metadata + auxiliary + partition-key columns); runs Linux/macOS/Windows/WASM. Backed by Mozilla Builders / Turso / Fly.io / SQLite Cloud sponsorships.
- **Caveats:** brute-force KNN (no ANN index in 0.1.x — fine ≤ ~50–100K vectors/tenant); fixed dimension per vec0 table; SQLite single-writer (already mitigated: WAL + busy_timeout); 3.5-month gap since last push (author is solo — the classic asg017 cadence).
- **Integration sketch (verified this run):**
  ```python
  # app/database.py — attach extension + pragmas to every pooled connection
  import sqlite_vec
  from sqlalchemy import event

  @event.listens_for(engine.sync_engine, "connect")
  def _sqlite_extras(dbapi_conn, rec):        # AsyncAdapt_aiosqlite_connection
      inner = getattr(dbapi_conn, "_connection", None)
      if inner is None: return                # plain sqlite3 (alembic/tests)
      dbapi_conn.await_(inner.enable_load_extension(True))
      dbapi_conn.await_(inner.load_extension(sqlite_vec.loadable_path()))
      dbapi_conn.await_(inner.enable_load_extension(False))
      dbapi_conn.await_(inner.execute("PRAGMA foreign_keys=ON"))   # closes E8 FK gap
      dbapi_conn.await_(inner.execute("PRAGMA busy_timeout=5000"))
  ```
  ```sql
  CREATE VIRTUAL TABLE kb_chunks_vec USING vec0(
    embedding float[768],   -- dimension locked to chosen embed model
    tenant_id integer,      -- filtered KNN (verified)
    chunk_id  text          -- auxiliary column
  );
  -- hybrid keyword+vector in ONE query, ONE database:
  SELECT f.rowid, f.text_ar, bm25(kb_fts) AS kw, v.distance
  FROM kb_fts f JOIN kb_chunks_vec v ON v.rowid = f.rowid
  WHERE kb_fts MATCH :q AND v.tenant_id = :tid
  ORDER BY kw LIMIT :k;
  ```
- **Verdict:** **ADOPT.** Zero new services, zero new stores, transactional with relational tenant data, and verified working under the exact backend stack today. Embeddings via the existing OpenAI-compatible gateway (llm_gateway) or a local multilingual sentence-transformers; normalize Arabizi→Arabic first (`arabizi_map.py` exists).

### #2 — SQLite FTS5 + Arabic pre-normalizer — Arabic keyword search, no new infra
- **URL:** https://sqlite.org/fts5.html (SQLite core, public domain — present in sandbox 3.53.1). In-repo reference: https://github.com/yshalsager/sqlite-tokenizer-ar (1★, pushed 2026-08-29, license unspecified — "native FTS5 tokenizer + helpers for Arabic", a Lucene ArabicAnalyzer port; explicitly experimental).
- **SQLite-compat:** 100% — `unicode61` and `trigram` verified working here. Postgres parity = `tsvector` + GIN with the `simple` config (Postgres has no Arabic stemmer) fed by the **same Python normalizer** → one code path across the migration.
- **Integration sketch (normalizer verified this run):**
  ```python
  def ar_norm(t: str) -> str:
      t = unicodedata.normalize("NFKC", t)
      t = re.sub(r"[\u064B-\u065F\u0670\u0640]", "", t)  # diacritics + tatweel
      t = re.sub("[أإآٱ]", "ا", t).replace("ة", "ه").replace("ى", "ي")
      t = re.sub(r"[^\w\u0600-\u06FF ]", " ", t)
      return re.sub(r"\s+", " ", t).strip().lower()
  ```
  Store raw + normalized columns; index normalized. Query side: same normalizer + `*` prefix terms for article/clitic variants (`قاهره*`, `للقاهره`→`قاهره*`); trigram table as typo-tolerant fallback; `sqlite-tokenizer-ar` later if Lucene-grade analysis is needed (park — 1★, no license file).
- **Verdict:** **ADOPT.** The only Arabic search path with zero dependencies that is verified in this sandbox; composes with #1 into hybrid retrieval in a single file. Keep the PageIndex tree as a top-level router (it already handles the ≤14-node case), use FTS5+vec for chunk-level recall.

### #3 — pgvector — the Postgres side of the same design (prod target)
- **URL:** https://github.com/pgvector/pgvector
- **Stars:** 22,839 · **Last push:** 2026-08-20 · **Release:** v0.8.6 (2026-07-29) · **License:** PostgreSQL License (permissive; spdx shows NOASSERTION) · exceptionally few open issues (~14)
- **SQLite-compat:** n/a (Postgres extension) — that's the point: `docker-compose.yml` already declares PostgreSQL 16 for prod, `asyncpg` + `psycopg2-binary` already pinned.
- **Integration sketch:** `CREATE EXTENSION vector;` → `embedding vector(768)` + `USING hnsw (embedding vector_cosine_ops)`; official SQLAlchemy type `pgvector.sqlalchemy.Vector`; dual-dialect via `with_variant()`/dialect-guarded alembic ops. FTS parity: `to_tsvector('simple', ar_norm(text))` + GIN — same normalizer as #2.
- **Verdict:** **ADOPT for prod.** Same "one database = relational + vectors + FTS" philosophy; the SQLite↔Postgres swap becomes a config change plus dialect-guarded migrations, not a rewrite.

### #4 — drizzle-orm vs Prisma — verdict for the Next.js side
- **URL:** https://github.com/drizzle-team/drizzle-orm
- **Stars:** 35,644 · **Last push:** 2026-08-31 · **Release:** v1.0.0-rc.4 (2026-06-27, approaching 1.0) · **License:** Apache-2.0
- **SQLite-compat:** first-class (better-sqlite3, libsql/Turso, bun:sqlite, Cloudflare D1) + Postgres/MySQL + edge runtimes; 0 deps, tiny runtime; `drizzle-kit` generates SQL migrations; Drizzle Studio for browsing.
- **Prisma comparison (measured, for THIS repo):** upstream is now **prisma/orm** (repo renamed from prisma/prisma; 47,581★, pushed 2026-08-31, Apache-2.0, v8.0.0-rc era) — a fine product, **but here it is dead weight**: schema.prisma is the untouched demo template, `lib/db.ts` is imported by nothing, and the FastAPI/SQLAlchemy backend owns all real data (the BFF just proxies). Prisma would add a Rust query-engine binary + a second migration system over either nothing or someone else's SQLite file. (Repo pins `@prisma/client ^6.11.1` while upstream is at v8-rc — another sign nobody touches it.)
- **Integration sketch (only if a Next-side store ever appears — BFF cache, UI prefs, analytics rollups):**
  ```ts
  // src/lib/db.ts (replacement)
  import { drizzle } from "drizzle-orm/bun-sqlite"; // or better-sqlite3
  export const nextDb = drizzle("zemest_next.db");
  // Postgres day: drizzle-orm/node-postgres with the same schema.ts
  ```
- **Verdict:** **Prisma: REMOVE the scaffold + scripts + dep (or leave dormant — never build on it). Drizzle: the pick if/when the Next.js side needs its own tables** — it mirrors the backend's "SQLite today, Postgres tomorrow" story at near-zero runtime weight. Source of truth stays in FastAPI/SQLAlchemy.

### #5 — DVC (treeverse/dvc, formerly iterative/dvc) — versioning the training corpus
- **URL:** https://github.com/treeverse/dvc (org renamed; `iterative/dvc` now resolves here)
- **Stars:** 15,853 · **Last push:** 2026-08-31 · **Release:** 3.67.1 (2026-03-31) · **License:** Apache-2.0
- **SQLite-compat:** orthogonal (manages files, not DBs) — works fully offline in this sandbox.
- **Integration sketch:** silent-trainer / style-learner exports, crawled corpora, and prompt eval sets become tracked artifacts:
  ```bash
  dvc init && dvc add data/style-train.jsonl data/crawl-corpus/
  dvc remote add -d localstore /home/z/my-project/dvc-storage   # → S3 in prod
  git tag style-2026-09-01        # git = code lineage, dvc = data lineage
  # dvc.yaml pipeline: export → embed → eval; `dvc repro` regenerates + diffs metrics
  ```
- **Verdict:** **ADOPT when the trainer corpus becomes a real dataset** (reproducible fine-tuning/eval per R4's LoRA plan). Until exports exceed a few MB, `git add` of JSONL suffices; DVC pays off with `dvc repro` pipelines + metrics diffing. Cheap to start now (pure pip, offline, no daemon).

---

## 4. Also-rans (researched, verified, not picked)

| Tool | Observed data | Why not for zemest now |
|---|---|---|
| **qdrant/qdrant** | 34,299★ · pushed 2026-08-31 · v1.19.0 (2026-08-04) · Apache-2.0 · Rust | Excellent filtered/quantized/sparse-hybrid search at scale — but a **separate server + store**: breaks "SQLite file in sandbox today", splits the tenant's source of truth. Escape hatch > ~1M vectors or multi-node HA. |
| **chroma-core/chroma** | 29,192★ · pushed 2026-09-01 · 1.5.9 (2026-05-05) + rolling "Latest" · Apache-2.0 | Fastest RAG demo API (embedded or server) but owns its storage directory (duplicating the DB), opinionated defaults, Rust core dep, no Postgres story. sqlite-vec gives the same "embedded" win inside the existing DB. |
| **lancedb/lancedb** | 11,321★ · pushed 2026-09-01 · v0.38.0 · Apache-2.0 | Strongest single-binary alternative: embedded columnar (Lance) + ANN + Tantivy FTS + SQL filters + versioning/time-travel. Not picked only because sqlite-vec+FTS5 reuses the existing DB and its transactions; keep as the escape hatch if vec0 brute force becomes the bottleneck. |
| **prisma/orm** | 47,581★ · pushed 2026-08-31 · v8.0.0-rc · Apache-2.0 | Great product, wrong fit here — see #4. |
| **yshalsager/sqlite-tokenizer-ar** | 1★ · pushed 2026-08-29 · license unspecified | Interesting (Lucene ArabicAnalyzer as FTS5 C tokenizer: normalization + stopwords + light stemming) but self-declared experimental — future upgrade behind the Python normalizer. |
| **asg017/sqlite-lembed / sqlite-rembed** | 262★ / 153★ · both last pushed 2024 | Generate embeddings *in SQL* (GGUF via llama.cpp / remote APIs). Stale ~2 years; useful only as pattern references for experiments. |

Supporting cast (already in the stack, both healthy — no replacement warranted): **sqlalchemy** 12,122★ · MIT · 2.1.0rc1/2.0.52 · pushed 2026-08-31; **alembic** 4,358★ · MIT · 1.19.1 (repo pins 1.14.1 — safe to bump) · pushed 2026-08-14.

---

## 5. Comparison table (observed 2026-09-01; GitHub search API + atom cross-check)

| Tool | Role | Stars | Last push | License | Runs in sandbox TODAY | Postgres-prod path | Arabic fit | Embedding storage |
|---|---|---|---|---|---|---|---|---|
| **sqlite-vec** | vector KNN in SQLite | 8,062 | 2026-05-18 | Apache-2.0 | ✅ **verified** (SQLAlchemy-async stack) | swap to pgvector | embed normalized text | float/int8/binary, fixed dim, metadata cols |
| **SQLite FTS5** | Arabic keyword search | (SQLite core 3.53.1) | — | Public domain | ✅ **verified** (unicode61+trigram) | tsvector+GIN 'simple' | ⚠ needs 12-line normalizer (verified) | n/a |
| **pgvector** | vectors in Postgres | 22,839 | 2026-08-20 | PostgreSQL Lic. | n/a (prod DB) | ✅ native | same normalizer | vector(768)+HNSW |
| **drizzle-orm** | Next.js ORM | 35,644 | 2026-08-31 | Apache-2.0 | ✅ (SQLite drivers) | ✅ | n/a | n/a |
| **DVC (treeverse/dvc)** | dataset versioning | 15,853 | 2026-08-31 | Apache-2.0 | ✅ offline | n/a | n/a | n/a (files) |
| lancedb | embedded lakehouse | 11,321 | 2026-09-01 | Apache-2.0 | ✅ (pip) | n/a (own format) | Tantivy FTS + normalize | columnar Lance + ANN |
| qdrant | vector DB server | 34,299 | 2026-08-31 | Apache-2.0 | ⚠ embedded mode only | n/a (standalone) | embed normalized | payload filters, quantization |
| chroma | embedded RAG store | 29,192 | 2026-09-01 | Apache-2.0 | ✅ | n/a (own format) | embed normalized | own dir |
| prisma/orm | Node ORM | 47,581 | 2026-08-31 | Apache-2.0 | ✅ but **unused here** | ✅ | n/a | n/a |

---

## 6. Recommended migration path (SQLite → Postgres)

**Phase 0 — now, in-sandbox, one SQLite file (all verified above):**
1. `pip install sqlite-vec` (+ pin `sqlite-vec==0.1.9`); add the connect-event loader (§3.1) with `PRAGMA foreign_keys=ON` + `busy_timeout` — fixes E8's FK-enforcement gap for free.
2. New alembic revision (dialect-guarded): `vec0` virtual table (`embedding float[768], tenant_id, chunk_id`) + FTS5 table (`text_ar_norm`, `text_raw`) + app-level dual-write (or triggers) to keep FTS in sync. Use `render_as_batch=True` for future SQLite ALTERs.
3. **Fix the drift first or in the same pass**: regenerate a consolidated `create_all`-equivalent revision (E8: head covers 11/18 tables, no `alembic_version` in the live DB) — otherwise every later migration compounds the drift.
4. Embedding source: existing OpenAI-compatible gateway (llm_gateway), fallback local `sentence-transformers` multilingual-e5-small (Arabic-capable); normalize Arabizi→Arabic (`arabizi_map.py`) then `ar_norm()`; store model + dim per row.
5. New `retrieve_hybrid(db, tenant_id, query)`: `ar_norm` + prefix terms → FTS5 bm25 top-k; embed query → vec0 tenant-filtered KNN top-k; RRF merge; **keep** PageIndex tree navigation as router (≤14-node bypass already exists).
6. Optional now: `dvc init` on trainer exports (cheap, offline).

**Phase 1 — same code, flag-flipped to prod:**
7. Postgres 16 (already in docker-compose) + `CREATE EXTENSION vector`; alembic dialect guard adds `vector(768)` + HNSW(cosine) + GIN tsvector('simple'). SQLAlchemy: `with_variant(Vector(768), "postgresql")` over the packed-blob column; hybrid query switches operators (`embedding <=> :q ORDER BY … LIMIT k` ↔ `MATCH … AND k =`).
8. Backfill by re-embedding the corpus through the same Python path (deterministic normalizer; dataset pinned via DVC tag).

**Phase 2 — scale escape hatches (only if triggered):**
9. vec0 brute force too slow / > ~100K vectors per tenant → LanceDB (embedded, files-not-servers) or Qdrant (server, filtered+quantized+sparse hybrid) behind the same `retrieve_hybrid` seam — keep that function dialect-agnostic from day one.

**Alembic/SQLAlchemy 2 pattern notes (repo-specific):** keep the sync-URL migrations (already correct); move idempotent runtime DDL out of `daemon_backend.py` into numbered revisions; PRAGMAs via engine events, never scattered scripts; one revision per schema change, data migrations separate from DDL; run `alembic upgrade head` in CI against a throwaway SQLite file so drift can never silently regrow.

---

## 7. Bottom line

- **#1 + #2 together**: sqlite-vec + FTS5 + a 12-line Arabic normalizer give zemest hybrid (keyword + vector) Arabic search **inside the existing ~400 KB SQLite file with zero new services — verified end-to-end in this sandbox today**, including under the backend's exact SQLAlchemy-async stack and with tenant-filtered KNN.
- **#3 pgvector** is the prod counterpart — same design, dialect-guarded alembic, no rewrite; asyncpg already pinned.
- **#4**: delete/ignore the dead Prisma scaffold (upstream renamed to prisma/orm, now v8-rc — repo still pins unused ^6.11.1); Drizzle if the Next.js side ever owns tables.
- **#5 DVC** (org renamed iterative→treeverse) once the silent-trainer corpus becomes a training dataset.
- Bonus: FK enforcement rides along with the connect-event listener; sqlite-lembed/rembed are pattern references only (stale since 2024).

*Data notes: stars/push dates captured 2026-09-01 via GitHub search API in batched `repo:` queries (core /repos 0/60 on shared IP, reset ~02:21 UTC) and cross-checked against releases.atom feeds; prisma/prisma→prisma/orm and iterative/dvc→treeverse/dvc are live renames (old paths no longer resolve in search). This run re-verified every empirical claim independently (isolated /tmp install; live DB opened read-only).*
