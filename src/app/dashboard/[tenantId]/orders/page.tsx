"use client";

import { useState, useEffect, useCallback, use } from "react";
import { Search, ShoppingCart, AlertTriangle, RefreshCw, Loader2 } from "lucide-react";
import { ordersApi, formatDateTime, egp, type Order } from "@/lib/zemest-api";
import {
  WinCard,
  StatusBadge,
  DashHeader,
  TableShell,
  Th,
  Td,
  Row,
  LoadingState,
  ErrorState,
  EmptyState,
  STATUS_STYLE,
} from "@/components/site/dash";

const ORDER_STATUSES = ["pending", "confirmed", "shipped", "delivered", "cancelled"] as const;

/** Backend order status state machine (probed from the API). */
const ALLOWED_TRANSITIONS: Record<string, string[]> = {
  pending: ["confirmed", "cancelled"],
  confirmed: ["shipped", "cancelled"],
  shipped: ["delivered"],
  delivered: [],
  cancelled: [],
};

export default function OrdersPage({ params }: { params: Promise<{ tenantId: string }> }) {
  const { tenantId } = use(params);
  const [orders, setOrders] = useState<Order[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [updatingId, setUpdatingId] = useState<string | null>(null);
  const [updateError, setUpdateError] = useState<{ orderId: string; message: string } | null>(null);

  const load = useCallback(async (p: number) => {
    setLoading(true);
    setError(null);
    try {
      const res = await ordersApi.list(tenantId, p);
      setOrders(res?.orders ?? []);
      setTotal(res?.total ?? 0);
      setPage(res?.page ?? p);
      setPageSize(res?.page_size ?? 20);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load orders");
    } finally {
      setLoading(false);
    }
  }, [tenantId]);

  useEffect(() => {
    load(1);
  }, [load]);

  async function handleStatusChange(order: Order, status: string) {
    if (status === order.status) return;
    setUpdatingId(order.id);
    setUpdateError(null);
    try {
      await ordersApi.updateStatus(tenantId, order.id, status);
      setOrders((prev) => prev.map((o) => (o.id === order.id ? { ...o, status } : o)));
    } catch (err: unknown) {
      setUpdateError({
        orderId: order.id,
        message: err instanceof Error ? err.message : `Failed to update order ${order.order_number}`,
      });
    } finally {
      setUpdatingId(null);
    }
  }

  const filtered = orders.filter((o) => {
    const q = search.toLowerCase();
    const matchSearch =
      !q || o.order_number.toLowerCase().includes(q) || o.customer_name.toLowerCase().includes(q) || (o.customer_phone || "").includes(q);
    const matchStatus = statusFilter === "all" || o.status === statusFilter;
    return matchSearch && matchStatus;
  });

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="space-y-6">
      {/* Header */}
      <DashHeader
        eyebrow="Orders"
        title="Order"
        tail="queue"
        action={
          <button
            onClick={() => load(page)}
            title="Refresh"
            aria-label="Refresh"
            className="inline-flex items-center justify-center w-11 h-11 border-[3px] border-[var(--tavus-terminal-black)] bg-white shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:shadow-[4px_4px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] transition-all"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} strokeWidth={2.5} />
          </button>
        }
      />

      {/* Error state */}
      {error ? <ErrorState message={error} onRetry={() => load(1)} /> : null}

      {/* Loading state */}
      {loading ? <LoadingState label="Loading orders" /> : null}

      {/* Empty state */}
      {!loading && !error && orders.length === 0 ? (
        <WinCard title="No orders yet" dot="var(--tavus-atomic-glow-1)">
          <EmptyState
            icon={<ShoppingCart className="w-6 h-6" strokeWidth={2} />}
            title="Your first order awaits"
            hint="Orders are created automatically when customers buy through your AI chat agent. Connect a channel and start selling."
          />
        </WinCard>
      ) : null}

      {/* Orders table */}
      {!loading && !error && orders.length > 0 ? (
        <>
          {/* Filters */}
          <div className="flex flex-wrap gap-3">
            <div className="relative flex-1 min-w-[200px]">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--tavus-hardware-gray-8)]" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search by order #, customer or phone..."
                className="w-full h-10 pl-10 pr-3 bg-white border-[2.5px] border-[var(--tavus-terminal-black)] text-sm font-semibold text-[var(--tavus-terminal-black)] placeholder:text-[var(--tavus-hardware-gray-8)]/60 placeholder:font-medium focus:outline-none focus:shadow-[3px_3px_0_0_var(--tavus-terminal-black)] transition-shadow"
              />
            </div>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="h-10 px-3 bg-white border-[2.5px] border-[var(--tavus-terminal-black)] text-sm font-semibold text-[var(--tavus-terminal-black)] cursor-pointer"
            >
              <option value="all">All Status</option>
              {ORDER_STATUSES.map((s) => (
                <option key={s} value={s}>
                  {s.charAt(0).toUpperCase() + s.slice(1)}
                </option>
              ))}
            </select>
          </div>

          {updateError ? (
            <div className="flex items-center gap-3 border-[3px] border-[var(--tavus-coral-1)] bg-[var(--tavus-coral-3)]/40 p-3">
              <AlertTriangle className="w-4 h-4 text-[var(--tavus-terminal-black)] shrink-0" strokeWidth={2.5} />
              <div className="text-xs font-bold text-[var(--tavus-terminal-black)]">{updateError.message}</div>
            </div>
          ) : null}

          <WinCard title="Orders" dot="var(--tavus-bubbletech-4)">
            <TableShell>
              <thead>
                <tr>
                  <Th>Order #</Th>
                  <Th>Customer</Th>
                  <Th>Governorate</Th>
                  <Th className="text-center">Items</Th>
                  <Th>Total</Th>
                  <Th>Status</Th>
                  <Th>Created</Th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((o) => {
                  const itemsCount = o.items?.length ?? 0;
                  const isUpdating = updatingId === o.id;
                  return (
                    <Row key={o.id}>
                      <Td className="font-mono whitespace-nowrap">{o.order_number}</Td>
                      <Td>
                        <div className="font-bold text-[var(--tavus-terminal-black)]">{o.customer_name}</div>
                        <div className="text-[10px] font-mono font-medium text-[var(--tavus-hardware-gray-8)]">{o.customer_phone || "—"}</div>
                      </Td>
                      <Td className="font-semibold text-[var(--tavus-hardware-gray-8)] capitalize whitespace-nowrap">{o.governorate || "—"}</Td>
                      <Td className="text-center font-bold tabular-nums">{itemsCount}</Td>
                      <Td className="font-bold whitespace-nowrap tabular-nums">{egp(o.total)}</Td>
                      <Td>
                        <div className="inline-flex items-center gap-1.5">
                          {isUpdating ? <Loader2 className="w-3 h-3 animate-spin text-[var(--tavus-terminal-black)]" /> : null}
                          {(ALLOWED_TRANSITIONS[o.status] ?? (ORDER_STATUSES as readonly string[])).length > 0 ? (
                            <select
                              value={o.status}
                              onChange={(e) => handleStatusChange(o, e.target.value)}
                              disabled={isUpdating}
                              title="Change order status"
                              className="px-2 py-0.5 text-[9px] font-extrabold tracking-[0.12em] uppercase border-[1.5px] border-[var(--tavus-terminal-black)] outline-none cursor-pointer disabled:opacity-60"
                              style={{
                                background: STATUS_STYLE[o.status]?.bg ?? "var(--tavus-plastic-2)",
                                color: STATUS_STYLE[o.status]?.fg ?? "var(--tavus-terminal-black)",
                              }}
                            >
                              <option value={o.status} className="bg-white text-[var(--tavus-terminal-black)]">
                                {o.status}
                              </option>
                              {(ALLOWED_TRANSITIONS[o.status] ?? []).map((s) => (
                                <option key={s} value={s} className="bg-white text-[var(--tavus-terminal-black)]">
                                  → {s}
                                </option>
                              ))}
                            </select>
                          ) : (
                            <StatusBadge status={o.status} />
                          )}
                        </div>
                        {updateError?.orderId === o.id ? (
                          <div className="text-[9px] font-bold text-[var(--tavus-coral-1)] mt-1 max-w-[140px]">{updateError.message}</div>
                        ) : null}
                      </Td>
                      <Td className="text-[10px] font-medium text-[var(--tavus-hardware-gray-8)] whitespace-nowrap">{formatDateTime(o.created_at)}</Td>
                    </Row>
                  );
                })}
                {filtered.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="p-8 text-center text-sm font-semibold text-[var(--tavus-hardware-gray-8)]">
                      No orders match your filters.
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </TableShell>
            <div className="relative flex items-center justify-between flex-wrap gap-2 px-4 py-3 border-t-[2px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-plastic-1)]">
              <div className="text-[10px] font-bold tracking-[0.14em] uppercase text-[var(--tavus-hardware-gray-8)]">{total} orders total</div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-bold text-[var(--tavus-hardware-gray-8)]">
                  {orders.filter((o) => o.status === "pending").length} pending on this page
                </span>
                <button
                  onClick={() => load(page - 1)}
                  disabled={page <= 1 || loading}
                  className="px-2.5 h-7 border-[2px] border-[var(--tavus-terminal-black)] bg-white text-[10px] font-extrabold tracking-[0.1em] uppercase text-[var(--tavus-terminal-black)] disabled:opacity-40"
                >
                  Prev
                </button>
                <span className="text-[10px] font-bold tabular-nums text-[var(--tavus-terminal-black)]">
                  {page} / {totalPages}
                </span>
                <button
                  onClick={() => load(page + 1)}
                  disabled={page >= totalPages || loading}
                  className="px-2.5 h-7 border-[2px] border-[var(--tavus-terminal-black)] bg-white text-[10px] font-extrabold tracking-[0.1em] uppercase text-[var(--tavus-terminal-black)] disabled:opacity-40"
                >
                  Next
                </button>
              </div>
            </div>
          </WinCard>
        </>
      ) : null}
    </div>
  );
}
