import { Navbar } from "@/components/site/navbar";
import { Footer } from "@/components/site/footer";
import { PageHero, PageSection } from "@/components/site/page-shell";
import { ArrowUpRight } from "lucide-react";

export const metadata = { title: "Zemest Blog: Conversational Commerce & Conversational AI" };

const featured = {
  slug: "introducing-deployments-send-your-pal-into-the-world",
  category: "Product",
  title: "Introducing Deployments: Send Your PAL Into the World",
  author: "Hassaan Raza",
  date: "August 13, 2026",
  excerpt: "Deployments let you ship a PAL into production with the same confidence you ship code. Versioned, observable, and rollback-ready — your PALs now live where your customers do.",
  gradient: "from-[var(--tavus-bubbletech-1)] via-[var(--tavus-frost-4)] to-[var(--tavus-bubbletech-4)]",
};

const posts = [
  { slug: "phoenix-4-real-time-human-rendering-with-emotional-intelligence", category: "RESEARCH", title: "Phoenix-4", desc: "Real-time human rendering with emotional intelligence — our most lifelike model yet.", date: "Aug 31, 2026", gradient: "from-[var(--tavus-bubbletech-1)] to-[var(--tavus-bubbletech-4)]" },
  { slug: "raven-1-bringing-emotional-intelligence-to-artificial-intelligence", category: "RESEARCH", title: "Raven-1: Bringing Emotional Intelligence to Artificial Intelligence", desc: "A multimodal perception system that captures not just what users say, but how they say it.", date: "Aug 11, 2026", gradient: "from-[var(--tavus-frost-4)] to-[var(--tavus-frost-5)]" },
  { slug: "sparrow-1-human-level-conversational-timing-in-real-time-voice", category: "RESEARCH", title: "Sparrow-1: Human-Level Conversational Timing in Real-Time Voice", desc: "A specialized, multilingual audio model for real-time conversational flow and floor transfer.", date: "Aug 11, 2026", gradient: "from-[var(--tavus-atomic-glow-5)] to-[var(--tavus-atomic-glow-1)]" },
  { slug: "rag-chatbots-vs-rag-video-agents", category: "AI, NEWS, AND ETHICS", title: "RAG-powered chatbots vs. RAG-powered video agents", desc: "RAG chatbots retrieve facts fast. RAG video agents add presence, perception, and trust. See which interface fits your use case.", date: "Aug 11, 2026", gradient: "from-[var(--tavus-floppy-fog-1)] to-[var(--tavus-floppy-fog-3)]" },
  { slug: "onboarding-automation", category: "AI, NEWS, AND ETHICS", title: "Onboarding Automation: Where AI Video Replaces Manual Touchpoints", desc: "Workflows handle forms and provisioning. PALs handle the conversations that can't wait for Thursday's check-in.", date: "Aug 10, 2026", gradient: "from-[var(--tavus-bubbletech-1)] to-[var(--tavus-frost-4)]" },
  { slug: "candidate-experience-ai-video-agents", category: "AI, NEWS, AND ETHICS", title: "Candidate Experience: How AI Video Agents Make Every Applicant Feel Heard", desc: "AI video agents give every candidate a live, face-to-face screening conversation. See how PALs replace one-way video intros.", date: "Aug 10, 2026", gradient: "from-[var(--tavus-frost-4)] to-[var(--tavus-bubbletech-1)]" },
  { slug: "realistic-ai-avatars", category: "AI, NEWS, AND ETHICS", title: "Realistic AI Avatars: How to Create and Evaluate Them (2026)", desc: "Learn what makes AI video agents realistic, how they're built, and how to evaluate platforms on latency, perception, and presence.", date: "Aug 10, 2026", gradient: "from-[var(--tavus-atomic-glow-5)] to-[var(--tavus-bubbletech-1)]" },
  { slug: "what-is-human-computing", category: "AI, NEWS, AND ETHICS", title: "What Is Conversational Commerce? The Research Behind Making AI Feel Human", desc: "Human computing makes AI feel human through perception, timing, and memory. Explore the research foundation.", date: "Aug 10, 2026", gradient: "from-[var(--tavus-floppy-fog-3)] to-[var(--tavus-frost-5)]" },
  { slug: "ai-human", category: "AI, NEWS, AND ETHICS", title: "AI Humans: What They Are, How They Work, and Why Enterprise Cares", desc: "AI humans see, hear, and respond in real time. Learn how full-stack AI humans work and where enterprises deploy them.", date: "Aug 10, 2026", gradient: "from-[var(--tavus-bubbletech-4)] to-[var(--tavus-floppy-fog-3)]" },
  { slug: "ai-knowledge-base", category: "GUIDE", title: "AI knowledge base: 2026 guide to powering conversational agents", desc: "Learn how a video knowledge base powers AI humans with RAG retrieval, grounded responses, and real-time accuracy.", date: "Aug 10, 2026", gradient: "from-[var(--tavus-frost-5)] to-[var(--tavus-bubbletech-1)]" },
  { slug: "hiring-process-automation", category: "AI, NEWS, AND ETHICS", title: "Hiring Process Automation: Where AI Video Agents Can Reduce Manual Work", desc: "See where hiring process automation saves recruiters the most time, from screening to scheduling, and where it falls short.", date: "Aug 10, 2026", gradient: "from-[var(--tavus-atomic-glow-5)] to-[var(--tavus-frost-4)]" },
  { slug: "video-prospecting", category: "AI, NEWS, AND ETHICS", title: "Video prospecting: how PALs can support personalized outreach at scale", desc: "AI agents turn video prospecting into live, two-way conversations that answer questions, catch hesitation, and book meetings.", date: "Aug 10, 2026", gradient: "from-[var(--tavus-bubbletech-1)] to-[var(--tavus-atomic-glow-5)]" },
  { slug: "ai-for-customer-success", category: "AI, NEWS, AND ETHICS", title: "AI for Customer Success: Video Agents for Renewal, Upsell, and QBRs", desc: "See how AI video agents help customer success teams run renewal calls, upsell conversations, and QBRs that don't feel like QBRs.", date: "Aug 10, 2026", gradient: "from-[var(--tavus-floppy-fog-1)] to-[var(--tavus-bubbletech-4)]" },
  { slug: "customer-retention-strategy", category: "AI, NEWS, AND ETHICS", title: "Customer Retention Strategy: How PALs Build Loyalty", desc: "Build customer loyalty with proactive support, real-time AI video agents, and persistent memory. See how Zemest PALs reduce churn.", date: "Aug 10, 2026", gradient: "from-[var(--tavus-frost-4)] to-[var(--tavus-atomic-glow-5)]" },
  { slug: "employee-experience-ai-video-touchpoints", category: "AI, NEWS, AND ETHICS", title: "Employee Experience: How AI Video Touchpoints Transform the Journey", desc: "Real-time AI video agents turn onboarding, policy questions, coaching, and exit interviews into live conversations.", date: "Aug 10, 2026", gradient: "from-[var(--tavus-bubbletech-4)] to-[var(--tavus-frost-5)]" },
  { slug: "facial-expression-ai", category: "AI, NEWS, AND ETHICS", title: "Facial Expression Generation: Teaching AI Agents to Emote Naturally", desc: "Facial expression AI gives AI video agents contingent, well-timed expressions in live conversation.", date: "Aug 10, 2026", gradient: "from-[var(--tavus-atomic-glow-5)] to-[var(--tavus-floppy-fog-3)]" },
  { slug: "best-ai-avatar-generators", category: "AI, NEWS, AND ETHICS", title: "Best AI Avatar Generators in 2026: Consumer Tools vs. Enterprise Platforms", desc: "Compare AI avatar generators by use case: photo tools, pre-rendered video, and real-time AI humans.", date: "Aug 10, 2026", gradient: "from-[var(--tavus-frost-5)] to-[var(--tavus-atomic-glow-5)]" },
  { slug: "hipaa-compliant-ai-video-patient-conversations", category: "AI, NEWS, AND ETHICS", title: "HIPAA-Compliant AI Video: Building Secure Patient Conversations", desc: "Learn how to build secure, HIPAA-compliant AI video patient conversations with PALs, BAAs, encryption, and the workflows that scale.", date: "Aug 10, 2026", gradient: "from-[var(--tavus-bubbletech-1)] to-[var(--tavus-floppy-fog-1)]" },
];

