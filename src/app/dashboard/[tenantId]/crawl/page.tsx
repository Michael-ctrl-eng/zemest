"use client";

import { useState, useEffect, useCallback, use } from "react";
import { Globe, Play, FileText, Package, Database, Search, AlertTriangle, RefreshCw, CheckCircle, Loader2 } from "lucide-react";
import { crawlApi, formatDateTime, type CrawlJob } from "@/lib/zemest-api";
import {
  WinCard,
  StatusBadge,
  DashHeader,
  TavusButton,
  TableShell,
  Th,
  Td,
  Row,
  LoadingState,
  ErrorState,
  EmptyState,
  labelClass,
} from "@/components/site/dash";

export default function CrawlPage({ params }: { params: Promise<{ tenantId: string }> }) {
  const { tenantId } = use(params);
  const [jobs, setJobs] = useState<CrawlJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [url, setUrl] = useState("");
  const [depth, setDepth] = useState("2");
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);
  const [startSuccess, setStartSuccess] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await crawlApi.jobs(tenantId);
      setJobs(Array.isArray(res) ? res : []);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load crawl jobs");
    } finally {
      setLoading(false);
    }
  }, [tenantId]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleStartCrawl() {
    if (!url.trim()) {
      setStartError("A target URL is required.");
      return;
    }
    setStarting(true);
    setStartError(null);
    setStartSuccess(null);
    try {
      await crawlApi.start(tenantId, url.trim(), Number(depth));
      setStartSuccess(`Crawl job queued for ${url.trim()} (depth ${depth}).`);
      setUrl("");
      await load();
    } catch (err: unknown) {
      setStartError(err instanceof Error ? err.message : "Failed to start crawl");
    } finally {
      setStarting(false);
    }
  }

  const filtered = jobs.filter((j) => !search || j.url.toLowerCase().includes(search.toLowerCase()));
  const totalPagesFound = jobs.reduce((acc, j) => acc + (j.pages_found ?? 0), 0);
  const totalProducts = jobs.reduce((acc, j) => acc + (j.products_extracted ?? 0), 0);
  const runningCount = jobs.filter((j) => j.status === "running" || j.status === "pending").length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <DashHeader
        eyebrow="Crawl & knowledge"
        title="Knowledge"
        tail="engine"
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

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Start crawl form */}
        <WinCard title="Start crawl" dot="var(--tavus-bubbletech-4)" className="lg:col-span-2">
          <div className="relative p-5 space-y-4">
            <div>
              <label htmlFor="crawl-url" className={labelClass}>
                Target URL *
              </label>
              <div className="relative">
                <Globe className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--tavus-hardware-gray-8)]" />
                <input
                  id="crawl-url"
                  type="url"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="https://mystore.com"
                  className="w-full h-11 pl-10 pr-3 bg-white border-[2.5px] border-[var(--tavus-terminal-black)] text-sm font-semibold text-[var(--tavus-terminal-black)] placeholder:text-[var(--tavus-hardware-gray-8)]/60 placeholder:font-medium focus:outline-none focus:shadow-[3px_3px_0_0_var(--tavus-terminal-black)] transition-shadow"
                />
              </div>
            </div>
            <div>
              <label htmlFor="crawl-depth" className={labelClass}>
                Crawl depth
              </label>
              <select
                id="crawl-depth"
                value={depth}
                onChange={(e) => setDepth(e.target.value)}
                className="w-full h-11 px-3 bg-white border-[2.5px] border-[var(--tavus-terminal-black)] text-sm font-semibold text-[var(--tavus-terminal-black)] cursor-pointer focus:outline-none focus:shadow-[3px_3px_0_0_var(--tavus-terminal-black)] transition-shadow"
              >
                <option value="1">1 — Top-level pages only</option>
                <option value="2">2 — Two levels deep (recommended)</option>
                <option value="3">3 — Three levels deep (slow)</option>
                <option value="5">5 — Full site crawl (very slow)</option>
              </select>
            </div>

            {startError ? (
              <div className="flex items-start gap-3 border-[3px] border-[var(--tavus-coral-1)] bg-[var(--tavus-coral-3)]/40 p-3">
                <AlertTriangle className="w-4 h-4 text-[var(--tavus-terminal-black)] shrink-0 mt-0.5" strokeWidth={2.5} />
                <div>
                  <div className="text-[10px] font-extrabold tracking-[0.14em] uppercase text-[var(--tavus-terminal-black)] mb-0.5">Crawl rejected</div>
                  <div className="text-xs font-bold break-words text-[var(--tavus-terminal-black)]">{startError}</div>
                  <div className="text-[10px] font-medium text-[var(--tavus-terminal-black)]/70 mt-1">
                    Only public websites are allowed — local files (file://) and private network addresses are blocked for security.
                  </div>
                </div>
              </div>
            ) : null}
            {startSuccess ? (
              <div className="flex items-center gap-3 border-[3px] border-[var(--tavus-signal-green-2)] bg-[var(--tavus-signal-green)]/15 p-3">
                <CheckCircle className="w-4 h-4 text-[var(--tavus-terminal-black)] shrink-0" strokeWidth={2.5} />
                <div className="text-xs font-bold text-[var(--tavus-terminal-black)]">{startSuccess}</div>
              </div>
            ) : null}

            <TavusButton onClick={handleStartCrawl} disabled={starting} className="w-full h-11">
              {starting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" strokeWidth={2.5} />}
              {starting ? "Starting…" : "Start crawl job"}
            </TavusButton>
          </div>
        </WinCard>

        {/* Knowledge base info (computed from live jobs) */}
        <WinCard title="Knowledge base" dot="var(--tavus-neon-field-2)">
          <div className="relative p-5 space-y-3">
            <div className="flex items-center gap-2 mb-2">
              <Database className="w-5 h-5 text-[var(--tavus-terminal-black)]" strokeWidth={2} />
              <div className="text-[10px] font-extrabold tracking-[0.18em] uppercase text-[var(--tavus-hardware-gray-8)]">Crawled so far</div>
            </div>
            <KBStat icon={FileText} label="PAGES FOUND" value={totalPagesFound.toLocaleString()} color="var(--tavus-bubbletech-4)" />
            <KBStat icon={Package} label="PRODUCTS EXTRACTED" value={totalProducts.toLocaleString()} color="var(--tavus-neon-field-2)" />
            <KBStat icon={Database} label="CRAWL JOBS" value={String(jobs.length)} color="var(--tavus-atomic-glow-1)" />
          </div>
        </WinCard>
      </div>

      {/* Error state */}
      {error ? <ErrorState message={error} onRetry={load} /> : null}

      {/* Loading state */}
      {loading ? <LoadingState label="Loading crawl jobs" /> : null}

      {/* Empty state */}
      {!loading && !error && jobs.length === 0 ? (
        <WinCard title="No crawl jobs yet" dot="var(--tavus-atomic-glow-1)">
          <EmptyState
            icon={<Globe className="w-6 h-6" strokeWidth={2} />}
            title="Build your knowledge base"
            hint="Point the crawler at your public store URL and it will index pages and extract products so your AI agent can answer questions about them."
          />
        </WinCard>
      ) : null}

      {/* Jobs table */}
      {!loading && !error && jobs.length > 0 ? (
        <WinCard
          title="Crawl jobs"
          dot="var(--tavus-bubbletech-4)"
          action={
            <span className="relative block">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[var(--tavus-hardware-gray-8)]" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Filter by URL..."
                className="w-44 h-8 pl-8 pr-2 bg-white border-[2px] border-[var(--tavus-terminal-black)] text-xs font-semibold text-[var(--tavus-terminal-black)] placeholder:text-[var(--tavus-hardware-gray-8)]/60 outline-none focus:shadow-[2px_2px_0_0_var(--tavus-terminal-black)] transition-shadow"
              />
            </span>
          }
        >
          <TableShell>
            <thead>
              <tr>
                <Th>URL</Th>
                <Th>Status</Th>
                <Th className="text-center">Pages</Th>
                <Th className="text-center">Products</Th>
                <Th>Created</Th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((j) => (
                <JobRow key={j.id} job={j} />
              ))}
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={5} className="p-8 text-center text-sm font-semibold text-[var(--tavus-hardware-gray-8)]">
                    No jobs match your filter.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </TableShell>
          <div className="relative flex items-center justify-between px-4 py-3 border-t-[2px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-plastic-1)]">
            <div className="text-[10px] font-bold tracking-[0.14em] uppercase text-[var(--tavus-hardware-gray-8)]">{filtered.length} jobs</div>
            <div className="text-[10px] font-bold text-[var(--tavus-hardware-gray-8)]">{runningCount} running or queued</div>
          </div>
        </WinCard>
      ) : null}
    </div>
  );
}

