import { NextRequest, NextResponse } from "next/server";
import { fetchWithHeal } from "@/lib/backend-health";
import { authCookieAttributes } from "@/lib/auth-cookies";

// ZEMEST_BACKEND_URL (runtime, container-friendly) takes precedence over
// NEXT_PUBLIC_API_URL (build-time inlined) — same precedence as the
// /api/zemest catch-all proxy in lib/backend-health.ts.
const BACKEND_URL =
  process.env.ZEMEST_BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { email, password, remember } = body;

    // Self-healing: if the backend daemon died (sandbox restart), revive it and retry
    const res = await fetchWithHeal(`${BACKEND_URL}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });

    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: "Invalid email or password" }));
      return NextResponse.json(error, { status: res.status });
    }

    const data = await res.json();
    const { access_token, refresh_token } = data;

    // Set httpOnly cookies (BFF pattern — JWT never exposed to JS).
    // Attributes adapt to HTTPS/iframe contexts — see auth-cookies.ts.
    const response = NextResponse.json({ success: true });
    const maxAge = remember ? 30 * 24 * 60 * 60 : 24 * 60 * 60; // 30 days or 24 hours

    response.cookies.set("zemest_auth", access_token, {
      ...authCookieAttributes(request),
      maxAge,
    });

    if (refresh_token) {
      response.cookies.set("zemest_refresh", refresh_token, {
        ...authCookieAttributes(request),
        maxAge: 7 * 24 * 60 * 60, // 7 days
      });
    }

    return response;
  } catch {
    return NextResponse.json({ detail: "Network error — check your connection" }, { status: 500 });
  }
}
