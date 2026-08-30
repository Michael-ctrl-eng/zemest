"use client";

import { motion } from "framer-motion";
import { Quote, Star } from "lucide-react";

const testimonials = [
  {
    quote:
      "Zemest replaced an entire production pipeline. Our reps now ship personalized follow-ups within seconds of a call ending — and reply rates jumped 3×.",
    name: "Daniela Reyes",
    role: "VP Revenue Enablement",
    company: "NorthPeak",
    initials: "DR",
    accent: "from-violet-500 to-purple-600",
  },
  {
    quote:
      "We swapped our entire win-back program from static email to Zemest personalized video. CTR is up 62% and we recovered 1.4× more churned revenue in Q2.",
    name: "Marcus Lindqvist",
    role: "Head of Lifecycle",
    company: "Lumen Retail",
    initials: "ML",
    accent: "from-fuchsia-500 to-pink-600",
  },
  {
    quote:
      "Phoenix-3 is the first model our L&D team trusts in front of new hires. It answers questions live, in 7 languages, and never gets tired.",
    name: "Priya Iyer",
    role: "Director of People Ops",
    company: "Cadence Health",
    initials: "PI",
    accent: "from-purple-500 to-indigo-600",
  },
  {
    quote:
      "We built a full support concierge with Zemest in a week. CSAT jumped 24 points in 30 days — customers genuinely prefer it to chat.",
    name: "Jonas Berger",
    role: "VP Customer Experience",
    company: "Helio SaaS",
    initials: "JB",
    accent: "from-pink-500 to-rose-600",
  },
  {
    quote:
      "The developer API is shockingly simple. Three calls and we had personalized video flowing into our app. Webhooks, SDKs, docs — everything's first-class.",
    name: "Aisha Karim",
    role: "Staff Engineer",
    company: "Forge Labs",
    initials: "AK",
    accent: "from-violet-500 to-fuchsia-600",
  },
  {
    quote:
      "Our outbound SDRs were skeptical. After two weeks with Zemest they refused to go back. We're saving 8 hours per rep per week, easily.",
    name: "Tomás Oliveira",
    role: "Head of Sales Dev",
    company: "Beacon Cloud",
    initials: "TO",
    accent: "from-purple-500 to-violet-700",
  },
];

export function Testimonials() {
  return (
    <section id="testimonials" className="relative py-24 sm:py-32 border-t border-border/40">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="max-w-3xl">
          <span className="inline-flex items-center gap-2 rounded-full border border-border/60 bg-secondary/40 px-3 py-1 text-xs font-medium text-muted-foreground">
            <Star className="h-3.5 w-3.5 text-accent" />
            Customers
          </span>
          <h2 className="mt-5 text-3xl sm:text-5xl font-semibold tracking-tight text-white">
            Teams ship faster
            <br />
            <span className="text-gradient">with Zemest in their stack</span>
          </h2>
          <p className="mt-5 text-base sm:text-lg text-muted-foreground leading-relaxed">
            From scrappy startups to the Fortune 500 — see how teams are turning
            AI video into measurable business outcomes.
          </p>
        </div>

        <div className="mt-14 columns-1 md:columns-2 lg:columns-3 gap-5 [column-fill:_balance]">
          {testimonials.map((t, i) => (
            <motion.figure
              key={i}
              initial={{ opacity: 0, y: 12 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-60px" }}
              transition={{ duration: 0.45, delay: (i % 3) * 0.05 }}
              className="break-inside-avoid mb-5 rounded-2xl border border-border/60 bg-card/40 backdrop-blur p-6 hover:border-primary/40 transition-colors"
            >
              <Quote className="h-5 w-5 text-accent/70" />
              <blockquote className="mt-4 text-sm leading-relaxed text-foreground">
                {t.quote}
              </blockquote>
              <figcaption className="mt-5 flex items-center gap-3">
                <div className={`flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-br ${t.accent} text-white text-xs font-semibold`}>
                  {t.initials}
                </div>
                <div>
                  <div className="text-sm font-medium text-white">{t.name}</div>
                  <div className="text-xs text-muted-foreground">
                    {t.role} · {t.company}
                  </div>
                </div>
              </figcaption>
            </motion.figure>
          ))}
        </div>
      </div>
    </section>
  );
}
