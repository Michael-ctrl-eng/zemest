"use client";

import { Calendar as CalIcon, Sparkles } from "lucide-react";
import { WinCard, DashHeader, EmptyState } from "@/components/site/dash";

export default function SchedulerPage() {
  return (
    <div className="space-y-6">
      {/* Header */}
      <DashHeader eyebrow="Scheduler" title="Post" tail="scheduler" />

      {/* Coming soon */}
      <WinCard title="Coming soon" dot="var(--tavus-atomic-glow-1)">
        <EmptyState
          icon={<CalIcon className="w-6 h-6" strokeWidth={2} />}
          title="Scheduling isn't connected yet"
          hint="The calendar, post composer and best-time heatmap will appear here once the Postiz publishing integration is live. No posts are scheduled or published from this workspace yet."
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
