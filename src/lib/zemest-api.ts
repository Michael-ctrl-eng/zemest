/**
 * Client-side API helper for the unified Zemest platform.
 *
 * All calls go through the same-origin BFF proxy (`/api/zemest/*`), which
 * attaches the httpOnly auth cookie as a Bearer header server-side.
 * No tokens in localStorage, no CORS, no exposed secrets.
 */

export class ApiError extends Error {
  status: number;
  detail: string;
  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
  }
}

// ---------- Instant cache (stale-while-revalidate) ----------
// Module memory cache + sessionStorage persistence so dashboard stats paint
// INSTANTLY on revisit/navigation instead of showing a loading spinner while
// the network round-trip runs. GETs populate the cache; mutations invalidate it.

type CacheEntry = { data: unknown; ts: number };
const CACHE_PREFIX = "zemest:v1:";
const memCache = new Map<string, CacheEntry>();

function readCache(path: string): CacheEntry | null {
  const mem = memCache.get(path);
  if (mem) return mem;
  if (typeof window !== "undefined") {
    try {
      const raw = sessionStorage.getItem(CACHE_PREFIX + path);
      if (raw) {
        const entry = JSON.parse(raw) as CacheEntry;
        memCache.set(path, entry);
        return entry;
      }
    } catch {
      /* corrupted entry — ignore */
    }
  }
  return null;
}

function writeCache(path: string, data: unknown) {
  const entry = { data, ts: Date.now() };
  memCache.set(path, entry);
  if (typeof window !== "undefined") {
    try {
      sessionStorage.setItem(CACHE_PREFIX + path, JSON.stringify(entry));
    } catch {
      /* quota exceeded — memory cache still works */
    }
  }
}

/** Drop every cached GET (called after any mutation so stats never go stale). */
function invalidateCache() {
  memCache.clear();
  if (typeof window !== "undefined") {
    try {
      Object.keys(sessionStorage)
        .filter((k) => k.startsWith(CACHE_PREFIX))
        .forEach((k) => sessionStorage.removeItem(k));
    } catch {
      /* ignore */
    }
  }
}

// In-flight request dedupe — parallel mounts asking for the same path share one fetch.
const inflight = new Map<string, Promise<unknown>>();

async function request<T = any>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`/api/zemest${path}`, {
    ...options,
    credentials: "same-origin",
    // Bounded request: a hung BFF/backend shows an error instead of an
    // infinite spinner (30s covers the slowest legitimate LLM endpoints).
    signal: options.signal ?? AbortSignal.timeout(30_000),
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });
  if (res.status === 204) return undefined as T;

  const contentType = res.headers.get("content-type") || "";
  const body = contentType.includes("application/json") ? await res.json().catch(() => ({})) : {};

  if (!res.ok) {
    const detail =
      (typeof body.detail === "string" && body.detail) ||
      (Array.isArray(body.detail) && body.detail[0]?.msg) ||
      `Request failed (${res.status})`;
    if (res.status === 401) {
      // Session expired — send to login (middleware also guards this)
      if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
        window.location.href = `/login?redirect=${encodeURIComponent(window.location.pathname)}`;
      }
    }
    throw new ApiError(res.status, detail);
  }
  return body as T;
}

/** GET that populates the instant cache (with in-flight dedupe). */
async function cachedGet<T = any>(path: string): Promise<T> {
  const existing = inflight.get(path);
  if (existing) return existing as Promise<T>;
  const p = request<T>(path)
    .then((data) => {
      writeCache(path, data);
      return data;
    })
    .finally(() => {
      inflight.delete(path);
    });
  inflight.set(path, p);
  return p;
}

export const api = {
  /** Sync stale read — returns cached data IMMEDIATELY (no fetch, no promise). */
  peek<T = any>(path: string): T | null {
    const entry = readCache(path);
    return entry ? (entry.data as T) : null;
  },
  /** GET + cache. Components seed state with api.peek() for instant paint. */
  get: <T = any>(path: string) => cachedGet<T>(path),
  /** GET that bypasses the cache — for health probes where a real round-trip (and its latency) is the point. */
  getFresh: <T = any>(path: string) => request<T>(path),
  /** Background fetch that only warms the cache (hover-prefetch). Fire-and-forget. */
  prefetch: (path: string) => {
    void cachedGet(path).catch(() => undefined);
  },
  post: <T = any>(path: string, data?: unknown) =>
    request<T>(path, { method: "POST", body: data !== undefined ? JSON.stringify(data) : undefined }).then(
      (r) => (invalidateCache(), r)
    ),
  patch: <T = any>(path: string, data?: unknown) =>
    request<T>(path, { method: "PATCH", body: data !== undefined ? JSON.stringify(data) : undefined }).then(
      (r) => (invalidateCache(), r)
    ),
  put: <T = any>(path: string, data?: unknown) =>
    request<T>(path, { method: "PUT", body: data !== undefined ? JSON.stringify(data) : undefined }).then(
      (r) => (invalidateCache(), r)
    ),
  delete: <T = any>(path: string) =>
    request<T>(path, { method: "DELETE" }).then((r) => (invalidateCache(), r)),
};

