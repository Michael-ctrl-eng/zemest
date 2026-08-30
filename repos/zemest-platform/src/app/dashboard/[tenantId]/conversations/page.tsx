"use client";

import { useState } from "react";
import { Search, X, Send, User } from "lucide-react";

interface Conversation {
  id: string;
  customer_name: string;
  channel: "facebook" | "instagram" | "whatsapp";
  status: "active" | "waiting" | "resolved" | "handed_off";
  message_count: number;
  last_message: string;
  last_message_at: string;
}

interface ThreadMessage {
  role: "customer" | "ai";
  content: string;
  time: string;
}

const mockConversations: Conversation[] = [
  { id: "conv1", customer_name: "Ahmed Hassan", channel: "facebook", status: "active", message_count: 14, last_message: "Perfect, please ship to Maadi, Cairo", last_message_at: "2 min ago" },
  { id: "conv2", customer_name: "Sara Mohamed", channel: "instagram", status: "waiting", message_count: 8, last_message: "Do you have this in red?", last_message_at: "1 hour ago" },
  { id: "conv3", customer_name: "Omar Khaled", channel: "whatsapp", status: "resolved", message_count: 22, last_message: "Thank you, order received", last_message_at: "3 hours ago" },
  { id: "conv4", customer_name: "Fatma Ali", channel: "facebook", status: "handed_off", message_count: 11, last_message: "I want to speak to the owner", last_message_at: "5 hours ago" },
  { id: "conv5", customer_name: "Mahmoud Ibrahim", channel: "instagram", status: "active", message_count: 6, last_message: "What sizes do you have?", last_message_at: "6 hours ago" },
  { id: "conv6", customer_name: "Nour El-Din", channel: "whatsapp", status: "waiting", message_count: 4, last_message: "Is cash on delivery available?", last_message_at: "8 hours ago" },
];

const mockThread: ThreadMessage[] = [
  { role: "customer", content: "Hello, do you have Air Max 90 in size 42?", time: "10:30 AM" },
  { role: "ai", content: "Welcome! Yes, we have 2 pairs of Air Max 90 in size 42. The price is 850 EGP. Would you like to place an order?", time: "10:30 AM" },
  { role: "customer", content: "Yes, how long does shipping take to Maadi?", time: "10:32 AM" },
  { role: "ai", content: "Shipping to Maadi takes 1-2 business days. Cash on delivery is available. Shall I create the order?", time: "10:32 AM" },
  { role: "customer", content: "Perfect, please ship to Maadi, Cairo", time: "10:35 AM" },
];

const channelColors: Record<string, string> = {
  facebook: "var(--tavus-bubbletech-4)",
  instagram: "var(--tavus-neon-field-2)",
  whatsapp: "var(--tavus-atomic-glow-5)",
};

const statusColors: Record<string, string> = {
  active: "var(--tavus-neon-field-2)",
  waiting: "var(--tavus-atomic-glow-5)",
  resolved: "var(--tavus-frost-4)",
  handed_off: "var(--tavus-bubbletech-1)",
};