export default function BlogPage() {
  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main>
        <PageHero
          eyebrow="BLOG"
          title={<>Latest insights in <span className="serif-italic">Conversational Commerce</span></>}
          description="Explore our blogs, research, and updates on Conversational Commerce. Engineering deep-dives, customer stories, and perspectives from the Zemest team."
        />

        {/* Featured post */}
        <PageSection bg="grain">
          <a
            href={`/blog/${featured.slug}`}
            className="block bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[8px_8px_0_0_var(--tavus-terminal-black)] hover:shadow-[10px_10px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[2px_2px_0_0_var(--tavus-terminal-black)] transition-all overflow-hidden"
          >
            <div className="grid grid-cols-1 lg:grid-cols-2">
              <div className={`aspect-[4/3] lg:aspect-auto bg-gradient-to-br ${featured.gradient} border-b-[3px] lg:border-b-0 lg:border-r-[3px] border-[var(--tavus-terminal-black)] relative`}>
                <div className="absolute inset-0 bg-halftone opacity-30" />
                <div className="absolute top-4 left-4 bg-white border-[2px] border-[var(--tavus-terminal-black)] px-3 py-1 text-[10px] font-extrabold tracking-wider uppercase">
                  FEATURED · {featured.category}
                </div>
              </div>
              <div className="p-8 sm:p-10">
                <h2 className="font-[var(--font-serif-display)] text-3xl sm:text-4xl font-normal leading-tight text-[var(--tavus-terminal-black)]">
                  {featured.title}
                </h2>
                <p className="mt-4 text-base text-[var(--tavus-hardware-gray-8)] leading-relaxed">
                  {featured.excerpt}
                </p>
                <div className="mt-6 flex items-center gap-3 text-[11px] font-mono text-[var(--tavus-hardware-gray-8)]">
                  <span className="font-bold text-[var(--tavus-terminal-black)]">{featured.author}</span>
                  <span>·</span>
                  <span>{featured.date}</span>
                </div>
                <div className="mt-6 inline-flex items-center gap-1.5 text-[11px] font-bold tracking-wider uppercase text-[var(--tavus-terminal-black)]">
                  READ MORE
                  <ArrowUpRight className="w-3.5 h-3.5" />
                </div>
              </div>
            </div>
          </a>
        </PageSection>

        {/* All posts */}
        <PageSection bg="white">
          <div className="text-center mb-10">
            <div className="inline-flex items-center gap-2 mb-4">
              <span className="w-2 h-2 bg-[var(--tavus-terminal-black)]" />
              <span className="text-[11px] font-bold tracking-[0.2em] uppercase text-[var(--tavus-hardware-gray-8)]">ALL POSTS</span>
              <span className="w-2 h-2 bg-[var(--tavus-terminal-black)]" />
            </div>
            <h2 className="font-[var(--font-serif-display)] text-4xl sm:text-5xl font-normal tracking-tight text-[var(--tavus-terminal-black)]">
              Read the <span className="serif-italic">blog</span>
            </h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {posts.map((p) => (
              <a
                key={p.slug}
                href={`/blog/${p.slug}`}
                className="block bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[6px_6px_0_0_var(--tavus-terminal-black)] hover:shadow-[8px_8px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[2px_2px_0_0_var(--tavus-terminal-black)] transition-all overflow-hidden"
              >
                <div className={`aspect-[4/3] bg-gradient-to-br ${p.gradient} border-b-[3px] border-[var(--tavus-terminal-black)] relative`}>
                  <div className="absolute inset-0 bg-halftone opacity-30" />
                  <div className="absolute top-3 left-3 bg-white border-[2px] border-[var(--tavus-terminal-black)] px-2 py-0.5 text-[10px] font-extrabold tracking-wider uppercase">
                    {p.category}
                  </div>
                </div>
                <div className="p-5">
                  <h3 className="font-[var(--font-serif-display)] text-lg font-normal leading-tight text-[var(--tavus-terminal-black)] line-clamp-2">
                    {p.title}
                  </h3>
                  <p className="mt-2 text-sm text-[var(--tavus-hardware-gray-8)] leading-relaxed line-clamp-3">
                    {p.desc}
                  </p>
                  <div className="mt-4 flex items-center justify-between text-[10px] font-mono text-[var(--tavus-hardware-gray-8)]">
                    <span>{p.date}</span>
                    <ArrowUpRight className="w-3.5 h-3.5" />
                  </div>
                </div>
              </a>
            ))}
          </div>
        </PageSection>

        {/* Newsletter */}
        <PageSection bg="grain">
          <div className="text-center">
            <h2 className="font-[var(--font-serif-display)] text-4xl sm:text-5xl font-normal tracking-tight text-[var(--tavus-terminal-black)]">
              Subscribe to our <span className="serif-italic">newsletter</span>
            </h2>
            <p className="mt-4 text-base text-[var(--tavus-hardware-gray-8)] max-w-md mx-auto">
              Get the latest from Zemest — engineering deep-dives, customer stories, and research updates — straight to your inbox.
            </p>
            <form className="mt-6 flex max-w-md mx-auto gap-2">
              <input
                type="email"
                placeholder="you@company.com"
                className="flex-1 h-12 px-4 border-[3px] border-[var(--tavus-terminal-black)] bg-white text-sm text-[var(--tavus-terminal-black)] placeholder:text-[var(--tavus-hardware-gray-8)]/50 outline-none shadow-[3px_3px_0_0_var(--tavus-terminal-black)] focus:shadow-[4px_4px_0_0_var(--tavus-terminal-black)] focus:-translate-x-0.5 focus:-translate-y-0.5 transition-all"
              />
              <button
                type="submit"
                className="inline-flex items-center gap-2 px-5 h-12 border-[3px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-bubbletech-4)] text-xs font-extrabold tracking-wider uppercase shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:shadow-[4px_4px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] transition-all"
              >
                SUBSCRIBE
                <ArrowUpRight className="w-3.5 h-3.5" />
              </button>
            </form>
          </div>
        </PageSection>
      </main>
      <Footer />
    </div>
  );
}
