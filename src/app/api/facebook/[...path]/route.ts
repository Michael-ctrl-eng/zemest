import { NextRequest, NextResponse } from "next/server";
import { fetchWithHeal } from "@/lib/backend-health";

/**
 * BFF proxy for the backend's `/api/facebook/*` routes.
 *
 * The load-bearing route here is `GET /api/facebook/oauth/callback` — the
 * browser lands on it AFTER the Meta consent redirect, so it must be
 * reachable from the public origin. In the production edge routing
 * (deploy/Caddyfile.prod) browser `/api/*` traffic is sent to THIS Next
 * server, not to the FastAPI replicas — without this catch-all the OAuth
 * flow would dead-end at a 404 (the original A4-M2 bug, resurrected by
 * the edge split).
 *
 * Same security contract as the `/api/zemest/*` catch-all:
 *  - Cookie → Bearer translation (no tokens in the browser)
 *  - hop-by-hop header stripping
 *  - client-supplied forwarding headers removed (rate-limit spoofing)
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
  // Strip empty segments (edge proxies can append trailing slashes —
  // FastAPI would 307 and bounce back through here).
  const cleanPath = path.filter((seg) => seg !== "");
  const target = `${BACKEND_URL}/api/facebook/${cleanPath.join("/")}`;
  const url = new URL(request.url);

  const headers = new Headers();
  request.headers.forEach((value, key) => {
    if (!HOP_BY_HOP.has(key.toLowerCase())) {
      headers.set(key, value);
    }
  });

  // Cookie → Bearer (authenticated facebook routes, e.g. /pages)
  const authCookie = request.cookies.get("zemest_auth")?.value;
  if (authCookie) {
    headers.set("Authorization", `Bearer ${authCookie}`);
  }
  headers.delete("cookie");

  headers.delete("x-forwarded-for");
  headers.delete("x-real-ip");
  headers.delete("x-forwarded-host");

  const init: RequestInit = {
    method: request.method,
    headers,
    redirect: "manual",
  };

  if (!["GET", "HEAD"].includes(request.method)) {
    init.body = await request.arrayBuffer();
  }

  try {
    const res = await fetchWithHeal(`${target}${url.search}`, init);
    const respHeaders = new Headers();
    res.headers.forEach((value, key) => {
      if (!HOP_BY_HOP.has(key.toLowerCase()) && key.toLowerCase() !== "set-cookie") {
        respHeaders.set(key, value);
      }
    });
    respHeaders.set("Cache-Control", "no-store");
    return new NextResponse(res.body, {
      status: res.status,
      statusText: res.statusText,
      headers: respHeaders,
    });
  } catch (e) {
    console.error("[BFF facebook proxy] backend unreachable:", e);
    return NextResponse.json(
      { ok: false, error: "The server is reconnecting — the Facebook request didn't reach it. Try again now." },
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
