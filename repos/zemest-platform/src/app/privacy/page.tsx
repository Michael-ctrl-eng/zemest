import { Navbar } from "@/components/site/navbar";
import { Footer } from "@/components/site/footer";
import { PageHero, PageSection } from "@/components/site/page-shell";

export const metadata = { title: "Privacy Policy — Zemest" };

export default function PrivacyPage() {
  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main>
        <PageHero eyebrow="LEGAL" title={<>Privacy <span className="serif-italic">policy</span></>} description="How Zemest collects, uses, and protects your data." />
        <PageSection bg="grain">
          <div className="prose prose-sm max-w-2xl mx-auto space-y-4 text-[var(--tavus-terminal-black)]">
            <p>Zemest is committed to protecting your privacy. This policy explains what data we collect, why we collect it, and what you can do about it.</p>
            <h3 className="font-[var(--font-serif-display)] text-2xl font-normal">Data we collect</h3>
            <p>Account information (name, email), connected channel data (WhatsApp / Facebook / Instagram chats you connect), usage data, and conversation logs needed to train your agents.</p>
            <h3 className="font-[var(--font-serif-display)] text-2xl font-normal">How we use it</h3>
            <p>To train your moderation agents, provide the service, improve model quality, and prevent abuse. We never sell your data.</p>
            <h3 className="font-[var(--font-serif-display)] text-2xl font-normal">Your rights</h3>
            <p>You can export or delete your data at any time from your dashboard. Email privacy@zemest.ai for any data requests.</p>
            <p className="text-xs text-[var(--tavus-hardware-gray-8)] mt-8">Last updated: August 2026</p>
          </div>
        </PageSection>
      </main>
      <Footer />
    </div>
  );
}
