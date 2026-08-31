"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  LayoutDashboard,
  Users,
  Store,
  ShieldBan,
  MonitorPlay,
  ScrollText,
  BarChart3,
  Activity,
  ArrowLeft,
} from "lucide-react";
import { authApi, adminApi, ApiError } from "@/lib/zemest-api";

const sidebarItems = [
  { label: "Dashboard", href: "/admin", icon: LayoutDashboard },
  { label: "Users", href: "/admin/users", icon: Users },
  { label: "Tenants", href: "/admin/tenants", icon: Store },
  { label: "IP Bans", href: "/admin/ip-bans", icon: ShieldBan },
  { label: "Sessions", href: "/admin/sessions", icon: MonitorPlay },
  { label: "Audit Log", href: "/admin/audit-log", icon: ScrollText },
  { label: "Analytics", href: "/admin/analytics", icon: BarChart3 },
  { label: "System Health", href: "/admin/health", icon: Activity },
];

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [allowed, setAllowed] = useState(false);

  // Superadmin gate: /auth/me decides when it reports is_superadmin. Older
  // daemon builds always report false there, so fall back to a real
  // admin-authorized probe (GET /admin/analytics/overview — 200 = superadmin,
  // 403 = everyone else) before allowing the section to render.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const me = await authApi.me();
        if (me?.is_superadmin) {
          if (!cancelled) setAllowed(true);
          return;
        }
        await adminApi.overview();
        if (!cancelled) setAllowed(true);
      } catch (err) {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 401) return; // request() already redirects to /login
        router.replace("/dashboard");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [router]);

  return (
    <div className="min-h-screen bg-grain">
      <Navbar />
      <div className="flex pt-[140px]">
        {/* Sidebar */}
        <aside className="sticky top-[140px] h-[calc(100vh-140px)] w-56 shrink-0 border-r-[3px] border-[var(--tavus-terminal-black)] bg-white overflow-y-auto scrollbar-thin hidden md:block">
          <div className="p-4">
            <Link
              href="/"
              className="inline-flex items-center gap-1 text-[10px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)] hover:text-[var(--tavus-terminal-black)] mb-4"
            >
              <ArrowLeft className="w-3 h-3" />
              BACK TO SITE
            </Link>
            <div className="mb-3 px-1 text-[10px] font-bold tracking-[0.2em] uppercase text-[var(--tavus-hardware-gray-8)]">ADMIN PANEL</div>
            <nav className="space-y-1">
              {sidebarItems.map((item) => {
                const isActive = item.href === "/admin" ? pathname === "/admin" : pathname.startsWith(item.href);
                return (
                  <Link
                    key={item.label}
                    href={item.href}
                    className={`flex items-center gap-2 px-3 py-2.5 border-2 text-sm font-bold transition-all ${
                      isActive
                        ? "border-[var(--tavus-terminal-black)] bg-[var(--tavus-bubbletech-4)] text-[var(--tavus-terminal-black)] shadow-[2px_2px_0_0_var(--tavus-terminal-black)]"
                        : "border-transparent text-[var(--tavus-terminal-black)] hover:bg-[var(--tavus-plastic-2)] hover:border-[var(--tavus-terminal-black)]/20"
                    }`}
                  >
                    <item.icon className="w-4 h-4 shrink-0" strokeWidth={2} />
                    <span>{item.label}</span>
                  </Link>
                );
              })}
            </nav>
          </div>
        </aside>

        {/* Main content */}
        <main className="flex-1 min-w-0 p-5 sm:p-8">
          {allowed ? children : null}
        </main>
      </div>
    </div>
  );
}

function Navbar() {
  return (
    <div className="fixed top-0 inset-x-0 z-50">
      <div className="bg-[var(--tavus-terminal-black)] text-white border-b-[3px] border-[var(--tavus-bubbletech-4)] py-2.5">
        <div className="mx-auto max-w-[1400px] px-4 flex items-center justify-center text-center">
          <p className="text-[13px] font-semibold text-white">
            <span className="font-bold">ADMIN PANEL.</span> Restricted access — superadmins only.
          </p>
        </div>
      </div>
      <div className="bg-white border-b-[3px] border-[var(--tavus-terminal-black)]">
        <div className="mx-auto max-w-[1400px] px-4 h-14 flex items-center justify-between">
          <Link href="/admin" className="flex items-center gap-2">
            <span className="inline-flex items-center justify-center w-7 h-7 border-2 border-[var(--tavus-terminal-black)] bg-[var(--tavus-bubbletech-4)]">
              <ShieldBan className="w-4 h-4" strokeWidth={2} />
            </span>
            <span className="font-extrabold tracking-[0.04em] text-[var(--tavus-terminal-black)] text-lg">ZEMEST</span>
            <span className="text-[10px] font-bold tracking-[0.2em] uppercase text-[var(--tavus-hardware-gray-8)] border-l-2 border-[var(--tavus-terminal-black)] pl-2 ml-1">ADMIN</span>
          </Link>
          <div className="flex items-center gap-3">
            <div className="hidden sm:flex items-center gap-2 px-3 h-9 border-2 border-[var(--tavus-terminal-black)] bg-[var(--tavus-plastic-2)]">
              <span className="w-2 h-2 bg-[var(--tavus-neon-field-2)] border border-[var(--tavus-terminal-black)]" />
              <span className="text-[10px] font-bold tracking-wider uppercase text-[var(--tavus-terminal-black)]">SUPERADMIN</span>
            </div>
            <Link
              href="/"
              className="inline-flex items-center px-4 h-9 border-[3px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-bubbletech-1)] text-[11px] font-extrabold tracking-wider uppercase"
            >
              LOGOUT
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
