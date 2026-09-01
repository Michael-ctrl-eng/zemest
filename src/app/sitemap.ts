import type { MetadataRoute } from "next";
import { posts } from "@/lib/blog-posts";

/**
 * Next.js Metadata Route — serves /sitemap.xml automatically.
 *
 * Marketing + legal + blog routes only. Private areas (/dashboard, /admin,
 * /api) are excluded here AND disallowed in public/robots.txt (G5).
 */
const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "https://zemest.ai";

const now = new Date();

const staticRoutes: { path: string; priority: number; freq: MetadataRoute.Sitemap[number]["changeFrequency"] }[] = [
  { path: "", priority: 1.0, freq: "weekly" },
  { path: "/solutions", priority: 0.9, freq: "monthly" },
  { path: "/solutions/whatsapp", priority: 0.9, freq: "monthly" },
  { path: "/solutions/messenger", priority: 0.9, freq: "monthly" },
  { path: "/solutions/instagram", priority: 0.9, freq: "monthly" },
  { path: "/solutions/inventory", priority: 0.9, freq: "monthly" },
  { path: "/products", priority: 0.9, freq: "monthly" },
  { path: "/models", priority: 0.8, freq: "monthly" },
  { path: "/pricing", priority: 0.9, freq: "monthly" },
  { path: "/blog", priority: 0.9, freq: "daily" },
  { path: "/research", priority: 0.7, freq: "monthly" },
  { path: "/careers", priority: 0.6, freq: "monthly" },
  { path: "/enterprise", priority: 0.8, freq: "monthly" },
  { path: "/partnerships", priority: 0.7, freq: "monthly" },
  { path: "/get-started", priority: 0.8, freq: "monthly" },
  { path: "/book-demo", priority: 0.8, freq: "monthly" },
  { path: "/support", priority: 0.6, freq: "monthly" },
  { path: "/trust", priority: 0.5, freq: "monthly" },
  { path: "/status", priority: 0.4, freq: "daily" },
  { path: "/brand-kit", priority: 0.4, freq: "yearly" },
  { path: "/press-kit", priority: 0.4, freq: "yearly" },
  { path: "/privacy", priority: 0.3, freq: "yearly" },
  { path: "/terms", priority: 0.3, freq: "yearly" },
  { path: "/acceptable-use", priority: 0.3, freq: "yearly" },
  { path: "/dpa", priority: 0.3, freq: "yearly" },
];

export default function sitemap(): MetadataRoute.Sitemap {
  const entries: MetadataRoute.Sitemap = staticRoutes.map((r) => ({
    url: `${SITE_URL}${r.path}`,
    lastModified: now,
    changeFrequency: r.freq,
    priority: r.priority,
  }));

  for (const post of posts) {
    entries.push({
      url: `${SITE_URL}/blog/${post.slug}`,
      lastModified: post.date ? new Date(post.date) : now,
      changeFrequency: "monthly",
      priority: 0.7,
    });
  }

  return entries;
}
