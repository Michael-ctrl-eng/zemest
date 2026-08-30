"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  MessageSquare,
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
} from "lucide-react";
import { MobileSidebar } from "@/components/site/mobile-sidebar";

const sidebarItems = [
  { label: "Overview", href: "", icon: LayoutDashboard },
  { label: "Chat", href: "/chat", icon: MessageSquare },
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

export default function TenantLayout({ children, params }: { children: React.ReactNode; params: { tenantId: string } }) {
  const pathname = usePathname();
  const basePath = `/dashboard/${params.tenantId}`;

  return (
    <div className="min-h-screen bg-grain">
      <Navbar />
      <div className="flex pt-[140px]">
        {/* Sidebar */}
        <aside className="sticky top-[140px] h-[calc(100vh-140px)] w-56 shrink-0 border-r-[3px] border-[var(--tavus-terminal-black)] bg-white overflow-y-auto scrollbar-thin hidden md:block">
          <div className="p-4">
            <Link
              href="/dashboard"
              className="inline-flex items-center gap-1 text-[10px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)] hover:text-[var(--tavus-terminal-black)] mb-4"
            >
              <ArrowLeft className="w-3 h-3" />
              ALL BUSINESSES
            </Link>
            <nav className="space-y-1">
              {sidebarItems.map((item) => {
                const fullPath = `${basePath}${item.href}`;
                const isActive = pathname === fullPath;
                return (
                  <Link
                    key={item.label}
                    href={fullPath}
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
          {children}
        </main>
      </div>

      {/* Mobile sidebar drawer */}
      <MobileSidebar tenantId={params.tenantId} />
    </div>
  );
}

function Navbar() {
  return (
    <div className="fixed top-0 inset-x-0 z-50">
      <div className="bg-[var(--tavus-bubbletech-1)] border-b-[3px] border-[var(--tavus-terminal-black)] py-2.5">
        <div className="mx-auto max-w-[1400px] px-4 flex items-center justify-center text-center">
          <p className="text-[13px] font-semibold text-[var(--tavus-terminal-black)]">
            <span className="font-bold">Rabbit v1 is now live:</span> Arabic moderation with every accent.{" "}
            <a href="/models" className="font-bold underline">Learn more.</a>
          </p>
        </div>
      </div>
      <div className="bg-white border-b-[3px] border-[var(--tavus-terminal-black)]">
        <div className="mx-auto max-w-[1400px] px-4 h-14 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2">
            <span className="font-extrabold tracking-[0.04em] text-[var(--tavus-terminal-black)] text-lg">ZEMEST</span>
          </Link>
          <Link
            href="/get-started"
            className="inline-flex items-center px-4 h-9 border-[3px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-bubbletech-4)] text-[11px] font-extrabold tracking-wider uppercase"
          >
            LOGOUT
          </Link>
        </div>
      </div>
    </div>
  );
}
