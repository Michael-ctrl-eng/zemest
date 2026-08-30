import { Navbar } from "@/components/site/navbar";
import { Footer } from "@/components/site/footer";
import { PageHero, PageSection, RetroCard } from "@/components/site/page-shell";
import { Feather, Bird, ArrowUpRight } from "lucide-react";

export const metadata = { title: "Models — Zemest" };

const models = [
  {
    name: "Rabbit v1",
    family: "RABBIT",
    icon: Feather,
    role: "Arabic moderation · every dialect",
    desc: "Our flagship Arabic model. Speaks Egyptian, Gulf, Levantine, Maghrebi, Sudanese, and Yemeni — and replies in the same dialect the customer used. Voice-note transcription built in. Trained on millions of Arabic commerce conversations.",
    specs: [
      { k: "Dialects", v: "30+" },
      { k: "Voice", v: "Native" },
      { k: "Languages", v: "Arabic" },
    ],
    colorSquare: "var(--tavus-bubbletech-4)",
    sample: {
      user: "لو سمحت، عندي النايك الأبيض مقاس 42؟",
      agent: "أيوا متوفر، 2 pieces في المخزن. 850 جنيه. تحب أثبتهولك؟",
      lang: "ar",
    },
  },
  {
    name: "Rat v1",
    family: "RAT",
    icon: Bird,
    role: "English moderation · every accent",
    desc: "Our flagship English model. Handles US, UK, Australian, Indian, South African, and Irish English — the way your customers actually speak it. Reads images, listens to voice, replies in your brand tone.",
    specs: [
      { k: "Accents", v: "12+" },
      { k: "Voice", v: "Native" },
      { k: "Languages", v: "English" },
    ],
    colorSquare: "var(--tavus-neon-field-2)",
    sample: {
      user: "Hey, do you have these in a size 10?",
      agent: "Yep — 2 left in stock. $120. Want me to hold one?",
      lang: "en",
    },
  },
];

export default function ModelsPage() {
  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main>
        <PageHero
          eyebrow="MODELS"
          title={<>Two models. <span className="serif-italic">One mission.</span></>}
          description="Each Zemest model is specialized for a language — Rabbit v1 for Arabic, Rat v1 for English. Together they cover the conversations your customers actually have, in the dialects they actually use."
          ctas={[{ label: "Try an agent", href: "/get-started", variant: "primary" }]}
        />

        <PageSection bg="grain">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            {models.map((m) => (
              <div
                key={m.name}
                className="bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[6px_6px_0_0_var(--tavus-terminal-black)] hover:shadow-[8px_8px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[2px_2px_0_0_var(--tavus-terminal-black)] transition-all overflow-hidden"
              >
                <div className="flex items-center justify-between px-4 py-2 border-b-2 border-[var(--tavus-terminal-black)] bg-[var(--tavus-plastic-1)]">
                  <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 border border-[var(--tavus-terminal-black)] text-white" style={{ background: m.colorSquare }} />
                    <span className="text-[10px] font-bold tracking-wider uppercase">{m.family}</span>
                  </div>
                  <span className="text-[10px] font-mono font-bold text-[var(--tavus-hardware-gray-8)]">v1</span>
                </div>
                <div className="p-6">
                  <div className="flex items-end gap-3 mb-4">
                    <div
                      className="inline-flex h-14 w-14 items-center justify-center border-2 border-[var(--tavus-terminal-black)] shadow-[2px_2px_0_0_var(--tavus-terminal-black)]"
                      style={{ background: m.colorSquare }}
                    >
                      <m.icon className="h-6 w-6 text-[var(--tavus-terminal-black)]" strokeWidth={2} />
                    </div>
                    <div>
                      <h3 className="font-[var(--font-serif-display)] text-3xl font-normal leading-none text-[var(--tavus-terminal-black)]">
                        {m.name}
                      </h3>
                      <p className="text-[11px] font-bold tracking-wider uppercase text-[var(--tavus-terminal-black)]/70 mt-1">
                        {m.role}
                      </p>
                    </div>
                  </div>

                  <p className="text-sm text-[var(--tavus-terminal-black)]/80 leading-relaxed mb-5">{m.desc}</p>

                  <div className="grid grid-cols-3 gap-2 mb-5">
                    {m.specs.map((s) => (
                      <div key={s.k} className="bg-[var(--tavus-plastic-1)] border-2 border-[var(--tavus-terminal-black)] p-2">
                        <div className="text-[9px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)]">{s.k}</div>
                        <div className="text-sm font-bold text-[var(--tavus-terminal-black)] font-[var(--font-serif-display)] mt-0.5">{s.v}</div>
                      </div>
                    ))}
                  </div>

                  {/* Sample chat */}
                  <div className="bg-[var(--tavus-terminal-black)] border-2 border-[var(--tavus-terminal-black)] p-3 space-y-2">
                    <div className="text-[9px] font-mono text-white/40 uppercase tracking-wider">SAMPLE CONVERSATION</div>
                    <div className="bg-white border border-white p-2 text-[12px] text-[var(--tavus-terminal-black)]" dir={m.sample.lang === "ar" ? "rtl" : "ltr"}>
                      <span className="text-[9px] font-bold text-[var(--tavus-hardware-gray-8)] uppercase block mb-1">CUSTOMER</span>
                      {m.sample.user}
                    </div>
                    <div className="border-2 border-white p-2 text-[12px] text-[var(--tavus-terminal-black)] ml-8" style={{ background: m.colorSquare }} dir={m.sample.lang === "ar" ? "rtl" : "ltr"}>
                      <span className="text-[9px] font-bold text-[var(--tavus-terminal-black)]/70 uppercase block mb-1">AGENT</span>
                      {m.sample.agent}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </PageSection>

        {/* Capabilities */}
        <PageSection bg="white">
          <div className="text-center mb-10">
            <h2 className="font-[var(--font-serif-display)] text-4xl sm:text-5xl font-normal tracking-tight text-[var(--tavus-terminal-black)]">
              What every agent <span className="serif-italic">can do</span>
            </h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {[
              { label: "TEXT", title: "Reads every message", desc: "From DMs to comments — answers in <3 seconds, in your brand tone." },
              { label: "VOICE", title: "Listens to voice notes", desc: "Transcribes Arabic + English voice messages natively, with dialect-aware accuracy." },
              { label: "IMAGE", title: "Looks at images", desc: "Customer sends a product photo? Agent recognizes it and replies with stock info." },
              { label: "INVENTORY", title: "Checks stock live", desc: "Connects to your shop or POS. Knows what's in stock before answering." },
            ].map((c) => (
              <RetroCard key={c.label} label={c.label} title={c.title} description={c.desc} />
            ))}
          </div>
        </PageSection>
      </main>
      <Footer />
    </div>
  );
}
