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
      { label: "Rooster v1", href: "/models" },
      { label: "Inventory Connect", href: "/products" },
      { label: "Solutions", href: "/solutions" },
    ],
  },
  {
    title: "CAPABILITIES",
    links: [
      { label: "Dialect Detection", href: "/models" },
      { label: "Voice Transcription", href: "/models" },
      { label: "Image Understanding", href: "/models" },
      { label: "Inventory Connect", href: "/products" },
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

      {/* Bottom band — full-bleed bluish-white sky/clouds with black ZEMEST wordmark */}
      <div className="relative border-t-[3px] border-[var(--tavus-terminal-black)] overflow-hidden bg-[#0a0a0a]">
        {/* The cloud photo fills the whole band */}
        <img
          src="/zemest-cloud-sea-footer.avif"
          alt=""
          aria-hidden="true"
          width={1920}
          height={640}
          loading="lazy"
          decoding="async"
          className="absolute inset-0 w-full h-full object-cover"
        />
        {/* Subtle bitmap dot pattern — true black, keeps the print identity */}
        <div
          className="absolute inset-0 opacity-[0.12] pointer-events-none"
          style={{
            backgroundImage:
              "radial-gradient(circle at 1px 1px, rgba(0, 0, 0, 0.9) 1.5px, transparent 0)",
            backgroundSize: "10px 10px",
          }}
        />
        {/* Soft white haze at the very bottom so the wordmark stays crisp */}
        <div className="absolute inset-x-0 bottom-0 h-1/2 bg-gradient-to-t from-white/85 via-white/35 to-transparent" />

        <div className="relative mx-auto max-w-[1400px] px-4 sm:px-6 pt-8 pb-10">
          {/* copyright */}
          <div className="text-[11px] font-extrabold tracking-[0.12em] uppercase text-[var(--tavus-terminal-black)] text-center drop-shadow-[0_1px_0_rgba(255,255,255,0.8)]">
            © 2026 ZEMEST | THE COMMERCE MODERATION COMPANY | ALL RIGHTS RESERVED
          </div>

          {/* Giant ZEMEST wordmark — true black over the clouds */}
          <div className="mt-8 select-none">
            <div
              className="font-extrabold tracking-tighter text-[var(--tavus-terminal-black)] text-left leading-none"
              style={{
                fontSize: "clamp(80px, 16vw, 200px)",
                lineHeight: 0.85,
                textShadow: "3px 3px 0 rgba(255, 255, 255, 0.85)",
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
