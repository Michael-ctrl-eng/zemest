#!/usr/bin/env python3
"""Nightly SQLite snapshot via VACUUM INTO (G2 research → implemented).

Why not `cp`: the DB runs in WAL mode — a plain file copy of `zemest_local.db`
silently produces a stale/corrupt snapshot because recent committed data
lives in the `-wal` file. `VACUUM INTO` goes through the SQLite API and
writes a clean, self-contained, integrity-checked snapshot.

Restores survive sandbox resets: backups land in /home/z/my-project/backups/
(OUTSIDE repos/ so workspace resets don't take them).

Usage:
  python3 scripts/backup_db.py            # snapshot now + prune old ones
  python3 scripts/backup_db.py --keep 30  # keep last 30 snapshots

Restore:
  sqlite3 zemest_local.db ".restore <backup file>"   # or just copy the
  snapshot over the live file while the daemon is STOPPED.
"""
from __future__ import annotations

import argparse
import os
import re
import sqlite3
import sys
import time
from datetime import datetime, timezone

DB = "/home/z/my-project/repos/zemest/zemest_local.db"
BACKUP_DIR = "/home/z/my-project/backups"
NAME_RE = re.compile(r"^zemest-(\d{8}-\d{6})\.db$")


def snapshot(db_path: str, backup_dir: str) -> str:
    if not os.path.exists(db_path):
        print(f"SKIP: {db_path} does not exist")
        sys.exit(0)
    os.makedirs(backup_dir, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    dest = os.path.join(backup_dir, f"zemest-{stamp}.db")
    if os.path.exists(dest):
        print(f"SKIP: {dest} already exists")
        sys.exit(0)

    con = sqlite3.connect(db_path)
    try:
        con.execute("PRAGMA wal_checkpoint(PASSIVE)")  # fold WAL in first
        con.execute("VACUUM INTO ?", (dest,))
    finally:
        con.close()

    # Verify the snapshot is a valid, complete database.
    vcon = sqlite3.connect(f"file:{dest}?mode=ro", uri=True)
    try:
        ok = vcon.execute("PRAGMA integrity_check").fetchone()[0]
        tables = vcon.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
        ).fetchone()[0]
    finally:
        vcon.close()
    if ok != "ok":
        print(f"FAILED integrity check — removing {dest}")
        os.remove(dest)
        sys.exit(1)

    size = os.path.getsize(dest)
    print(f"OK: {dest} ({size / 1024:.0f} KB, {tables} tables, integrity ok)")
    return dest


def prune(backup_dir: str, keep: int) -> None:
    if not os.path.isdir(backup_dir):
        return
    snaps = sorted(
        f for f in os.listdir(backup_dir) if NAME_RE.match(f)
    )
    for old in snaps[:-keep] if len(snaps) > keep else []:
        os.remove(os.path.join(backup_dir, old))
        print(f"pruned {old}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", type=int, default=14, help="snapshots to retain")
    ap.add_argument("--db", default=DB, help="live database path")
    ap.add_argument("--dir", default=BACKUP_DIR, help="backup directory")
    args = ap.parse_args()
    snapshot(args.db, args.dir)
    prune(args.dir, args.keep)
    # Optional watchdog: if a healthchecks.io ping URL is configured, tell it
    # this run succeeded (silent-failure alerting, G2 finding #4).
    ping = os.environ.get("BACKUP_HEALTHCHECK_URL")
    if ping:
        try:
            import urllib.request

            urllib.request.urlopen(ping, timeout=10).read()
        except Exception as e:  # non-fatal
            print(f"healthcheck ping failed: {e}")


if __name__ == "__main__":
    main()
