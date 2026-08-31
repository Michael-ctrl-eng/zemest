"use client";

import { useCallback, useEffect, useState } from "react";
import { Search, Facebook, Instagram, MessageCircle as WhatsApp, Package, ShoppingCart, Users as UsersIcon, Coins, Eye } from "lucide-react";
import { tenantsApi, adminApi, apiErrorMessage, type Tenant, type TenantStats } from "@/lib/zemest-api";
import { LoadingState, ErrorState } from "@/components/site/dash";

interface TenantRow {
  id: string;
  page_name: string;
  owner_email: string;
  fb_page_id: string;
  ig_user_id: string;
  wa_phone_id: string;
  is_active: boolean;
  products_count: number | null;
  orders_count: number | null;
  customers_count: number | null;
  tokens_used: number | null;
}

/**
 * There is no platform-wide GET /api/admin/tenants endpoint yet, so this page
 * lists the caller's real tenants (GET /tenants) with real per-tenant stats
 * (GET /tenants/{id}/stats, owner-scoped). Fields the API does not expose
 * (IG user id, WA phone id) render as "—".
 */
function toRows(tenants: Tenant[], stats: PromiseSettledResult<TenantStats>[]): TenantRow[] {
  return tenants.map((t, i) => {
    const s = stats[i]?.status === "fulfilled" ? stats[i].value : null;
    return {
      id: t.id,
      page_name: t.page_name,
      owner_email: t.business_email || "—",
      fb_page_id: t.fb_page_id || "—",
      ig_user_id: "—",
      wa_phone_id: "—",
      is_active: t.is_active,
      products_count: s ? s.products_count : null,
      orders_count: s ? s.orders_count : null,
      customers_count: s ? s.customers_count : null,
      tokens_used: s ? s.total_tokens : null,
    };
  });
}

