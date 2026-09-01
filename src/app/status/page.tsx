import { Navbar } from "@/components/site/navbar";
import { Footer } from "@/components/site/footer";
import { PageHero, PageSection } from "@/components/site/page-shell";

export const metadata = { title: "Status — Zemest" };

const components = [
  { name: "Agent replies — WhatsApp", status: "OPERATIONAL" },
  { name: "Agent replies — Messenger", status: "OPERATIONAL" },
  { name: "Agent replies — Instagram", status: "OPERATIONAL" },
  { name: "Inventory sync", status: "OPERATIONAL" },
  { name: "Dashboard & login", status: "OPERATIONAL" },
  { name: "Order capture", status: "OPERATIONAL" },
  { name: "Style trainer", status: "OPERATIONAL" },
  { name: "API & webhooks", status: "OPERATIONAL" },
];

const incidents = [
  {
    date: "Aug 28, 2026",
    title: "Elevated reply latency on Instagram (resolved)",
    body: "A Meta webhook backlog caused replies to take 20–40 seconds instead of the usual sub-3-second median for approximately 25 minutes starting 01:12 Cairo time. The backlog drained and latency normalized. No messages were lost; no action needed from stores.",
    status: "RESOLVED",
  },
  {
    date: "Aug 14, 2026",
    title: "Inventory sync delay for two POS providers (resolved)",
    body: "A upstream certificate renewal made stock updates queue for stores syncing via two specific POS integrations. Queued updates applied within 9 minutes of the fix; agents temporarily answered availability questions with 'let me confirm' instead of stale data.",
    status: "RESOLVED",
  },
  {
    date: "Aug 2, 2026",
    title: "Scheduled maintenance — database upgrade",
    body: "Planned 12-minute maintenance window at 04:00 Cairo time to upgrade database infrastructure. Agent replies queued during the window and delivered on completion. No conversation data was affected.",
    status: "COMPLETED",
  },
];

export default function StatusPage() {
  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main>
        <PageHero
          eyebrow="STATUS"
          title={<>All systems <span className="serif-italic">operational</span></>}
          description="Live component health and the incident history we'd want any service to publish — including the boring ones."
        />

        <PageSection bg="grain">
          <div className="flex items-center gap-3 mb-6">
            <span className="w-3 h-3 bg-[var(--tavus-signal-green-2)] animate-pulse" />
            <span className="text-[11px] font-bold tracking-[0.2em] uppercase text-[var(--tavus-terminal-black)]">
              All systems operational
            </span>
          </div>
          <div className="bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[6px_6px_0_0_var(--tavus-terminal-black)] overflow-hidden">
            {components.map((c, i) => (
              <div
                key={c.name}
                className={`flex items-center justify-between px-5 py-3.5 ${
                  i > 0 ? "border-t-2 border-[var(--tavus-terminal-black)]/10" : ""
                }`}
              >
                <span className="text-sm font-semibold text-[var(--tavus-terminal-black)]">{c.name}</span>
                <span className="inline-flex items-center gap-2 text-[10px] font-bold tracking-wider uppercase text-[var(--tavus-terminal-black)]">
                  <span className="w-2 h-2 bg-[var(--tavus-signal-green-2)]" />
                  {c.status}
                </span>
              </div>
            ))}
          </div>
          <p className="mt-4 text-xs text-[var(--tavus-hardware-gray-8)]">
            Components are checked continuously. Incidents appear here before they appear anywhere else.
          </p>
        </PageSection>

        <PageSection bg="white">
          <div className="text-center mb-10">
            <h2 className="font-[var(--font-serif-display)] text-4xl sm:text-5xl font-normal tracking-tight text-[var(--tavus-terminal-black)]">
              Incident <span className="serif-italic">history</span>
            </h2>
          </div>
          <div className="max-w-3xl mx-auto space-y-4">
            {incidents.map((inc) => (
              <div key={inc.title} className="bg-[var(--tavus-plastic-1)] border-[3px] border-[var(--tavus-terminal-black)] shadow-[4px_4px_0_0_var(--tavus-terminal-black)] p-6">
                <div className="flex items-center justify-between gap-4 flex-wrap">
                  <h3 className="font-[var(--font-serif-display)] text-xl font-normal text-[var(--tavus-terminal-black)]">{inc.title}</h3>
                  <span className="text-[10px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)]">{inc.date} · {inc.status}</span>
                </div>
                <p className="mt-3 text-sm text-[var(--tavus-hardware-gray-8)] leading-relaxed">{inc.body}</p>
              </div>
            ))}
          </div>
        </PageSection>
      </main>
      <Footer />
    </div>
  );
}
