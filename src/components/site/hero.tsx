"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { ArrowRight, Phone, X } from "lucide-react";
import { AgentChatModal } from "@/components/site/agent-chat-modal";

/**
 * Instant-paint hero imagery.
 *
 * 1. LQIP below is a 0.4KB blurred JPEG embedded in the JS bundle — it paints
 *    with the very first render, BEFORE fonts/text resolve (the user asked for
 *    "image visible before text").
 * 2. The real AVIFs are pre-optimized static files (81KB bg / 97KB live) served
 *    directly from /public — no /_next/image optimizer hop — and the bg is
 *    preloaded from <head> with fetchpriority=high so it starts downloading
 *    before any CSS/JS finishes parsing.
 */
const HERO_LQIP =
  "data:image/jpeg;base64,/9j/2wBDABQODxIPDRQSEBIXFRQYHjIhHhwcHj0sLiQySUBMS0dARkVQWnNiUFVtVkVGZIhlbXd7gYKBTmCNl4x9lnN+gXz/2wBDARUXFx4aHjshITt8U0ZTfHx8fHx8fHx8fHx8fHx8fHx8fHx8fHx8fHx8fHx8fHx8fHx8fHx8fHx8fHx8fHx8fHz/wAARCAAQABgDASIAAhEBAxEB/8QAGAAAAwEBAAAAAAAAAAAAAAAAAAEDAgX/xAAXEAEBAQEAAAAAAAAAAAAAAAAAAgED/8QAFwEAAwEAAAAAAAAAAAAAAAAAAQIDBP/EABQRAQAAAAAAAAAAAAAAAAAAAAD/2gAMAwEAAhEDEQA/AOfnJmuamdCq8a00dgHVgSv/2Q==";

export function Hero() {
  const [chatOpen, setChatOpen] = useState(false);
  return (
    <section className="relative overflow-hidden border-b-2 border-[var(--tavus-terminal-black)] -mt-[80px] pt-[80px] z-0">
      {/* Preload the hero background before anything else parses */}
      <link rel="preload" as="image" href="/zemest-hero-bg.avif" fetchPriority="high" />

      {/* Uploaded background image — LQIP paints instantly, AVIF covers it */}
      <img
        src="/zemest-hero-bg.avif"
        alt=""
        aria-hidden="true"
        width={1536}
        height={1024}
        fetchPriority="high"
        decoding="async"
        sizes="100vw"
        className="absolute inset-0 w-full h-full object-cover"
        style={{ backgroundImage: `url(${HERO_LQIP})`, backgroundSize: "cover", backgroundPosition: "center" }}
      />
      {/* Dark gradient overlay — stronger where the copy sits (left) */}
      <div className="absolute inset-0 bg-gradient-to-r from-[var(--tavus-terminal-black)]/80 via-[var(--tavus-terminal-black)]/55 to-[var(--tavus-terminal-black)]/35" />
      <div className="absolute inset-x-0 bottom-0 h-24 bg-gradient-to-t from-[var(--tavus-terminal-black)]/60 to-transparent" />
      {/* Premium bitmap dot grain texture */}
      <div
        className="absolute inset-0 opacity-20 pointer-events-none mix-blend-overlay"
        style={{
          backgroundImage:
            "radial-gradient(circle at 1px 1px, rgba(255, 255, 255, 0.4) 1px, transparent 0)",
          backgroundSize: "8px 8px",
        }}
      />

      {/* Floating hand illustrations */}
      <img
        src="/tavus-hand-left.avif"
        alt=""
        aria-hidden="true"
        width={180}
        height={220}
        decoding="async"
        className="hidden lg:block absolute top-4 left-0 w-32 h-auto opacity-90 animate-float-soft pointer-events-none -rotate-3 z-10"
      />
      <img
        src="/tavus-hand-right.avif"
        alt=""
        aria-hidden="true"
        width={160}
        height={200}
        decoding="async"
        className="hidden lg:block absolute bottom-12 right-0 w-28 h-auto opacity-90 animate-float-soft-2 pointer-events-none rotate-6 z-10"
      />

      <div className="mx-auto max-w-[1400px] px-5 sm:px-8 py-12 sm:py-16 lg:py-20 relative">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-12 items-center">
          {/* Left column - copy */}
          <div className="lg:col-span-5 lg:pr-4">
            <motion.h1
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6 }}
              className="font-[var(--font-serif-display)] text-[44px] sm:text-[58px] lg:text-[76px] leading-[1.02] font-normal tracking-tight text-white"
            >
              <span className="font-jersey text-[var(--tavus-signal-green)] block text-[40px] sm:text-[52px] lg:text-[64px] mb-2">
                Commerce just got an agent.
              </span>
              Your customers won&apos;t know it&apos;s{" "}
              <span className="serif-italic text-[var(--tavus-bubbletech-1)]">not you.</span>
              <span className="inline-block w-[3px] h-[0.85em] bg-white ml-1 align-middle animate-pulse" />
            </motion.h1>

            <motion.p
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.08 }}
              className="mt-6 text-base sm:text-lg text-white/85 leading-relaxed max-w-md font-[var(--font-serif-display)]"
            >
              Ready-made AI agents that <strong className="font-bold text-white">moderate</strong>{" "}
              your <strong className="font-bold text-white">WhatsApp</strong>,{" "}
              <strong className="font-bold text-white">Facebook</strong>, and{" "}
              <strong className="font-bold text-white">Instagram</strong> chats, replying like the buyer themselves. They read{" "}
              <span className="font-bold text-[var(--tavus-bubbletech-1)]">text</span>,{" "}
              <span className="font-bold text-[var(--tavus-bubbletech-1)]">voice</span>, and{" "}
              <span className="font-bold text-[var(--tavus-bubbletech-1)]">images</span>, check inventory, and close the sale.
            </motion.p>

            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.14 }}
              className="mt-8"
            >
              <a
                href="/get-started"
                className="inline-flex items-center gap-2 px-6 h-12 border-2 border-[var(--tavus-terminal-black)] bg-[var(--tavus-bubbletech-4)] text-xs font-bold tracking-[0.08em] uppercase shadow-[4px_4px_0_0_var(--tavus-terminal-black)] hover:shadow-[6px_6px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] transition-all"
              >
                Start building
                <ArrowRight className="h-3.5 w-3.5" />
              </a>
            </motion.div>
          </div>

          {/* Right column - live agent window */}
          <div className="lg:col-span-7 relative">
            <HeroWindows onTalkToAgent={() => setChatOpen(true)} />
          </div>
        </div>
      </div>

      {/* Instagram-styled demo chat — opens from TALK TO AGENT */}
      <AgentChatModal open={chatOpen} onClose={() => setChatOpen(false)} />

      <div className="absolute bottom-0 inset-x-0 h-[3px] bg-[var(--tavus-terminal-black)]" />
    </section>
  );
}

