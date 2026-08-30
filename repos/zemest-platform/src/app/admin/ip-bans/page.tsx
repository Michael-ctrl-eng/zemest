"use client";

import { useState } from "react";
import { Plus, Trash2, ShieldBan, Globe, X } from "lucide-react";

interface IPBan {
  id: string;
  ip: string;
  reason: string;
  banned_by: string;
  banned_at: string;
  hits: number;
}

const mockBans: IPBan[] = [
  { id: "ban1", ip: "197.45.21.8", reason: "Repeated failed logins (15 attempts)", banned_by: "root@zemest.com", banned_at: "Aug 27, 09:42 AM", hits: 142 },
  { id: "ban2", ip: "85.105.42.10", reason: "Suspicious bot activity detected", banned_by: "system", banned_at: "Aug 26, 04:15 PM", hits: 89 },
  { id: "ban3", ip: "156.219.213.4", reason: "Chargeback fraud on multiple orders", banned_by: "ops@zemest.com", banned_at: "Aug 25, 11:30 AM", hits: 64 },
  { id: "ban4", ip: "41.232.10.5", reason: "Spam messages via Instagram DMs", banned_by: "system", banned_at: "Aug 24, 08:22 PM", hits: 31 },
  { id: "ban5", ip: "197.55.10.2", reason: "Manual ban by superadmin", banned_by: "root@zemest.com", banned_at: "Aug 23, 02:50 PM", hits: 12 },
];

