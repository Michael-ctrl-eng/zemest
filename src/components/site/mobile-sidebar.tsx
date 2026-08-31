"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
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
  Menu,
  X,
  ArrowLeft,
} from "lucide-react";

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

export function MobileSidebar({ tenantId }: { tenantId: string }) {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();
  const basePath = `/dashboard/${tenantId}`;

  return (
    <>
      {/* Mobile toggle button */}
      <button
        onClick={() => setOpen(true)}
        className="md:hidden fixed bottom-4 right-4 z-50 w-12 h-12 border-[3px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-bubbletech-4)] shadow-[3px_3px_0_0_var(--tavus-terminal-black)] flex items-center justify-center active:translate-x-1 active:translate-y-1 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] transition-all"
        aria-label="Open navigation"
      >
        <Menu className="w-5 h-5" />
      </button>

      {/* Drawer */}
      <AnimatePresence>
        {open && (
          <>
            {/* Backdrop */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setOpen(false)}
              className="md:hidden fixed inset-0 z-[60] bg-[var(--tavus-terminal-black)]/50"
            />

            {/* Drawer panel */}
            <motion.div
              initial={{ x: "-100%" }}
              animate={{ x: 0 }}
              exit={{ x: "-100%" }}
              transition={{ type: "tween", duration: 0.25 }}
              className="md:hidden fixed top-0 left-0 bottom-0 z-[70] w-64 bg-white border-r-[3px] border-[var(--tavus-terminal-black)] overflow-y-auto scrollbar-thin"
            >
              {/* Drawer header */}
              <div className="flex items-center justify-between p-4 border-b-[3px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-plastic-1)]">
                <span className="font-extrabold text-[var(--tavus-terminal-black)] text-sm">MENU</span>
                <button onClick={() => setOpen(false)} className="w-8 h-8 border-2 border-[var(--tavus-terminal-black)] bg-white flex items-center justify-center">
                  <X className="w-4 h-4" />
                </button>
              </div>

              {/* Nav items */}
              <div className="p-3">
                <Link
                  href="/dashboard"
                  onClick={() => setOpen(false)}
                  className="inline-flex items-center gap-1 text-[10px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)] hover:text-[var(--tavus-terminal-black)] mb-3"
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
                        onClick={() => setOpen(false)}
                        className={`flex items-center gap-2 px-3 py-2.5 border-2 text-sm font-bold transition-all ${
                          isActive
                            ? "border-[var(--tavus-terminal-black)] bg-[var(--tavus-bubbletech-4)] text-[var(--tavus-terminal-black)]"
                            : "border-transparent text-[var(--tavus-terminal-black)] hover:bg-[var(--tavus-plastic-2)]"
                        }`}
                      >
                        <item.icon className="w-4 h-4 shrink-0" strokeWidth={2} />
                        <span>{item.label}</span>
                      </Link>
                    );
                  })}
                </nav>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </>
  );
}
