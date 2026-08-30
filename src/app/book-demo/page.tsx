"use client";

import { useState } from "react";
import { Navbar } from "@/components/site/navbar";
import { Footer } from "@/components/site/footer";
import { PageHero, PageSection } from "@/components/site/page-shell";
import { ArrowRight, Check } from "lucide-react";

export default function BookDemoPage() {
  const [submitted, setSubmitted] = useState(false);

  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main>
        <PageHero
          eyebrow="BOOK A DEMO"
          title={<>See PALs in <span className="serif-italic">action</span></>}
          description="Get a 30-minute live demo with our solutions team. We'll show you PALs solving your exact workflow, answer your questions, and design a deployment that fits your business."
        />

        <PageSection bg="grain">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            {/* Left: What you get */}
            <div>
              <h3 className="font-[var(--font-serif-display)] text-2xl font-normal text-[var(--tavus-terminal-black)] mb-5">
                What you&apos;ll get
              </h3>
              <ul className="space-y-3">
                {[
                  "30-minute live PAL conversation tailored to your workflow",
                  "Architecture deep-dive with a solutions engineer",
                  "Custom pricing & deployment plan",
                  "Risk-free — no commitment, no pressure",
                  "A follow-up written proposal within 24 hours",
                ].map((item) => (
                  <li key={item} className="flex items-start gap-3 text-sm text-[var(--tavus-terminal-black)]">
                    <span className="flex items-center justify-center w-5 h-5 bg-[var(--tavus-neon-field-2)] text-white border-[2px] border-[var(--tavus-terminal-black)] mt-0.5 shrink-0">
                      <Check className="w-3 h-3" strokeWidth={3} />
                    </span>
                    <span>{item}</span>
                  </li>
                ))}
              </ul>

              <div className="mt-8 bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[4px_4px_0_0_var(--tavus-terminal-black)] p-5">
                <div className="text-[10px] font-bold tracking-[0.15em] uppercase text-[var(--tavus-hardware-gray-8)]">RESPONSE TIME</div>
                <div className="font-[var(--font-serif-display)] text-3xl font-normal text-[var(--tavus-terminal-black)] mt-1">&lt; 24 hours</div>
                <div className="text-xs text-[var(--tavus-hardware-gray-8)] mt-1">We&apos;ll reach out to schedule a time that works for you.</div>
              </div>
            </div>

            {/* Right: Form */}
            <div className="bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[6px_6px_0_0_var(--tavus-terminal-black)] overflow-hidden">
              <div className="win-title-bar">
                <span className="w-2.5 h-2.5 bg-[var(--tavus-bubbletech-4)] border border-[var(--tavus-terminal-black)]" />
                <span>TAVUS · BOOK A DEMO</span>
                <span className="ml-auto flex gap-1">
                  <span className="w-2.5 h-2.5 border border-[var(--tavus-terminal-black)]" />
                  <span className="w-2.5 h-2.5 border border-[var(--tavus-terminal-black)]" />
                  <span className="w-2.5 h-2.5 border border-[var(--tavus-terminal-black)]" />
                </span>
              </div>
              {submitted ? (
                <div className="p-8 text-center">
                  <div className="inline-flex items-center justify-center w-12 h-12 bg-[var(--tavus-neon-field-2)] text-white border-[3px] border-[var(--tavus-terminal-black)] mb-4">
                    <Check className="w-6 h-6" strokeWidth={3} />
                  </div>
                  <h3 className="font-[var(--font-serif-display)] text-3xl font-normal text-[var(--tavus-terminal-black)]">
                    Got it!
                  </h3>
                  <p className="mt-3 text-sm text-[var(--tavus-hardware-gray-8)]">
                    We&apos;ll reach out within 24 hours to schedule your demo.
                  </p>
                </div>
              ) : (
                <form
                  className="p-6 space-y-4"
                  onSubmit={(e) => {
                    e.preventDefault();
                    setSubmitted(true);
                  }}
                >
                  <div className="grid grid-cols-2 gap-3">
                    <FormField label="FIRST NAME" name="first" placeholder="Charlie" />
                    <FormField label="LAST NAME" name="last" placeholder="Zemest" />
                  </div>
                  <FormField label="WORK EMAIL" name="email" type="email" placeholder="you@company.com" />
                  <FormField label="COMPANY" name="company" placeholder="Acme Inc." />
                  <div>
                    <label className="block text-[10px] font-bold tracking-[0.1em] uppercase text-[var(--tavus-hardware-gray-8)] mb-1.5">
                      COMPANY SIZE
                    </label>
                    <select className="w-full h-11 px-3 border-[2px] border-[var(--tavus-terminal-black)] bg-white text-sm text-[var(--tavus-terminal-black)] outline-none shadow-[2px_2px_0_0_var(--tavus-terminal-black)]">
                      <option>1-10 employees</option>
                      <option>11-50 employees</option>
                      <option>51-200 employees</option>
                      <option>201-1000 employees</option>
                      <option>1000+ employees</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-[10px] font-bold tracking-[0.1em] uppercase text-[var(--tavus-hardware-gray-8)] mb-1.5">
                      WHAT ARE YOU TRYING TO BUILD?
                    </label>
                    <textarea
                      rows={3}
                      placeholder="Tell us about your use case..."
                      className="w-full p-3 border-[2px] border-[var(--tavus-terminal-black)] bg-white text-sm text-[var(--tavus-terminal-black)] placeholder:text-[var(--tavus-hardware-gray-8)]/50 outline-none shadow-[2px_2px_0_0_var(--tavus-terminal-black)] resize-none"
                    />
                  </div>
                  <button
                    type="submit"
                    className="w-full inline-flex items-center justify-center gap-2 px-5 h-12 border-[3px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-bubbletech-4)] text-xs font-extrabold tracking-[0.08em] uppercase shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:shadow-[4px_4px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] transition-all"
                  >
                    BOOK MY DEMO
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                </form>
              )}
            </div>
          </div>
        </PageSection>
      </main>
      <Footer />
    </div>
  );
}

function FormField({
  label,
  name,
  type = "text",
  placeholder,
}: {
  label: string;
  name: string;
  type?: string;
  placeholder: string;
}) {
  return (
    <div>
      <label className="block text-[10px] font-bold tracking-[0.1em] uppercase text-[var(--tavus-hardware-gray-8)] mb-1.5">
        {label}
      </label>
      <input
        name={name}
        type={type}
        placeholder={placeholder}
        className="w-full h-11 px-3 border-[2px] border-[var(--tavus-terminal-black)] bg-white text-sm text-[var(--tavus-terminal-black)] placeholder:text-[var(--tavus-hardware-gray-8)]/50 outline-none shadow-[2px_2px_0_0_var(--tavus-terminal-black)] focus:shadow-[3px_3px_0_0_var(--tavus-terminal-black)] focus:-translate-x-0.5 focus:-translate-y-0.5 transition-all"
      />
    </div>
  );
}
