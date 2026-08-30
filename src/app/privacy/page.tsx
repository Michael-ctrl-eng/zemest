import { Navbar } from "@/components/site/navbar";
import { Footer } from "@/components/site/footer";
import { PageHero, PageSection } from "@/components/site/page-shell";

export const metadata = { title: "Privacy Policy — Zemest" };

const PROMISES = [
  {
    title: "Your data is yours",
    body: "The conversations that run through Zemest belong to you and your customers — not to us. We hold them only to keep your store's chats working, and you can take them back or erase them whenever you want. We never sell, rent, or trade a single message, address, or phone number.",
  },
  {
    title: "What we hold — and why",
    body: "Your name and email for the account. The chats you connect, so your agent can keep answering them. Delivery addresses and order details, so packages reach the right door. That is the complete list — nothing is collected beyond it, and nothing is kept a day longer than the service needs.",
  },
  {
    title: "No ads. No tracking. No resale.",
    body: "Your customers' messages are never scanned for advertising, never fed to ad networks, and never used to build profiles. We run no tracking pixels inside your conversations and share nothing with third parties for marketing — full stop.",
  },
  {
    title: "Locked down by default",
    body: "Every message is encrypted in transit and at rest. Access follows least-privilege rules: only the small team that keeps the service alive can touch production systems, every access is logged, and passwords are hashed with industry-standard algorithms.",
  },
  {
    title: "Leave whenever you want",
    body: "You can export everything or delete your account permanently at any time. Deletion is immediate and real — chats, addresses, and account details are erased, not archived in a hidden corner.",
  },
];

export default function PrivacyPage() {
  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main>
        <PageHero
          eyebrow="LEGAL"
          title={<>Privacy <span className="serif-italic">policy</span></>}
          description="Short, honest, and written for humans. Your privacy comes first — everything else is second."
        />
        <PageSection bg="grain">
          <div className="max-w-2xl mx-auto space-y-10 text-[var(--tavus-terminal-black)]">
            <p className="text-base leading-relaxed">
              Zemest handles messages between stores and the people who buy from them. That is a
              position of trust, and this page is our entire position on it — five promises, no
              fine print, no legal fog.
            </p>
            {PROMISES.map((p) => (
              <div key={p.title} className="border-2 border-[var(--tavus-terminal-black)] bg-white shadow-[4px_4px_0_0_var(--tavus-terminal-black)] p-5">
                <h3 className="font-[var(--font-serif-display)] text-2xl font-normal mb-2 flex items-center gap-2">
                  <span className="w-2.5 h-2.5 bg-[var(--tavus-signal-green)] border-2 border-[var(--tavus-terminal-black)]" />
                  {p.title}
                </h3>
                <p className="text-sm leading-relaxed text-[var(--tavus-hardware-gray-8)]">{p.body}</p>
              </div>
            ))}
            <p className="text-sm leading-relaxed">
              Questions about any of this? A real person answers{" "}
              <a href="mailto:privacy@zemest.ai" className="font-bold underline">privacy@zemest.ai</a> —
              usually within a day.
            </p>
            <p className="text-xs text-[var(--tavus-hardware-gray-8)]">Last updated: August 2026</p>
          </div>
        </PageSection>
      </main>
      <Footer />
    </div>
  );
}