export default function AdminIPBansPage() {
  const [bans, setBans] = useState(mockBans);
  const [showAdd, setShowAdd] = useState(false);
  const [newIP, setNewIP] = useState("");
  const [newReason, setNewReason] = useState("");

  const handleAdd = () => {
    if (!newIP.trim()) return;
    const ban: IPBan = {
      id: `ban${bans.length + 1}`,
      ip: newIP.trim(),
      reason: newReason.trim() || "Manual ban by superadmin",
      banned_by: "root@zemest.com",
      banned_at: "Just now",
      hits: 0,
    };
    setBans([ban, ...bans]);
    setNewIP("");
    setNewReason("");
    setShowAdd(false);
  };

  const handleRemove = (id: string) => {
    setBans(bans.filter((b) => b.id !== id));
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <div className="inline-flex items-center gap-2 mb-3">
            <span className="w-2 h-2 bg-[var(--tavus-terminal-black)]" />
            <span className="text-[11px] font-bold tracking-[0.2em] uppercase text-[var(--tavus-hardware-gray-8)]">ADMIN · IP BANS</span>
          </div>
          <h1 className="font-[var(--font-serif-display)] text-3xl sm:text-4xl font-normal tracking-tight text-[var(--tavus-terminal-black)]">
            IP <span className="serif-italic">bans</span>
          </h1>
        </div>
        <button
          onClick={() => setShowAdd(true)}
          className="inline-flex items-center gap-2 px-4 h-10 border-[3px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-bubbletech-4)] text-[11px] font-extrabold tracking-wider uppercase shadow-[2px_2px_0_0_var(--tavus-terminal-black)] hover:shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] transition-all"
        >
          <Plus className="w-4 h-4" />
          NEW BAN
        </button>
      </div>

      {/* Add form (toggle) */}
      {showAdd && (
        <div className="relative bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[6px_6px_0_0_var(--tavus-terminal-black)] overflow-hidden">
          <div className="absolute inset-0 bg-halftone-light opacity-10 pointer-events-none" />
          <div className="win-title-bar relative">
            <span className="w-2.5 h-2.5 bg-[var(--tavus-bubbletech-1)] border border-[var(--tavus-terminal-black)]" />
            <span>ADD IP BAN</span>
            <button onClick={() => setShowAdd(false)} className="ml-auto inline-flex items-center justify-center w-5 h-5 border border-[var(--tavus-terminal-black)] bg-white">
              <X className="w-3 h-3" />
            </button>
          </div>
          <div className="relative p-5 space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div className="sm:col-span-1">
                <label className="block text-[10px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)] mb-1.5">IP ADDRESS *</label>
                <input
                  type="text"
                  value={newIP}
                  onChange={(e) => setNewIP(e.target.value)}
                  placeholder="197.45.21.8"
                  className="w-full h-10 px-3 border-2 border-[var(--tavus-terminal-black)] bg-white text-sm font-mono outline-none"
                />
              </div>
              <div className="sm:col-span-2">
                <label className="block text-[10px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)] mb-1.5">REASON</label>
                <input
                  type="text"
                  value={newReason}
                  onChange={(e) => setNewReason(e.target.value)}
                  placeholder="Manual ban reason..."
                  className="w-full h-10 px-3 border-2 border-[var(--tavus-terminal-black)] bg-white text-sm outline-none"
                />
              </div>
            </div>
            <button
              onClick={handleAdd}
              disabled={!newIP.trim()}
              className="inline-flex items-center gap-2 px-5 h-10 border-[3px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-bubbletech-1)] text-[11px] font-extrabold tracking-wider uppercase shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:shadow-[4px_4px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] transition-all disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:translate-x-0 disabled:hover:translate-y-0"
            >
              <ShieldBan className="w-3.5 h-3.5" />
              BAN IP
            </button>
          </div>
        </div>
      )}

      {/* Bans table */}
      <div className="relative bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[6px_6px_0_0_var(--tavus-terminal-black)] overflow-hidden">
        <div className="absolute inset-0 bg-halftone-light opacity-10 pointer-events-none" />
        <div className="win-title-bar relative">
          <span className="w-2.5 h-2.5 bg-[var(--tavus-bubbletech-1)] border border-[var(--tavus-terminal-black)]" />
          <span>BANNED IP ADDRESSES</span>
        </div>
        <div className="relative overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-[var(--tavus-terminal-black)] text-white">
              <tr>
                <th className="text-left p-3 font-extrabold tracking-wider uppercase text-[10px]">IP ADDRESS</th>
                <th className="text-left p-3 font-extrabold tracking-wider uppercase text-[10px]">REASON</th>
                <th className="text-left p-3 font-extrabold tracking-wider uppercase text-[10px]">BANNED BY</th>
                <th className="text-left p-3 font-extrabold tracking-wider uppercase text-[10px]">BANNED AT</th>
                <th className="text-center p-3 font-extrabold tracking-wider uppercase text-[10px]">HITS</th>
                <th className="text-center p-3 font-extrabold tracking-wider uppercase text-[10px]">ACTIONS</th>
              </tr>
            </thead>
            <tbody>
              {bans.map((b) => (
                <tr key={b.id} className="border-t border-[var(--tavus-terminal-black)]/10 hover:bg-[var(--tavus-plastic-1)]">
                  <td className="p-3">
                    <span className="inline-flex items-center gap-1.5 font-mono text-[var(--tavus-terminal-black)] font-bold">
                      <Globe className="w-3.5 h-3.5" />
                      {b.ip}
                    </span>
                  </td>
                  <td className="p-3 text-[var(--tavus-terminal-black)]">{b.reason}</td>
                  <td className="p-3 text-[11px] text-[var(--tavus-hardware-gray-8)]">{b.banned_by}</td>
                  <td className="p-3 text-[10px] text-[var(--tavus-hardware-gray-8)] whitespace-nowrap">{b.banned_at}</td>
                  <td className="p-3 text-center font-bold text-[var(--tavus-terminal-black)]">{b.hits}</td>
                  <td className="p-3">
                    <div className="flex items-center justify-center">
                      <button
                        onClick={() => handleRemove(b.id)}
                        className="inline-flex items-center justify-center w-7 h-7 border border-[var(--tavus-terminal-black)] bg-[var(--tavus-bubbletech-1)] hover:bg-[var(--tavus-bubbletech-4)]"
                        title="Remove ban"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="relative flex items-center justify-between p-3 border-t-2 border-[var(--tavus-terminal-black)] bg-[var(--tavus-plastic-1)]">
          <div className="text-[10px] font-bold text-[var(--tavus-hardware-gray-8)]">{bans.length} banned IPs</div>
          <div className="text-[10px] text-[var(--tavus-hardware-gray-8)]">{bans.reduce((a, b) => a + b.hits, 0).toLocaleString()} total blocked requests</div>
        </div>
      </div>
    </div>
  );
}
