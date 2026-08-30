import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { email, password, remember } = body;

    // Call backend
    const res = await fetch(`${BACKEND_URL}/api/auth/login`, {
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

    // Set httpOnly cookies (BFF pattern — JWT never exposed to JS)
    const response = NextResponse.json({ success: true });
    const maxAge = remember ? 30 * 24 * 60 * 60 : 24 * 60 * 60; // 30 days or 24 hours

    response.cookies.set("zemest_auth", access_token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      maxAge,
      path: "/",
    });

    if (refresh_token) {
      response.cookies.set("zemest_refresh", refresh_token, {
        httpOnly: true,
        secure: process.env.NODE_ENV === "production",
        sameSite: "lax",
        maxAge: 7 * 24 * 60 * 60, // 7 days
        path: "/",
      });
    }

    return response;
  } catch {
    return NextResponse.json({ detail: "Network error — check your connection" }, { status: 500 });
  }
}
