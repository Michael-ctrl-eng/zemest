import { Navbar } from "@/components/site/navbar";
import { Footer } from "@/components/site/footer";
import { PageHero, PageSection, RetroCard } from "@/components/site/page-shell";
import { ArrowUpRight } from "lucide-react";

export const metadata = { title: "Zemest Research: Pioneering Conversational Commerce" };

const researchAreas = [
  { label: "PERCEPTION", title: "Multimodal", desc: "Understanding meaning beyond words. Tone, timing, intent, and everything unsaid." },
  { label: "LISTENING", title: "Awareness", desc: "Teaching machines to truly listen. Not just to sounds, but to emotion, cadence, and rhythm." },
  { label: "AGENCY", title: "Thinking", desc: "Building systems that act with awareness, not automation. Capable of response, reasoning, and restraint." },
  { label: "VOICE", title: "Expression", desc: "Synthesizing voice that carries emotion, not just words. Warmth, hesitation, humor, humanity." },
  { label: "MOTION", title: "Rendering", desc: "Turning intelligence into motion. Seamless, lifelike expression that feels natural and alive." },
  { label: "DIALOGUE", title: "Conversation", desc: "Making dialogue intuitive and human. Conversations that adapt, remember, and build trust over time." },
];

const traits = [
  { label: "EXPRESSIVE", title: "(and authentic)", desc: "AI Humans bring face-to-face connection to every conversation.", items: [
    "Trained on millions of conversations to deliver smooth, humanlike dialogue.",
    "Understands actions, emotions, and screenshares to respond with context.",
    "Displays expressive reactions and movement that build trust and engagement.",
  ]},
  { label: "PERCEPTIVE", title: "(and aware)", desc: "AI Humans are modeled after us: they see, sense, and understand to build trust through real conversation.", items: [
    "Deciphers nonverbal cues like body language and micro-expressions. Uses context to adapt responses and create meaningful, two-way interactions.",
    "Every input adds context, ensuring the AI Human sees the full picture: screenshare, voice, and surroundings.",
    "Monitors key events and behaviors to trigger function calls while continuously sensing subtle background shifts with real-time data.",
  ]},
  { label: "THINKING", title: "(with agency)", desc: "AI Humans are fully formed, with the cognitive skills needed for efficient, effective conversations.", items: [
    "Industry-leading RAG grounds responses in your data. 15x faster than other solutions.",
    "Remembers past interactions to personalize responses and pickup conversations where they left off. Free to toggle on or off to fit any interaction.",
    "Uses customizable frameworks and logic branching to naturally structure conversations and keep moving toward your goals.",
  ]},
];

const papers = [
  { label: "TURN-TAKING", title: "Raven-1: Bringing Emotional Intelligence to Artificial Intelligence", desc: "Introducing Raven-1. A multimodal perception system that captures not just what users say, but how they say it, how they look when they say it, and what that combination actually means. It interprets tone, expression, hesitation, and context in real time, enabling AI that can truly understand intent rather than simply respond to words." },
  { label: "CONVERSATIONAL FLOW", title: "Sparrow-1: Human-Level Conversational Timing in Real-Time Voice", desc: "Sparrow-1 is a specialized, multilingual audio model for real-time conversational flow and floor transfer. It predicts when a system should listen, wait, or speak, enabling response timing that mirrors human conversation rather than simply responding as fast as possible." },
  { label: "INTERFACE", title: "The Knowledge Navigator, Reimagined", desc: "Forty years ago, Apple imagined the Knowledge Navigator. Meet Dom, our real-life take on it, and the conversational commerce interface from Zemest that powers him." },
  { label: "FACE-TO-FACE", title: "Modern AI faces can hold live conversations and read your expressions", desc: "Explore the rendering, turn-taking, and perception models that make it possible." },
  { label: "COMPARISON", title: "Face-to-face conversational AI vs. chatbot", desc: "Understanding the full spectrum. The face-to-face conversational AI vs. chatbot comparison comes down to capability tiers. A guide to types, examples, and when to move from text to video." },
];

