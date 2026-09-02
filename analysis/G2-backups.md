# G2 — SQLite Durability & Backup Tooling Research

**Task ID:** G2 · **Agent:** github-research · **Date:** 2026-09-01 (sandbox clock)

## Context: why this matters for zemest

- The **entire platform state** — tenants, users, chats/conversations, learned
  style profiles, training checkpoints, audit log — lives in **one SQLite file**:
  `repos/zemest/zemest_local.db` (WAL mode: `sqlite+aiosqlite:///./zemest_local.db`,
  run by `daemon_backend.py` as a double-fork daemon on :8000).
- **The sandbox has already wiped this DB twice** (workspace resets). There is
  currently **zero backup tooling** — no `VACUUM INTO`, no cron, no replication.
- Live check today: `zemest_local.db` = 400 KB but `zemest_local.db-wal` = 185 KB —
  **~a third of recent data sits in the WAL, not the main file**. A naive
  `cp zemest_local.db <backup>` (or rsync of just the `.db`) silently produces a
  **stale/corrupt backup**. Any backup path must be WAL-aware.
- Sandbox constraints: **no S3, no Redis, no external services** — the solution
  must work with local file ops + Python stdlib *today*, and scale to S3 when
  prod lands (Postgres is planned later, but SQLite is the *current* state).
- venv SQLite version: **3.53.1** (way past 3.27) → `VACUUM INTO`,
  `Connection.backup()`, Online Backup API all fully supported.

---

## Method

GitHub API (repo lookups via `search/repositories` with `repo:` qualifiers after
hitting the unauthenticated rate limit; raw.githubusercontent.com for READMEs).
10 repos evaluated; top 5 ranked below. Data as of sandbox date 2026-09-01.
Verified locally: live `VACUUM INTO` against the WAL-active production DB —
result: `PRAGMA integrity_check = ok`, all 18 tables, 409,600-byte clean copy
(wal frames included, WAL untouched).

---

## #1 — sqlite3 `VACUUM INTO` + Python `sqlite3.Connection.backup()` (stdlib)

| Field | Value |
|---|---|
| URL | https://github.com/sqlite/sqlite (official mirror) |
| Stars | 10,386 |
| Last push | 2026-08-31 (daily upstream drops) |
| License | Public domain (mirror `NOASSERTION`; SQLite is public-domain) |
| Language | C (Python `sqlite3` / `aiosqlite` expose it) |
| Footprint | **0 dependencies, 0 external processes** |

**What it solves.** `VACUUM INTO '/path/backup.db'` (SQLite ≥ 3.27, 2019)
produces a **transactionally consistent, compacted snapshot** of the database
through the SQLite API — it reads through the live WAL, so the copy always
includes committed-but-not-checkpointed transactions. It never takes an
exclusive lock for the whole run (writers can proceed), and it works on a DB
being served by the daemon. Alternative in stdlib: `Connection.backup(dst)`
(Online Backup API) — same guarantee, page-by-page, also WAL-safe; `VACUUM INTO`
additionally defrags/vacuums the output.

**WAL-safety.** ✅ Native — the snapshot is taken inside a read transaction, so
WAL frames are merged in; result is a standalone `.db` with no `-wal` dependency.
**Verified live in this sandbox today** (see Method).

**Restore story.** Copy the file back, point `DATABASE_URL` at it, restart the
daemon. Zero conversion. Restores are also *portable* across SQLite versions
(forward). One file per snapshot → trivially diffable/git-able (`PRAGMA
page_size` fixed → stable binary layout → `rsync`/restic dedupes snapshots well).

