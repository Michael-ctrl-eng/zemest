"use client";

import { useState } from "react";
import Link from "next/link";
import { Navbar } from "@/components/site/navbar";
import { Footer } from "@/components/site/footer";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { ArrowRight, Check, Minus, Zap, ShieldCheck, Sparkles } from "lucide-react";

export default function PricingPage() {
  const [annual, setAnnual] = useState(false);

  const tiers = [
    {
      name: "STARTER",
      tagline: "Try the magic",
      monthly: 0,
      annual: 0,
      period: annual ? "/year" : "/14 days",
      desc: "For solo sellers testing AI moderation on one channel.",
      features: [
        "1 channel — WhatsApp, Facebook, or Instagram",
        "Rabbit v1 (Arabic) or Rooster v1 (English)",
        "100 conversations / month",
        "Inventory Connect (1 shop)",
        "Community support",
      ],
      volume: 100,
      volumeLabel: "100 convos / mo",
      cta: "START FREE",
      ctaHref: "/get-started",
      highlight: false,
    },
    {
      name: "GROWTH",
      tagline: "Most sellers pick this",
      monthly: 99,
      annual: 79,
      period: annual ? "/mo billed yearly" : "/mo",
      desc: "For small teams selling across every channel their customers use.",
      features: [
        "3 channels — WhatsApp + Facebook + Instagram",
        "Both models (Rabbit v1 + Rooster v1)",
        "5,000 conversations / month",
        "Inventory Connect (3 shops)",
        "Custom brand tone & style learning",
        "Priority email support",
      ],
      volume: 5000,
      volumeLabel: "5,000 convos / mo",
      cta: "START GROWTH",
      ctaHref: "/get-started",
      highlight: true,
    },
    {
      name: "ENTERPRISE",
      tagline: "Scale without limits",
      monthly: -1,
      annual: -1,
      period: "",
      desc: "For high-volume brands with bespoke integration needs.",
      features: [
        "Unlimited channels & conversations",
        "Both models + custom training",
        "Inventory Connect (unlimited)",
        "Order API bridge & webhooks",
        "Dedicated CSM + 99.95% SLA",
        "On-prem / private cloud option",
      ],
      volume: -1,
      volumeLabel: "Unlimited",
      cta: "BOOK DEMO",
      ctaHref: "/book-demo",
      highlight: false,
    },
  ];

  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main>
        {/* ---------- HERO + TOGGLE ---------- */}
        <section className="relative bg-grain border-b-[3px] border-[var(--tavus-terminal-black)] overflow-hidden">
          <div className="absolute inset-0 bg-halftone-light opacity-10 pointer-events-none" />
          <div className="relative mx-auto max-w-[1200px] px-5 sm:px-8 pt-20 pb-14 text-center">
            <div className="inline-flex items-center gap-2 mb-5">
              <span className="w-2 h-2 bg-[var(--tavus-terminal-black)]" />
              <span className="text-[11px] font-bold tracking-[0.25em] uppercase text-[var(--tavus-hardware-gray-8)]">
                PRICING
              </span>
              <span className="w-2 h-2 bg-[var(--tavus-terminal-black)]" />
            </div>

            <h1 className="font-[var(--font-serif-display)] text-5xl sm:text-6xl font-normal tracking-tight text-[var(--tavus-terminal-black)] leading-[1.02]">
              Pricing built to <span className="serif-italic">scale</span> with you
            </h1>
            <p className="mt-5 mx-auto max-w-xl text-sm sm:text-[15px] text-[var(--tavus-hardware-gray-8)] leading-relaxed">
              Start free for 14 days — no credit card. Upgrade when your agent is already
              selling. Every plan includes the full dialect engine, voice, and image understanding.
            </p>

            {/* Billing toggle */}
            <div className="mt-8 inline-flex items-center gap-0 border-[3px] border-[var(--tavus-terminal-black)] bg-white shadow-[4px_4px_0_0_var(--tavus-terminal-black)]">
              <button
                onClick={() => setAnnual(false)}
                className={`px-6 h-11 text-[11px] font-extrabold tracking-[0.1em] uppercase transition-colors ${
                  !annual ? "bg-[var(--tavus-terminal-black)] text-white" : "bg-white text-[var(--tavus-terminal-black)] hover:bg-[var(--tavus-plastic-2)]"
                }`}
              >
                Monthly
              </button>
              <button
                onClick={() => setAnnual(true)}
                className={`relative px-6 h-11 text-[11px] font-extrabold tracking-[0.1em] uppercase transition-colors border-l-[3px] border-[var(--tavus-terminal-black)] ${
                  annual ? "bg-[var(--tavus-terminal-black)] text-white" : "bg-white text-[var(--tavus-terminal-black)] hover:bg-[var(--tavus-plastic-2)]"
                }`}
              >
                Annual
                <span
                  className={`ml-2 inline-block px-1.5 py-0.5 text-[9px] font-extrabold border ${
                    annual
                      ? "bg-[var(--tavus-atomic-glow-1)] border-[var(--tavus-terminal-black)] text-[var(--tavus-terminal-black)]"
                      : "bg-[var(--tavus-atomic-glow-1)] border-[var(--tavus-terminal-black)] text-[var(--tavus-terminal-black)]"
                  }`}
                >
                  −20%
                </span>
              </button>
            </div>
          </div>
        </section>

        {/* ---------- TIER CARDS ---------- */}
        <section className="bg-grain pb-16 pt-2">
          <div className="mx-auto max-w-[1200px] px-5 sm:px-8">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-5 items-stretch">
              {tiers.map((tier) => {
                const price = annual ? tier.annual : tier.monthly;
                return (
                  <div
                    key={tier.name}
                    className={`relative border-[3px] border-[var(--tavus-terminal-black)] hover:shadow-[9px_9px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 transition-all overflow-hidden flex flex-col shadow-[6px_6px_0_0_var(--tavus-terminal-black)] ${
                      tier.highlight
                        ? "md:-mt-4 md:mb-4 bg-[var(--tavus-atomic-glow-00)] shadow-[8px_8px_0_0_var(--tavus-terminal-black)]"
                        : tier.name === "ENTERPRISE"
                        ? "bg-[var(--tavus-neon-field-2)] text-white"
                        : "bg-white"
                    }`}
                  >
                    <div className="absolute inset-0 bg-halftone-light opacity-[0.12] pointer-events-none" />

                    {tier.highlight && (
                      <div className="relative z-10 flex items-center gap-1.5 bg-[var(--tavus-atomic-glow-1)] border-b-[3px] border-[var(--tavus-terminal-black)] px-4 py-1.5">
                        <Sparkles className="w-3 h-3" strokeWidth={3} />
                        <span className="text-[10px] font-extrabold tracking-[0.15em] uppercase">
                          Most popular
                        </span>
                      </div>
                    )}

                    <div className="win-title-bar relative">
                      <span className="w-2.5 h-2.5 bg-[var(--tavus-bubbletech-4)] border border-[var(--tavus-terminal-black)]" />
                      <span>{tier.name}</span>
                      <span className="ml-auto text-[9px] tracking-[0.1em] text-[var(--tavus-hardware-gray-8)] uppercase">
                        {tier.tagline}
                      </span>
                    </div>

                    <div className="relative p-6 flex-1 flex flex-col">
                      {/* Price */}
                      <div className="flex items-end gap-1.5">
                        {price >= 0 ? (
                          <>
                            <span className="font-serif text-[64px] font-normal leading-none tracking-tight tabular-nums">
                              ${price}
                            </span>
                            <span className="text-xs text-[var(--tavus-hardware-gray-8)] mb-1.5">{tier.period}</span>
                          </>
                        ) : (
                          <span className="font-serif text-[64px] font-normal leading-none tracking-tight">
                            Custom
                          </span>
                        )}
                      </div>
                      {tier.highlight && annual && price > 0 && (
                        <div className="mt-2.5 inline-flex items-center gap-1.5 px-2 py-1 border-[2px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-signal-green)] text-[var(--tavus-terminal-black)] text-[10px] font-extrabold tracking-[0.08em] uppercase w-fit">
                          <Zap className="w-3 h-3" strokeWidth={2.5} /> Save ${(tier.monthly - tier.annual) * 12}/year
                        </div>
                      )}

                      <p className="mt-3 text-sm text-[var(--tavus-hardware-gray-8)] leading-relaxed min-h-[44px]">
                        {tier.desc}
                      </p>

                      {/* Volume meter */}
                      <div className="mt-4 mb-5">
                        <div className="flex items-center justify-between text-[9px] font-bold tracking-[0.12em] uppercase text-[var(--tavus-hardware-gray-8)] mb-1.5">
                          <span className="inline-flex items-center gap-1">
                            <Zap className="w-3 h-3" /> Conversation volume
                          </span>
                          <span className="text-[var(--tavus-terminal-black)]">{tier.volumeLabel}</span>
                        </div>
                        <div className="h-2.5 bg-[var(--tavus-plastic-2)] border-2 border-[var(--tavus-terminal-black)] overflow-hidden">
                          <div
                            className={`h-full transition-all duration-500 ${
                              tier.volume < 0
                                ? "w-full bg-[var(--tavus-bubbletech-4)]"
                                : tier.highlight
                                ? "bg-[var(--tavus-atomic-glow-1)]"
                                : "bg-[var(--tavus-neon-field-2)]"
                            }`}
                            style={{
                              width: tier.volume < 0 ? "100%" : `${Math.max(4, (tier.volume / 5000) * 100)}%`,
                            }}
                          />
                        </div>
                      </div>

                      <ul className="space-y-2.5 mb-7 flex-1">
                        {tier.features.map((f) => (
                          <li key={f} className="flex items-start gap-2.5 text-[13px] leading-snug">
                            <span className="mt-0.5 inline-flex w-4 h-4 shrink-0 items-center justify-center border-2 border-[var(--tavus-terminal-black)] bg-[var(--tavus-bubbletech-1)]">
                              <Check className="w-2.5 h-2.5" strokeWidth={4} />
                            </span>
                            <span>{f}</span>
                          </li>
                        ))}
                      </ul>

                      <Link
                        href={tier.ctaHref}
                        className={`w-full inline-flex items-center justify-center gap-2 px-4 h-12 border-[3px] border-[var(--tavus-terminal-black)] text-[11px] font-extrabold tracking-wider uppercase shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:shadow-[5px_5px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] transition-all ${
                          tier.highlight
                            ? "bg-[var(--tavus-bubbletech-4)]"
                            : tier.name === "ENTERPRISE"
                            ? "bg-[var(--tavus-coral-1)] text-white"
                            : "bg-white"
                        }`}
                      >
                        {tier.cta}
                        <ArrowRight className="w-3.5 h-3.5" />
                      </Link>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Guarantee strip */}
            <div className="mt-8 flex flex-wrap items-center justify-center gap-x-8 gap-y-3">
              <div className="inline-flex items-center gap-2 text-[11px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)]">
                <ShieldCheck className="w-4 h-4" /> 14-day free trial — no credit card
              </div>
              <div className="inline-flex items-center gap-2 text-[11px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)]">
                <Check className="w-4 h-4" /> Cancel anytime from your dashboard
              </div>
              <div className="inline-flex items-center gap-2 text-[11px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)]">
                <Check className="w-4 h-4" /> Your data stays yours — export anytime
              </div>
            </div>
          </div>
        </section>

        {/* ---------- COMPARISON TABLE ---------- */}
        <section className="bg-white border-y-[3px] border-[var(--tavus-terminal-black)] py-16">
          <div className="mx-auto max-w-[1100px] px-5 sm:px-8">
            <div className="text-center mb-10">
              <div className="inline-flex items-center gap-2 mb-3">
                <span className="w-2 h-2 bg-[var(--tavus-terminal-black)]" />
                <span className="text-[11px] font-bold tracking-[0.25em] uppercase text-[var(--tavus-hardware-gray-8)]">
                  FULL SPEC SHEET
                </span>
                <span className="w-2 h-2 bg-[var(--tavus-terminal-black)]" />
              </div>
              <h2 className="font-[var(--font-serif-display)] text-4xl sm:text-5xl font-normal tracking-tight text-[var(--tavus-terminal-black)]">
                Compare <span className="serif-italic">every detail</span>
              </h2>
            </div>

            <div className="overflow-x-auto scrollbar-thin border-[3px] border-[var(--tavus-terminal-black)] shadow-[8px_8px_0_0_var(--tavus-terminal-black)] bg-white">
              <table className="w-full text-sm min-w-[640px]">
                <thead>
                  <tr className="bg-[var(--tavus-terminal-black)] text-white">
                    <th className="text-left p-4 font-extrabold tracking-[0.1em] uppercase text-[10px] w-[28%]">
                      Feature
                    </th>
                    <th className="p-4 font-extrabold tracking-[0.1em] uppercase text-[10px]">STARTER</th>
                    <th className="p-4 font-extrabold tracking-[0.1em] uppercase text-[10px] bg-[var(--tavus-bubbletech-4)] text-[var(--tavus-terminal-black)] border-x-[3px] border-[var(--tavus-terminal-black)]">
                      GROWTH ★
                    </th>
                    <th className="p-4 font-extrabold tracking-[0.1em] uppercase text-[10px]">ENTERPRISE</th>
                  </tr>
                </thead>
                <tbody>
                  {[
                    ["Channels", "1", "3", "Unlimited"],
                    ["AI models", "Rabbit OR Rat", "Rabbit + Rat", "Both + custom training"],
                    ["Conversations / month", "100", "5,000", "Unlimited"],
                    ["Inventory Connect shops", "1", "3", "Unlimited"],
                    ["Dialect engine (26 dialects)", true, true, true],
                    ["Voice & image understanding", true, true, true],
                    ["Custom brand tone", false, true, true],
                    ["Order API bridge", false, false, true],
                    ["Style learning from chat history", false, "Beta", true],
                    ["Support", "Community", "Priority email", "Dedicated CSM"],
                    ["Uptime SLA", "—", "99.9%", "99.95%"],
                    ["On-prem / private cloud", false, false, true],
                  ].map((row, i) => (
                    <tr
                      key={i}
                      className={`${
                        i % 2 === 0 ? "bg-white" : "bg-[var(--tavus-plastic-1)]"
                      } border-t-2 border-[var(--tavus-terminal-black)]/10`}
                    >
                      <td className="p-4 font-semibold text-[var(--tavus-terminal-black)] text-[13px]">{row[0]}</td>
                      {[1, 2, 3].map((col) => (
                        <td
                          key={col}
                          className={`p-4 text-center text-[13px] ${
                            col === 2
                              ? "bg-[var(--tavus-bubbletech-1)]/40 border-x-[3px] border-[var(--tavus-terminal-black)]/10 font-semibold"
                              : ""
                          }`}
                        >
                          {typeof row[col] === "boolean" ? (
                            row[col] ? (
                              <Check className="w-4 h-4 mx-auto text-[var(--tavus-signal-green-2)]" strokeWidth={3.5} />
                            ) : (
                              <Minus className="w-4 h-4 mx-auto text-[var(--tavus-hardware-gray-8)]/50" />
                            )
                          ) : (
                            row[col]
                          )}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>

        {/* ---------- FAQ ---------- */}
        <section className="bg-grain py-16">
          <div className="mx-auto max-w-[900px] px-5 sm:px-8">
            <div className="text-center mb-10">
              <div className="inline-flex items-center gap-2 mb-3">
                <span className="w-2 h-2 bg-[var(--tavus-terminal-black)]" />
                <span className="text-[11px] font-bold tracking-[0.25em] uppercase text-[var(--tavus-hardware-gray-8)]">
                  ANSWERS
                </span>
                <span className="w-2 h-2 bg-[var(--tavus-terminal-black)]" />
              </div>
              <h2 className="font-[var(--font-serif-display)] text-4xl sm:text-5xl font-normal tracking-tight text-[var(--tavus-terminal-black)]">
                Common <span className="serif-italic">questions</span>
              </h2>
            </div>

            <Accordion type="single" collapsible className="space-y-3">
              {[
                {
                  q: "What's included in the free trial?",
                  a: "14 days, one channel (WhatsApp, Facebook, or Instagram), 100 conversations per month, your choice of Rabbit v1 or Rooster v1, and Inventory Connect for one shop. No credit card required — you only pay when you're convinced.",
                },
                {
                  q: "Can I switch models mid-conversation?",
                  a: "Yes — Rabbit v1 and Rooster v1 are both available on Growth and Enterprise plans. Most teams let auto-routing pick based on the customer's language, and switch manually when they want a specific tone.",
                },
                {
                  q: "Do you support multi-shop inventory?",
                  a: "Yes. Growth supports 3 shops, Enterprise unlimited. Each shop's inventory is checked live before the agent replies — so you never sell out-of-stock items.",
                },
                {
                  q: "How does the agent learn my tone?",
                  a: "Connect your WhatsApp Business, Facebook, or Instagram account and upload your chat history. The agent trains on your phrasing, slang, emoji use, and response patterns — on Growth and above.",
                },
                {
                  q: "Can I cancel anytime?",
                  a: "Yes. Plans are month-to-month with no lock-in. Upgrade, downgrade, or cancel from your dashboard in two clicks. Annual plans are refunded pro-rata within the first 30 days.",
                },
                {
                  q: "Does it really reply in my dialect?",
                  a: "That's the whole point of Rabbit v1. Egyptian, Gulf, Levantine, Maghrebi, Sudanese — the agent replies in the same dialect the customer used, not textbook MSA. Your customers feel the difference immediately.",
                },
                {
                  q: "What happens if I go over my conversation limit?",
                  a: "We never cut your agent off mid-month. You'll get a notification at 80% and 100%; overage conversations are billed at a small per-conversation rate, or you can upgrade instantly from the dashboard.",
                },
              ].map((faq, i) => (
                <AccordionItem
                  key={i}
                  value={`faq-${i}`}
                  className="border-[3px] border-[var(--tavus-terminal-black)] bg-white shadow-[4px_4px_0_0_var(--tavus-terminal-black)]! data-[state=open]:shadow-[6px_6px_0_0_var(--tavus-terminal-black)]! transition-shadow px-5! [&[data-state=open]]:bg-[var(--tavus-plastic-1)]"
                >
                  <AccordionTrigger className="text-left text-[15px] font-bold text-[var(--tavus-terminal-black)] hover:no-underline py-4! [&>svg]:hidden">
                    <span className="flex items-center gap-3">
                      <span className="inline-flex w-6 h-6 shrink-0 items-center justify-center border-2 border-[var(--tavus-terminal-black)] bg-[var(--tavus-bubbletech-1)] text-[10px] font-extrabold">
                        {String(i + 1).padStart(2, "0")}
                      </span>
                      {faq.q}
                    </span>
                  </AccordionTrigger>
                  <AccordionContent className="text-sm text-[var(--tavus-hardware-gray-8)] leading-relaxed pb-5 pl-9">
                    {faq.a}
                  </AccordionContent>
                </AccordionItem>
              ))}
            </Accordion>
          </div>
        </section>

        {/* ---------- FINAL CTA BAND ---------- */}
        <section className="relative bg-[var(--tavus-bubbletech-4)] border-t-[3px] border-[var(--tavus-terminal-black)] overflow-hidden">
          <div className="absolute inset-0 bg-halftone opacity-[0.15] pointer-events-none" />
          <div className="relative mx-auto max-w-[1000px] px-5 sm:px-8 py-16 text-center">
            <h2 className="font-[var(--font-serif-display)] text-4xl sm:text-5xl font-normal tracking-tight text-[var(--tavus-terminal-black)] leading-tight">
              Your agent could be selling <span className="serif-italic">tonight</span>
            </h2>
            <p className="mt-4 mx-auto max-w-lg text-sm text-[var(--tavus-terminal-black)]/80 leading-relaxed">
              Set up takes under 10 minutes. Connect a channel, import your products, and watch
              the first order roll in while you sleep.
            </p>
            <div className="mt-8 flex flex-wrap items-center justify-center gap-4">
              <Link
                href="/get-started"
                className="inline-flex items-center gap-2 px-8 h-13 py-3.5 border-[3px] border-[var(--tavus-terminal-black)] bg-white text-[12px] font-extrabold tracking-[0.1em] uppercase shadow-[4px_4px_0_0_var(--tavus-terminal-black)] hover:shadow-[6px_6px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] transition-all"
              >
                Start free trial
                <ArrowRight className="w-4 h-4" />
              </Link>
              <Link
                href="/book-demo"
                className="inline-flex items-center gap-2 px-8 py-3.5 border-[3px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-atomic-glow-1)] text-[12px] font-extrabold tracking-[0.1em] uppercase shadow-[4px_4px_0_0_var(--tavus-terminal-black)] hover:shadow-[6px_6px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] transition-all"
              >
                Book a demo
              </Link>
            </div>
          </div>
        </section>
      </main>
      <Footer />
    </div>
  );
}
