"use client";

/**
 * ZEMEST × TAVUS design kit — the ONE source of truth for the dashboard UI.
 * Rules (extracted from tavus.io production, Aug 2026):
 *  - 3px terminal-black borders, hard offset shadows (no blur)
 *  - win-title-bar OS window chrome with traffic dot
 *  - halftone dot texture overlays on cards
 *  - Instrument Serif display headings, italic last word
 *  - uppercase wide-tracked eyebrow labels
 *  - Zemest palette ONLY — raw tailwind colors are FORBIDDEN
 */
import type { ReactNode } from "react";
import Link from "next/link";
import { Loader2, AlertTriangle, RefreshCw } from "lucide-react";

/* ------------------------------------------------------------------ */
/* Status system — Zemest palette only                                  */
/* ------------------------------------------------------------------ */

export const STATUS_STYLE: Record<string, { bg: string; fg: string }> = {
  pending:    { bg: "var(--tavus-atomic-glow-5)", fg: "var(--tavus-terminal-black)" }, // pale amber
  confirmed:  { bg: "var(--tavus-bubbletech-4)",  fg: "var(--tavus-terminal-black)" }, // blue
  shipped:    { bg: "var(--tavus-floppy-fog-3)",  fg: "var(--tavus-terminal-black)" }, // lavender
  delivered:  { bg: "var(--tavus-signal-green)",  fg: "var(--tavus-terminal-black)" }, // electric green
  cancelled:  { bg: "var(--tavus-coral-1)",       fg: "var(--tavus-white)" },          // hot coral
  completed:  { bg: "var(--tavus-signal-green)",  fg: "var(--tavus-terminal-black)" },
  failed:     { bg: "var(--tavus-coral-1)",       fg: "var(--tavus-white)" },
  running:    { bg: "var(--tavus-bubbletech-4)",  fg: "var(--tavus-terminal-black)" },
  active:     { bg: "var(--tavus-signal-green)",  fg: "var(--tavus-terminal-black)" },
  open:       { bg: "var(--tavus-bubbletech-4)",  fg: "var(--tavus-terminal-black)" },
  closed:     { bg: "var(--tavus-plastic-2)",     fg: "var(--tavus-terminal-black)" },
  in_stock:   { bg: "var(--tavus-signal-green)",  fg: "var(--tavus-terminal-black)" },
  low_stock:  { bg: "var(--tavus-atomic-glow-1)", fg: "var(--tavus-terminal-black)" },
  out_of_stock: { bg: "var(--tavus-coral-1)",     fg: "var(--tavus-white)" },
  waiting:    { bg: "var(--tavus-atomic-glow-5)", fg: "var(--tavus-terminal-black)" },
  resolved:   { bg: "var(--tavus-signal-green)",  fg: "var(--tavus-terminal-black)" },
  handed_off: { bg: "var(--tavus-keyboard-tan-1)", fg: "var(--tavus-terminal-black)" },
};

export function StatusBadge({ status, children }: { status: string; children?: ReactNode }) {
  const s = STATUS_STYLE[status?.toLowerCase?.() ?? ""] ?? {
    bg: "var(--tavus-plastic-2)",
    fg: "var(--tavus-terminal-black)",
  };
  return (
    <span
      className="inline-flex items-center px-2 py-0.5 text-[9px] font-extrabold tracking-[0.12em] uppercase border-[1.5px] border-[var(--tavus-terminal-black)] whitespace-nowrap"
      style={{ background: s.bg, color: s.fg }}
    >
      {children ?? status}
    </span>
  );
}

/* ------------------------------------------------------------------ */
/* Window card — the signature Zemest OS-window container               */
/* ------------------------------------------------------------------ */

