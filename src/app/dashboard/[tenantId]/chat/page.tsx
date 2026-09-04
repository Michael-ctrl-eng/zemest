"use client";

import { useState, useRef, useEffect, use } from "react";
import { Send, Trash2, ToggleLeft, ToggleRight, AlertTriangle, Info, Loader2 } from "lucide-react";
import { useConversation, useSendChatMessage, CHAT_POLL_MS } from "@/hooks/use-dashboard-data";
import { chatApi } from "@/lib/zemest-api";
import {
  WinCard,
  DashHeader,
  TavusButton,
  inputClass,
  labelClass,
} from "@/components/site/dash";

interface Message {
  role: "customer" | "ai";
  content: string;
}

export default function ChatPlayground({ params }: { params: Promise<{ tenantId: string }> }) {
  const { tenantId } = use(params);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [customerName, setCustomerName] = useState("Test Customer");
  const [ownerMode, setOwnerMode] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [customerId, setCustomerId] = useState<string | null>(null);
  const [lastTokens, setLastTokens] = useState<number | null>(null);
  const [sessionTokens, setSessionTokens] = useState(0);
  const [latencyMs, setLatencyMs] = useState<number | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Real data wiring: the playground POSTs through a mutation and the live
  // conversation thread is polled from the backend (messages land in the DB).
  const sendMutation = useSendChatMessage(tenantId);
  const conversationQuery = useConversation(tenantId, conversationId, CHAT_POLL_MS);
  const sending = sendMutation.isPending;

  // Server transcript is authoritative — once a conversation exists, sync the
  // local transcript whenever the polled thread gains messages (catches
  // replies delivered outside this tab). Local optimistic messages are never
  // dropped: we only replace when the server has at least as many messages.
  const syncedCountRef = useRef(0);
  const serverMessages = conversationQuery.data?.messages;
  useEffect(() => {
    if (!serverMessages || serverMessages.length === 0) return;
    if (serverMessages.length > syncedCountRef.current && serverMessages.length >= messages.length) {
      syncedCountRef.current = serverMessages.length;
      setMessages(
        serverMessages.map((m) => ({
          role: (m.role === "customer" ? "customer" : "ai") as Message["role"],
          content: m.content,
        }))
      );
    }
  }, [serverMessages, messages.length]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, sending]);

  const handleSend = async () => {
    const text = input.trim();
    if (!text || sending) return;
    setError(null);

    // Owner mode: talk to the OWNER-side agent (postiz/scheduling) —
    // audit B6: this used to post to /test/chat, silently creating fake
    // CUSTOMER conversations while the user believed they were chatting
    // with the owner-side agent.
    if (ownerMode) {
      setMessages((prev) => [...prev, { role: "customer", content: text }]);
      setInput("");
      try {
        const res = await chatApi.sendOwner(tenantId, text);
        setMessages((prev) => [...prev, { role: "ai", content: res.reply }]);
      } catch (err: unknown) {
        const detail = err instanceof Error ? err.message : "The owner agent could not be reached";
        setError(detail);
        setMessages((prev) => [...prev, { role: "ai", content: "⚠ " + detail }]);
      }
      return;
    }

    setMessages((prev) => [...prev, { role: "customer", content: text }]);
    setInput("");
    const t0 = performance.now();
    try {
      const res = await sendMutation.mutateAsync({
        message: text,
        customerName: customerName || "Test Customer",
      });
      setLatencyMs(Math.round(performance.now() - t0));
      setMessages((prev) => [...prev, { role: "ai", content: res.reply }]);
      setConversationId(res.conversation_id ?? null);
      setCustomerId(res.customer_id ?? null);
      setLastTokens(res.tokens_used ?? 0);
      setSessionTokens((prev) => prev + (res.tokens_used ?? 0));
    } catch (err: unknown) {
      const detail = err instanceof Error ? err.message : "The agent could not be reached";
      setError(detail);
      setMessages((prev) => [...prev, { role: "ai", content: "⚠ " + detail }]);
    }
  };

  const clearChat = () => {
    setMessages([]);
    setError(null);
    setConversationId(null);
    setCustomerId(null);
    setLastTokens(null);
    setSessionTokens(0);
    setLatencyMs(null);
    syncedCountRef.current = 0;
  };

  return (
    <div className="space-y-6">
      <DashHeader eyebrow="Chat playground" title="Chat" tail="playground" />

      {/* Owner/Customer chat toggle */}
      <div className="flex items-center gap-3 flex-wrap">
        <button
          onClick={() => setOwnerMode(false)}
          aria-pressed={!ownerMode}
          className={`inline-flex items-center gap-2 px-4 h-10 border-[3px] border-[var(--tavus-terminal-black)] text-[11px] font-extrabold tracking-[0.1em] uppercase transition-all ${
            !ownerMode
              ? "bg-[var(--tavus-bubbletech-4)] text-[var(--tavus-terminal-black)] shadow-[3px_3px_0_0_var(--tavus-terminal-black)]"
              : "bg-white text-[var(--tavus-terminal-black)]"
          }`}
        >
          {!ownerMode ? <ToggleRight className="w-4 h-4" strokeWidth={2.5} /> : <ToggleLeft className="w-4 h-4" strokeWidth={2.5} />}
          Customer chat
        </button>
        <button
          onClick={() => setOwnerMode(true)}
          aria-pressed={ownerMode}
          className={`inline-flex items-center gap-2 px-4 h-10 border-[3px] border-[var(--tavus-terminal-black)] text-[11px] font-extrabold tracking-[0.1em] uppercase transition-all ${
            ownerMode
              ? "bg-[var(--tavus-neon-field-2)] text-white shadow-[3px_3px_0_0_var(--tavus-terminal-black)]"
              : "bg-white text-[var(--tavus-terminal-black)]"
          }`}
        >
          {ownerMode ? <ToggleRight className="w-4 h-4" strokeWidth={2.5} /> : <ToggleLeft className="w-4 h-4" strokeWidth={2.5} />}
          Owner chat
        </button>
      </div>

      {ownerMode ? (
        <div className="flex items-start gap-3 border-[2.5px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-plastic-1)] p-3">
          <Info className="w-4 h-4 mt-0.5 shrink-0 text-[var(--tavus-terminal-black)]" strokeWidth={2.5} />
          <p className="text-[12px] font-medium text-[var(--tavus-terminal-black)] leading-snug">
            Owner chat activates automatically once your Facebook page is connected (Settings → Connect
            Facebook). Until then, this playground simulates customer messages — exactly what your AI agent
            will see in production.
          </p>
        </div>
      ) : null}

      {error && !ownerMode ? (
        <div className="flex items-center gap-2 border-[2.5px] border-[var(--tavus-coral-1)] bg-[var(--tavus-coral-3)]/40 px-3 py-2">
          <AlertTriangle className="w-4 h-4 text-[var(--tavus-terminal-black)] shrink-0" strokeWidth={2.5} />
          <span className="text-[12px] font-bold text-[var(--tavus-terminal-black)]">{error}</span>
        </div>
      ) : null}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Chat panel (2/3) — thread window + composer window */}
        <div className="lg:col-span-2 flex flex-col gap-5 h-[560px]">
          <WinCard
            title={ownerMode ? "Owner chat (connect FB to enable)" : "Customer chat — live agent"}
            dot="var(--tavus-bubbletech-4)"
            className="flex-1 min-h-0 flex flex-col"
            contentClassName="flex flex-col flex-1 min-h-0"
          >
            {/* Messages */}
            <div ref={scrollRef} className="relative flex-1 overflow-y-auto scrollbar-thin p-4 space-y-3">
              {messages.length === 0 ? (
                <div className="h-full flex items-center justify-center text-center px-6">
                  <div>
                    <p className="text-sm font-bold tracking-[0.16em] uppercase text-[var(--tavus-hardware-gray-8)] mb-2">
                      Send your first message
                    </p>
                    <p className="text-[12px] font-medium text-[var(--tavus-hardware-gray-8)]">
                      Try: &quot;hello&quot; · &quot;what shoes do you have?&quot; · &quot;عندك مقاس 42؟&quot; — the agent detects
                      language &amp; dialect automatically.
                    </p>
                  </div>
                </div>
              ) : null}
              {messages.map((m, i) => (
                <div key={i} className={`flex ${m.role === "customer" ? "justify-end" : "justify-start"}`}>
                  <div
                    className={`max-w-[75%] px-3 py-2 text-sm whitespace-pre-wrap ${
                      m.role === "customer"
                        ? "bg-[var(--tavus-plastic-2)] border-2 border-[var(--tavus-terminal-black)]"
                        : "bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[3px_3px_0_0_var(--tavus-terminal-black)]"
                    }`}
                  >
                    {m.content}
                  </div>
                </div>
              ))}
              {sending ? (
                <div className="flex justify-start">
                  <div className="inline-flex items-center gap-2 border-2 border-[var(--tavus-terminal-black)] bg-white px-3 py-2 text-sm">
                    <Loader2 className="w-3.5 h-3.5 animate-spin text-[var(--tavus-terminal-black)]" strokeWidth={2.5} />
                    <span className="font-medium text-[var(--tavus-hardware-gray-8)]">Agent is typing…</span>
                  </div>
                </div>
              ) : null}
            </div>
          </WinCard>

          {/* Input row at bottom */}
          <WinCard title="Send a message" dot="var(--tavus-atomic-glow-1)" className="shrink-0">
            <div className="relative p-3 flex gap-2 bg-white">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && (e.preventDefault(), handleSend())}
                placeholder="Type a message..."
                disabled={sending}
                className={`flex-1 ${inputClass} disabled:opacity-50`}
              />
              <TavusButton
                onClick={handleSend}
                disabled={!input.trim() || sending}
                title="Send message"
                aria-label="Send message"
                className="w-11 h-11 px-0 shrink-0"
              >
                {sending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" strokeWidth={2.5} />}
              </TavusButton>
              <TavusButton
                onClick={clearChat}
                title="Clear conversation"
                aria-label="Clear conversation"
                variant="secondary"
                className="w-11 h-11 px-0 shrink-0"
              >
                <Trash2 className="w-4 h-4" strokeWidth={2.5} />
              </TavusButton>
            </div>
          </WinCard>
        </div>

        {/* Debug panel (1/3) */}
        <WinCard title="Agent telemetry" dot="var(--tavus-neon-field-2)">
          <div className="relative p-4 space-y-3">
            <div>
              <label className={labelClass} htmlFor="chat-customer-name">
                Customer name
              </label>
              <input
                id="chat-customer-name"
                type="text"
                value={customerName}
                onChange={(e) => setCustomerName(e.target.value)}
                className="w-full h-10 px-3 bg-white border-[2.5px] border-[var(--tavus-terminal-black)] text-sm font-semibold text-[var(--tavus-terminal-black)] focus:outline-none focus:shadow-[3px_3px_0_0_var(--tavus-terminal-black)] transition-shadow"
              />
            </div>
            <DebugField label="CONVERSATION ID" value={conversationId ?? "—"} />
            <DebugField label="CUSTOMER ID" value={customerId ?? "—"} />
            <DebugField label="TOKENS USED (LAST)" value={lastTokens !== null ? String(lastTokens) : "—"} />
            <DebugField label="TOTAL TOKENS (SESSION)" value={sessionTokens.toLocaleString()} />
            <DebugField label="LAST RESPONSE TIME" value={latencyMs !== null ? `${latencyMs} ms` : "—"} />
            <div className="relative border-[2px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-plastic-1)] p-2 overflow-hidden">
              <div className="absolute inset-0 bg-halftone-light opacity-[0.35] pointer-events-none" />
              <div className="relative text-[9px] font-extrabold tracking-[0.18em] uppercase text-[var(--tavus-hardware-gray-8)]">AI STATUS</div>
              <div className="relative flex items-center gap-1.5 mt-1">
                <span className={`w-2 h-2 ${lastTokens && lastTokens > 0 ? "bg-[var(--tavus-signal-green)]" : "bg-[var(--tavus-atomic-glow-1)]"}`} />
                <span className="text-[11px] font-bold text-[var(--tavus-terminal-black)]">
                  {lastTokens && lastTokens > 0 ? "LLM CONNECTED" : "FALLBACK MODE — NO LLM KEY"}
                </span>
              </div>
            </div>
          </div>
        </WinCard>
      </div>
    </div>
  );
}

function DebugField({ label, value }: { label: string; value: string }) {
  return (
    <div className="relative bg-[var(--tavus-plastic-1)] border-[2px] border-[var(--tavus-terminal-black)] p-2 overflow-hidden">
      <div className="absolute inset-0 bg-halftone-light opacity-[0.35] pointer-events-none" />
      <div className="relative text-[9px] font-extrabold tracking-[0.18em] uppercase text-[var(--tavus-hardware-gray-8)]">{label}</div>
      <div className="relative text-sm font-mono font-bold text-[var(--tavus-terminal-black)] mt-0.5 break-all tabular-nums">{value}</div>
    </div>
  );
}
