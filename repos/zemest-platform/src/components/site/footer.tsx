"use client";

import Link from "next/link";

// Real footer columns — all links go to real Zemest pages
const groups = [
  {
    title: "COMPANY",
    links: [
      { label: "Pricing", href: "/pricing" },
      { label: "Enterprise", href: "/enterprise" },
      { label: "Careers", href: "/careers" },
      { label: "Partnerships", href: "/partnerships" },
    ],
  },
  {
    title: "RESOURCES",
    links: [
      { label: "Blog", href: "/blog" },
      { label: "Brand kit", href: "/brand-kit" },
      { label: "Press kit", href: "/press-kit" },
      { label: "Book a demo", href: "/book-demo" },
    ],
  },
  {
    title: "PRODUCT",
    links: [
      { label: "Rabbit v1", href: "/models" },
      { label: "Rat v1", href: "/models" },
      { label: "Inventory Connect", href: "/products" },
      { label: "Solutions", href: "/solutions" },
    ],
  },
  {
    title: "RESEARCH",
    links: [
      { label: "Research Overview", href: "/research" },
      { label: "Dialect Detection", href: "/research" },
      { label: "Voice Transcription", href: "/research" },
      { label: "Image Understanding", href: "/research" },
    ],
  },
  {
    title: "SOCIALS",
    links: [
      { label: "LinkedIn", href: "#" },
      { label: "X", href: "#" },
      { label: "Discord", href: "#" },
      { label: "Email", href: "mailto:hello@zemest.ai" },
    ],
  },
  {
    title: "LEGAL",
    links: [
      { label: "Privacy policy", href: "/privacy" },
      { label: "Terms of service", href: "/terms" },
      { label: "Acceptable use", href: "/acceptable-use" },
      { label: "Data processing", href: "/dpa" },
    ],
  },
  {
    title: "SUPPORT",
    links: [
      { label: "Support center", href: "/support" },
      { label: "Trust center", href: "/trust" },
      { label: "Status", href: "/status" },
      { label: "Contact", href: "/book-demo" },
    ],
  },
];

export function Footer() {
  return (
    <footer className="bg-white">
      {/* Top section: 7 columns with separate header chips above each */}
      <div className="border-t-[3px] border-[var(--tavus-terminal-black)]">
        <div className="mx-auto max-w-[1400px] px-4 sm:px-6 py-12">
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-x-4 gap-y-8">
            {groups.map((g) => (
              <div key={g.title} className="flex flex-col">
                <div className="inline-flex items-center gap-1.5 px-2 py-1.5 bg-[var(--tavus-terminal-black)] border-2 border-[var(--tavus-terminal-black)] self-start mb-4">
                  <span className="w-1.5 h-1.5 bg-white shrink-0" />
                  <span className="text-[10px] font-extrabold tracking-[0.08em] uppercase text-white">
                    {g.title}
                  </span>
                </div>
                <ul className="space-y-2">
                  {g.links.map((l) => (
                    <li key={l.label}>
                      <Link
                        href={l.href}
                        className="text-[12px] text-[var(--tavus-terminal-black)] hover:underline leading-tight block"
                      >
                        {l.label}
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Bottom pink section with ZEMEST wordmark */}
      <div className="relative bg-[var(--tavus-bubbletech-4)] border-t-[3px] border-[var(--tavus-terminal-black)] overflow-hidden">
        {/* Premium bitmap dot pattern overlay */}
        <div
          className="absolute inset-0 opacity-40 pointer-events-none"
          style={{
            backgroundImage:
              "radial-gradient(circle at 1px 1px, rgba(255, 255, 255, 0.5) 1.5px, transparent 0)",
            backgroundSize: "10px 10px",
          }}
        />
        <div
          className="absolute inset-0 opacity-20 pointer-events-none mix-blend-overlay"
          style={{
            backgroundImage:
              "radial-gradient(circle at 1px 1px, rgba(20, 2, 6, 0.4) 1px, transparent 0)",
            backgroundSize: "6px 6px",
          }}
        />

        <div className="relative mx-auto max-w-[1400px] px-4 sm:px-6 py-10">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-6">
            {/* Left: accessibility icon + EXPLORE WITH AI */}
            <div className="flex items-center gap-3 flex-wrap">
              <div className="w-8 h-8 rounded-full bg-white border-2 border-[var(--tavus-terminal-black)] flex items-center justify-center shrink-0">
                <svg viewBox="0 0 24 24" className="w-5 h-5" fill="currentColor">
                  <circle cx="12" cy="5" r="2" />
                  <path
                    d="M 12 8 L 12 15 M 6 11 L 18 11 M 8 21 L 12 15 L 16 21"
                    stroke="currentColor"
                    strokeWidth="2"
                    fill="none"
                    strokeLinecap="round"
                  />
                </svg>
              </div>
              <span className="text-[10px] font-extrabold tracking-[0.12em] uppercase text-[var(--tavus-terminal-black)]">
                EXPLORE WITH AI:
              </span>
              {["Z", "@", "#", "*"].map((sym, i) => (
                <div
                  key={i}
                  className="w-6 h-6 border-2 border-[var(--tavus-terminal-black)] bg-white flex items-center justify-center text-[10px] font-bold text-[var(--tavus-terminal-black)]"
                >
                  {sym}
                </div>
              ))}
            </div>

            {/* Right: copyright */}
            <div className="text-[11px] font-extrabold tracking-[0.12em] uppercase text-[var(--tavus-terminal-black)] text-center sm:text-right">
              © 2026 ZEMEST | THE COMMERCE MODERATION COMPANY | ALL RIGHTS RESERVED
            </div>
          </div>

          {/* Giant ZEMEST wordmark */}
          <div className="mt-10 select-none">
            <div
              className="font-extrabold tracking-tighter text-[var(--tavus-terminal-black)] opacity-40 text-left leading-none"
              style={{
                fontSize: "clamp(80px, 16vw, 200px)",
                lineHeight: 0.85,
              }}
            >
              zemest
            </div>
          </div>
        </div>
      </div>
    </footer>
  );
}
