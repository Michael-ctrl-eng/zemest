"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import Image from "next/image";
import { motion, AnimatePresence } from "framer-motion";
import { Menu, X } from "lucide-react";

const nav = [
  { label: "PRODUCTS", href: "/products", bullet: true },
  { label: "SOLUTIONS", href: "/solutions", bullet: true },
  { label: "MODELS", href: "/models", bullet: true },
  { label: "ENTERPRISE", href: "/enterprise", bullet: true },
  { label: "PRICING", href: "/pricing", bullet: false },
];

export function Navbar() {
  const [scrolled, setScrolled] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [announcementClosed, setAnnouncementClosed] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 60);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <>
      {/* Announcement bar */}
      {!announcementClosed && <AnnouncementBar onClose={() => setAnnouncementClosed(true)} />}

      {/* Sticky transparent navbar */}
      <div className="sticky top-0 z-50">
        <div className="mx-auto max-w-[1400px] px-4 sm:px-6 py-3">
          <nav className="flex items-center gap-1.5 sm:gap-2 h-[60px]">
            {/* Logo box - Zemest Z logo */}
            <Link
              href="/"
              className="group relative flex items-center gap-2 px-3 h-11 border-[3px] border-[var(--tavus-terminal-black)] bg-white shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:shadow-[4px_4px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] transition-all shrink-0"
            >
              <Image
                src="/zemest-logo.png"
                alt="Zemest"
                width={32}
                height={32}
                className="h-7 w-7"
                priority
              />
              <span className="font-extrabold tracking-[0.04em] text-[var(--tavus-terminal-black)] text-base sm:text-lg">
                ZEMEST
              </span>
            </Link>

            {/* Nav items */}
            <div className="hidden lg:flex items-center gap-1.5">
              {nav.map((item) => (
                <Link
                  key={item.label}
                  href={item.href}
                  className="group relative flex items-center gap-1.5 px-3 h-11 border-[3px] border-[var(--tavus-terminal-black)] bg-white shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:shadow-[4px_4px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] transition-all"
                >
                  {item.bullet && (
                    <span className="w-[8px] h-[8px] bg-[var(--tavus-terminal-black)] shrink-0 transition-transform group-hover:scale-125 group-hover:bg-[var(--tavus-bubbletech-4)]" />
                  )}
                  <span className="text-[12px] font-extrabold tracking-[0.03em] text-[var(--tavus-terminal-black)] whitespace-nowrap">
                    {item.label}
                  </span>
                </Link>
              ))}
            </div>

            {/* LOGIN + GET STARTED */}
            <div className="ml-auto flex items-center gap-1.5">
              <Link
                href="/login"
                className="hidden sm:flex items-center px-4 h-11 border-[3px] border-[var(--tavus-terminal-black)] bg-white shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:shadow-[4px_4px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] text-[12px] font-extrabold tracking-[0.03em] uppercase text-[var(--tavus-terminal-black)] transition-all"
              >
                LOGIN
              </Link>
              <Link
                href="/get-started"
                className="flex items-center px-4 h-11 border-[3px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-bubbletech-4)] shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:shadow-[4px_4px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] text-[12px] font-extrabold tracking-[0.03em] uppercase text-[var(--tavus-terminal-black)] transition-all"
              >
                GET STARTED
              </Link>

              <button
                className="lg:hidden flex items-center justify-center w-11 h-11 border-[3px] border-[var(--tavus-terminal-black)] bg-white shadow-[3px_3px_0_0_var(--tavus-terminal-black)] active:translate-x-1 active:translate-y-1 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] transition-all"
                onClick={() => setMobileOpen((v) => !v)}
                aria-label="Toggle menu"
              >
                {mobileOpen ? <X className="h-4 w-4" strokeWidth={2.5} /> : <Menu className="h-4 w-4" strokeWidth={2.5} />}
              </button>
            </div>
          </nav>
        </div>

        {/* Mobile drawer */}
        <AnimatePresence>
          {mobileOpen && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.2 }}
              className="lg:hidden overflow-hidden bg-[var(--tavus-plastic-1)] border-b-[3px] border-[var(--tavus-terminal-black)]"
            >
              <div className="px-4 py-3 grid grid-cols-2 gap-2">
                {nav.map((item) => (
                  <Link
                    key={item.label}
                    href={item.href}
                    onClick={() => setMobileOpen(false)}
                    className="flex items-center gap-2 px-3 py-2.5 border-[3px] border-[var(--tavus-terminal-black)] bg-white shadow-[2px_2px_0_0_var(--tavus-terminal-black)] text-[11px] font-extrabold tracking-[0.03em]"
                  >
                    {item.bullet && <span className="w-2 h-2 bg-[var(--tavus-terminal-black)]" />}
                    {item.label}
                  </Link>
                ))}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </>
  );
}

function AnnouncementBar({ onClose }: { onClose: () => void }) {
  return (
    <div className="relative bg-[var(--tavus-bubbletech-1)] border-b-[3px] border-[var(--tavus-terminal-black)] py-2.5">
      <div className="mx-auto max-w-[1400px] px-4 flex items-center justify-center text-center">
        <p className="text-[13px] sm:text-sm font-semibold text-[var(--tavus-terminal-black)]">
          <span className="font-bold">Rabbit v1 is now live:</span> Arabic moderation with every accent — replies like you do.{" "}
          <a href="/models" className="font-bold underline hover:no-underline">
            Learn more.
          </a>
        </p>
        <button
          onClick={onClose}
          className="absolute right-4 top-1/2 -translate-y-1/2 w-6 h-6 border-2 border-[var(--tavus-terminal-black)] bg-white flex items-center justify-center hover:bg-[var(--tavus-plastic-2)] active:translate-y-[-1px] transition-all"
          aria-label="Close"
        >
          <X className="h-3 w-3" strokeWidth={2.5} />
        </button>
      </div>
    </div>
  );
}