// ---------- Typed domain helpers ----------

export interface Tenant {
  id: string;
  page_name: string;
  fb_page_id?: string | null;
  website_url: string | null;
  business_phone: string | null;
  business_email: string | null;
  is_active: boolean;
  delivery_inside_cairo: number | string | null;
  delivery_outside_cairo: number | string | null;
  free_delivery_above: number | string | null;
  owner_psid?: string | null;
}

export interface Product {
  id: string;
  name: string;
  price: string | number;
  is_active: boolean;
  source?: string;
  created_at?: string;
  /** Custom attributes (stock, category, color, size, …) */
  attributes?: Record<string, unknown>;
  [key: string]: unknown; // flattened attributes
}

export interface OrderItem {
  id: string;
  product_name: string;
  quantity: number;
  unit_price: string;
  total_price: string;
}

export interface Order {
  id: string;
  order_number: string;
  customer_name: string;
  customer_phone: string;
  governorate: string | null;
  city: string | null;
  status: string;
  subtotal: string | number | null;
  delivery_charge: string | number | null;
  total: string | number | null;
  created_at: string;
  items: OrderItem[];
  payment_method?: string | null;
}

export interface Customer {
  id: string;
  name: string | null;
  phone?: string | null;
  fb_psid?: string | null;
  governorate?: string | null;
  city?: string | null;
  area?: string | null;
  address_detail?: string | null;
  created_at?: string;
  orders_count?: number;
  conversations_count?: number;
  total_spent?: number;
}

export interface ConversationMessage {
  id: string;
  role: string;
  content: string;
  created_at: string;
}

export interface Conversation {
  id: string;
  customer_name: string | null;
  status: string;
  started_at: string;
  last_message_at: string;
  /** List responses are message-free (B8): these carry the summary. */
  last_message_preview?: string;
  message_count?: number;
  /** Detail responses only. */
  messages?: ConversationMessage[];
}

export interface CrawlJob {
  id: string;
  url: string;
  status: string;
  pages_found: number;
  products_extracted: number;
  error_message: string | null;
  created_at: string;
}

export interface TenantStats {
  products_count: number;
  orders_count: number;
  pending_orders: number;
  active_conversations: number;
  total_revenue: number;
  today_orders: number;
  today_revenue: number;
  month_revenue: number;
  customers_count: number;
  top_products: { name: string; qty: number; revenue: number }[];
  recent_orders: {
    order_number: string;
    customer_name: string;
    total: number;
    status: string;
    created_at: string;
  }[];
  total_tokens: number;
  chat_tokens: number;
  crawl_tokens: number;
  llm_calls: number;
}

export interface InsightsOverview {
  facebook: {
    page_name?: string;
    followers?: number;
    fans?: number;
    insights?: unknown[];
    error?: string;
  } | null;
  instagram: { insights?: unknown[]; error?: string } | null;
  period_days: number;
}

// ---------- Shared formatting helpers ----------

/** Backend timestamps come as "2026-08-28T12:39:50.837901" or "2026-08-28 12:39:50". */
export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const d = new Date(value.includes("T") ? value : value.replace(" ", "T"));
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString("en-EG", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: true,
  });
}

export function toNumber(value: string | number | null | undefined): number {
  if (value === null || value === undefined || value === "") return 0;
  const n = typeof value === "number" ? value : Number(value);
  return Number.isFinite(n) ? n : 0;
}

/** Format a decimal-ish money value with thousands separators + EGP suffix. */
export function egp(value: string | number | null | undefined): string {
  return `${toNumber(value).toLocaleString("en-EG", { maximumFractionDigits: 2 })} EGP`;
}

export const tenantsApi = {
  list: () => api.get<Tenant[]>("/tenants"),
  get: (id: string) => api.get<Tenant>(`/tenants/${id}`),
  create: (data: Partial<Tenant>) => api.post<Tenant>("/tenants", data),
  update: (id: string, data: Partial<Tenant>) => api.patch<Tenant>(`/tenants/${id}`, data),
  stats: (id: string) => api.get<TenantStats>(`/tenants/${id}/stats`),
  /** Warm the cache so the tenant overview paints instantly on click-through. */
  prefetchOverview: (id: string) => {
    api.prefetch(`/tenants/${id}`);
    api.prefetch(`/tenants/${id}/stats`);
  },
};