**Integration sketch for the daemon:**
```python
# scripts/backup_db.py — run from cron or daemon loop; no new deps
import sqlite3, os, time, subprocess
SRC = "/home/z/my-project/repos/zemest/zemest_local.db"
ts = time.strftime("%Y%m%d-%H%M%S")
dst = f"/home/z/my-project/backups/zemest-{ts}.db"   # OUTSIDE repos/ — survives repo resets
con = sqlite3.connect(f"file:{SRC}?mode=ro", uri=True)   # read-only handle
con.execute("VACUUM INTO ?", (dst,))
ok = con.execute("PRAGMA quick_check").fetchone()[0]
# verify the *backup*: open dst, quick_check, compare sqlite_master + row counts
con.close()
# retention: keep 7 daily, 4 weekly; rotate by filename
# optional watchdog: curl -fsS --retry 3 https://hc-ping.com/<uuid> on success
```
Nightly + before-risky-ops (migrations via alembic) cadence; rotate with a
3-line loop; encrypt later by feeding the snapshot to restic (see #3).

**Verdict.** **Adopt now — this is the backbone.** Works in the sandbox *today*
with zero external services, 100% WAL-safe, one-step verified restore. The
sandbox's two DB wipes would have cost minutes, not weeks, had this existed.
This is the only option with no moving parts.

---

## #2 — Litestream (benbjohnson/litestream)

| Field | Value |
|---|---|
| URL | https://github.com/benbjohnson/litestream |
| Stars | 14,334 |
| Last push | 2026-08-31 (active) |
| License | Apache-2.0 |
| Language | Go — single static binary (~15–20 MB) or Docker `litestream/litestream` |
| Backends | S3 (+ MinIO/Cloudflare R2/Backblaze B2/Tigris), GCS, Azure, SFTP, local file |

**What it solves.** **Continuous, near-real-time disaster recovery for SQLite**:
runs as a sidecar process, tails the WAL, and ships incremental frames to
object storage every ~1s (sync interval) / 24h compaction. It only talks to
SQLite through the C API — README explicitly states it will not corrupt the DB.
Point-in-time recovery: restore at any LSN/timestamp, so you can rewind past a
bad migration or a tenant-deletion bug. This is the *de-facto* standard for
"SQLite in prod" (used widely incl. by fly.io users).

**WAL-safety.** ✅ Designed around WAL — it owns checkpoint coordination via an
internal `_litestream_lock` table (empty rolled-back transactions; safe, but
note: the DB won't be byte-identical after Litestream touches it, and don't drop
that table while it runs).

**Restore story.** `litestream restore -o restored.db <replica-url>` (or
`litestream restore -timestamp ...` for PITR), then swap the file and restart.
Restores are tested by design (restore-to-temp + integrity check is the
documented drill).

**Caveats.** Needs a WAL-mode DB (✅ ours). **Not usable inside this sandbox**
(no S3 endpoint reachable; local `file://` replica would only help against
*app* corruption, not workspace wipes — though a `file:` replica on a *different
path* would still have survived the resets). Beta status per README badge. RPO
~1s vs nightly VACUUM's 24h. Adds one supervised process.

**Integration sketch (prod):**
```yaml
# /etc/litestream.yml
dbs:
  - path: /data/zemest_local.db
    replicas:
      - url: s3://zemest-backups/zemest
        retention: 720h          # 30d
        snapshot-interval: 24h
```
Run under supervisord/systemd next to FastAPI; app code needs **zero changes**.
Pre-prod: run it in `file:` mode to a second disk/dir as a poor-man's
continuous mirror.

**Verdict.** **Adopt at prod time (S3), keep nightly VACUUM INTO as the
second layer.** They compose perfectly — Litestream gives 1s RPO/PITR,
snapshots give belt-and-braces. Free, Apache-2.0, tiny footprint, actively
maintained. The clear winner for the "Postgres later, SQLite now" interim.

---

## #3 — restic (restic/restic)

| Field | Value |
|---|---|
| URL | https://github.com/restic/restic |
| Stars | 35,805 |
| Last push | 2026-09-01 (very active) |
| License | BSD-2-Clause |
| Language | Go — static binary, also in every distro repo |
| Backends | S3/MinIO/R2/B2, SFTP, local dir, rest-server, rclone remotes |

**What it solves.** Encrypted, deduplicated, incremental **file-level backups
with snapshots** — the standard answer to "my workspace gets wiped." Dedup
means 30 daily SQLite snapshots cost ~1 day + deltas (page-aligned `VACUUM INTO`
output dedupes beautifully). Client-side encryption (AES-256, repo is useless
without key), compression, verify (`restic check`), retention policies
(`--keep-daily 7 --keep-weekly 4`).

**WAL-safety.** ⚠️ **Do NOT point restic at the live `.db` + `-wal` pair** —
file-level copies of a WAL db are only consistent if captured atomically
(together, at rest, after `PRAGMA wal_checkpoint(TRUNCATE)`). Correct pattern:
**restic backs up the `VACUUM INTO` snapshot directory** (already consistent),
never the live files. That combination is safe and dedup-friendly.

**Restore story.** `restic restore latest:/backups --target /` (or `mount` to
browse snapshots), then swap + restart. `restic snapshots` = audit trail.

**Integration sketch:**
```bash
# after backup_db.py drops zemest-*.db into /home/z/my-project/backups:
restic backup /home/z/my-project/backups -r /mnt/backups/zemest-restic \
  --keep-daily 7 --keep-weekly 4 --keep-monthly 6 --prune
restic check --read-data-subset=10%
```
Sandbox: works with a **local-dir repo** (`-r /srv/restic` or an external
mount) — no S3 needed; same config grows to S3 by changing the `-r` URL.

**Verdict.** **Adopt — layer 2, once there is a second storage location**
(attached volume / repo mirror). In-sandbox value is limited (a repo inside the
wiped workspace dies with it), but the tool itself is the best-in-class
35k-star, BSD-2, zero-drama choice; borg (below) is equally capable.

---

## #4 — healthchecks (healthchecks/healthchecks) — cron watchdog

| Field | Value |
|---|---|
| URL | https://github.com/healthchecks/healthchecks |
| Stars | 10,294 |
| Last push | 2026-08-31 (active) |
| License | BSD-3-Clause |
| Language | Python/Django; hosted SaaS at healthchecks.io (free tier) |

**What it solves.** **Silent-backup-failure detection** — the other half of the
problem. A backup that hasn't run in 3 weeks is indistinguishable from no
backup. Pattern: backup script pings `https://hc-ping.com/<uuid>` on success;
the watchdog alerts (email/Slack/Telegram/webhook) when the ping is late, or
when the job pings with `/fail` (non-zero exit). Handles grace periods,
schedules (cron expressions), and "priority" escalation. Self-hostable
(single Django app + Postgres/SQLite) or just use the free hosted SaaS.

**WAL-safety.** N/A — monitoring only (but it's what tells you #1/#2/#3 died).

**Restore story.** N/A. Complements: it also watchdogs the *daemon* itself
(heartbeat from the FastAPI app = dead-man switch for the whole backend).

**Integration sketch:**
```python
# end of backup_db.py
import urllib.request
urllib.request.urlopen("https://hc-ping.com/<uuid>")           # success ping
# on exception: urlopen("https://hc-ping.com/<uuid>/fail")
```
Check = `failed to reach after 26h` (nightly + 2h grace) → alert. Also add
`https://hc-ping.com/<daemon-uuid>` heartbeat from a FastAPI startup+interval
task for process-level monitoring.

**Verdict.** **Adopt (hosted SaaS, zero infra) the moment backups exist.**
Without this, the two layers above are unverified hope. Not needed in-sandbox
(no cron/mail anyway) — but the `hc-ping` curl costs nothing and should ship
*with* the backup script so it's live when deployed.

---

## #5 — superfly/litefs & canonical/dqlite — evaluated honestly: overkill

**LiteFS** — https://github.com/superfly/litefs · 4,870★ · Apache-2.0 · Go ·
pushed 2026-05-11. FUSE filesystem that **replicates SQLite across a cluster of
machines** with primary/replica election via Consul or static config. Solves
*read-scale-out and HA across hosts*, not backup. Requires FUSE + Linux +
multiple nodes; write-forwarding adds latency; candidates-elect-a-primary
coordination is a whole ops surface. **Dqlite** — https://github.com/canonical/dqlite ·
4,368★ · pushed 2026-08-24. Raft-replicated embeddable SQLite (Canonical, drives
LXD/Juju). Requires libdqlite C lib + **replacing your SQLite driver** with
dqlite's Python bindings and a ≥3-node cluster. Neither replicates *off-box
cold storage*, both assume multi-server fleets, and both are ~0 help for
"sandbox wipes a single file". **Verdict: skip** — right tool when zemest is
a multi-region fleet, which it explicitly is not (single daemon, Postgres
planned for the scale-out path instead). Honorable mention:
**stephen/litefs-backup** (34★, streaming backups from LiteFS to S3 —
irrelevant unless LiteFS is adopted).

### Runners-up (not adopted, one line each)
- **kopia** (kopia/kopia · 13,998★ · Apache-2.0) — restic-class, better GUI/
  scheduled-mode, but no clear edge for a headless one-file workload; restic's
  CLI is a better daemon fit.
- **borgbackup/borg** (borgbackup/borg · 13,673★ · BSD) — excellent, but
  requires borg serve/SSH for remote repos and server-side mounts; restic's
  S3-native model maps 1:1 onto the future prod stack.
- **peak/s5cmd** (peak/s5cmd · 4,177★ · MIT · last push 2025-06 — slowed) —
  parallel S3 batch CLI; only useful *after* S3 exists, and Litestream already
  owns S3 upload. Revisit for bulk snapshot *exports* (e.g. monthly offsite
  copies: `s5cmd sync snapshots/ s3://zemest-offsite/`).

---

## Recommended architecture (final)

| Layer | Tool | When | RPO |
|---|---|---|---|
| 1. Snapshot | `VACUUM INTO` nightly (cron/daemon task) → `backups/` **outside repos/** | **now** (sandbox-safe, 0 deps) | ≤24h |
| 2. Continuous | Litestream → S3 (or `file:` to 2nd disk pre-prod) | prod / S3 day | ~1s + PITR |
| 3. Vault | restic → S3/second volume, on snapshots dir | when a 2nd location exists | n/a |
| 4. Watchdog | healthchecks ping in backup script + daemon heartbeat | ship with layer 1 | alert ≤26h |

Also: **one-time quick wins** — (a) `cp` the current DB (all three files) to
`/home/z/my-project/backups/seed-<date>.db` *after* a checkpoint so a
workspace reset never starts from zero; (b) add `backups/` to the reset-surviving
path convention alongside `.jwt_secret`; (c) restore drill: swap file → restart
daemon → hit `/health` (documented in the script header).

**Bottom line:** the missing 30 lines are `backup_db.py` + a cron entry. The
two sandbox wipes made the cost of *not* having them concrete.
