"use client";

import { use, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  LayoutDashboard,
  MessageSquare,
  Radio,
  Package,
  ShoppingCart,
  Users,
  MessagesSquare,
  Globe,
  Palette,
  Calendar,
  BarChart3,
  Settings,
  ArrowLeft,
  LogOut,
  Loader2,
} from "lucide-react";
import { MobileSidebar } from "@/components/site/mobile-sidebar";

const sidebarItems = [
  { label: "Overview", href: "", icon: LayoutDashboard },
  { label: "Chat", href: "/chat", icon: MessageSquare },
  { label: "Channels", href: "/channels", icon: Radio },
  { label: "Products", href: "/products", icon: Package },
  { label: "Orders", href: "/orders", icon: ShoppingCart },
  { label: "Customers", href: "/customers", icon: Users },
  { label: "Conversations", href: "/conversations", icon: MessagesSquare },
  { label: "Crawl & Knowledge", href: "/crawl", icon: Globe },
  { label: "Style Learning", href: "/style", icon: Palette },
  { label: "Scheduler", href: "/scheduler", icon: Calendar },
  { label: "Insights", href: "/insights", icon: BarChart3 },
  { label: "Settings", href: "/settings", icon: Settings },
];

export default function TenantLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ tenantId: string }>;
}) {
  const { tenantId } = use(params);
  const pathname = usePathname();
  const router = useRouter();
  const [loggingOut, setLoggingOut] = useState(false);
  const basePath = `/dashboard/${tenantId}`;

  async function logout() {
    setLoggingOut(true);
    try {
      await fetch("/api/auth/logout", { method: "POST" });
    } catch {
      /* cookie cleared best-effort */
    }
    router.push("/");
    router.refresh();
  }

  return (
    <div className="min-h-screen bg-grain">
      <Navbar onLogout={logout} loggingOut={loggingOut} />
      <div className="flex pt-[140px]">
        {/* Sidebar */}
        <aside className="sticky top-[140px] h-[calc(100vh-140px)] w-64 shrink-0 border-r-[3px] border-[var(--tavus-terminal-black)] bg-white overflow-y-auto scrollbar-thin hidden md:block">
          <div className="absolute inset-0 bg-halftone-light opacity-30 pointer-events-none" />
          <div className="relative p-5">
            <Link
              href="/dashboard"
              className="inline-flex items-center gap-1.5 text-[10px] font-extrabold tracking-[0.14em] uppercase text-[var(--tavus-hardware-gray-8)] hover:text-[var(--tavus-terminal-black)] mb-5"
            >
              <ArrowLeft className="w-3 h-3" strokeWidth={2.5} />
              All businesses
            </Link>
            <div className="mb-5 h-0 border-t-[2px] border-dashed border-[var(--tavus-terminal-black)]/20" />
            <nav className="space-y-1">
              {sidebarItems.map((item) => {
                const fullPath = `${basePath}${item.href}`;
                const isActive = pathname === fullPath;
                return (
                  <Link
                    key={item.label}
                    href={fullPath}
                    className={`group flex items-center gap-3 px-3.5 py-3 border-[2px] text-[13px] font-bold transition-all ${
                      isActive
                        ? "border-[var(--tavus-terminal-black)] bg-[var(--tavus-bubbletech-4)] text-[var(--tavus-terminal-black)] shadow-[3px_3px_0_0_var(--tavus-terminal-black)]"
                        : "border-transparent text-[var(--tavus-terminal-black)] hover:bg-[var(--tavus-plastic-2)] hover:border-[var(--tavus-terminal-black)]/25 hover:shadow-[2px_2px_0_0_var(--tavus-terminal-black)]/60"
                    }`}
                  >
                    <item.icon className="w-4 h-4 shrink-0" strokeWidth={2.25} />
                    <span className="truncate">{item.label}</span>
                    {isActive ? (
                      <span className="ml-auto w-1.5 h-1.5 bg-[var(--tavus-terminal-black)]" aria-hidden />
                    ) : null}
                  </Link>
                );
              })}
            </nav>
            <div className="mt-6 pt-5 border-t-[2px] border-dashed border-[var(--tavus-terminal-black)]/20">
              <button
                onClick={logout}
                disabled={loggingOut}
                className="flex w-full items-center gap-3 px-3.5 py-3 border-[2px] border-transparent text-[13px] font-bold text-[var(--tavus-terminal-black)] hover:bg-[var(--tavus-coral-3)]/50 hover:border-[var(--tavus-terminal-black)]/25 transition-all disabled:opacity-50"
              >
                {loggingOut ? (
                  <Loader2 className="w-4 h-4 shrink-0 animate-spin" strokeWidth={2.25} />
                ) : (
                  <LogOut className="w-4 h-4 shrink-0" strokeWidth={2.25} />
                )}
                <span>Log out</span>
              </button>
            </div>
          </div>
        </aside>

        {/* Main content */}
        <main className="relative flex-1 min-w-0 px-5 py-7 sm:px-8 sm:py-9">{children}</main>
      </div>

      {/* Mobile sidebar drawer */}
      <MobileSidebar tenantId={tenantId} />
    </div>
  );
}

function Navbar({ onLogout, loggingOut }: { onLogout: () => void; loggingOut: boolean }) {
  return (
    <div className="fixed top-0 inset-x-0 z-50">
      <div className="bg-[var(--tavus-bubbletech-1)] border-b-[3px] border-[var(--tavus-terminal-black)] py-2.5">
        <div className="mx-auto max-w-[1400px] px-4 flex items-center justify-center text-center">
          <p className="text-[13px] font-semibold text-[var(--tavus-terminal-black)]">
            <span className="font-bold">Rabbit v1 is now live:</span> Arabic moderation with every accent —
            live on your channels.{" "}
            <Link href="/models" className="font-bold underline hover:no-underline">
              Learn more.
            </Link>
          </p>
        </div>
      </div>
      <div className="bg-white border-b-[3px] border-[var(--tavus-terminal-black)]">
        <div className="mx-auto max-w-[1400px] px-4 h-16 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2.5">
            <span className="font-extrabold tracking-[0.04em] text-[var(--tavus-terminal-black)] text-lg">
              ZEMEST
            </span>
            <span className="hidden sm:inline-block px-2 py-0.5 text-[9px] font-extrabold tracking-[0.14em] uppercase border-[2px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-atomic-glow-5)]">
              Console
            </span>
          </Link>
          <div className="flex items-center gap-3">
            <Link
              href="/"
              className="hidden sm:inline-flex items-center px-4 h-9 border-[2.5px] border-[var(--tavus-terminal-black)] bg-white text-[11px] font-extrabold tracking-[0.1em] uppercase text-[var(--tavus-terminal-black)] shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:shadow-[4px_4px_0_0_var(--tavus-terminal-black)] hover:-translate-y-0.5 transition-all"
            >
              Website
            </Link>
            <button
              onClick={onLogout}
              disabled={loggingOut}
              className="inline-flex items-center gap-2 px-4 h-9 border-[2.5px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-coral-1)] text-[11px] font-extrabold tracking-[0.1em] uppercase text-white shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:shadow-[4px_4px_0_0_var(--tavus-terminal-black)] hover:-translate-y-0.5 transition-all disabled:opacity-50"
            >
              {loggingOut ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : null}
              Log out
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
