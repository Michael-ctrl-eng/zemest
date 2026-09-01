import { Navbar } from "@/components/site/navbar";
import { Footer } from "@/components/site/footer";
import { PageHero, PageSection, RetroCard } from "@/components/site/page-shell";
import { Handshake, Plug, Rocket, Building2 } from "lucide-react";

export const metadata = { title: "Partnerships — Zemest" };

const programs = [
  {
    icon: Plug,
    label: "TECHNOLOGY PARTNERS",
    title: "Integrate Zemest into your product",
    desc: "Embed Zemest agents natively in your platform — CRM, support tool, storefront, or vertical SaaS. Co-sell with our go-to-market team and earn revenue share.",
    cta: "Become a partner",
    href: "/book-demo",
  },
  {
    icon: Handshake,
    label: "AGENCY PARTNERS",
    title: "Build agents for your clients",
    desc: "Agencies and consultancies — get certified to design and deploy Zemest agents for your clients. Access to partner-only pricing, training, and lead sharing.",
    cta: "Join the agency program",
    href: "/book-demo",
  },
  {
    icon: Rocket,
    label: "STARTUP PROGRAM",
    title: "Build on Zemest, free for 12 months",
    desc: "Early-stage startups get $50k in credits, dedicated support, and co-marketing opportunities. If you're building on Zemest, we want to help.",
    cta: "Apply to startup program",
    href: "/book-demo",
  },
  {
    icon: Building2,
    label: "STRATEGIC PARTNERS",
    title: "Co-build the future of conversational commerce",
    desc: "For large enterprises and platform owners looking for deep, multi-year strategic relationships. Joint product, joint research, joint GTM.",
    cta: "Start a conversation",
    href: "/book-demo",
  },
];

export default function PartnershipsPage() {
  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main>
        <PageHero
          eyebrow="PARTNERSHIPS"
          title={<>Wanna make a <span className="serif-italic">deal?</span></>}
          description="Whether you're looking to integrate Zemest into your product, build agents for your clients, or explore a strategic partnership — we'd love to talk. Connect with us and let's figure out what we can build together."
          ctas={[
            { label: "Connect with us", href: "/book-demo", variant: "primary" },
            { label: "Explore partnerships", href: "#programs", variant: "secondary" },
          ]}
        />

        <PageSection bg="grain" id="programs">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            {programs.map((p) => (
              <div key={p.label} className="bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[6px_6px_0_0_var(--tavus-terminal-black)] hover:shadow-[8px_8px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[2px_2px_0_0_var(--tavus-terminal-black)] transition-all overflow-hidden">
                <div className="win-title-bar">
                  <span className="w-2.5 h-2.5 bg-[var(--tavus-bubbletech-4)] border border-[var(--tavus-terminal-black)]" />
                  <span>{p.label}</span>
                  <span className="ml-auto flex gap-1">
                    <span className="w-2.5 h-2.5 border border-[var(--tavus-terminal-black)]" />
                    <span className="w-2.5 h-2.5 border border-[var(--tavus-terminal-black)]" />
                    <span className="w-2.5 h-2.5 border border-[var(--tavus-terminal-black)]" />
                  </span>
                </div>
                <div className="p-6">
                  <p.icon className="h-8 w-8 text-[var(--tavus-terminal-black)]" strokeWidth={2} />
                  <h3 className="mt-4 font-[var(--font-serif-display)] text-2xl font-normal text-[var(--tavus-terminal-black)]">{p.title}</h3>
                  <p className="mt-2 text-sm text-[var(--tavus-hardware-gray-8)] leading-relaxed">{p.desc}</p>
                  <a
                    href={p.href}
                    className="mt-5 inline-flex items-center gap-2 px-4 h-10 border-[3px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-bubbletech-4)] text-[11px] font-extrabold tracking-wider uppercase shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:shadow-[4px_4px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] transition-all"
                  >
                    {p.cta}
                  </a>
                </div>
              </div>
            ))}
          </div>
        </PageSection>

        <PageSection bg="white">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5 text-center">
            {[
              { v: "100+", k: "Partners worldwide" },
              { v: "$50k", k: "Startup credits" },
              { v: "30%", k: "Revenue share (technology partners)" },
            ].map((s) => (
              <div key={s.k} className="bg-[var(--tavus-plastic-1)] border-[3px] border-[var(--tavus-terminal-black)] shadow-[4px_4px_0_0_var(--tavus-terminal-black)] p-6">
                <div className="font-[var(--font-serif-display)] text-5xl font-normal text-[var(--tavus-terminal-black)]">{s.v}</div>
                <div className="mt-1 text-[11px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)]">{s.k}</div>
              </div>
            ))}
          </div>
        </PageSection>
      </main>
      <Footer />
    </div>
  );
}
