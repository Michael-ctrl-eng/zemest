"use client";

/**
 * Zemest first-party analytics tracker.
 *
 * Design (product requirement: "analysis for every click and views" with
 * NO third-party script and NO PII leaving the browser):
 * - anonymous visitor id (localStorage) + session id (sessionStorage)
 * - page_view on every route change, click on any element (label from
 *   data-analytics or the element text), max scroll depth per page
 * - session_end on page hide (sendBeacon) with pages-per-session
 * - batches flush to /api/zemest/analytics/collect (the BFF route →
 *   FastAPI). Logged-in users are linked SERVER-SIDE from the httpOnly
 *   cookie — this script never reads or sends identity data.
 */

import { useEffect, useRef } from "react";
import { usePathname } from "next/navigation";

type EventType = "page_view" | "click" | "scroll" | "session_end";

interface TrackedEvent {
  type: EventType;
  path: string;
  page_name?: string;
  element?: string;
  scroll?: number;
  session_pages?: number;
}

const FLUSH_INTERVAL_MS = 5_000;
const MAX_BUFFER = 40;
const SESSION_TIMEOUT_MS = 30 * 60 * 1_000;
const COLLECT_URL = "/api/zemest/analytics/collect";

function uuid4(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  // Fallback for older browsers
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    return (c === "x" ? r : (r & 0x3) | 0x8).toString(16);
  });
}

function getVisitorId(): string {
  try {
    let id = localStorage.getItem("zemest_visitor");
    if (!id) {
      id = `v-${uuid4()}`;
      localStorage.setItem("zemest_visitor", id);
    }
    return id;
  } catch {
    return "v-anon";
  }
}

function getSessionId(): string {
  try {
    const now = Date.now();
    let raw = sessionStorage.getItem("zemest_session");
    if (raw) {
      const { id, ts } = JSON.parse(raw) as { id: string; ts: number };
      if (now - ts < SESSION_TIMEOUT_MS) {
        sessionStorage.setItem("zemest_session", JSON.stringify({ id, ts: now }));
        return id;
      }
    }
    const id = `s-${uuid4()}`;
    sessionStorage.setItem("zemest_session", JSON.stringify({ id, ts: now }));
    return id;
  } catch {
    return "s-anon";
  }
}

export function AnalyticsTracker() {
  const pathname = usePathname() || "/";
  const bufferRef = useRef<TrackedEvent[]>([]);
  const scrollRef = useRef(0);
  const pagesRef = useRef(0);
  const flushTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    const visitor = getVisitorId();
    const session = getSessionId();
    const buffer = bufferRef.current;

    const flush = (useBeacon = false) => {
      if (buffer.length === 0) return;
      const events = buffer.splice(0, buffer.length);
      const body = JSON.stringify({ visitor, session, events });
      if (useBeacon && typeof navigator !== "undefined" && navigator.sendBeacon) {
        navigator.sendBeacon(
          COLLECT_URL,
          new Blob([body], { type: "application/json" })
        );
      } else {
        void fetch(COLLECT_URL, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body,
          keepalive: true,
        }).catch(() => {
          /* analytics must never surface errors */
        });
      }
    };

    const push = (event: TrackedEvent) => {
      buffer.push(event);
      if (buffer.length >= MAX_BUFFER) flush();
    };

    // --- page_view on mount + route change ---
    scrollRef.current = 0;
    pagesRef.current += 1;
    push({
      type: "page_view",
      path: pathname,
      page_name: typeof document !== "undefined" ? document.title : undefined,
    });

    // --- scroll depth (max %) ---
    const onScroll = () => {
      if (typeof document === "undefined") return;
      const doc = document.documentElement;
      const max = doc.scrollHeight - window.innerHeight;
      if (max <= 0) return;
      const pct = Math.min(
        100,
        Math.round(((window.scrollY + window.innerHeight) / doc.scrollHeight) * 100)
      );
      if (pct > scrollRef.current) scrollRef.current = pct;
    };

    // --- click tracking with a friendly element label ---
    const onClick = (e: MouseEvent) => {
      const target = e.target as HTMLElement | null;
      if (!target) return;
      const labelled = target.closest<HTMLElement>("[data-analytics-label]");
      const label =
        labelled?.dataset.analyticsLabel ||
        target.getAttribute("aria-label") ||
        target.textContent?.trim().slice(0, 60) ||
        target.tagName.toLowerCase();
      push({ type: "click", path: pathname, element: label });
    };

    // --- flush the pending scroll value before leaving a page ---
    const emitScroll = () => {
      if (scrollRef.current > 0) {
        push({ type: "scroll", path: pathname, scroll: scrollRef.current });
        scrollRef.current = 0;
      }
    };

    const onPageHide = () => {
      emitScroll();
      push({ type: "session_end", path: pathname, session_pages: pagesRef.current });
      flush(true);
    };

    window.addEventListener("scroll", onScroll, { passive: true });
    document.addEventListener("click", onClick, { passive: true });
    window.addEventListener("pagehide", onPageHide);
    flushTimerRef.current = setInterval(flush, FLUSH_INTERVAL_MS);

    return () => {
      emitScroll();
      window.removeEventListener("scroll", onScroll);
      document.removeEventListener("click", onClick);
      window.removeEventListener("pagehide", onPageHide);
      if (flushTimerRef.current) clearInterval(flushTimerRef.current);
      flush();
    };
    // pathname: re-run on route change; the rest are stable references
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname]);

  return null;
}

export default AnalyticsTracker;
