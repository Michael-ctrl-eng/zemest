"use client";

import { useCallback, useEffect, useState } from "react";
import { MonitorPlay, X, Globe, Monitor, LogOut, AlertTriangle } from "lucide-react";
import { adminApi, apiErrorMessage, formatDateTime, type AdminActiveSession } from "@/lib/zemest-api";
import { LoadingState, ErrorState } from "@/components/site/dash";

interface Session {
  id: string;
  user_id: string;
  ip: string;
  country: string;
  device: string;
  started_at: string;
  last_activity: string;
  status: "active" | "expired" | "revoked";
}

const statusColors: Record<string, string> = {
  active: "var(--tavus-neon-field-2)",
  expired: "var(--tavus-atomic-glow-5)",
  revoked: "var(--tavus-bubbletech-1)",
};

/**
 * GET /api/admin/analytics/active-sessions only returns sessions active in
 * the last 30 minutes — every row is status "active" and the history tab
 * stays empty (the API has no session-history list endpoint). The response
 * carries no user email or login timestamp, so those columns show "—".
 */
function toRows(sessions: AdminActiveSession[]): Session[] {
  return (sessions ?? []).map((s) => ({
    id: s.id,
    user_id: s.user_id,
    ip: s.ip_address,
    country: s.country || "—",
    device: s.device_type || "—",
    started_at: "—",
    last_activity: formatDateTime(s.last_activity),
    status: "active" as const,
  }));
}

