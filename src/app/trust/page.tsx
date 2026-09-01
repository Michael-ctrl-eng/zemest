import { Navbar } from "@/components/site/navbar";
import { Footer } from "@/components/site/footer";
import { PageHero, PageSection, RetroCard } from "@/components/site/page-shell";

export const metadata = { title: "Trust Center — Zemest" };

export default function TrustPage() {
  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main>
        <PageHero
          eyebrow="TRUST"
          title={<>Your customers&apos; trust, <span className="serif-italic">in our hands</span></>}
          description="An agent that talks to your customers under your name carries your reputation. Here's exactly how we handle the data behind those conversations — and the promises we've built into the product."
        />

        <PageSection bg="grain">
          <div className="text-center mb-10">
            <h2 className="font-[var(--font-serif-display)] text-4xl sm:text-5xl font-normal tracking-tight text-[var(--tavus-terminal-black)]">
              How we treat your <span className="serif-italic">data</span>
            </h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {[
              { label: "OWNERSHIP", title: "Your data is yours", desc: "Conversations, products, orders, and customer details belong to your store. Export everything anytime from Settings — no export fees, no ticket required." },
              { label: "MINIMIZATION", title: "Only what's needed", desc: "We hold account details, connected chats, and order information — because the service needs them. Nothing is collected beyond that list." },
              { label: "ISOLATION", title: "Tenant separation", desc: "Every store's data is isolated at the tenant boundary. One store's catalog, chats, and style profile are never mixed with another's." },
              { label: "NO SELLING", title: "Never sold, never shared", desc: "We don't sell, rent, or trade your data — not messages, not addresses, not phone numbers. Our revenue comes from subscriptions, full stop." },
              { label: "DELETION", title: "Erasure on request", desc: "Close your account and your data is deleted on schedule — not archived 'just in case'. Ask us and we'll confirm it in writing." },
              { label: "TRANSPARENCY", title: "Plain-language promises", desc: "Our privacy policy and DPA are written to be read, not survived. If any clause confuses you, that's a bug — email us and we'll fix the wording." },
            ].map((s) => (
              <RetroCard key={s.title} label={s.label} title={s.title} description={s.desc} />
            ))}
          </div>
        </PageSection>

        <PageSection bg="white">
          <div className="text-center mb-10">
            <h2 className="font-[var(--font-serif-display)] text-4xl sm:text-5xl font-normal tracking-tight text-[var(--tavus-terminal-black)]">
              How we run the <span className="serif-italic">platform</span>
            </h2>
          </div>
          <div className="max-w-3xl mx-auto space-y-4">
            {[
              { title: "Security posture", body: "All traffic is encrypted in transit; credentials and access tokens are stored encrypted at rest and are never logged. Sessions use short-lived signed tokens, and administrative actions are audited. We undergo independent security reviews of our infrastructure and access controls." },
              { title: "Compliance", body: "SOC 2 Type II controls are in place with reports available on request for enterprise customers. GDPR compliance includes EU data residency options, a Data Processing Addendum with standard contractual clauses, and documented sub-processors. HIPAA BAAs are available where required." },
              { title: "Reliability", body: "Growth plans carry a 99.9% uptime commitment and Enterprise 99.95% with financial credits. Component health is published on the status page, and incidents get a written post-mortem — the honest kind, not the kind written by a lawyer." },
              { title: "The honesty line", body: "Our agents never claim to be human when asked directly, never invent prices or stock levels to keep a conversation alive, and route complaints, refunds, and angry customers to a person. We believe trust is the product; everything else is features." },
            ].map((s) => (
              <div key={s.title} className="bg-[var(--tavus-plastic-1)] border-[3px] border-[var(--tavus-terminal-black)] shadow-[4px_4px_0_0_var(--tavus-terminal-black)] p-6">
                <h3 className="font-[var(--font-serif-display)] text-2xl font-normal text-[var(--tavus-terminal-black)]">{s.title}</h3>
                <p className="mt-3 text-sm text-[var(--tavus-hardware-gray-8)] leading-relaxed">{s.body}</p>
              </div>
            ))}
          </div>
        </PageSection>
      </main>
      <Footer />
    </div>
  );
}
