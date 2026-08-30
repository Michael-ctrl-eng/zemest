"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import Image from "next/image";
import { ArrowLeft, ArrowRight } from "lucide-react";

const cases = [
  {
    tag: "FACEBOOK MESSENGER MODERATION",
    label: "MESSENGER AGENT",
    title: "Every comment, every message, answered instantly",
    desc: "The agent reads images, listens to voice messages, and responds in the dialect your customers actually use — no script, no awkward bot vibes.",
    image: "/zemest-card-messenger.avif",
    stat: { v: "+38%", k: "CSAT" },
  },
  {
    tag: "WHATSAPP MODERATION",
    label: "WHATSAPP AGENT",
    title: "Replies like the buyer is talking to you",
    desc: "The agent answers product questions, checks inventory live, and replies in your exact tone — voice notes included.",
    image: "/zemest-card-whatsapp.avif",
    stat: { v: "3.2×", k: "reply rate" },
  },
  {
    tag: "INSTAGRAM DM MODERATION",
    label: "INSTAGRAM AGENT",
    title: "Closes sales in the DMs while you sleep",
    desc: "From story replies to product inquiries, the agent handles every DM, knows what's in stock, quotes prices, and books the order — in Arabic or English.",
    image: "/zemest-card-instagram.avif",
    stat: { v: "+47%", k: "DM→sale lift" },
  },
];

export function UseCases() {
  const [active, setActive] = useState(0);
  const c = cases[active];

  const next = () => setActive((i) => (i + 1) % cases.length);
  const prev = () => setActive((i) => (i - 1 + cases.length) % cases.length);

  return (
    <section className="bg-grain border-b-2 border-[var(--tavus-terminal-black)] py-16 sm:py-24">
      <div className="mx-auto max-w-[1400px] px-5 sm:px-8">
        {/* Header */}
        <div className="text-center mb-12">
          <motion.h2
            initial={{ opacity: 0, y: 12 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5 }}
            className="font-[var(--font-serif-display)] text-4xl sm:text-6xl lg:text-7xl font-normal tracking-tight text-[var(--tavus-terminal-black)] leading-[1.05]"
          >
            One agent for every{" "}
            <span className="serif-italic">conversation</span>
          </motion.h2>
          <p className="mt-6 text-base sm:text-lg text-[var(--tavus-hardware-gray-8)] max-w-2xl mx-auto leading-relaxed">
            An agent can be whatever the moment calls for: a Messenger support rep, a WhatsApp seller, an Instagram DM closer. One agent that already knows your products, prices, and stock. Here are a few ways brands are putting them to work:
          </p>
        </div>

        {/* Carousel */}
        <div className="relative">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-5 lg:gap-4 items-stretch">
            <CarouselSideCard
              c={cases[(active - 1 + cases.length) % cases.length]}
              onClick={prev}
            />

            <AnimatePresence mode="wait">
              <motion.div
                key={active}
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -16 }}
                transition={{ duration: 0.3 }}
                className="relative bg-white border-2 border-[var(--tavus-terminal-black)] shadow-[8px_8px_0_0_var(--tavus-terminal-black)] overflow-hidden"
              >
                {/* Premium bitmap halftone overlay */}
                <div className="absolute inset-0 bg-halftone-light opacity-10 pointer-events-none z-20" />
                <div className="win-title-bar relative">
                  <span className="w-2.5 h-2.5 bg-[var(--tavus-bubbletech-4)] border border-[var(--tavus-terminal-black)]" />
                  <span>{c.label}</span>
                  <span className="ml-auto flex gap-1">
                    <span className="w-2.5 h-2.5 border border-[var(--tavus-terminal-black)]" />
                    <span className="w-2.5 h-2.5 border border-[var(--tavus-terminal-black)]" />
                    <span className="w-2.5 h-2.5 border border-[var(--tavus-terminal-black)]" />
                  </span>
                </div>
                <div className="relative aspect-[4/3] bg-[var(--tavus-terminal-black)] overflow-hidden">
                  <Image
                    src={c.image}
                    alt={c.title}
                    fill
                    sizes="(max-width: 1024px) 100vw, 33vw"
                    className="object-cover"
                  />
                  <div className="absolute inset-0 bg-gradient-to-t from-black/45 to-transparent" />
                  {/* Faint bitmap dot texture — print identity, photo stays readable */}
                  <div className="absolute inset-0 bg-halftone-light opacity-[0.08] pointer-events-none z-20" />
                  <div className="absolute top-3 left-3 inline-flex items-center gap-1.5 bg-white border-2 border-[var(--tavus-terminal-black)] px-2 py-1 text-[10px] font-bold tracking-wider uppercase">
                    <span className="w-1.5 h-1.5 bg-[var(--tavus-neon-field-2)]" />
                    {c.tag}
                  </div>
                  <div className="absolute top-3 right-3 bg-[var(--tavus-neon-field-2)] text-white border-2 border-[var(--tavus-terminal-black)] px-2 py-1 text-right">
                    <div className="text-base font-bold leading-none font-[var(--font-serif-display)]">{c.stat.v}</div>
                    <div className="text-[9px] font-bold tracking-wider uppercase mt-0.5">{c.stat.k}</div>
                  </div>
                  <div className="absolute bottom-3 left-3 bg-white border-2 border-[var(--tavus-terminal-black)] px-3 py-1.5 text-[11px] font-bold tracking-wider uppercase">
                    {c.label}
                  </div>
                </div>
                <div className="p-5">
                  <h3 className="font-[var(--font-serif-display)] text-2xl font-normal leading-tight text-[var(--tavus-terminal-black)]">
                    {c.title}
                  </h3>
                  <p className="mt-2 text-sm text-[var(--tavus-hardware-gray-8)] leading-relaxed">
                    {c.desc}
                  </p>
                  <a
                    href="#"
                    className="mt-4 inline-flex items-center gap-1.5 text-[11px] font-bold tracking-wider uppercase text-[var(--tavus-terminal-black)] hover:underline"
                  >
                    See it in action
                    <ArrowRight className="w-3 h-3" />
                  </a>
                </div>
              </motion.div>
            </AnimatePresence>

            <CarouselSideCard
              c={cases[(active + 1) % cases.length]}
              onClick={next}
            />
          </div>

          <button
            onClick={prev}
            className="hidden lg:flex absolute top-1/2 -left-5 -translate-y-1/2 w-12 h-12 items-center justify-center bg-[var(--tavus-neon-field-2)] text-white border-2 border-[var(--tavus-terminal-black)] shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:shadow-[4px_4px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-1/2 active:translate-x-0.5 active:translate-y-1/2 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] transition-all z-10"
            aria-label="Previous"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <button
            onClick={next}
            className="hidden lg:flex absolute top-1/2 -right-5 -translate-y-1/2 w-12 h-12 items-center justify-center bg-[var(--tavus-neon-field-2)] text-white border-2 border-[var(--tavus-terminal-black)] shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:shadow-[4px_4px_0_0_var(--tavus-terminal-black)] hover:translate-x-0.5 hover:-translate-y-1/2 active:translate-x-0 active:translate-y-1/2 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] transition-all z-10"
            aria-label="Next"
          >
            <ArrowRight className="w-5 h-5" />
          </button>
        </div>

        {/* Dots */}
        <div className="mt-8 flex items-center justify-center gap-2">
          {cases.map((_, i) => (
            <button
              key={i}
              onClick={() => setActive(i)}
              className={`h-2.5 w-2.5 border-2 border-[var(--tavus-terminal-black)] transition-all ${
                active === i ? "w-8 bg-[var(--tavus-bubbletech-4)]" : "bg-white"
              }`}
              aria-label={`Go to ${i + 1}`}
            />
          ))}
        </div>
      </div>
    </section>
  );
}

