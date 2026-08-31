import { NextRequest, NextResponse } from "next/server";
import { fetchWithHeal } from "@/lib/backend-health";

/**
 * PUBLIC calendar subscription route — /api/calendar/{token}
 *
 * Calendar apps (Google Calendar "From URL", Apple Calendar webcal://,
 * Outlook) can't authenticate with cookies, so the per-tenant calendar
 * token in the path IS the auth. The Next.js BFF proxies to the FastAPI
 * backend's /api/calendar/{token}/calendar.ics feed.
 */

const BACKEND_URL =
  process.env.ZEMEST_BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ token: string }> }
) {
  const { token } = await params;

  if (!token || token.length > 128 || !/^[A-Za-z0-9_-]+$/.test(token)) {
    return new NextResponse("Invalid calendar token", { status: 404 });
  }

  try {
    const res = await fetchWithHeal(`${BACKEND_URL}/api/calendar/${token}/calendar.ics`, {
      cache: "no-store",
    });

    if (!res.ok) {
      return new NextResponse("Invalid calendar token", { status: res.status });
    }

    const body = await res.text();
    return new NextResponse(body, {
      status: 200,
      headers: {
        "Content-Type": "text/calendar; charset=utf-8",
        "Content-Disposition": 'inline; filename="zemest-schedule.ics"',
        "Cache-Control": "no-store",
      },
    });
  } catch {
    return new NextResponse("Calendar unavailable — try again in a moment", { status: 502 });
  }
}
