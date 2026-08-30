"use client";

import { motion } from "framer-motion";
import { Eye, Ear, Brain, MessageSquare } from "lucide-react";

const layers = [
  { icon: Eye, label: "SEE", desc: "Reads images, screenshots, and product photos your customers send — knows a Nike from an Adidas on sight." },
  { icon: Ear, label: "HEAR", desc: "Transcribes voice notes in Arabic and English, every dialect — understands tone, urgency, and hesitation." },
  { icon: Brain, label: "UNDERSTAND", desc: "Trained on your old chats. Knows your products, your prices, your tone — and what's in stock right now." },
  { icon: MessageSquare, label: "REPLY", desc: "Replies in the buyer's own dialect, with the same warmth and shorthand you'd use. They can't tell it's not you." },
];

export function WhatIsPAL() {
  return (
    <section className="bg-grain border-b-2 border-[var(--tavus-terminal-black)] py-16 sm:py-24">
      <div className="mx-auto max-w-[1400px] px-5 sm:px-8">
        <div className="max-w-3xl mb-12">
          <div className="inline-flex items-center gap-2 mb-5">
            <span className="w-2 h-2 bg-[var(--tavus-terminal-black)]" />
            <span className="text-[11px] font-bold tracking-[0.15em] uppercase">WHAT IS AN AGENT?</span>
          </div>
          <h2 className="font-[var(--font-serif-display)] text-4xl sm:text-6xl font-normal tracking-tight text-[var(--tavus-terminal-black)] leading-[1.05]">
            A new type of agent that does what{" "}
            <span className="serif-italic">you do</span>
          </h2>
          <p className="mt-6 text-base sm:text-lg text-[var(--tavus-hardware-gray-8)] leading-relaxed">
            Every Zemest agent ships with four layers: it sees, hears, understands, and replies — trained on your own WhatsApp, Facebook, and Instagram history. It&apos;s not a chatbot. It&apos;s you, scaling.
          </p>
        </div>

        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {layers.map((l, i) => (
            <motion.div
              key={l.label}
              initial={{ opacity: 0, y: 14 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-60px" }}
              transition={{ duration: 0.5, delay: i * 0.06 }}
              className="group relative bg-white border-2 border-[var(--tavus-terminal-black)] shadow-[4px_4px_0_0_var(--tavus-terminal-black)] hover:shadow-[6px_6px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] transition-all p-5 overflow-hidden"
            >
              {/* Premium bitmap halftone overlay */}
              <div className="absolute inset-0 bg-halftone-light opacity-15 pointer-events-none" />
              <div className="relative flex items-center justify-between mb-4">
                <l.icon className="h-7 w-7 text-[var(--tavus-terminal-black)]" strokeWidth={2} />
                <span className="text-[10px] font-mono font-bold text-[var(--tavus-hardware-gray-8)]">
                  0{i + 1}
                </span>
              </div>
              <h3 className="relative font-[var(--font-serif-display)] text-3xl font-normal tracking-tight text-[var(--tavus-terminal-black)]">
                {l.label}
              </h3>
              <p className="relative mt-2 text-xs text-[var(--tavus-hardware-gray-8)] leading-relaxed">
                {l.desc}
              </p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
