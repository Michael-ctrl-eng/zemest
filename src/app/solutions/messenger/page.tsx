import { Navbar } from "@/components/site/navbar";
import { Footer } from "@/components/site/footer";
import { PageHero, PageSection, RetroCard } from "@/components/site/page-shell";
import { ArrowRight } from "lucide-react";

export const metadata = { title: "Messenger Agent — Zemest" };

export default function MessengerSolutionPage() {
  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main>
        <PageHero
          eyebrow="SOLUTIONS · MESSENGER"
          title={<>Every comment, every message, <span className="serif-italic">answered instantly</span></>}
          description="The Messenger agent handles your Facebook page around the clock — public comments and private threads, voice notes and photos, in the dialect your customers actually use."
          ctas={[
            { label: "Start free trial", href: "/get-started", variant: "primary" },
            { label: "Book a demo", href: "/book-demo", variant: "secondary" },
          ]}
        />

        <PageSection bg="grain">
          <div className="text-center mb-10">
            <h2 className="font-[var(--font-serif-display)] text-4xl sm:text-5xl font-normal tracking-tight text-[var(--tavus-terminal-black)]">
              Why comments <span className="serif-italic">matter</span>
            </h2>
            <p className="mt-4 text-base text-[var(--tavus-hardware-gray-8)] max-w-2xl mx-auto leading-relaxed">
              On Facebook, the comment section is the storefront. Unanswered questions under a post read as a closed shop — and every answered one is an ad that sells.
            </p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {[
              { label: "COMMENTS", title: "Public replies", desc: "Price questions, size checks, and 'available?' under every post — answered in seconds, in public, where every watcher can see it." },
              { label: "INBOX", title: "Private threads", desc: "The buyers who move to DMs get the full sales conversation: quotes, delivery fees, and order confirmation in writing." },
              { label: "TONE", title: "Your voice", desc: "The agent learns your phrasing and warmth from your own replies — so public and private both sound like the person behind the page." },
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
                  "'Price?' under posts — answered with the grounded number, every time",
                  "Size and availability checks against live inventory",
                  "Voice notes and photos understood, not just text",
                  "Dialect matched from the first message — Egyptian to Egyptian, Gulf to Gulf",
                  "Handoffs to a human for complaints, refunds, and regulars",
                ].map((t) => (
                  <li key={t} className="flex items-start gap-3 text-sm text-[var(--tavus-terminal-black)]">
                    <span className="mt-1.5 w-2 h-2 bg-[var(--tavus-terminal-black)] shrink-0" />
                    <span>{t}</span>
                  </li>
                ))}
              </ul>
            </div>
            <div className="bg-[var(--tavus-terminal-black)] border-[3px] border-[var(--tavus-terminal-black)] shadow-[6px_6px_0_0_var(--tavus-terminal-black)] p-6 space-y-3">
              <div className="text-[9px] font-mono text-white/40 uppercase tracking-wider">UNDER THE POST</div>
              <div className="bg-white/5 border border-white/10 p-3 text-[13px] text-white/80" dir="rtl">
                <span className="text-[9px] font-bold text-white/40 uppercase block mb-1">COMMENT</span>
                السعر كام؟ وفى مقاس 43؟
              </div>
              <div className="bg-[var(--tavus-bubbletech-4)] border-2 border-white p-3 text-[13px] text-[var(--tavus-terminal-black)]" dir="rtl">
                <span className="text-[9px] font-bold text-[var(--tavus-terminal-black)]/70 uppercase block mb-1">AGENT</span>
                مقاس 43 خلص، بس فى 42 و 44 — 850 جنيه. ابعتلنا رسالة ونثبتلك واحدة 🙂
              </div>
              <div className="text-[10px] text-white/50 font-mono flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 bg-[var(--tavus-signal-green)] animate-pulse" />
                Public reply · Honest stock answer · Moves the sale to DMs
              </div>
            </div>
          </div>
        </PageSection>

        <PageSection bg="grain">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5 text-center">
            {[
              { v: "+38%", k: "CSAT lift" },
              { v: "<3s", k: "median reply time" },
              { v: "0", k: "comments left unanswered overnight" },
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
              Put an agent on Messenger
              <ArrowRight className="w-4 h-4" />
            </a>
          </div>
        </PageSection>
      </main>
      <Footer />
    </div>
  );
}
