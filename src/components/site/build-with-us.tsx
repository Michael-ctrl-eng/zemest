"use client";

import { motion } from "framer-motion";
import Image from "next/image";
import { ArrowUpRight } from "lucide-react";

export function BuildWithUs() {
  return (
    <section id="enterprise" className="relative bg-grain border-b-2 border-[var(--tavus-terminal-black)] py-16 sm:py-24 overflow-hidden">
      <div className="mx-auto max-w-[1400px] px-5 sm:px-8">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-10 items-center">
          {/* Left - glitch portrait illustration */}
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true, margin: "-60px" }}
            transition={{ duration: 0.6 }}
            className="relative"
          >
            <div className="bg-white border-2 border-[var(--tavus-terminal-black)] shadow-[8px_8px_0_0_var(--tavus-terminal-black)] overflow-hidden">
              <div className="win-title-bar">
                <span className="w-2.5 h-2.5 bg-[var(--tavus-frost-5)] border border-[var(--tavus-terminal-black)]" />
                <span>ART · AGENT × CUSTOMER</span>
                <span className="ml-auto flex gap-1">
                  <span className="w-2.5 h-2.5 border border-[var(--tavus-terminal-black)]" />
                  <span className="w-2.5 h-2.5 border border-[var(--tavus-terminal-black)]" />
                  <span className="w-2.5 h-2.5 border border-[var(--tavus-terminal-black)]" />
                </span>
              </div>
              <div className="relative aspect-[4/5] bg-[var(--tavus-frost-2)] overflow-hidden">
                <Image
                  src="/tavus-art-portrait.avif"
                  alt="Zemest — agent and customer"
                  fill
                  sizes="(max-width: 1024px) 100vw, 50vw"
                  className="object-cover"
                />
                <div className="absolute inset-0 bg-halftone opacity-20 pointer-events-none mix-blend-multiply" />
                <div className="absolute inset-0 opacity-20 pointer-events-none mix-blend-multiply" style={{
                  backgroundImage: 'repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(20,2,6,0.5) 2px, rgba(20,2,6,0.5) 3px)'
                }} />
              </div>
            </div>
          </motion.div>

          {/* Right - copy */}
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true, margin: "-60px" }}
            transition={{ duration: 0.6, delay: 0.1 }}
          >
            <span className="inline-block text-[11px] font-bold tracking-[0.25em] uppercase text-[var(--tavus-bubbletech-4)]">
              PARTNERSHIPS
            </span>

            <h2 className="mt-6 font-[var(--font-serif-display)] text-5xl sm:text-7xl lg:text-[88px] font-normal tracking-tight text-[var(--tavus-terminal-black)] leading-[1.02]">
              Wanna make a <span className="serif-italic">deal?</span>
            </h2>

            <p className="mt-6 text-base sm:text-lg text-[var(--tavus-hardware-gray-8)] max-w-xl leading-relaxed">
              Whether you&apos;re a brand looking to scale moderation, an agency building for clients, or a platform wanting to embed Zemest agents — we&apos;d love to talk. Connect with us and let&apos;s figure out what we can build together.
            </p>

            <div className="mt-9 flex flex-col sm:flex-row items-start gap-3">
              <a
                href="/partnerships"
                className="inline-flex items-center gap-2 px-6 h-12 border-2 border-[var(--tavus-terminal-black)] bg-[var(--tavus-bubbletech-4)] text-xs font-bold tracking-[0.08em] uppercase shadow-[4px_4px_0_0_var(--tavus-terminal-black)] hover:shadow-[6px_6px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] transition-all"
              >
                Connect with us
                <ArrowUpRight className="w-4 h-4" />
              </a>
              <a
                href="/partnerships"
                className="inline-flex items-center gap-2 px-6 h-12 border-2 border-[var(--tavus-terminal-black)] bg-white text-xs font-bold tracking-[0.08em] uppercase shadow-[4px_4px_0_0_var(--tavus-terminal-black)] hover:shadow-[6px_6px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] transition-all"
              >
                Explore partnerships
              </a>
            </div>

            {/* Floating team avatars */}
            <div className="mt-10 flex items-center gap-2">
              {[
                { i: "AR", c: "var(--tavus-bubbletech-4)" },
                { i: "EN", c: "var(--tavus-neon-field-2)" },
                { i: "EG", c: "var(--tavus-atomic-glow-1)" },
                { i: "SA", c: "var(--tavus-floppy-fog-3)" },
                { i: "US", c: "var(--tavus-frost-5)" },
                { i: "+", c: "var(--tavus-bubbletech-1)" },
              ].map((m, idx) => (
                <div
                  key={idx}
                  className={`h-10 w-10 border-2 border-[var(--tavus-terminal-black)] flex items-center justify-center text-xs font-bold text-[var(--tavus-terminal-black)] ${
                    idx > 0 ? "-ml-3" : ""
                  }`}
                  style={{ background: m.c }}
                >
                  {m.i}
                </div>
              ))}
              <span className="ml-4 text-xs text-[var(--tavus-hardware-gray-8)]">
                Let&apos;s build something · together
              </span>
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  );
}
