"use client";

import { ShoppingBag, DollarSign, MessageCircle, Activity, ArrowRight } from "lucide-react";

const stats = [
  { label: "TODAY'S ORDERS", value: "12", icon: ShoppingBag, color: "var(--tavus-bubbletech-4)" },
  { label: "TODAY'S REVENUE", value: "8,400 EGP", icon: DollarSign, color: "var(--tavus-neon-field-2)" },
  { label: "ACTIVE CONVERSATIONS", value: "5", icon: MessageCircle, color: "var(--tavus-atomic-glow-1)" },
  { label: "TOKEN USAGE", value: "45k / 100k", icon: Activity, color: "var(--tavus-floppy-fog-3)" },
];

const recentOrders = [
  { order_number: "ORD-260827-001", customer_name: "Ahmed Hassan", total: 850, status: "pending", created_at: "2 min ago" },
  { order_number: "ORD-260827-002", customer_name: "Sara Mohamed", total: 1200, status: "confirmed", created_at: "15 min ago" },
  { order_number: "ORD-260827-003", customer_name: "Omar Khaled", total: 450, status: "shipped", created_at: "1 hour ago" },
  { order_number: "ORD-260827-004", customer_name: "Fatma Ali", total: 2100, status: "delivered", created_at: "3 hours ago" },
  { order_number: "ORD-260827-005", customer_name: "Mahmoud Ibrahim", total: 670, status: "cancelled", created_at: "5 hours ago" },
];

const topProducts = [
  { product_name: "Air Max 90 - White", quantity_sold: 24, revenue: 20400 },
  { product_name: "Air Force 1 - Black", quantity_sold: 18, revenue: 14400 },
  { product_name: "Nike Air Jordan 1", quantity_sold: 12, revenue: 36000 },
  { product_name: "Adidas Stan Smith", quantity_sold: 9, revenue: 7200 },
  { product_name: "Puma Suede Classic", quantity_sold: 7, revenue: 4200 },
];

const statusColors: Record<string, string> = {
  pending: "var(--tavus-atomic-glow-5)",
  confirmed: "var(--tavus-frost-4)",
  shipped: "var(--tavus-floppy-fog-1)",
  delivered: "var(--tavus-neon-field-2)",
  cancelled: "var(--tavus-bubbletech-1)",
};

