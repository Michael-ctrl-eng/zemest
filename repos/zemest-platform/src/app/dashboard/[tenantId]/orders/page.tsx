"use client";

import { useState } from "react";
import { Plus, Search, Eye, RefreshCw } from "lucide-react";

const mockOrders = [
  { order_number: "ORD-260827-001", customer_name: "Ahmed Hassan", customer_phone: "01012345678", governorate: "Cairo", items_count: 2, total: 850, payment_method: "cod", status: "pending", api_status: "not_configured", created_at: "Aug 27, 10:30 AM" },
  { order_number: "ORD-260827-002", customer_name: "Sara Mohamed", customer_phone: "01098765432", governorate: "Giza", items_count: 1, total: 1200, payment_method: "vodafone_cash", status: "confirmed", api_status: "success", created_at: "Aug 27, 09:15 AM" },
  { order_number: "ORD-260827-003", customer_name: "Omar Khaled", customer_phone: "01155667788", governorate: "Alexandria", items_count: 3, total: 450, payment_method: "instapay", status: "shipped", api_status: "success", created_at: "Aug 26, 04:20 PM" },
  { order_number: "ORD-260827-004", customer_name: "Fatma Ali", customer_phone: "01233445566", governorate: "Cairo", items_count: 1, total: 2100, payment_method: "fawry", status: "delivered", api_status: "success", created_at: "Aug 26, 01:00 PM" },
  { order_number: "ORD-260827-005", customer_name: "Mahmoud Ibrahim", customer_phone: "01099887766", governorate: "Giza", items_count: 2, total: 670, payment_method: "cod", status: "cancelled", api_status: "failed", created_at: "Aug 25, 06:45 PM" },
];

const statusColors: Record<string, string> = {
  pending: "var(--tavus-atomic-glow-5)",
  confirmed: "var(--tavus-frost-4)",
  shipped: "var(--tavus-floppy-fog-1)",
  delivered: "var(--tavus-neon-field-2)",
  cancelled: "var(--tavus-bubbletech-1)",
};

const apiColors: Record<string, string> = {
  not_configured: "var(--tavus-plastic-2)",
  pending: "var(--tavus-atomic-glow-5)",
  success: "var(--tavus-neon-field-2)",
  failed: "var(--tavus-bubbletech-4)",
};

