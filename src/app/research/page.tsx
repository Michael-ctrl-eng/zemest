import { Navbar } from "@/components/site/navbar";
import { Footer } from "@/components/site/footer";
import { PageHero, PageSection, RetroCard } from "@/components/site/page-shell";
import { ArrowUpRight } from "lucide-react";

export const metadata = { title: "Zemest Research: Pioneering Conversational Commerce" };

const researchAreas = [
  { label: "DIALECT", title: "Register matching", desc: "Detecting the dialect of the first message in under 50ms, so every reply speaks the buyer's variety — not textbook MSA." },
  { label: "LISTENING", title: "Voice understanding", desc: "Transcribing Egyptian and Gulf voice notes with their code-switching, street noise, and four-second brevity intact." },
  { label: "PERCEPTION", title: "Image grounding", desc: "Matching the screenshot a buyer sends to the catalog behind it — the shoe, the price list, the blurry in-store photo." },
  { label: "GROUNDING", title: "Fact discipline", desc: "Constraining every price and availability claim to the live inventory record, so confidence never outruns the truth." },
  { label: "MEMORY", title: "Style learning", desc: "Studying how a seller actually writes — phrasing, warmth, shorthand — and folding that voice into the agent over time." },
  { label: "EVALUATION", title: "Conversation science", desc: "Measuring what matters in a sales chat: not fluency scores, but whether the reply kept the conversation moving to an order." },
];

const traits = [
  { label: "SPEAKS LIKE YOU", title: "(in every dialect)", desc: "Agents reply in the register the buyer opened with — Egyptian, Gulf, Levantine, Maghrebi, or English.", items: [
    "Dialect is detected on the first message and locked for the whole conversation.",
    "Sellers train the agent on their own phrasing, emoji, and shorthand via the silent trainer.",
    "Formality is treated as distance: casual buyers get casual replies.",
  ]},
  { label: "NEVER GUESSES", title: "(grounded or silent)", desc: "Every price, size, and availability claim is checked against live inventory before a word is written.", items: [
    "Retrieval runs before generation: the product record constrains the reply.",
    "Out-of-catalog questions get honest answers and the closest real match — never an invented price.",
    "Stock re-syncs continuously, so a 2 a.m. reply reflects the 1:58 a.m. sale.",
  ]},
  { label: "CLOSES THE LOOP", title: "(to the order)", desc: "Agents are optimized for the conversation's business outcome, not for ending the thread.", items: [
    "Order confirmations are written and confirmed before capture — item, total, address, payment method.",
    "Out-of-stock replies offer the wait, the alternative, or the variation instead of a dead end.",
    "Emotional moments and edge cases route to a human, by design.",
  ]},
];

const papers = [
  { label: "DIALECT", title: "Rabbit v1: Learning to Sell in Six Arabic Dialects", desc: "How we trained an Arabic model that replies in Egyptian, Gulf, Levantine, and Maghrebi — and why the gap between MSA and how people text decides whether buyers trust a store." },
  { label: "LATENCY", title: "Detecting Dialect in Under 50 Milliseconds", desc: "The register of the first message decides the register of every reply after it. Inside the single-purpose classifier that makes that call before the buyer's cursor blinks — and the evaluation harness that keeps it honest." },
  { label: "VOICE", title: "Voice Notes Are Half Your Inbox", desc: "Egyptian buyers send audio the way other markets send text. Rebuilding transcription around real commerce speech: code-switching, street noise, and the four-second note that just says 'same as before'." },
  { label: "GROUNDING", title: "Grounded by Design: Every Reply Checks Your Stock First", desc: "The most expensive sentence an AI can write is a confident price. Our order of operations puts the live inventory record before the model, and treats hallucination as a solvable architecture problem." },
  { label: "EVALUATION", title: "Bots Answer. Agents Sell.", desc: "The chatbot era optimized for deflection; commerce agents optimize for the opposite. The metrics, training signals, and design decisions that come from measuring whether a conversation reaches an order." },
];

export default function ResearchPage() {
  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main>
        <PageHero
          eyebrow="RESEARCH"
          title={<>A new kind of <span className="serif-italic">research lab</span></>}
          description="We study how conversations become sales — dialect, tone, timing, and truthfulness — and turn what we learn into agents that sell like the best sellers do."
          ctas={[{ label: "Start a demo conversation", href: "/get-started", variant: "primary" }]}
        />

        {/* Bridging the divide */}
        <PageSection bg="grain">
          <div className="text-center max-w-3xl mx-auto">
            <h2 className="font-[var(--font-serif-display)] text-4xl sm:text-5xl font-normal tracking-tight text-[var(--tavus-terminal-black)]">
              Bridging the buyer-seller <span className="serif-italic">gap</span>
            </h2>
            <p className="mt-6 text-base sm:text-lg text-[var(--tavus-hardware-gray-8)] leading-relaxed">
              A store's chat has a rhythm: the buyer's dialect, the shorthand, the hour when
              questions arrive. At Zemest, we study that rhythm — what makes a buyer stay,
              what makes them go quiet, what closes the sale — and build agents that move
              with it. We&apos;re not chasing conversation for its own sake; we&apos;re chasing the
              moment a question becomes an order.
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
              What we&apos;re <span className="serif-italic">working on</span>
            </h2>
            <p className="mt-4 text-base text-[var(--tavus-hardware-gray-8)] max-w-2xl mx-auto leading-relaxed">
              Six disciplines, one goal: agents that answer like your best day, every day.
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
              Our research shows up as the traits that make agents <span className="serif-italic">sell</span>
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
              <RetroCard key={p.title} label={p.label} title={p.title} description={p.desc} cta={{ label: "Read the post", href: "/blog" }} />
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
              Honest by <span className="serif-italic">design</span>
            </h2>
            <p className="mt-6 text-base sm:text-lg text-[var(--tavus-hardware-gray-8)] leading-relaxed">
              An agent that sells for you is an agent that speaks to your customers under
              your name — and we believe that comes with obligations. Our agents never claim
              to be human when asked, never invent facts to keep a conversation alive, and
              hand the emotional moments — complaints, refunds, anger — to a person. Customer
              conversations belong to the store that earned them, and every model we train
              runs on data with permission and purpose. The magic shouldn&apos;t be hidden; it
              should just work, honestly.
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
