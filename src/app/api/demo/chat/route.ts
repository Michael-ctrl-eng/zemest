import { NextRequest, NextResponse } from "next/server";
import { fetchWithHeal } from "@/lib/backend-health";

/**
 * Public BFF proxy for the landing-page demo agent: /api/demo/chat.
 *
 * NO auth cookie required — this is the marketing "Talk to Agent" widget.
 * The backend replies come from a pure-Python rule matcher (no LLM, no cost),
 * and the backend rate-limits per IP (30 msg/min) so it can't be abused.
 * If the backend daemon is down, it is auto-restarted once and the request
 * retried — so the widget never shows a dead end.
 */

const BACKEND_URL =
  process.env.ZEMEST_BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function POST(request: NextRequest) {
  try {
    const body = await request.text();
    const res = await fetchWithHeal(`${BACKEND_URL}/api/demo/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        // forward client IP so slowapi limits per-visitor, not per-proxy
        "X-Forwarded-For": request.headers.get("x-forwarded-for") || "",
        "X-Real-IP": request.headers.get("x-real-ip") || "",
      },
      body,
      cache: "no-store",
      signal: AbortSignal.timeout(15_000),
    });

    const text = await res.text();
    return new NextResponse(text, {
      status: res.status,
      headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
    });
  } catch {
    return NextResponse.json(
      { reply: "Hmm, the shop went quiet for a second — please try again! 🙏", quick_replies: [] },
      { status: 502 }
    );
  }
}
