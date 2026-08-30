"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { Navbar } from "@/components/site/navbar";
import { Footer } from "@/components/site/footer";
import {
  Plus,
  ShoppingBag,
  DollarSign,
  MessageCircle,
  Users,
  Facebook,
  Instagram,
  MessageCircle as WhatsApp,
  RefreshCw,
  ArrowRight,
  Building2,
} from "lucide-react";
import { tenantsApi, api, type Tenant, type TenantStats } from "@/lib/zemest-api";
import {
  WinCard,
  DashHeader,
  LoadingState,
  ErrorState,
  EmptyState,
  TavusButton,
  TavusLink,
  Field,
  inputClass,
} from "@/components/site/dash";

interface TenantWithStats extends Tenant {
  fb_connected?: boolean;
  ig_connected?: boolean;
  wa_connected?: boolean;
  today_orders?: number;
  today_revenue?: number;
  total_customers?: number;
  active_conversations?: number;
}

/** Instantly seed tenant cards from the SWR cache (paints before any network). */
function seedTenantsFromCache(): TenantWithStats[] | null {
  const list = api.peek<Tenant[]>("/tenants");
  if (!list || !list.length) return null;
  return list.map((t) => {
    const s = api.peek<TenantStats>(`/tenants/${t.id}/stats`);
    return {
      ...t,
      fb_connected: Boolean((t as Tenant & { fb_page_id?: string }).fb_page_id),
      ig_connected: Boolean((t as Tenant & { ig_user_id?: string }).ig_user_id),
      wa_connected: Boolean((t as Tenant & { wa_phone_number_id?: string }).wa_phone_number_id),
      today_orders: s?.today_orders ?? 0,
      today_revenue: s?.today_revenue ?? 0,
      total_customers: s?.customers_count ?? 0,
      active_conversations: s?.active_conversations ?? 0,
    };
  });
}

export default function DashboardHome() {
  const [showCreate, setShowCreate] = useState(false);
  const [tenants, setTenants] = useState<TenantWithStats[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (opts?: { silent?: boolean }) => {
    const silent = opts?.silent ?? false;
    if (silent) setRefreshing(true);
    else setLoading(true);
    setError(null);
    try {
      const list = await tenantsApi.list();
      // Enrich each tenant with live stats (fast parallel calls)
      const enriched = await Promise.all(
        (list || []).map(async (t) => {
          try {
            const s = await tenantsApi.stats(t.id);
            return {
              ...t,
              fb_connected: Boolean((t as Tenant & { fb_page_id?: string }).fb_page_id),
              ig_connected: Boolean((t as Tenant & { ig_user_id?: string }).ig_user_id),
              wa_connected: Boolean((t as Tenant & { wa_phone_number_id?: string }).wa_phone_number_id),
              today_orders: s?.today_orders ?? 0,
              today_revenue: s?.today_revenue ?? 0,
              total_customers: s?.customers_count ?? 0,
              active_conversations: s?.active_conversations ?? 0,
            };
          } catch {
            return { ...t, fb_connected: false, ig_connected: false, wa_connected: false };
          }
        })
      );
      setTenants(enriched);
    } catch (err: unknown) {
      const detail = err instanceof Error ? err.message : "Failed to load businesses";
      setError(detail);
    } finally {
      if (silent) setRefreshing(false);
      else setLoading(false);
    }
  }, []);

  useEffect(() => {
    // Instant paint from cache, then silently revalidate in the background.
    const cached = seedTenantsFromCache();
    if (cached) {
      setTenants(cached);
      setLoading(false);
      load({ silent: true });
    } else {
      load();
    }
  }, [load]);

  return (
    <div className="min-h-screen bg-grain">
      <Navbar />
      <main className="pt-24 pb-16">
        <div className="mx-auto max-w-[1280px] px-5 sm:px-8">
          <div className="mb-8">
            <DashHeader
              eyebrow="Dashboard"
              title="Your"
              tail="businesses"
              action={
                <>
                  <button
                    onClick={() => load()}
                    title="Refresh"
                    aria-label="Refresh"
                    className="inline-flex items-center justify-center w-11 h-11 border-[3px] border-[var(--tavus-terminal-black)] bg-white shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:shadow-[4px_4px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] transition-all"
                  >
                    <RefreshCw className={`w-4 h-4 ${loading || refreshing ? "animate-spin" : ""}`} strokeWidth={2.5} />
                  </button>
                  <TavusButton onClick={() => setShowCreate(!showCreate)}>
                    <Plus className="w-4 h-4" strokeWidth={2.5} /> New business
                  </TavusButton>
                </>
              }
            />
          </div>

          {showCreate ? <CreateBusinessForm onClose={() => setShowCreate(false)} onCreated={load} /> : null}

          {error ? <ErrorState message={error} onRetry={load} /> : null}

          {loading ? <LoadingState label="Loading your businesses" /> : null}

          {!loading && !error && tenants.length === 0 ? (
            <WinCard title="No businesses yet" dot="var(--tavus-atomic-glow-1)">
              <EmptyState
                icon={<Building2 className="w-6 h-6" strokeWidth={2} />}
                title="Start your first business"
                hint="Create a business to connect your Facebook page, import products, and let your AI agent start selling."
                action={
                  <TavusButton onClick={() => setShowCreate(true)}>
                    <Plus className="w-4 h-4" strokeWidth={2.5} /> Create business
                  </TavusButton>
                }
              />
            </WinCard>
          ) : null}

          {!loading && tenants.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              {tenants.map((t) => (
                <TenantCard key={t.id} tenant={t} />
              ))}
            </div>
          ) : null}
        </div>
      </main>
      <Footer />
    </div>
  );
}

