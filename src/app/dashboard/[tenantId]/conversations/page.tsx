"use client";

import { useState, useEffect, useCallback, use } from "react";
import { Search, X, Send, User, MessagesSquare, AlertTriangle, RefreshCw, Loader2 } from "lucide-react";
import { conversationsApi, formatDateTime, type Conversation, type ConversationMessage } from "@/lib/zemest-api";
import {
  WinCard,
  StatusBadge,
  DashHeader,
  TableShell,
  Th,
  Td,
  LoadingState,
  ErrorState,
  EmptyState,
} from "@/components/site/dash";

function lastMessagePreview(c: Conversation): string | null {
  if (!c.messages || c.messages.length === 0) return null;
  const last = c.messages[c.messages.length - 1];
  return last?.content ?? null;
}

export default function ConversationsPage({ params }: { params: Promise<{ tenantId: string }> }) {
  const { tenantId } = use(params);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [selected, setSelected] = useState<Conversation | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await conversationsApi.list(tenantId);
      setConversations(res?.conversations ?? []);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load conversations");
    } finally {
      setLoading(false);
    }
  }, [tenantId]);

  useEffect(() => {
    load();
  }, [load]);

  const statuses = Array.from(new Set(conversations.map((c) => c.status)));

  const filtered = conversations.filter((c) => {
    const matchSearch = !search || (c.customer_name || "").toLowerCase().includes(search.toLowerCase());
    const matchStatus = statusFilter === "all" || c.status === statusFilter;
    return matchSearch && matchStatus;
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <DashHeader
        eyebrow="Conversations"
        title="Customer"
        tail="conversations"
        action={
          <button
            onClick={load}
            title="Refresh"
            aria-label="Refresh"
            className="inline-flex items-center justify-center w-11 h-11 border-[3px] border-[var(--tavus-terminal-black)] bg-white shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:shadow-[4px_4px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] transition-all"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} strokeWidth={2.5} />
          </button>
        }
      />

      {/* Error state */}
      {error ? <ErrorState message={error} onRetry={load} /> : null}

      {/* Loading state */}
      {loading ? <LoadingState label="Loading conversations" /> : null}

      {/* Empty state */}
      {!loading && !error && conversations.length === 0 ? (
        <WinCard title="No conversations yet" dot="var(--tavus-atomic-glow-1)">
          <EmptyState
            icon={<MessagesSquare className="w-6 h-6" strokeWidth={2} />}
            title="No conversations yet"
            hint="Chats between customers and your AI agent appear here. Connect a channel or try the chat playground to see it in action."
          />
        </WinCard>
      ) : null}

      {/* Conversations table */}
      {!loading && !error && conversations.length > 0 ? (
        <>
          {/* Filters */}
          <div className="flex flex-wrap gap-3">
            <div className="relative flex-1 min-w-[200px]">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--tavus-hardware-gray-8)]" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search by customer name..."
                className="w-full h-10 pl-10 pr-3 bg-white border-[2.5px] border-[var(--tavus-terminal-black)] text-sm font-semibold text-[var(--tavus-terminal-black)] placeholder:text-[var(--tavus-hardware-gray-8)]/60 placeholder:font-medium focus:outline-none focus:shadow-[3px_3px_0_0_var(--tavus-terminal-black)] transition-shadow"
              />
            </div>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="h-10 px-3 bg-white border-[2.5px] border-[var(--tavus-terminal-black)] text-sm font-semibold text-[var(--tavus-terminal-black)] cursor-pointer"
            >
              <option value="all">All Status</option>
              {statuses.map((s) => (
                <option key={s} value={s}>
                  {s.replace("_", " ").charAt(0).toUpperCase() + s.slice(1)}
                </option>
              ))}
            </select>
          </div>

          <WinCard title="Conversations" dot="var(--tavus-bubbletech-4)">
            <TableShell>
              <thead>
                <tr>
                  <Th>Customer</Th>
                  <Th>Status</Th>
                  <Th>Last message</Th>
                  <Th>Started</Th>
                  <Th>Last activity</Th>
                  <Th className="text-center">View</Th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((c) => {
                  const preview = lastMessagePreview(c);
                  return (
                    /* kit Row doesn't forward onClick — replicate Row classes so the whole row stays clickable */
                    <tr
                      key={c.id}
                      onClick={() => setSelected(c)}
                      className="border-b border-[var(--tavus-terminal-black)]/10 hover:bg-[var(--tavus-plastic-1)]/70 transition-colors cursor-pointer"
                    >
                      <Td className="font-bold">{c.customer_name || "Unknown"}</Td>
                      <Td>
                        <StatusBadge status={c.status}>{c.status.replace("_", " ")}</StatusBadge>
                      </Td>
                      <Td className="max-w-[280px] truncate font-medium text-[var(--tavus-hardware-gray-8)]">{preview || "—"}</Td>
                      <Td className="text-[10px] font-medium text-[var(--tavus-hardware-gray-8)] whitespace-nowrap">{formatDateTime(c.started_at)}</Td>
                      <Td className="text-[10px] font-medium text-[var(--tavus-hardware-gray-8)] whitespace-nowrap">{formatDateTime(c.last_message_at)}</Td>
                      <Td>
                        <div className="flex items-center justify-center">
                          <button
                            title="Open thread"
                            aria-label="Open thread"
                            className="inline-flex items-center justify-center w-8 h-8 border-[2px] border-[var(--tavus-terminal-black)] bg-white hover:bg-[var(--tavus-bubbletech-4)] transition-colors"
                          >
                            <Search className="w-3.5 h-3.5" strokeWidth={2.25} />
                          </button>
                        </div>
                      </Td>
                    </tr>
                  );
                })}
                {filtered.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="p-8 text-center text-sm font-semibold text-[var(--tavus-hardware-gray-8)]">
                      No conversations match your filters.
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </TableShell>
            <div className="relative flex items-center justify-between px-4 py-3 border-t-[2px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-plastic-1)]">
              <div className="text-[10px] font-bold tracking-[0.14em] uppercase text-[var(--tavus-hardware-gray-8)]">{filtered.length} conversations</div>
              <div className="text-[10px] font-bold text-[var(--tavus-hardware-gray-8)]">{conversations.filter((c) => c.status === "active").length} active</div>
            </div>
          </WinCard>
        </>
      ) : null}

      {selected ? <ConversationDetailModal tenantId={tenantId} conversation={selected} onClose={() => setSelected(null)} /> : null}
    </div>
  );
}

