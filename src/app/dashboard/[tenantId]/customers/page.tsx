"use client";

import { useState, useEffect, useCallback, use } from "react";
import { Search, Eye, X, Phone, MapPin, Users, ShoppingBag, DollarSign, MessageCircle, Calendar, RefreshCw } from "lucide-react";
import { customersApi, formatDateTime, egp, toNumber, type Customer } from "@/lib/zemest-api";
import {
  WinCard,
  DashHeader,
  TableShell,
  Th,
  Td,
  Row,
  LoadingState,
  ErrorState,
  EmptyState,
} from "@/components/site/dash";

export default function CustomersPage({ params }: { params: Promise<{ tenantId: string }> }) {
  const { tenantId } = use(params);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<Customer | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await customersApi.list(tenantId);
      setCustomers(res?.customers ?? []);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load customers");
    } finally {
      setLoading(false);
    }
  }, [tenantId]);

  useEffect(() => {
    load();
  }, [load]);

  const filtered = customers.filter((c) => {
    const q = search.toLowerCase();
    const name = (c.name || "").toLowerCase();
    const phone = c.phone || "";
    return !q || name.includes(q) || phone.includes(q);
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <DashHeader
        eyebrow="Customers"
        title="Your"
        tail="customers"
        action={
          <button
            onClick={load}
            title="Refresh"
            aria-label="Refresh"
            className="inline-flex items-center justify-center w-11 h-11 border-[3px] border-[var(--tavus-terminal-black)] bg-white shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:shadow-[4px_4px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] transition-all"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} strokeWidth={2.5} />
          </button>
        }
      />

      {/* Error state */}
      {error ? <ErrorState message={error} onRetry={load} /> : null}

      {/* Loading state */}
      {loading ? <LoadingState label="Loading customers" /> : null}

      {/* Empty state */}
      {!loading && !error && customers.length === 0 ? (
        <WinCard title="No customers yet" dot="var(--tavus-atomic-glow-1)">
          <EmptyState
            icon={<Users className="w-6 h-6" strokeWidth={2} />}
            title="No customers yet"
            hint="Every person who chats with your AI agent or places an order is saved here automatically."
          />
        </WinCard>
      ) : null}

      {/* Customers table */}
      {!loading && !error && customers.length > 0 ? (
        <>
          {/* Search */}
          <div className="relative flex-1 min-w-[200px]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--tavus-hardware-gray-8)]" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by name or phone..."
              className="w-full h-10 pl-10 pr-3 bg-white border-[2.5px] border-[var(--tavus-terminal-black)] text-sm font-semibold text-[var(--tavus-terminal-black)] placeholder:text-[var(--tavus-hardware-gray-8)]/60 placeholder:font-medium focus:outline-none focus:shadow-[3px_3px_0_0_var(--tavus-terminal-black)] transition-shadow"
            />
          </div>

          <WinCard title="Customers" dot="var(--tavus-bubbletech-4)">
            <TableShell>
              <thead>
                <tr>
                  <Th>Name</Th>
                  <Th>Phone</Th>
                  <Th>Location</Th>
                  <Th className="text-center">Orders</Th>
                  <Th>Total spent</Th>
                  <Th>Joined</Th>
                  <Th className="text-center">View</Th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((c) => (
                  <Row key={c.id}>
                    <Td className="font-bold">{c.name || "Unknown"}</Td>
                    <Td className="font-mono font-medium text-[var(--tavus-hardware-gray-8)]">{c.phone || "—"}</Td>
                    <Td className="font-semibold text-[var(--tavus-hardware-gray-8)]">
                      <span className="capitalize">{c.governorate || "—"}</span>
                      {c.city ? <span className="text-[10px] block">{c.city}</span> : null}
                    </Td>
                    <Td className="text-center font-bold tabular-nums">{toNumber(c.orders_count)}</Td>
                    <Td className="font-bold whitespace-nowrap tabular-nums">{egp(c.total_spent)}</Td>
                    <Td className="text-[10px] font-medium text-[var(--tavus-hardware-gray-8)] whitespace-nowrap">{formatDateTime(c.created_at)}</Td>
                    <Td>
                      <div className="flex items-center justify-center">
                        <button
                          onClick={() => setSelected(c)}
                          title="View profile"
                          aria-label="View profile"
                          className="inline-flex items-center justify-center w-8 h-8 border-[2px] border-[var(--tavus-terminal-black)] bg-white hover:bg-[var(--tavus-bubbletech-4)] transition-colors"
                        >
                          <Eye className="w-3.5 h-3.5" strokeWidth={2.25} />
                        </button>
                      </div>
                    </Td>
                  </Row>
                ))}
                {filtered.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="p-8 text-center text-sm font-semibold text-[var(--tavus-hardware-gray-8)]">
                      No customers match your search.
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </TableShell>
            <div className="relative flex items-center justify-between flex-wrap gap-2 px-4 py-3 border-t-[2px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-plastic-1)]">
              <div className="text-[10px] font-bold tracking-[0.14em] uppercase text-[var(--tavus-hardware-gray-8)]">{filtered.length} customers</div>
              <div className="text-[10px] font-bold text-[var(--tavus-hardware-gray-8)] tabular-nums">
                Total spent: {filtered.reduce((acc, c) => acc + toNumber(c.total_spent), 0).toLocaleString("en-EG", { maximumFractionDigits: 2 })} EGP
              </div>
            </div>
          </WinCard>
        </>
      ) : null}

      {selected ? <CustomerDetailModal customer={selected} onClose={() => setSelected(null)} /> : null}
    </div>
  );
}

