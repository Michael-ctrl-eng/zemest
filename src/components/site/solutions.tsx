"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  TrendingUp,
  HeartPulse,
  UserCheck,
  GraduationCap,
  Boxes,
  ArrowUpRight,
} from "lucide-react";
import { cn } from "@/lib/utils";

const solutions = [
  {
    id: "sales",
    icon: TrendingUp,
    label: "Sales Agents",
    headline: "Convert more by talking face-to-face",
    desc:
      "Agents handle inbound demos and outbound follow-ups in real-time. They reference each prospect's company, role, and pain point — and book meetings before the conversation ends.",
    stats: [
      { v: "3.2×", k: "reply rate" },
      { v: "47%", k: "meeting lift" },
      { v: "24/7", k: "always on" },
    ],
    accent: "from-violet-500 to-purple-600",
    accentText: "text-violet-300",
    scenario: {
      tag: "Outbound · SDR",
      to: "sam.rivera@acme.io",
      line: "Hey Sam — saw your team just shipped analytics. Want me to walk you through a fit in 30s?",
    },
  },
  {
    id: "healthcare",
    icon: HeartPulse,
    label: "Healthcare Agents",
    headline: "Deliver better patient care",
    desc:
      "Agents take intake at the patient's own pace, in their language, and hand the clinician a clear picture before anyone walks into the room. Compliance, privacy, and empathy built in.",
    stats: [
      { v: "+24pt", k: "patient CSAT" },
      { v: "-38%", k: "intake time" },
      { v: "30+", k: "languages" },
    ],
    accent: "from-rose-500 to-pink-600",
    accentText: "text-rose-300",
    scenario: {
      tag: "Intake · Pre-visit",
      to: "patient · case #48213",
      line: "Hi Marcus — before your appointment, can you describe where the discomfort is? Take your time.",
    },
  },
  {
    id: "interview",
    icon: UserCheck,
    label: "Interview Agents",
    headline: "Screen candidates at scale, fairly",
    desc:
      "Every candidate gets the same structured interview. Agents score consistently, eliminate scheduling friction, and free your team to focus on finalists.",
    stats: [
      { v: "10×", k: "throughput" },
      { v: "+18pt", k: "diversity" },
      { v: "100%", k: "consistency" },
    ],
    accent: "from-fuchsia-500 to-purple-600",
    accentText: "text-fuchsia-300",
    scenario: {
      tag: "Screening · Round 1",
      to: "candidate · backend eng",
      line: "Walk me through a system you designed end-to-end. I'll follow up with questions as you go.",
    },
  },
  {
    id: "lnd",
    icon: GraduationCap,
    label: "L&D Agents",
    headline: "Onboarding that adapts to every learner",
    desc:
      "Replace static LMS videos with interactive agent instructors. Learners ask questions aloud, the agent answers in real-time using approved knowledge bases — every cohort gets a personal mentor.",
    stats: [
      { v: "+38%", k: "completion" },
      { v: "-54%", k: "time-to-competency" },
      { v: "24/7", k: "mentor" },
    ],
    accent: "from-purple-500 to-indigo-600",
    accentText: "text-purple-300",
    scenario: {
      tag: "Onboarding · New hire",
      to: "newhire · week 1",
      line: "Welcome Priya — let's walk through your first week. Ask me anything about benefits, security, or your team.",
    },
  },
  {
    id: "custom",
    icon: Boxes,
    label: "Custom Agents",
    headline: "Bespoke agents built around your workflow",
    desc:
      "Bring us any use case — from internal IT helpdesk to field-service diagnostics. We design, build, and tune an agent around your exact workflow, then run it in production at the scale your business requires.",
    stats: [
      { v: "1:1", k: "tailored" },
      { v: "SLA", k: "guaranteed" },
      { v: "∞", k: "use cases" },
    ],
    accent: "from-violet-500 to-fuchsia-600",
    accentText: "text-violet-300",
    scenario: {
      tag: "Custom · Your workflow",
      to: "any use case",
      line: "Tell us the moment that matters most — we'll craft an agent that fits it, end to end.",
    },
  },
];