function JobRow({ job }: { job: CrawlJob }) {
  return (
    <>
      <Row className="align-top">
        <Td className="font-mono break-all max-w-[320px]">{job.url}</Td>
        <Td>
          <div className="inline-flex items-center gap-1.5">
            {job.status === "running" ? <Loader2 className="w-3 h-3 animate-spin text-[var(--tavus-terminal-black)]" strokeWidth={2.5} /> : null}
            <StatusBadge status={job.status} />
          </div>
        </Td>
        <Td className="text-center font-bold tabular-nums">{job.pages_found}</Td>
        <Td className="text-center font-bold tabular-nums">{job.products_extracted}</Td>
        <Td className="text-[10px] font-medium text-[var(--tavus-hardware-gray-8)] whitespace-nowrap">{formatDateTime(job.created_at)}</Td>
      </Row>
      {job.error_message ? (
        <Row className="bg-[var(--tavus-coral-3)]/20">
          <td colSpan={5} className="px-4 py-2 border-t border-[var(--tavus-terminal-black)]/10">
            <div className="flex items-start gap-2">
              <AlertTriangle className="w-3.5 h-3.5 text-[var(--tavus-coral-1)] shrink-0 mt-0.5" strokeWidth={2.5} />
              <div className="text-[11px] font-bold break-words text-[var(--tavus-terminal-black)]">{job.error_message}</div>
            </div>
          </td>
        </Row>
      ) : null}
    </>
  );
}

function KBStat({ icon: Icon, label, value, color }: { icon: React.ElementType; label: string; value: string; color: string }) {
  return (
    <div className="relative bg-[var(--tavus-plastic-1)] border-[2px] border-[var(--tavus-terminal-black)] p-2.5 overflow-hidden">
      <div className="absolute inset-0 bg-halftone-light opacity-[0.35] pointer-events-none" />
      <div className="relative flex items-center gap-2.5">
        <span
          className="inline-flex items-center justify-center w-7 h-7 border-[2px] border-[var(--tavus-terminal-black)] text-[var(--tavus-terminal-black)]"
          style={{ background: color }}
        >
          <Icon className="w-3.5 h-3.5" strokeWidth={2} />
        </span>
        <div>
          <div className="text-[9px] font-bold tracking-[0.14em] uppercase text-[var(--tavus-hardware-gray-8)]">{label}</div>
          <div className="text-sm font-bold text-[var(--tavus-terminal-black)] tabular-nums">{value}</div>
        </div>
      </div>
    </div>
  );
}
