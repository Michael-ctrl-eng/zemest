"use client";

import { motion } from "framer-motion";
import Image from "next/image";

export function PioneeringSection() {
  return (
    <section id="research" className="bg-grain border-b-2 border-[var(--tavus-terminal-black)] py-16 sm:py-24">
      <div className="mx-auto max-w-[1100px] px-5 sm:px-8">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-60px" }}
          transition={{ duration: 0.6 }}
          className="relative bg-white border-2 border-[var(--tavus-terminal-black)] shadow-[8px_8px_0_0_var(--tavus-terminal-black)] overflow-hidden"
        >
          <div className="win-title-bar">
            <span className="w-2.5 h-2.5 bg-[var(--tavus-bubbletech-4)] border border-[var(--tavus-terminal-black)]" />
            <span>ZEMEST · AGENT & THE CUSTOMER</span>
            <span className="ml-auto flex gap-1">
              <span className="w-2.5 h-2.5 border border-[var(--tavus-terminal-black)]" />
              <span className="w-2.5 h-2.5 border border-[var(--tavus-terminal-black)]" />
              <span className="w-2.5 h-2.5 border border-[var(--tavus-terminal-black)]" />
            </span>
          </div>
          <div className="relative aspect-[16/9] bg-[var(--tavus-keyboard-tan-1)]">
            <Image
              src="/tavus-shadow-portrait.avif"
              alt="Agent and customer reaching across"
              fill
              sizes="(max-width: 1024px) 100vw, 1100px"
              className="object-cover"
            />
            <div className="absolute inset-0 bg-halftone-light opacity-30 pointer-events-none mix-blend-multiply" />
            <div className="absolute inset-0 opacity-15 pointer-events-none mix-blend-multiply" style={{
              backgroundImage: 'repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(20,2,6,0.4) 2px, rgba(20,2,6,0.4) 3px)'
            }} />
            <div className="absolute bottom-3 left-3 bg-white border-2 border-[var(--tavus-terminal-black)] px-3 py-1.5 text-[11px] font-bold tracking-wider uppercase">
              agent & the customer
            </div>
          </div>
        </motion.div>

        <motion.h2
          initial={{ opacity: 0, y: 12 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-60px" }}
          transition={{ duration: 0.6, delay: 0.1 }}
          className="mt-12 text-center font-[var(--font-serif-display)] text-4xl sm:text-5xl lg:text-6xl font-normal tracking-tight text-[var(--tavus-terminal-black)] leading-[1.1]"
        >
          Pioneering commerce moderation <span className="serif-italic">since 2024</span>
        </motion.h2>

        <motion.p
          initial={{ opacity: 0, y: 12 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-60px" }}
          transition={{ duration: 0.6, delay: 0.16 }}
          className="mt-6 text-base sm:text-lg text-[var(--tavus-hardware-gray-8)] leading-relaxed max-w-3xl mx-auto text-center"
        >
          Zemest is an AI research lab pioneering <span className="font-bold text-[var(--tavus-terminal-black)]">commerce moderation</span>: a future where every customer message — on WhatsApp, Facebook, or Instagram — gets an instant, friendly, on-brand reply that closes the sale. We build foundational models that teach machines the art of being a great seller: to listen, read images, understand dialects, check inventory, and respond with the warmth of a human shop owner. The result is a new kind of commerce that feels personal, alive, and impossible to distinguish from you.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 12 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-60px" }}
          transition={{ duration: 0.6, delay: 0.22 }}
          className="mt-9 flex justify-center"
        >
          <a
            href="#"
            className="inline-flex items-center gap-2 px-7 h-12 border-2 border-[var(--tavus-terminal-black)] bg-[var(--tavus-bubbletech-4)] text-xs font-bold tracking-[0.08em] uppercase shadow-[4px_4px_0_0_var(--tavus-terminal-black)] hover:shadow-[6px_6px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] transition-all"
          >
            Start a demo conversation
          </a>
        </motion.div>
      </div>
    </section>
  );
}
