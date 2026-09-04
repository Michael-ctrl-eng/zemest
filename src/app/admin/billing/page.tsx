"use client";

import { useState, useEffect, useCallback } from "react";
import {
  Coins,
  Landmark,
  RefreshCw,
  CheckCircle2,
  AlertTriangle,
  Play,
  ThumbsUp,
  XCircle,
} from "lucide-react";
import {
  adminBillingApi,
  type TreasuryStatus,
  type PayoutRequestItem,
  type BillingOverview,
  type BillingTickStats,
  apiErrorMessage,
} from "@/lib/zemest-api";
import {
  StatusBadge,
  TableShell,
  Th,
  Td,
  Row,
  LoadingState,
  ErrorState,
  EmptyState,
  WinCard,
} from "@/components/site/dash";

export default function AdminBillingPage() {
  const [treasury, setTreasury] = useState<TreasuryStatus | null>(null);
  const [overview, setOverview] = useState<BillingOverview | null>(null);
  const [withdrawals, setWithdrawals] = useState<PayoutRequestItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [lastTick, setLastTick] = useState<BillingTickStats | null>(null);

  // New withdrawal form state
  const [kind, setKind] = useState<"usdc" | "bank">("usdc");
  const [amountUsdc, setAmountUsdc] = useState("");
  const [amountEgp, setAmountEgp] = useState("");
  const [destination, setDestination] = useState("");
  const [execRef, setExecRef] = useState<Record<string, string>>({});

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [t, o, w] = await Promise.all([
        adminBillingApi.treasury(),
        adminBillingApi.overview(),
        adminBillingApi.withdrawals(),
      ]);
      setTreasury(t);
      setOverview(o);
      setWithdrawals(w);
    } catch (err: unknown) {
      setError(apiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const runTick = useCallback(async () => {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const stats = await adminBillingApi.tick();
      setLastTick(stats);
      setNotice(`Billing cycle ran — renewed ${stats.renewed}, dunning ${stats.dunning_attempted}, USDC settled ${stats.usdc_settled}.`);
      await load();
    } catch (err: unknown) {
      setError(apiErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }, [load]);

  const createWithdrawal = useCallback(async () => {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await adminBillingApi.createWithdrawal({
        kind,
        amount_usdc: kind === "usdc" && amountUsdc ? amountUsdc : undefined,
        amount_egp: kind === "bank" && amountEgp ? amountEgp : undefined,
        destination: destination
          ? kind === "usdc"
            ? { wallet: destination, network: "solana" }
            : { bank_label: destination }
          : undefined,
      });
      setNotice("Withdrawal request created — needs TWO distinct superadmin approvals.");
      setAmountUsdc("");
      setAmountEgp("");
      setDestination("");
      await load();
    } catch (err: unknown) {
      setError(apiErrorMessage(err, "Withdrawal request rejected"));
    } finally {
      setBusy(false);
    }
  }, [kind, amountUsdc, amountEgp, destination, load]);

  const act = useCallback(
    async (fn: () => Promise<PayoutRequestItem>, message: string) => {
      setBusy(true);
      setError(null);
      setNotice(null);
      try {
        await fn();
        setNotice(message);
        await load();
      } catch (err: unknown) {
        setError(apiErrorMessage(err));
      } finally {
        setBusy(false);
      }
    },
    [load]
  );

  if (loading && !treasury) return <LoadingState label="Billing / treasury" />;
  if (error && !treasury) return <ErrorState message={error} onRetry={load} />;

  const held = treasury?.payouts_held ?? false;

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between flex-wrap gap-4">
        <div className="min-w-0">
          <div className="inline-flex items-center gap-2 mb-2.5">
            <span className="w-2 h-2 bg-[var(--tavus-terminal-black)]" />
            <span className="text-[10px] font-extrabold tracking-[0.22em] uppercase text-[var(--tavus-hardware-gray-8)]">
              Admin · Billing
            </span>
          </div>
          <h1 className="font-serif text-3xl sm:text-4xl font-normal tracking-tight text-[var(--tavus-terminal-black)] leading-[1.05]">
            Treasury <span className="serif-italic">& withdrawals</span>
          </h1>
        </div>
        <div className="flex gap-2">
          <button
            onClick={load}
            className="inline-flex items-center gap-2 h-10 px-4 border-[2.5px] border-[var(--tavus-terminal-black)] bg-white text-[11px] font-extrabold tracking-[0.1em] uppercase shadow-[3px_3px_0_0_var(--tavus-terminal-black)]"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Refresh
          </button>
          <button
            onClick={runTick}
            disabled={busy}
            className="inline-flex items-center gap-2 h-10 px-4 border-[2.5px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-bubbletech-4)] text-[11px] font-extrabold tracking-[0.1em] uppercase shadow-[3px_3px_0_0_var(--tavus-terminal-black)] disabled:opacity-50"
          >
            <Play className="w-3.5 h-3.5" />
            Run billing cycle
          </button>
        </div>
      </div>

      {error ? (
        <div className="flex items-center gap-2 border-[2.5px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-coral-1)]/10 px-4 py-3 text-[13px] font-semibold text-[var(--tavus-terminal-black)]">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          {error}
        </div>
      ) : null}
      {notice ? (
        <div className="flex items-center gap-2 border-[2.5px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-bubbletech-4)]/40 px-4 py-3 text-[13px] font-semibold text-[var(--tavus-terminal-black)]">
          <CheckCircle2 className="w-4 h-4 shrink-0" />
          {notice}
        </div>
      ) : null}
      {lastTick ? (
        <div className="text-[12px] font-semibold text-[var(--tavus-hardware-gray-8)]">
          last tick: renewed {lastTick.renewed} · dunning {lastTick.dunning_attempted} · past_due{" "}
          {lastTick.past_due} · canceled {lastTick.canceled} · expired {lastTick.expired} · usdc
          settled {lastTick.usdc_settled} · usdc voided {lastTick.usdc_voided}
        </div>
      ) : null}

      {held ? (
        <div className="flex items-center gap-2 border-[2.5px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-coral-1)]/20 px-4 py-3 text-[13px] font-bold text-[var(--tavus-terminal-black)]">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          PAYOUTS HELD — {treasury?.open_disputes} disputed invoice(s) open. Resolve the disputes
          before executing withdrawals.
        </div>
      ) : null}

      {/* Treasury + overview cards */}
      <div className="grid gap-4 md:grid-cols-2">
        <WinCard title="USDC treasury (Solana)">
          <div className="space-y-2 text-[13px] font-semibold text-[var(--tavus-terminal-black)]">
            <StatRow label="Balance" value={`${treasury?.usdc_balance ?? "—"} USDC`} icon={<Coins className="w-4 h-4" />} />
            <StatRow label="Min reserve" value={`${treasury?.min_reserve_usdc ?? "—"} USDC`} />
            <StatRow label="Wallet" value={treasury?.treasury_wallet || "not configured"} mono />
            <StatRow label="Mint" value={treasury?.usdc_mint ?? "—"} mono />
          </div>
          <p className="mt-3 text-[12px] font-semibold text-[var(--tavus-hardware-gray-8)]">
            The app is read-only against the chain: deposits are detected on-chain, signing
            happens offline (hardware wallet / bank portal) and executions are reconciled by
            signature.
          </p>
        </WinCard>

        <WinCard title="Billing health">
          <div className="space-y-2 text-[13px] font-semibold text-[var(--tavus-terminal-black)]">
            <StatRow label="MRR" value={`${overview?.mrr_egp ?? "0"} EGP`} />
            <StatRow
              label="Subscriptions"
              value={
                overview
                  ? Object.entries(overview.subscriptions)
                      .map(([k, v]) => `${k}: ${v}`)
                      .join(" · ") || "none"
                  : "—"
              }
            />
            <StatRow
              label="Invoices"
              value={
                overview
                  ? Object.entries(overview.invoices)
                      .map(([k, v]) => `${k}: ${v}`)
                      .join(" · ") || "none"
                  : "—"
              }
            />
            <StatRow label="Open disputes" value={String(overview?.open_disputes ?? 0)} />
          </div>
        </WinCard>
      </div>

      {/* New withdrawal request */}
      <WinCard title="New treasury withdrawal request">
        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1">
            <span className="text-[10px] font-extrabold tracking-[0.16em] uppercase text-[var(--tavus-hardware-gray-8)]">Kind</span>
            <select
              value={kind}
              onChange={(e) => setKind(e.target.value as "usdc" | "bank")}
              className="h-10 border-[2.5px] border-[var(--tavus-terminal-black)] bg-white px-3 text-[13px] font-bold"
            >
              <option value="usdc">USDC · Solana rail</option>
              <option value="bank">Bank transfer</option>
            </select>
          </label>
          {kind === "usdc" ? (
            <label className="flex flex-col gap-1">
              <span className="text-[10px] font-extrabold tracking-[0.16em] uppercase text-[var(--tavus-hardware-gray-8)]">Amount (USDC)</span>
              <input
                value={amountUsdc}
                onChange={(e) => setAmountUsdc(e.target.value)}
                placeholder="e.g. 250.0"
                className="h-10 w-40 border-[2.5px] border-[var(--tavus-terminal-black)] bg-white px-3 text-[13px] font-bold"
              />
            </label>
          ) : (
            <label className="flex flex-col gap-1">
              <span className="text-[10px] font-extrabold tracking-[0.16em] uppercase text-[var(--tavus-hardware-gray-8)]">Amount (EGP)</span>
              <input
                value={amountEgp}
                onChange={(e) => setAmountEgp(e.target.value)}
                placeholder="e.g. 250000.00"
                className="h-10 w-40 border-[2.5px] border-[var(--tavus-terminal-black)] bg-white px-3 text-[13px] font-bold"
              />
            </label>
          )}
          <label className="flex flex-col gap-1 flex-1 min-w-56">
            <span className="text-[10px] font-extrabold tracking-[0.16em] uppercase text-[var(--tavus-hardware-gray-8)]">
              Destination {kind === "usdc" ? "(wallet address)" : "(masked bank label)"}
            </span>
            <input
              value={destination}
              onChange={(e) => setDestination(e.target.value)}
              placeholder={kind === "usdc" ? "base58 wallet address…" : "CIB ****1234 — ops"}
              className="h-10 border-[2.5px] border-[var(--tavus-terminal-black)] bg-white px-3 text-[13px] font-bold font-mono"
            />
          </label>
          <button
            onClick={createWithdrawal}
            disabled={busy || held}
            className="inline-flex items-center gap-2 h-10 px-4 border-[2.5px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-bubbletech-4)] text-[11px] font-extrabold tracking-[0.1em] uppercase shadow-[3px_3px_0_0_var(--tavus-terminal-black)] disabled:opacity-50"
          >
            <Landmark className="w-3.5 h-3.5" />
            Create request
          </button>
        </div>
        <p className="mt-3 text-[12px] font-semibold text-[var(--tavus-hardware-gray-8)]">
          Requests need TWO distinct superadmin approvals (the creator cannot approve first),
          keep the treasury above the reserve floor, and are frozen while disputes are open.
          Execution records the Solana signature (verified on-chain) or bank receipt.
        </p>
      </WinCard>

      {/* Withdrawal queue */}
      <WinCard title="Withdrawal requests">
        {withdrawals.length === 0 ? (
          <EmptyState title="No withdrawal requests" hint="Treasury withdrawal requests appear here." />
        ) : (
          <TableShell>
            <thead>
              <tr>
                <Th>Request</Th>
                <Th>Kind</Th>
                <Th>Amount</Th>
                <Th>Status</Th>
                <Th>Approvals</Th>
                <Th>Reference</Th>
                <Th>Actions</Th>
              </tr>
            </thead>
            <tbody>
              {withdrawals.map((w) => (
                <Row key={w.id}>
                  <Td className="font-mono text-[11px]">{w.id.slice(0, 8)}…</Td>
                  <Td>{w.kind === "usdc" ? "USDC" : "Bank"}</Td>
                  <Td>
                    {w.kind === "usdc"
                      ? `${w.amount_usdc ?? "—"} USDC`
                      : `${w.amount_egp ?? "—"} EGP`}
                  </Td>
                  <Td><StatusBadge status={w.status} /></Td>
                  <Td>{(w.approvers ?? []).length} / 2</Td>
                  <Td className="font-mono text-[11px]">
                    {w.execution_reference ?? "—"}
                  </Td>
                  <Td>
                    <div className="flex items-center gap-1.5 flex-wrap">
                      {(w.status === "request" || w.status === "pending") && (
                        <SmallBtn
                          title="Approve"
                          icon={<ThumbsUp className="w-3 h-3" />}
                          onClick={() =>
                            act(
                              () => adminBillingApi.approveWithdrawal(w.id),
                              "Approval recorded."
                            )
                          }
                          disabled={busy || held}
                        />
                      )}
                      {(w.status === "request" || w.status === "pending") && (
                        <SmallBtn
                          title="Reject"
                          icon={<XCircle className="w-3 h-3" />}
                          onClick={() =>
                            act(
                              () => adminBillingApi.rejectWithdrawal(w.id),
                              "Request rejected."
                            )
                          }
                          disabled={busy}
                        />
                      )}
                      {w.status === "approved" && (
                        <div className="flex items-center gap-1.5">
                          <input
                            value={execRef[w.id] ?? ""}
                            onChange={(e) =>
                              setExecRef((prev) => ({ ...prev, [w.id]: e.target.value }))
                            }
                            placeholder={w.kind === "usdc" ? "solana signature…" : "bank receipt…"}
                            className="h-8 w-44 border-2 border-[var(--tavus-terminal-black)] bg-white px-2 text-[11px] font-bold font-mono"
                          />
                          <SmallBtn
                            title="Record execution"
                            icon={<CheckCircle2 className="w-3 h-3" />}
                            onClick={() =>
                              act(
                                () =>
                                  adminBillingApi.executeWithdrawal(
                                    w.id,
                                    execRef[w.id] ?? ""
                                  ),
                                "Execution recorded and reconciled."
                              )
                            }
                            disabled={busy || held || !(execRef[w.id] ?? "").trim()}
                          />
                        </div>
                      )}
                    </div>
                  </Td>
                </Row>
              ))}
            </tbody>
          </TableShell>
        )}
      </WinCard>
    </div>
  );
}

function StatRow({ label, value, icon, mono }: { label: string; value: string; icon?: React.ReactNode; mono?: boolean }) {
  return (
    <div className="flex items-center gap-2">
      {icon ?? <span className="w-1.5 h-1.5 bg-[var(--tavus-terminal-black)]" />}
      <span className="text-[10px] font-extrabold tracking-[0.16em] uppercase text-[var(--tavus-hardware-gray-8)] w-32 shrink-0">
        {label}
      </span>
      <span className={`min-w-0 truncate ${mono ? "font-mono text-[11px]" : ""}`}>{value}</span>
    </div>
  );
}

function SmallBtn({
  icon,
  title,
  onClick,
  disabled,
}: {
  icon: React.ReactNode;
  title: string;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      title={title}
      onClick={onClick}
      disabled={disabled}
      className="inline-flex items-center justify-center w-8 h-8 border-2 border-[var(--tavus-terminal-black)] bg-white shadow-[2px_2px_0_0_var(--tavus-terminal-black)] disabled:opacity-40"
    >
      {icon}
    </button>
  );
}