function CustomerDetailModal({ customer, onClose }: { customer: Customer; onClose: () => void }) {
  const ordersCount = toNumber(customer.orders_count);
  const totalSpent = toNumber(customer.total_spent);
  const stats = [
    { label: "ORDERS", value: String(ordersCount), icon: ShoppingBag, color: "var(--tavus-bubbletech-4)" },
    { label: "TOTAL SPENT", value: egp(totalSpent), icon: DollarSign, color: "var(--tavus-neon-field-2)" },
    { label: "AVG ORDER", value: ordersCount > 0 ? egp(totalSpent / ordersCount) : "—", icon: MessageCircle, color: "var(--tavus-atomic-glow-1)" },
    { label: "CONVERSATIONS", value: String(toNumber(customer.conversations_count)), icon: Calendar, color: "var(--tavus-floppy-fog-3)" },
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[var(--tavus-terminal-black)]/50">
      <div className="relative w-full max-w-2xl border-[3px] border-[var(--tavus-terminal-black)] shadow-[8px_8px_0_0_var(--tavus-terminal-black)] bg-white overflow-hidden max-h-[90vh] overflow-y-auto scrollbar-thin">
        <div className="absolute inset-0 bg-halftone-light opacity-[0.35] pointer-events-none" />
        <div className="win-title-bar relative justify-between">
          <span className="flex items-center gap-2 min-w-0">
            <span className="w-2.5 h-2.5 bg-[var(--tavus-bubbletech-4)] border border-[var(--tavus-terminal-black)] shrink-0" />
            <span className="truncate">Customer profile</span>
          </span>
          <button
            onClick={onClose}
            aria-label="Close"
            title="Close"
            className="shrink-0 inline-flex items-center justify-center w-6 h-6 border-[2px] border-[var(--tavus-terminal-black)] bg-white text-[var(--tavus-terminal-black)] hover:bg-[var(--tavus-coral-3)]/50 transition-colors"
          >
            <X className="w-3.5 h-3.5" strokeWidth={2.5} />
          </button>
        </div>
        <div className="relative p-5 space-y-5">
          {/* Identity */}
          <div className="flex items-start justify-between flex-wrap gap-3">
            <div>
              <div className="font-serif text-2xl text-[var(--tavus-terminal-black)]">{customer.name || "Unknown"}</div>
              <div className="mt-1 flex flex-wrap items-center gap-3 text-xs text-[var(--tavus-hardware-gray-8)]">
                {customer.phone ? (
                  <span className="inline-flex items-center gap-1">
                    <Phone className="w-3 h-3" strokeWidth={2.25} />
                    <span className="font-mono">{customer.phone}</span>
                  </span>
                ) : null}
                {customer.governorate || customer.city ? (
                  <span className="inline-flex items-center gap-1 capitalize">
                    <MapPin className="w-3 h-3" strokeWidth={2.25} />
                    {[customer.governorate, customer.city].filter(Boolean).join(", ")}
                  </span>
                ) : null}
              </div>
              {customer.address_detail ? (
                <div className="mt-1 text-[11px] font-medium text-[var(--tavus-hardware-gray-8)]">{customer.address_detail}</div>
              ) : null}
            </div>
          </div>

          {/* Stats grid */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            {stats.map((s) => (
              <div key={s.label} className="relative bg-[var(--tavus-plastic-1)] border-[2px] border-[var(--tavus-terminal-black)] p-2.5 overflow-hidden">
                <div className="absolute inset-0 bg-halftone-light opacity-[0.35] pointer-events-none" />
                <div className="relative flex items-center gap-1.5 mb-1">
                  <s.icon className="w-3 h-3 text-[var(--tavus-terminal-black)]" strokeWidth={2} />
                  <span className="text-[9px] font-bold tracking-[0.14em] uppercase text-[var(--tavus-hardware-gray-8)]">{s.label}</span>
                </div>
                <div className="relative text-sm font-bold text-[var(--tavus-terminal-black)] tabular-nums">{s.value}</div>
              </div>
            ))}
          </div>

          {/* Meta */}
          <WinCard title="Details" dot="var(--tavus-neon-field-2)" className="shadow-[4px_4px_0_0_var(--tavus-terminal-black)]">
            <div className="relative divide-y divide-[var(--tavus-terminal-black)]/10 text-sm">
              <DetailRow label="CUSTOMER SINCE" value={formatDateTime(customer.created_at)} />
              <DetailRow label="AREA" value={customer.area || "—"} />
              <DetailRow label="ADDRESS" value={customer.address_detail || "—"} />
            </div>
          </WinCard>
        </div>
      </div>
    </div>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 px-4 py-2.5">
      <span className="text-[10px] font-bold tracking-[0.14em] uppercase text-[var(--tavus-hardware-gray-8)]">{label}</span>
      <span className="text-[var(--tavus-terminal-black)] font-bold text-right">{value}</span>
    </div>
  );
}
