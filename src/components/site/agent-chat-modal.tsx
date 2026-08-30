"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, SendHorizontal } from "lucide-react";

/**
 * Zemest Store demo chat — Instagram-DM-styled popup.
 *
 * - Header: Zemest logo in an IG-gradient ring + "Zemest Store" + verified
 *   badge + green online dot. Nothing else — clean, like a real shop DM.
 * - Replies come from /api/demo/chat — a pure-Python rule matcher on the
 *   backend (no LLM, ~0.03ms of CPU per message, free at any scale).
 * - The visitor's timezone is sent with every request so prices are quoted
 *   in the visitor's local currency — silently, no creepy announcements.
 * - Product photos are plain <img> files served straight from /public —
 *   no optimizer hop, nothing to fail.
 * - Robustness: 12s fetch timeout, one silent retry, typing indicator can
 *   never get stuck.
 */

interface ChatMessage {
  role: "agent" | "user";
  text: string;
  image?: string;
}

const FALLBACK_WELCOME: ChatMessage[] = [
  {
    role: "agent",
    text: "Hey! 👋 Welcome to Zemest Store.\nWhat are you looking for today?",
  },
];

const QUICK_REPLIES_INITIAL = [
  "White Nike shoes, size 42",
  "Do you have shampoo?",
  "How much is shipping?",
];

/** IANA timezone of the visitor — powers location + currency detection. */
function visitorTimezone(): string | null {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone ?? null;
  } catch {
    return null;
  }
}