export default function ConversationsPage() {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [selected, setSelected] = useState<Conversation | null>(null);

  const filtered = mockConversations.filter((c) => {
    const matchSearch = !search || c.customer_name.toLowerCase().includes(search.toLowerCase());
    const matchStatus = statusFilter === "all" || c.status === statusFilter;
    return matchSearch && matchStatus;
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <div className="inline-flex items-center gap-2 mb-3">
          <span className="w-2 h-2 bg-[var(--tavus-terminal-black)]" />
          <span className="text-[11px] font-bold tracking-[0.2em] uppercase text-[var(--tavus-hardware-gray-8)]">CONVERSATIONS</span>
        </div>
        <h1 className="font-[var(--font-serif-display)] text-3xl sm:text-4xl font-normal tracking-tight text-[var(--tavus-terminal-black)]">
          Conversation <span className="serif-italic">log</span>
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
            placeholder="Search by customer name..."
            className="w-full h-10 pl-10 pr-3 border-2 border-[var(--tavus-terminal-black)] bg-white text-sm outline-none"
          />
        </div>
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="h-10 px-3 border-2 border-[var(--tavus-terminal-black)] bg-white text-sm font-bold">
          <option value="all">All Status</option>
          <option value="active">Active</option>
          <option value="waiting">Waiting</option>
          <option value="resolved">Resolved</option>
          <option value="handed_off">Handed Off</option>
        </select>
      </div>

      {/* Conversations table */}
      <div className="relative bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[6px_6px_0_0_var(--tavus-terminal-black)] overflow-hidden">
        <div className="absolute inset-0 bg-halftone-light opacity-10 pointer-events-none" />
        <div className="relative overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-[var(--tavus-terminal-black)] text-white">
              <tr>
                <th className="text-left p-3 font-extrabold tracking-wider uppercase text-[10px]">CUSTOMER</th>
                <th className="text-left p-3 font-extrabold tracking-wider uppercase text-[10px]">CHANNEL</th>
                <th className="text-left p-3 font-extrabold tracking-wider uppercase text-[10px]">STATUS</th>
                <th className="text-center p-3 font-extrabold tracking-wider uppercase text-[10px]">MSGS</th>
                <th className="text-left p-3 font-extrabold tracking-wider uppercase text-[10px]">LAST MESSAGE</th>
                <th className="text-left p-3 font-extrabold tracking-wider uppercase text-[10px]">LAST AT</th>
                <th className="text-center p-3 font-extrabold tracking-wider uppercase text-[10px]">VIEW</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((c) => (
                <tr
                  key={c.id}
                  onClick={() => setSelected(c)}
                  className="border-t border-[var(--tavus-terminal-black)]/10 hover:bg-[var(--tavus-plastic-1)] cursor-pointer"
                >
                  <td className="p-3 font-bold text-[var(--tavus-terminal-black)]">{c.customer_name}</td>
                  <td className="p-3">
                    <span className="inline-block px-2 py-0.5 text-[9px] font-bold tracking-wider uppercase border border-[var(--tavus-terminal-black)] text-white" style={{ background: channelColors[c.channel] }}>
                      {c.channel}
                    </span>
                  </td>
                  <td className="p-3">
                    <span className="inline-block px-2 py-0.5 text-[9px] font-bold tracking-wider uppercase border border-[var(--tavus-terminal-black)] text-white" style={{ background: statusColors[c.status] }}>
                      {c.status.replace("_", " ")}
                    </span>
                  </td>
                  <td className="p-3 text-center font-bold text-[var(--tavus-terminal-black)]">{c.message_count}</td>
                  <td className="p-3 text-[var(--tavus-hardware-gray-8)] max-w-[280px] truncate">{c.last_message}</td>
                  <td className="p-3 text-[10px] text-[var(--tavus-hardware-gray-8)] whitespace-nowrap">{c.last_message_at}</td>
                  <td className="p-3 text-center">
                    <button className="inline-flex items-center justify-center w-7 h-7 border border-[var(--tavus-terminal-black)] bg-white hover:bg-[var(--tavus-bubbletech-4)]">
                      <Search className="w-3.5 h-3.5" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="relative flex items-center justify-between p-3 border-t-2 border-[var(--tavus-terminal-black)] bg-[var(--tavus-plastic-1)]">
          <div className="text-[10px] font-bold text-[var(--tavus-hardware-gray-8)]">{filtered.length} conversations</div>
          <div className="text-[10px] text-[var(--tavus-hardware-gray-8)]">{filtered.filter((c) => c.status === "active").length} active</div>
        </div>
      </div>

      {selected && <ConversationDetailModal conversation={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}

function ConversationDetailModal({ conversation, onClose }: { conversation: Conversation; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[var(--tavus-terminal-black)]/50">
      <div className="relative w-full max-w-2xl bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[8px_8px_0_0_var(--tavus-terminal-black)] overflow-hidden max-h-[90vh] overflow-y-auto">
        <div className="absolute inset-0 bg-halftone-light opacity-10 pointer-events-none" />
        <div className="win-title-bar relative">
          <span className="w-2.5 h-2.5 bg-[var(--tavus-bubbletech-4)] border border-[var(--tavus-terminal-black)]" />
          <span>CONVERSATION THREAD</span>
          <button onClick={onClose} className="ml-auto inline-flex items-center justify-center w-5 h-5 border border-[var(--tavus-terminal-black)] bg-white">
            <X className="w-3 h-3" />
          </button>
        </div>
        <div className="relative p-4 space-y-4">
          {/* Customer header */}
          <div className="flex items-center justify-between flex-wrap gap-3">
            <div className="flex items-center gap-3">
              <div className="inline-flex items-center justify-center w-10 h-10 border-2 border-[var(--tavus-terminal-black)] bg-[var(--tavus-plastic-2)]">
                <User className="w-5 h-5" />
              </div>
              <div>
                <div className="font-bold text-[var(--tavus-terminal-black)]">{conversation.customer_name}</div>
                <div className="flex items-center gap-2 mt-1">
                  <span className="inline-block px-2 py-0.5 text-[9px] font-bold tracking-wider uppercase border border-[var(--tavus-terminal-black)] text-white" style={{ background: channelColors[conversation.channel] }}>
                    {conversation.channel}
                  </span>
                  <span className="inline-block px-2 py-0.5 text-[9px] font-bold tracking-wider uppercase border border-[var(--tavus-terminal-black)] text-white" style={{ background: statusColors[conversation.status] }}>
                    {conversation.status.replace("_", " ")}
                  </span>
                  <span className="text-[10px] text-[var(--tavus-hardware-gray-8)]">{conversation.message_count} messages</span>
                </div>
              </div>
            </div>
            <div className="text-[10px] text-[var(--tavus-hardware-gray-8)]">Last activity: {conversation.last_message_at}</div>
          </div>

          {/* Thread */}
          <div className="relative bg-white border-2 border-[var(--tavus-terminal-black)] overflow-hidden">
            <div className="win-title-bar relative">
              <span className="w-2.5 h-2.5 bg-[var(--tavus-neon-field-2)] border border-[var(--tavus-terminal-black)]" />
              <span>READ-ONLY THREAD</span>
            </div>
            <div className="relative max-h-[400px] overflow-y-auto scrollbar-thin p-4 space-y-3 bg-[var(--tavus-plastic-1)]">
              {mockThread.map((m, i) => (
                <div key={i} className={`flex ${m.role === "customer" ? "justify-end" : "justify-start"}`}>
                  <div className={`max-w-[75%] border-2 border-[var(--tavus-terminal-black)] px-3 py-2 text-sm ${m.role === "customer" ? "bg-[var(--tavus-bubbletech-1)]" : "bg-white"}`}>
                    <div className="text-[9px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)] mb-1 flex items-center gap-1">
                      {m.role === "ai" ? <Send className="w-2.5 h-2.5" /> : <User className="w-2.5 h-2.5" />}
                      {m.role === "ai" ? "AI AGENT" : "CUSTOMER"}
                    </div>
                    <div className="text-[var(--tavus-terminal-black)]">{m.content}</div>
                    <div className="text-[9px] text-[var(--tavus-hardware-gray-8)] mt-1 text-right">{m.time}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-[var(--tavus-plastic-2)] border-2 border-[var(--tavus-terminal-black)] p-2.5 text-[10px] text-[var(--tavus-hardware-gray-8)]">
            This thread is read-only. To reply, open the live chat interface.
          </div>
        </div>
      </div>
    </div>
  );
}
