"use client";

import { useCallback, useEffect, useState } from "react";
import { Globe, Coins, Activity, TrendingUp, TrendingDown, Users as UsersIcon, MousePointerClick, Clock, MessageSquare } from "lucide-react";
import { tenantsApi, adminApi, apiErrorMessage, type Tenant, type TenantStats, type AdminGeoItem, type AdminOverview } from "@/lib/zemest-api";
import { LoadingState, ErrorState } from "@/components/site/dash";

interface GeoRow {
  country: string;
  users: number;
  percentage: number;
  code: string;
}

interface TokenRow {
  tenant: string;
  used: number;
  quota: number | null;
  color: string;
}

interface BehaviorMetric {
  label: string;
  value: string;
  delta: string | null;
  up: boolean;
  icon: React.ElementType;
}

const TOKEN_COLORS = [
  "var(--tavus-bubbletech-4)",
  "var(--tavus-neon-field-2)",
  "var(--tavus-atomic-glow-1)",
  "var(--tavus-floppy-fog-3)",
  "var(--tavus-frost-4)",
  "var(--tavus-bubbletech-3)",
];

export default function AdminAnalyticsPage() {
  const [tab, setTab] = useState<"geo" | "tokens" | "behavior">("geo");
  const [geo, setGeo] = useState<GeoRow[]>([]);
  const [tokens, setTokens] = useState<TokenRow[]>([]);
  const [platformTokens, setPlatformTokens] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [geoData, tenantList, overview] = await Promise.all([
        adminApi.geoDistribution(),
        tenantsApi.list(),
        adminApi.overview(),
      ]);
      const totalGeoUsers = (geoData ?? []).reduce((a, g) => a + g.user_count, 0);
      setGeo(
        (geoData ?? []).map((g: AdminGeoItem) => ({
          country: g.country,
          users: g.user_count,
          percentage: totalGeoUsers > 0 ? (g.user_count / totalGeoUsers) * 100 : 0,
          code: "—", // country codes are not part of the API response
        }))
      );
      setPlatformTokens(overview?.total_tokens_used ?? null);
      // Per-tenant token usage from the caller's real tenants (no platform-wide
      // admin endpoint exists yet); quotas are not exposed by the API → "—".
      const stats = await Promise.allSettled((tenantList ?? []).map((t: Tenant) => tenantsApi.stats(t.id)));
      setTokens(
        (tenantList ?? []).map((t: Tenant, i: number) => {
          const s: TenantStats | null = stats[i]?.status === "fulfilled" ? (stats[i] as PromiseFulfilledResult<TenantStats>).value : null;
          return {
            tenant: t.page_name,
            used: s ? s.total_tokens : 0,
            quota: null,
            color: TOKEN_COLORS[i % TOKEN_COLORS.length],
          };
        })
      );
    } catch (err: unknown) {
      setError(apiErrorMessage(err, "Failed to load analytics"));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // The backend exposes no behavior-metrics endpoint — every value renders "—".
  const behaviorMetrics: BehaviorMetric[] = [
    { label: "AVG SESSION DURATION", value: "—", delta: null, up: true, icon: Clock },
    { label: "AVG MESSAGES PER SESSION", value: "—", delta: null, up: true, icon: MessageSquare },
    { label: "AVG ORDERS PER USER", value: "—", delta: null, up: true, icon: TrendingUp },
    { label: "BOUNCE RATE", value: "—", delta: null, up: false, icon: TrendingDown },
    { label: "DAILY ACTIVE USERS", value: "—", delta: null, up: true, icon: UsersIcon },
    { label: "CLICK-THROUGH RATE", value: "—", delta: null, up: true, icon: MousePointerClick },
  ];

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

      {/* Error state */}
      {error ? <ErrorState message={error} onRetry={() => load()} /> : null}

      {/* Loading state */}
      {loading ? <LoadingState label="Loading analytics" /> : null}

      {!loading && !error ? (
        <>
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
                    {geo.map((g) => (
                      <tr key={g.country} className="border-t border-[var(--tavus-terminal-black)]/10 hover:bg-[var(--tavus-plastic-1)]">
                        <td className="p-3 font-bold text-[var(--tavus-terminal-black)]">
                          <span className="inline-flex items-center gap-1.5"><Globe className="w-3.5 h-3.5" />{g.country}</span>
                        </td>
                        <td className="p-3 text-center">
                          <span className="inline-block px-2 py-0.5 text-[9px] font-bold tracking-wider uppercase border border-[var(--tavus-terminal-black)] bg-[var(--tavus-plastic-2)]">{g.code}</span>
                        </td>
                        <td className="p-3 text-center font-bold text-[var(--tavus-terminal-black)]">{g.users.toLocaleString()}</td>
                        <td className="p-3 font-bold text-[var(--tavus-terminal-black)]">{g.percentage.toFixed(1)}%</td>
                        <td className="p-3">
                          <div className="h-3 bg-[var(--tavus-plastic-2)] border border-[var(--tavus-terminal-black)] overflow-hidden">
                            <div className="h-full bg-[var(--tavus-bubbletech-4)]" style={{ width: `${g.percentage}%` }} />
                          </div>
                        </td>
                      </tr>
                    ))}
                    {geo.length === 0 ? (
                      <tr>
                        <td colSpan={5} className="p-8 text-center text-sm font-semibold text-[var(--tavus-hardware-gray-8)]">
                          No geographic data recorded yet.
                        </td>
                      </tr>
                    ) : null}
                  </tbody>
                </table>
              </div>
              <div className="relative flex items-center justify-between p-3 border-t-2 border-[var(--tavus-terminal-black)] bg-[var(--tavus-plastic-1)]">
                <div className="text-[10px] font-bold text-[var(--tavus-hardware-gray-8)]">{geo.reduce((a, g) => a + g.users, 0).toLocaleString()} total users</div>
                <div className="text-[10px] text-[var(--tavus-hardware-gray-8)]">{geo.length} countries</div>
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
                {tokens.map((t, i) => {
                  const pct = t.quota != null ? Math.min(100, (t.used / t.quota) * 100) : null;
                  return (
                    <div key={`${t.tenant}-${i}`}>
                      <div className="flex items-center justify-between mb-1.5">
                        <span className="text-sm font-bold text-[var(--tavus-terminal-black)]">{t.tenant}</span>
                        <span className="text-[10px] font-bold font-mono text-[var(--tavus-hardware-gray-8)]">
                          {t.used.toLocaleString()} / {t.quota != null ? t.quota.toLocaleString() : "—"}{pct != null ? ` (${pct.toFixed(1)}%)` : ""}
                        </span>
                      </div>
                      {pct != null ? (
                        <div className="h-4 bg-[var(--tavus-plastic-2)] border-2 border-[var(--tavus-terminal-black)] overflow-hidden">
                          <div className="h-full" style={{ width: `${pct}%`, background: t.color }} />
                        </div>
                      ) : (
                        <div className="h-4 bg-[var(--tavus-plastic-2)] border-2 border-[var(--tavus-terminal-black)] overflow-hidden">
                          <div className="h-full w-0" style={{ background: t.color }} />
                        </div>
                      )}
                    </div>
                  );
                })}
                {tokens.length === 0 ? (
                  <div className="text-center text-sm font-semibold text-[var(--tavus-hardware-gray-8)] py-6">
                    No tenants visible to your account.
                  </div>
                ) : null}
                <div className="relative bg-[var(--tavus-plastic-1)] border-2 border-[var(--tavus-terminal-black)] p-3 overflow-hidden">
                  <div className="absolute inset-0 bg-halftone-light opacity-10 pointer-events-none" />
                  <div className="relative flex items-center justify-between">
                    <div>
                      <div className="text-[9px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)]">PLATFORM TOTAL</div>
                      <div className="text-xl font-bold text-[var(--tavus-terminal-black)]">{platformTokens != null ? platformTokens.toLocaleString() : "—"} / —</div>
                    </div>
                    <div className="text-right">
                      <div className="text-[9px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)]">UTILIZATION</div>
                      <div className="text-xl font-bold text-[var(--tavus-terminal-black)]">—</div>
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
                    {m.delta != null ? (
                      <span className={`text-[10px] font-bold ${m.up ? "text-[var(--tavus-neon-field-4)]" : "text-[var(--tavus-bubbletech-4)]"}`}>
                        {m.up ? <TrendingUp className="w-3 h-3 inline mr-0.5" /> : <TrendingDown className="w-3 h-3 inline mr-0.5" />}
                        {m.delta}
                      </span>
                    ) : (
                      <span className="text-[10px] font-bold text-[var(--tavus-hardware-gray-8)]">—</span>
                    )}
                  </div>
                  <div className="relative text-lg font-bold text-[var(--tavus-terminal-black)]">{m.value}</div>
                  <div className="relative text-[9px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)] mt-0.5">{m.label}</div>
                </div>
              ))}
            </div>
          )}
        </>
      ) : null}
    </div>
  );
}
