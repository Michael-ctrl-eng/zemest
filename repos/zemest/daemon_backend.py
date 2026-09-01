#!/usr/bin/env python3
"""Start/stop the zemest FastAPI backend as a double-fork daemon on :8000.
Usage:
  .venv/bin/python daemon_backend.py start|stop|restart|status
"""
import os
import secrets
import shutil
import signal
import subprocess
import sys
import time

REPO = "/home/z/my-project/repos/zemest"
PIDFILE = os.path.join(REPO, "backend.pid")
LOG = os.path.join(REPO, "backend.log")
SECRET_FILE = os.path.join(REPO, ".jwt_secret")  # gitignored, stable across restarts


def _persistent_jwt_secret() -> str:
    """Return a random secret, generated once and persisted (not committed).

    A stable secret keeps issued tokens valid across daemon restarts while
    never shipping the compiled-in default (forgeable-tokens hole).
    """
    try:
        existing = open(SECRET_FILE).read().strip()
        if len(existing) >= 32:
            return existing
    except OSError:
        pass
    fresh = secrets.token_urlsafe(48)
    with open(SECRET_FILE, "w") as f:
        f.write(fresh)
    try:
        os.chmod(SECRET_FILE, 0o600)
    except OSError:
        pass
    return fresh


ENV = {
    **os.environ,
    "DATABASE_URL": "sqlite+aiosqlite:///./zemest_local.db",
    "JWT_SECRET_KEY": _persistent_jwt_secret(),
    # No Redis in the sandbox: skip the ~1s startup probe + rate-limiter wait.
    "REDIS_URL": "",
}


def read_pid():
    try:
        return int(open(PIDFILE).read().strip())
    except Exception:
        return None


def alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _db_needs_bootstrap() -> bool:
    """True when the local SQLite DB is missing or lacks the users table."""
    import sqlite3
    db_path = os.path.join(REPO, "zemest_local.db")
    if not os.path.exists(db_path):
        return True
    try:
        con = sqlite3.connect(db_path)
        row = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
        ).fetchone()
        con.close()
        return row is None
    except Exception:
        return True


def start():
    pid = read_pid()
    if pid and alive(pid):
        print(f"already running (pid {pid})")
        return
    # Auto-bootstrap: sandbox resets can wipe the SQLite file. If the schema
    # is gone, recreate tables + demo accounts BEFORE booting uvicorn so the
    # platform never comes up 500ing on every endpoint.
    if _db_needs_bootstrap():
        print("db missing/empty — running bootstrap_local.py ...")
        try:
            proc = subprocess.run(
                [sys.executable, "bootstrap_local.py"],
                cwd=REPO, env=ENV, capture_output=True, timeout=180,
            )
            if proc.returncode != 0:
                # Surface the failure — a swallowed bootstrap error boots a
                # backend that 500s on every request (bit us once already).
                print(f"bootstrap FAILED (exit {proc.returncode}):")
                print(proc.stderr.decode()[-800:] if proc.stderr else "(no stderr)")
            else:
                print("bootstrap done")
        except Exception as e:
            print(f"bootstrap failed (continuing): {e}")
    pid = os.fork()
    if pid == 0:
        os.setsid()
        if os.fork() == 0:
            os.chdir(REPO)
            os.umask(0)
            with open(LOG, "ab", 0) as f:
                os.dup2(f.fileno(), 1)
                os.dup2(f.fileno(), 2)
            devnull = os.open(os.devnull, os.O_RDONLY)
            os.dup2(devnull, 0)
            # Prefer repo venv; fall back to any uvicorn on PATH (survives venv wipes)
            uv = os.path.join(REPO, ".venv", "bin", "uvicorn")
            if not os.path.exists(uv):
                uv = shutil.which("uvicorn") or "/home/z/.venv/bin/uvicorn"
            os.execve(uv,
                      [uv, "app.main:app", "--host", "0.0.0.0", "--port", "8000"], ENV)
        os._exit(0)
    os.waitpid(pid, 0)
    # find the daemon pid
    for _ in range(20):
        time.sleep(0.3)
        out = subprocess.run(["pgrep", "-f", "uvicorn app.main:app"], capture_output=True, text=True).stdout.strip()
        if out:
            open(PIDFILE, "w").write(out.splitlines()[-1])
            print(f"started (pid {out.splitlines()[-1]})")
            return
    print("started (pid unknown)")


def stop():
    pid = read_pid()
    if pid and alive(pid):
        os.kill(pid, signal.SIGTERM)
        for _ in range(15):
            time.sleep(0.3)
            if not alive(pid):
                break
        if alive(pid):
            os.kill(pid, signal.SIGKILL)
        print(f"stopped (pid {pid})")
    else:
        subprocess.run(["pkill", "-f", "uvicorn app.main:app"], capture_output=True)
        print("stopped (pkill fallback)")
    try:
        os.remove(PIDFILE)
    except OSError:
        pass


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "start":
        start()
    elif cmd == "stop":
        stop()
    elif cmd == "restart":
        stop()
        time.sleep(1)
        start()
    elif cmd == "status":
        pid = read_pid()
        print("running" if pid and alive(pid) else "stopped")
    else:
        print(__doc__)
