"use client";

import { useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { ArrowLeft, ArrowRight, Mail } from "lucide-react";

export default function ForgotPasswordPage() {
  const [submitted, setSubmitted] = useState(false);
  const [email, setEmail] = useState("");

  return (
    <div className="relative min-h-screen flex flex-col bg-[var(--tavus-terminal-black)] overflow-hidden">
      <Image src="/cta-bg.webp" alt="" aria-hidden="true" fill priority sizes="100vw" className="absolute inset-0 w-full h-full object-cover" />
      <div className="absolute inset-0 bg-[var(--tavus-terminal-black)]/70" />
      <div className="absolute inset-0 opacity-20 pointer-events-none mix-blend-overlay" style={{ backgroundImage: "radial-gradient(circle at 1px 1px, rgba(255,255,255,0.4) 1px, transparent 0)", backgroundSize: "8px 8px" }} />

      <div className="absolute inset-0 flex items-center justify-center pointer-events-none select-none" aria-hidden="true">
        <div className="font-bitcount text-white/25 text-center leading-none" style={{ fontSize: "clamp(80px, 22vw, 280px)", letterSpacing: "-0.04em" }}>RESET</div>
      </div>

      <header className="relative z-10 p-4 sm:p-6">
        <Link href="/login" className="inline-flex items-center gap-2 px-3 h-10 border-[3px] border-white bg-white/10 backdrop-blur text-[11px] font-extrabold tracking-[0.06em] uppercase text-white hover:bg-white/20 transition-colors">
          <ArrowLeft className="w-3.5 h-3.5" /> Back to login
        </Link>
      </header>

      <main className="relative z-10 flex-1 flex items-center justify-center p-4 sm:p-6">
        <div className="relative w-full max-w-md">
          <div className="text-center mb-6">
            <div className="inline-flex items-center gap-2 mb-3">
              <span className="w-2 h-2 bg-[var(--tavus-neon-field-2)]" />
              <span className="text-[11px] font-bold tracking-[0.25em] uppercase text-white/70">PASSWORD RESET</span>
              <span className="w-2 h-2 bg-[var(--tavus-neon-field-2)]" />
            </div>
            <h1 className="font-[var(--font-serif-display)] text-4xl sm:text-5xl font-normal tracking-tight text-white leading-[1.05]">
              Forgot your <span className="serif-italic text-[var(--tavus-bubbletech-1)]">password?</span>
            </h1>
          </div>

          <div className="relative bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[8px_8px_0_0_var(--tavus-terminal-black)] overflow-hidden">
            <div className="win-title-bar">
              <span className="w-2.5 h-2.5 bg-[var(--tavus-bubbletech-4)] border border-[var(--tavus-terminal-black)]" />
              <span>ZEMEST · RESET PASSWORD</span>
            </div>
            {submitted ? (
              <div className="p-8 text-center">
                <div className="inline-flex items-center justify-center w-12 h-12 bg-[var(--tavus-neon-field-2)] text-white border-[3px] border-[var(--tavus-terminal-black)] mb-4">
                  <Mail className="w-6 h-6" strokeWidth={2} />
                </div>
                <h3 className="font-[var(--font-serif-display)] text-2xl font-normal text-[var(--tavus-terminal-black)]">Check your email</h3>
                <p className="mt-3 text-sm text-[var(--tavus-hardware-gray-8)]">We sent a reset link to <strong>{email}</strong>. Click the link in the email to set a new password.</p>
                <Link href="/login" className="mt-6 inline-flex items-center gap-2 px-5 h-10 border-[3px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-bubbletech-4)] text-[11px] font-extrabold tracking-wider uppercase shadow-[2px_2px_0_0_var(--tavus-terminal-black)] hover:shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] transition-all">
                  Back to login <ArrowRight className="w-3.5 h-3.5" />
                </Link>
              </div>
            ) : (
              <form className="p-6 space-y-4" onSubmit={(e) => { e.preventDefault(); setSubmitted(true); }}>
                <div>
                  <label className="block text-[10px] font-bold tracking-[0.1em] uppercase text-[var(--tavus-hardware-gray-8)] mb-1.5">EMAIL</label>
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@company.com"
                    className="w-full h-11 px-3 border-[2px] border-[var(--tavus-terminal-black)] bg-white text-[14px] outline-none shadow-[2px_2px_0_0_var(--tavus-terminal-black)] focus:shadow-[3px_3px_0_0_var(--tavus-terminal-black)] transition-shadow"
                  />
                </div>
                <p className="text-[11px] text-[var(--tavus-hardware-gray-8)] leading-relaxed">
                  Enter the email address associated with your Zemest account. We&apos;ll send you a link to reset your password.
                </p>
                <button type="submit" className="w-full inline-flex items-center justify-center gap-2 px-5 h-12 border-[3px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-bubbletech-4)] text-xs font-extrabold tracking-[0.08em] uppercase shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:shadow-[4px_4px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] transition-all">
                  Send reset link <ArrowRight className="w-3.5 h-3.5" />
                </button>
              </form>
            )}
          </div>
          <div className="mt-6 text-center">
            <p className="text-[12px] text-white/70">Remembered it? <Link href="/login" className="font-bold text-[var(--tavus-bubbletech-1)] underline hover:no-underline">Login</Link></p>
          </div>
        </div>
      </main>
      <footer className="relative z-10 p-4 text-center"><p className="text-[10px] font-bold tracking-[0.15em] uppercase text-white/40">© 2026 ZEMEST | THE COMMERCE MODERATION COMPANY</p></footer>
    </div>
  );
}
