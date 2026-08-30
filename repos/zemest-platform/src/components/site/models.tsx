"use client";

import { motion } from "framer-motion";
import Image from "next/image";
import { Feather, Bird, ArrowUpRight } from "lucide-react";

const models = [
  {
    code: "Rabbit v1",
    family: "RABBIT",
    version: "v1",
    icon: Feather,
    role: "Arabic moderation · every dialect",
    desc: "Our flagship Arabic model. Speaks Egyptian, Gulf, Levantine, Maghrebi, and Sudanese — and replies in the same dialect the customer used. Voice-note transcription built in. Trained on millions of Arabic commerce conversations.",
    specs: [
      { k: "Dialects", v: "30+" },
      { k: "Voice", v: "Native" },
      { k: "Languages", v: "Arabic" },
    ],
    colorSquare: "var(--tavus-bubbletech-4)",
  },
  {
    code: "Rat v1",
    family: "RAT",
    version: "v1",
    icon: Bird,
    role: "English moderation · every accent",
    desc: "Our flagship English model. Handles US, UK, Australian, Indian, and South African English — the way your customers actually speak it. Reads images, listens to voice, replies in your brand tone.",
    specs: [
      { k: "Accents", v: "12+" },
      { k: "Voice", v: "Native" },
      { k: "Languages", v: "English" },
    ],
    colorSquare: "var(--tavus-neon-field-2)",
  },
];

export function Models() {
  return (
    <section className="bg-grain border-b-2 border-[var(--tavus-terminal-black)] py-16 sm:py-24">
      <div className="mx-auto max-w-[1400px] px-5 sm:px-8">
        <div className="max-w-3xl mb-12">
          <div className="inline-flex items-center gap-2 mb-5">
            <span className="w-2 h-2 bg-[var(--tavus-terminal-black)]" />
            <span className="text-[11px] font-bold tracking-[0.15em] uppercase">MODELS</span>
          </div>
          <h2 className="font-[var(--font-serif-display)] text-4xl sm:text-6xl font-normal tracking-tight text-[var(--tavus-terminal-black)] leading-[1.05]">
            Two models.{" "}
            <span className="serif-italic">One mission.</span>
          </h2>
          <p className="mt-6 text-base sm:text-lg text-[var(--tavus-hardware-gray-8)] leading-relaxed">
            Each Zemest model is specialized for a language — Rabbit v1 for Arabic, Rat v1 for English. Together they cover the conversations your customers actually have, in the dialects they actually use.
          </p>
        </div>

        {/* Models grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {models.map((m, i) => (
            <motion.div
              key={m.code}
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-60px" }}
              transition={{ duration: 0.5, delay: i * 0.08 }}
              className="relative bg-white border-2 border-[var(--tavus-terminal-black)] shadow-[6px_6px_0_0_var(--tavus-terminal-black)] hover:shadow-[8px_8px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[2px_2px_0_0_var(--tavus-terminal-black)] transition-all overflow-hidden"
            >
              {/* Premium bitmap halftone overlay */}
              <div className="absolute inset-0 bg-halftone-light opacity-10 pointer-events-none" />
              <div className="relative flex items-center justify-between px-4 py-2 border-b-2 border-[var(--tavus-terminal-black)] bg-[var(--tavus-plastic-1)]">
                <div className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 border border-[var(--tavus-terminal-black)] text-white" style={{ background: m.colorSquare }} />
                  <span className="text-[10px] font-bold tracking-wider uppercase">{m.family}</span>
                </div>
                <span className="text-[10px] font-mono font-bold text-[var(--tavus-hardware-gray-8)]">{m.version}</span>
              </div>

              <div className="relative p-6">
                <div className="flex items-end gap-3 mb-4">
                  <div
                    className="inline-flex h-14 w-14 items-center justify-center border-2 border-[var(--tavus-terminal-black)] shadow-[2px_2px_0_0_var(--tavus-terminal-black)]"
                    style={{ background: m.colorSquare }}
                  >
                    <m.icon className="h-6 w-6 text-[var(--tavus-terminal-black)]" strokeWidth={2} />
                  </div>
                  <div>
                    <h3 className="font-[var(--font-serif-display)] text-3xl font-normal leading-none text-[var(--tavus-terminal-black)]">
                      {m.code}
                    </h3>
                    <p className="text-[11px] font-bold tracking-wider uppercase text-[var(--tavus-terminal-black)]/70 mt-1">
                      {m.role}
                    </p>
                  </div>
                </div>

                <p className="text-sm text-[var(--tavus-terminal-black)]/80 leading-relaxed mb-5">
                  {m.desc}
                </p>

                <div className="grid grid-cols-3 gap-2 mb-5">
                  {m.specs.map((s) => (
                    <div
                      key={s.k}
                      className="bg-[var(--tavus-plastic-1)] border-2 border-[var(--tavus-terminal-black)] p-2"
                    >
                      <div className="text-[9px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)]">
                        {s.k}
                      </div>
                      <div className="text-sm font-bold text-[var(--tavus-terminal-black)] font-[var(--font-serif-display)] mt-0.5">
                        {s.v}
                      </div>
                    </div>
                  ))}
                </div>

                <a
                  href="/models"
                  className="inline-flex items-center gap-1 text-[11px] font-bold tracking-wider uppercase text-[var(--tavus-terminal-black)] hover:underline"
                >
                  Read the model card
                  <ArrowUpRight className="w-3 h-3" />
                </a>
              </div>
            </motion.div>
          ))}
        </div>

        {/* Research strip */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-60px" }}
          transition={{ duration: 0.5 }}
          className="mt-8 relative overflow-hidden bg-white border-2 border-[var(--tavus-terminal-black)] shadow-[6px_6px_0_0_var(--tavus-terminal-black)] hover:shadow-[8px_8px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 transition-all"
        >
          <div className="grid grid-cols-1 sm:grid-cols-[auto_1fr_auto] gap-5 items-center p-5">
            <Image
              src="/tavus-models-birds.avif"
              alt="Zemest models — Rabbit + Rat"
              width={80}
              height={80}
              className="w-16 h-16 object-cover border-2 border-[var(--tavus-terminal-black)]"
            />
            <div>
              <div className="text-[10px] font-bold tracking-[0.15em] uppercase text-[var(--tavus-hardware-gray-8)]">
                RESEARCH
              </div>
              <h3 className="mt-1 font-[var(--font-serif-display)] text-2xl font-normal text-[var(--tavus-terminal-black)]">
                The science behind the agents
              </h3>
              <p className="mt-1 text-sm text-[var(--tavus-hardware-gray-8)]">
                Dialect detection · Voice transcription · Image understanding · Inventory reasoning — explore the research powering Zemest agents.
              </p>
            </div>
            <a
              href="/research"
              className="inline-flex items-center gap-1.5 px-4 h-10 border-2 border-[var(--tavus-terminal-black)] bg-[var(--tavus-neon-field-2)] text-white text-[11px] font-bold tracking-wider uppercase shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:shadow-[4px_4px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] transition-all whitespace-nowrap"
            >
              Our Research
              <ArrowUpRight className="w-3.5 h-3.5" />
            </a>
          </div>
        </motion.div>
      </div>
    </section>
  );
}
