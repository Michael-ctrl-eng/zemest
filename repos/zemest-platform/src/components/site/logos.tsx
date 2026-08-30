"use client";

import Image from "next/image";

const logos = [
  { src: "/logo-amazon.png", name: "Amazon", w: 90 },
  { src: "/logo-salesforce.svg", name: "Salesforce", w: 90 },
  { src: "/logo-deloitte.png", name: "Deloitte", w: 85 },
  { src: "/logo-cvs.svg", name: "CVS Health", w: 85 },
  { src: "/logo-frame.png", name: "Frame", w: 75 },
];

export function Logos() {
  return (
    <section className="bg-[var(--tavus-terminal-black)] border-b-2 border-[var(--tavus-terminal-black)] py-4 overflow-hidden">
      <div className="mx-auto max-w-[1400px] px-4">
        <p className="text-center text-[10px] font-bold tracking-[0.15em] uppercase text-white/50 mb-3">
          Powering moderation for 100,000+ sellers and the world&apos;s most ambitious brands
        </p>
        <div className="relative overflow-hidden mask-fade-x">
          <div className="flex w-max animate-scroll-x gap-10 items-center">
            {[...logos, ...logos, ...logos].map((logo, i) => (
              <div key={i} className="flex items-center justify-center opacity-60 hover:opacity-100 transition-opacity">
                <Image
                  src={logo.src}
                  alt={logo.name}
                  width={logo.w}
                  height={20}
                  className="h-4 w-auto"
                  style={{ height: "auto" }}
                />
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
