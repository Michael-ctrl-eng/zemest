"use client";

import { useState, useEffect, useCallback, use } from "react";
import Link from "next/link";
import {
  ShoppingBag,
  DollarSign,
  MessageCircle,
  Users,
  Clock,
  ArrowRight,
  RefreshCw,
  Package,
  Globe,
} from "lucide-react";
import { tenantsApi, api, formatDateTime, egp, toNumber, type TenantStats, type Tenant } from "@/lib/zemest-api";
import {
  WinCard,
  StatTile,
  StatusBadge,
  DashHeader,
  LoadingState,
  ErrorState,
  EmptyState,
  TavusLink,
} from "@/components/site/dash";

export default function OverviewPage({ params }: { params: Promise<{ tenantId: string }> }) {
  const { tenantId } = use(params);
  const [stats, setStats] = useState<TenantStats | null>(null);
  const [pageName, setPageName] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (opts?: { silent?: boolean }) => {
    const silent = opts?.silent ?? false;
    if (silent) setRefreshing(true);
    else setLoading(true);
    setError(null);
    try {
      const [t, s] = await Promise.all([
        tenantsApi.get(tenantId).catch(() => null),
        tenantsApi.stats(tenantId),
      ]);
      setStats(s);
      setPageName(t?.page_name || "");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load overview");
    } finally {
      if (silent) setRefreshing(false);
      else setLoading(false);
    }
  }, [tenantId]);

  useEffect(() => {
    // Instant paint from cache (warmed by hover-prefetch on the tenants page),
    // then silently revalidate in the background.
    const cachedStats = api.peek<TenantStats>(`/tenants/${tenantId}/stats`);
    const cachedTenant = api.peek<Tenant>(`/tenants/${tenantId}`);
    if (cachedStats) {
      setStats(cachedStats);
      if (cachedTenant?.page_name) setPageName(cachedTenant.page_name);
      setLoading(false);
      load({ silent: true });
    } else {
      load();
    }
  }, [load]);

  const nameParts = pageName.trim().split(/\s+/);
  const nameHead = nameParts.length > 1 ? nameParts.slice(0, -1).join(" ") : "";
  const nameTail = nameParts.length > 1 ? nameParts[nameParts.length - 1] : pageName || "Overview";

  return (
    <div className="space-y-6">
      <DashHeader
        eyebrow="Overview"
        title={nameHead || "Business"}
        tail={nameTail}
        action={
          <button
            onClick={() => load()}
            title="Refresh"
            aria-label="Refresh"
            className="inline-flex items-center justify-center w-11 h-11 border-[3px] border-[var(--tavus-terminal-black)] bg-white shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:shadow-[4px_4px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] transition-all"
          >
            <RefreshCw className={`w-4 h-4 ${loading || refreshing ? "animate-spin" : ""}`} strokeWidth={2.5} />
          </button>
        }
      />

      {error ? <ErrorState message={error} onRetry={load} /> : null}

      {loading ? <LoadingState label="Loading overview" /> : null}

      {!loading && !error && stats ? (
        <>
          {/* Stats tiles */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3.5">
            <StatTile
              icon={<ShoppingBag className="w-[18px] h-[18px]" strokeWidth={2.25} />}
              label="Today's orders"
              value={String(stats.today_orders ?? 0)}
              color="var(--tavus-bubbletech-4)"
            />
            <StatTile
              icon={<DollarSign className="w-[18px] h-[18px]" strokeWidth={2.25} />}
              label="Today's revenue"
              value={egp(stats.today_revenue)}
              color="var(--tavus-atomic-glow-1)"
            />
            <StatTile
              icon={<Users className="w-[18px] h-[18px]" strokeWidth={2.25} />}
              label="Total customers"
              value={String(stats.customers_count ?? 0)}
              color="var(--tavus-frost-4)"
            />
            <StatTile
              icon={<MessageCircle className="w-[18px] h-[18px]" strokeWidth={2.25} />}
              label="Active conversations"
              value={String(stats.active_conversations ?? 0)}
              color="var(--tavus-floppy-fog-3)"
            />
            <StatTile
              icon={<Clock className="w-[18px] h-[18px]" strokeWidth={2.25} />}
              label="Pending orders"
              value={String(stats.pending_orders ?? 0)}
              color="var(--tavus-keyboard-tan-2)"
            />
          </div>

          {/* Recent orders + Top products */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            <WinCard title="Recent orders" dot="var(--tavus-bubbletech-4)">
              {stats.recent_orders?.length ? (
                <div className="divide-y divide-[var(--tavus-terminal-black)]/10">
                  {stats.recent_orders.map((o) => (
                    <div
                      key={o.order_number}
                      className="flex items-center gap-3 px-4 py-3.5 hover:bg-[var(--tavus-plastic-1)] transition-colors"
                    >
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-bold text-[var(--tavus-terminal-black)] truncate">
                          {o.customer_name}
                        </div>
                        <div className="text-[10px] font-mono text-[var(--tavus-hardware-gray-8)]">
                          {o.order_number}
                        </div>
                      </div>
                      <div className="text-sm font-extrabold text-[var(--tavus-terminal-black)] whitespace-nowrap tabular-nums">
                        {egp(o.total)}
                      </div>
                      <div className="w-24 text-center shrink-0">
                        <StatusBadge status={o.status} />
                      </div>
                      <div className="hidden xl:block text-[10px] font-medium text-[var(--tavus-hardware-gray-8)] w-24 text-right whitespace-nowrap">
                        {formatDateTime(o.created_at)}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState
                  icon={<ShoppingBag className="w-6 h-6" strokeWidth={2} />}
                  title="No orders yet"
                  hint="Orders captured by your AI agent will land here. Try the chat playground to generate your first one."
                  action={
                    <TavusLink href={`/dashboard/${tenantId}/chat`} variant="dark">
                      Open chat playground <ArrowRight className="w-3.5 h-3.5" />
                    </TavusLink>
                  }
                />
              )}
            </WinCard>

            <WinCard title="Top products" dot="var(--tavus-neon-field-2)">
              {stats.top_products?.length ? (
                <div className="divide-y divide-[var(--tavus-terminal-black)]/10">
                  {stats.top_products.map((p, i) => (
                    <div
                      key={`${p.name}-${i}`}
                      className="flex items-center gap-3 px-4 py-3.5 hover:bg-[var(--tavus-plastic-1)] transition-colors"
                    >
                      <div className="font-serif text-[26px] leading-none font-bold text-[var(--tavus-terminal-black)]/25 w-8 text-center">
                        {i + 1}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-bold text-[var(--tavus-terminal-black)] truncate">{p.name}</div>
                        <div className="text-[10px] font-medium text-[var(--tavus-hardware-gray-8)]">
                          {toNumber(p.qty)} sold
                        </div>
                      </div>
                      <div className="text-sm font-extrabold text-[var(--tavus-terminal-black)] whitespace-nowrap tabular-nums">
                        {egp(p.revenue)}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState
                  icon={<Package className="w-6 h-6" strokeWidth={2} />}
                  title="No top products yet"
                  hint="Once orders roll in, your best sellers get ranked here automatically."
                  action={
                    <TavusLink href={`/dashboard/${tenantId}/products`} variant="secondary">
                      Add a product <ArrowRight className="w-3.5 h-3.5" />
                    </TavusLink>
                  }
                />
              )}
            </WinCard>
          </div>

          {/* Quick actions — editorial band */}
          <div className="relative border-[3px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-bubbletech-1)] shadow-[6px_6px_0_0_var(--tavus-terminal-black)] overflow-hidden">
            <div className="absolute inset-0 bg-halftone opacity-20 pointer-events-none" />
            <div className="relative flex flex-wrap items-center justify-between gap-4 px-5 py-4">
              <div>
                <div className="text-[9px] font-extrabold tracking-[0.22em] uppercase text-[var(--tavus-hardware-gray-8)]">
                  Quick actions
                </div>
                <div className="font-serif text-xl text-[var(--tavus-terminal-black)] mt-0.5">
                  Put your agent <span className="serif-italic">to work</span>
                </div>
              </div>
              <div className="flex flex-wrap gap-3">
                <TavusLink href={`/dashboard/${tenantId}/products`} variant="secondary">
                  Add product <ArrowRight className="w-3.5 h-3.5" />
                </TavusLink>
                <TavusLink href={`/dashboard/${tenantId}/chat`} variant="dark">
                  Test chat <ArrowRight className="w-3.5 h-3.5" />
                </TavusLink>
                <TavusLink href={`/dashboard/${tenantId}/crawl`}>
                  Build knowledge <Globe className="w-3.5 h-3.5" />
                </TavusLink>
              </div>
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
}
