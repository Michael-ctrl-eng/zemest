/**
 * Zemest API Client
 *
 * Uses fetch with credentials (httpOnly cookies).
 * In production, this would use openapi-fetch with auto-generated types
 * from the backend's OpenAPI spec.
 */

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  detail: string;
  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
  }
}

async function request<T = any>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const res = await fetch(`${BACKEND_URL}${path}`, {
    ...options,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Something went wrong" }));

    // Handle 401 — try refresh, then redirect to login
    if (res.status === 401) {
      if (typeof window !== "undefined") {
        window.location.href = "/login";
      }
      throw new ApiError(401, "Session expired — please log in again");
    }

    // Handle 429 — rate limited
    if (res.status === 429) {
      const retryAfter = res.headers.get("Retry-After") || "5";
      throw new ApiError(429, `Too many requests — try again in ${retryAfter}s`);
    }

    throw new ApiError(res.status, error.detail || "Something went wrong");
  }

  return res.json();
}

// Auth endpoints
export const authApi = {
  login: (email: string, password: string) =>
    request("/api/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  register: (name: string, email: string, password: string) =>
    request("/api/auth/register", { method: "POST", body: JSON.stringify({ name, email, password }) }),
  me: () => request("/api/auth/me"),
};

// Tenant endpoints
export const tenantsApi = {
  list: () => request("/api/tenants"),
  get: (id: string) => request(`/api/tenants/${id}`),
  create: (data: any) => request("/api/tenants", { method: "POST", body: JSON.stringify(data) }),
  update: (id: string, data: any) => request(`/api/tenants/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  stats: (id: string) => request(`/api/tenants/${id}/stats`),
};

// Product endpoints
export const productsApi = {
  list: (tenantId: string, params?: { page?: number; page_size?: number; search?: string }) => {
    const query = new URLSearchParams();
    if (params?.page) query.set("page", String(params.page));
    if (params?.page_size) query.set("page_size", String(params.page_size));
    if (params?.search) query.set("search", params.search);
    return request(`/api/tenants/${tenantId}/products?${query}`);
  },
  get: (tenantId: string, productId: string) => request(`/api/tenants/${tenantId}/products/${productId}`),
  create: (tenantId: string, data: any) => request(`/api/tenants/${tenantId}/products`, { method: "POST", body: JSON.stringify(data) }),
  update: (tenantId: string, productId: string, data: any) => request(`/api/tenants/${tenantId}/products/${productId}`, { method: "PATCH", body: JSON.stringify(data) }),
  delete: (tenantId: string, productId: string) => request(`/api/tenants/${tenantId}/products/${productId}`, { method: "DELETE" }),
};

// Order endpoints
export const ordersApi = {
  list: (tenantId: string, params?: { page?: number; status?: string }) => {
    const query = new URLSearchParams();
    if (params?.page) query.set("page", String(params.page));
    if (params?.status) query.set("status", params.status);
    return request(`/api/tenants/${tenantId}/orders?${query}`);
  },
  get: (tenantId: string, orderId: string) => request(`/api/tenants/${tenantId}/orders/${orderId}`),
  create: (tenantId: string, data: any) => request(`/api/tenants/${tenantId}/orders`, { method: "POST", body: JSON.stringify(data) }),
  updateStatus: (tenantId: string, orderId: string, status: string, notes?: string) =>
    request(`/api/tenants/${tenantId}/orders/${orderId}/status`, { method: "PATCH", body: JSON.stringify({ status, notes }) }),
};

// Address endpoints (Egyptian governorates)
export const addressApi = {
  governorates: () => request("/api/address/governorates"),
  cities: (governorate: string) => request(`/api/address/cities?governorate=${encodeURIComponent(governorate)}`),
  areas: (governorate: string) => request(`/api/address/areas?governorate=${encodeURIComponent(governorate)}`),
  shipping: (governorate: string, subtotal: number) => request(`/api/address/shipping?governorate=${encodeURIComponent(governorate)}&subtotal=${subtotal}`),
};

// Test chat
export const chatApi = {
  test: (tenantId: string, message: string, customerName: string) =>
    request("/api/test/chat", { method: "POST", body: JSON.stringify({ tenant_id: tenantId, message, customer_name: customerName }) }),
  ownerChat: (tenantId: string, message: string) =>
    request("/api/test/postiz-chat", { method: "POST", body: JSON.stringify({ tenant_id: tenantId, message }) }),
};

// Admin endpoints
export const adminApi = {
  stats: () => request("/api/admin/analytics/overview"),
  geoDistribution: () => request("/api/admin/analytics/geo-distribution"),
  activeSessions: () => request("/api/admin/analytics/active-sessions"),
  auditLog: (params?: { page?: number; action?: string }) => {
    const query = new URLSearchParams();
    if (params?.page) query.set("page", String(params.page));
    if (params?.action) query.set("action", params.action);
    return request(`/api/admin/audit-log?${query}`);
  },
};

export { request as apiClient };
