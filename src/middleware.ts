import { NextRequest, NextResponse } from "next/server";

// Public routes — no auth required
const publicRoutes = ["/", "/login", "/register", "/get-started", "/forgot-password", "/pricing", "/enterprise", "/research", "/careers", "/blog", "/book-demo", "/partnerships", "/solutions", "/products", "/models", "/privacy", "/terms", "/acceptable-use", "/dpa", "/support", "/trust", "/status", "/brand-kit", "/press-kit"];

// Check if a path is public
function isPublicRoute(pathname: string): boolean {
  // Check exact matches
  if (publicRoutes.includes(pathname)) return true;
  // Check solution sub-routes
  if (pathname.startsWith("/solutions/")) return true;
  // Check static assets
  if (pathname.startsWith("/_next/") || pathname.startsWith("/api/")) return true;
  if (pathname.match(/\.(svg|png|jpg|jpeg|webp|avif|ico|webmanifest)$/)) return true;
  return false;
}

export function middleware(request: NextRequest) {
  const { pathname: rawPathname } = request.nextUrl;
  // With skipTrailingSlashRedirect the raw path may carry a trailing slash —
  // normalize so route matching behaves identically for /dashboard and /dashboard/.
  const pathname = rawPathname !== "/" && rawPathname.endsWith("/") ? rawPathname.slice(0, -1) : rawPathname;

  // Skip public routes
  if (isPublicRoute(pathname)) {
    return NextResponse.next();
  }

  // Protected routes: /dashboard/*, /admin/*
  const isProtected = pathname.startsWith("/dashboard") || pathname.startsWith("/admin");
  if (!isProtected) {
    return NextResponse.next();
  }

  // Check for auth cookie (httpOnly cookie set by BFF route)
  // In production, this checks the JWT cookie
  const authCookie = request.cookies.get("zemest_auth") || request.cookies.get("sb-access-token");

  if (!authCookie) {
    // Redirect to login with return URL
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("redirect", pathname);
    return NextResponse.redirect(loginUrl);
  }

  // Admin routes require superadmin
  if (pathname.startsWith("/admin")) {
    // In production, decode the JWT and check is_superadmin
    // For now, allow if cookie exists — real check happens client-side
    // via GET /api/auth/me
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
