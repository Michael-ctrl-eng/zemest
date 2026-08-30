"use client";

import { useState } from "react";
import { Globe, Coins, Activity, TrendingUp, TrendingDown, Users as UsersIcon, MousePointerClick, Clock, MessageSquare } from "lucide-react";

const geoDistribution = [
  { country: "Egypt", users: 842, percentage: 65.5, code: "EG" },
  { country: "Saudi Arabia", users: 187, percentage: 14.6, code: "SA" },
  { country: "United Arab Emirates", users: 92, percentage: 7.2, code: "AE" },
  { country: "Kuwait", users: 58, percentage: 4.5, code: "KW" },
  { country: "Qatar", users: 41, percentage: 3.2, code: "QA" },
  { country: "Jordan", users: 28, percentage: 2.2, code: "JO" },
  { country: "Turkey", users: 19, percentage: 1.5, code: "TR" },
  { country: "Morocco", users: 11, percentage: 0.9, code: "MA" },
  { country: "Other", users: 6, percentage: 0.4, code: "—" },
];

const tokenUsage = [
  { tenant: "Giza Gadget Store", used: 89000, quota: 200000, color: "var(--tavus-bubbletech-4)" },
  { tenant: "Cairo Sneakers Store", used: 45000, quota: 100000, color: "var(--tavus-neon-field-2)" },
  { tenant: "Delta Books", used: 22000, quota: 50000, color: "var(--tavus-atomic-glow-1)" },
  { tenant: "Alexandria Fashion Hub", used: 12000, quota: 50000, color: "var(--tavus-floppy-fog-3)" },
  { tenant: "Sinai Spices", used: 6700, quota: 20000, color: "var(--tavus-frost-4)" },
  { tenant: "Cairo Cosmetics", used: 8400, quota: 50000, color: "var(--tavus-bubbletech-3)" },
];

const behaviorMetrics = [
  { label: "AVG SESSION DURATION", value: "8m 42s", delta: "+12%", up: true, icon: Clock },
  { label: "AVG MESSAGES PER SESSION", value: "14.2", delta: "+5%", up: true, icon: MessageSquare },
  { label: "AVG ORDERS PER USER", value: "2.4", delta: "+8%", up: true, icon: TrendingUp },
  { label: "BOUNCE RATE", value: "23.8%", delta: "-3%", up: false, icon: TrendingDown },
  { label: "DAILY ACTIVE USERS", value: "412", delta: "+18", up: true, icon: UsersIcon },
  { label: "CLICK-THROUGH RATE", value: "4.8%", delta: "+0.6%", up: true, icon: MousePointerClick },
];

