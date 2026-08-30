"use client";

import { motion } from "framer-motion";
import Image from "next/image";
import { ArrowUpRight } from "lucide-react";

const products = [
  {
    label: "RABBIT V1",
    colorSquare: "var(--tavus-bubbletech-4)",
    headline: "Arabic moderation, every accent",
    desc: "Rabbit v1 speaks Egyptian, Gulf, Levantine, Maghrebi — and replies in the same dialect the customer used. Trained on millions of Arabic commerce conversations, with voice-note transcription built in.",
    cta: "GET STARTED",
    ctaBg: "var(--tavus-bubbletech-4)",
    ctaText: "var(--tavus-terminal-black)",
    bg: "var(--tavus-plastic-1)",
    visual: "rabbit",
  },
  {
    label: "ROOSTER V1",
    colorSquare: "var(--tavus-neon-field-2)",
    headline: "English moderation, every accent",
    desc: "Rooster v1 handles US, UK, AUS, Indian, and South African English — the way your customers actually speak it. Reads images, listens to voice, replies in your brand tone.",
    cta: "GET STARTED",
    ctaBg: "var(--tavus-neon-field-2)",
    ctaText: "var(--tavus-terminal-black)",
    bg: "var(--tavus-plastic-1)",
    visual: "rooster",
  },
  {
    label: "INVENTORY CONNECT",
    colorSquare: "var(--tavus-atomic-glow-1)",
    headline: "Live inventory in every reply",
    desc: "Connect your shop or POS. The agent checks stock in real-time before answering — so when a buyer asks for size 42, it knows if it's available, the price, and how many are left.",
    cta: "CONNECT SHOP",
    ctaBg: "var(--tavus-atomic-glow-5)",
    ctaText: "var(--tavus-terminal-black)",
    bg: "var(--tavus-plastic-1)",
    visual: "inventory",
  },
];

