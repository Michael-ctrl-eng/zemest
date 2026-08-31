"""Diagnose why the new columns did not land in zemest_local.db."""
import asyncio
import sqlite3

from sqlalchemy import text

REPO = "/home/z/my-project/repos/zemest"


async def main():
    import os, sys
    sys.path.insert(0, REPO)
    os.chdir(REPO)
    os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./zemest_local.db"  # force-override shell junk

    from app.database import engine

    stmts = [
        ("tenants", "training_state", "JSON"),
        ("conversations", "classification", "VARCHAR(20)"),
        ("conversations", "classification_score", "FLOAT"),
        ("conversations", "classification_signals", "JSON"),
        ("conversations", "classified_at", "TIMESTAMP"),
        ("conversations", "classified_by", "VARCHAR(16)"),
    ]
    async with engine.begin() as conn:
        for table, col, coltype in stmts:
            try:
                await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {coltype}"))
                print(f"OK    {table}.{col}")
            except Exception as e:
                print(f"FAIL  {table}.{col}: {type(e).__name__}: {e}")
    await engine.dispose()

    db = sqlite3.connect(f"{REPO}/zemest_local.db")
    cols = [r[1] for r in db.execute("PRAGMA table_info(conversations)")]
    print("conversations cols now:", cols)


asyncio.run(main())
