import { Navbar } from "@/components/site/navbar";
import { Footer } from "@/components/site/footer";
import { PageHero, PageSection, RetroCard } from "@/components/site/page-shell";
import { ArrowRight } from "lucide-react";

export const metadata = { title: "Support Center — Zemest" };

export default function SupportPage() {
  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main>
        <PageHero
          eyebrow="SUPPORT"
          title={<>Help, <span className="serif-italic">fast</span></>}
          description="Your agent answers customers in three seconds — your support shouldn't be slower. Here's how to reach a human, what to expect, and where to help yourself."
        />

        <PageSection bg="grain">
          <div className="text-center mb-10">
            <h2 className="font-[var(--font-serif-display)] text-4xl sm:text-5xl font-normal tracking-tight text-[var(--tavus-terminal-black)]">
              Ways to <span className="serif-italic">reach us</span>
            </h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {[
              { label: "EVERYONE", title: "Email support", desc: "hello@zemest.ai — answered by a person, typically within one business day. No ticket maze, no bot loop." },
              { label: "EVERYONE", title: "Support docs", desc: "Step-by-step guides for connecting channels, importing catalogs, and tuning your agent's tone — written for store owners, not engineers." },
              { label: "GROWTH", title: "Priority email", desc: "Growth plans jump the queue: priority routing and a first response target of four business hours." },
              { label: "ENTERPRISE", title: "Dedicated CSM", desc: "A named customer success manager, a shared Slack channel, and 30-minute response on critical incidents." },
            ].map((s) => (
              <RetroCard key={s.title} label={s.label} title={s.title} description={s.desc} />
            ))}
          </div>
        </PageSection>

        <PageSection bg="white">
          <div className="text-center mb-10">
            <h2 className="font-[var(--font-serif-display)] text-4xl sm:text-5xl font-normal tracking-tight text-[var(--tavus-terminal-black)]">
              Common <span className="serif-italic">fixes</span>
            </h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5 max-w-4xl mx-auto">
            <div className="bg-[var(--tavus-plastic-1)] border-[3px] border-[var(--tavus-terminal-black)] shadow-[6px_6px_0_0_var(--tavus-terminal-black)] p-6">
              <h3 className="font-[var(--font-serif-display)] text-2xl font-normal text-[var(--tavus-terminal-black)]">Agent &amp; channels</h3>
              <ul className="mt-4 space-y-3">
                {[
                  "My agent stopped replying — check the channel connection from the Channels page first; a disconnected page pauses replies, not the agent.",
                  "Replies feel off-tone — upload more chat history on the Style page; the trainer improves as evidence accumulates.",
                  "Wrong prices quoted — re-sync your catalog from the Products page; prices always come from the live record.",
                  "A customer was quoted an out-of-stock item — check the sync timestamp; stock changes propagate within minutes.",
                ].map((t) => (
                  <li key={t} className="flex items-start gap-3 text-sm text-[var(--tavus-terminal-black)]">
                    <span className="mt-1.5 w-2 h-2 bg-[var(--tavus-terminal-black)] shrink-0" />
                    <span>{t}</span>
                  </li>
                ))}
              </ul>
            </div>
            <div className="bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[6px_6px_0_0_var(--tavus-terminal-black)] p-6">
              <h3 className="font-[var(--font-serif-display)] text-2xl font-normal text-[var(--tavus-terminal-black)]">Account &amp; billing</h3>
              <ul className="mt-4 space-y-3">
                {[
                  "Upgrade, downgrade, or cancel from your dashboard in two clicks — plans are month-to-month with no lock-in.",
                  "Hit your conversation limit? We never cut the agent off mid-month; overage is billed at a small per-conversation rate or upgrade instantly.",
                  "Data export — your conversations, products, and orders are yours; export anytime from Settings.",
                  "Anything about a refund, complaint, or account incident goes straight to a human — email us and it routes to the on-call owner.",
                ].map((t) => (
                  <li key={t} className="flex items-start gap-3 text-sm text-[var(--tavus-terminal-black)]">
                    <span className="mt-1.5 w-2 h-2 bg-[var(--tavus-terminal-black)] shrink-0" />
                    <span>{t}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
          <div className="mt-10 text-center">
            <a
              href="mailto:hello@zemest.ai"
              className="inline-flex items-center gap-2 px-7 h-12 border-[3px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-bubbletech-4)] text-xs font-extrabold tracking-[0.08em] uppercase shadow-[4px_4px_0_0_var(--tavus-terminal-black)] hover:shadow-[6px_6px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] transition-all"
            >
              Email hello@zemest.ai
              <ArrowRight className="w-4 h-4" />
            </a>
          </div>
        </PageSection>
      </main>
      <Footer />
    </div>
  );
}