function TenantCard({ tenant }: { tenant: TenantWithStats }) {
  const channels = [
    tenant.fb_connected && { icon: Facebook, label: "Facebook", bg: "var(--tavus-bubbletech-4)" },
    tenant.ig_connected && { icon: Instagram, label: "Instagram", bg: "var(--tavus-neon-field-2)", fg: "white" },
    tenant.wa_connected && { icon: WhatsApp, label: "WhatsApp", bg: "var(--tavus-atomic-glow-5)" },
  ].filter(Boolean) as { icon: React.ElementType; label: string; bg: string; fg?: string }[];

  return (
    <Link
      href={`/dashboard/${tenant.id}`}
      onMouseEnter={() => tenantsApi.prefetchOverview(tenant.id)}
      onFocus={() => tenantsApi.prefetchOverview(tenant.id)}
      onTouchStart={() => tenantsApi.prefetchOverview(tenant.id)}
      className="block group relative bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[6px_6px_0_0_var(--tavus-terminal-black)] hover:shadow-[9px_9px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[2px_2px_0_0_var(--tavus-terminal-black)] transition-all overflow-hidden"
    >
      <div className="absolute inset-0 bg-halftone-light opacity-[0.35] pointer-events-none" />
      <div className="win-title-bar relative justify-between">
        <span className="flex items-center gap-2 min-w-0">
          <span className="w-2.5 h-2.5 bg-[var(--tavus-bubbletech-4)] border border-[var(--tavus-terminal-black)] shrink-0" />
          <span className="text-[10px] font-extrabold tracking-[0.18em] uppercase truncate">{tenant.page_name}</span>
        </span>
        <span className="flex gap-1 shrink-0" aria-hidden>
          <span className="w-2.5 h-2.5 border border-[var(--tavus-terminal-black)]" />
          <span className="w-2.5 h-2.5 border border-[var(--tavus-terminal-black)]" />
        </span>
      </div>

      <div className="relative p-5">
        {/* Name + channel chips */}
        <div className="flex items-start justify-between gap-3 mb-4">
          <h3 className="font-serif text-[26px] leading-tight font-normal text-[var(--tavus-terminal-black)]">
            {tenant.page_name}
          </h3>
          {channels.length ? (
            <span className="flex items-center gap-1.5 shrink-0 pt-1">
              {channels.map((c) => (
                <span
                  key={c.label}
                  title={c.label}
                  className="inline-flex items-center justify-center w-6 h-6 border-[2px] border-[var(--tavus-terminal-black)]"
                  style={{ background: c.bg, color: c.fg ?? "var(--tavus-terminal-black)" }}
                >
                  <c.icon className="w-3.5 h-3.5" strokeWidth={2.25} />
                </span>
              ))}
            </span>
          ) : (
            <span className="text-[9px] font-extrabold tracking-[0.16em] uppercase text-[var(--tavus-hardware-gray-8)] border-[1.5px] border-dashed border-[var(--tavus-terminal-black)]/40 px-2 py-1 shrink-0">
              No channels
            </span>
          )}
        </div>

        {/* Live stats — one honest strip */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 mb-4">
          <MiniStat icon={ShoppingBag} label="Orders" value={String(tenant.today_orders ?? 0)} />
          <MiniStat
            icon={DollarSign}
            label="Revenue"
            value={`${Number(tenant.today_revenue ?? 0).toLocaleString()}`}
            unit="EGP"
          />
          <MiniStat icon={MessageCircle} label="Chats" value={String(tenant.active_conversations ?? 0)} />
          <MiniStat icon={Users} label="Customers" value={String(tenant.total_customers ?? 0)} />
        </div>

        <div className="flex items-center justify-between border-t-[2px] border-dashed border-[var(--tavus-terminal-black)]/20 pt-3.5">
          <span className="text-[9px] font-extrabold tracking-[0.18em] uppercase text-[var(--tavus-hardware-gray-8)]">
            Today · live
          </span>
          <span className="inline-flex items-center gap-1.5 text-[10px] font-extrabold tracking-[0.14em] uppercase text-[var(--tavus-terminal-black)] group-hover:gap-2.5 transition-all">
            Open console <ArrowRight className="w-3.5 h-3.5" strokeWidth={2.5} />
          </span>
        </div>
      </div>
    </Link>
  );
}

function MiniStat({
  icon: Icon,
  label,
  value,
  unit,
}: {
  icon: React.ElementType;
  label: string;
  value: string;
  unit?: string;
}) {
  return (
    <div className="bg-[var(--tavus-plastic-1)] border-[2px] border-[var(--tavus-terminal-black)] px-3 py-2.5">
      <div className="flex items-center gap-1.5 mb-1">
        <Icon className="w-3 h-3 text-[var(--tavus-terminal-black)]" strokeWidth={2.5} />
        <span className="text-[8px] font-extrabold tracking-[0.14em] uppercase text-[var(--tavus-hardware-gray-8)]">
          {label}
        </span>
      </div>
      <div className="text-lg leading-none font-extrabold text-[var(--tavus-terminal-black)] tabular-nums">
        {value}
        {unit ? <span className="text-[10px] font-bold ml-0.5">{unit}</span> : null}
      </div>
    </div>
  );
}

function CreateBusinessForm({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [pageName, setPageName] = useState("");
  const [websiteUrl, setWebsiteUrl] = useState("");
  const [businessEmail, setBusinessEmail] = useState("");
  const [businessPhone, setBusinessPhone] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleCreate() {
    if (!pageName.trim()) {
      setError("Page name is required.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await tenantsApi.create({
        page_name: pageName.trim(),
        website_url: websiteUrl.trim() || undefined,
        business_email: businessEmail.trim() || undefined,
        business_phone: businessPhone.trim() || undefined,
      });
      onCreated();
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create business");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mb-8">
      <WinCard
        title="Create new business"
        dot="var(--tavus-signal-green)"
        action={
          <button
            onClick={onClose}
            aria-label="Close"
            className="text-[var(--tavus-terminal-black)] hover:opacity-60 text-sm font-extrabold"
          >
            ✕
          </button>
        }
      >
        <div className="p-6">
          {error ? (
            <div className="mb-4 border-[2.5px] border-[var(--tavus-coral-1)] bg-[var(--tavus-coral-3)]/40 text-[var(--tavus-terminal-black)] px-3 py-2 text-[12px] font-bold">
              {error}
            </div>
          ) : null}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Field label="Page name *">
              <input
                type="text"
                placeholder="My Store"
                value={pageName}
                onChange={(e) => setPageName(e.target.value)}
                className={inputClass}
              />
            </Field>
            <Field label="Website URL">
              <input
                type="url"
                placeholder="https://mystore.com"
                value={websiteUrl}
                onChange={(e) => setWebsiteUrl(e.target.value)}
                className={inputClass}
              />
            </Field>
            <Field label="Business email">
              <input
                type="email"
                placeholder="business@mystore.com"
                value={businessEmail}
                onChange={(e) => setBusinessEmail(e.target.value)}
                className={inputClass}
              />
            </Field>
            <Field label="Business phone">
              <input
                type="tel"
                placeholder="01XXXXXXXXX"
                value={businessPhone}
                onChange={(e) => setBusinessPhone(e.target.value)}
                className={inputClass}
              />
            </Field>
          </div>
          <div className="mt-5 flex items-center gap-3">
            <TavusButton onClick={handleCreate} disabled={loading}>
              {loading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" strokeWidth={2.5} />}
              Create business
            </TavusButton>
            <TavusLink href="/pricing" variant="secondary">
              View plans
            </TavusLink>
          </div>
        </div>
      </WinCard>
    </div>
  );
}
