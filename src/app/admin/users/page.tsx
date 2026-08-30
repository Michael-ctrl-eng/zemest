"use client";

import { useState } from "react";
import { Search, ShieldCheck, ShieldBan, Eye, Globe, Monitor } from "lucide-react";

interface AdminUser {
  id: string;
  name: string;
  email: string;
  fb_id: string;
  is_superadmin: boolean;
  is_blocked: boolean;
  tenant_count: number;
  last_login: string;
  last_ip: string;
  last_country: string;
  last_device: string;
}

const mockUsers: AdminUser[] = [
  { id: "u1", name: "Ahmed Hassan", email: "ahmed@example.com", fb_id: "1029384756", is_superadmin: true, is_blocked: false, tenant_count: 3, last_login: "5 min ago", last_ip: "197.45.21.8", last_country: "Egypt", last_device: "MacBook · Chrome" },
  { id: "u2", name: "Sara Mohamed", email: "sara@example.com", fb_id: "1029384777", is_superadmin: false, is_blocked: false, tenant_count: 1, last_login: "1 hour ago", last_ip: "41.232.10.5", last_country: "Egypt", last_device: "iPhone · Safari" },
  { id: "u3", name: "Omar Khaled", email: "omar@example.com", fb_id: "1029384810", is_superadmin: false, is_blocked: true, tenant_count: 2, last_login: "2 days ago", last_ip: "156.219.213.4", last_country: "Saudi Arabia", last_device: "Windows · Edge" },
  { id: "u4", name: "Fatma Ali", email: "fatma@example.com", fb_id: "1029384912", is_superadmin: false, is_blocked: false, tenant_count: 1, last_login: "4 hours ago", last_ip: "197.45.21.8", last_country: "Egypt", last_device: "Android · Chrome" },
  { id: "u5", name: "Mahmoud Ibrahim", email: "mahmoud@example.com", fb_id: "1029385023", is_superadmin: false, is_blocked: false, tenant_count: 4, last_login: "1 day ago", last_ip: "197.55.10.2", last_country: "Egypt", last_device: "iPad · Safari" },
  { id: "u6", name: "Nour El-Din", email: "nour@example.com", fb_id: "1029385147", is_superadmin: false, is_blocked: true, tenant_count: 0, last_login: "1 week ago", last_ip: "85.105.42.10", last_country: "Turkey", last_device: "Unknown · Other" },
  { id: "u7", name: "Yasmin Adel", email: "yasmin@example.com", fb_id: "1029385268", is_superadmin: false, is_blocked: false, tenant_count: 2, last_login: "3 hours ago", last_ip: "156.219.213.4", last_country: "Saudi Arabia", last_device: "MacBook · Chrome" },
  { id: "u8", name: "Karim Tarek", email: "karim@example.com", fb_id: "1029385390", is_superadmin: false, is_blocked: false, tenant_count: 1, last_login: "30 min ago", last_ip: "197.45.21.8", last_country: "Egypt", last_device: "Windows · Firefox" },
];

