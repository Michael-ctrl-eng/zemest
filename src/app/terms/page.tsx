import { Navbar } from "@/components/site/navbar";
import { Footer } from "@/components/site/footer";
import { PageHero, PageSection } from "@/components/site/page-shell";

export const metadata = { title: "Terms of Service — Zemest" };

export default function TermsPage() {
  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main>
        <PageHero eyebrow="LEGAL" title={<>Terms of <span className="serif-italic">service</span></>} description="The rules of using Zemest." />
        <PageSection bg="grain">
          <div className="prose prose-sm max-w-2xl mx-auto space-y-4 text-[var(--tavus-terminal-black)]">
            <p>By using Zemest, you agree to these terms. Use the service lawfully, don&apos;t abuse it, and respect the rights of your customers.</p>
            <h3 className="font-[var(--font-serif-display)] text-2xl font-normal">Acceptable use</h3>
            <p>You may not use Zemest to send spam, deceive customers, or violate any law. Agents must clearly indicate they are automated where required by local regulation.</p>
            <h3 className="font-[var(--font-serif-display)] text-2xl font-normal">Accounts & billing</h3>
            <p>Plans are month-to-month. You can cancel anytime. Refunds are issued at our discretion within 14 days of payment.</p>
            <p className="text-xs text-[var(--tavus-hardware-gray-8)] mt-8">Last updated: August 2026</p>
          </div>
        </PageSection>
      </main>
      <Footer />
    </div>
  );
}