function HeroWindows({ onTalkToAgent }: { onTalkToAgent: () => void }) {
  return (
    <div className="relative h-[480px] sm:h-[540px] lg:h-[600px] flex items-center justify-center">
      {/* LIVE MODERATION window (single hero window, centered, slight rotate) */}
      <motion.div
        initial={{ opacity: 0, y: 20, rotate: 2 }}
        animate={{ opacity: 1, y: 0, rotate: 1.25 }}
        transition={{ duration: 0.7, delay: 0.2 }}
        className="relative w-[92%] sm:w-[520px] bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[8px_8px_0_0_var(--tavus-terminal-black)]"
      >
        <div className="win-title-bar">
          <span className="w-2.5 h-2.5 bg-[var(--tavus-signal-green)] border border-[var(--tavus-terminal-black)]" />
          <span>LIVE MODERATION</span>
          <span className="ml-auto flex gap-1">
            <span className="w-2.5 h-2.5 border border-[var(--tavus-terminal-black)]" />
            <span className="w-2.5 h-2.5 border border-[var(--tavus-terminal-black)]" />
            <span className="w-2.5 h-2.5 border border-[var(--tavus-terminal-black)] flex items-center justify-center">
              <X className="w-2 h-2" />
            </span>
          </span>
        </div>
        <div className="relative aspect-[4/3] overflow-hidden bg-black">
          <img
            src="/zemest-hero-window-live.avif"
            alt="Zemest agent — always on, replying in Arabic and English"
            width={960}
            height={720}
            loading="eager"
            fetchPriority="high"
            decoding="async"
            sizes="(max-width: 768px) 92vw, 520px"
            className="absolute inset-0 w-full h-full object-cover"
            style={{ backgroundImage: `url(${HERO_LQIP})`, backgroundSize: "cover", backgroundPosition: "center" }}
          />
          <div className="absolute top-3 left-3 inline-flex items-center gap-1.5 bg-[var(--tavus-terminal-black)] text-white px-2 py-1 text-[10px] font-bold tracking-wider uppercase">
            <span className="w-1.5 h-1.5 bg-[var(--tavus-signal-green)] rounded-full animate-pulse" />
            ONLINE
          </div>
          <div className="absolute top-3 right-3 bg-white border-2 border-[var(--tavus-terminal-black)] px-1.5 py-0.5 text-[10px] font-bold tracking-wider">
            AR · EN
          </div>
          <button
            onClick={onTalkToAgent}
            className="absolute bottom-3 right-3 inline-flex items-center gap-1.5 px-3 h-9 border-2 border-[var(--tavus-terminal-black)] bg-[var(--tavus-neon-field-2)] text-white text-[10px] font-bold tracking-wider uppercase shadow-[2px_2px_0_0_var(--tavus-terminal-black)] hover:shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-0.5 active:translate-y-0.5 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] transition-all cursor-pointer"
          >
            <Phone className="w-3 h-3" />
            TALK TO AGENT
          </button>
        </div>
      </motion.div>

      {/* Floating small stat card */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.7 }}
        className="absolute bottom-4 left-0 sm:left-4 bg-white border-2 border-[var(--tavus-terminal-black)] shadow-[3px_3px_0_0_var(--tavus-terminal-black)] p-3 animate-float-soft z-20"
      >
        <div className="text-[10px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)]">
          Reply
        </div>
        <div className="text-2xl font-bold font-[var(--font-serif-display)] text-[var(--tavus-terminal-black)] leading-tight">
          &gt;3s
        </div>
        <div className="text-[10px] text-[var(--tavus-terminal-black)] flex items-center gap-1 mt-0.5">
          <span className="w-1.5 h-1.5 bg-[var(--tavus-neon-field-2)]" />
          Real-time
        </div>
      </motion.div>
    </div>
  );
}
