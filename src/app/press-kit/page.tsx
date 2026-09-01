import { Navbar } from "@/components/site/navbar";
import { Footer } from "@/components/site/footer";
import { PageHero, PageSection, RetroCard } from "@/components/site/page-shell";

export const metadata = { title: "Press Kit — Zemest" };

export default function PressKitPage() {
  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main>
        <PageHero
          eyebrow="PRESS KIT"
          title={<>Zemest, in <span className="serif-italic">short</span></>}
          description="Company facts, boilerplate, and media contact — everything you need to write about us accurately. Logo files are in the brand kit; interviews are faster than you'd expect."
        />

        <PageSection bg="grain">
          <div className="text-center mb-10">
            <h2 className="font-[var(--font-serif-display)] text-4xl sm:text-5xl font-normal tracking-tight text-[var(--tavus-terminal-black)]">
              The <span className="serif-italic">facts</span>
            </h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {[
              { label: "FOUNDED", title: "2026", desc: "Built in Cairo, for the merchants everyone else overlooks." },
              { label: "PRODUCT", title: "Commerce agents", desc: "AI agents that moderate and sell across WhatsApp, Facebook, and Instagram for small and mid-size stores." },
              { label: "MODELS", title: "Rabbit v1 & Rooster v1", desc: "Specialized Arabic (30+ dialects) and English (12+ accents) moderation models, trained on real commerce conversations." },
              { label: "CONTACT", title: "hello@zemest.ai", desc: "For press inquiries, interviews, and fact-checking. We answer within one business day." },
            ].map((s) => (
              <RetroCard key={s.label} label={s.label} title={s.title} description={s.desc} />
            ))}
          </div>
        </PageSection>

        <PageSection bg="white">
          <div className="text-center mb-10">
            <h2 className="font-[var(--font-serif-display)] text-4xl sm:text-5xl font-normal tracking-tight text-[var(--tavus-terminal-black)]">
              Approved <span className="serif-italic">boilerplate</span>
            </h2>
          </div>
          <div className="max-w-3xl mx-auto space-y-4">
            <div className="bg-[var(--tavus-plastic-1)] border-[3px] border-[var(--tavus-terminal-black)] shadow-[4px_4px_0_0_var(--tavus-terminal-black)] p-6">
              <div className="text-[10px] font-bold tracking-[0.15em] uppercase text-[var(--tavus-hardware-gray-8)]">SHORT (ONE SENTENCE)</div>
              <p className="mt-3 text-sm text-[var(--tavus-terminal-black)] leading-relaxed">
                Zemest is the commerce moderation company — its AI agents answer and sell for stores on WhatsApp, Facebook, and Instagram, in every Arabic dialect and in English.
              </p>
            </div>
            <div className="bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[4px_4px_0_0_var(--tavus-terminal-black)] p-6">
              <div className="text-[10px] font-bold tracking-[0.15em] uppercase text-[var(--tavus-hardware-gray-8)]">LONG (ONE PARAGRAPH)</div>
              <p className="mt-3 text-sm text-[var(--tavus-terminal-black)] leading-relaxed">
                Zemest builds AI agents that moderate and sell for small and mid-size stores across WhatsApp, Facebook, and Instagram. Its specialized models — Rabbit v1 for Arabic and Rooster v1 for English — reply in the customer&apos;s own dialect or accent within seconds, reading text, voice notes, and images, and checking live inventory before quoting a price. Orders are captured and confirmed in writing, and a silent trainer learns each seller&apos;s tone from their own messages, so customers can&apos;t tell the agent from the owner. Zemest is headquartered in Cairo and serves merchants across the Middle East and North Africa.
              </p>
            </div>
            <div className="bg-[var(--tavus-plastic-1)] border-[3px] border-[var(--tavus-terminal-black)] shadow-[4px_4px_0_0_var(--tavus-terminal-black)] p-6">
              <div className="text-[10px] font-bold tracking-[0.15em] uppercase text-[var(--tavus-hardware-gray-8)]">USAGE NOTES</div>
              <ul className="mt-3 space-y-2.5">
                {[
                  "The company is 'Zemest' — one word, never 'Zemest AI'.",
                  "The products are 'agents'; 'chatbots' and 'AI assistants' are both wrong.",
                  "Rabbit v1 and Rooster v1 are models, not separate products.",
                  "Please link to zemest.ai rather than deep-linking app pages.",
                ].map((t) => (
                  <li key={t} className="flex items-start gap-3 text-sm text-[var(--tavus-terminal-black)]">
                    <span className="mt-1.5 w-2 h-2 bg-[var(--tavus-terminal-black)] shrink-0" />
                    <span>{t}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </PageSection>
      </main>
      <Footer />
    </div>
  );
}
