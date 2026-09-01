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
      // Try every python that can run the daemon — the repo venv can be wiped
      // by sandbox resets while /home/z/.venv (or system python) survives.
      const pyCandidates = [
        `${REPO}/.venv/bin/python3`,
        "/home/z/.venv/bin/python3",
        "python3",
      ];
      for (const py of pyCandidates) {
        try {
          // daemon_backend.py start — double-forks and returns immediately
          await execFileAsync(py, [`${REPO}/daemon_backend.py`, "start"], {
            cwd: REPO,
            timeout: 15_000,
          });
          break;
        } catch {
          // try the next interpreter
        }
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

/** Run a fetch against the backend; on a network error, heal once and retry.
 * A hung backend can never pin the UI: every attempt is bounded by a 30s
 * timeout (was unbounded → infinite spinner on worst-case stalls).
 *
 * DUPLICATE-SAFE RETRY: a timeout on a POST/PATCH/DELETE may mean the
 * request *reached* the backend and only the response was lost — replaying
 * it would double-create orders, messages and scheduled posts. So
 * non-idempotent methods are only retried when the failure is a
 * connection-level error (backend down, request never sent); timeouts
 * surface immediately to the caller. */
const IDEMPOTENT = new Set(["GET", "HEAD", "OPTIONS"]);

function isTimeout(e: unknown): boolean {
  return e instanceof Error && (e.name === "TimeoutError" || e.name === "AbortError");
}

export async function fetchWithHeal(
  path: string,
  init: RequestInit,
  maxAttempts = 2,
): Promise<Response> {
  let lastErr: unknown = null;
  const method = (init.method ?? "GET").toUpperCase();
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    try {
      return await fetch(path, {
        ...init,
        signal: init.signal ?? AbortSignal.timeout(30_000),
      });
    } catch (e) {
      lastErr = e;
      // Non-idempotent request that timed out: the backend may have already
      // applied it. Retrying is not safe — fail fast instead.
      if (!IDEMPOTENT.has(method) && isTimeout(e)) {
        throw e;
      }
      const healed = await ensureBackend();
      if (!healed) break;
    }
  }
  throw lastErr ?? new Error("backend unreachable");
}