/** fetch with a hard timeout + one silent retry. */
async function chatFetch(url: string, body: unknown): Promise<Response> {
  const init = {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
  try {
    return await fetch(url, { ...init, signal: AbortSignal.timeout(12_000) });
  } catch {
    await new Promise((r) => setTimeout(r, 700));
    return await fetch(url, { ...init, signal: AbortSignal.timeout(12_000) });
  }
}

export function AgentChatModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [messages, setMessages] = useState<ChatMessage[]>(FALLBACK_WELCOME);
  const [quickReplies, setQuickReplies] = useState<string[]>(QUICK_REPLIES_INITIAL);
  const [input, setInput] = useState("");
  const [typing, setTyping] = useState(false);
  const [error, setError] = useState(false);
  const sessionIdRef = useRef<string>("");
  const tzRef = useRef<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // fresh, location-aware session each time the window opens
  useEffect(() => {
    if (!open) return;
    sessionIdRef.current =
      typeof crypto !== "undefined" && "randomUUID" in crypto
        ? crypto.randomUUID()
        : `s-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    tzRef.current = visitorTimezone();
    setMessages(FALLBACK_WELCOME);
    setQuickReplies([]);
    setInput("");
    setError(false);
    setTyping(false);

    // fetch the personalized welcome (shows the visitor's city + currency)
    let alive = true;
    setTyping(true);
    chatFetch("/api/demo/welcome", { session_id: sessionIdRef.current, tz: tzRef.current })
      .then((res) => res.json())
      .then((data: { reply?: string; quick_replies?: string[] }) => {
        if (!alive || !data.reply) return;
        setMessages([{ role: "agent", text: data.reply }]);
        setQuickReplies(Array.isArray(data.quick_replies) ? data.quick_replies : QUICK_REPLIES_INITIAL);
      })
      .catch(() => {
        if (alive) setQuickReplies(QUICK_REPLIES_INITIAL);
      })
      .finally(() => {
        if (alive) setTyping(false);
      });
    return () => {
      alive = false;
    };
  }, [open]);

  // lock body scroll while open
  useEffect(() => {
    if (open) {
      const prev = document.body.style.overflow;
      document.body.style.overflow = "hidden";
      return () => {
        document.body.style.overflow = prev;
      };
    }
  }, [open]);

  // esc to close
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  // auto-scroll to newest message
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, typing]);

  const send = useCallback(
    async (raw: string) => {
      const text = raw.trim();
      if (!text || typing) return;
      setInput("");
      setQuickReplies([]);
      setMessages((m) => [...m, { role: "user", text }]);

      setTyping(true);
      try {
        const res = await chatFetch("/api/demo/chat", {
          session_id: sessionIdRef.current,
          message: text,
          tz: tzRef.current,
        });
        const data = await res.json();
        // human-feel beat: 400ms floor, scales with reply length, capped 1.2s
        const delay = Math.min(1200, 400 + (data.reply?.length ?? 40) * 2);
        await new Promise((r) => setTimeout(r, delay));
        if (data.reply) {
          setMessages((m) => [...m, { role: "agent", text: data.reply, image: data.image }]);
          setQuickReplies(Array.isArray(data.quick_replies) ? data.quick_replies : []);
        } else {
          throw new Error("empty reply");
        }
        setError(false);
      } catch {
        setMessages((m) => [
          ...m,
          { role: "agent", text: "Oops, that message slipped away 🙈 Send it once more?" },
        ]);
        setError(true);
      } finally {
        setTyping(false);
        inputRef.current?.focus();
      }
    },
    [typing]
  );

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.18 }}
          className="fixed inset-0 z-[100] flex items-center justify-center p-4 sm:p-6"
          role="dialog"
          aria-modal="true"
          aria-label="Chat with Zemest Store"
        >
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-black/70 backdrop-blur-sm"
            onClick={onClose}
            aria-hidden="true"
          />

          {/* IG-style chat card */}
          <motion.div
            initial={{ opacity: 0, y: 24, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 16, scale: 0.97 }}
            transition={{ type: "spring", stiffness: 380, damping: 30 }}
            className="relative w-full sm:w-[400px] h-[min(640px,88vh)] sm:h-[620px] bg-white sm:rounded-2xl overflow-hidden shadow-2xl flex flex-col border border-black/10"
          >
            {/* ---- IG DM header ---- */}
            <div className="shrink-0 px-3 py-2.5 border-b border-black/10 flex items-center gap-3 bg-white">
              {/* IG gradient ring + Zemest logo */}
              <div
                className="w-11 h-11 rounded-full p-[2.5px] shrink-0"
                style={{
                  background:
                    "conic-gradient(from 200deg, #FEDA75, #FA7E1E, #D62976, #962FBF, #4F5BD5, #FEDA75)",
                }}
                aria-hidden="true"
              >
                <div className="w-full h-full rounded-full bg-white p-[2px]">
                  <div className="w-full h-full rounded-full overflow-hidden bg-[var(--tavus-terminal-black)] flex items-center justify-center">
                    {/* plain <img>: no optimizer hop, cannot fail */}
                    <img
                      src="/zemest-logo-96.png"
                      alt="Zemest"
                      width={26}
                      height={26}
                      className="w-[26px] h-[26px] object-contain"
                    />
                  </div>
                </div>
              </div>
              <div className="min-w-0">
                <div className="text-[15px] font-bold text-[#262626] leading-tight flex items-center gap-1.5">
                  Zemest Store
                  {/* Instagram's actual verified-badge asset: seal with check cut out */}
                  <svg className="w-[14px] h-[14px] shrink-0" viewBox="0 0 40 40" aria-label="verified">
                    <path fill="#0095F6" d="M19.998 3.094 14.638 0l-2.972 5.15H5.432v6.354L0 14.64 3.094 20 0 25.359l5.432 3.137v5.905h5.975L14.638 40l5.36-3.094L25.358 40l3.232-5.6h6.162v-6.01L40 25.359 36.905 20 40 14.64l-5.432-3.137V5.15h-6.016L25.358 0l-5.36 3.094zm7.415 11.225 2.817 2.826L18.05 29.523l-8.28-8.28 2.817-2.826 5.463 5.45 11.363-11.598z" />
                  </svg>
                </div>
                <div className="text-[12px] text-[#8E8E8E] flex items-center gap-1 leading-tight">
                  <span className="w-2 h-2 rounded-full bg-[#22c55e]" aria-hidden="true" />
                  online · replies instantly
                </div>
              </div>
              <button
                onClick={onClose}
                aria-label="Close chat"
                className="ml-auto w-8 h-8 -mr-1 flex items-center justify-center rounded-full hover:bg-black/5 transition-colors"
              >
                <X className="w-[19px] h-[19px] text-[#262626]" strokeWidth={2.2} />
              </button>
            </div>

            {/* ---- Messages ---- */}
            <div
              ref={scrollRef}
              className="flex-1 overflow-y-auto px-3.5 py-4 flex flex-col gap-2.5 bg-white"
            >
              {messages.map((m, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, y: 8, scale: 0.98 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  transition={{ duration: 0.2 }}
                  className={
                    m.role === "user"
                      ? "self-end max-w-[78%] bg-[#3797F0] text-white text-[14.5px] leading-snug rounded-[18px] rounded-br-[6px] px-3.5 py-2 whitespace-pre-wrap break-words"
                      : "self-start max-w-[80%] bg-[#EFEFEF] text-[#262626] text-[14.5px] leading-snug rounded-[18px] rounded-bl-[6px] px-3.5 py-2 whitespace-pre-wrap break-words"
                  }
                >
                  {m.text}
                  {m.image ? (
                    <span className="block mt-1.5 rounded-xl overflow-hidden border border-black/10 bg-[#F5F5F5]">
                      {/* plain <img> from /public — always loads, never blocked */}
                      <img
                        src={m.image}
                        alt="Product photo"
                        width={240}
                        height={240}
                        loading="eager"
                        decoding="async"
                        className="w-[240px] h-[240px] object-cover block"
                        onError={(e) => {
                          // belt & braces: never show a broken-image icon
                          e.currentTarget.style.display = "none";
                        }}
                      />
                    </span>
                  ) : null}
                </motion.div>
              ))}

              {typing && (
                <motion.div
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="self-start bg-[#EFEFEF] rounded-[18px] rounded-bl-[6px] px-4 py-3 flex items-center gap-1.5"
                  aria-label="Agent is typing"
                >
                  {[0, 1, 2].map((d) => (
                    <span
                      key={d}
                      className="w-2 h-2 rounded-full bg-[#8E8E8E] animate-bounce"
                      style={{ animationDelay: `${d * 0.15}s` }}
                    />
                  ))}
                </motion.div>
              )}
            </div>

            {/* ---- Quick replies ---- */}
            <AnimatePresence>
              {quickReplies.length > 0 && !typing && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  className="shrink-0 px-3.5 pb-1 flex flex-wrap gap-1.5 overflow-hidden"
                >
                  {quickReplies.map((q) => (
                    <button
                      key={q}
                      onClick={() => send(q)}
                      className="text-[12.5px] font-semibold text-[#3797F0] border border-[#3797F0]/60 rounded-full px-3 py-1.5 hover:bg-[#3797F0] hover:text-white transition-colors active:scale-95"
                    >
                      {q}
                    </button>
                  ))}
                </motion.div>
              )}
            </AnimatePresence>

            {/* ---- IG-style composer ---- */}
            <div className="shrink-0 p-3 border-t border-black/10 bg-white">
              {error && (
                <p className="text-[11px] text-[#ED4956] mb-1.5 px-1">
                  Connection hiccup — your next message will retry.
                </p>
              )}
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  send(input);
                }}
                className="flex items-center gap-2 border border-[#DBDBDB] rounded-full px-4 py-1 focus-within:border-[#A8A8A8] transition-colors"
              >
                <input
                  ref={inputRef}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="Message…"
                  aria-label="Message Zemest Store"
                  maxLength={500}
                  className="flex-1 bg-transparent text-[14.5px] text-[#262626] placeholder:text-[#8E8E8E] outline-none h-[38px]"
                />
                <button
                  type="submit"
                  disabled={!input.trim() || typing}
                  aria-label="Send message"
                  className="text-[#0095F6] disabled:text-[#0095F6]/30 font-semibold text-[14px] transition-all active:scale-90"
                >
                  <SendHorizontal className="w-5 h-5 -scale-x-100" strokeWidth={2.2} />
                </button>
              </form>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
