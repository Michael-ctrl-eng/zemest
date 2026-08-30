"use client";

import { useState, useEffect, useCallback, use } from "react";
import { Facebook, Instagram, AlertTriangle, RefreshCw, ArrowRight } from "lucide-react";
import { insightsApi, type InsightsOverview } from "@/lib/zemest-api";
import {
  WinCard,
  DashHeader,
  TavusLink,
  LoadingState,
  ErrorState,
  EmptyState,
} from "@/components/site/dash";

interface GraphMetric {
  name?: string;
  title?: string;
  period?: string;
  values?: { value?: unknown; end_time?: string }[];
  [key: string]: unknown;
}

function asMetrics(raw: unknown): GraphMetric[] {
  return Array.isArray(raw) ? (raw as GraphMetric[]) : [];
}

function metricLabel(m: GraphMetric): string {
  const base = (typeof m.title === "string" && m.title) || (typeof m.name === "string" && m.name) || "metric";
  return base.replace(/_/g, " ").toUpperCase();
}

function metricValue(m: GraphMetric): string {
  const values = Array.isArray(m.values) ? m.values : [];
  const last = values.length > 0 ? values[values.length - 1] : undefined;
  const v = last?.value;
  if (v === undefined || v === null) return "—";
  if (typeof v === "number") return v.toLocaleString("en-EG");
  if (typeof v === "object") return JSON.stringify(v).slice(0, 48);
  return String(v);
}

export default function InsightsPage({ params }: { params: Promise<{ tenantId: string }> }) {
  const { tenantId } = use(params);
  const [data, setData] = useState<InsightsOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await insightsApi.overview(tenantId, 30);
      setData(res);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load insights");
    } finally {
      setLoading(false);
    }
  }, [tenantId]);

  useEffect(() => {
    load();
  }, [load]);

  const fb = data?.facebook;
  const ig = data?.instagram;
  const noData = !fb && !ig;

  return (
    <div className="space-y-6">
      {/* Header */}
      <DashHeader
        eyebrow="Insights"
        title="Page"
        tail="insights"
        action={
          <button
            onClick={load}
            title="Refresh"
            aria-label="Refresh"
            className="inline-flex items-center justify-center w-11 h-11 border-[3px] border-[var(--tavus-terminal-black)] bg-white shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:shadow-[4px_4px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] transition-all"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} strokeWidth={2.5} />
          </button>
        }
      />

      {/* Error state */}
      {error ? <ErrorState message={error} onRetry={load} /> : null}

      {/* Loading state */}
      {loading ? <LoadingState label="Loading insights" /> : null}

      {/* Empty state — no social channel connected */}
      {!loading && !error && noData ? (
        <WinCard title="No insights source" dot="var(--tavus-atomic-glow-1)">
          <EmptyState
            icon={<Facebook className="w-6 h-6" strokeWidth={2} />}
            title="Connect your Facebook page to see insights"
            hint={`Followers, reach and engagement metrics from your connected Facebook and Instagram accounts will appear here. Link a page first, then check back after ${data?.period_days ?? 30} days of activity.`}
            action={
              <TavusLink href={`/dashboard/${tenantId}/settings`}>
                Go to settings <ArrowRight className="w-3.5 h-3.5" strokeWidth={2.5} />
              </TavusLink>
            }
          />
        </WinCard>
      ) : null}

      {/* Data state */}
      {!loading && !error && !noData ? (
        <div className="space-y-5">
          <div className="text-[10px] font-extrabold tracking-[0.18em] uppercase text-[var(--tavus-hardware-gray-8)]">
            Last {data?.period_days ?? 30} days
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            {/* Facebook */}
            {fb ? (
              <WinCard title="Facebook" dot="var(--tavus-bubbletech-4)">
                <div className="relative p-4 space-y-4">
                  {typeof fb.error === "string" ? (
                    <div className="flex items-start gap-2 border-[2.5px] border-[var(--tavus-coral-1)] bg-[var(--tavus-coral-3)]/40 p-3">
                      <AlertTriangle className="w-4 h-4 text-[var(--tavus-terminal-black)] shrink-0 mt-0.5" strokeWidth={2.5} />
                      <div className="text-xs font-bold break-words text-[var(--tavus-terminal-black)]">{fb.error}</div>
                    </div>
                  ) : (
                    <>
                      {fb.page_name ? <div className="font-serif text-xl text-[var(--tavus-terminal-black)]">{fb.page_name}</div> : null}
                      <div className="grid grid-cols-2 gap-3">
                        <StatCard label="FOLLOWERS" value={typeof fb.followers === "number" ? fb.followers.toLocaleString("en-EG") : "—"} />
                        <StatCard label="FANS" value={typeof fb.fans === "number" ? fb.fans.toLocaleString("en-EG") : "—"} />
                      </div>
                      <MetricTable metrics={asMetrics(fb.insights)} emptyLabel="No Facebook insight metrics for this period." />
                    </>
                  )}
                </div>
              </WinCard>
            ) : null}

            {/* Instagram */}
            {ig ? (
              <WinCard title="Instagram" dot="var(--tavus-neon-field-2)">
                <div className="relative p-4 space-y-4">
                  {typeof ig.error === "string" ? (
                    <div className="flex items-start gap-2 border-[2.5px] border-[var(--tavus-coral-1)] bg-[var(--tavus-coral-3)]/40 p-3">
                      <AlertTriangle className="w-4 h-4 text-[var(--tavus-terminal-black)] shrink-0 mt-0.5" strokeWidth={2.5} />
                      <div className="text-xs font-bold break-words text-[var(--tavus-terminal-black)]">{ig.error}</div>
                    </div>
                  ) : (
                    <MetricTable metrics={asMetrics(ig.insights)} emptyLabel="No Instagram insight metrics for this period." />
                  )}
                </div>
              </WinCard>
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="relative bg-[var(--tavus-plastic-1)] border-[2px] border-[var(--tavus-terminal-black)] p-3 overflow-hidden">
      <div className="absolute inset-0 bg-halftone-light opacity-[0.35] pointer-events-none" />
      <div className="relative text-[9px] font-extrabold tracking-[0.18em] uppercase text-[var(--tavus-hardware-gray-8)] mb-1">{label}</div>
      <div className="relative text-xl font-extrabold text-[var(--tavus-terminal-black)] tabular-nums">{value}</div>
    </div>
  );
}

function MetricTable({ metrics, emptyLabel }: { metrics: GraphMetric[]; emptyLabel: string }) {
  if (metrics.length === 0) {
    return <div className="text-xs font-medium text-[var(--tavus-hardware-gray-8)] py-4 text-center">{emptyLabel}</div>;
  }
  return (
    <div className="relative border-[2px] border-[var(--tavus-terminal-black)] overflow-hidden">
      <div className="relative divide-y divide-[var(--tavus-terminal-black)]/10 max-h-96 overflow-y-auto scrollbar-thin">
        {metrics.map((m, i) => (
          <div key={`${m.name ?? "metric"}-${i}`} className="flex items-center justify-between gap-3 px-3 py-2 bg-white">
            <span className="text-[10px] font-bold tracking-[0.12em] uppercase text-[var(--tavus-hardware-gray-8)] truncate">{metricLabel(m)}</span>
            <span className="text-sm font-bold text-[var(--tavus-terminal-black)] whitespace-nowrap tabular-nums">{metricValue(m)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
