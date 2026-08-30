"use client";

import { useState } from "react";
import { Search, Eye, X, Phone, MapPin, ShoppingBag, DollarSign, MessageCircle, Calendar } from "lucide-react";

interface Customer {
  id: string;
  name: string;
  phone: string;
  governorate: string;
  channel: "facebook" | "instagram" | "whatsapp";
  orders_count: number;
  total_spent: number;
  last_seen: string;
}

interface Order {
  order_number: string;
  total: number;
  status: "pending" | "confirmed" | "shipped" | "delivered" | "cancelled";
  created_at: string;
}

const mockCustomers: Customer[] = [
  { id: "c1", name: "Ahmed Hassan", phone: "01012345678", governorate: "Cairo", channel: "facebook", orders_count: 12, total_spent: 8450, last_seen: "2 min ago" },
  { id: "c2", name: "Sara Mohamed", phone: "01098765432", governorate: "Giza", channel: "instagram", orders_count: 8, total_spent: 6200, last_seen: "1 hour ago" },
  { id: "c3", name: "Omar Khaled", phone: "01155667788", governorate: "Alexandria", channel: "whatsapp", orders_count: 5, total_spent: 4100, last_seen: "3 hours ago" },
  { id: "c4", name: "Fatma Ali", phone: "01233445566", governorate: "Cairo", channel: "facebook", orders_count: 15, total_spent: 12300, last_seen: "1 day ago" },
  { id: "c5", name: "Mahmoud Ibrahim", phone: "01099887766", governorate: "Giza", channel: "instagram", orders_count: 3, total_spent: 1800, last_seen: "2 days ago" },
  { id: "c6", name: "Nour El-Din", phone: "01225554433", governorate: "Alexandria", channel: "whatsapp", orders_count: 7, total_spent: 5400, last_seen: "3 days ago" },
  { id: "c7", name: "Yasmin Adel", phone: "01077889900", governorate: "Cairo", channel: "facebook", orders_count: 21, total_spent: 18750, last_seen: "5 days ago" },
  { id: "c8", name: "Karim Tarek", phone: "01122334455", governorate: "Giza", channel: "instagram", orders_count: 2, total_spent: 950, last_seen: "1 week ago" },
];

const mockOrders: Order[] = [
  { order_number: "ORD-260827-001", total: 850, status: "pending", created_at: "Aug 27, 10:30 AM" },
  { order_number: "ORD-260825-014", total: 1200, status: "delivered", created_at: "Aug 25, 02:15 PM" },
  { order_number: "ORD-260820-008", total: 450, status: "delivered", created_at: "Aug 20, 11:00 AM" },
  { order_number: "ORD-260815-022", total: 2100, status: "delivered", created_at: "Aug 15, 04:45 PM" },
  { order_number: "ORD-260810-003", total: 670, status: "cancelled", created_at: "Aug 10, 09:30 AM" },
];

const channelColors: Record<string, string> = {
  facebook: "var(--tavus-bubbletech-4)",
  instagram: "var(--tavus-neon-field-2)",
  whatsapp: "var(--tavus-atomic-glow-5)",
};

const statusColors: Record<string, string> = {
  pending: "var(--tavus-atomic-glow-5)",
  confirmed: "var(--tavus-frost-4)",
  shipped: "var(--tavus-floppy-fog-1)",
  delivered: "var(--tavus-neon-field-2)",
  cancelled: "var(--tavus-bubbletech-1)",
};

