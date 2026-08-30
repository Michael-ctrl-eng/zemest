import Link from "next/link";
import { Navbar } from "@/components/site/navbar";
import { Footer } from "@/components/site/footer";
import { PageHero, PageSection } from "@/components/site/page-shell";
import { MessageCircle, Instagram, Facebook, Boxes, Globe, ShoppingCart, ArrowUpRight } from "lucide-react";

export const metadata = { title: "Solutions — Zemest" };

const solutions = [
  { icon: MessageCircle, label: "WHATSAPP AGENT", title: "Replies like the buyer is talking to you", desc: "Reads text, voice, images. Checks inventory. Closes the sale.", stat: "3.2× reply rate", href: "/solutions/whatsapp" },
  { icon: Instagram, label: "INSTAGRAM AGENT", title: "Closes sales in the DMs while you sleep", desc: "From story replies to product inquiries — every DM answered, in Arabic or English, in your tone.", stat: "+47% DM→sale", href: "/solutions/instagram" },
  { icon: Facebook, label: "MESSENGER AGENT", title: "Every comment, every message, answered instantly", desc: "The agent reads images, listens to voice, responds in the dialect your customers actually use.", stat: "+38% CSAT", href: "/solutions/messenger" },
  { icon: ShoppingCart, label: "INVENTORY AGENT", title: "Knows what's in stock before you do", desc: "A buyer asks for size 42. The agent checks your inventory live: 'Available, 2 left, 850 EGP. Want me to hold one?'", stat: "-41% lost sales", href: "/solutions/inventory" },
  { icon: Globe, label: "ARABIC + ALL DIALECTS", title: "Arabic, the way your customers actually speak it", desc: "Rabbit v1 — Egyptian, Gulf, Levantine, Maghrebi, Sudanese. Replies in the same dialect, not textbook MSA.", stat: "30+ dialects", href: "/models" },
  { icon: Boxes, label: "CUSTOM AGENTS", title: "Bespoke agents built around your workflow", desc: "Bring us any moderation use case — we design, train, and deploy an agent that fits your business.", stat: "1:1 tailored", href: "/enterprise" },
];

export default function SolutionsPage() {
  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main>
        <PageHero
          eyebrow="SOLUTIONS"
          title={<>One agent for every <span className="serif-italic">conversation</span></>}
          description="An agent can be whatever the moment calls for: a WhatsApp seller, an Instagram DM closer, a Messenger support rep, or an inventory checker. Here are the most common ways brands are putting them to work."
          ctas={[{ label: "Book a demo", href: "/book-demo", variant: "primary" }]}
        />

        <PageSection bg="grain">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {solutions.map((s) => (
              <Link
                key={s.label}
                href={s.href}
                className="block bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[6px_6px_0_0_var(--tavus-terminal-black)] hover:shadow-[8px_8px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[2px_2px_0_0_var(--tavus-terminal-black)] transition-all overflow-hidden"
              >
                <div className="win-title-bar">
                  <span className="w-2.5 h-2.5 bg-[var(--tavus-bubbletech-4)] border border-[var(--tavus-terminal-black)]" />
                  <span>{s.label}</span>
                  <span className="ml-auto flex gap-1">
                    <span className="w-2.5 h-2.5 border border-[var(--tavus-terminal-black)]" />
                    <span className="w-2.5 h-2.5 border border-[var(--tavus-terminal-black)]" />
                    <span className="w-2.5 h-2.5 border border-[var(--tavus-terminal-black)]" />
                  </span>
                </div>
                <div className="p-6">
                  <div className="flex items-center gap-3">
                    <div className="inline-flex h-11 w-11 items-center justify-center border-[2px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-bubbletech-1)]">
                      <s.icon className="h-5 w-5 text-[var(--tavus-terminal-black)]" strokeWidth={2} />
                    </div>
                    <div className="text-right ml-auto">
                      <div className="font-[var(--font-serif-display)] text-2xl font-normal text-[var(--tavus-terminal-black)] leading-none">{s.stat.split(" ")[0]}</div>
                      <div className="text-[9px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)] mt-1">{s.stat.split(" ").slice(1).join(" ")}</div>
                    </div>
                  </div>
                  <h3 className="mt-5 font-[var(--font-serif-display)] text-xl font-normal leading-tight text-[var(--tavus-terminal-black)]">{s.title}</h3>
                  <p className="mt-2 text-sm text-[var(--tavus-hardware-gray-8)] leading-relaxed">{s.desc}</p>
                  <div className="mt-4 inline-flex items-center gap-1 text-[11px] font-bold tracking-wider uppercase text-[var(--tavus-terminal-black)]">
                    LEARN MORE
                    <ArrowUpRight className="w-3.5 h-3.5" />
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </PageSection>
      </main>
      <Footer />
    </div>
  );
}
