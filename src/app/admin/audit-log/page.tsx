"use client";

import { useCallback, useEffect, useState } from "react";
import { Download, Filter } from "lucide-react";
import { adminApi, apiErrorMessage, formatDateTime, type AdminAuditLogItem } from "@/lib/zemest-api";
import { LoadingState, ErrorState } from "@/components/site/dash";

interface AuditLog {
  id: string;
  admin: string;
  action: string;
  target_type: string;
  target_id: string;
  metadata: Record<string, string> | null;
  ip: string;
  timestamp: string;
}

const actionColors: Record<string, string> = {
  // Real backend actions (GET /api/admin/audit-log)
  "user.block": "var(--tavus-bubbletech-1)",
  "ip.ban": "var(--tavus-bubbletech-1)",
  "user.unblock": "var(--tavus-neon-field-2)",
  "ip.unban": "var(--tavus-neon-field-2)",
  // Legacy display keys
  BLOCKED_USER: "var(--tavus-bubbletech-1)",
  BANNED_IP: "var(--tavus-bubbletech-1)",
  AUTO_BAN: "var(--tavus-bubbletech-1)",
  DELETED_TENANT: "var(--tavus-bubbletech-1)",
  UPDATED_TENANT: "var(--tavus-frost-4)",
  RESET_TENANT_TOKENS: "var(--tavus-atomic-glow-5)",
  VIEWED_USER: "var(--tavus-plastic-2)",
  EXPORTED_AUDIT_LOG: "var(--tavus-floppy-fog-1)",
  GRANTED_SUPERADMIN: "var(--tavus-neon-field-2)",
  RESTARTED_SERVICE: "var(--tavus-atomic-glow-1)",
};

function toRows(logs: AdminAuditLogItem[]): AuditLog[] {
  // The API response does not include the metadata blob, so it renders as "—".
  return (logs ?? []).map((l) => ({
    id: String(l.id),
    admin: l.admin_id || "—",
    action: l.action,
    target_type: l.target_type || "—",
    target_id: l.target_id || "—",
    metadata: null,
    ip: l.ip || "—",
    timestamp: formatDateTime(l.created_at),
  }));
}

