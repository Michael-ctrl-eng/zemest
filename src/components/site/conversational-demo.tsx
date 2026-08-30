"use client";

import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import Image from "next/image";
import { Phone, PhoneOff, Mic, Volume2, X } from "lucide-react";

type Msg = { role: "user" | "ai"; text: string; lang: "ar" | "en" };

const script: Msg[] = [
  { role: "user", text: "Hey, do you have the white Air Max in size 10?", lang: "en" },
  { role: "ai", text: "Yep — 2 left in stock. $120. Want me to hold one for you?", lang: "en" },
  { role: "user", text: "لو سمحت، عندك النايك الأبيض مقاس 42؟", lang: "ar" },
  { role: "ai", text: "أيوا متوفر، 2 pieces في المخزن. 850 جنيه. تحب أثبتهولك؟", lang: "ar" },
  { role: "user", text: "Send me a pic of the black ones too?", lang: "en" },
  { role: "ai", text: "Here are 3 black Air Max in size 10, also $120. Want both?", lang: "en" },
];

export function ConversationalDemo() {
  const [playing, setPlaying] = useState(false);
  const [idx, setIdx] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!playing) return;
    timer.current = setInterval(() => {
      setElapsed((e) => e + 1);
      setIdx((i) => (i + 1) % (script.length + 1));
    }, 2400);
    return () => {
      if (timer.current) clearInterval(timer.current);
    };
  }, [playing]);

  const visible = script.slice(0, Math.min(idx, script.length));

  return (
    <section id="conversational" className="bg-grain-tan border-b-2 border-[var(--tavus-terminal-black)] py-16 sm:py-24">
      <div className="mx-auto max-w-[1400px] px-5 sm:px-8">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
          {/* Left copy */}
          <div>
            <div className="inline-flex items-center gap-2 mb-5">
              <span className="w-2 h-2 bg-[var(--tavus-terminal-black)]" />
              <span className="text-[11px] font-bold tracking-[0.15em] uppercase">LIVE MODERATION</span>
            </div>
            <h2 className="font-[var(--font-serif-display)] text-4xl sm:text-5xl lg:text-6xl font-normal tracking-tight text-[var(--tavus-terminal-black)] leading-[1.05]">
              What if your customer couldn&apos;t tell it&apos;s{" "}
              <span className="serif-italic">an agent?</span>
            </h2>
            <p className="mt-6 text-base sm:text-lg text-[var(--tavus-hardware-gray-8)] leading-relaxed max-w-xl">
              Replies in the same dialect, the same tone, the same shorthand. Reads text, listens to voice, looks at images — answers like you would, in &lt;3 seconds.
            </p>

            <ul className="mt-7 space-y-2.5">
              {[
                "Replies in <3 seconds, 24/7",
                "Arabic + English, every dialect",
                "Reads voice notes, images, and text",
                "Live inventory check before every reply",
              ].map((t) => (
                <li key={t} className="flex items-start gap-3 text-sm text-[var(--tavus-terminal-black)]">
                  <span className="mt-1.5 w-2 h-2 bg-[var(--tavus-terminal-black)] shrink-0" />
                  <span>{t}</span>
                </li>
              ))}
            </ul>

            <button
              onClick={() => {
                setIdx(0);
                setElapsed(0);
                setPlaying((v) => !v);
              }}
              className="mt-8 inline-flex items-center gap-2 px-5 h-11 border-2 border-[var(--tavus-terminal-black)] bg-[var(--tavus-neon-field-2)] text-white text-[11px] font-bold tracking-wider uppercase shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:shadow-[4px_4px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] transition-all"
            >
              {playing ? (
                <>
                  <PhoneOff className="w-3.5 h-3.5" /> END CONVERSATION
                </>
              ) : (
                <>
                  <Phone className="w-3.5 h-3.5" /> START A DEMO CONVERSATION
                </>
              )}
            </button>
          </div>

          {/* Right demo UI */}
          <div className="relative">
            <div className="bg-white border-2 border-[var(--tavus-terminal-black)] shadow-[8px_8px_0_0_var(--tavus-terminal-black)] overflow-hidden">
              <div className="win-title-bar">
                <span className="w-2.5 h-2.5 bg-[var(--tavus-bubbletech-4)] border border-[var(--tavus-terminal-black)]" />
                <span>WHATSAPP · LIVE MODERATION</span>
                <span className="ml-auto flex gap-1">
                  <span className="w-2.5 h-2.5 border border-[var(--tavus-terminal-black)]" />
                  <span className="w-2.5 h-2.5 border border-[var(--tavus-terminal-black)]" />
                  <span className="w-2.5 h-2.5 border border-[var(--tavus-terminal-black)] flex items-center justify-center">
                    <X className="w-2 h-2" />
                  </span>
                </span>
              </div>

              {/* Video area */}
              <div className="relative aspect-[4/3] bg-[var(--tavus-terminal-black)] overflow-hidden">
                {/* Premium bitmap scanline texture */}
                <div className="absolute inset-0 opacity-25 pointer-events-none z-10" style={{
                  backgroundImage: 'repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(56,242,97,0.1) 2px, rgba(56,242,97,0.1) 3px)'
                }} />
                <div className="absolute inset-0 flex items-center justify-center">
                  <div className="relative">
                    {playing && (
                      <div className="absolute -inset-8 rounded-full bg-[var(--tavus-neon-field-2)] text-white/30 blur-2xl animate-pulse" />
                    )}
                    <div
                      className={`relative h-28 w-28 rounded-full bg-[var(--tavus-bubbletech-4)] border-2 border-[var(--tavus-terminal-black)] flex items-center justify-center shadow-[4px_4px_0_0_var(--tavus-terminal-black)] ${
                        playing ? "animate-pulse" : ""
                      }`}
                    >
                      <Image
                        src="/zemest-logo.png"
                        alt="Zemest"
                        width={48}
                        height={48}
                        className="w-12 h-12"
                      />
                    </div>
                    {playing && (
                      <div className="absolute -bottom-9 left-1/2 -translate-x-1/2 flex items-end gap-1 h-7 bg-white border-2 border-[var(--tavus-terminal-black)] px-2 py-1.5">
                        {[0.4, 0.7, 0.5, 0.9, 0.6, 0.8, 0.5, 0.7, 0.4].map((h, i) => (
                          <motion.span
                            key={i}
                            className="w-0.5 bg-[var(--tavus-terminal-black)]"
                            animate={{ height: [`${h * 6}px`, `${h * 20}px`, `${h * 6}px`] }}
                            transition={{ duration: 0.6 + i * 0.05, repeat: Infinity, ease: "easeInOut" }}
                          />
                        ))}
                      </div>
                    )}
                  </div>
                </div>

                <div className="absolute top-3 left-3 inline-flex items-center gap-1.5 bg-white border-2 border-[var(--tavus-terminal-black)] px-2 py-1 text-[10px] font-bold tracking-wider uppercase">
                  <span className={`w-1.5 h-1.5 ${playing ? "bg-[var(--tavus-bubbletech-4)] animate-pulse" : "bg-[var(--tavus-hardware-gray-8)]"}`} />
                  {playing ? `LIVE · 00:0${Math.min(9, Math.floor(elapsed / 2))}` : "READY"}
                </div>

                <div className="absolute bottom-3 right-3 h-20 w-28 border-2 border-[var(--tavus-terminal-black)] bg-white overflow-hidden">
                  <div className="h-full w-full bg-gradient-to-br from-[var(--tavus-floppy-fog-3)] to-[var(--tavus-floppy-fog-4)] flex items-center justify-center">
                    <span className="font-[var(--font-serif-display)] text-2xl font-normal text-[var(--tavus-terminal-black)]">U</span>
                  </div>
                </div>
              </div>

              {/* Transcript */}
              <div className="h-40 p-3 border-t-2 border-[var(--tavus-terminal-black)] overflow-y-auto scrollbar-thin bg-[var(--tavus-plastic-1)] space-y-2">
                {visible.length === 0 && (
                  <div className="text-center text-xs text-[var(--tavus-hardware-gray-8)] mt-12">
                    Press <span className="font-bold">START A DEMO CONVERSATION</span> to begin.
                  </div>
                )}
                <AnimatePresence initial={false}>
                  {visible.map((m, i) => (
                    <motion.div
                      key={i}
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      className={`flex gap-2 ${m.role === "user" ? "justify-end" : "justify-start"}`}
                    >
                      <div
                        className={`max-w-[80%] border-2 border-[var(--tavus-terminal-black)] px-3 py-1.5 text-xs leading-relaxed ${
                          m.role === "user"
                            ? "bg-[var(--tavus-bubbletech-1)]"
                            : "bg-white"
                        } ${m.lang === "ar" ? "text-right" : "text-left"}`}
                        dir={m.lang === "ar" ? "rtl" : "ltr"}
                      >
                        {m.text}
                      </div>
                    </motion.div>
                  ))}
                </AnimatePresence>
              </div>

              {/* Control bar */}
              <div className="flex items-center gap-2 px-3 py-2 border-t-2 border-[var(--tavus-terminal-black)] bg-white">
                <button className="w-7 h-7 border-2 border-[var(--tavus-terminal-black)] flex items-center justify-center hover:bg-[var(--tavus-plastic-2)] active:translate-y-0.5 transition-all">
                  <Volume2 className="w-3.5 h-3.5" />
                </button>
                <button className="w-7 h-7 border-2 border-[var(--tavus-terminal-black)] flex items-center justify-center hover:bg-[var(--tavus-plastic-2)] active:translate-y-0.5 transition-all">
                  <Mic className="w-3.5 h-3.5" />
                </button>
                <div className="ml-auto text-[10px] font-mono text-[var(--tavus-hardware-gray-8)]">
                  Reply <span className="font-bold text-[var(--tavus-terminal-black)]">&lt;3s</span>
                </div>
                <button
                  onClick={() => setPlaying((v) => !v)}
                  className={`w-9 h-9 border-2 border-[var(--tavus-terminal-black)] flex items-center justify-center transition-all active:translate-x-0.5 active:translate-y-0.5 ${
                    playing
                      ? "bg-[var(--tavus-bubbletech-4)]"
                      : "bg-[var(--tavus-neon-field-2)] text-white"
                  }`}
                >
                  {playing ? <PhoneOff className="w-3.5 h-3.5" /> : <Phone className="w-3.5 h-3.5" />}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
