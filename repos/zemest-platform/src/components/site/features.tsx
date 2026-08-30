"use client";

import { motion } from "framer-motion";
import {
  Sparkles,
  Zap,
  Video,
  Globe,
  Code2,
  GitBranch,
  ShieldCheck,
} from "lucide-react";

const features = [
  {
    icon: Sparkles,
    title: "Phoenix-3 model",
    desc: "The most expressive AI video model — natural micro-expressions, accurate lip-sync, and emotional delivery that rivals studio footage.",
    accent: "from-violet-500 to-purple-600",
    size: "lg",
  },
  {
    icon: Zap,
    title: "Real-time rendering",
    desc: "Stream responses in <1s with our edge rendering engine built for low-latency dialogue.",
    accent: "from-fuchsia-500 to-pink-600",
    size: "sm",
  },
  {
    icon: Video,
    title: "Personalized at scale",
    desc: "Generate millions of 1:1 video variants from a single template — names, offers, and scenes swapped automatically.",
    accent: "from-purple-500 to-indigo-600",
    size: "sm",
  },
  {
    icon: Globe,
    title: "30+ languages",
    desc: "Native-quality delivery across global languages with region-appropriate intonation and cadence.",
    accent: "from-violet-500 to-blue-600",
    size: "sm",
  },
  {
    icon: Code2,
    title: "Developer-first API",
    desc: "Drop video generation into your stack with a few lines of code. Webhooks, SDKs, and SOC 2 Type II compliance included.",
    accent: "from-pink-500 to-rose-600",
    size: "lg",
  },
];

export function Features() {
  return (
    <section id="platform" className="relative py-24 sm:py-32">
      <div className="absolute inset-0 bg-radial-purple opacity-50" />
      <div className="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="max-w-3xl">
          <span className="inline-flex items-center gap-2 rounded-full border border-border/60 bg-secondary/40 px-3 py-1 text-xs font-medium text-muted-foreground">
            <Sparkles className="h-3.5 w-3.5 text-accent" />
            The platform
          </span>
          <h2 className="mt-5 text-3xl sm:text-5xl font-semibold tracking-tight text-white">
            Everything you need to build
            <br />
            <span className="text-gradient">with AI video</span>
          </h2>
          <p className="mt-5 text-base sm:text-lg text-muted-foreground leading-relaxed">
            One platform for generating, personalizing, and streaming
            human-quality video. Train your replica in minutes and ship to
            production the same day — no studio, no crew, no per-shoot costs.
          </p>
        </div>

        {/* Bento grid */}
        <div className="mt-14 grid grid-cols-1 md:grid-cols-3 gap-4 sm:gap-5">
          {features.map((f, i) => (
            <motion.div
              key={f.title}
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-80px" }}
              transition={{ duration: 0.5, delay: i * 0.05 }}
              className={`group relative overflow-hidden rounded-2xl border border-border/60 bg-card/60 backdrop-blur p-6 hover:border-primary/40 transition-all duration-300 ${
                f.size === "lg" ? "md:col-span-2" : ""
              }`}
            >
              {/* Hover glow */}
              <div className={`absolute inset-0 bg-gradient-to-br ${f.accent} opacity-0 group-hover:opacity-[0.08] transition-opacity duration-500`} />
              <div className={`absolute -top-12 -right-12 h-32 w-32 rounded-full bg-gradient-to-br ${f.accent} opacity-15 blur-2xl group-hover:opacity-25 transition-opacity duration-500`} />

              <div className="relative">
                <div className={`inline-flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br ${f.accent} shadow-lg`}>
                  <f.icon className="h-5 w-5 text-white" />
                </div>
                <h3 className="mt-5 text-lg font-semibold text-white">{f.title}</h3>
                <p className="mt-2 text-sm text-muted-foreground leading-relaxed">
                  {f.desc}
                </p>

                {f.size === "lg" && i === 0 && (
                  <div className="mt-6 grid grid-cols-3 gap-3">
                    {[
                      { k: "Lip-sync", v: "98.4%" },
                      { k: "Render", v: "2.4s" },
                      { k: "Languages", v: "30+" },
                    ].map((m) => (
                      <div key={m.k} className="rounded-lg bg-secondary/40 border border-border/40 p-3">
                        <div className="text-[11px] text-muted-foreground">{m.k}</div>
                        <div className="text-base font-semibold text-white mt-0.5">{m.v}</div>
                      </div>
                    ))}
                  </div>
                )}

                {f.size === "lg" && i === 4 && (
                  <pre className="mt-6 rounded-lg border border-border/40 bg-black/40 p-4 text-[11px] leading-relaxed overflow-x-auto scrollbar-thin">
                    <code className="text-white/90 font-mono">
                      <span className="text-pink-400">const</span> video = <span className="text-pink-400">await</span> tavus.videos.<span className="text-violet-300">create</span>({"{"}{"\n"}
                      {"  "}replica_id: <span className="text-emerald-300">"r_alex_01"</span>,{"\n"}
                      {"  "}script: <span className="text-emerald-300">"Hey {`{{name}}`}, congrats!"</span>,{"\n"}
                      {"  "}variables: {"{"} name: <span className="text-emerald-300">"Sam"</span> {"}"},{"\n"}
                      {"  "}resolution: <span className="text-emerald-300">"4k"</span>,{"\n"}
                      {"}"});
                    </code>
                  </pre>
                )}
              </div>
            </motion.div>
          ))}
        </div>

        {/* Trust badges */}
        <div className="mt-12 flex flex-wrap items-center justify-center gap-x-8 gap-y-3 text-xs text-muted-foreground">
          <span className="inline-flex items-center gap-1.5">
            <ShieldCheck className="h-3.5 w-3.5 text-accent" /> SOC 2 Type II
          </span>
          <span className="inline-flex items-center gap-1.5">
            <GitBranch className="h-3.5 w-3.5 text-accent" /> Versioned model APIs
          </span>
          <span className="inline-flex items-center gap-1.5">
            <Globe className="h-3.5 w-3.5 text-accent" /> GDPR & HIPAA ready
          </span>
          <span className="inline-flex items-center gap-1.5">
            <Code2 className="h-3.5 w-3.5 text-accent" /> 99.95% uptime SLA
          </span>
        </div>
      </div>
    </section>
  );
}
