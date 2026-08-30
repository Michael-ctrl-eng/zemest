import { Navbar } from "@/components/site/navbar";
import { Footer } from "@/components/site/footer";
import { PageHero, PageSection, RetroCard } from "@/components/site/page-shell";
import { ArrowRight, Check } from "lucide-react";

export const metadata = { title: "Plans and Pricing - Zemest" };

const tiers = [
  {
    name: "STARTER",
    price: "$0",
    period: "/14 days",
    desc: "For solo sellers trying moderation on one channel.",
    features: ["1 channel (WhatsApp, FB, or IG)", "Rabbit v1 OR Rat v1", "100 conversations / month", "Inventory Connect (1 shop)", "Community Discord support"],
    cta: "GET STARTED",
    ctaHref: "/get-started",
  },
  {
    name: "GROWTH",
    price: "$99",
    period: "/mo",
    desc: "For small teams scaling moderation across channels.",
    features: ["3 channels (WhatsApp + FB + IG)", "Both models (Rabbit + Rat)", "5,000 conversations / month", "Inventory Connect (3 shops)", "Priority email support", "Custom brand tone"],
    cta: "START GROWTH",
    ctaHref: "/get-started",
    highlight: true,
  },
  {
    name: "ENTERPRISE",
    price: "Custom",
    period: "",
    desc: "For brands with high volume and bespoke needs.",
    features: ["Unlimited channels", "Both models + custom training", "Unlimited conversations", "Inventory Connect (unlimited)", "Dedicated CSM", "99.95% SLA + on-prem option"],
    cta: "BOOK DEMO",
    ctaHref: "/book-demo",
  },
];

const faqs = [
  { q: "What's included in the free trial?", a: "14 days, one channel (WhatsApp, Facebook, or Instagram), 100 conversations per month, your choice of Rabbit v1 or Rat v1, and Inventory Connect for one shop. No credit card required." },
  { q: "Can I switch models mid-conversation?", a: "Yes — Rabbit v1 and Rat v1 are both available on Growth and Enterprise plans. Most teams pick a primary model and switch based on the customer's language." },
  { q: "Do you support multi-shop inventory?", a: "Yes. Growth plan supports 3 shops, Enterprise supports unlimited. Each shop's inventory is checked live before the agent replies." },
  { q: "How does the agent learn my tone?", a: "On signup, you connect your WhatsApp Business / Facebook / Instagram. The agent trains on your historical chats — learning your phrasing, slang, emoji use, and response patterns." },
  { q: "Can I cancel anytime?", a: "Yes. Plans are month-to-month with no long-term lock-in. You can upgrade, downgrade, or cancel from your dashboard." },
  { q: "Does it really reply in my dialect?", a: "Yes — that's the whole point of Rabbit v1. Egyptian, Gulf, Levantine, Maghrebi, Sudanese — the agent replies in the same dialect the customer used, not textbook MSA." },
];

