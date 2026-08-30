import { Navbar } from "@/components/site/navbar";
import { Footer } from "@/components/site/footer";
import { PageHero, PageSection, RetroCard } from "@/components/site/page-shell";
import { ArrowUpRight, MapPin, Heart, Shield, Sparkles, Users, Zap } from "lucide-react";

export const metadata = { title: "Careers | Zemest — The Conversational Commerce Company" };

const principles = [
  { icon: Zap, title: "Faster, faster", desc: "No legacy systems. No bloated process. Just better ideas, tested quickly." },
  { icon: Shield, title: "Results over effort", desc: "We measure outcomes, not hours. Ship something that matters." },
  { icon: Sparkles, title: "Craft and conviction", desc: "We take inspiration from the past, as we barrel towards the future." },
  { icon: Users, title: "On the shoulders of giants", desc: "We support each other, challenge each other, and grow together." },
  { icon: Heart, title: "People first", desc: "We're building something amazing. And we're having a lot of fun doing it." },
  { icon: Zap, title: "Challenge convention", desc: "We're a small team by design. Everyone here meaningfully shapes outcomes." },
];

const perks = [
  { title: "Fully-covered medical, dental, vision", desc: "For you and your family." },
  { title: "Gear + learning stipends", desc: "Set up your workspace with the tools you need to do your best work." },
  { title: "Wellness benefits", desc: "We support your health, in and out of the office." },
  { title: "Learn from AI leaders", desc: "Work alongside AI leaders and learn every day through meaningful ownership." },
  { title: "Semi-annual team retreats", desc: "Semi-annual full team retreats. Always a highlight of everyone's year." },
  { title: "Competitive pay + equity", desc: "Competitive pay and meaningful ownership in the company we're building together." },
];

const roles = [
  { team: "ENGINEERING", title: "Senior Research Engineer — Perception", location: "San Francisco · Remote", type: "Full-time" },
  { team: "ENGINEERING", title: "Staff Frontend Engineer", location: "Remote · US/EU", type: "Full-time" },
  { team: "ENGINEERING", title: "Distributed Systems Engineer", location: "San Francisco", type: "Full-time" },
  { team: "RESEARCH", title: "Research Scientist — Conversational AI", location: "San Francisco · Remote", type: "Full-time" },
  { team: "DESIGN", title: "Senior Product Designer", location: "San Francisco · Remote", type: "Full-time" },
  { team: "GO-TO-MARKET", title: "Enterprise Account Executive", location: "New York · Remote", type: "Full-time" },
  { team: "GO-TO-MARKET", title: "Solutions Engineer", location: "San Francisco", type: "Full-time" },
  { team: "PEOPLE", title: "Technical Recruiter", location: "Remote · US", type: "Full-time" },
];

