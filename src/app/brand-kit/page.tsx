import { Navbar } from "@/components/site/navbar";
import { Footer } from "@/components/site/footer";
import { PageHero, PageSection, RetroCard } from "@/components/site/page-shell";

export const metadata = { title: "Brand Kit — Zemest" };

export default function BrandKitPage() {
  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main>
        <PageHero
          eyebrow="BRAND KIT"
          title={<>The Zemest <span className="serif-italic">look</span></>}
          description="Everything you need to reference Zemest correctly — the wordmark, the palette, the type, and the voice. Write to hello@zemest.ai for current logo files and usage questions."
        />

        <PageSection bg="grain">
          <div className="text-center mb-10">
            <h2 className="font-[var(--font-serif-display)] text-4xl sm:text-5xl font-normal tracking-tight text-[var(--tavus-terminal-black)]">
              The <span className="serif-italic">basics</span>
            </h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {[
              { label: "WORDMARK", title: "zemest", desc: "Lowercase, set tight, always as one word. Never 'ZemestAI', never 'ZEMEST AI'. In running text, capitalize normally: Zemest." },
              { label: "LOGO", title: "The Z mark", desc: "The square Z sits in a bordered box with a hard offset shadow — it should never float, gradient, or glow. Clear space equals the box's border width on all sides." },
              { label: "TAGLINE", title: "The commerce moderation company", desc: "Our one-line description of record. Use it whole or not at all — and never as part of a longer sentence of your own." },
              { label: "NAMING", title: "Products", desc: "Rabbit v1 (Arabic) and Rooster v1 (English) — always lowercase 'v', never 'V1'. Inventory Connect is two words, capitalized." },
            ].map((s) => (
              <RetroCard key={s.label} label={s.label} title={s.title} description={s.desc} />
            ))}
          </div>
        </PageSection>

        <PageSection bg="white">
          <div className="text-center mb-10">
            <h2 className="font-[var(--font-serif-display)] text-4xl sm:text-5xl font-normal tracking-tight text-[var(--tavus-terminal-black)]">
              Color &amp; <span className="serif-italic">type</span>
            </h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5 max-w-4xl mx-auto">
            <div className="bg-[var(--tavus-plastic-1)] border-[3px] border-[var(--tavus-terminal-black)] shadow-[6px_6px_0_0_var(--tavus-terminal-black)] p-6">
              <h3 className="font-[var(--font-serif-display)] text-2xl font-normal text-[var(--tavus-terminal-black)]">Palette</h3>
              <div className="mt-4 grid grid-cols-2 gap-3">
                {[
                  { name: "Terminal black", hex: "#140206", bg: "#140206", light: true },
                  { name: "Paper white", hex: "#FFFFFF", bg: "#FFFFFF", light: false },
                  { name: "Bubble tech", hex: "Warm cream-yellow", bg: "var(--tavus-bubbletech-4)", light: false },
                  { name: "Neon field", hex: "Deep signal green", bg: "var(--tavus-neon-field-2)", light: true },
                ].map((c) => (
                  <div key={c.name} className="border-2 border-[var(--tavus-terminal-black)]">
                    <div
                      className="h-16"
                      style={{ background: c.bg }}
                    />
                    <div className="bg-white px-2 py-1.5">
                      <div className="text-[11px] font-bold text-[var(--tavus-terminal-black)]">{c.name}</div>
                      <div className="text-[10px] text-[var(--tavus-hardware-gray-8)]">{c.hex}</div>
                    </div>
                  </div>
                ))}
              </div>
              <p className="mt-4 text-sm text-[var(--tavus-hardware-gray-8)] leading-relaxed">
                Our palette is built for contrast: near-black ink on paper, with cream and signal-green accents used sparingly. If a layout needs a mid-gray, the type — not the palette — is wrong.
              </p>
            </div>
            <div className="bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[6px_6px_0_0_var(--tavus-terminal-black)] p-6">
              <h3 className="font-[var(--font-serif-display)] text-2xl font-normal text-[var(--tavus-terminal-black)]">Typography</h3>
              <ul className="mt-4 space-y-3">
                {[
                  "Headlines: a high-contrast serif, set large and tight — serif italics carry the emphasis inside a headline, never bold.",
                  "Body: a neutral grotesque with generous leading; long-form never justified, always left-aligned.",
                  "Labels & UI: a monospace in uppercase with wide tracking — it's the 'control panel' voice of the product.",
                  "One rule above all: no letter may be decorative. Our type is print-inspired, not computer-styled.",
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

        <PageSection bg="grain">
          <div className="max-w-3xl mx-auto text-center">
            <h2 className="font-[var(--font-serif-display)] text-4xl sm:text-5xl font-normal tracking-tight text-[var(--tavus-terminal-black)]">
              The <span className="serif-italic">voice</span>
            </h2>
            <p className="mt-6 text-base sm:text-lg text-[var(--tavus-hardware-gray-8)] leading-relaxed">
              Zemest sounds like the best version of a store owner: warm, direct, and allergic to hype. We
              write the way our agents sell — short sentences, concrete facts, one idea per line. We say
              &apos;agent&apos; and not &apos;AI assistant&apos;, &apos;reply&apos; and not &apos;engage&apos;, &apos;price&apos; and not
              &apos;value proposition&apos;. Humor is allowed when it&apos;s earned; buzzwords are not. If a sentence
              could survive being read aloud to a Cairo shop owner without embarrassment, it ships.
            </p>
          </div>
        </PageSection>
      </main>
      <Footer />
    </div>
  );
}
