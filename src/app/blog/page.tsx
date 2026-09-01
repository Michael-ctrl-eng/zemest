import { Navbar } from "@/components/site/navbar";
import { Footer } from "@/components/site/footer";
import { PageHero, PageSection } from "@/components/site/page-shell";
import { ArrowUpRight } from "lucide-react";
import { featuredPost, posts } from "@/lib/blog-posts";

export const metadata = { title: "Zemest Blog: Conversational Commerce & Conversational AI" };

export default function BlogPage() {
  const featured = featuredPost;

  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main>
        <PageHero
          eyebrow="BLOG"
          title={<>Latest insights in <span className="serif-italic">Conversational Commerce</span></>}
          description="Engineering deep-dives, seller playbooks, and research notes from the team building the agents that sell for Egyptian stores."
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
                  {featured.desc}
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
              Seller playbooks, new research, and product updates — one thoughtful email a month, straight to your inbox.
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
