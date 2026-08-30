import Link from "next/link";
import { Navbar } from "@/components/site/navbar";
import { Footer } from "@/components/site/footer";
import { PageHero, PageSection } from "@/components/site/page-shell";
import { ArrowUpRight } from "lucide-react";

export const metadata = { title: "Products — Zemest" };

const products = [
  {
    label: "RABBIT V1",
    headline: "Arabic moderation, every accent",
    desc: "Speaks Egyptian, Gulf, Levantine, Maghrebi, Sudanese — replies in the same dialect. Voice-note transcription built in.",
    cta: "GET STARTED",
    ctaHref: "/get-started",
    bg: "var(--tavus-bubbletech-1)",
  },
  {
    label: "ROOSTER V1",
    headline: "English moderation, every accent",
    desc: "US, UK, AUS, Indian, South African English — the way your customers actually speak it. Reads images, listens to voice.",
    cta: "GET STARTED",
    ctaHref: "/get-started",
    bg: "var(--tavus-frost-4)",
  },
  {
    label: "INVENTORY CONNECT",
    headline: "Live inventory in every reply",
    desc: "Connect your shop or POS. The agent checks stock before answering — so every reply is accurate, every time.",
    cta: "CONNECT SHOP",
    ctaHref: "/get-started",
    bg: "var(--tavus-atomic-glow-5)",
  },
];

const capabilities = [
  { name: "Text", desc: "Reads every DM, comment, and message — replies in <3 seconds." },
  { name: "Voice", desc: "Transcribes Arabic + English voice notes natively." },
  { name: "Image", desc: "Customer sends a product photo? Agent recognizes it and replies." },
  { name: "Inventory", desc: "Checks your shop live before answering. Knows stock + price." },
];

export default function ProductsPage() {
  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main>
        <PageHero
          eyebrow="OUR PRODUCTS"
          title={<>Three ways to build <span className="serif-italic">with Zemest</span></>}
          description="Two specialized models and one inventory brain. Together, they make every customer conversation feel like it's coming from you — not a bot. No API, no developer setup — everything's on the Zemest platform."
        />

        <PageSection bg="grain">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            {products.map((p) => (
              <div
                key={p.label}
                className="bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[6px_6px_0_0_var(--tavus-terminal-black)] hover:shadow-[8px_8px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[2px_2px_0_0_var(--tavus-terminal-black)] transition-all overflow-hidden flex flex-col"
              >
                <div className="win-title-bar">
                  <span className="w-2.5 h-2.5 bg-[var(--tavus-bubbletech-4)] border border-[var(--tavus-terminal-black)]" />
                  <span>{p.label}</span>
                  <span className="ml-auto flex gap-1">
                    <span className="w-2.5 h-2.5 border border-[var(--tavus-terminal-black)]" />
                    <span className="w-2.5 h-2.5 border border-[var(--tavus-terminal-black)]" />
                    <span className="w-2.5 h-2.5 border border-[var(--tavus-terminal-black)]" />
                  </span>
                </div>
                <div className="p-6 flex-1 flex flex-col">
                  <div className="aspect-[4/3] border-[2px] border-[var(--tavus-terminal-black)] mb-4" style={{ background: p.bg }} />
                  <h3 className="font-[var(--font-serif-display)] text-2xl font-normal leading-tight text-[var(--tavus-terminal-black)]">{p.headline}</h3>
                  <p className="mt-3 text-sm text-[var(--tavus-hardware-gray-8)] leading-relaxed flex-1">{p.desc}</p>
                  <Link
                    href={p.ctaHref}
                    className="mt-5 w-full inline-flex items-center justify-center gap-2 px-4 h-11 border-[3px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-bubbletech-4)] text-[11px] font-extrabold tracking-wider uppercase shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:shadow-[4px_4px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] transition-all"
                  >
                    {p.cta}
                    <ArrowUpRight className="w-3.5 h-3.5" />
                  </Link>
                </div>
              </div>
            ))}
          </div>
        </PageSection>

        <PageSection bg="white">
          <div className="text-center mb-10">
            <h2 className="font-[var(--font-serif-display)] text-4xl sm:text-5xl font-normal tracking-tight text-[var(--tavus-terminal-black)]">
              Every agent <span className="serif-italic">can do</span>
            </h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
            {capabilities.map((c) => (
              <div key={c.name} className="bg-[var(--tavus-plastic-1)] border-[3px] border-[var(--tavus-terminal-black)] shadow-[6px_6px_0_0_var(--tavus-terminal-black)] p-6">
                <h3 className="font-[var(--font-serif-display)] text-3xl font-normal text-[var(--tavus-terminal-black)]">{c.name}</h3>
                <p className="mt-2 text-sm text-[var(--tavus-hardware-gray-8)] leading-relaxed">{c.desc}</p>
              </div>
            ))}
          </div>
        </PageSection>
      </main>
      <Footer />
    </div>
  );
}