export default function CustomersPage() {
  const [search, setSearch] = useState("");
  const [channelFilter, setChannelFilter] = useState("all");
  const [selected, setSelected] = useState<Customer | null>(null);

  const filtered = mockCustomers.filter((c) => {
    const matchSearch =
      !search ||
      c.name.toLowerCase().includes(search.toLowerCase()) ||
      c.phone.includes(search);
    const matchChannel = channelFilter === "all" || c.channel === channelFilter;
    return matchSearch && matchChannel;
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <div className="inline-flex items-center gap-2 mb-3">
          <span className="w-2 h-2 bg-[var(--tavus-terminal-black)]" />
          <span className="text-[11px] font-bold tracking-[0.2em] uppercase text-[var(--tavus-hardware-gray-8)]">CUSTOMERS</span>
        </div>
        <h1 className="font-[var(--font-serif-display)] text-3xl sm:text-4xl font-normal tracking-tight text-[var(--tavus-terminal-black)]">
          Customer <span className="serif-italic">directory</span>
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
            placeholder="Search by name or phone..."
            className="w-full h-10 pl-10 pr-3 border-2 border-[var(--tavus-terminal-black)] bg-white text-sm outline-none"
          />
        </div>
        <select value={channelFilter} onChange={(e) => setChannelFilter(e.target.value)} className="h-10 px-3 border-2 border-[var(--tavus-terminal-black)] bg-white text-sm font-bold">
          <option value="all">All Channels</option>
          <option value="facebook">Facebook</option>
          <option value="instagram">Instagram</option>
          <option value="whatsapp">WhatsApp</option>
        </select>
      </div>

      {/* Customers table */}
      <div className="relative bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[6px_6px_0_0_var(--tavus-terminal-black)] overflow-hidden">
        <div className="absolute inset-0 bg-halftone-light opacity-10 pointer-events-none" />
        <div className="relative overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-[var(--tavus-terminal-black)] text-white">
              <tr>
                <th className="text-left p-3 font-extrabold tracking-wider uppercase text-[10px]">NAME</th>
                <th className="text-left p-3 font-extrabold tracking-wider uppercase text-[10px]">PHONE</th>
                <th className="text-left p-3 font-extrabold tracking-wider uppercase text-[10px]">GOV</th>
                <th className="text-left p-3 font-extrabold tracking-wider uppercase text-[10px]">CHANNEL</th>
                <th className="text-center p-3 font-extrabold tracking-wider uppercase text-[10px]">ORDERS</th>
                <th className="text-left p-3 font-extrabold tracking-wider uppercase text-[10px]">TOTAL SPENT</th>
                <th className="text-left p-3 font-extrabold tracking-wider uppercase text-[10px]">LAST SEEN</th>
                <th className="text-center p-3 font-extrabold tracking-wider uppercase text-[10px]">ACTIONS</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((c) => (
                <tr key={c.id} className="border-t border-[var(--tavus-terminal-black)]/10 hover:bg-[var(--tavus-plastic-1)]">
                  <td className="p-3 font-bold text-[var(--tavus-terminal-black)]">{c.name}</td>
                  <td className="p-3 font-mono text-[var(--tavus-hardware-gray-8)]">{c.phone}</td>
                  <td className="p-3 text-[var(--tavus-hardware-gray-8)]">{c.governorate}</td>
                  <td className="p-3">
                    <span className="inline-block px-2 py-0.5 text-[9px] font-bold tracking-wider uppercase border border-[var(--tavus-terminal-black)] text-white" style={{ background: channelColors[c.channel] }}>
                      {c.channel}
                    </span>
                  </td>
                  <td className="p-3 text-center text-[var(--tavus-terminal-black)] font-bold">{c.orders_count}</td>
                  <td className="p-3 font-bold text-[var(--tavus-terminal-black)]">{c.total_spent.toLocaleString()} EGP</td>
                  <td className="p-3 text-[10px] text-[var(--tavus-hardware-gray-8)]">{c.last_seen}</td>
                  <td className="p-3">
                    <div className="flex items-center justify-center">
                      <button
                        onClick={() => setSelected(c)}
                        className="inline-flex items-center justify-center w-7 h-7 border border-[var(--tavus-terminal-black)] bg-white hover:bg-[var(--tavus-bubbletech-4)]"
                      >
                        <Eye className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="relative flex items-center justify-between p-3 border-t-2 border-[var(--tavus-terminal-black)] bg-[var(--tavus-plastic-1)]">
          <div className="text-[10px] font-bold text-[var(--tavus-hardware-gray-8)]">{filtered.length} customers</div>
          <div className="text-[10px] text-[var(--tavus-hardware-gray-8)]">Total: {filtered.reduce((a, c) => a + c.total_spent, 0).toLocaleString()} EGP</div>
        </div>
      </div>

      {selected && <CustomerDetailModal customer={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}

function CustomerDetailModal({ customer, onClose }: { customer: Customer; onClose: () => void }) {
  const stats = [
    { label: "ORDERS", value: customer.orders_count.toString(), icon: ShoppingBag, color: "var(--tavus-bubbletech-4)" },
    { label: "TOTAL SPENT", value: `${customer.total_spent.toLocaleString()} EGP`, icon: DollarSign, color: "var(--tavus-neon-field-2)" },
    { label: "AVG ORDER", value: `${Math.round(customer.total_spent / Math.max(1, customer.orders_count))} EGP`, icon: MessageCircle, color: "var(--tavus-atomic-glow-1)" },
    { label: "LAST SEEN", value: customer.last_seen, icon: Calendar, color: "var(--tavus-floppy-fog-3)" },
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[var(--tavus-terminal-black)]/50">
      <div className="relative w-full max-w-2xl bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[8px_8px_0_0_var(--tavus-terminal-black)] overflow-hidden max-h-[90vh] overflow-y-auto">
        <div className="absolute inset-0 bg-halftone-light opacity-10 pointer-events-none" />
        <div className="win-title-bar relative">
          <span className="w-2.5 h-2.5 bg-[var(--tavus-bubbletech-4)] border border-[var(--tavus-terminal-black)]" />
          <span>CUSTOMER PROFILE</span>
          <button onClick={onClose} className="ml-auto inline-flex items-center justify-center w-5 h-5 border border-[var(--tavus-terminal-black)] bg-white">
            <X className="w-3 h-3" />
          </button>
        </div>
        <div className="relative p-5 space-y-5">
          {/* Identity */}
          <div className="flex items-start justify-between flex-wrap gap-3">
            <div>
              <div className="font-[var(--font-serif-display)] text-2xl text-[var(--tavus-terminal-black)]">{customer.name}</div>
              <div className="mt-1 flex flex-wrap items-center gap-3 text-xs text-[var(--tavus-hardware-gray-8)]">
                <span className="inline-flex items-center gap-1"><Phone className="w-3 h-3" />{customer.phone}</span>
                <span className="inline-flex items-center gap-1"><MapPin className="w-3 h-3" />{customer.governorate}</span>
                <span className="inline-block px-2 py-0.5 text-[9px] font-bold tracking-wider uppercase border border-[var(--tavus-terminal-black)] text-white" style={{ background: channelColors[customer.channel] }}>
                  {customer.channel}
                </span>
              </div>
            </div>
          </div>

          {/* Stats grid */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            {stats.map((s) => (
              <div key={s.label} className="relative bg-[var(--tavus-plastic-1)] border-2 border-[var(--tavus-terminal-black)] p-2.5 overflow-hidden">
                <div className="absolute inset-0 bg-halftone-light opacity-10 pointer-events-none" />
                <div className="relative flex items-center gap-1.5 mb-1">
                  <s.icon className="w-3 h-3 text-[var(--tavus-terminal-black)]" strokeWidth={2} />
                  <span className="text-[9px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)]">{s.label}</span>
                </div>
                <div className="relative text-sm font-bold text-[var(--tavus-terminal-black)]">{s.value}</div>
              </div>
            ))}
          </div>

          {/* Order history */}
          <div className="relative bg-white border-2 border-[var(--tavus-terminal-black)] overflow-hidden">
            <div className="win-title-bar relative">
              <span className="w-2.5 h-2.5 bg-[var(--tavus-neon-field-2)] border border-[var(--tavus-terminal-black)]" />
              <span>ORDER HISTORY</span>
            </div>
            <div className="relative divide-y divide-[var(--tavus-terminal-black)]/10">
              {mockOrders.map((o) => (
                <div key={o.order_number} className="flex items-center gap-3 px-4 py-2.5 hover:bg-[var(--tavus-plastic-1)]">
                  <div className="flex-1 min-w-0">
                    <div className="font-mono text-xs text-[var(--tavus-terminal-black)]">{o.order_number}</div>
                    <div className="text-[10px] text-[var(--tavus-hardware-gray-8)]">{o.created_at}</div>
                  </div>
                  <div className="text-sm font-bold text-[var(--tavus-terminal-black)]">{o.total} EGP</div>
                  <span className="inline-block px-2 py-0.5 text-[9px] font-bold tracking-wider uppercase border border-[var(--tavus-terminal-black)] text-white" style={{ background: statusColors[o.status] }}>
                    {o.status}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
