"use client";

import { useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { ArrowLeft, ArrowRight } from "lucide-react";

type AuthMode = "get-started" | "login";

interface AuthPageProps {
  mode: AuthMode;
}

export function AuthPage({ mode }: AuthPageProps) {
  const isSignup = mode === "get-started";
  const title = isSignup ? "Getting Started" : "Login";
  const eyebrow = isSignup ? "CREATE YOUR ACCOUNT" : "WELCOME BACK";
  const submitLabel = isSignup ? "Create account" : "Sign in";
  const footerText = isSignup
    ? "Already have an account?"
    : "Don't have an account yet?";
  const footerLink = isSignup ? "/login" : "/register";
  const footerCta = isSignup ? "Login" : "Get started";

  return (
    <div className="relative min-h-screen flex flex-col bg-[var(--tavus-terminal-black)] overflow-hidden">
      {/* Background image */}
      <Image
        src="/cta-bg.webp"
        alt=""
        aria-hidden="true"
        fill
        priority
        sizes="100vw"
        className="absolute inset-0 w-full h-full object-cover"
      />
      {/* Dark overlay for legibility */}
      <div className="absolute inset-0 bg-[var(--tavus-terminal-black)]/70" />
      {/* Premium bitmap dot grain texture */}
      <div
        className="absolute inset-0 opacity-20 pointer-events-none mix-blend-overlay"
        style={{
          backgroundImage:
            "radial-gradient(circle at 1px 1px, rgba(255, 255, 255, 0.4) 1px, transparent 0)",
          backgroundSize: "8px 8px",
        }}
      />

      {/* Giant Bitcount title behind the form */}
      <div
        className="absolute inset-0 flex items-center justify-center pointer-events-none select-none"
        aria-hidden="true"
      >
        <div
          className="font-bitcount text-white/25 text-center leading-none"
          style={{
            fontSize: "clamp(80px, 22vw, 280px)",
            letterSpacing: "-0.04em",
          }}
        >
          {title.toUpperCase()}
        </div>
      </div>

      {/* Top bar — back to home */}
      <header className="relative z-10 p-4 sm:p-6">
        <Link
          href="/"
          className="inline-flex items-center gap-2 px-3 h-10 border-[3px] border-white bg-white/10 backdrop-blur text-[11px] font-extrabold tracking-[0.06em] uppercase text-white hover:bg-white/20 transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          Back to home
        </Link>
      </header>

      {/* Form card */}
      <main className="relative z-10 flex-1 flex items-center justify-center p-4 sm:p-6">
        <div className="relative w-full max-w-md">
          {/* Eyebrow */}
          <div className="text-center mb-6">
            <div className="inline-flex items-center gap-2 mb-3">
              <span className="w-2 h-2 bg-[var(--tavus-neon-field-2)]" />
              <span className="text-[11px] font-bold tracking-[0.25em] uppercase text-white/70">
                {eyebrow}
              </span>
              <span className="w-2 h-2 bg-[var(--tavus-neon-field-2)]" />
            </div>
            <h1
              className="font-[var(--font-serif-display)] text-4xl sm:text-5xl font-normal tracking-tight text-white leading-[1.05]"
            >
              {isSignup ? (
                <>
                  Build your <span className="serif-italic text-[var(--tavus-bubbletech-1)]">first agent</span>
                </>
              ) : (
                <>
                  Welcome <span className="serif-italic text-[var(--tavus-bubbletech-1)]">back</span>
                </>
              )}
            </h1>
          </div>

          {/* Form card */}
          <div className="relative bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[8px_8px_0_0_var(--tavus-terminal-black)] overflow-hidden">
            {/* Window title bar */}
            <div className="win-title-bar">
              <span className="w-2.5 h-2.5 bg-[var(--tavus-bubbletech-4)] border border-[var(--tavus-terminal-black)]" />
              <span>{isSignup ? "ZEMEST · SIGN UP" : "ZEMEST · LOGIN"}</span>
              <span className="ml-auto flex gap-1">
                <span className="w-2.5 h-2.5 border border-[var(--tavus-terminal-black)]" />
                <span className="w-2.5 h-2.5 border border-[var(--tavus-terminal-black)]" />
                <span className="w-2.5 h-2.5 border border-[var(--tavus-terminal-black)]" />
              </span>
            </div>

            <form className="p-6 space-y-4" onSubmit={(e) => e.preventDefault()}>
              {isSignup && (
                <Field label="FULL NAME" name="name" type="text" placeholder="Ahmed Zemest" />
              )}
              <Field label="EMAIL" name="email" type="email" placeholder="you@company.com" />
              <Field label="PASSWORD" name="password" type="password" placeholder="••••••••" />

              {isSignup ? (
                <label className="flex items-start gap-2 text-[11px] text-[var(--tavus-hardware-gray-8)] leading-snug cursor-pointer">
                  <input type="checkbox" className="mt-0.5 w-3.5 h-3.5 accent-[var(--tavus-bubbletech-4)]" />
                  <span>
                    I agree to the{" "}
                    <a href="#" className="font-bold underline">Terms of Service</a> and{" "}
                    <a href="#" className="font-bold underline">Privacy Policy</a>.
                  </span>
                </label>
              ) : (
                <div className="flex items-center justify-between text-[11px]">
                  <label className="flex items-center gap-2 text-[var(--tavus-hardware-gray-8)] cursor-pointer">
                    <input type="checkbox" className="w-3.5 h-3.5 accent-[var(--tavus-bubbletech-4)]" />
                    Remember me
                  </label>
                  <a href="/forgot-password" className="font-bold text-[var(--tavus-terminal-black)] hover:underline">
                    Forgot password?
                  </a>
                </div>
              )}

              <button
                type="submit"
                className="w-full inline-flex items-center justify-center gap-2 px-5 h-12 border-[3px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-bubbletech-4)] text-xs font-extrabold tracking-[0.08em] uppercase shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:shadow-[4px_4px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] transition-all"
              >
                {submitLabel}
                <ArrowRight className="w-3.5 h-3.5" />
              </button>

              {/* Divider */}
              <div className="relative py-2">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-[var(--tavus-terminal-black)]/20" />
                </div>
                <div className="relative flex justify-center">
                  <span className="bg-white px-2 text-[10px] font-bold tracking-[0.15em] uppercase text-[var(--tavus-hardware-gray-8)]">
                    OR CONTINUE WITH
                  </span>
                </div>
              </div>

              {/* Social buttons — Facebook first per PDF spec */}
              <div className="grid grid-cols-3 gap-2">
                <button
                  type="button"
                  onClick={() => (window.location.href = "/api/auth/facebook")}
                  className="h-10 border-[2px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-bubbletech-4)] text-[10px] font-bold tracking-[0.05em] uppercase hover:bg-[var(--tavus-bubbletech-3)] active:translate-y-0.5 transition-all"
                >
                  Facebook
                </button>
                {["Google", "SSO"].map((s) => (
                  <button
                    key={s}
                    type="button"
                    className="h-10 border-[2px] border-[var(--tavus-terminal-black)] bg-white text-[10px] font-bold tracking-[0.05em] uppercase hover:bg-[var(--tavus-plastic-2)] active:translate-y-0.5 transition-all"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </form>
          </div>

          {/* Footer */}
          <div className="mt-6 text-center">
            <p className="text-[12px] text-white/70">
              {footerText}{" "}
              <Link
                href={footerLink}
                className="font-bold text-[var(--tavus-bubbletech-1)] underline hover:no-underline"
              >
                {footerCta}
              </Link>
            </p>
          </div>
        </div>
      </main>

      {/* Bottom footer strip */}
      <footer className="relative z-10 p-4 text-center">
        <p className="text-[10px] font-bold tracking-[0.15em] uppercase text-white/40">
          © 2026 ZEMEST | THE COMMERCE MODERATION COMPANY
        </p>
      </footer>
    </div>
  );
}

function Field({
  label,
  name,
  type,
  placeholder,
}: {
  label: string;
  name: string;
  type: string;
  placeholder: string;
}) {
  const [focused, setFocused] = useState(false);
  return (
    <div>
      <label
        htmlFor={name}
        className="block text-[10px] font-bold tracking-[0.1em] uppercase text-[var(--tavus-hardware-gray-8)] mb-1.5"
      >
        {label}
      </label>
      <input
        id={name}
        name={name}
        type={type}
        placeholder={placeholder}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        className={`w-full h-11 px-3 border-[2px] border-[var(--tavus-terminal-black)] bg-white text-[14px] text-[var(--tavus-terminal-black)] placeholder:text-[var(--tavus-hardware-gray-8)]/50 outline-none transition-shadow ${
          focused ? "shadow-[3px_3px_0_0_var(--tavus-terminal-black)]" : "shadow-[2px_2px_0_0_var(--tavus-terminal-black)]"
        }`}
      />
    </div>
  );
}
