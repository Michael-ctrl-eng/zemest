import { Navbar } from "@/components/site/navbar";
import { Footer } from "@/components/site/footer";
import { PageHero, PageSection, RetroCard } from "@/components/site/page-shell";
import { ArrowRight } from "lucide-react";

export const metadata = { title: "Inventory Connect — Zemest" };

export default function InventorySolutionPage() {
  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main>
        <PageHero
          eyebrow="SOLUTIONS · INVENTORY"
          title={<>Knows what&apos;s in stock <span className="serif-italic">before you do</span></>}
          description="Inventory Connect links your shop or POS to every agent reply. A buyer asks for size 42 — the agent checks the live record and answers with the truth: available, the price, and how many are left."
          ctas={[
            { label: "Start free trial", href: "/get-started", variant: "primary" },
            { label: "Book a demo", href: "/book-demo", variant: "secondary" },
          ]}
        />

        <PageSection bg="grain">
          <div className="text-center mb-10">
            <h2 className="font-[var(--font-serif-display)] text-4xl sm:text-5xl font-normal tracking-tight text-[var(--tavus-terminal-black)]">
              Grounded replies, <span className="serif-italic">zero overselling</span>
            </h2>
            <p className="mt-4 text-base text-[var(--tavus-hardware-gray-8)] max-w-2xl mx-auto leading-relaxed">
              The most expensive sentence an AI can write is a confident price. Inventory Connect makes sure it never has to — every claim is checked before a word is written.
            </p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {[
              { label: "SYNC", title: "Live stock", desc: "Your catalog re-syncs continuously — a sale at 1:58 a.m. is reflected in the reply at 2:00 a.m., across every channel." },
              { label: "QUOTE", title: "True prices", desc: "Prices come from the record, not the model's memory. Multi-shop stores quote each storefront's price correctly." },
              { label: "SELL OUT", title: "Honest 'no'", desc: "Out-of-stock replies offer the wait, the alternative, or another size — never a dead end, never a broken promise." },
              { label: "CAPTURE", title: "Clean orders", desc: "Orders enter your dashboard with variant, quantity, and total already confirmed in writing with the buyer." },
            ].map((s) => (
              <RetroCard key={s.label} label={s.label} title={s.title} description={s.desc} />
            ))}
          </div>
        </PageSection>

        <PageSection bg="white">
          <div className="text-center mb-10">
            <h2 className="font-[var(--font-serif-display)] text-4xl sm:text-5xl font-normal tracking-tight text-[var(--tavus-terminal-black)]">
              What it <span className="serif-italic">looks like</span>
            </h2>
          </div>
          <div className="max-w-3xl mx-auto">
            <div className="bg-[var(--tavus-terminal-black)] border-[3px] border-[var(--tavus-terminal-black)] shadow-[6px_6px_0_0_var(--tavus-terminal-black)] p-6 space-y-2.5">
              <div className="text-[9px] font-mono text-white/40 uppercase tracking-wider mb-2">LIVE INVENTORY · YOUR SHOP</div>
              {[
                { name: "Air Max 90 · Size 42", stock: "IN STOCK", count: "2", color: "var(--tavus-signal-green)" },
                { name: "Air Max 90 · Size 43", stock: "OUT OF STOCK", count: "0", color: "var(--tavus-bubbletech-4)" },
                { name: "Air Force 1 · Size 42", stock: "IN STOCK", count: "7", color: "var(--tavus-signal-green)" },
              ].map((s, i) => (
                <div key={i} className="flex items-center justify-between bg-white/5 border border-white/10 px-3 py-2.5">
                  <div className="flex items-center gap-2.5">
                    <span
                      className="px-1.5 py-0.5 text-[9px] font-bold tracking-wider uppercase"
                      style={{ background: s.color, color: "var(--tavus-terminal-black)" }}
                    >
                      {s.stock}
                    </span>
                    <span className="text-[13px] text-white">{s.name}</span>
                  </div>
                  <span className="text-[10px] text-white/40 font-mono">{s.count} LEFT</span>
                </div>
              ))}
              <div className="text-[10px] text-white/50 font-mono flex items-center gap-1.5 pt-2">
                <span className="w-1.5 h-1.5 bg-[var(--tavus-signal-green)] animate-pulse" />
                Checked before every reply — on WhatsApp, Messenger, and Instagram alike
              </div>
            </div>
          </div>
        </PageSection>

        <PageSection bg="grain">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5 text-center">
            {[
              { v: "-41%", k: "lost sales from bad answers" },
              { v: "0", k: "items oversold across channels" },
              { v: "3+", k: "shops on one agent — Growth runs 3, Enterprise unlimited" },
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
              Connect your shop
              <ArrowRight className="w-4 h-4" />
            </a>
          </div>
        </PageSection>
      </main>
      <Footer />
    </div>
  );
}
