/**
 * SKALE Network payout sender — ethers v6.
 *
 * One module, two rails:
 *   - "usdc"   → ERC-20 transfer() on the configured USDC contract (6 decimals)
 *   - "native" → plain value transfer of the chain's native token
 *
 * SKALE Europa specifics:
 *   - EVM-compatible → ethers.JsonRpcProvider works unchanged.
 *   - Gas-free chain: transactions need no gas stipend from us; ethers
 *     still populates a gas limit (the chain ignores pricing).
 *   - Fast finality: the returned tx hash is mined within seconds.
 *
 * Security: the private key lives ONLY in this process (env). Callers
 * authenticate with an HMAC-SHA256 signature over the exact raw request
 * body — see index.js. This module never exposes the key or signs
 * anything except payout transactions it initiated.
 */
import { ethers } from "ethers";

const RPC_URL = process.env.SKALE_RPC_URL || "https://mainnet.skalenodes.com/v1/green-giddoni";
const CHAIN_ID = parseInt(process.env.SKALE_CHAIN_ID || "2046398127", 10);
const PRIVATE_KEY = process.env.SKALE_PAYOUT_PRIVATE_KEY || "";
export const USDC_CONTRACT = process.env.SKALE_USDC_CONTRACT || "";
export const USDC_DECIMALS = parseInt(process.env.SKALE_USDC_DECIMALS || "6", 10);

const ERC20_ABI = [
  "function transfer(address to, uint256 amount) returns (bool)",
  "function balanceOf(address owner) view returns (uint256)",
  "function decimals() view returns (uint8)",
];

let _provider = null;
let _wallet = null;

export function configured() {
  return Boolean(PRIVATE_KEY);
}

export function provider() {
  if (!_provider) {
    _provider = new ethers.JsonRpcProvider(RPC_URL, { chainId: CHAIN_ID, name: "skale" });
  }
  return _provider;
}

export function wallet() {
  if (!_wallet) {
    if (!PRIVATE_KEY) {
      throw new Error("SKALE_PAYOUT_PRIVATE_KEY is not configured");
    }
    _wallet = new ethers.Wallet(PRIVATE_KEY, provider());
  }
  return _wallet;
}

/** Validate a destination address (EIP-55 tolerant, shape-checked). */
export function isValidAddress(address) {
  try {
    return ethers.isAddress(address);
  } catch {
    return false;
  }
}

/**
 * Send one payout. Idempotency: `idempotencyKey` is hashed into the data
 * memo... no — the caller (FastAPI) already dedupes by request id, and the
 * on-chain transfer carries the key in the receipt log via this process's
 * processed-keys journal (index.js). Here we just send.
 *
 * @param {object} params
 * @param {string} params.to        destination wallet (0x…, 42 chars)
 * @param {string} params.amount    decimal string in WHOLE units ("12.50")
 * @param {string} params.token     "usdc" | "native"
 * @returns {Promise<{tx_hash: string, status: string}>}
 */
export async function sendPayout({ to, amount, token }) {
  const w = wallet();

  if (!isValidAddress(to)) {
    throw Object.assign(new Error(`invalid destination address: ${to}`), { statusCode: 400 });
  }
  if (!["usdc", "native"].includes(token)) {
    throw Object.assign(new Error(`unsupported token: ${token}`), { statusCode: 400 });
  }
  const parsed = token === "usdc" ? parseUnitsSafe(amount, USDC_DECIMALS) : ethers.parseEther(amount);
  if (parsed <= 0n) {
    throw Object.assign(new Error("amount must be positive"), { statusCode: 400 });
  }

  let tx;
  if (token === "usdc") {
    if (!USDC_CONTRACT || !ethers.isAddress(USDC_CONTRACT)) {
      throw Object.assign(new Error("SKALE_USDC_CONTRACT is not configured"), { statusCode: 500 });
    }
    const contract = new ethers.Contract(USDC_CONTRACT, ERC20_ABI, w);
    // await the tx being MINED (SKALE finalizes in seconds) — the backend
    // records the hash either way, and the receipt confirms landing.
    tx = await contract.transfer(to, parsed);
  } else {
    tx = await w.sendTransaction({ to, value: parsed });
  }

  const receipt = await tx.wait(1); // 1 confirmation — SKALE fast finality
  return {
    tx_hash: tx.hash,
    status: receipt && receipt.status === 1 ? "sent" : "unknown",
  };
}

/** Wallet balance (native + USDC) for the health endpoint / monitoring. */
export async function balances() {
  const w = wallet();
  const nativeBal = await provider().getBalance(w.address);
  let usdcBal = null;
  if (USDC_CONTRACT) {
    try {
      const contract = new ethers.Contract(USDC_CONTRACT, ERC20_ABI, w);
      const raw = await contract.balanceOf(w.address);
      usdcBal = ethers.formatUnits(raw, USDC_DECIMALS);
    } catch {
      usdcBal = null; // contract not deployed at that address — surfaced as null
    }
  }
  return {
    wallet: w.address,
    native: ethers.formatEther(nativeBal),
    usdc: usdcBal,
  };
}

function parseUnitsSafe(amount, decimals) {
  try {
    const parsed = ethers.parseUnits(String(amount), decimals);
    return parsed;
  } catch (e) {
    throw Object.assign(new Error(`invalid amount: ${amount}`), { statusCode: 400 });
  }
}
