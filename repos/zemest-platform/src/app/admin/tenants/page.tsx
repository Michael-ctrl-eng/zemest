"use client";

import { useState } from "react";
import { Search, Facebook, Instagram, MessageCircle as WhatsApp, Package, ShoppingCart, Users as UsersIcon, Coins, Eye } from "lucide-react";

interface Tenant {
  id: string;
  page_name: string;
  owner_email: string;
  fb_page_id: string;
  ig_user_id: string;
  wa_phone_id: string;
  is_active: boolean;
  products_count: number;
  orders_count: number;
  customers_count: number;
  tokens_used: number;
}

const mockTenants: Tenant[] = [
  { id: "tnt_001", page_name: "Cairo Sneakers Store", owner_email: "owner@cairosneakers.com", fb_page_id: "10482937106", ig_user_id: "17841400823910284", wa_phone_id: "1029384756", is_active: true, products_count: 87, orders_count: 1842, customers_count: 1340, tokens_used: 45000 },
  { id: "tnt_002", page_name: "Alexandria Fashion Hub", owner_email: "admin@alexhub.com", fb_page_id: "1029384810", ig_user_id: "17841400823910392", wa_phone_id: "—", is_active: true, products_count: 124, orders_count: 980, customers_count: 560, tokens_used: 12000 },
  { id: "tnt_003", page_name: "Cairo Cosmetics", owner_email: "info@cairoke.com", fb_page_id: "1029385023", ig_user_id: "17841400823910456", wa_phone_id: "1029384799", is_active: false, products_count: 56, orders_count: 312, customers_count: 240, tokens_used: 8400 },
  { id: "tnt_004", page_name: "Giza Gadget Store", owner_email: "support@gizagadgets.com", fb_page_id: "1029385147", ig_user_id: "—", wa_phone_id: "1029384822", is_active: true, products_count: 218, orders_count: 4210, customers_count: 2890, tokens_used: 89000 },
  { id: "tnt_005", page_name: "Delta Books", owner_email: "hello@deltabooks.com", fb_page_id: "1029385268", ig_user_id: "17841400823910567", wa_phone_id: "—", is_active: true, products_count: 410, orders_count: 1240, customers_count: 720, tokens_used: 22000 },
  { id: "tnt_006", page_name: "Sinai Spices", owner_email: "owner@sinaispices.com", fb_page_id: "1029385390", ig_user_id: "17841400823910678", wa_phone_id: "1029384855", is_active: true, products_count: 32, orders_count: 410, customers_count: 180, tokens_used: 6700 },
];

export default function AdminTenantsPage() {
  const [search, setSearch] = useState("");
  const [activeFilter, setActiveFilter] = useState("all");

  const filtered = mockTenants.filter((t) => {
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
                    <span className="inline-flex items-center gap-1"><Package className="w-3 h-3" />{t.products_count}</span>
                  </td>
                  <td className="p-3 text-center font-bold text-[var(--tavus-terminal-black)]">
                    <span className="inline-flex items-center gap-1"><ShoppingCart className="w-3 h-3" />{t.orders_count.toLocaleString()}</span>
                  </td>
                  <td className="p-3 text-center font-bold text-[var(--tavus-terminal-black)]">
                    <span className="inline-flex items-center gap-1"><UsersIcon className="w-3 h-3" />{t.customers_count.toLocaleString()}</span>
                  </td>
                  <td className="p-3 text-center font-bold text-[var(--tavus-terminal-black)]">
                    <span className="inline-flex items-center gap-1"><Coins className="w-3 h-3" />{t.tokens_used.toLocaleString()}</span>
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
            </tbody>
          </table>
        </div>
        <div className="relative flex items-center justify-between p-3 border-t-2 border-[var(--tavus-terminal-black)] bg-[var(--tavus-plastic-1)]">
          <div className="text-[10px] font-bold text-[var(--tavus-hardware-gray-8)]">{filtered.length} tenants</div>
          <div className="text-[10px] text-[var(--tavus-hardware-gray-8)]">{filtered.filter((t) => t.is_active).length} active</div>
        </div>
      </div>
    </div>
  );
}
