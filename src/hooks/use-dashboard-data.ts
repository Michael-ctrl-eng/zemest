"use client";

/**
 * Typed TanStack Query hooks for the tenant dashboard.
 *
 * All requests go through the existing BFF client (`src/lib/zemest-api.ts`),
 * so auth (httpOnly cookie → Bearer) is unchanged. Query keys are namespaced
 * per entity + tenantId so invalidation is scoped (never global):
 *
 *   ["conversations", tenantId]                    — list
 *   ["conversations", tenantId, conversationId]    — thread detail (prefix of the list key)
 *   ["style-profile", tenantId]
 *
 * Polling (R7 audit: polling is fine until an SSE layer lands):
 *   - conversations list/thread poll every 10s (chat playground thread: 5s)
 *   - `refetchIntervalInBackground` stays false → polling pauses while the
 *     window is hidden and resumes on focus.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  chatApi,
  conversationsApi,
  styleApi,
  type Conversation,
  type StyleProfile,
  type StyleProfileResponse,
} from "@/lib/zemest-api";

/** Interval used for list + read-only thread polling (ms). */
export const CONVERSATIONS_POLL_MS = 10_000;
/** Faster interval for the chat playground's live thread. */
export const CHAT_POLL_MS = 5_000;

// ---------------------------------------------------------------- conversations

export function useConversations(tenantId: string) {
  return useQuery<{ conversations: Conversation[]; total: number }, Error>({
    queryKey: ["conversations", tenantId],
    queryFn: () => conversationsApi.list(tenantId),
    refetchInterval: CONVERSATIONS_POLL_MS,
  });
}

/**
 * Single conversation thread (messages included by the detail endpoint).
 * Pass `null`/`undefined` to disable (e.g. no conversation selected yet).
 */
export function useConversation(
  tenantId: string,
  conversationId?: string | null,
  refetchInterval: number | false = CONVERSATIONS_POLL_MS
) {
  return useQuery<Conversation, Error>({
    queryKey: ["conversations", tenantId, conversationId ?? null],
    queryFn: () => conversationsApi.get(tenantId, conversationId as string),
    enabled: Boolean(conversationId),
    refetchInterval,
  });
}

// ---------------------------------------------------------------- chat playground

export interface SendChatMessageInput {
  message: string;
  customerName?: string;
}

export interface SendChatMessageResult {
  reply: string;
  conversation_id: string;
  customer_id: string;
  tokens_used: number;
}

/** POST /test/chat — creates real conversation + messages, so the
 *  conversations queries must be refreshed on success. */
export function useSendChatMessage(tenantId: string) {
  const queryClient = useQueryClient();
  return useMutation<SendChatMessageResult, Error, SendChatMessageInput>({
    mutationFn: ({ message, customerName }) =>
      chatApi.send(tenantId, message, customerName || "Test Customer"),
    onSuccess: () => {
      // Scoped invalidation: refreshes the list AND every thread detail
      // for this tenant (detail keys extend the list key).
      void queryClient.invalidateQueries({ queryKey: ["conversations", tenantId] });
    },
  });
}

// ---------------------------------------------------------------- style learning

export function useStyleProfile(tenantId: string) {
  return useQuery<StyleProfileResponse, Error>({
    queryKey: ["style-profile", tenantId],
    queryFn: () => styleApi.get(tenantId),
  });
}

/** POST /rebuild-style — re-analyzes existing messages and rebuilds the profile. */
export function useRebuildStyle(tenantId: string) {
  const queryClient = useQueryClient();
  return useMutation<{ status: string; profile: StyleProfile }, Error, void>({
    mutationFn: () => styleApi.rebuild(tenantId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["style-profile", tenantId] });
    },
  });
}
