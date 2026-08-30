"use client";

import Link from "next/link";
import Image from "next/image";
import { ArrowLeft, ArrowRight } from "lucide-react";

interface PageHeroProps {
  eyebrow: string;
  title: React.ReactNode;
  description?: string;
  backHref?: string;
  backLabel?: string;
  ctas?: Array<{
    label: string;
    href: string;
    variant?: "primary" | "secondary";
  }>;
}

export function PageHero({
  eyebrow,
  title,
  description,
  backHref = "/",
  backLabel = "Back to home",
  ctas = [],
}: PageHeroProps) {
  return (
    <section className="relative bg-tavus-header-bg border-b-[3px] border-[var(--tavus-terminal-black)] pt-20 pb-12 sm:pt-24 sm:pb-16 overflow-hidden">
      {/* Premium bitmap halftone fade overlay */}
      <div className="absolute inset-0 bg-halftone-fade opacity-40 pointer-events-none" />
      {/* Bitmap noise texture */}
      <div className="absolute inset-0 bg-bitmap-noise opacity-30 pointer-events-none" />
      <div className="relative mx-auto max-w-[1280px] px-5 sm:px-8">
        <Link
          href={backHref}
          className="inline-flex items-center gap-2 px-3 h-9 border-[3px] border-[var(--tavus-terminal-black)] bg-white shadow-[2px_2px_0_0_var(--tavus-terminal-black)] text-[11px] font-extrabold tracking-[0.04em] uppercase mb-6 hover:shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] transition-all"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          {backLabel}
        </Link>

        <div className="inline-flex items-center gap-2 mb-5">
          <span className="w-2 h-2 bg-[var(--tavus-terminal-black)]" />
          <span className="text-[11px] font-bold tracking-[0.2em] uppercase text-[var(--tavus-hardware-gray-8)]">
            {eyebrow}
          </span>
          <span className="w-2 h-2 bg-[var(--tavus-terminal-black)]" />
        </div>

        <h1 className="font-[var(--font-serif-display)] text-5xl sm:text-7xl lg:text-[88px] font-normal tracking-tight text-[var(--tavus-terminal-black)] leading-[1.02]">
          {title}
        </h1>

        {description && (
          <p className="mt-6 text-base sm:text-lg text-[var(--tavus-hardware-gray-8)] max-w-2xl leading-relaxed">
            {description}
          </p>
        )}

        {ctas.length > 0 && (
          <div className="mt-9 flex flex-col sm:flex-row items-start gap-3">
            {ctas.map((cta, i) => (
              <Link
                key={cta.label}
                href={cta.href}
                className={`inline-flex items-center gap-2 px-6 h-12 border-[3px] border-[var(--tavus-terminal-black)] text-xs font-extrabold tracking-[0.08em] uppercase shadow-[4px_4px_0_0_var(--tavus-terminal-black)] hover:shadow-[6px_6px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] transition-all ${
                  cta.variant === "secondary" || (i > 0 && cta.variant !== "primary")
                    ? "bg-white"
                    : "bg-[var(--tavus-bubbletech-4)]"
                }`}
              >
                {cta.label}
                <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

interface PageSectionProps {
  children: React.ReactNode;
  bg?: "grain" | "white" | "tan" | "dark" | "periwinkle";
  className?: string;
}

const bgMap: Record<NonNullable<PageSectionProps["bg"]>, string> = {
  grain: "bg-grain",
  white: "bg-white",
  tan: "bg-grain-tan",
  dark: "bg-[var(--tavus-terminal-black)] text-white",
  periwinkle: "bg-periwinkle-cloud",
};

export function PageSection({ children, bg = "grain", className = "" }: PageSectionProps) {
  return (
    <section className={`relative ${bgMap[bg]} border-b-[3px] border-[var(--tavus-terminal-black)] py-16 sm:py-24 ${className} overflow-hidden`}>
      {/* Premium bitmap texture overlay */}
      {bg === "dark" ? (
        <div className="absolute inset-0 bg-halftone-white opacity-30 pointer-events-none" />
      ) : bg === "white" ? (
        <div className="absolute inset-0 bg-halftone-light opacity-20 pointer-events-none" />
      ) : null}
      <div className="relative mx-auto max-w-[1280px] px-5 sm:px-8">
        {children}
      </div>
    </section>
  );
}

interface RetroCardProps {
  label?: string;
  title: string;
  description?: string;
  bg?: string;
  cta?: { label: string; href: string };
  children?: React.ReactNode;
}

export function RetroCard({ label, title, description, bg, cta, children }: RetroCardProps) {
  return (
    <div
      className="relative bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[6px_6px_0_0_var(--tavus-terminal-black)] hover:shadow-[8px_8px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[2px_2px_0_0_var(--tavus-terminal-black)] transition-all overflow-hidden"
      style={bg ? { background: bg } : {}}
    >
      {/* Premium bitmap halftone overlay on the card body */}
      <div className="absolute inset-0 bg-halftone-light opacity-10 pointer-events-none" />
      {label && (
        <div className="win-title-bar relative">
          <span className="w-2.5 h-2.5 bg-[var(--tavus-bubbletech-4)] border border-[var(--tavus-terminal-black)]" />
          <span>{label}</span>
          <span className="ml-auto flex gap-1">
            <span className="w-2.5 h-2.5 border border-[var(--tavus-terminal-black)]" />
            <span className="w-2.5 h-2.5 border border-[var(--tavus-terminal-black)]" />
            <span className="w-2.5 h-2.5 border border-[var(--tavus-terminal-black)]" />
          </span>
        </div>
      )}
      <div className="relative p-6">
        <h3 className="font-[var(--font-serif-display)] text-2xl font-normal leading-tight text-[var(--tavus-terminal-black)]">
          {title}
        </h3>
        {description && (
          <p className="mt-3 text-sm text-[var(--tavus-hardware-gray-8)] leading-relaxed">
            {description}
          </p>
        )}
        {children}
        {cta && (
          <Link
            href={cta.href}
            className="mt-5 inline-flex items-center gap-1 text-[11px] font-bold tracking-wider uppercase text-[var(--tavus-terminal-black)] hover:underline"
          >
            {cta.label}
            <ArrowRight className="w-3 h-3" />
          </Link>
        )}
      </div>
    </div>
  );
}

// Compact navbar-less page wrapper (for pages that just need hero + sections + footer)
export function PageShell({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
