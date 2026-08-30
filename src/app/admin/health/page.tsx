"use client";

import { useState } from "react";
import { Server, Database, HardDrive, Cpu, Calendar, Brain, Eye, RefreshCw } from "lucide-react";

interface Service {
  name: string;
  description: string;
  status: "operational" | "degraded" | "down";
  response_time_ms: number;
  uptime_30d: number;
  last_check: string;
  icon: React.ElementType;
  color: string;
}

const services: Service[] = [
  { name: "FastAPI", description: "Backend API gateway and core REST endpoints", status: "operational", response_time_ms: 42, uptime_30d: 99.98, last_check: "2 min ago", icon: Server, color: "var(--tavus-bubbletech-4)" },
  { name: "PostgreSQL", description: "Primary relational database", status: "operational", response_time_ms: 8, uptime_30d: 100.0, last_check: "2 min ago", icon: Database, color: "var(--tavus-neon-field-2)" },
  { name: "Redis", description: "Cache, sessions, and Celery broker", status: "operational", response_time_ms: 2, uptime_30d: 99.95, last_check: "1 min ago", icon: HardDrive, color: "var(--tavus-atomic-glow-1)" },
  { name: "Celery Worker", description: "Background job execution pool", status: "degraded", response_time_ms: 1240, uptime_30d: 98.40, last_check: "3 min ago", icon: Cpu, color: "var(--tavus-floppy-fog-3)" },
  { name: "Celery Beat", description: "Periodic task scheduler", status: "operational", response_time_ms: 5, uptime_30d: 99.97, last_check: "1 min ago", icon: Calendar, color: "var(--tavus-frost-4)" },
  { name: "Postiz", description: "Social media publishing pipeline", status: "operational", response_time_ms: 380, uptime_30d: 99.20, last_check: "5 min ago", icon: Server, color: "var(--tavus-bubbletech-3)" },
  { name: "OpenRouter LLM", description: "External LLM routing proxy (GPT, Claude, etc.)", status: "degraded", response_time_ms: 2840, uptime_30d: 97.85, last_check: "4 min ago", icon: Brain, color: "var(--tavus-atomic-glow-3)" },
  { name: "Gemini Vision", description: "Multimodal image understanding for product uploads", status: "down", response_time_ms: 0, uptime_30d: 94.10, last_check: "6 min ago", icon: Eye, color: "var(--tavus-bubbletech-1)" },
];

const statusConfig = {
  operational: { color: "var(--tavus-neon-field-2)", label: "OPERATIONAL", bg: "var(--tavus-neon-field-1)" },
  degraded: { color: "var(--tavus-atomic-glow-1)", label: "DEGRADED", bg: "var(--tavus-atomic-glow-5)" },
  down: { color: "var(--tavus-bubbletech-4)", label: "DOWN", bg: "var(--tavus-bubbletech-1)" },
};

