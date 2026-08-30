"use client";

import { cn } from "@/lib/utils";

export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "animate-pulse bg-[var(--tavus-plastic-2)] border border-[var(--tavus-terminal-black)]/10",
        className
      )}
    />
  );
}

/** Skeleton for table rows */
export function TableSkeleton({ rows = 5, cols = 5 }: { rows?: number; cols?: number }) {
  return (
    <div className="space-y-2 p-4">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex gap-2">
          {Array.from({ length: cols }).map((_, j) => (
            <Skeleton key={j} className="h-8 flex-1" />
          ))}
        </div>
      ))}
    </div>
  );
}

/** Skeleton for stat cards */
export function StatCardSkeleton() {
  return (
    <div className="bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[4px_4px_0_0_var(--tavus-terminal-black)] p-4">
      <Skeleton className="h-5 w-5 mb-2" />
      <Skeleton className="h-6 w-20 mb-1" />
      <Skeleton className="h-3 w-24" />
    </div>
  );
}

/** Skeleton for card content */
export function CardSkeleton() {
  return (
    <div className="bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[6px_6px_0_0_var(--tavus-terminal-black)] p-6 space-y-3">
      <Skeleton className="h-6 w-3/4" />
      <Skeleton className="h-4 w-full" />
      <Skeleton className="h-4 w-2/3" />
      <Skeleton className="h-10 w-32 mt-4" />
    </div>
  );
}
