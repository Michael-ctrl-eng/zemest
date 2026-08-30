"use client";

import { useState } from "react";
import { ChevronDown, Store, Truck, CreditCard, Facebook, Instagram, MessageCircle as WhatsApp, Code, BookOpen, UserCircle, AlertTriangle } from "lucide-react";

const sections = [
  { id: "business", label: "BUSINESS SETTINGS", icon: Store, color: "var(--tavus-bubbletech-4)" },
  { id: "delivery", label: "DELIVERY SETTINGS", icon: Truck, color: "var(--tavus-neon-field-2)" },
  { id: "payment", label: "PAYMENT METHODS", icon: CreditCard, color: "var(--tavus-atomic-glow-1)" },
  { id: "facebook", label: "FACEBOOK INTEGRATION", icon: Facebook, color: "var(--tavus-bubbletech-4)" },
  { id: "instagram", label: "INSTAGRAM INTEGRATION", icon: Instagram, color: "var(--tavus-neon-field-2)" },
  { id: "whatsapp", label: "WHATSAPP INTEGRATION", icon: WhatsApp, color: "var(--tavus-atomic-glow-5)" },
  { id: "order_api", label: "ORDER API CONFIG", icon: Code, color: "var(--tavus-floppy-fog-3)" },
  { id: "knowledge", label: "KNOWLEDGE BASE INFO", icon: BookOpen, color: "var(--tavus-frost-4)" },
  { id: "owner_chat", label: "OWNER CHAT SETTINGS", icon: UserCircle, color: "var(--tavus-bubbletech-3)" },
  { id: "danger", label: "DANGER ZONE", icon: AlertTriangle, color: "var(--tavus-bubbletech-1)" },
];