export function Products() {
  return (
    <section id="products" className="bg-grain border-b-2 border-[var(--tavus-terminal-black)] py-16 sm:py-24">
      <div className="mx-auto max-w-[1400px] px-5 sm:px-8">
        <div className="text-center mb-12">
          <motion.h2
            initial={{ opacity: 0, y: 12 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5 }}
            className="font-[var(--font-serif-display)] text-4xl sm:text-6xl lg:text-7xl font-normal tracking-tight text-[var(--tavus-terminal-black)] leading-[1.05]"
          >
            Our <span className="serif-italic">products</span>
          </motion.h2>
          <p className="mt-6 text-base sm:text-lg text-[var(--tavus-hardware-gray-8)] max-w-2xl mx-auto leading-relaxed">
            Two specialized models and one inventory brain. Together, they make every customer conversation feel like it&apos;s coming from you — not a bot.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {products.map((p, i) => (
            <motion.div
              key={p.label}
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-60px" }}
              transition={{ duration: 0.5, delay: i * 0.08 }}
              className="relative bg-white border-2 border-[var(--tavus-terminal-black)] shadow-[6px_6px_0_0_var(--tavus-terminal-black)] hover:shadow-[8px_8px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[2px_2px_0_0_var(--tavus-terminal-black)] transition-all overflow-hidden flex flex-col"
            >
              {/* Premium bitmap halftone overlay */}
              <div className="absolute inset-0 bg-halftone-light opacity-10 pointer-events-none" />
              <div className="win-title-bar relative">
                <span
                  className="w-2.5 h-2.5 border border-[var(--tavus-terminal-black)]"
                  style={{ background: p.colorSquare }}
                />
                <span>{p.label}</span>
                <span className="ml-auto flex gap-1">
                  <span className="w-2.5 h-2.5 border border-[var(--tavus-terminal-black)]" />
                  <span className="w-2.5 h-2.5 border border-[var(--tavus-terminal-black)]" />
                  <span className="w-2.5 h-2.5 border border-[var(--tavus-terminal-black)]" />
                </span>
              </div>

              <div className="relative h-44 border-b-2 border-[var(--tavus-terminal-black)] overflow-hidden bg-[var(--tavus-terminal-black)]">
                <ProductVisual kind={p.visual} />
              </div>

              <div className="relative flex-1 flex flex-col p-6 bg-white">
                <h3 className="font-[var(--font-serif-display)] text-2xl font-normal leading-tight text-[var(--tavus-terminal-black)]">
                  {p.headline}
                </h3>
                <p className="mt-3 text-sm text-[var(--tavus-hardware-gray-8)] leading-relaxed flex-1">
                  {p.desc}
                </p>
                <a
                  href="/get-started"
                  className="mt-5 inline-flex items-center justify-center gap-2 px-5 h-10 border-2 border-[var(--tavus-terminal-black)] text-[11px] font-bold tracking-wider uppercase shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:shadow-[4px_4px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] transition-all w-full"
                  style={{ background: p.ctaBg, color: p.ctaText }}
                >
                  {p.cta}
                  <ArrowUpRight className="w-3.5 h-3.5" />
                </a>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}

function ProductVisual({ kind }: { kind: string }) {
  if (kind === "rabbit") {
    return (
      <div className="absolute inset-0 bg-[var(--tavus-terminal-black)] p-4 flex flex-col justify-center gap-2">
        <div className="text-[10px] font-mono text-white/40">RABBIT V1 · العربية</div>
        <div className="bg-white border-2 border-white p-2 text-[11px] text-[var(--tavus-terminal-black)] font-mono">
          &quot;لو سمحت، عندي بمقاس 42؟&quot;
        </div>
        <div className="bg-[var(--tavus-bubbletech-4)] border-2 border-white p-2 text-[11px] text-[var(--tavus-terminal-black)] font-mono ml-8">
          &quot;أيوا متوفر، 850 جنيه. تحب أثبتهولك؟&quot;
        </div>
        <div className="flex items-center gap-1.5 mt-1 text-[10px] text-[var(--tavus-neon-field-2)] font-mono">
          <span className="w-1.5 h-1.5 bg-[var(--tavus-neon-field-2)] animate-pulse" />
          Dialect: Egyptian · Voice-ready
        </div>
      </div>
    );
  }
  if (kind === "rooster") {
    return (
      <div className="absolute inset-0 bg-[var(--tavus-terminal-black)] p-4 flex flex-col justify-center gap-2">
        <div className="text-[10px] font-mono text-white/40">ROOSTER V1 · ENGLISH</div>
        <div className="bg-white border-2 border-white p-2 text-[11px] text-[var(--tavus-terminal-black)] font-mono">
          &quot;Hey, do you have these in a size 10?&quot;
        </div>
        <div className="bg-[var(--tavus-neon-field-2)] border-2 border-white p-2 text-[11px] text-white font-mono ml-8">
          &quot;Yep — 2 left, $120. Want me to hold one?&quot;
        </div>
        <div className="flex items-center gap-1.5 mt-1 text-[10px] text-[var(--tavus-neon-field-2)] font-mono">
          <span className="w-1.5 h-1.5 bg-[var(--tavus-neon-field-2)] animate-pulse" />
          Accent: US · Voice-ready
        </div>
      </div>
    );
  }
  // inventory
  return (
    <div className="absolute inset-0 bg-[var(--tavus-terminal-black)] p-4 flex flex-col justify-center gap-1.5">
      {[
        { name: "Air Max 90 · Size 42", stock: "IN STOCK", count: "2", color: "var(--tavus-neon-field-2)" },
        { name: "Air Max 90 · Size 43", stock: "OUT OF STOCK", count: "0", color: "var(--tavus-bubbletech-4)" },
        { name: "Air Force 1 · Size 42", stock: "IN STOCK", count: "7", color: "var(--tavus-neon-field-2)" },
      ].map((s, i) => (
        <div key={i} className="flex items-center justify-between bg-white/5 border border-white/10 px-2 py-1.5">
          <div className="flex items-center gap-2">
            <span
              className="px-1.5 py-0.5 text-[9px] font-bold tracking-wider uppercase"
              style={{ background: s.color, color: "var(--tavus-terminal-black)" }}
            >
              {s.stock}
            </span>
            <span className="text-[11px] text-white">{s.name}</span>
          </div>
          <span className="text-[10px] text-white/40 font-mono">{s.count} LEFT</span>
        </div>
      ))}
    </div>
  );
}
