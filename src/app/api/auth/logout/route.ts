import { NextResponse } from "next/server";

export async function POST() {
  const response = NextResponse.json({ success: true });

  // Clear auth cookies
  response.cookies.delete("zemest_auth");
  response.cookies.delete("zemest_refresh");

  return response;
}
