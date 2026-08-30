"use client";

import { Users, Store, ShoppingBag, MonitorPlay, ShieldBan, Activity, Coins, ScrollText } from "lucide-react";

const platformStats = [
  { label: "TOTAL USERS", value: "1,284", icon: Users, color: "var(--tavus-bubbletech-4)" },
  { label: "TOTAL TENANTS", value: "37", icon: Store, color: "var(--tavus-neon-field-2)" },
  { label: "TOTAL ORDERS", value: "18,420", icon: ShoppingBag, color: "var(--tavus-atomic-glow-1)" },
  { label: "ACTIVE SESSIONS", value: "126", icon: MonitorPlay, color: "var(--tavus-floppy-fog-3)" },
  { label: "BLOCKED USERS", value: "23", icon: ShieldBan, color: "var(--tavus-bubbletech-1)" },
  { label: "IP BANS", value: "147", icon: ShieldBan, color: "var(--tavus-atomic-glow-3)" },
  { label: "TOKENS USED", value: "4.8M / 12M", icon: Coins, color: "var(--tavus-frost-4)" },
];

const adminActions = [
  { admin: "root@zemest.com", action: "BLOCKED_USER", target: "user_8821 (hassan@example.com)", time: "2 min ago", ip: "197.45.21.8" },
  { admin: "root@zemest.com", action: "BANNED_IP", target: "197.45.21.8", time: "5 min ago", ip: "197.45.21.8" },
  { admin: "ops@zemest.com", action: "UPDATED_TENANT", target: "tnt_001 (Cairo Sneakers)", time: "12 min ago", ip: "41.232.10.5" },
  { admin: "root@zemest.com", action: "RESET_TENANT_TOKENS", target: "tnt_002 (Alexandria Fashion)", time: "32 min ago", ip: "197.45.21.8" },
  { admin: "ops@zemest.com", action: "VIEWED_USER", target: "user_1024 (sara@example.com)", time: "1 hour ago", ip: "41.232.10.5" },
  { admin: "root@zemest.com", action: "EXPORTED_AUDIT_LOG", target: "2026-08-27.csv", time: "2 hours ago", ip: "197.45.21.8" },
  { admin: "ops@zemest.com", action: "GRANTED_SUPERADMIN", target: "user_551 (ops@zemest.com)", time: "5 hours ago", ip: "41.232.10.5" },
  { admin: "root@zemest.com", action: "RESTARTED_SERVICE", target: "celery-worker-2", time: "8 hours ago", ip: "197.45.21.8" },
];

const actionColors: Record<string, string> = {
  BLOCKED_USER: "var(--tavus-bubbletech-1)",
  BANNED_IP: "var(--tavus-bubbletech-1)",
  UPDATED_TENANT: "var(--tavus-frost-4)",
  RESET_TENANT_TOKENS: "var(--tavus-atomic-glow-5)",
  VIEWED_USER: "var(--tavus-plastic-2)",
  EXPORTED_AUDIT_LOG: "var(--tavus-floppy-fog-1)",
  GRANTED_SUPERADMIN: "var(--tavus-neon-field-2)",
  RESTARTED_SERVICE: "var(--tavus-atomic-glow-1)",
};

export default function AdminDashboardPage() {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <div className="inline-flex items-center gap-2 mb-3">
          <span className="w-2 h-2 bg-[var(--tavus-terminal-black)]" />
          <span className="text-[11px] font-bold tracking-[0.2em] uppercase text-[var(--tavus-hardware-gray-8)]">ADMIN DASHBOARD</span>
        </div>
        <h1 className="font-[var(--font-serif-display)] text-3xl sm:text-4xl font-normal tracking-tight text-[var(--tavus-terminal-black)]">
          Platform <span className="serif-italic">overview</span>
        </h1>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
        {platformStats.map((s) => (
          <div key={s.label} className="relative bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[4px_4px_0_0_var(--tavus-terminal-black)] p-4 overflow-hidden">
            <div className="absolute inset-0 bg-halftone-light opacity-10 pointer-events-none" />
            <div className="relative flex items-center justify-between mb-2">
              <s.icon className="w-5 h-5" strokeWidth={2} style={{ color: "var(--tavus-terminal-black)" }} />
              <span className="w-3 h-3 border border-[var(--tavus-terminal-black)] text-white" style={{ background: s.color }} />
            </div>
            <div className="relative text-lg font-bold text-[var(--tavus-terminal-black)]">{s.value}</div>
            <div className="relative text-[9px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)] mt-0.5">{s.label}</div>
          </div>
        ))}
      </div>

      {/* Recent admin actions feed */}
      <div className="relative bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[6px_6px_0_0_var(--tavus-terminal-black)] overflow-hidden">
        <div className="absolute inset-0 bg-halftone-light opacity-10 pointer-events-none" />
        <div className="win-title-bar relative">
          <span className="w-2.5 h-2.5 bg-[var(--tavus-bubbletech-4)] border border-[var(--tavus-terminal-black)]" />
          <span className="inline-flex items-center gap-1.5"><ScrollText className="w-3 h-3" /> RECENT ADMIN ACTIONS</span>
        </div>
        <div className="relative divide-y divide-[var(--tavus-terminal-black)]/10">
          {adminActions.map((a, i) => (
            <div key={i} className="flex items-center gap-3 px-4 py-3 hover:bg-[var(--tavus-plastic-1)] transition-colors">
              <span className="inline-block w-2 h-2 bg-[var(--tavus-terminal-black)] shrink-0" />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-bold text-[var(--tavus-terminal-black)]">{a.admin}</span>
                  <span className="inline-block px-2 py-0.5 text-[9px] font-bold tracking-wider uppercase border border-[var(--tavus-terminal-black)] text-white" style={{ background: actionColors[a.action] }}>
                    {a.action.replace(/_/g, " ")}
                  </span>
                </div>
                <div className="text-[11px] text-[var(--tavus-hardware-gray-8)] mt-0.5 truncate">
                  Target: <span className="font-mono text-[var(--tavus-terminal-black)]">{a.target}</span>
                </div>
              </div>
              <div className="text-[10px] text-[var(--tavus-hardware-gray-8)] font-mono shrink-0 hidden sm:block">IP {a.ip}</div>
              <div className="text-[10px] text-[var(--tavus-hardware-gray-8)] shrink-0 w-20 text-right">{a.time}</div>
            </div>
          ))}
        </div>
        <div className="relative flex items-center justify-between p-3 border-t-2 border-[var(--tavus-terminal-black)] bg-[var(--tavus-plastic-1)]">
          <div className="text-[10px] font-bold text-[var(--tavus-hardware-gray-8)]">{adminActions.length} actions in last 24h</div>
          <a href="/admin/audit-log" className="text-[10px] font-bold tracking-wider uppercase text-[var(--tavus-terminal-black)] underline">VIEW FULL LOG</a>
        </div>
      </div>
    </div>
  );
}
