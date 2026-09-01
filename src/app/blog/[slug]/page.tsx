import { notFound } from "next/navigation";
import { Navbar } from "@/components/site/navbar";
import { Footer } from "@/components/site/footer";
import { PageHero, PageSection } from "@/components/site/page-shell";
import { ArrowUpRight } from "lucide-react";
import { featuredPost, posts, type BlogPost } from "@/lib/blog-posts";

interface Props {
  params: Promise<{ slug: string }>;
}

function findPost(slug: string): BlogPost | undefined {
  if (featuredPost.slug === slug) return featuredPost;
  return posts.find((p) => p.slug === slug);
}

export async function generateStaticParams() {
  return [featuredPost, ...posts].map((p) => ({ slug: p.slug }));
}

export async function generateMetadata({ params }: Props) {
  const { slug } = await params;
  const post = findPost(slug);
  return { title: post ? `${post.title} — Zemest Blog` : "Blog — Zemest" };
}

export default async function BlogPostPage({ params }: Props) {
  const { slug } = await params;
  const post = findPost(slug);
  if (!post) notFound();

  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main>
        <PageHero
          eyebrow={`BLOG · ${post.category}`}
          title={<>{post.title}</>}
          description={post.desc}
        />

        <PageSection bg="white">
          <article className="max-w-2xl mx-auto">
            <div className="flex items-center gap-3 text-[11px] font-mono text-[var(--tavus-hardware-gray-8)] border-b-[3px] border-[var(--tavus-terminal-black)] pb-4 mb-8">
              <span className="font-bold text-[var(--tavus-terminal-black)]">{post.author}</span>
              <span>·</span>
              <span>{post.date}</span>
            </div>

            <div className="space-y-6">
              {post.body.map((paragraph, i) => (
                <p key={i} className="text-base text-[var(--tavus-terminal-black)]/90 leading-relaxed">
                  {paragraph}
                </p>
              ))}
            </div>

            <div className="mt-10 pt-6 border-t-[3px] border-[var(--tavus-terminal-black)]">
              <a
                href="/blog"
                className="text-[11px] font-bold tracking-wider uppercase text-[var(--tavus-terminal-black)] hover:underline"
              >
                ← Back to all posts
              </a>
            </div>
          </article>
        </PageSection>

        {/* Newsletter */}
        <PageSection bg="grain">
          <div className="text-center">
            <h2 className="font-[var(--font-serif-display)] text-3xl sm:text-4xl font-normal tracking-tight text-[var(--tavus-terminal-black)]">
              Get the next one in your <span className="serif-italic">inbox</span>
            </h2>
            <p className="mt-4 text-sm text-[var(--tavus-hardware-gray-8)] max-w-md mx-auto">
              Seller playbooks, new research, and product updates — one thoughtful email a month.
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
