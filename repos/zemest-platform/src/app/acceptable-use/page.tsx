import { Navbar } from "@/components/site/navbar";
import { Footer } from "@/components/site/footer";
import { PageHero, PageSection } from "@/components/site/page-shell";

export const metadata = { title: "TITLE — Zemest" };

export default function Page() {
  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main>
        <PageHero eyebrow="EYEBROW" title={<>TITLE <span className="serif-italic">italic</span></>} description="DESCRIPTION" />
        <PageSection bg="grain">
          <div className="max-w-2xl mx-auto space-y-4 text-[var(--tavus-terminal-black)]">
            <p>This page is coming soon. In the meantime, contact us at hello@zemest.ai with any questions.</p>
          </div>
        </PageSection>
      </main>
      <Footer />
    </div>
  );
}
