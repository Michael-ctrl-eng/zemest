import Link from "next/link";
import { Navbar } from "@/components/site/navbar";
import { Footer } from "@/components/site/footer";
import { PageSection } from "@/components/site/page-shell";
import { ArrowLeft } from "lucide-react";

export default function NotFound() {
  return (
    <div className="min-h-screen bg-background flex flex-col">
      <Navbar />
      <main className="flex-1 flex items-center justify-center bg-tavus-header-bg">
        <div className="text-center px-4">
          <div className="inline-flex items-center gap-2 mb-5">
            <span className="w-2 h-2 bg-[var(--tavus-terminal-black)]" />
            <span className="text-[11px] font-bold tracking-[0.2em] uppercase text-[var(--tavus-hardware-gray-8)]">
              ERROR 404
            </span>
            <span className="w-2 h-2 bg-[var(--tavus-terminal-black)]" />
          </div>
          <h1 className="font-[var(--font-serif-display)] text-7xl sm:text-9xl font-normal tracking-tight text-[var(--tavus-terminal-black)] leading-[1.02]">
            <span className="serif-italic">Not found</span>
          </h1>
          <p className="mt-6 text-base sm:text-lg text-[var(--tavus-hardware-gray-8)] max-w-md mx-auto leading-relaxed">
            The page you&apos;re looking for doesn&apos;t exist — or maybe it never did.
            Either way, let&apos;s get you back on track.
          </p>
          <Link
            href="/"
            className="mt-8 inline-flex items-center gap-2 px-6 h-12 border-[3px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-bubbletech-4)] text-xs font-extrabold tracking-[0.08em] uppercase shadow-[4px_4px_0_0_var(--tavus-terminal-black)] hover:shadow-[6px_6px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] transition-all"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to home
          </Link>
        </div>
      </main>
      <Footer />
    </div>
  );
}