export default function OverviewPage({ params }: { params: { tenantId: string } }) {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <div className="inline-flex items-center gap-2 mb-3">
          <span className="w-2 h-2 bg-[var(--tavus-terminal-black)]" />
          <span className="text-[11px] font-bold tracking-[0.2em] uppercase text-[var(--tavus-hardware-gray-8)]">OVERVIEW</span>
        </div>
        <h1 className="font-[var(--font-serif-display)] text-3xl sm:text-4xl font-normal tracking-tight text-[var(--tavus-terminal-black)]">
          Cairo Sneakers <span className="serif-italic">Store</span>
        </h1>
      </div>

      {/* Stats tiles */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {stats.map((s) => (
          <div key={s.label} className="relative bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[4px_4px_0_0_var(--tavus-terminal-black)] p-4 overflow-hidden">
            <div className="absolute inset-0 bg-halftone-light opacity-10 pointer-events-none" />
            <div className="relative flex items-center justify-between mb-2">
              <s.icon className="w-5 h-5" strokeWidth={2} style={{ color: "var(--tavus-terminal-black)" }} />
              <span className="w-3 h-3 border border-[var(--tavus-terminal-black)] text-white" style={{ background: s.color }} />
            </div>
            <div className="relative text-lg font-bold text-[var(--tavus-terminal-black)]">{s.value}</div>
            <div className="relative text-[9px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)] mt-0.5">{s.label}</div>
          </div>
        ))}
      </div>

      {/* Recent orders + Top products */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Recent orders */}
        <div className="relative bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[6px_6px_0_0_var(--tavus-terminal-black)] overflow-hidden">
          <div className="absolute inset-0 bg-halftone-light opacity-10 pointer-events-none" />
          <div className="win-title-bar relative">
            <span className="w-2.5 h-2.5 bg-[var(--tavus-bubbletech-4)] border border-[var(--tavus-terminal-black)]" />
            <span>RECENT ORDERS</span>
          </div>
          <div className="relative divide-y divide-[var(--tavus-terminal-black)]/10">
            {recentOrders.map((o) => (
              <div key={o.order_number} className="flex items-center gap-3 px-4 py-3 hover:bg-[var(--tavus-plastic-1)] transition-colors">
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-bold text-[var(--tavus-terminal-black)] truncate">{o.customer_name}</div>
                  <div className="text-[10px] font-mono text-[var(--tavus-hardware-gray-8)]">{o.order_number}</div>
                </div>
                <div className="text-sm font-bold text-[var(--tavus-terminal-black)]">{o.total} EGP</div>
                <div className="w-20 text-center">
                  <span className="inline-block px-2 py-0.5 text-[9px] font-bold tracking-wider uppercase border border-[var(--tavus-terminal-black)] text-white" style={{ background: statusColors[o.status] }}>
                    {o.status}
                  </span>
                </div>
                <div className="text-[10px] text-[var(--tavus-hardware-gray-8)] w-16 text-right">{o.created_at}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Top products */}
        <div className="relative bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[6px_6px_0_0_var(--tavus-terminal-black)] overflow-hidden">
          <div className="absolute inset-0 bg-halftone-light opacity-10 pointer-events-none" />
          <div className="win-title-bar relative">
            <span className="w-2.5 h-2.5 bg-[var(--tavus-neon-field-2)] border border-[var(--tavus-terminal-black)]" />
            <span>TOP PRODUCTS</span>
          </div>
          <div className="relative divide-y divide-[var(--tavus-terminal-black)]/10">
            {topProducts.map((p, i) => (
              <div key={p.product_name} className="flex items-center gap-3 px-4 py-3 hover:bg-[var(--tavus-plastic-1)] transition-colors">
                <div className="font-[var(--font-serif-display)] text-2xl font-bold text-[var(--tavus-terminal-black)]/20 w-8">{i + 1}</div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-bold text-[var(--tavus-terminal-black)] truncate">{p.product_name}</div>
                  <div className="text-[10px] text-[var(--tavus-hardware-gray-8)]">{p.quantity_sold} sold</div>
                </div>
                <div className="text-sm font-bold text-[var(--tavus-terminal-black)]">{p.revenue.toLocaleString()} EGP</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Quick actions */}
      <div className="flex flex-wrap gap-3">
        <a href={`/dashboard/${params.tenantId}/products`} className="inline-flex items-center gap-2 px-4 h-10 border-[3px] border-[var(--tavus-terminal-black)] bg-white text-[11px] font-extrabold tracking-wider uppercase shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:shadow-[4px_4px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] transition-all">
          ADD PRODUCT
          <ArrowRight className="w-3.5 h-3.5" />
        </a>
        <a href={`/dashboard/${params.tenantId}/chat`} className="inline-flex items-center gap-2 px-4 h-10 border-[3px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-neon-field-2)] text-white text-[11px] font-extrabold tracking-wider uppercase shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:shadow-[4px_4px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] transition-all">
          TEST CHAT
          <ArrowRight className="w-3.5 h-3.5" />
        </a>
        <a href={`/dashboard/${params.tenantId}/style`} className="inline-flex items-center gap-2 px-4 h-10 border-[3px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-bubbletech-4)] text-[11px] font-extrabold tracking-wider uppercase shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:shadow-[4px_4px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x=1 active:translate-y-1 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] transition-all">
          IMPORT CHAT HISTORY
          <ArrowRight className="w-3.5 h-3.5" />
        </a>
      </div>
    </div>
  );
}
