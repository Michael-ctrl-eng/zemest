"use client";

import { useState } from "react";
import Link from "next/link";
import { ArrowLeft, ArrowRight, Eye, EyeOff } from "lucide-react";
import { AuthBackdrop } from "@/components/site/auth-backdrop";

export default function RegisterPage() {
  const [showPassword, setShowPassword] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const formData = new FormData(e.target as HTMLFormElement);
    const data = {
      name: formData.get("name") as string,
      email: formData.get("email") as string,
      password: formData.get("password") as string,
      confirmPassword: formData.get("confirmPassword") as string,
    };

    const newErrors: Record<string, string> = {};
    if (!data.name || data.name.length < 2) newErrors.name = "Name must be at least 2 characters";
    if (!data.email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(data.email)) newErrors.email = "Invalid email format";
    if (!data.password || data.password.length < 8) newErrors.password = "Password must be at least 8 characters";
    else if (!/(?=.*[a-zA-Z])(?=.*\d)/.test(data.password)) newErrors.password = "Password must contain a letter and a number";
    if (data.password !== data.confirmPassword) newErrors.confirmPassword = "Passwords do not match";

    setErrors(newErrors);
    if (Object.keys(newErrors).length === 0) {
      window.location.href = "/dashboard";
    }
  };

  return (
    <div className="relative min-h-screen flex flex-col bg-[var(--tavus-terminal-black)] overflow-hidden">
      <AuthBackdrop />

      <div className="absolute inset-0 flex items-center justify-center pointer-events-none select-none" aria-hidden="true">
        <div className="font-bitcount text-white/25 text-center leading-none" style={{ fontSize: "clamp(80px, 22vw, 280px)", letterSpacing: "-0.04em" }}>REGISTER</div>
      </div>

      <header className="relative z-10 p-4 sm:p-6">
        <Link href="/" className="inline-flex items-center gap-2 px-3 h-10 border-[3px] border-white bg-white/10 backdrop-blur text-[11px] font-extrabold tracking-[0.06em] uppercase text-white hover:bg-white/20 transition-colors">
          <ArrowLeft className="w-3.5 h-3.5" /> Back to home
        </Link>
      </header>

      <main className="relative z-10 flex-1 flex items-center justify-center p-4 sm:p-6">
        <div className="relative w-full max-w-md">
          <div className="text-center mb-6">
            <div className="inline-flex items-center gap-2 mb-3">
              <span className="w-2 h-2 bg-[var(--tavus-neon-field-2)]" />
              <span className="text-[11px] font-bold tracking-[0.25em] uppercase text-white/70">CREATE YOUR ACCOUNT</span>
              <span className="w-2 h-2 bg-[var(--tavus-neon-field-2)]" />
            </div>
            <h1 className="font-[var(--font-serif-display)] text-4xl sm:text-5xl font-normal tracking-tight text-white leading-[1.05]">
              Build your <span className="serif-italic text-[var(--tavus-bubbletech-1)]">first agent</span>
            </h1>
          </div>

          <div className="relative bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[8px_8px_0_0_var(--tavus-terminal-black)] overflow-hidden">
            <div className="win-title-bar">
              <span className="w-2.5 h-2.5 bg-[var(--tavus-bubbletech-4)] border border-[var(--tavus-terminal-black)]" />
              <span>ZEMEST · SIGN UP</span>
              <span className="ml-auto flex gap-1"><span className="w-2.5 h-2.5 border border-[var(--tavus-terminal-black)]" /><span className="w-2.5 h-2.5 border border-[var(--tavus-terminal-black)]" /><span className="w-2.5 h-2.5 border border-[var(--tavus-terminal-black)]" /></span>
            </div>
            <form className="p-6 space-y-4" onSubmit={handleSubmit}>
              <div>
                <label className="block text-[10px] font-bold tracking-[0.1em] uppercase text-[var(--tavus-hardware-gray-8)] mb-1.5">FULL NAME</label>
                <input name="name" type="text" placeholder="Your name" className="w-full h-11 px-3 border-[2px] border-[var(--tavus-terminal-black)] bg-white text-[14px] outline-none shadow-[2px_2px_0_0_var(--tavus-terminal-black)] focus:shadow-[3px_3px_0_0_var(--tavus-terminal-black)] transition-shadow" />
                {errors.name && <p className="text-[11px] text-[var(--tavus-bubbletech-4)] mt-1 font-bold">{errors.name}</p>}
              </div>
              <div>
                <label className="block text-[10px] font-bold tracking-[0.1em] uppercase text-[var(--tavus-hardware-gray-8)] mb-1.5">EMAIL</label>
                <input name="email" type="email" placeholder="you@company.com" className="w-full h-11 px-3 border-[2px] border-[var(--tavus-terminal-black)] bg-white text-[14px] outline-none shadow-[2px_2px_0_0_var(--tavus-terminal-black)] focus:shadow-[3px_3px_0_0_var(--tavus-terminal-black)] transition-shadow" />
                {errors.email && <p className="text-[11px] text-[var(--tavus-bubbletech-4)] mt-1 font-bold">{errors.email}</p>}
              </div>
              <div>
                <label className="block text-[10px] font-bold tracking-[0.1em] uppercase text-[var(--tavus-hardware-gray-8)] mb-1.5">PASSWORD</label>
                <div className="relative">
                  <input name="password" type={showPassword ? "text" : "password"} placeholder="Min 8 chars, 1 letter + 1 number" className="w-full h-11 px-3 pr-10 border-[2px] border-[var(--tavus-terminal-black)] bg-white text-[14px] outline-none shadow-[2px_2px_0_0_var(--tavus-terminal-black)] focus:shadow-[3px_3px_0_0_var(--tavus-terminal-black)] transition-shadow" />
                  <button type="button" onClick={() => setShowPassword(!showPassword)} className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--tavus-hardware-gray-8)] hover:text-[var(--tavus-terminal-black)]">{showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}</button>
                </div>
                {errors.password && <p className="text-[11px] text-[var(--tavus-bubbletech-4)] mt-1 font-bold">{errors.password}</p>}
              </div>
              <div>
                <label className="block text-[10px] font-bold tracking-[0.1em] uppercase text-[var(--tavus-hardware-gray-8)] mb-1.5">CONFIRM PASSWORD</label>
                <input name="confirmPassword" type={showPassword ? "text" : "password"} placeholder="Re-enter password" className="w-full h-11 px-3 border-[2px] border-[var(--tavus-terminal-black)] bg-white text-[14px] outline-none shadow-[2px_2px_0_0_var(--tavus-terminal-black)] focus:shadow-[3px_3px_0_0_var(--tavus-terminal-black)] transition-shadow" />
                {errors.confirmPassword && <p className="text-[11px] text-[var(--tavus-bubbletech-4)] mt-1 font-bold">{errors.confirmPassword}</p>}
              </div>
              <button type="submit" className="w-full inline-flex items-center justify-center gap-2 px-5 h-12 border-[3px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-bubbletech-4)] text-xs font-extrabold tracking-[0.08em] uppercase shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:shadow-[4px_4px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] transition-all">
                Create account <ArrowRight className="w-3.5 h-3.5" />
              </button>
              <div className="relative py-2">
                <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-[var(--tavus-terminal-black)]/20" /></div>
                <div className="relative flex justify-center"><span className="bg-white px-2 text-[10px] font-bold tracking-[0.15em] uppercase text-[var(--tavus-hardware-gray-8)]">OR CONTINUE WITH</span></div>
              </div>
              <div className="grid grid-cols-3 gap-2">
                <button type="button" onClick={() => (window.location.href = "/api/auth/facebook")} className="h-10 border-[2px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-bubbletech-4)] text-[10px] font-bold tracking-[0.05em] uppercase hover:bg-[var(--tavus-bubbletech-3)] active:translate-y-0.5 transition-all">Facebook</button>
                <button type="button" className="h-10 border-[2px] border-[var(--tavus-terminal-black)] bg-white text-[10px] font-bold tracking-[0.05em] uppercase hover:bg-[var(--tavus-plastic-2)] active:translate-y-0.5 transition-all">Google</button>
                <button type="button" className="h-10 border-[2px] border-[var(--tavus-terminal-black)] bg-white text-[10px] font-bold tracking-[0.05em] uppercase hover:bg-[var(--tavus-plastic-2)] active:translate-y-0.5 transition-all">SSO</button>
              </div>
            </form>
          </div>
          <div className="mt-6 text-center">
            <p className="text-[12px] text-white/70">Already have an account? <Link href="/login" className="font-bold text-[var(--tavus-bubbletech-1)] underline hover:no-underline">Login</Link></p>
          </div>
        </div>
      </main>
      <footer className="relative z-10 p-4 text-center"><p className="text-[10px] font-bold tracking-[0.15em] uppercase text-white/40">© 2026 ZEMEST | THE COMMERCE MODERATION COMPANY</p></footer>
    </div>
  );
}
