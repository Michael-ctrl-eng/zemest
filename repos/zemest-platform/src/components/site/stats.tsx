"use client";

import { motion } from "framer-motion";
import { Users, Clock, Globe2, Film } from "lucide-react";

const stats = [
  { icon: Film, v: "10M+", k: "Videos generated monthly", sub: "across 70+ countries" },
  { icon: Clock, v: "2.4s", k: "Avg. render time", sub: "down from 4 min" },
  { icon: Globe2, v: "30+", k: "Languages supported", sub: "native-quality delivery" },
  { icon: Users, v: "500+", k: "Enterprise customers", sub: "including 12 of the F500" },
];

export function Stats() {
  return (
    <section className="relative py-20 sm:py-24 border-t border-border/40">
      <div className="absolute inset-0 bg-grid opacity-20" />
      <div className="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6">
          {stats.map((s, i) => (
            <motion.div
              key={s.k}
              initial={{ opacity: 0, y: 12 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-60px" }}
              transition={{ duration: 0.5, delay: i * 0.08 }}
              className="relative rounded-2xl border border-border/60 bg-card/40 backdrop-blur p-6 text-center overflow-hidden"
            >
              <div className="absolute -top-10 -right-10 h-24 w-24 rounded-full bg-primary/15 blur-2xl" />
              <s.icon className="h-6 w-6 text-accent mx-auto" />
              <div className="mt-4 text-3xl sm:text-4xl font-semibold text-gradient-purple">
                {s.v}
              </div>
              <div className="mt-1.5 text-sm font-medium text-foreground">{s.k}</div>
              <div className="text-[11px] text-muted-foreground mt-0.5">{s.sub}</div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
