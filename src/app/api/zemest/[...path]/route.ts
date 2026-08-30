import { NextRequest, NextResponse } from "next/server";
import { fetchWithHeal } from "@/lib/backend-health";

/**
 * Universal BFF proxy: /api/zemest/* → FastAPI backend.
 *
 * - Reads the httpOnly `zemest_auth` cookie and forwards it as an
 *   `Authorization: Bearer` header (the backend is HTTPBearer-only).
 * - Same-origin from the browser → no CORS needed at all.
 * - The backend URL is configurable via ZEMEST_BACKEND_URL.
 */

const BACKEND_URL =
  process.env.ZEMEST_BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const HOP_BY_HOP = new Set([
  "connection",
  "keep-alive",
  "transfer-encoding",
  "upgrade",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "host",
  "content-length",
  "cookie",
]);

async function proxy(request: NextRequest, path: string[]) {
  // The preview edge proxy can append trailing slashes; strip empties so the
  // backend URL is never /api/x/ (FastAPI would 307 and loop through the BFF).
  const cleanPath = path.filter((seg) => seg !== "");
  const target = `${BACKEND_URL}/api/${cleanPath.join("/")}`;
  const url = new URL(request.url);

  const headers = new Headers();
  request.headers.forEach((value, key) => {
    if (!HOP_BY_HOP.has(key.toLowerCase())) {
      headers.set(key, value);
    }
  });

  // Cookie → Bearer (the security-critical wiring that was missing)
  const authCookie = request.cookies.get("zemest_auth")?.value;
  if (authCookie) {
    headers.set("Authorization", `Bearer ${authCookie}`);
  }
  headers.delete("cookie");

  const init: RequestInit = {
    method: request.method,
    headers,
    redirect: "manual",
  };

  if (!["GET", "HEAD"].includes(request.method)) {
    init.body = await request.arrayBuffer();
  }

  try {
    // Network error → auto-restart the backend daemon once, then retry
    const res = await fetchWithHeal(`${target}${url.search}`, init);
    const respHeaders = new Headers();
    res.headers.forEach((value, key) => {
      if (!HOP_BY_HOP.has(key.toLowerCase()) && key.toLowerCase() !== "set-cookie") {
        respHeaders.set(key, value);
      }
    });
    // Never cache API responses at the edge
    respHeaders.set("Cache-Control", "no-store");
    return new NextResponse(res.body, {
      status: res.status,
      statusText: res.statusText,
      headers: respHeaders,
    });
  } catch (e) {
    console.error("[BFF proxy] backend unreachable:", e);
    return NextResponse.json(
      { detail: "The server woke up for a second — please try again, it responds instantly now." },
      { status: 502 }
    );
  }
}

export async function GET(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params;
  return proxy(request, path);
}
export async function POST(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params;
  return proxy(request, path);
}
export async function PATCH(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params;
  return proxy(request, path);
}
export async function PUT(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params;
  return proxy(request, path);
}
export async function DELETE(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params;
  return proxy(request, path);
}
