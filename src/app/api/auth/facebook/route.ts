import { NextRequest, NextResponse } from "next/server";
import { fetchWithHeal } from "@/lib/backend-health";
import { authCookieAttributes } from "@/lib/auth-cookies";

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Facebook OAuth login
// POST /api/auth/facebook with { fb_access_token }
// Calls backend POST /api/auth/facebook
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { fb_access_token } = body;

    if (!fb_access_token) {
      // Redirect to Facebook OAuth
      const fbClientId = process.env.NEXT_PUBLIC_FB_APP_ID;
      const redirectUri = `${request.nextUrl.origin}/api/auth/facebook/callback`;
      const fbAuthUrl = `https://www.facebook.com/v18.0/dialog/oauth?client_id=${fbClientId}&redirect_uri=${redirectUri}&scope=email&response_type=code`;
      return NextResponse.redirect(fbAuthUrl);
    }

    // Self-healing: if the backend daemon died (sandbox restart), revive it and retry
    const res = await fetchWithHeal(`${BACKEND_URL}/api/auth/facebook`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ fb_access_token }),
    });

    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: "Facebook login failed" }));
      return NextResponse.json(error, { status: res.status });
    }

    const data = await res.json();
    const { access_token, refresh_token } = data;

    const response = NextResponse.json({ success: true });
    response.cookies.set("zemest_auth", access_token, {
      ...authCookieAttributes(request),
      maxAge: 24 * 60 * 60,
    });

    if (refresh_token) {
      response.cookies.set("zemest_refresh", refresh_token, {
        ...authCookieAttributes(request),
        maxAge: 7 * 24 * 60 * 60,
      });
    }

    return response;
  } catch {
    return NextResponse.json({ detail: "Network error — check your connection" }, { status: 500 });
  }
}

// GET handler — redirects to Facebook OAuth dialog
export async function GET(request: NextRequest) {
  const fbClientId = process.env.NEXT_PUBLIC_FB_APP_ID || "demo_client_id";
  const redirectUri = `${request.nextUrl.origin}/api/auth/facebook/callback`;
  const fbAuthUrl = `https://www.facebook.com/v18.0/dialog/oauth?client_id=${fbClientId}&redirect_uri=${redirectUri}&scope=email&response_type=code`;
  return NextResponse.redirect(fbAuthUrl);
}
