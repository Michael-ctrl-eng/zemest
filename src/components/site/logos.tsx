"use client";

/**
 * Brand marquee — text wordmarks for our fictional partner brands.
 * No image requests at all (instant paint) and each wordmark gets its own
 * type treatment so the strip reads like a real, diverse logo wall.
 */

const brands = [
  { name: "Novus", cls: "font-sans font-semibold uppercase tracking-[0.32em] text-[15px]" },
  { name: "Arosota", cls: "font-serif italic text-[22px]" },
  { name: "Rose", cls: "font-serif font-normal uppercase tracking-[0.18em] text-[19px]" },
  { name: "Poly", cls: "font-sans font-extrabold lowercase tracking-tight text-[24px]" },
  { name: "Trinch", cls: "font-mono uppercase tracking-[0.14em] text-[16px]" },
  { name: "Exom", cls: "font-sans font-black uppercase tracking-tight text-[24px]" },
  { name: "Verzian", cls: "font-serif uppercase tracking-[0.42em] text-[14px]" },
  { name: "Çelebi", cls: "font-serif italic font-medium text-[21px]" },
  { name: "Mersin", cls: "font-sans font-bold uppercase tracking-[0.08em] text-[19px]" },
  { name: "Nemo", cls: "font-mono lowercase tracking-[0.34em] text-[15px]" },
];

export function Logos() {
  return (
    <section className="bg-[var(--tavus-terminal-black)] border-b-2 border-[var(--tavus-terminal-black)] py-4 overflow-hidden">
      <div className="mx-auto max-w-[1400px] px-4">
        <p className="text-center text-[10px] font-bold tracking-[0.15em] uppercase text-white/50 mb-4">
          Powering moderation for 1,000+ sellers and the world&apos;s most ambitious brands
        </p>
        <div className="relative overflow-hidden mask-fade-x">
          <div className="flex w-max animate-scroll-x gap-14 items-center">
            {[...brands, ...brands, ...brands].map((b, i) => (
              <div
                key={i}
                className={`flex items-center justify-center text-white/60 hover:text-white transition-colors ${b.cls}`}
                aria-hidden={i >= brands.length ? true : undefined}
              >
                {b.name}
              </div>
            ))}
          </div>
        </div>
        <p className="text-center text-[10px] tracking-[0.08em] uppercase text-white/35 mt-4">
          Every agent knows every tool and price — straight from your brand&apos;s page.
        </p>
      </div>
    </section>
  );
}