export default function OrdersPage() {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [showCreate, setShowCreate] = useState(false);

  const filtered = mockOrders.filter((o) => {
    const matchSearch = !search || o.order_number.toLowerCase().includes(search.toLowerCase()) || o.customer_name.toLowerCase().includes(search.toLowerCase());
    const matchStatus = statusFilter === "all" || o.status === statusFilter;
    return matchSearch && matchStatus;
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <div className="inline-flex items-center gap-2 mb-3">
            <span className="w-2 h-2 bg-[var(--tavus-terminal-black)]" />
            <span className="text-[11px] font-bold tracking-[0.2em] uppercase text-[var(--tavus-hardware-gray-8)]">ORDERS</span>
          </div>
          <h1 className="font-[var(--font-serif-display)] text-3xl sm:text-4xl font-normal tracking-tight text-[var(--tavus-terminal-black)]">
            Order <span className="serif-italic">management</span>
          </h1>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="inline-flex items-center gap-2 px-4 h-10 border-[3px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-bubbletech-4)] text-[11px] font-extrabold tracking-wider uppercase shadow-[2px_2px_0_0_var(--tavus-terminal-black)] hover:shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] transition-all"
        >
          <Plus className="w-4 h-4" />
          NEW ORDER
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--tavus-hardware-gray-8)]" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by order # or customer..."
            className="w-full h-10 pl-10 pr-3 border-2 border-[var(--tavus-terminal-black)] bg-white text-sm outline-none"
          />
        </div>
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="h-10 px-3 border-2 border-[var(--tavus-terminal-black)] bg-white text-sm font-bold">
          <option value="all">All Status</option>
          <option value="pending">Pending</option>
          <option value="confirmed">Confirmed</option>
          <option value="shipped">Shipped</option>
          <option value="delivered">Delivered</option>
          <option value="cancelled">Cancelled</option>
        </select>
      </div>

      {/* Orders table */}
      <div className="relative bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[6px_6px_0_0_var(--tavus-terminal-black)] overflow-hidden">
        <div className="absolute inset-0 bg-halftone-light opacity-10 pointer-events-none" />
        <div className="relative overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-[var(--tavus-terminal-black)] text-white">
              <tr>
                <th className="text-left p-3 font-extrabold tracking-wider uppercase text-[10px]">ORDER #</th>
                <th className="text-left p-3 font-extrabold tracking-wider uppercase text-[10px]">CUSTOMER</th>
                <th className="text-left p-3 font-extrabold tracking-wider uppercase text-[10px]">GOV</th>
                <th className="text-center p-3 font-extrabold tracking-wider uppercase text-[10px]">ITEMS</th>
                <th className="text-left p-3 font-extrabold tracking-wider uppercase text-[10px]">TOTAL</th>
                <th className="text-left p-3 font-extrabold tracking-wider uppercase text-[10px]">PAYMENT</th>
                <th className="text-left p-3 font-extrabold tracking-wider uppercase text-[10px]">STATUS</th>
                <th className="text-left p-3 font-extrabold tracking-wider uppercase text-[10px]">API</th>
                <th className="text-center p-3 font-extrabold tracking-wider uppercase text-[10px]">ACTIONS</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((o) => (
                <tr key={o.order_number} className="border-t border-[var(--tavus-terminal-black)]/10 hover:bg-[var(--tavus-plastic-1)]">
                  <td className="p-3 font-mono text-[var(--tavus-terminal-black)]">{o.order_number}</td>
                  <td className="p-3">
                    <div className="font-bold text-[var(--tavus-terminal-black)]">{o.customer_name}</div>
                    <div className="text-[10px] text-[var(--tavus-hardware-gray-8)]">{o.customer_phone}</div>
                  </td>
                  <td className="p-3 text-[var(--tavus-hardware-gray-8)]">{o.governorate}</td>
                  <td className="p-3 text-center text-[var(--tavus-terminal-black)]">{o.items_count}</td>
                  <td className="p-3 font-bold text-[var(--tavus-terminal-black)]">{o.total} EGP</td>
                  <td className="p-3">
                    <span className="inline-block px-1.5 py-0.5 text-[9px] font-bold uppercase border border-[var(--tavus-terminal-black)] bg-[var(--tavus-plastic-2)]">
                      {o.payment_method.replace("_", " ")}
                    </span>
                  </td>
                  <td className="p-3">
                    <span className="inline-block px-2 py-0.5 text-[9px] font-bold tracking-wider uppercase border border-[var(--tavus-terminal-black)] text-white" style={{ background: statusColors[o.status] }}>
                      {o.status}
                    </span>
                  </td>
                  <td className="p-3">
                    <span className="inline-block px-1.5 py-0.5 text-[8px] font-bold uppercase border border-[var(--tavus-terminal-black)] text-white" style={{ background: apiColors[o.api_status] }}>
                      {o.api_status.replace("_", " ")}
                    </span>
                  </td>
                  <td className="p-3">
                    <div className="flex items-center justify-center gap-1">
                      <button className="inline-flex items-center justify-center w-7 h-7 border border-[var(--tavus-terminal-black)] bg-white">
                        <Eye className="w-3.5 h-3.5" />
                      </button>
                      <button className="inline-flex items-center justify-center w-7 h-7 border border-[var(--tavus-terminal-black)] bg-white">
                        <RefreshCw className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="relative flex items-center justify-between p-3 border-t-2 border-[var(--tavus-terminal-black)] bg-[var(--tavus-plastic-1)]">
          <div className="text-[10px] font-bold text-[var(--tavus-hardware-gray-8)]">{filtered.length} orders</div>
          <div className="text-[10px] text-[var(--tavus-hardware-gray-8)]">{filtered.filter(o => o.status === "pending").length} pending</div>
        </div>
      </div>

      {showCreate && <CreateOrderModal onClose={() => setShowCreate(false)} />}
    </div>
  );
}

function CreateOrderModal({ onClose }: { onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[var(--tavus-terminal-black)]/50">
      <div className="relative w-full max-w-lg bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[8px_8px_0_0_var(--tavus-terminal-black)] overflow-hidden max-h-[90vh] overflow-y-auto">
        <div className="absolute inset-0 bg-halftone-light opacity-10 pointer-events-none" />
        <div className="win-title-bar relative">
          <span className="w-2.5 h-2.5 bg-[var(--tavus-bubbletech-4)] border border-[var(--tavus-terminal-black)]" />
          <span>CREATE ORDER</span>
          <button onClick={onClose} className="ml-auto">X</button>
        </div>
        <div className="relative p-5 space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-[10px] font-bold uppercase text-[var(--tavus-hardware-gray-8)] mb-1">CUSTOMER NAME *</label>
              <input type="text" className="w-full h-10 px-2 border-2 border-[var(--tavus-terminal-black)] bg-white text-sm outline-none" />
            </div>
            <div>
              <label className="block text-[10px] font-bold uppercase text-[var(--tavus-hardware-gray-8)] mb-1">PHONE *</label>
              <input type="tel" placeholder="01XXXXXXXXX" className="w-full h-10 px-2 border-2 border-[var(--tavus-terminal-black)] bg-white text-sm outline-none" />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-[10px] font-bold uppercase text-[var(--tavus-hardware-gray-8)] mb-1">GOVERNORATE *</label>
              <select className="w-full h-10 px-2 border-2 border-[var(--tavus-terminal-black)] bg-white text-sm outline-none">
                <option value="">Select...</option>
                <option value="cairo">Cairo</option>
                <option value="giza">Giza</option>
                <option value="alexandria">Alexandria</option>
              </select>
            </div>
            <div>
              <label className="block text-[10px] font-bold uppercase text-[var(--tavus-hardware-gray-8)] mb-1">CITY *</label>
              <select className="w-full h-10 px-2 border-2 border-[var(--tavus-terminal-black)] bg-white text-sm outline-none">
                <option value="">Select...</option>
              </select>
            </div>
          </div>
          <div>
            <label className="block text-[10px] font-bold uppercase text-[var(--tavus-hardware-gray-8)] mb-1">ADDRESS *</label>
            <textarea rows={2} className="w-full p-2 border-2 border-[var(--tavus-terminal-black)] bg-white text-sm outline-none resize-none" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-[10px] font-bold uppercase text-[var(--tavus-hardware-gray-8)] mb-1">PAYMENT METHOD</label>
              <select className="w-full h-10 px-2 border-2 border-[var(--tavus-terminal-black)] bg-white text-sm outline-none">
                <option value="cod">Cash on Delivery</option>
                <option value="vodafone_cash">Vodafone Cash</option>
                <option value="instapay">InstaPay</option>
                <option value="fawry">Fawry</option>
              </select>
            </div>
            <div>
              <label className="block text-[10px] font-bold uppercase text-[var(--tavus-hardware-gray-8)] mb-1">DELIVERY CHARGE</label>
              <input type="number" placeholder="auto" className="w-full h-10 px-2 border-2 border-[var(--tavus-terminal-black)] bg-white text-sm outline-none" />
            </div>
          </div>
          {/* Items */}
          <div>
            <label className="block text-[10px] font-bold uppercase text-[var(--tavus-hardware-gray-8)] mb-1">ITEMS</label>
            <div className="space-y-2">
              <div className="flex gap-2">
                <select className="flex-1 h-9 px-2 border-2 border-[var(--tavus-terminal-black)] bg-white text-sm">
                  <option>Select product...</option>
                  <option>Air Max 90 - White (850 EGP)</option>
                  <option>Air Force 1 - Black (1200 EGP)</option>
                </select>
                <input type="number" placeholder="QTY" defaultValue="1" className="w-16 h-9 px-2 border-2 border-[var(--tavus-terminal-black)] bg-white text-sm" />
                <button className="w-9 h-9 border-2 border-[var(--tavus-terminal-black)] bg-white text-sm">X</button>
              </div>
              <button className="text-[11px] font-bold uppercase text-[var(--tavus-terminal-black)] underline">+ ADD ITEM</button>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-full inline-flex items-center justify-center gap-2 px-5 h-11 border-[3px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-bubbletech-4)] text-[11px] font-extrabold tracking-wider uppercase shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:shadow-[4px_4px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] transition-all"
          >
            CREATE ORDER
          </button>
        </div>
      </div>
    </div>
  );
}