export default function AdminSessionsPage() {
  const [tab, setTab] = useState<"active" | "history">("active");
  const [sessions, setSessions] = useState<Session[]>([]);
  const [detail, setDetail] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setSessions(toRows(await adminApi.activeSessions()));
    } catch (err: unknown) {
      setError(apiErrorMessage(err, "Failed to load sessions"));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleRevoke = (_id: string) => {
    // The backend exposes no POST /admin/sessions/{id}/revoke endpoint yet,
    // so revocation reports unsupported instead of faking a state change.
    setActionError("Session revocation is not supported by the backend yet.");
  };

  const activeSessions = sessions.filter((s) => s.status === "active");
  const historySessions = sessions.filter((s) => s.status !== "active");
  const shown = tab === "active" ? activeSessions : historySessions;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <div className="inline-flex items-center gap-2 mb-3">
          <span className="w-2 h-2 bg-[var(--tavus-terminal-black)]" />
          <span className="text-[11px] font-bold tracking-[0.2em] uppercase text-[var(--tavus-hardware-gray-8)]">ADMIN · SESSIONS</span>
        </div>
        <h1 className="font-[var(--font-serif-display)] text-3xl sm:text-4xl font-normal tracking-tight text-[var(--tavus-terminal-black)]">
          Active <span className="serif-italic">sessions</span>
        </h1>
      </div>

      {/* Error state */}
      {error ? <ErrorState message={error} onRetry={() => load()} /> : null}

      {/* Loading state */}
      {loading ? <LoadingState label="Loading sessions" /> : null}

      {!loading && !error ? (
        <>
          {/* Tabs */}
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => setTab("active")}
              className={`inline-flex items-center gap-2 px-4 h-9 border-[3px] border-[var(--tavus-terminal-black)] text-[11px] font-extrabold tracking-wider uppercase transition-all ${tab === "active" ? "bg-[var(--tavus-neon-field-2)] text-white shadow-[2px_2px_0_0_var(--tavus-terminal-black)]" : "bg-white"}`}
            >
              <MonitorPlay className="w-3.5 h-3.5" />
              ACTIVE ({activeSessions.length})
            </button>
            <button
              onClick={() => setTab("history")}
              className={`inline-flex items-center gap-2 px-4 h-9 border-[3px] border-[var(--tavus-terminal-black)] text-[11px] font-extrabold tracking-wider uppercase transition-all ${tab === "history" ? "bg-[var(--tavus-plastic-2)] shadow-[2px_2px_0_0_var(--tavus-terminal-black)]" : "bg-white"}`}
            >
              HISTORY ({historySessions.length})
            </button>
          </div>

          {actionError ? (
            <div className="flex items-center gap-3 border-[3px] border-[var(--tavus-coral-1)] bg-[var(--tavus-coral-3)]/40 p-3">
              <AlertTriangle className="w-4 h-4 text-[var(--tavus-terminal-black)] shrink-0" strokeWidth={2.5} />
              <div className="text-xs font-bold text-[var(--tavus-terminal-black)]">{actionError}</div>
            </div>
          ) : null}

          {/* Sessions table */}
          <div className="relative bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[6px_6px_0_0_var(--tavus-terminal-black)] overflow-hidden">
            <div className="absolute inset-0 bg-halftone-light opacity-10 pointer-events-none" />
            <div className="win-title-bar relative">
              <span className="w-2.5 h-2.5 bg-[var(--tavus-neon-field-2)] border border-[var(--tavus-terminal-black)]" />
              <span>{tab === "active" ? "ACTIVE SESSIONS" : "SESSION HISTORY"}</span>
            </div>
            <div className="relative overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-[var(--tavus-terminal-black)] text-white">
                  <tr>
                    <th className="text-left p-3 font-extrabold tracking-wider uppercase text-[10px]">USER</th>
                    <th className="text-left p-3 font-extrabold tracking-wider uppercase text-[10px]">IP</th>
                    <th className="text-left p-3 font-extrabold tracking-wider uppercase text-[10px]">COUNTRY</th>
                    <th className="text-left p-3 font-extrabold tracking-wider uppercase text-[10px]">DEVICE</th>
                    <th className="text-left p-3 font-extrabold tracking-wider uppercase text-[10px]">STARTED</th>
                    <th className="text-left p-3 font-extrabold tracking-wider uppercase text-[10px]">LAST ACTIVITY</th>
                    <th className="text-left p-3 font-extrabold tracking-wider uppercase text-[10px]">STATUS</th>
                    <th className="text-center p-3 font-extrabold tracking-wider uppercase text-[10px]">ACTIONS</th>
                  </tr>
                </thead>
                <tbody>
                  {shown.map((s) => (
                    <tr key={s.id} className="border-t border-[var(--tavus-terminal-black)]/10 hover:bg-[var(--tavus-plastic-1)]">
                      <td className="p-3">
                        <button onClick={() => setDetail(s)} className="font-bold text-[var(--tavus-terminal-black)] hover:underline text-left">{s.user_id}</button>
                        <div className="text-[10px] font-mono text-[var(--tavus-hardware-gray-8)]">{s.id}</div>
                      </td>
                      <td className="p-3 font-mono text-[10px] text-[var(--tavus-terminal-black)]">{s.ip}</td>
                      <td className="p-3 text-[10px] text-[var(--tavus-terminal-black)]">
                        <span className="inline-flex items-center gap-1"><Globe className="w-3 h-3" />{s.country}</span>
                      </td>
                      <td className="p-3 text-[10px] text-[var(--tavus-hardware-gray-8)]">
                        <span className="inline-flex items-center gap-1"><Monitor className="w-3 h-3" />{s.device}</span>
                      </td>
                      <td className="p-3 text-[10px] text-[var(--tavus-hardware-gray-8)] whitespace-nowrap">{s.started_at}</td>
                      <td className="p-3 text-[10px] text-[var(--tavus-terminal-black)] font-bold whitespace-nowrap">{s.last_activity}</td>
                      <td className="p-3">
                        <span className="inline-block px-2 py-0.5 text-[9px] font-bold tracking-wider uppercase border border-[var(--tavus-terminal-black)] text-white" style={{ background: statusColors[s.status] }}>
                          {s.status}
                        </span>
                      </td>
                      <td className="p-3">
                        <div className="flex items-center justify-center">
                          {s.status === "active" ? (
                            <button
                              onClick={() => handleRevoke(s.id)}
                              className="inline-flex items-center justify-center w-7 h-7 border border-[var(--tavus-terminal-black)] bg-[var(--tavus-bubbletech-1)] hover:bg-[var(--tavus-bubbletech-4)]"
                              title="Revoke session"
                            >
                              <LogOut className="w-3.5 h-3.5" />
                            </button>
                          ) : (
                            <span className="text-[9px] text-[var(--tavus-hardware-gray-8)]">—</span>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                  {shown.length === 0 ? (
                    <tr>
                      <td colSpan={8} className="p-8 text-center text-sm font-semibold text-[var(--tavus-hardware-gray-8)]">
                        {tab === "active" ? "No active sessions right now." : "No session history available yet."}
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
            <div className="relative flex items-center justify-between p-3 border-t-2 border-[var(--tavus-terminal-black)] bg-[var(--tavus-plastic-1)]">
              <div className="text-[10px] font-bold text-[var(--tavus-hardware-gray-8)]">{shown.length} sessions</div>
              <div className="text-[10px] text-[var(--tavus-hardware-gray-8)]">{activeSessions.length} currently online</div>
            </div>
          </div>
        </>
      ) : null}

      {detail && <SessionDetailModal session={detail} onClose={() => setDetail(null)} />}
    </div>
  );
}

function SessionDetailModal({ session, onClose }: { session: Session; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[var(--tavus-terminal-black)]/50">
      <div className="relative w-full max-w-md bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[8px_8px_0_0_var(--tavus-terminal-black)] overflow-hidden">
        <div className="absolute inset-0 bg-halftone-light opacity-10 pointer-events-none" />
        <div className="win-title-bar relative">
          <span className="w-2.5 h-2.5 bg-[var(--tavus-neon-field-2)] border border-[var(--tavus-terminal-black)]" />
          <span>SESSION DETAIL</span>
          <button onClick={onClose} className="ml-auto inline-flex items-center justify-center w-5 h-5 border border-[var(--tavus-terminal-black)] bg-white">
            <X className="w-3 h-3" />
          </button>
        </div>
        <div className="relative p-5 space-y-3">
          <DetailRow label="SESSION ID" value={session.id} />
          <DetailRow label="USER ID" value={session.user_id} />
          <DetailRow label="IP ADDRESS" value={session.ip} />
          <DetailRow label="COUNTRY" value={session.country} />
          <DetailRow label="DEVICE" value={session.device} />
          <DetailRow label="STARTED AT" value={session.started_at} />
          <DetailRow label="LAST ACTIVITY" value={session.last_activity} />
          <div className="pt-2">
            <span className="inline-block px-2 py-0.5 text-[9px] font-bold tracking-wider uppercase border border-[var(--tavus-terminal-black)] text-white" style={{ background: statusColors[session.status] }}>
              {session.status}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-[var(--tavus-plastic-1)] border-2 border-[var(--tavus-terminal-black)] p-2.5">
      <div className="text-[9px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)]">{label}</div>
      <div className="text-sm font-mono text-[var(--tavus-terminal-black)] mt-0.5 break-all">{value}</div>
    </div>
  );
}
