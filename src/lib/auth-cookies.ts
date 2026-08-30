import { NextRequest } from "next/server";

/**
 * Auth-cookie attributes that survive BOTH top-level pages and cross-site
 * iframe embeds (the space-z.ai preview pane renders the app inside an
 * iframe).
 *
 * Why this exists: browsers silently refuse SameSite=Lax cookies in
 * cross-site iframe contexts. Symptom: login POST returns success, the
 * cookie never lands in the jar, /dashboard redirects straight back to
 * /login — the user is "stuck on the login page". The fix is
 * SameSite=None; Secure (+ Partitioned, i.e. CHIPS, so Chrome's
 * third-party-cookie phase-out can't kill it either).
 *
 * SameSite=None REQUIRES Secure, and Secure cookies are rejected on plain
 * HTTP — so we only switch when the request is genuinely HTTPS. The edge
 * proxy in front of this app forwards HTTPS traffic as internal HTTP
 * without a usable x-forwarded-proto, so the trustworthy signal is the
 * browser's own Origin header (present on same-origin fetch POSTs).
 */
export function authCookieAttributes(request: NextRequest) {
  const origin = request.headers.get("origin") ?? "";
  const forwardedProto = (request.headers.get("x-forwarded-proto") ?? "")
    .split(",")[0]
    .trim()
    .toLowerCase();
  const isHttps = origin.startsWith("https://") || forwardedProto === "https";

  return {
    httpOnly: true as const,
    secure: isHttps,
    sameSite: (isHttps ? "none" : "lax") as "lax" | "none",
    ...(isHttps ? { partitioned: true } : {}),
    path: "/",
  };
}