function CarouselSideCard({
  c,
  onClick,
}: {
  c: (typeof cases)[0];
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="hidden lg:flex flex-col bg-white border-2 border-[var(--tavus-terminal-black)] shadow-[6px_6px_0_0_var(--tavus-terminal-black)] overflow-hidden text-left opacity-70 hover:opacity-100 hover:-translate-y-1 hover:shadow-[8px_8px_0_0_var(--tavus-terminal-black)] transition-all"
    >
      <div className="win-title-bar">
        <span className="w-2.5 h-2.5 bg-[var(--tavus-hardware-gray-8)] border border-[var(--tavus-terminal-black)]" />
        <span className="truncate">{c.label}</span>
      </div>
      <div className="relative aspect-[4/3] bg-[var(--tavus-terminal-black)] overflow-hidden">
        <Image
          src={c.image}
          alt={c.title}
          fill
          sizes="33vw"
          className="object-cover opacity-60"
        />
        <div className="absolute top-3 left-3 inline-flex items-center gap-1.5 bg-white/90 border border-[var(--tavus-terminal-black)] px-2 py-1 text-[10px] font-bold tracking-wider uppercase">
          <span className="w-1.5 h-1.5 bg-[var(--tavus-hardware-gray-8)]" />
          {c.tag}
        </div>
      </div>
      <div className="p-3 flex-1">
        <div className="text-[10px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)]">
          {c.label}
        </div>
        <div className="mt-1 text-sm font-normal font-[var(--font-serif-display)] text-[var(--tavus-terminal-black)] line-clamp-2">
          {c.title}
        </div>
      </div>
    </button>
  );
}
