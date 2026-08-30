"use client";

import { useState } from "react";
import { Send, Trash2, ToggleLeft, ToggleRight } from "lucide-react";

interface Message {
  role: "customer" | "ai";
  content: string;
}

const mockMessages: Message[] = [
  { role: "customer", content: "Hello, do you have Air Max 90 in size 42?" },
  { role: "ai", content: "Yes, we have 2 in stock. Price is 850 EGP. Would you like me to hold one for you?" },
];

export default function ChatPlayground({ params }: { params: { tenantId: string } }) {
  const [messages, setMessages] = useState<Message[]>(mockMessages);
  const [input, setInput] = useState("");
  const [customerName, setCustomerName] = useState("Test Customer");
  const [ownerMode, setOwnerMode] = useState(false);

  const handleSend = () => {
    if (!input.trim()) return;
    const newMsg: Message = { role: "customer", content: input };
    setMessages([...messages, newMsg]);
    setInput("");
    // Simulate AI reply
    setTimeout(() => {
      const aiReply: Message = {
        role: "ai",
        content: ownerMode
          ? "I can help you generate posts, check insights, or find the best time to post. What would you like to do?"
          : "I understand. Let me check that for you right away.",
      };
      setMessages((prev) => [...prev, aiReply]);
    }, 1200);
  };

  return (
    <div className="space-y-6">
      <div>
        <div className="inline-flex items-center gap-2 mb-3">
          <span className="w-2 h-2 bg-[var(--tavus-terminal-black)]" />
          <span className="text-[11px] font-bold tracking-[0.2em] uppercase text-[var(--tavus-hardware-gray-8)]">CHAT PLAYGROUND</span>
        </div>
        <h1 className="font-[var(--font-serif-display)] text-3xl sm:text-4xl font-normal tracking-tight text-[var(--tavus-terminal-black)]">
          Test your <span className="serif-italic">agent</span>
        </h1>
      </div>

      {/* Owner/Customer chat toggle */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => setOwnerMode(false)}
          className={`inline-flex items-center gap-2 px-4 h-9 border-[3px] border-[var(--tavus-terminal-black)] text-[11px] font-extrabold tracking-wider uppercase transition-all ${
            !ownerMode ? "bg-[var(--tavus-bubbletech-4)]" : "bg-white"
          }`}
        >
          {!ownerMode ? <ToggleRight className="w-4 h-4" /> : <ToggleLeft className="w-4 h-4" />}
          CUSTOMER CHAT
        </button>
        <button
          onClick={() => setOwnerMode(true)}
          className={`inline-flex items-center gap-2 px-4 h-9 border-[3px] border-[var(--tavus-terminal-black)] text-[11px] font-extrabold tracking-wider uppercase transition-all ${
            ownerMode ? "bg-[var(--tavus-neon-field-2)] text-white" : "bg-white"
          }`}
        >
          {ownerMode ? <ToggleRight className="w-4 h-4" /> : <ToggleLeft className="w-4 h-4" />}
          OWNER CHAT
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Chat panel (2/3) */}
        <div className="lg:col-span-2 relative bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[6px_6px_0_0_var(--tavus-terminal-black)] overflow-hidden flex flex-col" style={{ height: "500px" }}>
          <div className="absolute inset-0 bg-halftone-light opacity-10 pointer-events-none" />
          <div className="win-title-bar relative">
            <span className="w-2.5 h-2.5 bg-[var(--tavus-bubbletech-4)] border border-[var(--tavus-terminal-black)]" />
            <span>{ownerMode ? "OWNER CHAT" : "CUSTOMER CHAT"}</span>
          </div>

          {/* Messages */}
          <div className="relative flex-1 overflow-y-auto scrollbar-thin p-4 space-y-3">
            {messages.map((m, i) => (
              <div key={i} className={`flex ${m.role === "customer" ? "justify-end" : "justify-start"}`}>
                <div
                  className={`max-w-[75%] border-2 border-[var(--tavus-terminal-black)] px-3 py-2 text-sm ${
                    m.role === "customer" ? "bg-[var(--tavus-bubbletech-1)]" : "bg-white"
                  }`}
                >
                  {m.content}
                </div>
              </div>
            ))}
          </div>

          {/* Input */}
          <div className="relative border-t-2 border-[var(--tavus-terminal-black)] p-3 flex gap-2 bg-white">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && (e.preventDefault(), handleSend())}
              placeholder="Type a message..."
              className="flex-1 h-10 px-3 border-2 border-[var(--tavus-terminal-black)] bg-white text-sm outline-none"
            />
            <button
              onClick={handleSend}
              disabled={!input.trim()}
              className="inline-flex items-center justify-center w-10 h-10 border-2 border-[var(--tavus-terminal-black)] bg-[var(--tavus-neon-field-2)] text-white disabled:opacity-30"
            >
              <Send className="w-4 h-4" />
            </button>
            <button
              onClick={() => setMessages([])}
              className="inline-flex items-center justify-center w-10 h-10 border-2 border-[var(--tavus-terminal-black)] bg-white"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Debug panel (1/3) */}
        <div className="relative bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[6px_6px_0_0_var(--tavus-terminal-black)] overflow-hidden">
          <div className="absolute inset-0 bg-halftone-light opacity-10 pointer-events-none" />
          <div className="win-title-bar relative">
            <span className="w-2.5 h-2.5 bg-[var(--tavus-neon-field-2)] border border-[var(--tavus-terminal-black)]" />
            <span>DEBUG INFO</span>
          </div>
          <div className="relative p-4 space-y-3">
            <div>
              <label className="block text-[10px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)] mb-1">CUSTOMER NAME</label>
              <input
                type="text"
                value={customerName}
                onChange={(e) => setCustomerName(e.target.value)}
                className="w-full h-9 px-2 border-2 border-[var(--tavus-terminal-black)] bg-white text-sm outline-none"
              />
            </div>
            <DebugField label="CONVERSATION ID" value="conv_test_001" />
            <DebugField label="CUSTOMER ID" value="cust_test_001" />
            <DebugField label="TOKENS USED (LAST)" value="142" />
            <DebugField label="TOTAL TOKENS (SESSION)" value="1,840" />
            <DebugField label="DETECTED LANGUAGE" value="english" />
            <DebugField label="DETECTED DIALECT" value="us_english" />
          </div>
        </div>
      </div>
    </div>
  );
}

function DebugField({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-[var(--tavus-plastic-1)] border-2 border-[var(--tavus-terminal-black)] p-2">
      <div className="text-[9px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)]">{label}</div>
      <div className="text-sm font-mono text-[var(--tavus-terminal-black)] mt-0.5">{value}</div>
    </div>
  );
}