export const productsApi = {
  list: (tenantId: string) => api.get<{ products: Product[]; total: number; page: number; page_size: number }>(`/tenants/${tenantId}/products`),
  create: (tenantId: string, data: Partial<Product>) =>
    api.post<Product>(`/tenants/${tenantId}/products`, data),
};

export const ordersApi = {
  list: (tenantId: string, page = 1) =>
    api.get<{ orders: Order[]; total: number; page: number; page_size: number }>(
      `/tenants/${tenantId}/orders?page=${page}`
    ),
  create: (tenantId: string, data: unknown) => api.post<Order>(`/tenants/${tenantId}/orders`, data),
  updateStatus: (tenantId: string, orderId: string, status: string) =>
    api.patch<Order>(`/tenants/${tenantId}/orders/${orderId}/status`, { status }),
};

export const customersApi = {
  list: (tenantId: string) =>
    api.get<{ customers: Customer[]; total: number; page: number; page_size: number }>(
      `/tenants/${tenantId}/customers`
    ),
};

export const chatApi = {
  send: (tenantId: string, message: string, customerName = "Test Customer") =>
    api.post<{ reply: string; conversation_id: string; customer_id: string; tokens_used: number }>(
      "/test/chat",
      { tenant_id: tenantId, message, customer_name: customerName }
    ),
  /** Owner-mode chat: the merchant talks to the OWNER-side agent
   *  (postiz/scheduling actions), not the customer-side flow. The old
   *  UI posted owner-mode messages to /test/chat — silently creating
   *  fake customer conversations (audit B6). */
  sendOwner: (tenantId: string, message: string) =>
    api.post<{ reply: string; action: string; data: Record<string, unknown> }>(
      "/test/postiz-chat",
      { tenant_id: tenantId, message }
    ),
};

export const conversationsApi = {
  list: (tenantId: string) =>
    api.get<{ conversations: Conversation[]; total: number }>(`/tenants/${tenantId}/conversations`),
  get: (tenantId: string, conversationId: string) =>
    api.get<Conversation>(`/tenants/${tenantId}/conversations/${conversationId}`),
};

// ---------- Style learning (brand voice profile) ----------

/**
 * Learned communication-style profile for a tenant.
 * Core fields come from the style learner; the silent trainer enriches the
 * dict with extra keys (buyer_persona, exemplars, silent_training, …), so the
 * known fields below are all optional and the object stays open-ended.
 */
export interface StyleProfile {
  tone?: string | null;
  formality_level?: number | null;
  greeting_patterns?: string[];
  signoff_patterns?: string[];
  emoji_frequency?: string | null;
  emoji_inventory?: string[];
  avg_response_length?: string | null;
  avg_length_chars?: number | null;
  language_mix?: Record<string, number> | null;
  vocabulary?: string[];
  sample_replies?: string[];
  message_count_analyzed?: number | null;
  total_messages_available?: number | null;
  built_at?: string | null;
  /** Silent-trainer enrichment */
  silent_training?: {
    stage?: string;
    maturity?: number;
    version?: string;
    last_epoch_at?: string | null;
    [key: string]: unknown;
  } | null;
  buyer_persona?: {
    dialects?: Record<string, number> | null;
    franco_ratio?: number | null;
    top_openers?: string[];
    [key: string]: unknown;
  } | null;
  exemplars?: { customer?: string | null; reply?: string | null }[];
  [key: string]: unknown;
}

export interface StyleProfileResponse {
  status: string; // "built" | "not_built"
  built_at?: string | null;
  message?: string | null;
  profile?: StyleProfile | null;
}

export const styleApi = {
  get: (tenantId: string) => api.get<StyleProfileResponse>(`/tenants/${tenantId}/style-profile`),
  /** Rebuild the profile from the merchant messages already in the DB. */
  rebuild: (tenantId: string) =>
    api.post<{ status: string; profile: StyleProfile }>(`/tenants/${tenantId}/rebuild-style`),
};

export const crawlApi = {
  jobs: (tenantId: string) => api.get<CrawlJob[]>(`/tenants/${tenantId}/crawl/jobs`),
  start: (tenantId: string, url: string, depth = 1) =>
    api.post<CrawlJob>(`/tenants/${tenantId}/crawl`, { url, depth }),
};

