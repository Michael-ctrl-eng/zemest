"use client";

import { useCallback, useEffect, useState } from "react";
import { Search, ShieldCheck, ShieldBan, Eye, Globe, Monitor, Loader2, AlertTriangle } from "lucide-react";
import {
  adminApi,
  apiErrorMessage,
  formatDateTime,
  type AdminAuditLogItem,
  type AdminUserActivityItem,
} from "@/lib/zemest-api";
import { LoadingState, ErrorState } from "@/components/site/dash";

interface AdminUser {
  id: string;
  name: string;
  email: string;
  fb_id: string;
  is_superadmin: boolean;
  is_blocked: boolean;
  tenant_count: number | null;
  last_login: string;
  last_ip: string;
  last_country: string;
  last_device: string;
}

/**
 * The backend has no GET /api/admin/users list endpoint. The users shown here
 * are therefore derived from REAL admin data: audit-log actors + user
 * block/unblock targets, plus user ids seen in active sessions. Fields the
 * API does not expose (name, email, fb id, tenant count, superadmin flag)
 * render as "—" until such an endpoint exists.
 */
function deriveUsers(logs: AdminAuditLogItem[], sessionUserIds: string[]): AdminUser[] {
  const byId = new Map<string, { isBlocked?: boolean }>();
  const ensure = (id: string) => {
    let row = byId.get(id);
    if (!row) {
      row = {};
      byId.set(id, row);
    }
    return row;
  };
  // logs are newest-first: the FIRST block/unblock seen for a target is its latest state
  for (const l of logs) {
    if (l.admin_id) ensure(l.admin_id);
    if (l.target_type === "user" && l.target_id) {
      const row = ensure(l.target_id);
      if (row.isBlocked === undefined) row.isBlocked = l.action === "user.block";
    }
  }
  for (const uid of sessionUserIds) ensure(uid);
  return [...byId.entries()].map(([id, row]) => ({
    id,
    name: "—",
    email: id, // the API exposes no name/email — the user id is the only real identifier
    fb_id: "—",
    is_superadmin: false,
    is_blocked: row.isBlocked === true,
    tenant_count: null,
    last_login: "—",
    last_ip: "—",
    last_country: "—",
    last_device: "—",
  }));
}

function applyActivity(users: AdminUser[], activities: PromiseSettledResult<AdminUserActivityItem[]>[]) {
  return users.map((u, i) => {
    const res = activities[i];
    if (res.status !== "fulfilled" || !res.value?.length) return u;
    const latest = res.value[0];
    return {
      ...u,
      last_login: formatDateTime(latest.login_at),
      last_ip: latest.ip_address || "—",
      last_country: latest.country || "—",
      last_device: [latest.device_type, latest.browser].filter(Boolean).join(" · ") || "—",
    };
  });
}

export default function AdminUsersPage() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updatingId, setUpdatingId] = useState<string | null>(null);
  const [updateError, setUpdateError] = useState<{ userId: string; message: string } | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [audit, sessions] = await Promise.all([
        adminApi.auditLog(1, 200),
        adminApi.activeSessions(),
      ]);
      const derived = deriveUsers(audit?.logs ?? [], (sessions ?? []).map((s) => s.user_id));
      // Enrich with each user's real session history (last login / IP / country / device)
      const activities = await Promise.allSettled(derived.map((u) => adminApi.userActivity(u.id)));
      setUsers(applyActivity(derived, activities));
    } catch (err: unknown) {
      setError(apiErrorMessage(err, "Failed to load users"));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function handleToggleBlock(user: AdminUser) {
    setUpdatingId(user.id);
    setUpdateError(null);
    try {
      if (user.is_blocked) {
        await adminApi.unblockUser(user.id);
      } else {
        await adminApi.blockUser(user.id, "Blocked via admin users page");
      }
      await load();
    } catch (err: unknown) {
      setUpdateError({
        userId: user.id,
        message: err instanceof Error ? err.message : `Failed to ${user.is_blocked ? "unblock" : "block"} user`,
      });
    } finally {
      setUpdatingId(null);
    }
  }

  const filtered = users.filter((u) => {
    const matchSearch = !search || u.name.toLowerCase().includes(search.toLowerCase()) || u.email.toLowerCase().includes(search.toLowerCase()) || u.id.toLowerCase().includes(search.toLowerCase());
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

      {/* Error state */}
      {error ? <ErrorState message={error} onRetry={() => load()} /> : null}

      {/* Loading state */}
      {loading ? <LoadingState label="Loading users" /> : null}

      {!loading && !error ? (
        <>
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

          {updateError ? (
            <div className="flex items-center gap-3 border-[3px] border-[var(--tavus-coral-1)] bg-[var(--tavus-coral-3)]/40 p-3">
              <AlertTriangle className="w-4 h-4 text-[var(--tavus-terminal-black)] shrink-0" strokeWidth={2.5} />
              <div className="text-xs font-bold text-[var(--tavus-terminal-black)]">{updateError.message}</div>
            </div>
          ) : null}

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
                  {filtered.map((u) => {
                    const isUpdating = updatingId === u.id;
                    return (
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
                        <td className="p-3 text-center font-bold text-[var(--tavus-terminal-black)]">{u.tenant_count ?? "—"}</td>
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
                              onClick={() => handleToggleBlock(u)}
                              disabled={isUpdating}
                              className={`inline-flex items-center justify-center w-7 h-7 border border-[var(--tavus-terminal-black)] ${u.is_blocked ? "bg-[var(--tavus-neon-field-2)] text-white" : "bg-[var(--tavus-bubbletech-1)]"}`}
                              title={u.is_blocked ? "Unblock user" : "Block user"}
                            >
                              {isUpdating ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : u.is_blocked ? <ShieldCheck className="w-3.5 h-3.5" /> : <ShieldBan className="w-3.5 h-3.5" />}
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                  {filtered.length === 0 ? (
                    <tr>
                      <td colSpan={9} className="p-8 text-center text-sm font-semibold text-[var(--tavus-hardware-gray-8)]">
                        No users match your filters.
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
            <div className="relative flex items-center justify-between p-3 border-t-2 border-[var(--tavus-terminal-black)] bg-[var(--tavus-plastic-1)]">
              <div className="text-[10px] font-bold text-[var(--tavus-hardware-gray-8)]">{filtered.length} users</div>
              <div className="text-[10px] text-[var(--tavus-hardware-gray-8)]">{filtered.filter((u) => u.is_blocked).length} blocked · {filtered.filter((u) => u.is_superadmin).length} superadmins</div>
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
}
