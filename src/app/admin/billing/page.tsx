"use client";

import { useCallback, useEffect, useState } from "react";
import {
  CreditCard,
  Receipt,
  Wallet,
  ShieldAlert,
  Loader2,
  RefreshCw,
  Play,
  CheckCircle2,
  XCircle,
  RotateCcw,
  DollarSign,
} from "lucide-react";
import {
  adminBillingApi,
  apiErrorMessage,
  formatDateTime,
  formatMoney,
  type AdminBillingOverview,
  type AdminBillingSubscription,
  type AdminBillingInvoice,
  type AdminBillingPayout,
  type AdminFraudFlag,
} from "@/lib/zemest-api";
import { LoadingState, ErrorState } from "@/components/site/dash";

type Tab = "subscriptions" | "invoices" | "payouts" | "fraud";

const TABS: { key: Tab; label: string; icon: typeof CreditCard }[] = [
  { key: "subscriptions", label: "Subscriptions", icon: CreditCard },
  { key: "invoices", label: "Invoices", icon: Receipt },
  { key: "payouts", label: "Payouts", icon: Wallet },
  { key: "fraud", label: "Fraud", icon: ShieldAlert },
];

export default function AdminBillingPage() {
  const [tab, setTab] = useState<Tab>("subscriptions");
  const [overview, setOverview] = useState<AdminBillingOverview | null>(null);
  const [subs, setSubs] = useState<AdminBillingSubscription[] | null>(null);
  const [invoices, setInvoices] = useState<AdminBillingInvoice[] | null>(null);
  const [payouts, setPayouts] = useState<AdminBillingPayout[] | null>(null);
  const [flags, setFlags] = useState<AdminFraudFlag[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [ov, s, i, p, f] = await Promise.all([
        adminBillingApi.overview(),
        adminBillingApi.subscriptions(),
        adminBillingApi.invoices(),
        adminBillingApi.payouts(),
        adminBillingApi.fraudFlags(),
      ]);
      setOverview(ov);
      setSubs(s);
      setInvoices(i);
      setPayouts(p);
      setFlags(f);
    } catch (err: unknown) {
      setError(apiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function approvePayout(id: string) {
    setBusyId(id);
    setNote(null);
    try {
      const r = await adminBillingApi.approvePayout(id);
      setNote(
        r.status === "paid"
          ? `Payout sent (${r.tx_hash ? `${r.tx_hash.slice(0, 16)}…` : "rail accepted"}).`
          : "Payout approved — processing on the rail."
      );
      await load();
    } catch (err: unknown) {
      setError(apiErrorMessage(err, "Could not approve the payout"));
    } finally {
      setBusyId(null);
    }
  }

  async function retryPayout(id: string) {
    setBusyId(id);
    setNote(null);
    try {
      await adminBillingApi.retryPayout(id);
      setNote("Payout retry sent.");
      await load();
    } catch (err: unknown) {
      setError(apiErrorMessage(err, "Could not retry the payout"));
    } finally {
      setBusyId(null);
    }
  }

  async function resolveFlag(id: string) {
    setBusyId(id);
    setNote(null);
    try {
      await adminBillingApi.resolveFraudFlag(id);
      setNote("Fraud flag resolved — payout holds lift when none remain.");
      await load();
    } catch (err: unknown) {
      setError(apiErrorMessage(err, "Could not resolve the flag"));
    } finally {
      setBusyId(null);
    }
  }

  async function runTick() {
    setBusyId("tick");
    setNote(null);
    try {
      const stats = await adminBillingApi.runTick();
      setNote(`Billing cycle run: ${Object.entries(stats).map(([k, v]) => `${k}=${v}`).join(", ")}`);
      await load();
    } catch (err: unknown) {
      setError(apiErrorMessage(err, "Could not run the billing cycle"));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight">Billing</h1>
          <p className="text-sm text-[var(--tavus-hardware-gray-8)] mt-0.5">
            Subscriptions, revenue, payouts and fraud — every state change is webhook-driven and idempotent.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={runTick}
            disabled={busyId === "tick"}
            className="inline-flex items-center gap-1.5 px-3 h-9 border-[2.5px] border-[var(--tavus-terminal-black)] bg-white text-[11px] font-extrabold tracking-[0.1em] uppercase shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:shadow-[4px_4px_0_0_var(--tavus-terminal-black)] hover:-translate-y-0.5 transition-all disabled:opacity-50"
          >
            {busyId === "tick" ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
            Run cycle
          </button>
          <button
            onClick={load}
            disabled={loading}
            className="inline-flex items-center gap-1.5 px-3 h-9 border-[2.5px] border-[var(--tavus-terminal-black)]/40 text-[11px] font-extrabold tracking-[0.1em] uppercase hover:border-[var(--tavus-terminal-black)] hover:bg-[var(--tavus-plastic-2)] disabled:opacity-50 transition-all"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} strokeWidth={2.5} />
            Refresh
          </button>
        </div>
      </div>

      {note ? (
        <p className="text-sm font-semibold border-[2px] border-[var(--tavus-terminal-black)]/30 bg-[var(--tavus-signal-green)]/25 px-3 py-2">
          {note}
        </p>
      ) : null}

      {/* Headline counters */}
      {overview ? (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          <StatCard label="Active subs" value={String(overview.active_subscriptions)} icon={CreditCard} />
          <StatCard label="MRR" value={formatMoney(overview.mrr_cents)} icon={DollarSign} />
          <StatCard label="Revenue (paid)" value={formatMoney(overview.lifetime_revenue_cents)} icon={Receipt} />
          <StatCard label="Open invoices" value={String(overview.open_invoices)} icon={Receipt} />
          <StatCard label="Payouts pending" value={String(overview.payouts_pending)} icon={Wallet} />
          <StatCard
            label="Fraud flags"
            value={String(overview.fraud_flags_open)}
            icon={ShieldAlert}
            highlight={overview.fraud_flags_open > 0}
          />
        </div>
      ) : null}

      {/* Tabs */}
      <div className="flex flex-wrap gap-2">
        {TABS.map((t) => {
          const isPicked = tab === t.key;
          return (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`inline-flex items-center gap-1.5 px-3.5 h-9 border-[2.5px] text-[11px] font-extrabold tracking-[0.1em] uppercase transition-all ${
                isPicked
                  ? "border-[var(--tavus-terminal-black)] bg-[var(--tavus-bubbletech-4)] shadow-[2px_2px_0_0_var(--tavus-terminal-black)]"
                  : "border-[var(--tavus-terminal-black)]/30 bg-white hover:border-[var(--tavus-terminal-black)]/70"
              }`}
            >
              <t.icon className="w-3.5 h-3.5" strokeWidth={2.5} />
              {t.label}
            </button>
          );
        })}
      </div>

      {error ? <ErrorState message={error} onRetry={load} /> : null}
      {loading && !subs ? (
        <LoadingState label="Loading billing" />
      ) : (
        <>
          {tab === "subscriptions" ? <SubscriptionsTable subs={subs ?? []} /> : null}
          {tab === "invoices" ? <InvoicesTable invoices={invoices ?? []} /> : null}
          {tab === "payouts" ? (
            <PayoutsTable payouts={payouts ?? []} busyId={busyId} onApprove={approvePayout} onRetry={retryPayout} />
          ) : null}
          {tab === "fraud" ? (
            <FraudTable flags={flags ?? []} busyId={busyId} onResolve={resolveFlag} />
          ) : null}
        </>
      )}
    </div>
  );
}

function StatCard({
  label,
  value,
  icon: Icon,
  highlight,
}: {
  label: string;
  value: string;
  icon: typeof CreditCard;
  highlight?: boolean;
}) {
  return (
    <div
      className={`border-[3px] border-[var(--tavus-terminal-black)] bg-white p-3.5 shadow-[3px_3px_0_0_var(--tavus-terminal-black)] ${
        highlight ? "bg-[var(--tavus-coral-1)]/10" : ""
      }`}
    >
      <div className="flex items-center gap-1.5 text-[var(--tavus-hardware-gray-8)]">
        <Icon className="w-3.5 h-3.5" strokeWidth={2.5} />
        <p className="text-[9px] font-extrabold tracking-[0.14em] uppercase">{label}</p>
      </div>
      <p className="text-lg font-extrabold mt-1.5">{value}</p>
    </div>
  );
}

const SUB_CLS: Record<string, string> = {
  active: "bg-[var(--tavus-signal-green)]/50",
  past_due: "bg-[var(--tavus-coral-1)]/20",
  canceled: "bg-[var(--tavus-plastic-2)]",
  trialing: "bg-[var(--tavus-atomic-glow-5)]",
  incomplete: "bg-[var(--tavus-plastic-2)]",
};

function SubscriptionsTable({ subs }: { subs: AdminBillingSubscription[] }) {
  if (subs.length === 0) {
    return <p className="border-[3px] border-[var(--tavus-terminal-black)]/25 bg-white p-5 text-sm font-semibold">No subscriptions yet.</p>;
  }
  return (
    <div className="border-[3px] border-[var(--tavus-terminal-black)] bg-white shadow-[4px_4px_0_0_var(--tavus-terminal-black)] overflow-x-auto">
      <table className="w-full text-[13px]">
        <thead>
          <tr className="border-b-[3px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-plastic-2)]/60">
            <th className="text-left px-4 py-2.5 text-[10px] font-extrabold uppercase tracking-wide">User</th>
            <th className="text-left px-4 py-2.5 text-[10px] font-extrabold uppercase tracking-wide">Plan</th>
            <th className="text-left px-4 py-2.5 text-[10px] font-extrabold uppercase tracking-wide">Status</th>
            <th className="text-left px-4 py-2.5 text-[10px] font-extrabold uppercase tracking-wide">Rail</th>
            <th className="text-left px-4 py-2.5 text-[10px] font-extrabold uppercase tracking-wide">Renews</th>
            <th className="text-left px-4 py-2.5 text-[10px] font-extrabold uppercase tracking-wide">Fails</th>
          </tr>
        </thead>
        <tbody>
          {subs.map((s) => (
            <tr key={s.id} className="border-b-[2px] border-[var(--tavus-terminal-black)]/10">
              <td className="px-4 py-2.5">
                <p className="font-bold truncate max-w-[220px]">{s.user_name || s.user_email || "—"}</p>
                <p className="text-[11px] font-mono text-[var(--tavus-hardware-gray-8)] truncate max-w-[220px]">{s.user_email || s.user_id.slice(0, 8)}</p>
              </td>
              <td className="px-4 py-2.5 font-extrabold uppercase">{s.plan}</td>
              <td className="px-4 py-2.5">
                <span className={`px-2 py-0.5 text-[10px] font-extrabold uppercase border-[2px] border-[var(--tavus-terminal-black)]/30 ${SUB_CLS[s.status] ?? ""}`}>
                  {s.status.replace("_", " ")}
                </span>
              </td>
              <td className="px-4 py-2.5 font-mono text-[12px]">{s.provider}</td>
              <td className="px-4 py-2.5 font-mono text-[12px]">
                {s.current_period_end ? new Date(s.current_period_end).toLocaleDateString("en-EG") : "—"}
              </td>
              <td className="px-4 py-2.5 font-mono">{s.failed_attempts}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const INV_CLS: Record<string, string> = {
  paid: "bg-[var(--tavus-signal-green)]/50",
  open: "bg-[var(--tavus-atomic-glow-5)]",
  uncollectible: "bg-[var(--tavus-coral-1)]/20",
};

function InvoicesTable({ invoices }: { invoices: AdminBillingInvoice[] }) {
  if (invoices.length === 0) {
    return <p className="border-[3px] border-[var(--tavus-terminal-black)]/25 bg-white p-5 text-sm font-semibold">No invoices yet.</p>;
  }
  return (
    <div className="border-[3px] border-[var(--tavus-terminal-black)] bg-white shadow-[4px_4px_0_0_var(--tavus-terminal-black)] overflow-x-auto">
      <table className="w-full text-[13px]">
        <thead>
          <tr className="border-b-[3px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-plastic-2)]/60">
            <th className="text-left px-4 py-2.5 text-[10px] font-extrabold uppercase tracking-wide">Invoice</th>
            <th className="text-left px-4 py-2.5 text-[10px] font-extrabold uppercase tracking-wide">User</th>
            <th className="text-left px-4 py-2.5 text-[10px] font-extrabold uppercase tracking-wide">Amount</th>
            <th className="text-left px-4 py-2.5 text-[10px] font-extrabold uppercase tracking-wide">Status</th>
            <th className="text-left px-4 py-2.5 text-[10px] font-extrabold uppercase tracking-wide">Attempts</th>
            <th className="text-left px-4 py-2.5 text-[10px] font-extrabold uppercase tracking-wide">Paid at</th>
          </tr>
        </thead>
        <tbody>
          {invoices.map((i) => (
            <tr key={i.id} className="border-b-[2px] border-[var(--tavus-terminal-black)]/10">
              <td className="px-4 py-2.5 font-mono font-bold">{i.number}</td>
              <td className="px-4 py-2.5 font-mono text-[11px] text-[var(--tavus-hardware-gray-8)]">{i.user_id.slice(0, 8)}…</td>
              <td className="px-4 py-2.5 font-extrabold">{formatMoney(i.amount, i.currency)}</td>
              <td className="px-4 py-2.5">
                <span className={`px-2 py-0.5 text-[10px] font-extrabold uppercase border-[2px] border-[var(--tavus-terminal-black)]/30 ${INV_CLS[i.status] ?? ""}`}>
                  {i.status}
                </span>
              </td>
              <td className="px-4 py-2.5 font-mono">{i.attempt_count}</td>
              <td className="px-4 py-2.5 font-mono text-[12px]">{i.paid_at ? formatDateTime(i.paid_at) : "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const PO_CLS: Record<string, string> = {
  pending: "bg-[var(--tavus-atomic-glow-5)]",
  approved: "bg-[var(--tavus-plastic-2)]",
  processing: "bg-[var(--tavus-bubbletech-4)]/60",
  paid: "bg-[var(--tavus-signal-green)]/50",
  failed: "bg-[var(--tavus-coral-1)]/20",
};

function PayoutsTable({
  payouts,
  busyId,
  onApprove,
  onRetry,
}: {
  payouts: AdminBillingPayout[];
  busyId: string | null;
  onApprove: (id: string) => void;
  onRetry: (id: string) => void;
}) {
  if (payouts.length === 0) {
    return <p className="border-[3px] border-[var(--tavus-terminal-black)]/25 bg-white p-5 text-sm font-semibold">No payout requests yet.</p>;
  }
  return (
    <div className="border-[3px] border-[var(--tavus-terminal-black)] bg-white shadow-[4px_4px_0_0_var(--tavus-terminal-black)] overflow-x-auto">
      <table className="w-full text-[13px]">
        <thead>
          <tr className="border-b-[3px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-plastic-2)]/60">
            <th className="text-left px-4 py-2.5 text-[10px] font-extrabold uppercase tracking-wide">User</th>
            <th className="text-left px-4 py-2.5 text-[10px] font-extrabold uppercase tracking-wide">Rail</th>
            <th className="text-left px-4 py-2.5 text-[10px] font-extrabold uppercase tracking-wide">Net</th>
            <th className="text-left px-4 py-2.5 text-[10px] font-extrabold uppercase tracking-wide">Status</th>
            <th className="text-left px-4 py-2.5 text-[10px] font-extrabold uppercase tracking-wide">Tx / ref</th>
            <th className="text-right px-4 py-2.5 text-[10px] font-extrabold uppercase tracking-wide">Actions</th>
          </tr>
        </thead>
        <tbody>
          {payouts.map((p) => (
            <tr key={p.id} className="border-b-[2px] border-[var(--tavus-terminal-black)]/10">
              <td className="px-4 py-2.5 font-mono text-[11px] text-[var(--tavus-hardware-gray-8)]">{p.user_id.slice(0, 8)}…</td>
              <td className="px-4 py-2.5 font-mono">{p.rail}</td>
              <td className="px-4 py-2.5 font-extrabold">{formatMoney(p.net_amount, p.currency)}</td>
              <td className="px-4 py-2.5">
                <span className={`px-2 py-0.5 text-[10px] font-extrabold uppercase border-[2px] border-[var(--tavus-terminal-black)]/30 ${PO_CLS[p.status] ?? ""}`}>
                  {p.status}
                </span>
                {p.failure_reason ? (
                  <p className="text-[10px] text-red-700 mt-1 max-w-[200px] truncate" title={p.failure_reason}>
                    {p.failure_reason}
                  </p>
                ) : null}
              </td>
              <td className="px-4 py-2.5 font-mono text-[11px] max-w-[140px] truncate">
                {p.tx_hash ? `${p.tx_hash.slice(0, 12)}…` : p.provider_ref || "—"}
              </td>
              <td className="px-4 py-2.5 text-right whitespace-nowrap">
                {p.status === "pending" ? (
                  <button
                    onClick={() => onApprove(p.id)}
                    disabled={busyId === p.id}
                    className="inline-flex items-center gap-1 px-2.5 py-1.5 text-[10px] font-extrabold uppercase border-[2px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-signal-green)]/40 shadow-[2px_2px_0_0_var(--tavus-terminal-black)] hover:shadow-[3px_3px_0_0_var(--tavus-terminal-black)] disabled:opacity-50"
                  >
                    {busyId === p.id ? <Loader2 className="w-3 h-3 animate-spin" /> : <CheckCircle2 className="w-3 h-3" />}
                    Approve
                  </button>
                ) : null}
                {p.status === "failed" ? (
                  <button
                    onClick={() => onRetry(p.id)}
                    disabled={busyId === p.id}
                    className="inline-flex items-center gap-1 px-2.5 py-1.5 text-[10px] font-extrabold uppercase border-[2px] border-[var(--tavus-terminal-black)] bg-white shadow-[2px_2px_0_0_var(--tavus-terminal-black)] disabled:opacity-50 ml-2"
                  >
                    {busyId === p.id ? <Loader2 className="w-3 h-3 animate-spin" /> : <RotateCcw className="w-3 h-3" />}
                    Retry
                  </button>
                ) : null}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function FraudTable({
  flags,
  busyId,
  onResolve,
}: {
  flags: AdminFraudFlag[];
  busyId: string | null;
  onResolve: (id: string) => void;
}) {
  if (flags.length === 0) {
    return (
      <p className="border-[3px] border-[var(--tavus-terminal-black)]/25 bg-white p-5 text-sm font-semibold">
        No open fraud flags — the velocity and dispute rules are watching.
      </p>
    );
  }
  return (
    <div className="space-y-3">
      {flags.map((f) => (
        <div
          key={f.id}
          className="border-[3px] border-[var(--tavus-terminal-black)] bg-white shadow-[3px_3px_0_0_var(--tavus-terminal-black)] p-4 flex items-start justify-between gap-3 flex-wrap"
        >
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span
                className={`px-2 py-0.5 text-[10px] font-extrabold uppercase border-[2px] border-[var(--tavus-terminal-black)]/40 ${
                  f.severity === "high"
                    ? "bg-[var(--tavus-coral-1)]/25"
                    : f.severity === "medium"
                      ? "bg-[var(--tavus-atomic-glow-5)]"
                      : "bg-[var(--tavus-plastic-2)]"
                }`}
              >
                {f.severity}
              </span>
              <p className="text-[13px] font-extrabold uppercase">{f.kind.replace(/_/g, " ")}</p>
              <p className="text-[11px] font-mono text-[var(--tavus-hardware-gray-8)]">{formatDateTime(f.created_at)}</p>
            </div>
            <p className="text-[12px] mt-1.5">{f.detail}</p>
            <p className="text-[11px] font-mono text-[var(--tavus-hardware-gray-8)] mt-1">
              user {f.user_id.slice(0, 8)}…{f.action_taken ? ` · action: ${f.action_taken}` : ""}
            </p>
          </div>
          <button
            onClick={() => onResolve(f.id)}
            disabled={busyId === f.id}
            className="inline-flex items-center gap-1.5 px-3.5 h-9 border-[2.5px] border-[var(--tavus-terminal-black)] bg-white text-[11px] font-extrabold tracking-[0.1em] uppercase shadow-[2px_2px_0_0_var(--tavus-terminal-black)] hover:shadow-[3px_3px_0_0_var(--tavus-terminal-black)] disabled:opacity-50"
          >
            {busyId === f.id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <XCircle className="w-3.5 h-3.5" />}
            Resolve
          </button>
        </div>
      ))}
    </div>
  );
}
