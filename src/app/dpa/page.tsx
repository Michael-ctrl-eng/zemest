import { Navbar } from "@/components/site/navbar";
import { Footer } from "@/components/site/footer";
import { PageHero, PageSection } from "@/components/site/page-shell";

export const metadata = { title: "Data Processing Addendum — Zemest" };

export default function DpaPage() {
  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main>
        <PageHero
          eyebrow="LEGAL"
          title={<>Data processing <span className="serif-italic">addendum</span></>}
          description="How Zemest processes personal data on behalf of your store — the plain-language summary of the DPA available for signature on request."
        />
        <PageSection bg="grain">
          <div className="prose prose-sm max-w-2xl mx-auto space-y-4 text-[var(--tavus-terminal-black)]">
            <p>
              When your agent talks to a customer, Zemest processes that conversation on your
              behalf. In GDPR terms: you are the controller, we are the processor, and this
              page summarizes what that means in practice. The full addendum is available for
              signature at hello@zemest.ai.
            </p>

            <h3 className="font-[var(--font-serif-display)] text-2xl font-normal">What we process, and why</h3>
            <p>
              We process customer messages (text, voice, images), order details (name, address,
              phone, payment method), and product catalogs — for exactly one purpose: operating
              the moderation service you configured. We do not process your customer data for
              our own marketing, we do not sell it, and we do not use it to train models
              shared across customers without your written permission.
            </p>

            <h3 className="font-[var(--font-serif-display)] text-2xl font-normal">Where it lives</h3>
            <p>
              Data is stored on encrypted infrastructure in the region you chose at signup,
              with EU residency available on request. Access tokens for connected channels are
              encrypted at rest and never logged. Retention follows your instructions: delete
              your account and your data is deleted on schedule; export it first if you need
              it — your data is yours.
            </p>

            <h3 className="font-[var(--font-serif-display)] text-2xl font-normal">Sub-processors</h3>
            <p>
              We keep a short list, and we tell you before it changes: cloud hosting, the
              model providers that generate replies under our instructions, and the messaging
              platforms you connect (Meta and WhatsApp). Each is bound by data-protection
              terms no weaker than these. The current list with locations is available on
              request.
            </p>

            <h3 className="font-[var(--font-serif-display)] text-2xl font-normal">Your rights, our duties</h3>
            <p>
              As the controller, you answer your customers&apos; access and deletion requests —
              and we make that possible: conversations, orders, and customer records are
              exportable and erasable from your dashboard, on demand. As your processor, we
              assist with security incidents (notifying you without undue delay), assist with
              regulator inquiries, and certify compliance with standard contractual clauses
              where transfers apply.
            </p>

            <h3 className="font-[var(--font-serif-display)] text-2xl font-normal">Security measures</h3>
            <p>
              Encryption in transit and at rest, per-tenant data isolation, least-privilege
              access with audited administrative actions, short-lived signed sessions, and
              independent security reviews. If you need the detailed technical and
              organizational measures annex, ask — we&apos;ll send it the same day.
            </p>

            <p className="text-xs text-[var(--tavus-hardware-gray-8)] mt-8">Last updated: August 2026</p>
          </div>
        </PageSection>
      </main>
      <Footer />
    </div>
  );
}
