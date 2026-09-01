"use client";

import { use } from "react";
import { Sparkles, Palette, RefreshCw, Loader2, AlertTriangle } from "lucide-react";
import { formatDateTime, apiErrorMessage, type StyleProfile } from "@/lib/zemest-api";
import { useStyleProfile, useRebuildStyle } from "@/hooks/use-dashboard-data";
import {
  WinCard,
  StatusBadge,
  DashHeader,
  TavusButton,
  TableShell,
  Th,
  Td,
  Row,
  LoadingState,
  ErrorState,
  EmptyState,
} from "@/components/site/dash";

/** Fraction (0–1) → "90%"; already-percent values pass through. */
function pct(value: number): string {
  return value <= 1 ? `${Math.round(value * 100)}%` : `${Math.round(value)}%`;
}

/** {arabic: 0.9, english: 0.1} → "Arabic 90% · English 10%" */
function mixLabel(mix: Record<string, number> | null | undefined): string {
  if (!mix) return "—";
  const parts = Object.entries(mix)
    .filter(([, v]) => typeof v === "number")
    .map(([k, v]) => `${k.charAt(0).toUpperCase() + k.slice(1)} ${pct(v)}`);
  return parts.length > 0 ? parts.join(" · ") : "—";
}

export default function StylePage({ params }: { params: Promise<{ tenantId: string }> }) {
  const { tenantId } = use(params);

  // Real data wiring: GET /tenants/{id}/style-profile (built profile or
  // "not_built") + POST /tenants/{id}/rebuild-style mutation which
  // invalidates the same query key on success.
  const styleQuery = useStyleProfile(tenantId);
  const rebuildMutation = useRebuildStyle(tenantId);

  const loading = styleQuery.isPending;
  const error =
    styleQuery.isError && !styleQuery.data
      ? apiErrorMessage(styleQuery.error, "Failed to load style profile")
      : null;
  const rebuildError = rebuildMutation.isError ? apiErrorMessage(rebuildMutation.error, "Failed to rebuild style profile") : null;

  const profile: StyleProfile | null =
    styleQuery.data?.status === "built" && styleQuery.data?.profile ? styleQuery.data.profile : null;
  const builtAt = styleQuery.data?.built_at ?? profile?.built_at ?? null;

  const greetingPatterns = profile?.greeting_patterns ?? [];
  const signoffPatterns = profile?.signoff_patterns ?? [];
  const vocabulary = profile?.vocabulary ?? [];
  const exemplars = profile?.exemplars ?? [];

  const stage = profile?.silent_training?.stage ?? null;
  const maturity = typeof profile?.silent_training?.maturity === "number" ? profile.silent_training.maturity : null;
  const trainerLabel = profile?.silent_training?.version
    ? `Trainer ${profile.silent_training.version}${stage ? ` · ${stage}` : ""}`
    : "Trainer —";

  return (
    <div className="space-y-6">
      {/* Header */}
      <DashHeader
        eyebrow="Style learning"
        title="Brand"
        tail="voice"
        action={
          <>
            <button
              onClick={() => void styleQuery.refetch()}
              title="Refresh"
              aria-label="Refresh"
              className="inline-flex items-center justify-center w-11 h-11 border-[3px] border-[var(--tavus-terminal-black)] bg-white shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:shadow-[4px_4px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] transition-all"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} strokeWidth={2.5} />
            </button>
            <TavusButton onClick={() => rebuildMutation.mutate()} disabled={rebuildMutation.isPending}>
              {rebuildMutation.isPending ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Sparkles className="w-4 h-4" strokeWidth={2.5} />
              )}
              {rebuildMutation.isPending ? "Rebuilding…" : "Rebuild profile"}
            </TavusButton>
          </>
        }
      />

      {/* Rebuild error */}
      {rebuildError ? (
        <div className="flex items-center gap-2 border-[2.5px] border-[var(--tavus-coral-1)] bg-[var(--tavus-coral-3)]/40 px-3 py-2">
          <AlertTriangle className="w-4 h-4 text-[var(--tavus-terminal-black)] shrink-0" strokeWidth={2.5} />
          <span className="text-[12px] font-bold text-[var(--tavus-terminal-black)]">{rebuildError}</span>
        </div>
      ) : null}

      {/* Loading state */}
      {loading ? <LoadingState label="Loading style profile" /> : null}

      {/* Error state */}
      {error ? <ErrorState message={error} onRetry={() => void styleQuery.refetch()} /> : null}

      {/* No profile yet */}
      {!loading && !error && !profile ? (
        <WinCard title="No style profile yet" dot="var(--tavus-atomic-glow-1)">
          <EmptyState
            icon={<Palette className="w-6 h-6" strokeWidth={2} />}
            title="Style learning isn't active yet"
            hint="Your agent learns your voice automatically from real conversations — no upload needed. Once enough messages are captured, the learned profile appears here. You can also rebuild it now from the messages already stored."
            action={
              <TavusButton onClick={() => rebuildMutation.mutate()} disabled={rebuildMutation.isPending}>
                {rebuildMutation.isPending ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Sparkles className="w-4 h-4" strokeWidth={2.5} />
                )}
                {rebuildMutation.isPending ? "Rebuilding…" : "Build profile now"}
              </TavusButton>
            }
          />
        </WinCard>
      ) : null}

      {/* Learned profile */}
      {!loading && !error && profile ? (
        <>
          <WinCard title="Learned voice profile" dot="var(--tavus-bubbletech-4)">
            <TableShell>
              <thead>
                <tr>
                  <Th>Property</Th>
                  <Th>Learned value</Th>
                </tr>
              </thead>
              <tbody>
                <Row>
                  <Td className="font-bold">Tone</Td>
                  <Td>
                    <StatusBadge status={String(profile.tone ?? "unknown")}>{String(profile.tone ?? "—")}</StatusBadge>
                  </Td>
                </Row>
                <Row>
                  <Td className="font-bold">Formality level</Td>
                  <Td className="tabular-nums">{profile.formality_level != null ? `${profile.formality_level} / 10` : "—"}</Td>
                </Row>
                <Row>
                  <Td className="font-bold">Avg reply length</Td>
                  <Td>
                    {profile.avg_response_length ?? "—"}
                    {profile.avg_length_chars != null ? ` · ~${Math.round(profile.avg_length_chars)} chars` : ""}
                  </Td>
                </Row>
                <Row>
                  <Td className="font-bold">Emoji frequency</Td>
                  <Td>
                    {profile.emoji_frequency ?? "—"}
                    {profile.emoji_inventory && profile.emoji_inventory.length > 0
                      ? ` · ${profile.emoji_inventory.join(" ")}`
                      : ""}
                  </Td>
                </Row>
                <Row>
                  <Td className="font-bold">Language mix</Td>
                  <Td>{mixLabel(profile.language_mix)}</Td>
                </Row>
                <Row>
                  <Td className="font-bold">Buyer dialects</Td>
                  <Td>{mixLabel(profile.buyer_persona?.dialects)}</Td>
                </Row>
                <Row>
                  <Td className="font-bold">Messages analyzed</Td>
                  <Td className="tabular-nums">
                    {profile.message_count_analyzed != null
                      ? `${profile.message_count_analyzed}${
                          profile.total_messages_available != null ? ` of ${profile.total_messages_available}` : ""
                        }`
                      : "—"}
                  </Td>
                </Row>
                <Row>
                  <Td className="font-bold">Training stage</Td>
                  <Td>
                    {stage ?? "—"}
                    {maturity != null ? ` · ${pct(maturity)} mature` : ""}
                  </Td>
                </Row>
              </tbody>
            </TableShell>
            <div className="relative flex items-center justify-between px-4 py-3 border-t-[2px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-plastic-1)]">
              <div className="text-[10px] font-bold tracking-[0.14em] uppercase text-[var(--tavus-hardware-gray-8)]">
                Profile built {formatDateTime(builtAt)}
              </div>
              <div className="text-[10px] font-bold text-[var(--tavus-hardware-gray-8)]">{trainerLabel}</div>
            </div>
          </WinCard>

          {greetingPatterns.length > 0 ? (
            <WinCard title="Greeting patterns" dot="var(--tavus-floppy-fog-3)">
              <div className="relative p-4">
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                  {greetingPatterns.map((p, i) => (
                    <div key={i} className="bg-white border-[1.5px] border-[var(--tavus-terminal-black)] px-2 py-1">
                      <span className="text-[13px] font-semibold text-[var(--tavus-terminal-black)]">{p}</span>
                    </div>
                  ))}
                </div>
              </div>
            </WinCard>
          ) : null}

          {signoffPatterns.length > 0 ? (
            <WinCard title="Signoff patterns" dot="var(--tavus-plastic-2)">
              <div className="relative p-4">
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                  {signoffPatterns.map((p, i) => (
                    <div key={i} className="bg-white border-[1.5px] border-[var(--tavus-terminal-black)] px-2 py-1">
                      <span className="text-[13px] font-semibold text-[var(--tavus-terminal-black)]">{p}</span>
                    </div>
                  ))}
                </div>
              </div>
            </WinCard>
          ) : null}

          {vocabulary.length > 0 ? (
            <WinCard title="Vocabulary & phrases" dot="var(--tavus-atomic-glow-1)">
              <div className="relative p-4">
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                  {vocabulary.map((p, i) => (
                    <div key={i} className="bg-white border-[1.5px] border-[var(--tavus-terminal-black)] px-2 py-1">
                      <span className="text-[13px] font-semibold text-[var(--tavus-terminal-black)]">{p}</span>
                    </div>
                  ))}
                </div>
              </div>
            </WinCard>
          ) : null}

          {exemplars.length > 0 ? (
            <WinCard title="Sample replies" dot="var(--tavus-neon-field-2)">
              <div className="relative p-4 space-y-3 bg-[var(--tavus-plastic-1)]">
                {exemplars.map((ex, i) => (
                  <div key={i} className="space-y-2">
                    {ex.customer ? (
                      <div className="flex justify-end">
                        <div className="max-w-[75%] px-3 py-2 text-sm bg-[var(--tavus-plastic-2)] border-2 border-[var(--tavus-terminal-black)]">
                          <div className="text-[9px] font-bold tracking-[0.14em] uppercase text-[var(--tavus-hardware-gray-8)] mb-1">
                            Customer
                          </div>
                          <div className="text-[var(--tavus-terminal-black)] whitespace-pre-wrap break-words">{ex.customer}</div>
                        </div>
                      </div>
                    ) : null}
                    {ex.reply ? (
                      <div className="flex justify-start">
                        <div className="max-w-[75%] px-3 py-2 text-sm bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[3px_3px_0_0_var(--tavus-terminal-black)]">
                          <div className="text-[9px] font-bold tracking-[0.14em] uppercase text-[var(--tavus-hardware-gray-8)] mb-1">
                            Your agent
                          </div>
                          <div className="text-[var(--tavus-terminal-black)] whitespace-pre-wrap break-words">{ex.reply}</div>
                        </div>
                      </div>
                    ) : null}
                  </div>
                ))}
              </div>
            </WinCard>
          ) : null}
        </>
      ) : null}
    </div>
  );
}