export default function CareersPage() {
  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main>
        <PageHero
          eyebrow="CAREERS"
          title={<>Work at <span className="serif-italic">Zemest</span></>}
          description="Join the team decoding conversation. Zemest is an AI research lab reimagining the human and machine interface. We're building the foundations of conversational commerce — AI that sees, hears, and responds with emotion, so talking to a computer feels as natural as talking to a friend."
          ctas={[{ label: "Explore open roles", href: "#roles", variant: "primary" }]}
        />

        {/* The Next Intelligence is Emotional */}
        <PageSection bg="grain">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-10 items-center">
            <div>
              <div className="inline-flex items-center gap-2 mb-4">
                <span className="w-2 h-2 bg-[var(--tavus-terminal-black)]" />
                <span className="text-[11px] font-bold tracking-[0.2em] uppercase text-[var(--tavus-hardware-gray-8)]">THE NEXT INTELLIGENCE</span>
              </div>
              <h2 className="font-[var(--font-serif-display)] text-4xl sm:text-5xl font-normal tracking-tight text-[var(--tavus-terminal-black)] leading-[1.05]">
                The Next Intelligence is <span className="serif-italic">Emotional</span>
              </h2>
              <p className="mt-6 text-base sm:text-lg text-[var(--tavus-hardware-gray-8)] leading-relaxed">
                We're a small team by design. Everyone here meaningfully shapes outcomes. We move fast, work hard, and care about craft. Our HQ is in San Francisco, with team members across the globe.
              </p>
              <p className="mt-4 text-base sm:text-lg text-[var(--tavus-hardware-gray-8)] leading-relaxed">
                If you care about the future of intelligence and how it feels, you'll fit right in.
              </p>
            </div>
            <div className="bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[8px_8px_0_0_var(--tavus-terminal-black)] p-8">
              <div className="text-[11px] font-bold tracking-[0.15em] uppercase text-[var(--tavus-bubbletech-4)]">YOU'VE NEVER TALKED TO AI LIKE THIS BEFORE</div>
              <p className="mt-4 font-[var(--font-serif-display)] text-2xl font-normal text-[var(--tavus-terminal-black)] leading-snug">
                Bring human connection to every AI interaction.
              </p>
              <p className="mt-4 text-sm text-[var(--tavus-hardware-gray-8)] leading-relaxed">
                We're researchers, engineers, and artists building AI that listens, learns, and connects like people do. Come decode the conversation with us.
              </p>
            </div>
          </div>
        </PageSection>

        {/* Our Principles */}
        <PageSection bg="white">
          <div className="text-center mb-10">
            <div className="inline-flex items-center gap-2 mb-4">
              <span className="w-2 h-2 bg-[var(--tavus-terminal-black)]" />
              <span className="text-[11px] font-bold tracking-[0.2em] uppercase text-[var(--tavus-hardware-gray-8)]">OUR PRINCIPLES</span>
              <span className="w-2 h-2 bg-[var(--tavus-terminal-black)]" />
            </div>
            <h2 className="font-[var(--font-serif-display)] text-4xl sm:text-5xl font-normal tracking-tight text-[var(--tavus-terminal-black)]">
              How we <span className="serif-italic">work</span>
            </h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {principles.map((p) => (
              <div key={p.title} className="bg-[var(--tavus-plastic-1)] border-[3px] border-[var(--tavus-terminal-black)] shadow-[6px_6px_0_0_var(--tavus-terminal-black)] hover:shadow-[8px_8px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 transition-all p-6">
                <p.icon className="h-7 w-7 text-[var(--tavus-terminal-black)]" strokeWidth={2} />
                <h3 className="mt-4 font-[var(--font-serif-display)] text-xl font-normal text-[var(--tavus-terminal-black)]">{p.title}</h3>
                <p className="mt-2 text-sm text-[var(--tavus-hardware-gray-8)] leading-relaxed">{p.desc}</p>
              </div>
            ))}
          </div>
        </PageSection>

        {/* Perks + Benefits */}
        <PageSection bg="grain">
          <div className="text-center mb-10">
            <div className="inline-flex items-center gap-2 mb-4">
              <span className="w-2 h-2 bg-[var(--tavus-terminal-black)]" />
              <span className="text-[11px] font-bold tracking-[0.2em] uppercase text-[var(--tavus-hardware-gray-8)]">PERKS + BENEFITS</span>
              <span className="w-2 h-2 bg-[var(--tavus-terminal-black)]" />
            </div>
            <h2 className="font-[var(--font-serif-display)] text-4xl sm:text-5xl font-normal tracking-tight text-[var(--tavus-terminal-black)]">
              Life at <span className="serif-italic">Zemest</span>
            </h2>
            <p className="mt-4 text-base text-[var(--tavus-hardware-gray-8)] max-w-2xl mx-auto leading-relaxed">
              Our team moves mountains to bring the vision to life, and we've got their backs.
            </p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {perks.map((p) => (
              <RetroCard key={p.title} label="PERK" title={p.title} description={p.desc} />
            ))}
          </div>
        </PageSection>

        {/* Open roles */}
        <PageSection bg="white" id="roles">
          <div className="text-center mb-10">
            <div className="inline-flex items-center gap-2 mb-4">
              <span className="w-2 h-2 bg-[var(--tavus-terminal-black)]" />
              <span className="text-[11px] font-bold tracking-[0.2em] uppercase text-[var(--tavus-hardware-gray-8)]">OPEN ROLES</span>
              <span className="w-2 h-2 bg-[var(--tavus-terminal-black)]" />
            </div>
            <h2 className="font-[var(--font-serif-display)] text-4xl sm:text-5xl font-normal tracking-tight text-[var(--tavus-terminal-black)]">
              Join <span className="serif-italic">us</span>
            </h2>
          </div>
          <div className="space-y-3">
            {roles.map((r) => (
              <a
                key={r.title}
                href="#"
                className="block bg-[var(--tavus-plastic-1)] border-[3px] border-[var(--tavus-terminal-black)] shadow-[4px_4px_0_0_var(--tavus-terminal-black)] hover:shadow-[6px_6px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] transition-all p-5"
              >
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                  <div>
                    <div className="text-[10px] font-bold tracking-[0.15em] uppercase text-[var(--tavus-bubbletech-4)]">{r.team}</div>
                    <h3 className="mt-1 font-[var(--font-serif-display)] text-2xl font-normal text-[var(--tavus-terminal-black)]">{r.title}</h3>
                    <div className="mt-1 flex items-center gap-3 text-xs text-[var(--tavus-hardware-gray-8)]">
                      <span className="flex items-center gap-1"><MapPin className="w-3 h-3" />{r.location}</span>
                      <span>·</span>
                      <span>{r.type}</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-1 text-[11px] font-bold tracking-wider uppercase text-[var(--tavus-terminal-black)]">
                    APPLY
                    <ArrowUpRight className="w-3.5 h-3.5" />
                  </div>
                </div>
              </a>
            ))}
          </div>
        </PageSection>
      </main>
      <Footer />
    </div>
  );
}