export default function AdminAnalyticsPage() {
  const [tab, setTab] = useState<"geo" | "tokens" | "behavior">("geo");

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <div className="inline-flex items-center gap-2 mb-3">
          <span className="w-2 h-2 bg-[var(--tavus-terminal-black)]" />
          <span className="text-[11px] font-bold tracking-[0.2em] uppercase text-[var(--tavus-hardware-gray-8)]">ADMIN · ANALYTICS</span>
        </div>
        <h1 className="font-[var(--font-serif-display)] text-3xl sm:text-4xl font-normal tracking-tight text-[var(--tavus-terminal-black)]">
          Platform <span className="serif-italic">analytics</span>
        </h1>
      </div>

      {/* Tabs */}
      <div className="flex flex-wrap gap-2">
        {[
          { id: "geo", label: "GEOGRAPHIC", icon: Globe },
          { id: "tokens", label: "TOKEN USAGE", icon: Coins },
          { id: "behavior", label: "USER BEHAVIOR", icon: Activity },
        ].map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id as typeof tab)}
            className={`inline-flex items-center gap-2 px-4 h-9 border-[3px] border-[var(--tavus-terminal-black)] text-[11px] font-extrabold tracking-wider uppercase transition-all ${tab === t.id ? "bg-[var(--tavus-bubbletech-4)] shadow-[2px_2px_0_0_var(--tavus-terminal-black)]" : "bg-white"}`}
          >
            <t.icon className="w-3.5 h-3.5" />
            {t.label}
          </button>
        ))}
      </div>

      {tab === "geo" && (
        <div className="relative bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[6px_6px_0_0_var(--tavus-terminal-black)] overflow-hidden">
          <div className="absolute inset-0 bg-halftone-light opacity-10 pointer-events-none" />
          <div className="win-title-bar relative">
            <span className="w-2.5 h-2.5 bg-[var(--tavus-bubbletech-4)] border border-[var(--tavus-terminal-black)]" />
            <span className="inline-flex items-center gap-1.5"><Globe className="w-3 h-3" /> GEOGRAPHIC DISTRIBUTION</span>
          </div>
          <div className="relative overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-[var(--tavus-terminal-black)] text-white">
                <tr>
                  <th className="text-left p-3 font-extrabold tracking-wider uppercase text-[10px]">COUNTRY</th>
                  <th className="text-center p-3 font-extrabold tracking-wider uppercase text-[10px]">CODE</th>
                  <th className="text-center p-3 font-extrabold tracking-wider uppercase text-[10px]">USERS</th>
                  <th className="text-left p-3 font-extrabold tracking-wider uppercase text-[10px]">SHARE</th>
                  <th className="text-left p-3 font-extrabold tracking-wider uppercase text-[10px]">DISTRIBUTION</th>
                </tr>
              </thead>
              <tbody>
                {geoDistribution.map((g) => (
                  <tr key={g.country} className="border-t border-[var(--tavus-terminal-black)]/10 hover:bg-[var(--tavus-plastic-1)]">
                    <td className="p-3 font-bold text-[var(--tavus-terminal-black)]">
                      <span className="inline-flex items-center gap-1.5"><Globe className="w-3.5 h-3.5" />{g.country}</span>
                    </td>
                    <td className="p-3 text-center">
                      <span className="inline-block px-2 py-0.5 text-[9px] font-bold tracking-wider uppercase border border-[var(--tavus-terminal-black)] bg-[var(--tavus-plastic-2)]">{g.code}</span>
                    </td>
                    <td className="p-3 text-center font-bold text-[var(--tavus-terminal-black)]">{g.users.toLocaleString()}</td>
                    <td className="p-3 font-bold text-[var(--tavus-terminal-black)]">{g.percentage}%</td>
                    <td className="p-3">
                      <div className="h-3 bg-[var(--tavus-plastic-2)] border border-[var(--tavus-terminal-black)] overflow-hidden">
                        <div className="h-full bg-[var(--tavus-bubbletech-4)]" style={{ width: `${g.percentage}%` }} />
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="relative flex items-center justify-between p-3 border-t-2 border-[var(--tavus-terminal-black)] bg-[var(--tavus-plastic-1)]">
            <div className="text-[10px] font-bold text-[var(--tavus-hardware-gray-8)]">{geoDistribution.reduce((a, g) => a + g.users, 0).toLocaleString()} total users</div>
            <div className="text-[10px] text-[var(--tavus-hardware-gray-8)]">{geoDistribution.length} countries</div>
          </div>
        </div>
      )}

      {tab === "tokens" && (
        <div className="relative bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[6px_6px_0_0_var(--tavus-terminal-black)] overflow-hidden">
          <div className="absolute inset-0 bg-halftone-light opacity-10 pointer-events-none" />
          <div className="win-title-bar relative">
            <span className="w-2.5 h-2.5 bg-[var(--tavus-neon-field-2)] border border-[var(--tavus-terminal-black)]" />
            <span className="inline-flex items-center gap-1.5"><Coins className="w-3 h-3" /> TOKEN USAGE BY TENANT</span>
          </div>
          <div className="relative p-5 space-y-4">
            {tokenUsage.map((t) => {
              const pct = Math.min(100, (t.used / t.quota) * 100);
              return (
                <div key={t.tenant}>
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-sm font-bold text-[var(--tavus-terminal-black)]">{t.tenant}</span>
                    <span className="text-[10px] font-bold font-mono text-[var(--tavus-hardware-gray-8)]">{t.used.toLocaleString()} / {t.quota.toLocaleString()} ({pct.toFixed(1)}%)</span>
                  </div>
                  <div className="h-4 bg-[var(--tavus-plastic-2)] border-2 border-[var(--tavus-terminal-black)] overflow-hidden">
                    <div className="h-full" style={{ width: `${pct}%`, background: t.color }} />
                  </div>
                </div>
              );
            })}
            <div className="relative bg-[var(--tavus-plastic-1)] border-2 border-[var(--tavus-terminal-black)] p-3 overflow-hidden">
              <div className="absolute inset-0 bg-halftone-light opacity-10 pointer-events-none" />
              <div className="relative flex items-center justify-between">
                <div>
                  <div className="text-[9px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)]">PLATFORM TOTAL</div>
                  <div className="text-xl font-bold text-[var(--tavus-terminal-black)]">{tokenUsage.reduce((a, t) => a + t.used, 0).toLocaleString()} / {tokenUsage.reduce((a, t) => a + t.quota, 0).toLocaleString()}</div>
                </div>
                <div className="text-right">
                  <div className="text-[9px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)]">UTILIZATION</div>
                  <div className="text-xl font-bold text-[var(--tavus-terminal-black)]">{((tokenUsage.reduce((a, t) => a + t.used, 0) / tokenUsage.reduce((a, t) => a + t.quota, 0)) * 100).toFixed(1)}%</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {tab === "behavior" && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {behaviorMetrics.map((m) => (
            <div key={m.label} className="relative bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[4px_4px_0_0_var(--tavus-terminal-black)] p-4 overflow-hidden">
              <div className="absolute inset-0 bg-halftone-light opacity-10 pointer-events-none" />
              <div className="relative flex items-center justify-between mb-2">
                <m.icon className="w-5 h-5" strokeWidth={2} style={{ color: "var(--tavus-terminal-black)" }} />
                <span className={`text-[10px] font-bold ${m.up ? "text-[var(--tavus-neon-field-4)]" : "text-[var(--tavus-bubbletech-4)]"}`}>
                  {m.up ? <TrendingUp className="w-3 h-3 inline mr-0.5" /> : <TrendingDown className="w-3 h-3 inline mr-0.5" />}
                  {m.delta}
                </span>
              </div>
              <div className="relative text-lg font-bold text-[var(--tavus-terminal-black)]">{m.value}</div>
              <div className="relative text-[9px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)] mt-0.5">{m.label}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