export default function SettingsPage() {
  const [open, setOpen] = useState<string>("business");

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <div className="inline-flex items-center gap-2 mb-3">
          <span className="w-2 h-2 bg-[var(--tavus-terminal-black)]" />
          <span className="text-[11px] font-bold tracking-[0.2em] uppercase text-[var(--tavus-hardware-gray-8)]">SETTINGS</span>
        </div>
        <h1 className="font-[var(--font-serif-display)] text-3xl sm:text-4xl font-normal tracking-tight text-[var(--tavus-terminal-black)]">
          Tenant <span className="serif-italic">configuration</span>
        </h1>
      </div>

      <div className="space-y-3">
        {sections.map((s) => (
          <div key={s.id} className="relative bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[4px_4px_0_0_var(--tavus-terminal-black)] overflow-hidden">
            <div className="absolute inset-0 bg-halftone-light opacity-10 pointer-events-none" />
            <button
              onClick={() => setOpen(open === s.id ? "" : s.id)}
              className="relative w-full flex items-center gap-3 p-4 text-left hover:bg-[var(--tavus-plastic-1)] transition-colors"
            >
              <span className="inline-flex items-center justify-center w-8 h-8 border-2 border-[var(--tavus-terminal-black)]" style={{ background: s.color }}>
                <s.icon className="w-4 h-4" strokeWidth={2} />
              </span>
              <span className="text-[12px] font-extrabold tracking-wider uppercase text-[var(--tavus-terminal-black)] flex-1">{s.label}</span>
              <ChevronDown className={`w-4 h-4 text-[var(--tavus-terminal-black)] transition-transform ${open === s.id ? "rotate-180" : ""}`} />
            </button>
            {open === s.id && (
              <div className="relative p-5 pt-0">
                {s.id === "business" && <BusinessForm />}
                {s.id === "delivery" && <DeliveryForm />}
                {s.id === "payment" && <PaymentForm />}
                {s.id === "facebook" && <FacebookForm />}
                {s.id === "instagram" && <InstagramForm />}
                {s.id === "whatsapp" && <WhatsAppForm />}
                {s.id === "order_api" && <OrderApiForm />}
                {s.id === "knowledge" && <KnowledgeForm />}
                {s.id === "owner_chat" && <OwnerChatForm />}
                {s.id === "danger" && <DangerForm />}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function Field({ label, type = "text", placeholder = "", value = "", dir }: { label: string; type?: string; placeholder?: string; value?: string; dir?: string }) {
  return (
    <div>
      <label className="block text-[10px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)] mb-1.5">{label}</label>
      <input type={type} defaultValue={value} placeholder={placeholder} dir={dir} className="w-full h-10 px-3 border-2 border-[var(--tavus-terminal-black)] bg-white text-sm outline-none" />
    </div>
  );
}

function SelectField({ label, options, value }: { label: string; options: string[]; value?: string }) {
  return (
    <div>
      <label className="block text-[10px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)] mb-1.5">{label}</label>
      <select defaultValue={value} className="w-full h-10 px-3 border-2 border-[var(--tavus-terminal-black)] bg-white text-sm font-bold outline-none">
        {options.map((o) => (
          <option key={o} value={o.toLowerCase()}>{o}</option>
        ))}
      </select>
    </div>
  );
}

function ToggleRow({ label, desc, defaultChecked = false }: { label: string; desc: string; defaultChecked?: boolean }) {
  const [on, setOn] = useState(defaultChecked);
  return (
    <div className="flex items-center justify-between gap-3 p-3 border-2 border-[var(--tavus-terminal-black)] bg-white">
      <div>
        <div className="text-[11px] font-bold tracking-wider uppercase text-[var(--tavus-terminal-black)]">{label}</div>
        <div className="text-[10px] text-[var(--tavus-hardware-gray-8)]">{desc}</div>
      </div>
      <button
        onClick={() => setOn(!on)}
        className={`relative w-12 h-6 border-2 border-[var(--tavus-terminal-black)] transition-colors ${on ? "bg-[var(--tavus-neon-field-2)] text-white" : "bg-white"}`}
      >
        <span className={`absolute top-0.5 w-4 h-4 border border-[var(--tavus-terminal-black)] bg-[var(--tavus-terminal-black)] transition-all ${on ? "left-6" : "left-0.5"}`} />
      </button>
    </div>
  );
}

function SaveBar() {
  return (
    <div className="flex items-center gap-2 pt-3">
      <button className="inline-flex items-center gap-2 px-4 h-10 border-[3px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-bubbletech-4)] text-[11px] font-extrabold tracking-wider uppercase shadow-[2px_2px_0_0_var(--tavus-terminal-black)] hover:shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] transition-all">
        SAVE CHANGES
      </button>
      <button className="inline-flex items-center gap-2 px-4 h-10 border-[3px] border-[var(--tavus-terminal-black)] bg-white text-[11px] font-extrabold tracking-wider uppercase">
        DISCARD
      </button>
    </div>
  );
}

function BusinessForm() {
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <Field label="PAGE NAME *" value="Cairo Sneakers Store" />
        <Field label="WEBSITE URL" value="https://cairosneakers.com" />
        <Field label="BUSINESS EMAIL" value="hello@cairosneakers.com" type="email" />
        <Field label="BUSINESS PHONE" value="01012345678" type="tel" />
        <Field label="ARABIC NAME" value="كايرو سنيكرز ستور" dir="rtl" />
        <SelectField label="INDUSTRY" options={["Fashion", "Electronics", "Beauty", "Food & Beverage", "Home"]} value="Fashion" />
      </div>
      <div>
        <label className="block text-[10px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)] mb-1.5">DESCRIPTION</label>
        <textarea rows={3} defaultValue="Premium sneaker retailer based in Cairo. We carry Nike, Adidas, Puma and more." className="w-full p-3 border-2 border-[var(--tavus-terminal-black)] bg-white text-sm outline-none resize-none" />
      </div>
      <SaveBar />
    </div>
  );
}

function DeliveryForm() {
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <Field label="DEFAULT DELIVERY CHARGE (EGP)" value="50" type="number" />
        <Field label="FREE DELIVERY ABOVE (EGP)" value="1500" type="number" />
        <SelectField label="DEFAULT COURIER" options={["Bosta", "Aramex", "Mylerz", "Marsol"]} value="Bosta" />
        <SelectField label="DELIVERY TIME WINDOW" options={["1-2 days", "2-3 days", "3-5 days", "5-7 days"]} value="2-3 days" />
      </div>
      <div>
        <label className="block text-[10px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)] mb-1.5">SUPPORTED GOVERNORATES</label>
        <div className="flex flex-wrap gap-2">
          {["Cairo", "Giza", "Alexandria", "Dakahlia", "Sharqia", "Gharbia", "Monufia", "Qalyubia"].map((g) => (
            <span key={g} className="inline-block px-2 py-1 text-xs border-2 border-[var(--tavus-terminal-black)] bg-[var(--tavus-plastic-2)]">{g}</span>
          ))}
        </div>
      </div>
      <ToggleRow label="CASH ON DELIVERY" desc="Allow customers to pay with cash on delivery" defaultChecked />
      <ToggleRow label="EXPRESS DELIVERY" desc="Offer 24-hour express delivery option" defaultChecked />
      <SaveBar />
    </div>
  );
}

function PaymentForm() {
  return (
    <div className="space-y-3">
      {[
        { name: "Cash on Delivery", enabled: true, color: "var(--tavus-neon-field-2)" },
        { name: "Vodafone Cash", enabled: true, color: "var(--tavus-bubbletech-4)" },
        { name: "InstaPay", enabled: true, color: "var(--tavus-neon-field-2)" },
        { name: "Fawry", enabled: false, color: "var(--tavus-plastic-2)" },
        { name: "Visa / Mastercard", enabled: false, color: "var(--tavus-plastic-2)" },
      ].map((p) => (
        <ToggleRow key={p.name} label={p.name} desc={`${p.enabled ? "Active" : "Inactive"} payment method`} defaultChecked={p.enabled} />
      ))}
      <SaveBar />
    </div>
  );
}

function FacebookForm() {
  return (
    <div className="space-y-3">
      <div className="relative bg-[var(--tavus-bubbletech-1)] border-2 border-[var(--tavus-terminal-black)] p-3 overflow-hidden">
        <div className="absolute inset-0 bg-halftone-light opacity-10 pointer-events-none" />
        <div className="relative flex items-center gap-2">
          <span className="w-2.5 h-2.5 bg-[var(--tavus-neon-field-2)] border border-[var(--tavus-terminal-black)]" />
          <span className="text-[11px] font-bold tracking-wider uppercase text-[var(--tavus-terminal-black)]">CONNECTED · Page ID 10482937106</span>
        </div>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <Field label="PAGE NAME" value="Cairo Sneakers Store" />
        <Field label="PAGE ID" value="10482937106" />
        <Field label="ACCESS TOKEN" value="EAAG••••••••••••••••••••" />
        <Field label="WEBHOOK VERIFY TOKEN" value="zemest_verify_8s2k" />
      </div>
      <div className="flex items-center gap-2">
        <button className="inline-flex items-center gap-2 px-4 h-10 border-[3px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-neon-field-2)] text-white text-[11px] font-extrabold tracking-wider uppercase shadow-[2px_2px_0_0_var(--tavus-terminal-black)] hover:shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] transition-all">
          TEST WEBHOOK
        </button>
        <button className="inline-flex items-center gap-2 px-4 h-10 border-[3px] border-[var(--tavus-terminal-black)] bg-white text-[11px] font-extrabold tracking-wider uppercase">
          REFRESH TOKEN
        </button>
      </div>
      <SaveBar />
    </div>
  );
}

function InstagramForm() {
  return (
    <div className="space-y-3">
      <div className="relative bg-[var(--tavus-neon-field-1)] text-white border-2 border-[var(--tavus-terminal-black)] p-3 overflow-hidden">
        <div className="absolute inset-0 bg-halftone-light opacity-10 pointer-events-none" />
        <div className="relative flex items-center gap-2">
          <span className="w-2.5 h-2.5 bg-[var(--tavus-neon-field-2)] border border-[var(--tavus-terminal-black)]" />
          <span className="text-[11px] font-bold tracking-wider uppercase text-[var(--tavus-terminal-black)]">CONNECTED · IG User ID 17841400823910284</span>
        </div>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <Field label="IG USERNAME" value="cairosneakers" />
        <Field label="IG USER ID" value="17841400823910284" />
        <Field label="ACCESS TOKEN" value="IGQVJ••••••••••••••••••••" />
        <Field label="BUSINESS ACCOUNT ID" value="17841400823910284" />
      </div>
      <ToggleRow label="REPLY TO DMs" desc="Auto-reply to Instagram direct messages" defaultChecked />
      <ToggleRow label="REPLY TO COMMENT MENTIONS" desc="Auto-reply when customers comment on posts" />
      <SaveBar />
    </div>
  );
}

function WhatsAppForm() {
  return (
    <div className="space-y-3">
      <div className="relative bg-[var(--tavus-atomic-glow-5)] border-2 border-[var(--tavus-terminal-black)] p-3 overflow-hidden">
        <div className="absolute inset-0 bg-halftone-light opacity-10 pointer-events-none" />
        <div className="relative flex items-center gap-2">
          <span className="w-2.5 h-2.5 bg-[var(--tavus-neon-field-2)] border border-[var(--tavus-terminal-black)]" />
          <span className="text-[11px] font-bold tracking-wider uppercase text-[var(--tavus-terminal-black)]">CONNECTED · Phone +20 101 234 5678</span>
        </div>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <Field label="PHONE NUMBER ID" value="1029384756" />
        <Field label="WABA ID" value="1029384756102938" />
        <Field label="ACCESS TOKEN" value="EAAJ••••••••••••••••••••" />
        <Field label="WEBHOOK VERIFY TOKEN" value="zemest_wa_verify" />
      </div>
      <ToggleRow label="WHATSAPP BUSINESS API" desc="Use WhatsApp Business Cloud API for messaging" defaultChecked />
      <ToggleRow label="SEND ORDER NOTIFICATIONS" desc="Send customers order status updates via WhatsApp" defaultChecked />
      <SaveBar />
    </div>
  );
}

function OrderApiForm() {
  return (
    <div className="space-y-3">
      <div className="relative bg-[var(--tavus-plastic-2)] border-2 border-[var(--tavus-terminal-black)] p-3 overflow-hidden">
        <div className="absolute inset-0 bg-halftone-light opacity-10 pointer-events-none" />
        <div className="relative">
          <div className="text-[10px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)] mb-1">WEBHOOK URL</div>
          <div className="font-mono text-xs text-[var(--tavus-terminal-black)] break-all">https://api.zemest.com/v1/tenants/tnt_001/orders/webhook</div>
        </div>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <Field label="API KEY" value="zemest_live_8s2k4m9x" />
        <Field label="API SECRET" value="sk_live••••••••••••••" />
        <SelectField label="DEFAULT ORDER STATUS" options={["pending", "confirmed", "processing", "shipped", "delivered"]} value="pending" />
        <SelectField label="SYNC FREQUENCY" options={["Realtime", "Every 5 min", "Every 15 min", "Hourly"]} value="Realtime" />
      </div>
      <ToggleRow label="AUTO-SYNC TO 3RD PARTY" desc="Push orders to external fulfillment system" defaultChecked />
      <ToggleRow label="RETRY FAILED DELIVERIES" desc="Auto-retry webhook delivery up to 3 times" defaultChecked />
      <SaveBar />
    </div>
  );
}

function KnowledgeForm() {
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div className="bg-[var(--tavus-plastic-1)] border-2 border-[var(--tavus-terminal-black)] p-3">
          <div className="text-[9px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)]">PAGES INDEXED</div>
          <div className="text-lg font-bold text-[var(--tavus-terminal-black)]">62</div>
        </div>
        <div className="bg-[var(--tavus-plastic-1)] border-2 border-[var(--tavus-terminal-black)] p-3">
          <div className="text-[9px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)]">PRODUCTS</div>
          <div className="text-lg font-bold text-[var(--tavus-terminal-black)]">87</div>
        </div>
        <div className="bg-[var(--tavus-plastic-1)] border-2 border-[var(--tavus-terminal-black)] p-3">
          <div className="text-[9px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)]">VECTOR SIZE</div>
          <div className="text-lg font-bold text-[var(--tavus-terminal-black)]">14.2 MB</div>
        </div>
      </div>
      <Field label="LAST REINDEX" value="Aug 27, 2026 - 09:14 AM" />
      <Field label="KNOWLEDGE SOURCE URL" value="https://cairosneakers.com" />
      <SaveBar />
    </div>
  );
}

function OwnerChatForm() {
  return (
    <div className="space-y-3">
      <Field label="OWNER NOTIFICATION PHONE" value="01099887766" type="tel" />
      <Field label="OWNER NOTIFICATION EMAIL" value="owner@cairosneakers.com" type="email" />
      <SelectField label="HANDOFF TRIGGER" options={["Customer requests human", "AI confidence < 60%", "Order dispute", "High-value order"]} value="Customer requests human" />
      <SelectField label="HANDOFF CHANNEL" options={["WhatsApp", "SMS", "Email", "In-app notification"]} value="WhatsApp" />
      <ToggleRow label="ALLOW OWNER TO TAKE OVER" desc="Owner can intercept any conversation" defaultChecked />
      <ToggleRow label="AUTO-RESOLVE AFTER 24H" desc="Auto-resolve owner chats after 24 hours of inactivity" defaultChecked />
      <SaveBar />
    </div>
  );
}

function DangerForm() {
  return (
    <div className="space-y-3">
      <div className="relative bg-[var(--tavus-bubbletech-1)] border-2 border-[var(--tavus-terminal-black)] p-3 overflow-hidden">
        <div className="absolute inset-0 bg-halftone-light opacity-10 pointer-events-none" />
        <div className="relative flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-[var(--tavus-terminal-black)]" strokeWidth={2} />
          <span className="text-[11px] font-bold tracking-wider uppercase text-[var(--tavus-terminal-black)]">IRREVERSIBLE ACTIONS PROCEED WITH CAUTION</span>
        </div>
      </div>
      <div className="space-y-2">
        <DangerRow label="RESET STYLE PROFILE" desc="Wipe learned style and re-train from scratch" />
        <DangerRow label="CLEAR ALL CONVERSATIONS" desc="Delete all chat history for this tenant" />
        <DangerRow label="DISCONNECT ALL CHANNELS" desc="Disconnect FB, IG, WhatsApp integrations" />
        <DangerRow label="DELETE TENANT PERMANENTLY" desc="This will permanently delete the tenant and all related data" critical />
      </div>
    </div>
  );
}

function DangerRow({ label, desc, critical = false }: { label: string; desc: string; critical?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-3 p-3 border-2 border-[var(--tavus-terminal-black)] bg-white">
      <div>
        <div className="text-[11px] font-bold tracking-wider uppercase text-[var(--tavus-terminal-black)]">{label}</div>
        <div className="text-[10px] text-[var(--tavus-hardware-gray-8)]">{desc}</div>
      </div>
      <button
        className={`inline-flex items-center gap-2 px-3 h-9 border-[3px] border-[var(--tavus-terminal-black)] text-[10px] font-extrabold tracking-wider uppercase shadow-[2px_2px_0_0_var(--tavus-terminal-black)] hover:shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] transition-all ${
          critical ? "bg-[var(--tavus-bubbletech-1)]" : "bg-white"
        }`}
      >
        EXECUTE
      </button>
    </div>
  );
}