export default function AdminTenantsPage() {
  const [tenants, setTenants] = useState<TenantRow[]>([]);
  const [platformTotal, setPlatformTotal] = useState<number | null>(null);
  const [search, setSearch] = useState("");
  const [activeFilter, setActiveFilter] = useState("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [list, overview] = await Promise.all([
        tenantsApi.list(),
        adminApi.overview(),
      ]);
      setPlatformTotal(overview?.total_tenants ?? null);
      const stats = await Promise.allSettled((list ?? []).map((t) => tenantsApi.stats(t.id)));
      setTenants(toRows(list ?? [], stats));
    } catch (err: unknown) {
      setError(apiErrorMessage(err, "Failed to load tenants"));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const filtered = tenants.filter((t) => {
    const matchSearch = !search || t.page_name.toLowerCase().includes(search.toLowerCase()) || t.owner_email.toLowerCase().includes(search.toLowerCase());
    const matchActive = activeFilter === "all" || (activeFilter === "active" ? t.is_active : !t.is_active);
    return matchSearch && matchActive;
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <div className="inline-flex items-center gap-2 mb-3">
          <span className="w-2 h-2 bg-[var(--tavus-terminal-black)]" />
          <span className="text-[11px] font-bold tracking-[0.2em] uppercase text-[var(--tavus-hardware-gray-8)]">ADMIN · TENANTS</span>
        </div>
        <h1 className="font-[var(--font-serif-display)] text-3xl sm:text-4xl font-normal tracking-tight text-[var(--tavus-terminal-black)]">
          Tenant <span className="serif-italic">management</span>
        </h1>
      </div>

      {/* Error state */}
      {error ? <ErrorState message={error} onRetry={() => load()} /> : null}

      {/* Loading state */}
      {loading ? <LoadingState label="Loading tenants" /> : null}

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
                placeholder="Search by page name or owner email..."
                className="w-full h-10 pl-10 pr-3 border-2 border-[var(--tavus-terminal-black)] bg-white text-sm outline-none"
              />
            </div>
            <select value={activeFilter} onChange={(e) => setActiveFilter(e.target.value)} className="h-10 px-3 border-2 border-[var(--tavus-terminal-black)] bg-white text-sm font-bold">
              <option value="all">All Tenants</option>
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
            </select>
          </div>

          {/* Tenants table */}
          <div className="relative bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[6px_6px_0_0_var(--tavus-terminal-black)] overflow-hidden">
            <div className="absolute inset-0 bg-halftone-light opacity-10 pointer-events-none" />
            <div className="relative overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-[var(--tavus-terminal-black)] text-white">
                  <tr>
                    <th className="text-left p-3 font-extrabold tracking-wider uppercase text-[10px]">PAGE NAME</th>
                    <th className="text-left p-3 font-extrabold tracking-wider uppercase text-[10px]">OWNER</th>
                    <th className="text-left p-3 font-extrabold tracking-wider uppercase text-[10px]">FB PAGE ID</th>
                    <th className="text-left p-3 font-extrabold tracking-wider uppercase text-[10px]">IG USER ID</th>
                    <th className="text-left p-3 font-extrabold tracking-wider uppercase text-[10px]">WA PHONE ID</th>
                    <th className="text-center p-3 font-extrabold tracking-wider uppercase text-[10px]">ACTIVE</th>
                    <th className="text-center p-3 font-extrabold tracking-wider uppercase text-[10px]">PRODUCTS</th>
                    <th className="text-center p-3 font-extrabold tracking-wider uppercase text-[10px]">ORDERS</th>
                    <th className="text-center p-3 font-extrabold tracking-wider uppercase text-[10px]">CUSTOMERS</th>
                    <th className="text-center p-3 font-extrabold tracking-wider uppercase text-[10px]">TOKENS</th>
                    <th className="text-center p-3 font-extrabold tracking-wider uppercase text-[10px]">VIEW</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((t) => (
                    <tr key={t.id} className="border-t border-[var(--tavus-terminal-black)]/10 hover:bg-[var(--tavus-plastic-1)]">
                      <td className="p-3">
                        <div className="font-bold text-[var(--tavus-terminal-black)]">{t.page_name}</div>
                        <div className="text-[10px] font-mono text-[var(--tavus-hardware-gray-8)]">{t.id}</div>
                      </td>
                      <td className="p-3 text-[11px] text-[var(--tavus-hardware-gray-8)]">{t.owner_email}</td>
                      <td className="p-3">
                        {t.fb_page_id !== "—" ? (
                          <span className="inline-flex items-center gap-1 text-[10px] font-mono text-[var(--tavus-terminal-black)]">
                            <Facebook className="w-3 h-3" />{t.fb_page_id}
                          </span>
                        ) : <span className="text-[10px] text-[var(--tavus-hardware-gray-8)]">—</span>}
                      </td>
                      <td className="p-3">
                        {t.ig_user_id !== "—" ? (
                          <span className="inline-flex items-center gap-1 text-[10px] font-mono text-[var(--tavus-terminal-black)]">
                            <Instagram className="w-3 h-3" />{t.ig_user_id}
                          </span>
                        ) : <span className="text-[10px] text-[var(--tavus-hardware-gray-8)]">—</span>}
                      </td>
                      <td className="p-3">
                        {t.wa_phone_id !== "—" ? (
                          <span className="inline-flex items-center gap-1 text-[10px] font-mono text-[var(--tavus-terminal-black)]">
                            <WhatsApp className="w-3 h-3" />{t.wa_phone_id}
                          </span>
                        ) : <span className="text-[10px] text-[var(--tavus-hardware-gray-8)]">—</span>}
                      </td>
                      <td className="p-3 text-center">
                        <span className={`inline-block w-3 h-3 border border-[var(--tavus-terminal-black)] ${t.is_active ? "bg-[var(--tavus-neon-field-2)] text-white" : "bg-[var(--tavus-bubbletech-1)]"}`} />
                      </td>
                      <td className="p-3 text-center font-bold text-[var(--tavus-terminal-black)]">
                        <span className="inline-flex items-center gap-1"><Package className="w-3 h-3" />{t.products_count ?? "—"}</span>
                      </td>
                      <td className="p-3 text-center font-bold text-[var(--tavus-terminal-black)]">
                        <span className="inline-flex items-center gap-1"><ShoppingCart className="w-3 h-3" />{t.orders_count != null ? t.orders_count.toLocaleString() : "—"}</span>
                      </td>
                      <td className="p-3 text-center font-bold text-[var(--tavus-terminal-black)]">
                        <span className="inline-flex items-center gap-1"><UsersIcon className="w-3 h-3" />{t.customers_count != null ? t.customers_count.toLocaleString() : "—"}</span>
                      </td>
                      <td className="p-3 text-center font-bold text-[var(--tavus-terminal-black)]">
                        <span className="inline-flex items-center gap-1"><Coins className="w-3 h-3" />{t.tokens_used != null ? t.tokens_used.toLocaleString() : "—"}</span>
                      </td>
                      <td className="p-3">
                        <div className="flex items-center justify-center">
                          <button className="inline-flex items-center justify-center w-7 h-7 border border-[var(--tavus-terminal-black)] bg-white hover:bg-[var(--tavus-bubbletech-4)]">
                            <Eye className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                  {filtered.length === 0 ? (
                    <tr>
                      <td colSpan={11} className="p-8 text-center text-sm font-semibold text-[var(--tavus-hardware-gray-8)]">
                        {tenants.length === 0
                          ? `No tenants visible to your account${platformTotal != null ? ` — the platform has ${platformTotal.toLocaleString()} tenant${platformTotal === 1 ? "" : "s"} in total` : ""}.`
                          : "No tenants match your filters."}
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
            <div className="relative flex items-center justify-between p-3 border-t-2 border-[var(--tavus-terminal-black)] bg-[var(--tavus-plastic-1)]">
              <div className="text-[10px] font-bold text-[var(--tavus-hardware-gray-8)]">{filtered.length} tenants</div>
              <div className="text-[10px] text-[var(--tavus-hardware-gray-8)]">{filtered.filter((t) => t.is_active).length} active</div>
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
}