export const insightsApi = {
  overview: (tenantId: string, days = 30) =>
    api.get<InsightsOverview>(`/tenants/${tenantId}/insights/overview?days=${days}`),
};

export const addressApi = {
  governorates: () => api.get<any[]>("/address/governorates"),
  shipping: (governorate: string, subtotal = 0) =>
    api.get<any>(`/address/shipping?governorate=${encodeURIComponent(governorate)}&subtotal=${subtotal}`),
};

// ---------- Channels (Messenger / Instagram / WhatsApp) ----------

export interface ChannelStatus {
  connected: boolean;
  error: string | null;
  // present when connected
  page_id?: string;
  ig_user_id?: string;
  phone_number_id?: string;
  account_name?: string | null;
  avatar?: string | null;
  category?: string | null;
  followers?: number | null;
  display_phone_number?: string | null;
  verified_name?: string | null;
  quality_rating?: string | null;
  connected_at?: string | null;
}

export interface ChannelsStatus {
  platforms: { messenger: ChannelStatus; instagram: ChannelStatus; whatsapp: ChannelStatus };
  webhook_urls: { messenger: string; instagram: string; whatsapp: string };
  verify_token_configured: boolean;
  oauth: { ready: boolean };
}

export const channelsApi = {
  status: (tenantId: string) => api.get<ChannelsStatus>(`/tenants/${tenantId}/channels`),
  connectMessenger: (tenantId: string, pageAccessToken: string, pageId?: string) =>
    api.post<{ connected: boolean; page_name?: string; webhook_subscribed: boolean; webhook_note?: string | null }>(
      `/tenants/${tenantId}/channels/messenger`,
      { page_access_token: pageAccessToken, page_id: pageId || null }
    ),
  connectInstagram: (tenantId: string, igUserId: string, accessToken: string) =>
    api.post<{ connected: boolean; username?: string }>(`/tenants/${tenantId}/channels/instagram`, {
      ig_user_id: igUserId,
      access_token: accessToken,
    }),
  connectWhatsapp: (tenantId: string, phoneNumberId: string, accessToken: string) =>
    api.post<{ connected: boolean; display_phone_number?: string; verified_name?: string }>(
      `/tenants/${tenantId}/channels/whatsapp`,
      { phone_number_id: phoneNumberId, access_token: accessToken }
    ),
  disconnect: (tenantId: string, platform: string) =>
    api.delete<{ connected: boolean }>(`/tenants/${tenantId}/channels/${platform}`),
  test: (tenantId: string, platform: string, text?: string) =>
    api.post<Record<string, unknown>>(`/tenants/${tenantId}/channels/${platform}/test`, { text }),
};

// ---------- Scheduler (posts) + Calendar ----------

export interface ScheduledPostItem {
  id: string;
  platform: string;
  caption: string;
  media_type: string;
  media_urls: string[];
  scheduled_at: string;
  published_at: string | null;
  status: string;
  platform_post_id: string | null;
  error_message: string | null;
  ai_generated: boolean;
}

export const schedulerApi = {
  list: (tenantId: string) => api.get<{ posts: ScheduledPostItem[]; total: number }>(`/tenants/${tenantId}/schedule/posts`),
  create: (
    tenantId: string,
    data: { platform: string; caption: string; media_type?: string; media_urls?: string[]; link?: string; scheduled_at: string }
  ) => api.post<{ id: string; status: string; scheduled_at: string; platform: string }>(`/tenants/${tenantId}/schedule/post`, data),
  cancel: (tenantId: string, postId: string) =>
    api.patch<{ status: string }>(`/tenants/${tenantId}/schedule/posts/${postId}/status`, { status: "cancelled" }),
  remove: (tenantId: string, postId: string) => api.delete<{ status: string }>(`/tenants/${tenantId}/schedule/posts/${postId}`),
};

export const calendarApi = {
  url: (tenantId: string) => api.get<{ calendar_token: string }>(`/tenants/${tenantId}/calendar/url`),
  rotate: (tenantId: string) => api.post<{ calendar_token: string }>(`/tenants/${tenantId}/calendar/token`),
};

// ---------- Admin panel (superadmin endpoints, proxied via /api/zemest/admin/*) ----------

export interface AdminOverview {
  total_users: number;
  total_tenants: number;
  total_orders: number;
  active_sessions: number;
  blocked_users: number;
  ip_bans: number;
  total_tokens_used: number;
}

export interface AdminAuditLogItem {
  id: number;
  admin_id: string;
  action: string; // "user.block" | "user.unblock" | "ip.ban" | "ip.unban" | …
  target_type: string | null;
  target_id: string | null;
  ip: string | null;
  created_at: string;
}

