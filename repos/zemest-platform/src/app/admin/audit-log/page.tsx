"use client";

import { useState } from "react";
import { Download, Filter } from "lucide-react";

interface AuditLog {
  id: string;
  admin: string;
  action: string;
  target_type: string;
  target_id: string;
  metadata: Record<string, string>;
  ip: string;
  timestamp: string;
}

const mockLogs: AuditLog[] = [
  { id: "log1", admin: "root@zemest.com", action: "BLOCKED_USER", target_type: "user", target_id: "user_8821", metadata: { reason: "fraud", tenant: "tnt_001" }, ip: "197.45.21.8", timestamp: "Aug 27, 2026 09:42:18" },
  { id: "log2", admin: "root@zemest.com", action: "BANNED_IP", target_type: "ip", target_id: "197.45.21.8", metadata: { reason: "manual", scope: "global" }, ip: "197.45.21.8", timestamp: "Aug 27, 2026 09:38:02" },
  { id: "log3", admin: "ops@zemest.com", action: "UPDATED_TENANT", target_type: "tenant", target_id: "tnt_001", metadata: { field: "delivery_charge", old: "40", new: "50" }, ip: "41.232.10.5", timestamp: "Aug 27, 2026 09:18:42" },
  { id: "log4", admin: "root@zemest.com", action: "RESET_TENANT_TOKENS", target_type: "tenant", target_id: "tnt_002", metadata: { quota: "50000", used_before: "45000" }, ip: "197.45.21.8", timestamp: "Aug 27, 2026 08:58:11" },
  { id: "log5", admin: "ops@zemest.com", action: "VIEWED_USER", target_type: "user", target_id: "user_1024", metadata: { section: "profile" }, ip: "41.232.10.5", timestamp: "Aug 27, 2026 08:32:55" },
  { id: "log6", admin: "root@zemest.com", action: "EXPORTED_AUDIT_LOG", target_type: "system", target_id: "csv_export", metadata: { range: "30d", format: "csv" }, ip: "197.45.21.8", timestamp: "Aug 27, 2026 07:50:30" },
  { id: "log7", admin: "ops@zemest.com", action: "GRANTED_SUPERADMIN", target_type: "user", target_id: "user_551", metadata: { prev_role: "user", new_role: "superadmin" }, ip: "41.232.10.5", timestamp: "Aug 27, 2026 04:15:20" },
  { id: "log8", admin: "root@zemest.com", action: "RESTARTED_SERVICE", target_type: "service", target_id: "celery-worker-2", metadata: { duration: "12s", graceful: "true" }, ip: "197.45.21.8", timestamp: "Aug 27, 2026 01:20:00" },
  { id: "log9", admin: "system", action: "AUTO_BAN", target_type: "ip", target_id: "85.105.42.10", metadata: { reason: "brute_force", attempts: "15" }, ip: "0.0.0.0", timestamp: "Aug 26, 2026 22:14:00" },
  { id: "log10", admin: "ops@zemest.com", action: "DELETED_TENANT", target_type: "tenant", target_id: "tnt_007", metadata: { reason: "fraud", page_name: "Pharma X" }, ip: "41.232.10.5", timestamp: "Aug 26, 2026 16:48:33" },
];

const actionTypes = ["ALL", "BLOCKED_USER", "BANNED_IP", "UPDATED_TENANT", "RESET_TENANT_TOKENS", "VIEWED_USER", "EXPORTED_AUDIT_LOG", "GRANTED_SUPERADMIN", "RESTARTED_SERVICE", "AUTO_BAN", "DELETED_TENANT"];

const actionColors: Record<string, string> = {
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

export default function AdminAuditLogPage() {
  const [actionFilter, setActionFilter] = useState("ALL");
  const [adminFilter, setAdminFilter] = useState("");
  const [expanded, setExpanded] = useState<string | null>(null);

  const filtered = mockLogs.filter((l) => {
    const matchAction = actionFilter === "ALL" || l.action === actionFilter;
    const matchAdmin = !adminFilter || l.admin.toLowerCase().includes(adminFilter.toLowerCase());
    return matchAction && matchAdmin;
  });

  const handleCSVExport = () => {
    const headers = ["id", "admin", "action", "target_type", "target_id", "metadata", "ip", "timestamp"];
    const rows = filtered.map((l) => [l.id, l.admin, l.action, l.target_type, l.target_id, JSON.stringify(l.metadata), l.ip, l.timestamp]);
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
              placeholder="Filter by admin email..."
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
                    {Object.entries(l.metadata).map(([k, v]) => `${k}=${v}`).join(", ")}
                  </td>
                  <td className="p-3 font-mono text-[10px] text-[var(--tavus-hardware-gray-8)]">{l.ip}</td>
                  <td className="p-3 text-[10px] text-[var(--tavus-hardware-gray-8)] whitespace-nowrap">{l.timestamp}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {expanded && (
          <div className="relative border-t-2 border-[var(--tavus-terminal-black)] bg-[var(--tavus-plastic-1)] p-4">
            <div className="text-[10px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)] mb-2">FULL METADATA JSON</div>
            <pre className="text-xs font-mono text-[var(--tavus-terminal-black)] bg-white border-2 border-[var(--tavus-terminal-black)] p-3 overflow-x-auto">
              {JSON.stringify(mockLogs.find((l) => l.id === expanded)?.metadata, null, 2)}
            </pre>
          </div>
        )}
        <div className="relative flex items-center justify-between p-3 border-t-2 border-[var(--tavus-terminal-black)] bg-[var(--tavus-plastic-1)]">
          <div className="text-[10px] font-bold text-[var(--tavus-hardware-gray-8)]">{filtered.length} entries</div>
          <div className="text-[10px] text-[var(--tavus-hardware-gray-8)]">Click any row to expand metadata</div>
        </div>
      </div>
    </div>
  );
}
