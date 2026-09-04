"use client";

import { useCallback, useEffect, use, useState } from "react";
import { Flag, Loader2, RefreshCw, Send, CheckCircle2, Clock, Eye } from "lucide-react";
import { reportsApi, type MyReport } from "@/lib/zemest-api";
import { DashHeader, ErrorState, LoadingState, EmptyState } from "@/components/site/dash";

const STATUS_STYLES: Record<string, { label: string; cls: string; icon: typeof Clock }> = {
  open: { label: "Open", cls: "bg-[var(--tavus-coral-1)]/15 text-[var(--tavus-terminal-black)] border-[var(--tavus-terminal-black)]/30", icon: Flag },
  in_review: { label: "In review", cls: "bg-[var(--tavus-atomic-glow-5)]/60 text-[var(--tavus-terminal-black)] border-[var(--tavus-terminal-black)]/30", icon: Eye },
  resolved: { label: "Resolved", cls: "bg-[var(--tavus-bubbletech-4)]/60 text-[var(--tavus-terminal-black)] border-[var(--tavus-terminal-black)]/30", icon: CheckCircle2 },
};

export default function ReportsPage({ params }: { params: Promise<{ tenantId: string }> }) {
  const { tenantId } = use(params);
  const [reports, setReports] = useState<MyReport[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [title, setTitle] = useState("");
  const [subject, setSubject] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setReports(await reportsApi.list());
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load reports");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim() || subject.trim().length < 10) return;
    setSubmitting(true);
    setSubmitError(null);
    setSubmitted(false);
    try {
      await reportsApi.create(title.trim(), subject.trim());
      setTitle("");
      setSubject("");
      setSubmitted(true);
      await load();
    } catch (err: unknown) {
      setSubmitError(err instanceof Error ? err.message : "Could not send the report");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-6">
      <DashHeader
        title="Report"
        description="File a report — it goes straight to the Zemest admin team with your account context attached."
      />

      {/* New report form */}
      <form
        onSubmit={submit}
        className="border-[3px] border-[var(--tavus-terminal-black)] bg-white p-5 shadow-[4px_4px_0_0_var(--tavus-terminal-black)] sm:p-6 space-y-4"
      >
        <div className="flex items-center gap-2">
          <Flag className="w-4 h-4" strokeWidth={2.5} />
          <h2 className="text-sm font-extrabold tracking-[0.08em] uppercase">New report</h2>
        </div>

        <div>
          <label htmlFor="report-title" className="block text-xs font-bold uppercase tracking-wide mb-1.5">
            Title
          </label>
          <input
            id="report-title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            maxLength={200}
            placeholder="Short summary — e.g. WhatsApp replies stopped"
            className="w-full border-[2.5px] border-[var(--tavus-terminal-black)] px-3 py-2.5 text-sm bg-white focus:outline-none focus:shadow-[3px_3px_0_0_var(--tavus-terminal-black)]"
            required
          />
        </div>

        <div>
          <label htmlFor="report-subject" className="block text-xs font-bold uppercase tracking-wide mb-1.5">
            Subject
          </label>
          <textarea
            id="report-subject"
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            maxLength={5000}
            rows={5}
            placeholder="Describe the issue in detail — what happened, when, on which channel…"
            className="w-full border-[2.5px] border-[var(--tavus-terminal-black)] px-3 py-2.5 text-sm bg-white focus:outline-none focus:shadow-[3px_3px_0_0_var(--tavus-terminal-black)] resize-y"
            required
          />
          <p className="mt-1 text-[11px] text-[var(--tavus-hardware-gray-8)]">
            {subject.trim().length < 10
              ? "At least 10 characters so the team can act on it."
              : `${subject.length} / 5000 characters`}
          </p>
        </div>

        {submitError ? (
          <p className="text-sm font-semibold text-red-700 border-[2px] border-red-700/40 bg-red-50 px-3 py-2">
            {submitError}
          </p>
        ) : null}
        {submitted ? (
          <p className="text-sm font-semibold border-[2px] border-[var(--tavus-terminal-black)]/30 bg-[var(--tavus-bubbletech-4)]/60 px-3 py-2">
            Report sent — the admin team has been notified.
          </p>
        ) : null}

        <button
          type="submit"
          disabled={submitting || !title.trim() || subject.trim().length < 10}
          className="inline-flex items-center gap-2 px-5 h-10 border-[2.5px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-coral-1)] text-white text-[11px] font-extrabold tracking-[0.1em] uppercase shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:shadow-[4px_4px_0_0_var(--tavus-terminal-black)] hover:-translate-y-0.5 transition-all disabled:opacity-50 disabled:translate-y-0 disabled:shadow-[3px_3px_0_0_var(--tavus-terminal-black)]"
        >
          {submitting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
          Send report
        </button>
      </form>

      {/* Report history */}
      <div className="border-[3px] border-[var(--tavus-terminal-black)] bg-white shadow-[4px_4px_0_0_var(--tavus-terminal-black)]">
        <div className="flex items-center justify-between border-b-[3px] border-[var(--tavus-terminal-black)] px-5 py-3.5">
          <h2 className="text-sm font-extrabold tracking-[0.08em] uppercase">My reports</h2>
          <button
            onClick={load}
            disabled={loading}
            className="inline-flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wide border-[2px] border-[var(--tavus-terminal-black)]/40 px-2.5 py-1.5 hover:border-[var(--tavus-terminal-black)] hover:bg-[var(--tavus-plastic-2)] disabled:opacity-50 transition-all"
          >
            <RefreshCw className={`w-3 h-3 ${loading ? "animate-spin" : ""}`} strokeWidth={2.5} />
            Refresh
          </button>
        </div>

        <div className="p-5">
          {loading && !reports ? (
            <LoadingState label="Loading reports" />
          ) : error ? (
            <ErrorState message={error} onRetry={load} />
          ) : !reports || reports.length === 0 ? (
            <EmptyState
              title="No reports yet"
              description="When you file a report it appears here with its status until it's resolved."
            />
          ) : (
            <ul className="space-y-4">
              {reports.map((r) => {
                const status = STATUS_STYLES[r.status] ?? STATUS_STYLES.open;
                const StatusIcon = status.icon;
                return (
                  <li key={r.id} className="border-[2.5px] border-[var(--tavus-terminal-black)]/25 p-4 space-y-2">
                    <div className="flex items-start justify-between gap-3 flex-wrap">
                      <div className="min-w-0">
                        <p className="text-sm font-bold truncate">{r.title}</p>
                        <p className="text-[11px] font-mono text-[var(--tavus-hardware-gray-8)]">
                          {r.code}
                          {r.created_at ? ` · ${new Date(r.created_at).toLocaleDateString("en-EG")}` : ""}
                        </p>
                      </div>
                      <span
                        className={`inline-flex items-center gap-1.5 px-2.5 py-1 border-[2px] text-[10px] font-extrabold tracking-[0.08em] uppercase ${status.cls}`}
                      >
                        <StatusIcon className="w-3 h-3" strokeWidth={2.5} />
                        {status.label}
                      </span>
                    </div>
                    <p className="text-[13px] leading-relaxed text-[var(--tavus-terminal-black)]/85 line-clamp-3">
                      {r.subject}
                    </p>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