export default function AdminUsersPage() {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");

  const filtered = mockUsers.filter((u) => {
    const matchSearch = !search || u.name.toLowerCase().includes(search.toLowerCase()) || u.email.toLowerCase().includes(search.toLowerCase());
    const matchStatus = statusFilter === "all" || (statusFilter === "blocked" ? u.is_blocked : !u.is_blocked);
    return matchSearch && matchStatus;
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <div className="inline-flex items-center gap-2 mb-3">
          <span className="w-2 h-2 bg-[var(--tavus-terminal-black)]" />
          <span className="text-[11px] font-bold tracking-[0.2em] uppercase text-[var(--tavus-hardware-gray-8)]">ADMIN · USERS</span>
        </div>
        <h1 className="font-[var(--font-serif-display)] text-3xl sm:text-4xl font-normal tracking-tight text-[var(--tavus-terminal-black)]">
          User <span className="serif-italic">management</span>
        </h1>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--tavus-hardware-gray-8)]" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by name or email..."
            className="w-full h-10 pl-10 pr-3 border-2 border-[var(--tavus-terminal-black)] bg-white text-sm outline-none"
          />
        </div>
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="h-10 px-3 border-2 border-[var(--tavus-terminal-black)] bg-white text-sm font-bold">
          <option value="all">All Users</option>
          <option value="active">Active</option>
          <option value="blocked">Blocked</option>
        </select>
      </div>

      {/* Users table */}
      <div className="relative bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[6px_6px_0_0_var(--tavus-terminal-black)] overflow-hidden">
        <div className="absolute inset-0 bg-halftone-light opacity-10 pointer-events-none" />
        <div className="relative overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-[var(--tavus-terminal-black)] text-white">
              <tr>
                <th className="text-left p-3 font-extrabold tracking-wider uppercase text-[10px]">NAME</th>
                <th className="text-left p-3 font-extrabold tracking-wider uppercase text-[10px]">FB ID</th>
                <th className="text-center p-3 font-extrabold tracking-wider uppercase text-[10px]">BADGES</th>
                <th className="text-center p-3 font-extrabold tracking-wider uppercase text-[10px]">TENANTS</th>
                <th className="text-left p-3 font-extrabold tracking-wider uppercase text-[10px]">LAST LOGIN</th>
                <th className="text-left p-3 font-extrabold tracking-wider uppercase text-[10px]">LAST IP</th>
                <th className="text-left p-3 font-extrabold tracking-wider uppercase text-[10px]">COUNTRY</th>
                <th className="text-left p-3 font-extrabold tracking-wider uppercase text-[10px]">DEVICE</th>
                <th className="text-center p-3 font-extrabold tracking-wider uppercase text-[10px]">ACTIONS</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((u) => (
                <tr key={u.id} className="border-t border-[var(--tavus-terminal-black)]/10 hover:bg-[var(--tavus-plastic-1)]">
                  <td className="p-3">
                    <div className="font-bold text-[var(--tavus-terminal-black)]">{u.name}</div>
                    <div className="text-[10px] text-[var(--tavus-hardware-gray-8)]">{u.email}</div>
                  </td>
                  <td className="p-3 font-mono text-[10px] text-[var(--tavus-hardware-gray-8)]">{u.fb_id}</td>
                  <td className="p-3">
                    <div className="flex items-center justify-center gap-1 flex-wrap">
                      {u.is_superadmin && (
                        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 text-[8px] font-bold tracking-wider uppercase border border-[var(--tavus-terminal-black)] bg-[var(--tavus-neon-field-2)] text-white">
                          <ShieldCheck className="w-2.5 h-2.5" /> SUPERADMIN
                        </span>
                      )}
                      {u.is_blocked && (
                        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 text-[8px] font-bold tracking-wider uppercase border border-[var(--tavus-terminal-black)] bg-[var(--tavus-bubbletech-1)]">
                          <ShieldBan className="w-2.5 h-2.5" /> BLOCKED
                        </span>
                      )}
                      {!u.is_superadmin && !u.is_blocked && (
                        <span className="text-[9px] text-[var(--tavus-hardware-gray-8)]">—</span>
                      )}
                    </div>
                  </td>
                  <td className="p-3 text-center font-bold text-[var(--tavus-terminal-black)]">{u.tenant_count}</td>
                  <td className="p-3 text-[10px] text-[var(--tavus-hardware-gray-8)] whitespace-nowrap">{u.last_login}</td>
                  <td className="p-3 font-mono text-[10px] text-[var(--tavus-hardware-gray-8)]">{u.last_ip}</td>
                  <td className="p-3 text-[10px] text-[var(--tavus-terminal-black)]">
                    <span className="inline-flex items-center gap-1"><Globe className="w-3 h-3" />{u.last_country}</span>
                  </td>
                  <td className="p-3 text-[10px] text-[var(--tavus-hardware-gray-8)]">
                    <span className="inline-flex items-center gap-1"><Monitor className="w-3 h-3" />{u.last_device}</span>
                  </td>
                  <td className="p-3">
                    <div className="flex items-center justify-center gap-1">
                      <button className="inline-flex items-center justify-center w-7 h-7 border border-[var(--tavus-terminal-black)] bg-white hover:bg-[var(--tavus-bubbletech-4)]">
                        <Eye className="w-3.5 h-3.5" />
                      </button>
                      <button
                        className={`inline-flex items-center justify-center w-7 h-7 border border-[var(--tavus-terminal-black)] ${u.is_blocked ? "bg-[var(--tavus-neon-field-2)] text-white" : "bg-[var(--tavus-bubbletech-1)]"}`}
                        title={u.is_blocked ? "Unblock user" : "Block user"}
                      >
                        {u.is_blocked ? <ShieldCheck className="w-3.5 h-3.5" /> : <ShieldBan className="w-3.5 h-3.5" />}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="relative flex items-center justify-between p-3 border-t-2 border-[var(--tavus-terminal-black)] bg-[var(--tavus-plastic-1)]">
          <div className="text-[10px] font-bold text-[var(--tavus-hardware-gray-8)]">{filtered.length} users</div>
          <div className="text-[10px] text-[var(--tavus-hardware-gray-8)]">{filtered.filter((u) => u.is_blocked).length} blocked · {filtered.filter((u) => u.is_superadmin).length} superadmins</div>
        </div>
      </div>
    </div>
  );
}
