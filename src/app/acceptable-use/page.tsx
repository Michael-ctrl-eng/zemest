import { Navbar } from "@/components/site/navbar";
import { Footer } from "@/components/site/footer";
import { PageHero, PageSection } from "@/components/site/page-shell";

export const metadata = { title: "Acceptable Use — Zemest" };

export default function AcceptableUsePage() {
  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main>
        <PageHero
          eyebrow="LEGAL"
          title={<>Acceptable <span className="serif-italic">use</span></>}
          description="The short list of things you can't do with Zemest — written to be read."
        />
        <PageSection bg="grain">
          <div className="prose prose-sm max-w-2xl mx-auto space-y-4 text-[var(--tavus-terminal-black)]">
            <p>
              Zemest exists to help honest stores answer their customers. These rules protect
              that mission — and the customers on the other end of every agent. Breaking them
              gets your account suspended; breaking them badly gets it closed.
            </p>

            <h3 className="font-[var(--font-serif-display)] text-2xl font-normal">Your agent must be honest</h3>
            <p>
              Don&apos;t configure your agent to misrepresent prices, stock, delivery terms, or
              who the buyer is talking to. Agents must never claim to be a human when asked
              directly, and must hand conversations to a real person when a customer asks for
              one. Lying at scale is worse than lying once — don&apos;t use us to do it.
            </p>

            <h3 className="font-[var(--font-serif-display)] text-2xl font-normal">No spam, no strangers</h3>
            <p>
              Agents answer people who wrote to you. They don&apos;t cold-message buyers, mass-DM
              strangers, post automated comments on other pages, or add customers to groups
              without consent. You must have a real relationship (or a real inbound message)
              with every person your agent replies to.
            </p>

            <h3 className="font-[var(--font-serif-display)] text-2xl font-normal">No illegal or harmful commerce</h3>
            <p>
              Don&apos;t use Zemest to sell products that are illegal in the markets you serve,
              to process payments for third parties, or to run schemes that depend on new
              money paying old promises. We also won&apos;t carry stores selling counterfeits —
              the &apos;inspired by&apos; shelf ends here.
            </p>

            <h3 className="font-[var(--font-serif-display)] text-2xl font-normal">Respect the platform rules</h3>
            <p>
              WhatsApp, Facebook, and Instagram each have their own commerce and automation
              policies. You connected those accounts; you&apos;re responsible for using them
              within the rules. Zemest builds to their APIs and passes their reviews — meet us
              halfway.
            </p>

            <h3 className="font-[var(--font-serif-display)] text-2xl font-normal">No scraping, no resale</h3>
            <p>
              Don&apos;t use the service to harvest customer data for resale, to train
              competing models, or to reverse-engineer our API. Your data is yours; our
              platform is ours; everyone&apos;s lawyers stay bored.
            </p>

            <p className="text-xs text-[var(--tavus-hardware-gray-8)] mt-8">Last updated: August 2026</p>
          </div>
        </PageSection>
      </main>
      <Footer />
    </div>
  );
}
