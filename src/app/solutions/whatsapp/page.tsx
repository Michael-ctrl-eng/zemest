import { Navbar } from "@/components/site/navbar";
import { Footer } from "@/components/site/footer";
import { PageHero, PageSection, RetroCard } from "@/components/site/page-shell";
import { ArrowRight } from "lucide-react";

export const metadata = { title: "WhatsApp Agent — Zemest" };

export default function WhatsAppSolutionPage() {
  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main>
        <PageHero
          eyebrow="SOLUTIONS · WHATSAPP"
          title={<>Replies like the buyer is <span className="serif-italic">talking to you</span></>}
          description="Your WhatsApp agent answers product questions, quotes live prices, checks stock, and confirms the order in writing — in the buyer's own dialect, in seconds, around the clock."
          ctas={[
            { label: "Start free trial", href: "/get-started", variant: "primary" },
            { label: "Book a demo", href: "/book-demo", variant: "secondary" },
          ]}
        />

        <PageSection bg="grain">
          <div className="text-center mb-10">
            <h2 className="font-[var(--font-serif-display)] text-4xl sm:text-5xl font-normal tracking-tight text-[var(--tavus-terminal-black)]">
              How it <span className="serif-italic">works</span>
            </h2>
            <p className="mt-4 text-base text-[var(--tavus-hardware-gray-8)] max-w-2xl mx-auto leading-relaxed">
              The same four beats your best salesperson hits — applied to every conversation, every time.
            </p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {[
              { label: "01 · CONNECT", title: "Link your number", desc: "Connect your WhatsApp Business account in minutes. No developers, no API keys to babysit." },
              { label: "02 · GROUND", title: "Import your catalog", desc: "Sync products, prices, and stock. The agent answers from the live record, never from memory." },
              { label: "03 · ANSWER", title: "Chats get answered", desc: "Text, voice notes, and images — replied to in the buyer's dialect, with the real price and availability." },
              { label: "04 · CLOSE", title: "Orders land confirmed", desc: "Item, total, address, and payment method written and confirmed before the order hits your dashboard." },
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
                  "Product questions — sizes, colors, materials, and what's still in stock",
                  "Price quotes grounded in your live catalog, with deposit and hold options",
                  "Delivery fees by governorate, quoted straight from your rate card",
                  "Voice notes transcribed and answered with matching warmth or directness",
                  "Screenshots and product photos matched to your catalog",
                ].map((t) => (
                  <li key={t} className="flex items-start gap-3 text-sm text-[var(--tavus-terminal-black)]">
                    <span className="mt-1.5 w-2 h-2 bg-[var(--tavus-terminal-black)] shrink-0" />
                    <span>{t}</span>
                  </li>
                ))}
              </ul>
            </div>
            <div className="bg-[var(--tavus-terminal-black)] border-[3px] border-[var(--tavus-terminal-black)] shadow-[6px_6px_0_0_var(--tavus-terminal-black)] p-6 space-y-3">
              <div className="text-[9px] font-mono text-white/40 uppercase tracking-wider">SAMPLE EXCHANGE</div>
              <div className="bg-white border border-white p-3 text-[13px] text-[var(--tavus-terminal-black)]" dir="rtl">
                <span className="text-[9px] font-bold text-[var(--tavus-hardware-gray-8)] uppercase block mb-1">CUSTOMER</span>
                لو سمحت، النايك الأبيض مقاس 42؟ وبكام التوصيل ل مدينة نصر؟
              </div>
              <div className="bg-[var(--tavus-bubbletech-4)] border-2 border-white p-3 text-[13px] text-[var(--tavus-terminal-black)]" dir="rtl">
                <span className="text-[9px] font-bold text-[var(--tavus-terminal-black)]/70 uppercase block mb-1">AGENT</span>
                أيوا متوفر، 850 جنيه والتوصيل لمدينة نصر 50. أثبتهولك؟
              </div>
              <div className="text-[10px] text-white/50 font-mono flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 bg-[var(--tavus-signal-green)] animate-pulse" />
                Dialect: Egyptian · Grounded in live stock · Reply &lt;3s
              </div>
            </div>
          </div>
        </PageSection>

        <PageSection bg="grain">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5 text-center">
            {[
              { v: "3.2×", k: "reply rate" },
              { v: "<3s", k: "median reply time" },
              { v: "24/7", k: "coverage — nights & weekends included" },
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
              Put an agent on WhatsApp
              <ArrowRight className="w-4 h-4" />
            </a>
          </div>
        </PageSection>
      </main>
      <Footer />
    </div>
  );
}
