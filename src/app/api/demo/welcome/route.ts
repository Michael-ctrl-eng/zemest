import { NextRequest, NextResponse } from "next/server";
import { fetchWithHeal } from "@/lib/backend-health";

/**
 * Public BFF proxy: POST /api/demo/welcome -> backend /api/demo/welcome.
 * Returns the location-aware opening message for the "Talk to Agent" widget.
 */

const BACKEND_URL =
  process.env.ZEMEST_BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function POST(request: NextRequest) {
  try {
    const body = await request.text();
    const res = await fetchWithHeal(`${BACKEND_URL}/api/demo/welcome`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
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
      {
        reply: "Hey! 👋 Welcome to Zemest Store.\nWhat are you looking for today?",
        quick_replies: ["White Nike shoes, size 42", "Do you have shampoo?", "How much is shipping?"],
        is_arabic: false,
      },
      { status: 200 }
    );
  }
}