export default function PricingPage() {
  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main>
        <PageHero
          eyebrow="PRICING"
          title={<>Pricing Built to <span className="serif-italic">Scale</span></>}
          description="Flexible plans for every kind of seller. Start free for 14 days. Scale to millions of conversations per month. No API, no developer setup — everything's on the Zemest platform."
          ctas={[
            { label: "Start free trial", href: "/get-started", variant: "primary" },
            { label: "Talk to sales", href: "/book-demo", variant: "secondary" },
          ]}
        />

        <PageSection bg="grain">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            {tiers.map((tier) => (
              <div
                key={tier.name}
                className={`relative bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[6px_6px_0_0_var(--tavus-terminal-black)] hover:shadow-[8px_8px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 transition-all overflow-hidden ${tier.highlight ? "ring-4 ring-[var(--tavus-bubbletech-4)] ring-offset-4 ring-offset-[var(--tavus-plastic-1)]" : ""}`}
              >
                {/* Premium bitmap halftone overlay */}
                <div className="absolute inset-0 bg-halftone-light opacity-10 pointer-events-none" />
                {tier.highlight && (
                  <div className="relative absolute top-0 right-0 bg-[var(--tavus-bubbletech-4)] border-l-[3px] border-b-[3px] border-[var(--tavus-terminal-black)] px-3 py-1 text-[10px] font-extrabold tracking-wider uppercase">
                    MOST POPULAR
                  </div>
                )}
                <div className="win-title-bar relative">
                  <span className="w-2.5 h-2.5 bg-[var(--tavus-bubbletech-4)] border border-[var(--tavus-terminal-black)]" />
                  <span>{tier.name}</span>
                </div>
                <div className="relative p-6">
                  <div className="flex items-end gap-1">
                    <span className="font-[var(--font-serif-display)] text-5xl font-normal">{tier.price}</span>
                    <span className="text-xs text-[var(--tavus-hardware-gray-8)] mb-2">{tier.period}</span>
                  </div>
                  <p className="mt-3 text-sm text-[var(--tavus-hardware-gray-8)] leading-relaxed min-h-[60px]">
                    {tier.desc}
                  </p>
                  <ul className="mt-5 space-y-2">
                    {tier.features.map((f) => (
                      <li key={f} className="flex items-start gap-2 text-sm">
                        <Check className="w-3.5 h-3.5 mt-0.5 text-[var(--tavus-neon-field-3)] shrink-0" strokeWidth={3} />
                        <span>{f}</span>
                      </li>
                    ))}
                  </ul>
                  <a
                    href={tier.ctaHref}
                    className="mt-6 w-full inline-flex items-center justify-center gap-2 px-4 h-11 border-[3px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-bubbletech-4)] text-[11px] font-extrabold tracking-wider uppercase shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:shadow-[4px_4px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] transition-all"
                  >
                    {tier.cta}
                    <ArrowRight className="w-3.5 h-3.5" />
                  </a>
                </div>
              </div>
            ))}
          </div>
        </PageSection>

        <PageSection bg="white">
          <div className="text-center mb-10">
            <h2 className="font-[var(--font-serif-display)] text-4xl sm:text-5xl font-normal tracking-tight text-[var(--tavus-terminal-black)]">
              Compare <span className="serif-italic">plans</span>
            </h2>
          </div>
          <div className="bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[6px_6px_0_0_var(--tavus-terminal-black)] overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-[var(--tavus-terminal-black)] text-white">
                <tr>
                  <th className="text-left p-3 font-extrabold tracking-wider uppercase text-[11px]">Feature</th>
                  <th className="p-3 font-extrabold tracking-wider uppercase text-[11px]">STARTER</th>
                  <th className="p-3 font-extrabold tracking-wider uppercase text-[11px]">GROWTH</th>
                  <th className="p-3 font-extrabold tracking-wider uppercase text-[11px]">ENTERPRISE</th>
                </tr>
              </thead>
              <tbody>
                {[
                  ["Channels", "1", "3", "Unlimited"],
                  ["Models", "Rabbit OR Rat", "Both", "Both + custom"],
                  ["Conversations / month", "100", "5,000", "Unlimited"],
                  ["Inventory Connect shops", "1", "3", "Unlimited"],
                  ["Support", "Community", "Priority email", "Dedicated CSM"],
                  ["SLA", "—", "99.9%", "99.95%"],
                  ["Custom brand tone", "—", "Yes", "Yes"],
                  ["On-prem option", "—", "—", "Yes"],
                ].map((row, i) => (
                  <tr key={i} className={i % 2 === 0 ? "bg-white" : "bg-[var(--tavus-plastic-1)]"}>
                    <td className="p-3 font-semibold text-[var(--tavus-terminal-black)]">{row[0]}</td>
                    <td className="p-3 text-center text-[var(--tavus-terminal-black)]">{row[1]}</td>
                    <td className="p-3 text-center text-[var(--tavus-terminal-black)]">{row[2]}</td>
                    <td className="p-3 text-center text-[var(--tavus-terminal-black)]">{row[3]}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </PageSection>

        <PageSection bg="grain">
          <div className="text-center mb-10">
            <h2 className="font-[var(--font-serif-display)] text-4xl sm:text-5xl font-normal tracking-tight text-[var(--tavus-terminal-black)]">
              Common <span className="serif-italic">questions</span>
            </h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {faqs.map((faq) => (
              <RetroCard key={faq.q} label="FAQ" title={faq.q} description={faq.a} />
            ))}
          </div>
        </PageSection>
      </main>
      <Footer />
    </div>
  );
}