function ConversationDetailModal({
  tenantId,
  conversation,
  onClose,
}: {
  tenantId: string;
  conversation: Conversation;
  onClose: () => void;
}) {
  const [messages, setMessages] = useState<ConversationMessage[]>(conversation.messages ?? []);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function fetchThread() {
      setLoading(true);
      setError(null);
      try {
        const detail = await conversationsApi.get(tenantId, conversation.id);
        if (!cancelled) setMessages(detail?.messages ?? []);
      } catch (err: unknown) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load thread");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    fetchThread();
    return () => {
      cancelled = true;
    };
  }, [tenantId, conversation.id]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[var(--tavus-terminal-black)]/50">
      <div className="relative w-full max-w-2xl border-[3px] border-[var(--tavus-terminal-black)] shadow-[8px_8px_0_0_var(--tavus-terminal-black)] bg-white overflow-hidden max-h-[90vh] overflow-y-auto scrollbar-thin">
        <div className="absolute inset-0 bg-halftone-light opacity-[0.35] pointer-events-none" />
        <div className="win-title-bar relative justify-between">
          <span className="flex items-center gap-2 min-w-0">
            <span className="w-2.5 h-2.5 bg-[var(--tavus-bubbletech-4)] border border-[var(--tavus-terminal-black)] shrink-0" />
            <span className="truncate">Conversation thread</span>
          </span>
          <button
            onClick={onClose}
            aria-label="Close"
            title="Close"
            className="shrink-0 inline-flex items-center justify-center w-6 h-6 border-[2px] border-[var(--tavus-terminal-black)] bg-white text-[var(--tavus-terminal-black)] hover:bg-[var(--tavus-coral-3)]/50 transition-colors"
          >
            <X className="w-3.5 h-3.5" strokeWidth={2.5} />
          </button>
        </div>
        <div className="relative p-4 space-y-4">
          {/* Customer header */}
          <div className="flex items-center justify-between flex-wrap gap-3">
            <div className="flex items-center gap-3">
              <div className="inline-flex items-center justify-center w-10 h-10 border-[2px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-plastic-2)]">
                <User className="w-5 h-5" strokeWidth={2} />
              </div>
              <div>
                <div className="font-bold text-[var(--tavus-terminal-black)]">{conversation.customer_name || "Unknown"}</div>
                <div className="flex items-center gap-2 mt-1">
                  <StatusBadge status={conversation.status}>{conversation.status.replace("_", " ")}</StatusBadge>
                  <span className="text-[10px] font-medium text-[var(--tavus-hardware-gray-8)]">{messages.length} messages</span>
                </div>
              </div>
            </div>
            <div className="text-[10px] font-medium text-[var(--tavus-hardware-gray-8)]">Last activity: {formatDateTime(conversation.last_message_at)}</div>
          </div>

          {/* Thread */}
          <WinCard title="Read-only thread" dot="var(--tavus-neon-field-2)" className="shadow-[4px_4px_0_0_var(--tavus-terminal-black)]">
            <div className="relative max-h-[400px] overflow-y-auto scrollbar-thin p-4 space-y-3 bg-[var(--tavus-plastic-1)]">
              {loading ? (
                <div className="flex items-center justify-center gap-2 py-8">
                  <Loader2 className="w-4 h-4 animate-spin text-[var(--tavus-terminal-black)]" strokeWidth={2.5} />
                  <span className="text-xs font-bold tracking-[0.14em] uppercase text-[var(--tavus-hardware-gray-8)]">Loading thread…</span>
                </div>
              ) : null}
              {error ? (
                <div className="flex items-center gap-2 border-[2.5px] border-[var(--tavus-coral-1)] bg-[var(--tavus-coral-3)]/40 px-3 py-2">
                  <AlertTriangle className="w-4 h-4 text-[var(--tavus-terminal-black)] shrink-0" strokeWidth={2.5} />
                  <span className="text-xs font-bold text-[var(--tavus-terminal-black)]">{error}</span>
                </div>
              ) : null}
              {!loading && !error && messages.length === 0 ? (
                <div className="py-8 text-center text-xs font-medium text-[var(--tavus-hardware-gray-8)]">No messages in this conversation.</div>
              ) : null}
              {!loading
                ? messages.map((m) => (
                    <div key={m.id} className={`flex ${m.role === "customer" ? "justify-end" : "justify-start"}`}>
                      <div
                        className={`max-w-[75%] px-3 py-2 text-sm ${
                          m.role === "customer"
                            ? "bg-[var(--tavus-plastic-2)] border-2 border-[var(--tavus-terminal-black)]"
                            : "bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[3px_3px_0_0_var(--tavus-terminal-black)]"
                        }`}
                      >
                        <div className="text-[9px] font-bold tracking-[0.14em] uppercase text-[var(--tavus-hardware-gray-8)] mb-1 flex items-center gap-1">
                          {m.role !== "customer" ? <Send className="w-2.5 h-2.5" strokeWidth={2.5} /> : <User className="w-2.5 h-2.5" strokeWidth={2.5} />}
                          {m.role !== "customer" ? "AI AGENT" : m.role.toUpperCase()}
                        </div>
                        <div className="text-[var(--tavus-terminal-black)] whitespace-pre-wrap break-words">{m.content}</div>
                        <div className="text-[9px] font-medium text-[var(--tavus-hardware-gray-8)] mt-1 text-right">{formatDateTime(m.created_at)}</div>
                      </div>
                    </div>
                  ))
                : null}
            </div>
          </WinCard>

          <div className="bg-[var(--tavus-plastic-2)] border-[2px] border-[var(--tavus-terminal-black)] p-2.5 text-[10px] font-semibold text-[var(--tavus-hardware-gray-8)]">
            This thread is read-only. To reply, open the live chat on the connected channel.
          </div>
        </div>
      </div>
    </div>
  );
}
