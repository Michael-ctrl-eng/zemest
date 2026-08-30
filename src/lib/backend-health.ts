import { execFile } from "child_process";
import { promisify } from "util";

/**
 * Self-healing backend guard (server-only).
 *
 * The FastAPI backend runs as a daemon inside this sandbox. If the sandbox
 * ever restarts, the daemon dies and every sign-in shows "network error".
 * Instead of failing, the BFF calls ensureBackend() on a connection error:
 * it starts the daemon (single-flight, race-safe) and waits for it to answer.
 */

const execFileAsync = promisify(execFile);

const REPO = "/home/z/my-project/repos/zemest";
const HEALTH_TIMEOUT_MS = 1_500;
const BOOT_TIMEOUT_MS = 20_000;

const BACKEND_URL =
  process.env.ZEMEST_BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

let healing: Promise<boolean> | null = null;

async function ping(): Promise<boolean> {
  try {
    const res = await fetch(`${BACKEND_URL}/`, {
      signal: AbortSignal.timeout(HEALTH_TIMEOUT_MS),
      cache: "no-store",
    });
    return res.ok;
  } catch {
    return false;
  }
}

/** Start the daemon once (concurrent callers share one boot promise). */
export function ensureBackend(): Promise<boolean> {
  if (!healing) {
    healing = (async () => {
      if (await ping()) return true;
      try {
        // daemon_backend.py start — double-forks and returns immediately
        await execFileAsync(`${REPO}/.venv/bin/python3`, [`${REPO}/daemon_backend.py`, "start"], {
          cwd: REPO,
          timeout: 15_000,
        });
      } catch {
        // fall through to the polling loop — it may already be booting
      }
      const deadline = Date.now() + BOOT_TIMEOUT_MS;
      while (Date.now() < deadline) {
        await new Promise((r) => setTimeout(r, 500));
        if (await ping()) return true;
      }
      return false;
    })().finally(() => {
      healing = null;
    });
  }
  return healing;
}

/** Run a fetch against the backend; on a network error, heal once and retry. */
export async function fetchWithHeal(
  path: string,
  init: RequestInit,
  maxAttempts = 2,
): Promise<Response> {
  let lastErr: unknown = null;
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    try {
      return await fetch(path, init);
    } catch (e) {
      lastErr = e;
      const healed = await ensureBackend();
      if (!healed) break;
    }
  }
  throw lastErr ?? new Error("backend unreachable");
}