export interface AdminAuditLogResponse {
  logs: AdminAuditLogItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface AdminIPBan {
  id: string;
  ip_or_cidr: string;
  reason: string | null;
  created_at: string;
}

export interface AdminActiveSession {
  id: string;
  user_id: string;
  ip_address: string;
  country: string | null;
  city: string | null;
  device_type: string | null;
  last_activity: string;
}

export interface AdminUserActivityItem {
  id: string;
  ip_address: string;
  country: string | null;
  city: string | null;
  device_type: string | null;
  browser: string | null;
  login_at: string;
  last_activity: string;
  is_active: boolean;
}

export interface AdminGeoItem {
  country: string;
  user_count: number;
}

export const adminApi = {
  overview: () => api.get<AdminOverview>("/admin/analytics/overview"),
  /** Uncached probe (health checks / superadmin gate fallback) — always hits the backend. */
  overviewProbe: () => api.getFresh<AdminOverview>("/admin/analytics/overview"),
  auditLog: (page = 1, pageSize = 50) =>
    api.get<AdminAuditLogResponse>(`/admin/audit-log?page=${page}&page_size=${pageSize}`),
  ipBans: () => api.get<AdminIPBan[]>("/admin/ip-bans"),
  addIpBan: (ipOrCidr: string, reason?: string | null) =>
    api.post<{ status: string; ip_or_cidr: string }>("/admin/ip-bans", {
      ip_or_cidr: ipOrCidr,
      reason: reason ?? null,
    }),
  removeIpBan: (id: string) =>
    api.delete<{ status: string; ip_or_cidr: string }>(`/admin/ip-bans/${id}`),
  activeSessions: () => api.get<AdminActiveSession[]>("/admin/analytics/active-sessions"),
  userActivity: (userId: string) =>
    api.get<AdminUserActivityItem[]>(`/admin/analytics/user/${userId}/activity`),
  geoDistribution: () => api.get<AdminGeoItem[]>("/admin/analytics/geo-distribution"),
  blockUser: (userId: string, reason?: string | null) =>
    api.post<{ status: string; user_id: string }>(`/admin/users/${userId}/block`, {
      reason: reason ?? null,
    }),
  unblockUser: (userId: string) =>
    api.delete<{ status: string; user_id: string }>(`/admin/users/${userId}/block`),
  // --- Site analytics (first-party click/view tracking) ---
  analyticsPages: (days = 14, worst = true) =>
    api.get<any>(`/admin/analytics/pages?days=${days}&worst=${worst}`),
  analyticsVisitors: (q?: string) =>
    api.get<any>(`/admin/analytics/visitors${q ? `?q=${encodeURIComponent(q)}` : ""}`),
  analyticsStorage: () => api.get<any>("/admin/analytics/storage"),
  // --- Support reports ---
  adminReports: (status?: string) =>
    api.get<any>(`/admin/reports${status ? `?status=${status}` : ""}`),
  updateReport: (id: string, status: string, adminNote?: string | null) =>
    api.patch<any>(`/admin/reports/${id}`, {
      status,
      admin_note: adminNote ?? null,
    }),
};

export interface MyReport {
  id: string;
  code: string;
  title: string;
  subject: string;
  status: string;
  created_at: string | null;
  updated_at: string | null;
  resolved_at: string | null;
}

export const reportsApi = {
  list: () => api.get<MyReport[]>("/reports"),
  create: (title: string, subject: string) =>
    api.post<MyReport>("/reports", { title, subject }),
};

/** Human-friendly message for a thrown ApiError (403 gets a clear access-denied text). */
export function apiErrorMessage(err: unknown, fallback = "Failed to load data"): string {
  if (err instanceof ApiError) {
    if (err.status === 403) return "Access denied — this page requires superadmin privileges.";
    return err.detail || `Request failed (${err.status})`;
  }
  if (err instanceof Error && err.message) return err.message;
  return fallback;
}

export interface Me {
  id: string;
  name: string;
  email: string | null;
  fb_user_id: string | null;
  is_superadmin: boolean;
}

export const authApi = {
  // These go through the dedicated BFF auth routes (they set the cookie)
  login: async (email: string, password: string, remember = false) => {
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, remember }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new ApiError(res.status, body.detail || "Invalid email or password");
    }
    return res.json();
  },
  register: async (name: string, email: string, password: string) => {
    const res = await fetch("/api/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, email, password }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new ApiError(res.status, body.detail || "Registration failed");
    }
    return res.json();
  },
  me: () => api.get<Me>("/auth/me"),
};
