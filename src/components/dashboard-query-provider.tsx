"use client";

/**
 * TanStack Query provider for the tenant dashboard subtree.
 *
 * Mounted once in `src/app/dashboard/[tenantId]/layout.tsx` so every page
 * under /dashboard/[tenantId] can use the typed hooks in
 * `src/hooks/use-dashboard-data.ts` (queries + mutations + polling).
 *
 * Defaults follow the R9 performance audit recommendation:
 * 30s staleTime (instant cache paint on navigation), 5min gcTime,
 * refetch-on-focus, single retry.
 */
import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

export function DashboardQueryProvider({ children }: { children: React.ReactNode }) {
  // useState initializer → one client per browser session (never recreated
  // on re-render, never shared between requests on the server).
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            gcTime: 5 * 60_000,
            refetchOnWindowFocus: true,
            retry: 1,
          },
          mutations: {
            retry: 0,
          },
        },
      })
  );

  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}
