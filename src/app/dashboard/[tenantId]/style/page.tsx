"use client";

import { Sparkles, Palette } from "lucide-react";
import { WinCard, DashHeader, EmptyState } from "@/components/site/dash";

export default function StylePage() {
  return (
    <div className="space-y-6">
      {/* Header */}
      <DashHeader eyebrow="Style learning" title="Brand" tail="voice" />

      {/* Coming soon */}
      <WinCard title="Coming soon" dot="var(--tavus-atomic-glow-1)">
        <EmptyState
          icon={<Palette className="w-6 h-6" strokeWidth={2} />}
          title="Style learning isn't active yet"
          hint="Chat-history import and the learned style profile will show up here once the feature ships. In the meantime your agent uses the default Zemest voice."
          action={
            <span className="inline-flex items-center gap-2 px-4 py-2 border-[2px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-plastic-1)]">
              <Sparkles className="w-3.5 h-3.5 text-[var(--tavus-terminal-black)]" strokeWidth={2.25} />
              <span className="text-[10px] font-bold tracking-[0.14em] uppercase text-[var(--tavus-hardware-gray-8)]">Check back later</span>
            </span>
          }
        />
      </WinCard>
    </div>
  );
}