export function Solutions() {
  const [active, setActive] = useState(0);
  const s = solutions[active];

  return (
    <section id="solutions" className="relative py-24 sm:py-32 border-t border-border/40">
      <div className="absolute top-0 left-1/2 -translate-x-1/2 h-72 w-[700px] bg-accent/10 blur-[120px] rounded-full opacity-60" />
      <div className="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="max-w-3xl">
          <span className="inline-flex items-center gap-2 rounded-full border border-border/60 bg-secondary/40 px-3 py-1 text-xs font-medium text-muted-foreground">
            Solutions
          </span>
          <h2 className="mt-5 text-3xl sm:text-5xl lg:text-6xl font-semibold tracking-tight text-foreground">
            Infinite use cases built
            <br />
            <span className="text-gradient">for infinite scale</span>
          </h2>
          <p className="mt-6 text-base sm:text-lg text-muted-foreground leading-relaxed">
            An agent can be whatever the moment calls for: a teammate, an onboarding
            guide, a customer expert, or a trusted companion. Here are a few
            ways organizations are putting them to work.
          </p>
        </div>

        {/* Tabs */}
        <div className="mt-12 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2 sm:gap-3">
          {solutions.map((u, i) => (
            <button
              key={u.id}
              onClick={() => setActive(i)}
              className={cn(
                "group relative flex items-center gap-2.5 rounded-xl border px-4 py-3.5 text-sm font-medium transition-all",
                active === i
                  ? "border-accent/50 bg-accent/10 text-foreground"
                  : "border-border/50 bg-card/40 text-muted-foreground hover:text-foreground hover:border-border"
              )}
            >
              <u.icon
                className={cn(
                  "h-4 w-4 transition-colors",
                  active === i ? "text-accent" : "text-muted-foreground group-hover:text-foreground"
                )}
              />
              <span className="text-xs sm:text-sm leading-tight">{u.label}</span>
            </button>
          ))}
        </div>

        {/* Active panel */}
        <AnimatePresence mode="wait">
          <motion.div
            key={s.id}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -12 }}
            transition={{ duration: 0.3 }}
            className="mt-8 grid grid-cols-1 lg:grid-cols-2 gap-6"
          >
            {/* Left: copy + stats */}
            <div className="rounded-2xl border border-border/60 bg-card/40 p-8">
              <div className={`inline-flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br ${s.accent} shadow-lg`}>
                <s.icon className="h-5 w-5 text-white" />
              </div>
              <h3 className="mt-5 text-2xl font-semibold text-foreground">{s.headline}</h3>
              <p className="mt-3 text-sm text-muted-foreground leading-relaxed">
                {s.desc}
              </p>

              <div className="mt-7 grid grid-cols-3 gap-3">
                {s.stats.map((st) => (
                  <div key={st.k} className="rounded-lg bg-secondary/50 border border-border/40 p-3">
                    <div className="text-xl sm:text-2xl font-semibold text-foreground">{st.v}</div>
                    <div className="text-[11px] text-muted-foreground mt-0.5">{st.k}</div>
                  </div>
                ))}
              </div>

              <a
                href="#"
                className="mt-7 inline-flex items-center gap-1.5 text-sm font-medium text-accent hover:gap-2.5 transition-all"
              >
                See {s.label} in action <ArrowUpRight className="h-4 w-4" />
              </a>
            </div>

            {/* Right: video preview mockup */}
            <div className="relative rounded-2xl border border-border/60 bg-gradient-to-br from-[#15102a] to-[#0a0818] overflow-hidden">
              <div className={`absolute -top-20 -right-20 h-60 w-60 rounded-full bg-gradient-to-br ${s.accent} opacity-25 blur-3xl`} />
              <div className="flex items-center gap-2 px-4 py-3 border-b border-border/40 bg-secondary/40 backdrop-blur">
                <div className="flex gap-1.5">
                  <div className="h-2.5 w-2.5 rounded-full bg-red-400/70" />
                  <div className="h-2.5 w-2.5 rounded-full bg-yellow-400/70" />
                  <div className="h-2.5 w-2.5 rounded-full bg-green-400/70" />
                </div>
                <span className="ml-2 text-[11px] text-muted-foreground">{s.scenario.tag}</span>
                <span className="ml-auto inline-flex items-center gap-1.5 text-[11px] text-muted-foreground">
                  <span className="h-1.5 w-1.5 rounded-full bg-accent" />
                  to: {s.scenario.to}
                </span>
              </div>

              <div className="relative aspect-video bg-gradient-to-br from-[#1a1430] to-[#0c0a1f]">
                <div className="absolute inset-0 flex items-center justify-center">
                  <div className="relative">
                    <div className={`absolute inset-0 -m-8 rounded-full bg-gradient-to-br ${s.accent} opacity-30 blur-2xl`} />
                    <div className={`relative h-28 w-28 rounded-full bg-gradient-to-br ${s.accent} flex items-center justify-center shadow-2xl animate-breathe`}>
                      <s.icon className="h-12 w-12 text-white" />
                    </div>
                    <div className="absolute -inset-2 rounded-full border border-white/10" />
                  </div>
                </div>

                <div className="absolute inset-x-4 bottom-4">
                  <div className="rounded-lg bg-black/60 backdrop-blur px-3 py-2 text-xs text-white/95 font-medium leading-snug">
                    {s.scenario.line}
                  </div>
                </div>

                <div className="absolute top-3 left-3 inline-flex items-center gap-1.5 rounded-full bg-red-500/90 px-2 py-0.5 text-[10px] font-semibold text-white">
                  <span className="h-1 w-1 rounded-full bg-white animate-pulse" /> LIVE
                </div>
                <div className="absolute top-3 right-3 inline-flex items-center gap-1.5 rounded-full bg-black/60 backdrop-blur px-2 py-0.5 text-[10px] text-white/90">
                  4K · 60fps
                </div>
              </div>

              <div className="px-4 py-3 border-t border-border/40 bg-secondary/30 flex items-center gap-2">
                <div className="text-[10px] text-muted-foreground">0:00</div>
                <div className="flex-1 h-1 rounded-full bg-secondary overflow-hidden">
                  <div className="h-full w-1/3 bg-gradient-to-r from-accent to-foreground rounded-full" />
                </div>
                <div className="text-[10px] text-muted-foreground">0:24</div>
              </div>
            </div>
          </motion.div>
        </AnimatePresence>
      </div>
    </section>
  );
}
