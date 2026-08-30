import { Navbar } from "@/components/site/navbar";
import { Footer } from "@/components/site/footer";
import { PageHero, PageSection, RetroCard } from "@/components/site/page-shell";
import { ShieldCheck, Server, Lock, Users, FileCheck, Headset } from "lucide-react";

export const metadata = { title: "Enterprise — Zemest" };

const features = [
  { icon: ShieldCheck, title: "SOC 2 Type II", desc: "Independently audited security and availability controls. Reports available on request." },
  { icon: Lock, title: "HIPAA & GDPR", desc: "Business Associate Agreements available. Full GDPR compliance with EU data residency options." },
  { icon: Server, title: "Private cloud & on-prem", desc: "Deploy Tavus in your own VPC, on-prem, or in air-gapped environments. Your data stays yours." },
  { icon: Users, title: "Dedicated CSM", desc: "A named customer success manager and solutions engineer — not a queue, a person." },
  { icon: FileCheck, title: "99.95% uptime SLA", desc: "Production-grade reliability with financial credits if we miss it. Multi-region failover included." },
  { icon: Headset, title: "24/7 enterprise support", desc: "Round-the-clock Slack channel, dedicated phone line, and 30-minute critical incident response." },
];

export default function EnterprisePage() {
  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main>
        <PageHero
          eyebrow="ENTERPRISE"
          title={<>Customized PALs, <span className="serif-italic">fully managed</span></>}
          description="Solutions are bespoke, fully managed PAL deployments. Our team designs, builds, and tunes a PAL around your exact workflow, then runs it in production at the scale and reliability your business requires."
          ctas={[
            { label: "Book a demo", href: "/book-demo", variant: "primary" },
            { label: "Talk to sales", href: "/partnerships", variant: "secondary" },
          ]}
        />

        <PageSection bg="grain">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {features.map((f) => (
              <div key={f.title} className="bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[6px_6px_0_0_var(--tavus-terminal-black)] hover:shadow-[8px_8px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 transition-all p-6">
                <f.icon className="h-7 w-7 text-[var(--tavus-terminal-black)]" strokeWidth={2} />
                <h3 className="mt-4 font-[var(--font-serif-display)] text-xl font-normal text-[var(--tavus-terminal-black)]">{f.title}</h3>
                <p className="mt-2 text-sm text-[var(--tavus-hardware-gray-8)] leading-relaxed">{f.desc}</p>
              </div>
            ))}
          </div>
        </PageSection>

        {/* Process */}
        <PageSection bg="white">
          <div className="text-center mb-10">
            <h2 className="font-[var(--font-serif-display)] text-4xl sm:text-5xl font-normal tracking-tight text-[var(--tavus-terminal-black)]">
              How we <span className="serif-italic">work</span>
            </h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            {[
              { n: "01", title: "Discovery & design", desc: "We sit down with your team, map your workflow, and design the PAL around the moments that matter most." },
              { n: "02", title: "Build & integrate", desc: "Our solutions engineers build the PAL, integrate it into your stack, and tune it on real conversations." },
              { n: "03", title: "Deploy & manage", desc: "We run it in production — monitoring, tuning, scaling — so your team can stay focused on the business." },
            ].map((s) => (
              <div key={s.n} className="bg-[var(--tavus-plastic-1)] border-[3px] border-[var(--tavus-terminal-black)] shadow-[6px_6px_0_0_var(--tavus-terminal-black)] p-6">
                <div className="font-[var(--font-serif-display)] text-4xl text-[var(--tavus-terminal-black)]/20 font-bold">{s.n}</div>
                <h3 className="mt-2 font-[var(--font-serif-display)] text-2xl font-normal text-[var(--tavus-terminal-black)]">{s.title}</h3>
                <p className="mt-2 text-sm text-[var(--tavus-hardware-gray-8)] leading-relaxed">{s.desc}</p>
              </div>
            ))}
          </div>
        </PageSection>

        {/* Use cases */}
        <PageSection bg="grain">
          <div className="text-center mb-10">
            <h2 className="font-[var(--font-serif-display)] text-4xl sm:text-5xl font-normal tracking-tight text-[var(--tavus-terminal-black)]">
              What teams <span className="serif-italic">build</span>
            </h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {[
              { label: "SALES", title: "GTM agents", desc: "Inbound demos, outbound follow-ups, and QBR coaching." },
              { label: "HEALTHCARE", title: "Patient intake", desc: "Pre-visit intake, triage, and post-discharge check-ins." },
              { label: "INTERVIEWS", title: "Screening agents", desc: "Fair, structured, face-to-face screening at scale." },
              { label: "L&D", title: "Onboarding guides", desc: "Adaptive mentors that answer questions from day one." },
              { label: "SUPPORT", title: "Resolution agents", desc: "Tier-1 triage with screen-share and visual context." },
              { label: "CUSTOM", title: "Bespoke PALs", desc: "Bring us any workflow — we'll design a PAL for it." },
            ].map((u) => (
              <RetroCard key={u.label} label={u.label} title={u.title} description={u.desc} cta={{ label: "Learn more", href: "/solutions" }} />
            ))}
          </div>
        </PageSection>
      </main>
      <Footer />
    </div>
  );
}
