import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Format a number as EGP currency.
 * Uses Intl.NumberFormat for locale-aware formatting.
 * @param amount - The amount in EGP
 * @param locale - 'ar-EG' for Arabic, 'en-US' for English
 */
export function formatCurrency(amount: number, locale: string = "en-US"): string {
  return new Intl.NumberFormat(locale, {
    style: "currency",
    currency: "EGP",
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(amount);
}

/**
 * Format a number with thousand separators.
 */
export function formatNumber(num: number, locale: string = "en-US"): string {
  return new Intl.NumberFormat(locale).format(num);
}

/**
 * Format a date for display.
 * Always stored as UTC, converted to Africa/Cairo for display.
 */
export function formatDate(date: Date | string, locale: string = "en-US"): string {
  const d = typeof date === "string" ? new Date(date) : date;
  return new Intl.DateTimeFormat(locale, {
    timeZone: "Africa/Cairo",
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(d);
}

/**
 * Format a date as a relative time (e.g., "2 min ago").
 */
export function formatRelativeTime(date: Date | string): string {
  const d = typeof date === "string" ? new Date(date) : date;
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHour = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHour / 24);

  if (diffSec < 60) return "just now";
  if (diffMin < 60) return `${diffMin} min ago`;
  if (diffHour < 24) return `${diffHour} hour${diffHour > 1 ? "s" : ""} ago`;
  if (diffDay < 30) return `${diffDay} day${diffDay > 1 ? "s" : ""} ago`;
  return formatDate(d);
}

/**
 * Truncate text to a maximum length.
 */
export function truncate(text: string, maxLen: number = 50): string {
  if (text.length <= maxLen) return text;
  return text.slice(0, maxLen) + "...";
}

/**
 * Debounce a function call.
 * Used for search inputs (300ms per PDF spec).
 */
export function debounce<T extends (...args: any[]) => void>(
  fn: T,
  delay: number = 300
): (...args: Parameters<T>) => void {
  let timeoutId: ReturnType<typeof setTimeout>;
  return (...args: Parameters<T>) => {
    clearTimeout(timeoutId);
    timeoutId = setTimeout(() => fn(...args), delay);
  };
}

/**
 * Generate an order number like "ORD-260827-001"
 */
export function generateOrderNumber(): string {
  const now = new Date();
  const yy = String(now.getFullYear()).slice(2);
  const mm = String(now.getMonth() + 1).padStart(2, "0");
  const dd = String(now.getDate()).padStart(2, "0");
  const random = Math.floor(Math.random() * 999).toString().padStart(3, "0");
  return `ORD-${yy}${mm}${dd}-${random}`;
}

/**
 * Egyptian phone number validation
 * Must match 01XXXXXXXXX format
 */
export function validateEgyptianPhone(phone: string): boolean {
  return /^01[0125][0-9]{8}$/.test(phone);
}

/**
 * Get status color for badges.
 */
export function getStatusColor(status: string): string {
  const colors: Record<string, string> = {
    // Order statuses
    pending: "var(--tavus-atomic-glow-5)",
    confirmed: "var(--tavus-frost-4)",
    shipped: "var(--tavus-floppy-fog-1)",
    delivered: "var(--tavus-neon-field-2)",
    cancelled: "var(--tavus-bubbletech-1)",
    // API statuses
    not_configured: "var(--tavus-plastic-2)",
    success: "var(--tavus-neon-field-2)",
    failed: "var(--tavus-bubbletech-4)",
    // Conversation statuses
    active: "var(--tavus-neon-field-2)",
    imported: "var(--tavus-frost-4)",
    order_placed: "var(--tavus-bubbletech-4)",
    // Product stock
    in_stock: "var(--tavus-neon-field-2)",
    out_of_stock: "var(--tavus-bubbletech-4)",
    limited: "var(--tavus-atomic-glow-5)",
    // Crawl job statuses
    crawling: "var(--tavus-frost-4)",
    indexing: "var(--tavus-floppy-fog-1)",
    completed: "var(--tavus-neon-field-2)",
  };
  return colors[status] || "var(--tavus-plastic-2)";
}
