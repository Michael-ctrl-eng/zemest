#!/usr/bin/env python3
"""Start/stop the zemest FastAPI backend as a double-fork daemon on :8000.
Usage:
  .venv/bin/python daemon_backend.py start|stop|restart|status
"""
import os
import signal
import subprocess
import sys
import time

REPO = "/home/z/my-project/repos/zemest"
PIDFILE = os.path.join(REPO, "backend.pid")
LOG = os.path.join(REPO, "backend.log")
ENV = {**os.environ, "DATABASE_URL": "sqlite+aiosqlite:///./zemest_local.db"}


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


def start():
    pid = read_pid()
    if pid and alive(pid):
        print(f"already running (pid {pid})")
        return
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
            os.execve(f"{REPO}/.venv/bin/uvicorn",
                      ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"], ENV)
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