export function WinCard({
  title,
  dot = "var(--tavus-bubbletech-4)",
  action,
  children,
  className = "",
  contentClassName = "",
}: {
  title: string;
  dot?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
  contentClassName?: string;
}) {
  return (
    <div
      className={`relative bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[6px_6px_0_0_var(--tavus-terminal-black)] overflow-hidden ${className}`}
    >
      <div className="absolute inset-0 bg-halftone-light opacity-[0.35] pointer-events-none" />
      <div className="win-title-bar relative justify-between">
        <span className="flex items-center gap-2 min-w-0">
          <span
            className="w-2.5 h-2.5 border border-[var(--tavus-terminal-black)] shrink-0"
            style={{ background: dot }}
          />
          <span className="text-[10px] font-extrabold tracking-[0.18em] uppercase truncate">{title}</span>
        </span>
        {action ? <span className="shrink-0">{action}</span> : null}
      </div>
      <div className={`relative ${contentClassName}`}>{children}</div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Stat tile — big number, icon box, color chip                        */
/* ------------------------------------------------------------------ */

export function StatTile({
  label,
  value,
  sub,
  icon,
  color = "var(--tavus-bubbletech-4)",
}: {
  label: string;
  value: string;
  sub?: string;
  icon?: ReactNode;
  color?: string;
}) {
  return (
    <div className="relative bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[4px_4px_0_0_var(--tavus-terminal-black)] p-4 overflow-hidden">
      <div className="absolute inset-0 bg-halftone-light opacity-[0.35] pointer-events-none" />
      <div className="relative flex items-start justify-between mb-3">
        {icon ? (
          <span className="flex items-center justify-center w-9 h-9 border-[2px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-plastic-1)]">
            {icon}
          </span>
        ) : (
          <span />
        )}
        <span
          className="w-3.5 h-3.5 border border-[var(--tavus-terminal-black)]"
          style={{ background: color }}
          aria-hidden
        />
      </div>
      <div className="relative text-[26px] leading-none font-extrabold tracking-tight text-[var(--tavus-terminal-black)] tabular-nums">
        {value}
      </div>
      <div className="relative text-[9px] font-extrabold tracking-[0.18em] uppercase text-[var(--tavus-hardware-gray-8)] mt-1.5">
        {label}
      </div>
      {sub ? (
        <div className="relative text-[10px] font-semibold text-[var(--tavus-hardware-gray-8)] mt-1">{sub}</div>
      ) : null}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Page header — eyebrow + serif display title with italic tail        */
/* ------------------------------------------------------------------ */

export function DashHeader({
  eyebrow,
  title,
  tail,
  action,
}: {
  eyebrow: string;
  title: string;
  tail?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex items-start justify-between flex-wrap gap-4">
      <div className="min-w-0">
        <div className="inline-flex items-center gap-2 mb-2.5">
          <span className="w-2 h-2 bg-[var(--tavus-terminal-black)]" />
          <span className="text-[10px] font-extrabold tracking-[0.22em] uppercase text-[var(--tavus-hardware-gray-8)]">
            {eyebrow}
          </span>
        </div>
        <h1 className="font-serif text-3xl sm:text-4xl font-normal tracking-tight text-[var(--tavus-terminal-black)] leading-[1.05]">
          {title}
          {tail ? <span className="serif-italic"> {tail}</span> : null}
        </h1>
      </div>
      {action ? <div className="shrink-0 flex items-center gap-2">{action}</div> : null}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Buttons — chunky Zemest style                                        */
/* ------------------------------------------------------------------ */

const btnBase =
  "inline-flex items-center justify-center gap-2 h-10 px-4 border-[2.5px] border-[var(--tavus-terminal-black)] text-[11px] font-extrabold tracking-[0.1em] uppercase transition-all select-none disabled:opacity-50 disabled:pointer-events-none";

export function TavusButton({
  children,
  variant = "primary",
  className = "",
  ...rest
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "danger" | "dark" }) {
  const styles = {
    primary:
      "bg-[var(--tavus-bubbletech-4)] text-[var(--tavus-terminal-black)] shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:shadow-[4px_4px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-0.5 active:translate-y-0.5 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)]",
    secondary:
      "bg-white text-[var(--tavus-terminal-black)] shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:bg-[var(--tavus-plastic-1)] hover:shadow-[4px_4px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-0.5 active:translate-y-0.5 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)]",
    danger:
      "bg-[var(--tavus-coral-1)] text-white shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:shadow-[4px_4px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-0.5 active:translate-y-0.5 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)]",
    dark:
      "bg-[var(--tavus-terminal-black)] text-white shadow-[3px_3px_0_0_var(--tavus-hardware-gray-8)] hover:shadow-[4px_4px_0_0_var(--tavus-hardware-gray-8)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-0.5 active:translate-y-0.5 active:shadow-[1px_1px_0_0_var(--tavus-hardware-gray-8)]",
  }[variant];
  return (
    <button className={`${btnBase} ${styles} ${className}`} {...rest}>
      {children}
    </button>
  );
}

export function TavusLink({
  children,
  variant = "primary",
  className = "",
  ...rest
}: React.ComponentProps<typeof Link> & { variant?: "primary" | "secondary" | "danger" | "dark" }) {
  const styles = {
    primary:
      "bg-[var(--tavus-bubbletech-4)] text-[var(--tavus-terminal-black)] shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:shadow-[4px_4px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-0.5 active:translate-y-0.5 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)]",
    secondary:
      "bg-white text-[var(--tavus-terminal-black)] shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:bg-[var(--tavus-plastic-1)] hover:shadow-[4px_4px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-0.5 active:translate-y-0.5 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)]",
    danger:
      "bg-[var(--tavus-coral-1)] text-white shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:shadow-[4px_4px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-0.5 active:translate-y-0.5 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)]",
    dark:
      "bg-[var(--tavus-terminal-black)] text-white shadow-[3px_3px_0_0_var(--tavus-hardware-gray-8)] hover:shadow-[4px_4px_0_0_var(--tavus-hardware-gray-8)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-0.5 active:translate-y-0.5 active:shadow-[1px_1px_0_0_var(--tavus-hardware-gray-8)]",
  }[variant];
  return (
    <Link className={`${btnBase} ${styles} ${className}`} {...rest}>
      {children}
    </Link>
  );
}

/* ------------------------------------------------------------------ */
/* Table shell — consistent data tables                                */
/* ------------------------------------------------------------------ */

export function TableShell({ children }: { children: ReactNode }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left border-collapse">{children}</table>
    </div>
  );
}

export function Th({ children, className = "" }: { children?: ReactNode; className?: string }) {
  return (
    <th
      className={`px-4 py-2.5 text-[9px] font-extrabold tracking-[0.16em] uppercase text-[var(--tavus-hardware-gray-8)] border-b-[2px] border-[var(--tavus-terminal-black)] whitespace-nowrap ${className}`}
    >
      {children}
    </th>
  );
}

export function Td({ children, className = "" }: { children?: ReactNode; className?: string }) {
  return (
    <td className={`px-4 py-3 text-[13px] font-semibold text-[var(--tavus-terminal-black)] align-middle ${className}`}>
      {children}
    </td>
  );
}

export function Row({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <tr className={`border-b border-[var(--tavus-terminal-black)]/10 hover:bg-[var(--tavus-plastic-1)]/70 transition-colors ${className}`}>
      {children}
    </tr>
  );
}

/* ------------------------------------------------------------------ */
/* Loading / error / empty states — branded                            */
/* ------------------------------------------------------------------ */

export function LoadingState({ label = "Loading" }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 gap-3">
      <Loader2 className="w-6 h-6 animate-spin text-[var(--tavus-terminal-black)]" strokeWidth={2.5} />
      <span className="text-[10px] font-extrabold tracking-[0.22em] uppercase text-[var(--tavus-hardware-gray-8)]">
        {label}…
      </span>
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="m-4 flex flex-col items-center justify-center gap-3 border-[3px] border-[var(--tavus-coral-1)] bg-[var(--tavus-coral-3)]/40 px-6 py-10 text-center">
      <AlertTriangle className="w-7 h-7 text-[var(--tavus-terminal-black)]" strokeWidth={2.5} />
      <p className="text-sm font-bold text-[var(--tavus-terminal-black)] max-w-md">{message}</p>
      {onRetry ? (
        <TavusButton variant="secondary" onClick={onRetry}>
          <RefreshCw className="w-3.5 h-3.5" /> Retry
        </TavusButton>
      ) : null}
    </div>
  );
}

export function EmptyState({
  icon,
  title,
  hint,
  action,
}: {
  icon?: ReactNode;
  title: string;
  hint?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-12 text-center">
      <div className="flex items-center justify-center w-14 h-14 border-[3px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-plastic-2)] shadow-[4px_4px_0_0_var(--tavus-terminal-black)] mb-5">
        {icon}
      </div>
      <p className="text-[11px] font-extrabold tracking-[0.2em] uppercase text-[var(--tavus-terminal-black)]">{title}</p>
      {hint ? (
        <p className="text-[12px] font-medium text-[var(--tavus-hardware-gray-8)] mt-2 max-w-sm leading-relaxed">{hint}</p>
      ) : null}
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Inputs — Zemest form fields                                          */
/* ------------------------------------------------------------------ */

export const inputClass =
  "w-full h-11 px-3.5 bg-white border-[2.5px] border-[var(--tavus-terminal-black)] text-sm font-semibold text-[var(--tavus-terminal-black)] placeholder:text-[var(--tavus-hardware-gray-8)]/60 placeholder:font-medium focus:outline-none focus:shadow-[3px_3px_0_0_var(--tavus-terminal-black)] transition-shadow";

export const labelClass =
  "block text-[9px] font-extrabold tracking-[0.18em] uppercase text-[var(--tavus-hardware-gray-8)] mb-1.5";

export function Field({
  label,
  children,
  className = "",
}: {
  label: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <label className={`block ${className}`}>
      <span className={labelClass}>{label}</span>
      {children}
    </label>
  );
}