export default function AdminHealthPage() {
  const [refreshing, setRefreshing] = useState(false);

  const handleRefresh = () => {
    setRefreshing(true);
    setTimeout(() => setRefreshing(false), 800);
  };

  const operational = services.filter((s) => s.status === "operational").length;
  const degraded = services.filter((s) => s.status === "degraded").length;
  const down = services.filter((s) => s.status === "down").length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <div className="inline-flex items-center gap-2 mb-3">
            <span className="w-2 h-2 bg-[var(--tavus-terminal-black)]" />
            <span className="text-[11px] font-bold tracking-[0.2em] uppercase text-[var(--tavus-hardware-gray-8)]">ADMIN · SYSTEM HEALTH</span>
          </div>
          <h1 className="font-[var(--font-serif-display)] text-3xl sm:text-4xl font-normal tracking-tight text-[var(--tavus-terminal-black)]">
            Service <span className="serif-italic">status</span>
          </h1>
        </div>
        <button
          onClick={handleRefresh}
          className="inline-flex items-center gap-2 px-4 h-10 border-[3px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-bubbletech-4)] text-[11px] font-extrabold tracking-wider uppercase shadow-[2px_2px_0_0_var(--tavus-terminal-black)] hover:shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] transition-all"
        >
          <RefreshCw className={`w-4 h-4 ${refreshing ? "animate-spin" : ""}`} />
          REFRESH
        </button>
      </div>

      {/* Summary bar */}
      <div className="grid grid-cols-3 gap-3">
        <SummaryCard label="OPERATIONAL" value={operational} total={services.length} color="var(--tavus-neon-field-2)" bg="var(--tavus-neon-field-1)" />
        <SummaryCard label="DEGRADED" value={degraded} total={services.length} color="var(--tavus-atomic-glow-1)" bg="var(--tavus-atomic-glow-5)" />
        <SummaryCard label="DOWN" value={down} total={services.length} color="var(--tavus-bubbletech-4)" bg="var(--tavus-bubbletech-1)" />
      </div>

      {/* Service cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {services.map((s) => {
          const conf = statusConfig[s.status];
          return (
            <div key={s.name} className="relative bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[4px_4px_0_0_var(--tavus-terminal-black)] overflow-hidden">
              <div className="absolute inset-0 bg-halftone-light opacity-10 pointer-events-none" />
              <div className="relative p-4">
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-2.5">
                    <span className="inline-flex items-center justify-center w-9 h-9 border-2 border-[var(--tavus-terminal-black)]" style={{ background: s.color }}>
                      <s.icon className="w-4 h-4" strokeWidth={2} />
                    </span>
                    <div>
                      <div className="text-sm font-extrabold tracking-tight text-[var(--tavus-terminal-black)]">{s.name}</div>
                      <div className="text-[10px] text-[var(--tavus-hardware-gray-8)]">{s.last_check}</div>
                    </div>
                  </div>
                  <div className="relative flex items-center gap-1.5 px-2 py-1 border-2 border-[var(--tavus-terminal-black)]" style={{ background: conf.bg }}>
                    <span className={`w-2.5 h-2.5 border border-[var(--tavus-terminal-black)] text-white ${s.status === "down" ? "animate-pulse" : ""}`} style={{ background: conf.color }} />
                    <span className="text-[9px] font-extrabold tracking-wider uppercase text-[var(--tavus-terminal-black)]">{conf.label}</span>
                  </div>
                </div>
                <div className="text-[11px] text-[var(--tavus-hardware-gray-8)] mb-3 leading-snug">{s.description}</div>
                <div className="grid grid-cols-2 gap-2">
                  <div className="bg-[var(--tavus-plastic-1)] border-2 border-[var(--tavus-terminal-black)] p-2">
                    <div className="text-[9px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)]">RESPONSE</div>
                    <div className="text-sm font-mono font-bold text-[var(--tavus-terminal-black)]">
                      {s.response_time_ms > 0 ? `${s.response_time_ms}ms` : "—"}
                    </div>
                  </div>
                  <div className="bg-[var(--tavus-plastic-1)] border-2 border-[var(--tavus-terminal-black)] p-2">
                    <div className="text-[9px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)]">UPTIME 30D</div>
                    <div className="text-sm font-mono font-bold text-[var(--tavus-terminal-black)]">{s.uptime_30d.toFixed(2)}%</div>
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Recent incidents */}
      <div className="relative bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[6px_6px_0_0_var(--tavus-terminal-black)] overflow-hidden">
        <div className="absolute inset-0 bg-halftone-light opacity-10 pointer-events-none" />
        <div className="win-title-bar relative">
          <span className="w-2.5 h-2.5 bg-[var(--tavus-atomic-glow-1)] border border-[var(--tavus-terminal-black)]" />
          <span>RECENT INCIDENTS</span>
        </div>
        <div className="relative divide-y divide-[var(--tavus-terminal-black)]/10">
          <IncidentRow service="Gemini Vision" severity="down" message="Health check failed — connection timeout after 3000ms" time="6 min ago" />
          <IncidentRow service="OpenRouter LLM" severity="degraded" message="Response latency above SLO threshold (2800ms > 1000ms)" time="4 min ago" />
          <IncidentRow service="Celery Worker" severity="degraded" message="Queue backlog growing — 47 tasks waiting, 3 workers online" time="3 min ago" />
          <IncidentRow service="Redis" severity="operational" message="Recovered after brief connection spike" time="1 hour ago" />
        </div>
      </div>
    </div>
  );
}

function SummaryCard({ label, value, total, color, bg }: { label: string; value: number; total: number; color: string; bg: string }) {
  return (
    <div className="relative bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[4px_4px_0_0_var(--tavus-terminal-black)] p-4 overflow-hidden">
      <div className="absolute inset-0 bg-halftone-light opacity-10 pointer-events-none" />
      <div className="relative flex items-center gap-3">
        <div className="w-10 h-10 border-2 border-[var(--tavus-terminal-black)] flex items-center justify-center" style={{ background: bg }}>
          <span className="w-3 h-3 border border-[var(--tavus-terminal-black)] text-white" style={{ background: color }} />
        </div>
        <div>
          <div className="text-lg font-bold text-[var(--tavus-terminal-black)]">{value} / {total}</div>
          <div className="text-[9px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)]">{label}</div>
        </div>
      </div>
    </div>
  );
}

function IncidentRow({ service, severity, message, time }: { service: string; severity: "operational" | "degraded" | "down"; message: string; time: string }) {
  const conf = statusConfig[severity];
  return (
    <div className="flex items-start gap-3 px-4 py-3 hover:bg-[var(--tavus-plastic-1)]">
      <span className="w-2.5 h-2.5 mt-1.5 border border-[var(--tavus-terminal-black)] text-white shrink-0" style={{ background: conf.color }} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm font-bold text-[var(--tavus-terminal-black)]">{service}</span>
          <span className="inline-block px-1.5 py-0.5 text-[8px] font-bold tracking-wider uppercase border border-[var(--tavus-terminal-black)] text-white" style={{ background: conf.bg }}>{conf.label}</span>
        </div>
        <div className="text-[11px] text-[var(--tavus-hardware-gray-8)] mt-0.5">{message}</div>
      </div>
      <div className="text-[10px] text-[var(--tavus-hardware-gray-8)] shrink-0 whitespace-nowrap">{time}</div>
    </div>
  );
}