export default function ResearchPage() {
  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main>
        <PageHero
          eyebrow="RESEARCH"
          title={<>A new kind of <span className="serif-italic">research lab</span></>}
          description="We study how intelligence perceives context, emotion, and tone to create AI that understands and acts as humans do."
          ctas={[{ label: "Start a demo conversation", href: "/get-started", variant: "primary" }]}
        />

        {/* Bridging the divide */}
        <PageSection bg="grain">
          <div className="text-center max-w-3xl mx-auto">
            <h2 className="font-[var(--font-serif-display)] text-4xl sm:text-5xl font-normal tracking-tight text-[var(--tavus-terminal-black)]">
              Bridging the human-machine <span className="serif-italic">divide</span>
            </h2>
            <p className="mt-6 text-base sm:text-lg text-[var(--tavus-hardware-gray-8)] leading-relaxed">
              Human conversation is a rhythm — every glance, pause, and tone changes the meaning. At Zemest, we study that rhythm, designing AI that understands emotion, intent, and timing as one signal. We&apos;re building systems that don&apos;t just respond, they move with you.
            </p>
          </div>
        </PageSection>

        {/* Research areas */}
        <PageSection bg="white">
          <div className="text-center mb-10">
            <div className="inline-flex items-center gap-2 mb-4">
              <span className="w-2 h-2 bg-[var(--tavus-terminal-black)]" />
              <span className="text-[11px] font-bold tracking-[0.2em] uppercase text-[var(--tavus-hardware-gray-8)]">RESEARCH AREAS</span>
              <span className="w-2 h-2 bg-[var(--tavus-terminal-black)]" />
            </div>
            <h2 className="font-[var(--font-serif-display)] text-4xl sm:text-5xl font-normal tracking-tight text-[var(--tavus-terminal-black)]">
              We&apos;re building AI that feels <span className="serif-italic">human</span>
            </h2>
            <p className="mt-4 text-base text-[var(--tavus-hardware-gray-8)] max-w-2xl mx-auto leading-relaxed">
              Machines that see, listen, and respond naturally.
            </p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {researchAreas.map((r) => (
              <RetroCard key={r.label} label={r.label} title={r.title} description={r.desc} />
            ))}
          </div>
        </PageSection>

        {/* Traits */}
        <PageSection bg="grain">
          <div className="text-center mb-10">
            <div className="inline-flex items-center gap-2 mb-4">
              <span className="w-2 h-2 bg-[var(--tavus-terminal-black)]" />
              <span className="text-[11px] font-bold tracking-[0.2em] uppercase text-[var(--tavus-hardware-gray-8)]">TRAITS</span>
              <span className="w-2 h-2 bg-[var(--tavus-terminal-black)]" />
            </div>
            <h2 className="font-[var(--font-serif-display)] text-4xl sm:text-5xl font-normal tracking-tight text-[var(--tavus-terminal-black)]">
              Our research manifests as the traits that make AI feel <span className="serif-italic">human</span>
            </h2>
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
            {traits.map((t) => (
              <div key={t.label} className="bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[6px_6px_0_0_var(--tavus-terminal-black)] hover:shadow-[8px_8px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 transition-all p-6">
                <div className="text-[10px] font-bold tracking-[0.15em] uppercase text-[var(--tavus-bubbletech-4)]">{t.label}</div>
                <h3 className="mt-2 font-[var(--font-serif-display)] text-3xl font-normal text-[var(--tavus-terminal-black)]">
                  {t.title}
                </h3>
                <p className="mt-3 text-sm text-[var(--tavus-hardware-gray-8)] leading-relaxed">{t.desc}</p>
                <ul className="mt-4 space-y-3">
                  {t.items.map((item, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-[var(--tavus-terminal-black)]">
                      <span className="w-1.5 h-1.5 bg-[var(--tavus-terminal-black)] mt-1.5 shrink-0" />
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </PageSection>

        {/* Papers */}
        <PageSection bg="white">
          <div className="text-center mb-10">
            <h2 className="font-[var(--font-serif-display)] text-4xl sm:text-5xl font-normal tracking-tight text-[var(--tavus-terminal-black)]">
              Read our latest <span className="serif-italic">research</span>
            </h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            {papers.map((p) => (
              <RetroCard key={p.title} label={p.label} title={p.title} description={p.desc} cta={{ label: "Read paper", href: "#" }} />
            ))}
          </div>
        </PageSection>

        {/* Ethical */}
        <PageSection bg="grain">
          <div className="max-w-3xl mx-auto text-center">
            <div className="inline-flex items-center gap-2 mb-4">
              <span className="w-2 h-2 bg-[var(--tavus-terminal-black)]" />
              <span className="text-[11px] font-bold tracking-[0.2em] uppercase text-[var(--tavus-hardware-gray-8)]">ETHICS</span>
              <span className="w-2 h-2 bg-[var(--tavus-terminal-black)]" />
            </div>
            <h2 className="font-[var(--font-serif-display)] text-4xl sm:text-5xl font-normal tracking-tight text-[var(--tavus-terminal-black)]">
              Ethical and aligned <span className="serif-italic">by design</span>
            </h2>
            <p className="mt-6 text-base sm:text-lg text-[var(--tavus-hardware-gray-8)] leading-relaxed">
              We believe technology earns trust through honesty, not opacity. Zemest is built on informed consent, transparent systems, and full disclosure — no fine print, no hidden levers. Every model, dataset, and likeness we use exists with permission and purpose. You deserve to know how the magic works, and we&apos;re here to show you.
            </p>
            <a
              href="/blog"
              className="mt-8 inline-flex items-center gap-2 px-6 h-12 border-[3px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-bubbletech-4)] text-xs font-extrabold tracking-[0.08em] uppercase shadow-[4px_4px_0_0_var(--tavus-terminal-black)] hover:shadow-[6px_6px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] transition-all"
            >
              Read the blog
              <ArrowUpRight className="w-4 h-4" />
            </a>
          </div>
        </PageSection>
      </main>
      <Footer />
    </div>
  );
}