export default function AdminAuditLogPage() {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [total, setTotal] = useState(0);
  const [actionFilter, setActionFilter] = useState("ALL");
  const [adminFilter, setAdminFilter] = useState("");
  const [expanded, setExpanded] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await adminApi.auditLog(1, 50);
      setLogs(toRows(res?.logs ?? []));
      setTotal(res?.total ?? 0);
    } catch (err: unknown) {
      setError(apiErrorMessage(err, "Failed to load audit log"));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // Action types present in the REAL log data (plus ALL)
  const actionTypes = ["ALL", ...Array.from(new Set(logs.map((l) => l.action)))];

  const filtered = logs.filter((l) => {
    const matchAction = actionFilter === "ALL" || l.action === actionFilter;
    const matchAdmin = !adminFilter || l.admin.toLowerCase().includes(adminFilter.toLowerCase());
    return matchAction && matchAdmin;
  });

  const handleCSVExport = () => {
    const headers = ["id", "admin", "action", "target_type", "target_id", "metadata", "ip", "timestamp"];
    const rows = filtered.map((l) => [l.id, l.admin, l.action, l.target_type, l.target_id, l.metadata ? JSON.stringify(l.metadata) : "—", l.ip, l.timestamp]);
    const csv = [headers, ...rows].map((r) => r.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `audit-log-${new Date().toISOString().split("T")[0]}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <div className="inline-flex items-center gap-2 mb-3">
            <span className="w-2 h-2 bg-[var(--tavus-terminal-black)]" />
            <span className="text-[11px] font-bold tracking-[0.2em] uppercase text-[var(--tavus-hardware-gray-8)]">ADMIN · AUDIT LOG</span>
          </div>
          <h1 className="font-[var(--font-serif-display)] text-3xl sm:text-4xl font-normal tracking-tight text-[var(--tavus-terminal-black)]">
            Audit <span className="serif-italic">trail</span>
          </h1>
        </div>
        <button
          onClick={handleCSVExport}
          className="inline-flex items-center gap-2 px-4 h-10 border-[3px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-neon-field-2)] text-white text-[11px] font-extrabold tracking-wider uppercase shadow-[2px_2px_0_0_var(--tavus-terminal-black)] hover:shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] transition-all"
        >
          <Download className="w-4 h-4" />
          EXPORT CSV
        </button>
      </div>

      {/* Error state */}
      {error ? <ErrorState message={error} onRetry={() => load()} /> : null}

      {/* Loading state */}
      {loading ? <LoadingState label="Loading audit log" /> : null}

      {!loading && !error ? (
        <>
          {/* Filters */}
          <div className="relative bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[6px_6px_0_0_var(--tavus-terminal-black)] overflow-hidden">
            <div className="absolute inset-0 bg-halftone-light opacity-10 pointer-events-none" />
            <div className="win-title-bar relative">
              <span className="w-2.5 h-2.5 bg-[var(--tavus-bubbletech-4)] border border-[var(--tavus-terminal-black)]" />
              <span className="inline-flex items-center gap-1.5"><Filter className="w-3 h-3" /> FILTERS</span>
            </div>
            <div className="relative p-4 grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-[10px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)] mb-1.5">ADMIN EMAIL</label>
                <input
                  type="text"
                  value={adminFilter}
                  onChange={(e) => setAdminFilter(e.target.value)}
                  placeholder="Filter by admin id..."
                  className="w-full h-10 px-3 border-2 border-[var(--tavus-terminal-black)] bg-white text-sm outline-none"
                />
              </div>
              <div>
                <label className="block text-[10px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)] mb-1.5">ACTION TYPE</label>
                <select value={actionFilter} onChange={(e) => setActionFilter(e.target.value)} className="w-full h-10 px-3 border-2 border-[var(--tavus-terminal-black)] bg-white text-sm font-bold outline-none">
                  {actionTypes.map((a) => (
                    <option key={a} value={a}>{a.replace(/_/g, " ")}</option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          {/* Log table */}
          <div className="relative bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[6px_6px_0_0_var(--tavus-terminal-black)] overflow-hidden">
            <div className="absolute inset-0 bg-halftone-light opacity-10 pointer-events-none" />
            <div className="win-title-bar relative">
              <span className="w-2.5 h-2.5 bg-[var(--tavus-neon-field-2)] border border-[var(--tavus-terminal-black)]" />
              <span>AUDIT LOG ENTRIES</span>
            </div>
            <div className="relative overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-[var(--tavus-terminal-black)] text-white">
                  <tr>
                    <th className="text-left p-3 font-extrabold tracking-wider uppercase text-[10px]">ADMIN</th>
                    <th className="text-left p-3 font-extrabold tracking-wider uppercase text-[10px]">ACTION</th>
                    <th className="text-left p-3 font-extrabold tracking-wider uppercase text-[10px]">TARGET TYPE</th>
                    <th className="text-left p-3 font-extrabold tracking-wider uppercase text-[10px]">TARGET ID</th>
                    <th className="text-left p-3 font-extrabold tracking-wider uppercase text-[10px]">METADATA</th>
                    <th className="text-left p-3 font-extrabold tracking-wider uppercase text-[10px]">IP</th>
                    <th className="text-left p-3 font-extrabold tracking-wider uppercase text-[10px]">TIMESTAMP</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((l) => (
                    <tr
                      key={l.id}
                      onClick={() => setExpanded(expanded === l.id ? null : l.id)}
                      className="border-t border-[var(--tavus-terminal-black)]/10 hover:bg-[var(--tavus-plastic-1)] cursor-pointer"
                    >
                      <td className="p-3 font-bold text-[var(--tavus-terminal-black)] text-[11px]">{l.admin}</td>
                      <td className="p-3">
                        <span className="inline-block px-2 py-0.5 text-[9px] font-bold tracking-wider uppercase border border-[var(--tavus-terminal-black)] text-white" style={{ background: actionColors[l.action] || "var(--tavus-plastic-2)" }}>
                          {l.action.replace(/_/g, " ")}
                        </span>
                      </td>
                      <td className="p-3 text-[10px] font-mono text-[var(--tavus-hardware-gray-8)] uppercase">{l.target_type}</td>
                      <td className="p-3 text-[11px] font-mono text-[var(--tavus-terminal-black)]">{l.target_id}</td>
                      <td className="p-3 text-[10px] text-[var(--tavus-hardware-gray-8)] max-w-[200px] truncate">
                        {l.metadata ? Object.entries(l.metadata).map(([k, v]) => `${k}=${v}`).join(", ") : "—"}
                      </td>
                      <td className="p-3 font-mono text-[10px] text-[var(--tavus-hardware-gray-8)]">{l.ip}</td>
                      <td className="p-3 text-[10px] text-[var(--tavus-hardware-gray-8)] whitespace-nowrap">{l.timestamp}</td>
                    </tr>
                  ))}
                  {filtered.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="p-8 text-center text-sm font-semibold text-[var(--tavus-hardware-gray-8)]">
                        {logs.length === 0 ? `No audit entries yet${total > 0 ? ` (${total} total — first page shows the latest 50)` : ""}.` : "No entries match your filters."}
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
            {expanded && (
              <div className="relative border-t-2 border-[var(--tavus-terminal-black)] bg-[var(--tavus-plastic-1)] p-4">
                <div className="text-[10px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)] mb-2">FULL METADATA JSON</div>
                <pre className="text-xs font-mono text-[var(--tavus-terminal-black)] bg-white border-2 border-[var(--tavus-terminal-black)] p-3 overflow-x-auto">
                  {(() => {
                    const log = logs.find((l) => l.id === expanded);
                    return log?.metadata ? JSON.stringify(log.metadata, null, 2) : "—";
                  })()}
                </pre>
              </div>
            )}
            <div className="relative flex items-center justify-between p-3 border-t-2 border-[var(--tavus-terminal-black)] bg-[var(--tavus-plastic-1)]">
              <div className="text-[10px] font-bold text-[var(--tavus-hardware-gray-8)]">{filtered.length} entries</div>
              <div className="text-[10px] text-[var(--tavus-hardware-gray-8)]">Click any row to expand metadata</div>
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
}
