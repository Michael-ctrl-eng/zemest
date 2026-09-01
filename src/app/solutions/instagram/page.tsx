import { Navbar } from "@/components/site/navbar";
import { Footer } from "@/components/site/footer";
import { PageHero, PageSection, RetroCard } from "@/components/site/page-shell";
import { ArrowRight } from "lucide-react";

export const metadata = { title: "Instagram Agent — Zemest" };

export default function InstagramSolutionPage() {
  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main>
        <PageHero
          eyebrow="SOLUTIONS · INSTAGRAM"
          title={<>Closes sales in the DMs <span className="serif-italic">while you sleep</span></>}
          description="Story replies, sticker taps, and product inquiries — your Instagram agent answers within seconds, knows what's in stock, quotes real prices, and books the order in Arabic or English."
          ctas={[
            { label: "Start free trial", href: "/get-started", variant: "primary" },
            { label: "Book a demo", href: "/book-demo", variant: "secondary" },
          ]}
        />

        <PageSection bg="grain">
          <div className="text-center mb-10">
            <h2 className="font-[var(--font-serif-display)] text-4xl sm:text-5xl font-normal tracking-tight text-[var(--tavus-terminal-black)]">
              The DM window is <span className="serif-italic">minutes wide</span>
            </h2>
            <p className="mt-4 text-base text-[var(--tavus-hardware-gray-8)] max-w-2xl mx-auto leading-relaxed">
              A story reply isn't an email — the buyer is looking at their phone right now. The conversation opens and closes within minutes, and most of it happens after your last post, when the feed is quiet and you're asleep.
            </p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {[
              { label: "STORY TAPS", title: "Answer the tap", desc: "A product sticker tap is a purchase-intent signal with a countdown on it. The agent answers within seconds and keeps the reply short enough to act on." },
              { label: "PRODUCT Qs", title: "Quote and hold", desc: "Sizes, colors, and prices answered from live inventory — with the hold offer when stock runs low and the expiry that makes it real." },
              { label: "THE CLOSE", title: "Book the order", desc: "When the buyer commits, the agent writes the full order — item, total, delivery area, payment method — and confirms it before capture." },
            ].map((s) => (
              <RetroCard key={s.label} label={s.label} title={s.title} description={s.desc} />
            ))}
          </div>
        </PageSection>

        <PageSection bg="white">
          <div className="text-center mb-10">
            <h2 className="font-[var(--font-serif-display)] text-4xl sm:text-5xl font-normal tracking-tight text-[var(--tavus-terminal-black)]">
              What it <span className="serif-italic">handles</span>
            </h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5 max-w-4xl mx-auto">
            <div className="bg-[var(--tavus-plastic-1)] border-[3px] border-[var(--tavus-terminal-black)] shadow-[6px_6px_0_0_var(--tavus-terminal-black)] p-6">
              <ul className="space-y-3">
                {[
                  "Story replies and product sticker taps, answered in seconds",
                  "DM conversations in Arabic or English — dialect matched from the first message",
                  "'How much?' answered with the grounded price and the delivery fee, together",
                  "Screenshots from other apps matched to your catalog and answered honestly",
                  "Order capture in writing, with the total the buyer can screenshot and trust",
                ].map((t) => (
                  <li key={t} className="flex items-start gap-3 text-sm text-[var(--tavus-terminal-black)]">
                    <span className="mt-1.5 w-2 h-2 bg-[var(--tavus-terminal-black)] shrink-0" />
                    <span>{t}</span>
                  </li>
                ))}
              </ul>
            </div>
            <div className="bg-[var(--tavus-terminal-black)] border-[3px] border-[var(--tavus-terminal-black)] shadow-[6px_6px_0_0_var(--tavus-terminal-black)] p-6 space-y-3">
              <div className="text-[9px] font-mono text-white/40 uppercase tracking-wider">IN THE DMs · 12:40 A.M.</div>
              <div className="bg-white/5 border border-white/10 p-3 text-[13px] text-white/80">
                <span className="text-[9px] font-bold text-white/40 uppercase block mb-1">CUSTOMER · STORY REPLY</span>
                Saw this on your story — is this available in 42? And how much to deliver to Alexandria?
              </div>
              <div className="bg-[var(--tavus-bubbletech-4)] border-2 border-white p-3 text-[13px] text-[var(--tavus-terminal-black)]">
                <span className="text-[9px] font-bold text-[var(--tavus-terminal-black)]/70 uppercase block mb-1">AGENT</span>
                Yep — 2 left in 42. 850 EGP, and delivery to Alexandria is 70. Want me to hold one for you until tomorrow evening?
              </div>
              <div className="text-[10px] text-white/50 font-mono flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 bg-[var(--tavus-signal-green)] animate-pulse" />
                Live stock · Hold with expiry · Order-ready close
              </div>
            </div>
          </div>
        </PageSection>

        <PageSection bg="grain">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5 text-center">
            {[
              { v: "+47%", k: "DM→sale lift" },
              { v: "<3s", k: "median reply time" },
              { v: "2 a.m.", k: "when the best conversations happen" },
            ].map((s) => (
              <div key={s.k} className="bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[4px_4px_0_0_var(--tavus-terminal-black)] p-6">
                <div className="font-[var(--font-serif-display)] text-5xl font-normal text-[var(--tavus-terminal-black)]">{s.v}</div>
                <div className="mt-1 text-[11px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)]">{s.k}</div>
              </div>
            ))}
          </div>
          <div className="mt-10 text-center">
            <a
              href="/get-started"
              className="inline-flex items-center gap-2 px-7 h-12 border-[3px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-bubbletech-4)] text-xs font-extrabold tracking-[0.08em] uppercase shadow-[4px_4px_0_0_var(--tavus-terminal-black)] hover:shadow-[6px_6px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] transition-all"
            >
              Put an agent on Instagram
              <ArrowRight className="w-4 h-4" />
            </a>
          </div>
        </PageSection>
      </main>
      <Footer />
    </div>
  );
}
