import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  // React Compiler (stable 1.0) — auto-memoization via Turbopack's built-in
  // Babel. Verified top-level key in next 16.1.3 types (config-shared.d.ts).
  reactCompiler: true,
  // The space-z.ai preview edge proxy force-redirects some paths to a
  // trailing-slash form (301 /dashboard -> /dashboard/). Next's default
  // behavior strips the slash (308 /dashboard/ -> /dashboard), which ping-pongs
  // into ERR_TOO_MANY_REDIRECTS. Serving BOTH forms directly kills the loop.
  skipTrailingSlashRedirect: true,
  typescript: {
    ignoreBuildErrors: true,
  },
  reactStrictMode: false,
  images: {
    formats: ["image/avif", "image/webp"],
    remotePatterns: [
      { protocol: "https", hostname: "cdn.prod.website-files.com" },
      { protocol: "https", hostname: "cdn.jsdelivr.net" },
    ],
  },
};

export default nextConfig;
