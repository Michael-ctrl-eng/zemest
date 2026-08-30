"use client";

import { motion } from "framer-motion";
import { UserPlus, Mic2, Wand2, Rocket } from "lucide-react";

const steps = [
  {
    n: "01",
    icon: UserPlus,
    title: "Train your replica",
    desc: "Record a 2-minute video. Zemest trains a studio-grade replica of you — voice, face, expressions — in under 10 minutes.",
  },
  {
    n: "02",
    icon: Mic2,
    title: "Write or speak your script",
    desc: "Type a script, upload a doc, or speak live. Add variables like {{name}} for personalization at scale.",
  },
  {
    n: "03",
    icon: Wand2,
    title: "Render with Phoenix-3",
    desc: "Phoenix-3 generates your video in seconds — 4K, 60fps, with natural lip-sync and emotional delivery.",
  },
  {
    n: "04",
    icon: Rocket,
    title: "Ship to your stack",
    desc: "Embed, share, or trigger via API. Connect WhatsApp, Messenger, Instagram, or your own app with one webhook.",
  },
];

export function HowItWorks() {
  return (
    <section id="personalized" className="relative py-24 sm:py-32 border-t border-border/40">
      <div className="absolute top-1/2 -left-32 h-72 w-72 rounded-full bg-primary/15 blur-[100px] opacity-50" />
      <div className="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="max-w-3xl">
          <span className="inline-flex items-center gap-2 rounded-full border border-border/60 bg-secondary/40 px-3 py-1 text-xs font-medium text-muted-foreground">
            How it works
          </span>
          <h2 className="mt-5 text-3xl sm:text-5xl font-semibold tracking-tight text-white">
            From script to screen
            <br />
            <span className="text-gradient">in four steps</span>
          </h2>
          <p className="mt-5 text-base sm:text-lg text-muted-foreground leading-relaxed">
            No film crew, no editing software, no per-shoot costs. Zemest handles
            the entire pipeline from replica training to delivery — you just
            bring the message.
          </p>
        </div>

        <div className="mt-14 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
          {steps.map((s, i) => (
            <motion.div
              key={s.n}
              initial={{ opacity: 0, y: 14 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-60px" }}
              transition={{ duration: 0.5, delay: i * 0.08 }}
              className="relative group"
            >
              {/* Connector line */}
              {i < steps.length - 1 && (
                <div className="hidden lg:block absolute top-12 left-[60%] right-[-40%] h-px bg-gradient-to-r from-border/60 to-transparent" />
              )}

              <div className="relative rounded-2xl border border-border/60 bg-card/40 backdrop-blur p-6 h-full hover:border-primary/40 transition-colors">
                <div className="flex items-center justify-between">
                  <div className="inline-flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-primary/20 to-accent/20 border border-primary/30">
                    <s.icon className="h-5 w-5 text-accent" />
                  </div>
                  <span className="text-2xl font-semibold text-foreground/15">{s.n}</span>
                </div>
                <h3 className="mt-5 text-base font-semibold text-white">{s.title}</h3>
                <p className="mt-2 text-sm text-muted-foreground leading-relaxed">
                  {s.desc}
                </p>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
