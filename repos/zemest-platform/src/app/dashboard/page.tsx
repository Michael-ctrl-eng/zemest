"use client";

import { useState } from "react";
import Link from "next/link";
import { Navbar } from "@/components/site/navbar";
import { Footer } from "@/components/site/footer";
import { Plus, ShoppingBag, DollarSign, MessageCircle, Activity, Facebook, Instagram, MessageCircle as WhatsApp } from "lucide-react";

const mockTenants = [
  {
    id: "tnt_001",
    page_name: "Cairo Sneakers Store",
    fb_connected: true,
    ig_connected: true,
    wa_connected: true,
    today_orders: 12,
    today_revenue: 8400,
    month_revenue: 245000,
    total_customers: 1340,
    total_products: 87,
    active_conversations: 5,
    tokens_used: 45000,
    token_quota: 100000,
  },
  {
    id: "tnt_002",
    page_name: "Alexandria Fashion Hub",
    fb_connected: true,
    ig_connected: true,
    wa_connected: false,
    today_orders: 4,
    today_revenue: 3200,
    month_revenue: 89000,
    total_customers: 560,
    total_products: 124,
    active_conversations: 2,
    tokens_used: 12000,
    token_quota: 50000,
  },
];

export default function DashboardHome() {
  const [showCreate, setShowCreate] = useState(false);

  return (
    <div className="min-h-screen bg-grain">
      <Navbar />
      <main className="pt-24 pb-16">
        <div className="mx-auto max-w-[1280px] px-5 sm:px-8">
          {/* Header */}
          <div className="mb-8">
            <div className="inline-flex items-center gap-2 mb-4">
              <span className="w-2 h-2 bg-[var(--tavus-terminal-black)]" />
              <span className="text-[11px] font-bold tracking-[0.2em] uppercase text-[var(--tavus-hardware-gray-8)]">DASHBOARD</span>
              <span className="w-2 h-2 bg-[var(--tavus-terminal-black)]" />
            </div>
            <div className="flex items-center justify-between flex-wrap gap-4">
              <h1 className="font-[var(--font-serif-display)] text-4xl sm:text-5xl font-normal tracking-tight text-[var(--tavus-terminal-black)]">
                Your <span className="serif-italic">businesses</span>
              </h1>
              <button
                onClick={() => setShowCreate(!showCreate)}
                className="inline-flex items-center gap-2 px-5 h-11 border-[3px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-bubbletech-4)] text-[11px] font-extrabold tracking-wider uppercase shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:shadow-[4px_4px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] transition-all"
              >
                <Plus className="w-4 h-4" />
                NEW BUSINESS
              </button>
            </div>
          </div>

          {/* Create form (toggle) */}
          {showCreate && <CreateBusinessForm onClose={() => setShowCreate(false)} />}

          {/* Tenant cards grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            {mockTenants.map((t) => (
              <TenantCard key={t.id} tenant={t} />
            ))}
          </div>
        </div>
      </main>
      <Footer />
    </div>
  );
}

function TenantCard({ tenant }: { tenant: typeof mockTenants[0] }) {
  const tokenPct = Math.min(100, (tenant.tokens_used / tenant.token_quota) * 100);
  return (
    <Link
      href={`/dashboard/${tenant.id}`}
      className="block relative bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[6px_6px_0_0_var(--tavus-terminal-black)] hover:shadow-[8px_8px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[2px_2px_0_0_var(--tavus-terminal-black)] transition-all overflow-hidden"
    >
      {/* Bitmap halftone overlay */}
      <div className="absolute inset-0 bg-halftone-light opacity-10 pointer-events-none" />
      <div className="relative p-5">
        {/* Top row: name + connections */}
        <div className="flex items-start justify-between mb-4">
          <div>
            <h3 className="font-[var(--font-serif-display)] text-2xl font-normal text-[var(--tavus-terminal-black)]">
              {tenant.page_name}
            </h3>
            <div className="flex items-center gap-2 mt-1">
              {tenant.fb_connected && (
                <span className="inline-flex items-center justify-center w-5 h-5 border border-[var(--tavus-terminal-black)] bg-[var(--tavus-bubbletech-4)]">
                  <Facebook className="w-3 h-3" />
                </span>
              )}
              {tenant.ig_connected && (
                <span className="inline-flex items-center justify-center w-5 h-5 border border-[var(--tavus-terminal-black)] bg-[var(--tavus-neon-field-2)] text-white">
                  <Instagram className="w-3 h-3" />
                </span>
              )}
              {tenant.wa_connected && (
                <span className="inline-flex items-center justify-center w-5 h-5 border border-[var(--tavus-terminal-black)] bg-[var(--tavus-atomic-glow-5)]">
                  <WhatsApp className="w-3 h-3" />
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Stats grid */}
        <div className="grid grid-cols-2 gap-2 mb-4">
          <StatBox icon={ShoppingBag} label="TODAY'S ORDERS" value={tenant.today_orders.toString()} />
          <StatBox icon={DollarSign} label="TODAY'S REVENUE" value={`${tenant.today_revenue} EGP`} />
          <StatBox icon={MessageCircle} label="ACTIVE CHATS" value={tenant.active_conversations.toString()} />
          <StatBox icon={Activity} label="CUSTOMERS" value={tenant.total_customers.toString()} />
        </div>

        {/* Token usage bar */}
        <div>
          <div className="flex items-center justify-between text-[10px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)] mb-1">
            <span>TOKEN USAGE</span>
            <span>{tenant.tokens_used.toLocaleString()} / {tenant.token_quota.toLocaleString()}</span>
          </div>
          <div className="h-2 bg-[var(--tavus-plastic-2)] border border-[var(--tavus-terminal-black)] overflow-hidden">
            <div
              className={`h-full ${tokenPct > 80 ? "bg-[var(--tavus-bubbletech-4)]" : "bg-[var(--tavus-neon-field-2)] text-white"}`}
              style={{ width: `${tokenPct}%` }}
            />
          </div>
        </div>
      </div>
    </Link>
  );
}

function StatBox({ icon: Icon, label, value }: { icon: React.ElementType; label: string; value: string }) {
  return (
    <div className="bg-[var(--tavus-plastic-1)] border-2 border-[var(--tavus-terminal-black)] p-2.5">
      <div className="flex items-center gap-1.5 mb-1">
        <Icon className="w-3 h-3 text-[var(--tavus-terminal-black)]" strokeWidth={2} />
        <span className="text-[9px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)]">{label}</span>
      </div>
      <div className="text-sm font-bold text-[var(--tavus-terminal-black)]">{value}</div>
    </div>
  );
}

function CreateBusinessForm({ onClose }: { onClose: () => void }) {
  return (
    <div className="mb-8 relative bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[6px_6px_0_0_var(--tavus-terminal-black)] overflow-hidden">
      <div className="absolute inset-0 bg-halftone-light opacity-10 pointer-events-none" />
      <div className="win-title-bar relative">
        <span className="w-2.5 h-2.5 bg-[var(--tavus-bubbletech-4)] border border-[var(--tavus-terminal-black)]" />
        <span>CREATE NEW BUSINESS</span>
        <button onClick={onClose} className="ml-auto text-[var(--tavus-terminal-black)] hover:opacity-60">X</button>
      </div>
      <div className="relative p-6">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-[10px] font-bold tracking-[0.1em] uppercase text-[var(--tavus-hardware-gray-8)] mb-1.5">PAGE NAME *</label>
            <input type="text" placeholder="My Store" className="w-full h-11 px-3 border-[2px] border-[var(--tavus-terminal-black)] bg-white text-sm outline-none shadow-[2px_2px_0_0_var(--tavus-terminal-black)]" />
          </div>
          <div>
            <label className="block text-[10px] font-bold tracking-[0.1em] uppercase text-[var(--tavus-hardware-gray-8)] mb-1.5">WEBSITE URL</label>
            <input type="url" placeholder="https://mystore.com" className="w-full h-11 px-3 border-[2px] border-[var(--tavus-terminal-black)] bg-white text-sm outline-none shadow-[2px_2px_0_0_var(--tavus-terminal-black)]" />
          </div>
          <div>
            <label className="block text-[10px] font-bold tracking-[0.1em] uppercase text-[var(--tavus-hardware-gray-8)] mb-1.5">BUSINESS EMAIL</label>
            <input type="email" placeholder="business@mystore.com" className="w-full h-11 px-3 border-[2px] border-[var(--tavus-terminal-black)] bg-white text-sm outline-none shadow-[2px_2px_0_0_var(--tavus-terminal-black)]" />
          </div>
          <div>
            <label className="block text-[10px] font-bold tracking-[0.1em] uppercase text-[var(--tavus-hardware-gray-8)] mb-1.5">BUSINESS PHONE</label>
            <input type="tel" placeholder="01XXXXXXXXX" className="w-full h-11 px-3 border-[2px] border-[var(--tavus-terminal-black)] bg-white text-sm outline-none shadow-[2px_2px_0_0_var(--tavus-terminal-black)]" />
          </div>
        </div>
        <button className="mt-5 inline-flex items-center gap-2 px-6 h-11 border-[3px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-bubbletech-4)] text-[11px] font-extrabold tracking-wider uppercase shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:shadow-[4px_4px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] transition-all">
          CREATE BUSINESS
        </button>
      </div>
    </div>
  );
}
