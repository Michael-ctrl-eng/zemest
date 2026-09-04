/**
 * Zemest SKALE payout sidecar — HTTP service (zero framework deps: node:http).
 *
 * Endpoints:
 *   GET  /health        → wallet address, balances, chain id (no auth —
 *                         bound to the internal docker network / localhost)
 *   POST /payout        → send USDC or native token. AUTHENTICATED:
 *                         X-Signature = hex(HMAC-SHA256(rawBody, SECRET))
 *
 * Idempotency: every successful POST /payout stores its idempotency_key in
 * .data/processed-keys.json (append-only journal). A replayed key returns
 * the ORIGINAL result — a double-spend via request replay is impossible.
 *
 * Env contract (see .env.example):
 *   PORT=4010
 *   SKALE_PAYOUT_HMAC_SECRET=<same value as backend SKALE_PAYOUT_HMAC_SECRET>
 *   SKALE_RPC_URL, SKALE_CHAIN_ID, SKALE_USDC_CONTRACT, SKALE_PAYOUT_PRIVATE_KEY
 */
import http from "node:http";
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { configured, balances, sendPayout, isValidAddress } from "./skale.js";

const PORT = parseInt(process.env.PORT || "4010", 10);
const SECRET = process.env.SKALE_PAYOUT_HMAC_SECRET || "";
const DATA_DIR = path.join(path.dirname(fileURLToPath(import.meta.url)), ".data");
const KEYS_FILE = path.join(DATA_DIR, "processed-keys.json");

// --------------------------------------------------------------------------- //
// Idempotency journal (key → {tx_hash, status, ts})
// --------------------------------------------------------------------------- //
function loadJournal() {
  try {
    return JSON.parse(fs.readFileSync(KEYS_FILE, "utf-8"));
  } catch {
    return {};
  }
}

function saveJournal(journal) {
  fs.mkdirSync(DATA_DIR, { recursive: true });
  fs.writeFileSync(KEYS_FILE, JSON.stringify(journal, null, 2), { mode: 0o600 });
}

// --------------------------------------------------------------------------- //
// HMAC auth — constant-time compare over the RAW request body
// --------------------------------------------------------------------------- //
function validSignature(rawBody, signature) {
  if (!SECRET || !signature || !rawBody) return false;
  const expected = crypto.createHmac("sha256", SECRET).update(rawBody).digest("hex");
  const a = Buffer.from(expected, "utf-8");
  const b = Buffer.from(signature, "utf-8");
  if (a.length !== b.length) return false;
  return crypto.timingSafeEqual(a, b);
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    let size = 0;
    req.on("data", (chunk) => {
      size += chunk.length;
      if (size > 16 * 1024) {
        reject(Object.assign(new Error("body too large"), { statusCode: 413 }));
        req.destroy();
        return;
      }
      chunks.push(chunk);
    });
    req.on("end", () => resolve(Buffer.concat(chunks)));
    req.on("error", reject);
  });
}

function json(res, code, payload) {
  const body = JSON.stringify(payload);
  res.writeHead(code, {
    "Content-Type": "application/json",
    "Content-Length": Buffer.byteLength(body),
    "Cache-Control": "no-store",
  });
  res.end(body);
}

// --------------------------------------------------------------------------- //
// Server
// --------------------------------------------------------------------------- //
const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://localhost:${PORT}`);

  if (req.method === "GET" && url.pathname === "/health") {
    if (!configured()) {
      return json(res, 503, { ok: false, error: "SKALE_PAYOUT_PRIVATE_KEY not configured" });
    }
    try {
      const bals = await balances();
      return json(res, 200, {
        ok: true,
        chain: process.env.SKALE_CHAIN_ID || "2046398127",
        rpc: process.env.SKALE_RPC_URL || "",
        ...bals,
      });
    } catch (e) {
      return json(res, 503, { ok: false, error: String(e.message || e) });
    }
  }

  if (req.method === "POST" && url.pathname === "/payout") {
    // Auth first — everything else (even parsing) happens after verification.
    let raw;
    try {
      raw = await readBody(req);
    } catch (e) {
      return json(res, e.statusCode || 400, { error: e.message });
    }
    const signature = req.headers["x-signature"] || "";
    if (!validSignature(raw, signature)) {
      return json(res, 401, { error: "invalid or missing X-Signature" });
    }

    let body;
    try {
      body = JSON.parse(raw.toString("utf-8"));
    } catch {
      return json(res, 400, { error: "malformed JSON" });
    }

    const { to, amount, token = "usdc", idempotency_key } = body;
    if (!idempotency_key) {
      return json(res, 400, { error: "idempotency_key is required" });
    }
    if (!isValidAddress(to)) {
      return json(res, 400, { error: `invalid destination address: ${to}` });
    }

    // Replay protection: a processed key returns the original result.
    const journal = loadJournal();
    if (journal[idempotency_key]) {
      return json(res, 200, { ...journal[idempotency_key], idempotent: true });
    }

    try {
      const result = await sendPayout({ to, amount, token });
      journal[idempotency_key] = { ...result, ts: new Date().toISOString() };
      saveJournal(journal);
      return json(res, 200, result);
    } catch (e) {
      return json(res, e.statusCode || 502, { error: String(e.message || e) });
    }
  }

  return json(res, 404, { error: "not found" });
});

const BIND = process.env.HOST || "127.0.0.1";
server.listen(PORT, BIND, () => {
  // Loopback by default (bare-metal); docker-compose sets HOST=0.0.0.0
  // inside the private compose network (never exposed to the internet).
  console.log(`[skale-payout] listening on ${BIND}:${PORT} (configured=${configured()})`);
});

for (const sig of ["SIGTERM", "SIGINT"]) {
  process.on(sig, () => {
    server.close(() => process.exit(0));
  });
}
