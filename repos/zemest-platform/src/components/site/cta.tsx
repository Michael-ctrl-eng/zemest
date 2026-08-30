"use client";

import { motion } from "framer-motion";
import { ArrowUpRight } from "lucide-react";

export function CTA() {
  return (
    <section
      id="pricing"
      className="bg-periwinkle-cloud border-b-2 border-[var(--tavus-terminal-black)] py-16 sm:py-24"
    >
      <div className="mx-auto max-w-[1100px] px-5 sm:px-8">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-60px" }}
          transition={{ duration: 0.6 }}
          className="relative bg-white border-2 border-[var(--tavus-terminal-black)] shadow-[8px_8px_0_0_var(--tavus-terminal-black)] p-8 sm:p-12 lg:p-16 text-center overflow-hidden"
        >
          {/* Decorative corner squares */}
          <div className="absolute top-3 left-3 w-3 h-3 bg-[var(--tavus-bubbletech-4)] border border-[var(--tavus-terminal-black)]" />
          <div className="absolute top-3 right-3 w-3 h-3 bg-[var(--tavus-neon-field-2)] text-white border border-[var(--tavus-terminal-black)]" />
          <div className="absolute bottom-3 left-3 w-3 h-3 bg-[var(--tavus-atomic-glow-1)] border border-[var(--tavus-terminal-black)]" />
          <div className="absolute bottom-3 right-3 w-3 h-3 bg-[var(--tavus-floppy-fog-3)] border border-[var(--tavus-terminal-black)]" />

          <div className="relative">
            <div className="inline-flex items-center gap-2 mb-5">
              <span className="w-2 h-2 bg-[var(--tavus-terminal-black)]" />
              <span className="text-[11px] font-bold tracking-[0.25em] uppercase text-[var(--tavus-hardware-gray-8)]">
                START BUILDING
              </span>
              <span className="w-2 h-2 bg-[var(--tavus-terminal-black)]" />
            </div>

            <h2 className="font-[var(--font-serif-display)] text-4xl sm:text-6xl lg:text-7xl font-normal tracking-tight text-[var(--tavus-terminal-black)] leading-[1.05]">
              Configure your first agent in{" "}
              <span className="serif-italic">less than 5 minutes</span>
            </h2>

            <p className="mt-5 text-base sm:text-lg text-[var(--tavus-hardware-gray-8)] max-w-2xl mx-auto leading-relaxed">
              Create an account, connect your WhatsApp / Facebook / Instagram, train your agent on your old chats, and ship your first reply before your coffee gets cold. No API, no developer setup — everything&apos;s on the Zemest platform.
            </p>

            <div className="mt-9 flex flex-col sm:flex-row items-center justify-center gap-3">
              <a
                href="/get-started"
                className="inline-flex items-center gap-2 px-7 h-12 border-2 border-[var(--tavus-terminal-black)] bg-[var(--tavus-bubbletech-4)] text-xs font-bold tracking-[0.08em] uppercase shadow-[4px_4px_0_0_var(--tavus-terminal-black)] hover:shadow-[6px_6px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] transition-all"
              >
                Get started
                <ArrowUpRight className="w-4 h-4" />
              </a>
              <a
                href="/book-demo"
                className="inline-flex items-center gap-2 px-7 h-12 border-2 border-[var(--tavus-terminal-black)] bg-white text-xs font-bold tracking-[0.08em] uppercase shadow-[4px_4px_0_0_var(--tavus-terminal-black)] hover:shadow-[6px_6px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] transition-all"
              >
                Talk to sales
              </a>
            </div>

            <div className="mt-7 flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-[11px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)]">
              <span className="flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 bg-[var(--tavus-neon-field-2)]" />
                14-day free trial
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 bg-[var(--tavus-neon-field-2)]" />
                SOC 2 Type II
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 bg-[var(--tavus-neon-field-2)]" />
                Cancel anytime
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 bg-[var(--tavus-neon-field-2)]" />
                24/7 support
              </span>
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  );
}
