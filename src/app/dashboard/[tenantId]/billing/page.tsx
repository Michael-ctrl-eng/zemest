"use client";

import { useCallback, useEffect, use, useState } from "react";
import Link from "next/link";
import {
  CreditCard,
  Loader2,
  RefreshCw,
  Receipt,
  Wallet,
  ArrowUpRight,
  XCircle,
  RotateCcw,
  CheckCircle2,
  Clock,
  AlertTriangle,
  Landmark,
  Coins,
  Plus,
  Trash2,
  Banknote,
} from "lucide-react";
import {
  billingApi,
  formatMoney,
  apiErrorMessage,
  type BillingOverview,
  type BillingInvoice,
} from "@/lib/zemest-api";
import { DashHeader, ErrorState, LoadingState, EmptyState } from "@/components/site/dash";

const SUB_STATUS_STYLES: Record<string, { label: string; cls: string }> = {
  active: { label: "Active", cls: "bg-[var(--tavus-signal-green)]/60 text-[var(--tavus-terminal-black)] border-[var(--tavus-terminal-black)]/30" },
  trialing: { label: "Trialing", cls: "bg-[var(--tavus-atomic-glow-5)] text-[var(--tavus-terminal-black)] border-[var(--tavus-terminal-black)]/30" },
  past_due: { label: "Past due", cls: "bg-[var(--tavus-coral-1)]/20 text-[var(--tavus-terminal-black)] border-[var(--tavus-terminal-black)]/30" },
  canceled: { label: "Canceled", cls: "bg-[var(--tavus-plastic-2)] text-[var(--tavus-terminal-black)] border-[var(--tavus-terminal-black)]/30" },
  incomplete: { label: "Incomplete", cls: "bg-[var(--tavus-plastic-2)] text-[var(--tavus-terminal-black)] border-[var(--tavus-terminal-black)]/30" },
};

const INVOICE_STATUS_STYLES: Record<string, { label: string; cls: string }> = {
  paid: { label: "Paid", cls: "bg-[var(--tavus-signal-green)]/50" },
  open: { label: "Open", cls: "bg-[var(--tavus-atomic-glow-5)]" },
  draft: { label: "Draft", cls: "bg-[var(--tavus-plastic-2)]" },
  uncollectible: { label: "Failed", cls: "bg-[var(--tavus-coral-1)]/20" },
  refunded: { label: "Refunded", cls: "bg-[var(--tavus-plastic-2)]" },
  void: { label: "Void", cls: "bg-[var(--tavus-plastic-2)]" },
};

const PAYOUT_STATUS_STYLES: Record<string, { label: string; cls: string }> = {
  pending: { label: "Pending review", cls: "bg-[var(--tavus-atomic-glow-5)]" },
  approved: { label: "Approved", cls: "bg-[var(--tavus-plastic-2)]" },
  processing: { label: "Sending", cls: "bg-[var(--tavus-bubbletech-4)]/60" },
  paid: { label: "Sent", cls: "bg-[var(--tavus-signal-green)]/50" },
  failed: { label: "Failed", cls: "bg-[var(--tavus-coral-1)]/20" },
  canceled: { label: "Canceled", cls: "bg-[var(--tavus-plastic-2)]" },
};

const PLAN_CARDS = [
  {
    key: "growth",
    name: "Growth",
    priceUsd: "$12.99",
    priceEgp: "EGP 299",
    features: ["5 shops / multi-page", "10,000 messages/mo", "Post scheduling", "Blog + SEO toolkit"],
  },
  {
    key: "pro",
    name: "Pro",
    priceUsd: "$34.99",
    priceEgp: "EGP 899",
    features: ["25 shops", "100,000 messages/mo", "API access", "Dedicated support"],
  },
];

const PAYMENT_PROVIDERS = [
  { key: "stripe", label: "Card · Apple Pay · Google Pay", note: "International cards + wallets" },
  { key: "paymob", label: "Paymob (Egypt)", note: "EGP cards, wallets, installments" },
  { key: "payoneer", label: "Payoneer", note: "Pay from your Payoneer balance" },
];

export default function BillingPage({ params }: { params: Promise<{ tenantId: string }> }) {
  const { tenantId } = use(params);
  const [data, setData] = useState<BillingOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // subscribe state
  const [selectedPlan, setSelectedPlan] = useState<string>("growth");
  const [selectedProvider, setSelectedProvider] = useState<string>("stripe");
  const [subscribing, setSubscribing] = useState(false);
  const [subscribeError, setSubscribeError] = useState<string | null>(null);

  // cancel/reactivate state
  const [cancelling, setCancelling] = useState(false);
  const [actionNote, setActionNote] = useState<string | null>(null);

  // payout account state
  const [payoutMethod, setPayoutMethod] = useState("skale");
  const [payoutDetails, setPayoutDetails] = useState("");
  const [payoutLabel, setPayoutLabel] = useState("");
  const [addingAccount, setAddingAccount] = useState(false);
  const [accountError, setAccountError] = useState<string | null>(null);

  // payout request state
  const [payoutAccountId, setPayoutAccountId] = useState("");
  const [payoutAmount, setPayoutAmount] = useState("");
  const [requestingPayout, setRequestingPayout] = useState(false);
  const [payoutError, setPayoutError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await billingApi.overview());
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load billing");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function subscribe(plan: string) {
    setSubscribing(true);
    setSubscribeError(null);
    setActionNote(null);
    try {
      const result = await billingApi.subscribe(
        plan,
        selectedProvider,
        `/dashboard/${tenantId}/billing`
      );
      if (result.checkout?.url) {
        window.location.href = result.checkout.url;
        return;
      }
      setActionNote(
        `Invoice ${result.invoice_number} created (${formatMoney(result.invoice_amount, result.invoice_currency)}). Complete the payment — your plan activates the moment the payment is confirmed.`
      );
      await load();
    } catch (err: unknown) {
      setSubscribeError(apiErrorMessage(err, "Could not start the subscription"));
    } finally {
      setSubscribing(false);
    }
  }

  async function cancel(immediate: boolean) {
    setCancelling(true);
    setActionNote(null);
    try {
      await billingApi.cancel(immediate);
      setActionNote(
        immediate
          ? "Subscription canceled — your account is back on the free plan."
          : "Cancellation scheduled — you keep every feature until the end of the period you paid for."
      );
      await load();
    } catch (err: unknown) {
      setActionNote(null);
      setError(apiErrorMessage(err, "Could not cancel"));
    } finally {
      setCancelling(false);
    }
  }

  async function reactivate() {
    setCancelling(true);
    setActionNote(null);
    try {
      await billingApi.reactivate();
      setActionNote("Subscription reactivated — the scheduled cancellation was undone.");
      await load();
    } catch (err: unknown) {
      setActionNote(null);
      setError(apiErrorMessage(err, "Could not reactivate"));
    } finally {
      setCancelling(false);
    }
  }

  async function addPayoutAccount(e: React.FormEvent) {
    e.preventDefault();
    if (!payoutDetails.trim()) return;
    setAddingAccount(true);
    setAccountError(null);
    try {
      await billingApi.addPayoutAccount(
        payoutMethod,
        payoutDetails.trim(),
        payoutLabel.trim() || null
      );
      setPayoutDetails("");
      setPayoutLabel("");
      setActionNote("Payout destination added.");
      await load();
    } catch (err: unknown) {
      setAccountError(apiErrorMessage(err, "Could not add the payout account"));
    } finally {
      setAddingAccount(false);
    }
  }

  async function requestPayout(e: React.FormEvent) {
    e.preventDefault();
    const amount = Math.round(parseFloat(payoutAmount || "0") * 100);
    if (!payoutAccountId || !Number.isFinite(amount) || amount <= 0) return;
    setRequestingPayout(true);
    setPayoutError(null);
    try {
      const result = await billingApi.requestPayout(payoutAccountId, amount);
      setPayoutAmount("");
      setActionNote(
        result.status === "paid"
          ? `Payout sent — ${formatMoney(result.net_amount)} via ${result.rail}.`
          : `Payout request received (${formatMoney(result.net_amount)} via ${result.rail}). You'll see the status update here.`
      );
      await load();
    } catch (err: unknown) {
      setPayoutError(apiErrorMessage(err, "Could not request the payout"));
    } finally {
      setRequestingPayout(false);
    }
  }

  const sub = data?.subscription;
  const subStatus = SUB_STATUS_STYLES[sub?.status ?? ""] ?? SUB_STATUS_STYLES.incomplete;
  const activePaid = sub?.status === "active" || sub?.status === "trialing";
  const openInvoice = data?.open_invoice;
  const payoutAccounts = data?.payouts.accounts ?? [];
  const payoutRequests = data?.payouts.requests ?? [];

  return (
    <div className="space-y-6">
      <DashHeader
        title="Billing"
        description="Your subscription, invoices and payouts — plans activate automatically the moment a payment is confirmed."
      />

      {actionNote ? (
        <p className="text-sm font-semibold border-[2px] border-[var(--tavus-terminal-black)]/30 bg-[var(--tavus-signal-green)]/25 px-3 py-2">
          {actionNote}
        </p>
      ) : null}

      {/* --- Current subscription ---------------------------------------- */}
      <div className="border-[3px] border-[var(--tavus-terminal-black)] bg-white shadow-[4px_4px_0_0_var(--tavus-terminal-black)]">
        <div className="flex items-center justify-between border-b-[3px] border-[var(--tavus-terminal-black)] px-5 py-3.5">
          <div className="flex items-center gap-2">
            <CreditCard className="w-4 h-4" strokeWidth={2.5} />
            <h2 className="text-sm font-extrabold tracking-[0.08em] uppercase">Subscription</h2>
          </div>
          <button
            onClick={load}
            disabled={loading}
            className="inline-flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wide border-[2px] border-[var(--tavus-terminal-black)]/40 px-2.5 py-1.5 hover:border-[var(--tavus-terminal-black)] hover:bg-[var(--tavus-plastic-2)] disabled:opacity-50 transition-all"
          >
            <RefreshCw className={`w-3 h-3 ${loading ? "animate-spin" : ""}`} strokeWidth={2.5} />
            Refresh
          </button>
        </div>

        <div className="p-5">
          {loading && !data ? (
            <LoadingState label="Loading billing" />
          ) : error && !data ? (
            <ErrorState message={error} onRetry={load} />
          ) : !sub ? (
            <EmptyState
              title="No subscription yet"
              description="You're on the free plan. Pick a plan below — features unlock automatically after the first payment."
            />
          ) : (
            <div className="space-y-4">
              <div className="flex items-start justify-between gap-3 flex-wrap">
                <div>
                  <p className="text-lg font-extrabold">
                    Zemest {sub.plan === "pro" ? "Pro" : "Growth"}
                    <span className="ml-2 text-[11px] font-mono font-bold uppercase text-[var(--tavus-hardware-gray-8)]">
                      via {sub.provider}
                    </span>
                  </p>
                  <p className="text-xs font-mono text-[var(--tavus-hardware-gray-8)] mt-1">
                    {sub.current_period_end
                      ? `Renews ${new Date(sub.current_period_end).toLocaleDateString("en-EG")}`
                      : "—"}
                  </p>
                </div>
                <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 border-[2px] text-[10px] font-extrabold tracking-[0.08em] uppercase ${subStatus.cls}`}>
                  {subStatus.label}
                </span>
              </div>

              {openInvoice && openInvoice.status === "open" ? (
                <div className="border-[2.5px] border-[var(--tavus-terminal-black)]/25 p-4 flex items-center justify-between gap-3 flex-wrap bg-[var(--tavus-atomic-glow-5)]/40">
                  <div>
                    <p className="text-sm font-bold">
                      Invoice {openInvoice.number} — {formatMoney(openInvoice.amount, openInvoice.currency)}
                    </p>
                    <p className="text-[11px] text-[var(--tavus-hardware-gray-8)] mt-0.5">
                      Awaiting payment. Your plan activates the moment it clears.
                    </p>
                  </div>
                  {openInvoice.payment_url ? (
                    <Link
                      href={openInvoice.payment_url}
                      target="_blank"
                      className="inline-flex items-center gap-1.5 px-4 h-9 border-[2.5px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-coral-1)] text-white text-[11px] font-extrabold tracking-[0.1em] uppercase shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:shadow-[4px_4px_0_0_var(--tavus-terminal-black)] hover:-translate-y-0.5 transition-all"
                    >
                      <Banknote className="w-3.5 h-3.5" />
                      Pay now
                    </Link>
                  ) : null}
                </div>
              ) : null}

              {sub.cancel_at_period_end ? (
                <div className="flex flex-wrap items-center gap-3 border-[2.5px] border-[var(--tavus-terminal-black)]/25 p-4 bg-[var(--tavus-coral-1)]/10">
                  <AlertTriangle className="w-4 h-4 shrink-0" strokeWidth={2.5} />
                  <p className="text-[13px] font-semibold flex-1 min-w-[200px]">
                    Cancellation scheduled — features stay on until{" "}
                    {sub.current_period_end
                      ? new Date(sub.current_period_end).toLocaleDateString("en-EG")
                      : "period end"}
                    .
                  </p>
                  <button
                    onClick={reactivate}
                    disabled={cancelling}
                    className="inline-flex items-center gap-1.5 px-4 h-9 border-[2.5px] border-[var(--tavus-terminal-black)] bg-white text-[11px] font-extrabold tracking-[0.1em] uppercase shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:shadow-[4px_4px_0_0_var(--tavus-terminal-black)] hover:-translate-y-0.5 transition-all disabled:opacity-50"
                  >
                    {cancelling ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RotateCcw className="w-3.5 h-3.5" />}
                    Reactivate
                  </button>
                </div>
              ) : activePaid ? (
                <div className="flex flex-wrap items-center gap-3">
                  <button
                    onClick={() => cancel(false)}
                    disabled={cancelling}
                    className="inline-flex items-center gap-1.5 px-4 h-9 border-[2.5px] border-[var(--tavus-terminal-black)] bg-white text-[11px] font-extrabold tracking-[0.1em] uppercase shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:shadow-[4px_4px_0_0_var(--tavus-terminal-black)] hover:-translate-y-0.5 transition-all disabled:opacity-50"
                  >
                    {cancelling ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <XCircle className="w-3.5 h-3.5" />}
                    Cancel (keep until period end)
                  </button>
                </div>
              ) : null}
            </div>
          )}
        </div>
      </div>

      {/* --- Plan picker -------------------------------------------------- */}
      <div className="border-[3px] border-[var(--tavus-terminal-black)] bg-white shadow-[4px_4px_0_0_var(--tavus-terminal-black)]">
        <div className="border-b-[3px] border-[var(--tavus-terminal-black)] px-5 py-3.5 flex items-center gap-2">
          <ArrowUpRight className="w-4 h-4" strokeWidth={2.5} />
          <h2 className="text-sm font-extrabold tracking-[0.08em] uppercase">Upgrade plan</h2>
        </div>
        <div className="p-5 space-y-5">
          <div className="grid gap-4 sm:grid-cols-2">
            {PLAN_CARDS.map((plan) => {
              const isCurrent = sub?.plan === plan.key && activePaid;
              const isPicked = selectedPlan === plan.key;
              return (
                <button
                  key={plan.key}
                  onClick={() => setSelectedPlan(plan.key)}
                  className={`text-left border-[3px] p-4 space-y-2 transition-all ${
                    isPicked
                      ? "border-[var(--tavus-terminal-black)] bg-[var(--tavus-bubbletech-4)]/40 shadow-[3px_3px_0_0_var(--tavus-terminal-black)]"
                      : "border-[var(--tavus-terminal-black)]/25 bg-white hover:border-[var(--tavus-terminal-black)]/60"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-extrabold uppercase tracking-wide">{plan.name}</p>
                    {isCurrent ? (
                      <span className="px-2 py-0.5 text-[9px] font-extrabold uppercase border-[2px] border-[var(--tavus-terminal-black)]/40 bg-white">
                        Current
                      </span>
                    ) : null}
                  </div>
                  <p className="text-2xl font-extrabold">
                    {plan.priceUsd}
                    <span className="text-xs font-bold text-[var(--tavus-hardware-gray-8)]"> /mo</span>
                  </p>
                  <p className="text-[11px] font-mono text-[var(--tavus-hardware-gray-8)]">{plan.priceEgp} for Egypt</p>
                  <ul className="space-y-1 pt-1">
                    {plan.features.map((f) => (
                      <li key={f} className="text-[12px] font-semibold flex items-center gap-1.5">
                        <CheckCircle2 className="w-3 h-3 shrink-0" strokeWidth={2.5} />
                        {f}
                      </li>
                    ))}
                  </ul>
                </button>
              );
            })}
          </div>

          <div>
            <p className="text-xs font-bold uppercase tracking-wide mb-2">Pay with</p>
            <div className="grid gap-2 sm:grid-cols-3">
              {PAYMENT_PROVIDERS.map((p) => {
                const enabled =
                  (p.key === "stripe" && data?.rails.stripe_enabled) ||
                  (p.key === "paymob" && data?.rails.paymob_enabled) ||
                  (p.key === "payoneer" && data?.rails.payoneer_checkout);
                const isPicked = selectedProvider === p.key;
                return (
                  <button
                    key={p.key}
                    onClick={() => setSelectedProvider(p.key)}
                    disabled={!enabled}
                    className={`text-left border-[2.5px] px-3 py-2.5 transition-all disabled:opacity-40 disabled:cursor-not-allowed ${
                      isPicked
                        ? "border-[var(--tavus-terminal-black)] bg-[var(--tavus-plastic-2)] shadow-[2px_2px_0_0_var(--tavus-terminal-black)]"
                        : "border-[var(--tavus-terminal-black)]/25 hover:border-[var(--tavus-terminal-black)]/60"
                    }`}
                  >
                    <p className="text-[12px] font-extrabold">{p.label}</p>
                    <p className="text-[10px] text-[var(--tavus-hardware-gray-8)] mt-0.5">
                      {enabled ? p.note : "Not configured"}
                    </p>
                  </button>
                );
              })}
            </div>
          </div>

          {subscribeError ? (
            <p className="text-sm font-semibold text-red-700 border-[2px] border-red-700/40 bg-red-50 px-3 py-2">
              {subscribeError}
            </p>
          ) : null}

          <button
            onClick={() => subscribe(selectedPlan)}
            disabled={subscribing || (activePaid && sub?.plan === selectedPlan)}
            className="inline-flex items-center gap-2 px-5 h-10 border-[2.5px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-coral-1)] text-white text-[11px] font-extrabold tracking-[0.1em] uppercase shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:shadow-[4px_4px_0_0_var(--tavus-terminal-black)] hover:-translate-y-0.5 transition-all disabled:opacity-50 disabled:translate-y-0 disabled:shadow-[3px_3px_0_0_var(--tavus-terminal-black)]"
          >
            {subscribing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <CreditCard className="w-3.5 h-3.5" />}
            Subscribe monthly
          </button>
        </div>
      </div>

      {/* --- Invoices ----------------------------------------------------- */}
      <div className="border-[3px] border-[var(--tavus-terminal-black)] bg-white shadow-[4px_4px_0_0_var(--tavus-terminal-black)]">
        <div className="border-b-[3px] border-[var(--tavus-terminal-black)] px-5 py-3.5 flex items-center gap-2">
          <Receipt className="w-4 h-4" strokeWidth={2.5} />
          <h2 className="text-sm font-extrabold tracking-[0.08em] uppercase">Invoices</h2>
        </div>
        <div className="p-5">
          {!data || data.invoices.length === 0 ? (
            <EmptyState title="No invoices yet" description="Invoices appear here the moment you subscribe." />
          ) : (
            <ul className="space-y-3">
              {data.invoices.map((inv) => (
                <InvoiceRow key={inv.id} invoice={inv} />
              ))}
            </ul>
          )}
        </div>
      </div>

      {/* --- Payouts ------------------------------------------------------ */}
      <div className="border-[3px] border-[var(--tavus-terminal-black)] bg-white shadow-[4px_4px_0_0_var(--tavus-terminal-black)]">
        <div className="flex items-center justify-between border-b-[3px] border-[var(--tavus-terminal-black)] px-5 py-3.5">
          <div className="flex items-center gap-2">
            <Wallet className="w-4 h-4" strokeWidth={2.5} />
            <h2 className="text-sm font-extrabold tracking-[0.08em] uppercase">Payouts</h2>
          </div>
          <div className="text-right">
            <p className="text-[10px] font-extrabold uppercase tracking-wide text-[var(--tavus-hardware-gray-8)]">
              Available
            </p>
            <p className="text-lg font-extrabold">
              {formatMoney(data?.payouts.available_balance ?? 0, data?.payouts.currency ?? "USD")}
            </p>
          </div>
        </div>
        <div className="p-5 space-y-5">
          {/* Add destination */}
          <form onSubmit={addPayoutAccount} className="space-y-3">
            <p className="text-xs font-bold uppercase tracking-wide">Add payout destination</p>
            <div className="grid gap-2 sm:grid-cols-3">
              {[
                { key: "skale", label: "SKALE (USDC)", icon: Coins, hint: "Wallet address 0x… — instant, gas-free" },
                { key: "payoneer", label: "Payoneer", icon: Landmark, hint: "Payee ID — to Egypt bank / any country" },
                { key: "bank_egypt", label: "Egypt bank", icon: Landmark, hint: "Account details (encrypted)" },
              ].map((m) => {
                const isPicked = payoutMethod === m.key;
                return (
                  <button
                    key={m.key}
                    type="button"
                    onClick={() => setPayoutMethod(m.key)}
                    className={`text-left border-[2.5px] px-3 py-2.5 transition-all ${
                      isPicked
                        ? "border-[var(--tavus-terminal-black)] bg-[var(--tavus-plastic-2)] shadow-[2px_2px_0_0_var(--tavus-terminal-black)]"
                        : "border-[var(--tavus-terminal-black)]/25 hover:border-[var(--tavus-terminal-black)]/60"
                    }`}
                  >
                    <p className="text-[12px] font-extrabold flex items-center gap-1.5">
                      <m.icon className="w-3.5 h-3.5" strokeWidth={2.5} />
                      {m.label}
                    </p>
                    <p className="text-[10px] text-[var(--tavus-hardware-gray-8)] mt-0.5">{m.hint}</p>
                  </button>
                );
              })}
            </div>
            <div className="grid gap-2 sm:grid-cols-[2fr_1fr_auto]">
              <input
                value={payoutDetails}
                onChange={(e) => setPayoutDetails(e.target.value)}
                placeholder={
                  payoutMethod === "skale"
                    ? "0x71C7…wallet address"
                    : payoutMethod === "payoneer"
                      ? "Payoneer payee ID"
                      : "Bank account details"
                }
                maxLength={2000}
                className="border-[2.5px] border-[var(--tavus-terminal-black)] px-3 py-2.5 text-sm bg-white focus:outline-none focus:shadow-[3px_3px_0_0_var(--tavus-terminal-black)]"
                required
              />
              <input
                value={payoutLabel}
                onChange={(e) => setPayoutLabel(e.target.value)}
                placeholder="Label (optional)"
                maxLength={80}
                className="border-[2.5px] border-[var(--tavus-terminal-black)] px-3 py-2.5 text-sm bg-white focus:outline-none focus:shadow-[3px_3px_0_0_var(--tavus-terminal-black)]"
              />
              <button
                type="submit"
                disabled={addingAccount || !payoutDetails.trim()}
                className="inline-flex items-center gap-1.5 px-4 h-[42px] border-[2.5px] border-[var(--tavus-terminal-black)] bg-white text-[11px] font-extrabold tracking-[0.1em] uppercase shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:shadow-[4px_4px_0_0_var(--tavus-terminal-black)] hover:-translate-y-0.5 transition-all disabled:opacity-50"
              >
                {addingAccount ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />}
                Add
              </button>
            </div>
            {accountError ? (
              <p className="text-sm font-semibold text-red-700 border-[2px] border-red-700/40 bg-red-50 px-3 py-2">
                {accountError}
              </p>
            ) : null}
          </form>

          {/* Destinations list */}
          {payoutAccounts.length > 0 ? (
            <div className="space-y-2">
              <p className="text-xs font-bold uppercase tracking-wide">Destinations</p>
              <ul className="space-y-2">
                {payoutAccounts.map((a) => (
                  <li
                    key={a.id}
                    className="border-[2.5px] border-[var(--tavus-terminal-black)]/25 p-3 flex items-center justify-between gap-3 flex-wrap"
                  >
                    <div className="min-w-0">
                      <p className="text-[13px] font-bold">
                        {a.label || a.method.replace("_", " ")}
                        <span className="ml-2 font-mono text-[11px] text-[var(--tavus-hardware-gray-8)]">{a.masked}</span>
                      </p>
                      <p className="text-[10px] font-extrabold uppercase tracking-wide text-[var(--tavus-hardware-gray-8)] mt-0.5">
                        {a.method.replace("_", " ")} · {a.status}
                      </p>
                    </div>
                    <button
                      onClick={async () => {
                        await billingApi.removePayoutAccount(a.id).catch(() => undefined);
                        await load();
                      }}
                      className="inline-flex items-center gap-1 text-[11px] font-bold uppercase border-[2px] border-red-700/40 text-red-700 px-2.5 py-1.5 hover:bg-red-50"
                    >
                      <Trash2 className="w-3 h-3" strokeWidth={2.5} />
                      Remove
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          {/* Request payout */}
          {data && data.payouts.available_balance > 0 ? (
            <form onSubmit={requestPayout} className="space-y-3 border-[2.5px] border-[var(--tavus-terminal-black)]/25 p-4">
              <p className="text-xs font-bold uppercase tracking-wide">Request a payout</p>
              <div className="grid gap-2 sm:grid-cols-[2fr_1fr_auto]">
                <select
                  value={payoutAccountId}
                  onChange={(e) => setPayoutAccountId(e.target.value)}
                  className="border-[2.5px] border-[var(--tavus-terminal-black)] px-3 py-2.5 text-sm bg-white focus:outline-none"
                  required
                >
                  <option value="">Choose destination…</option>
                  {payoutAccounts
                    .filter((a) => a.status === "verified")
                    .map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.label || a.method} ({a.masked})
                      </option>
                    ))}
                </select>
                <input
                  value={payoutAmount}
                  onChange={(e) => setPayoutAmount(e.target.value)}
                  placeholder={`Min ${formatMoney(data.payouts.min_amount, data.payouts.currency)}`}
                  inputMode="decimal"
                  className="border-[2.5px] border-[var(--tavus-terminal-black)] px-3 py-2.5 text-sm bg-white focus:outline-none"
                  required
                />
                <button
                  type="submit"
                  disabled={requestingPayout || !payoutAccountId}
                  className="inline-flex items-center gap-1.5 px-4 h-[42px] border-[2.5px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-coral-1)] text-white text-[11px] font-extrabold tracking-[0.1em] uppercase shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:shadow-[4px_4px_0_0_var(--tavus-terminal-black)] hover:-translate-y-0.5 transition-all disabled:opacity-50"
                >
                  {requestingPayout ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Banknote className="w-3.5 h-3.5" />}
                  Request
                </button>
              </div>
              {payoutError ? (
                <p className="text-sm font-semibold text-red-700 border-[2px] border-red-700/40 bg-red-50 px-3 py-2">
                  {payoutError}
                </p>
              ) : null}
            </form>
          ) : null}

          {/* Payout history */}
          {payoutRequests.length > 0 ? (
            <div className="space-y-2">
              <p className="text-xs font-bold uppercase tracking-wide">History</p>
              <ul className="space-y-2">
                {payoutRequests.map((p) => {
                  const st = PAYOUT_STATUS_STYLES[p.status] ?? PAYOUT_STATUS_STYLES.pending;
                  return (
                    <li
                      key={p.id}
                      className="border-[2.5px] border-[var(--tavus-terminal-black)]/25 p-3 flex items-start justify-between gap-3 flex-wrap"
                    >
                      <div className="min-w-0">
                        <p className="text-[13px] font-bold">
                          {formatMoney(p.net_amount, p.currency)} via {p.rail}
                        </p>
                        <p className="text-[11px] font-mono text-[var(--tavus-hardware-gray-8)]">
                          {p.requested_at ? new Date(p.requested_at).toLocaleDateString("en-EG") : ""}
                          {p.tx_hash ? ` · ${p.tx_hash.slice(0, 14)}…` : ""}
                        </p>
                        {p.failure_reason ? (
                          <p className="text-[11px] text-red-700 mt-1">{p.failure_reason}</p>
                        ) : null}
                      </div>
                      <span className={`px-2.5 py-1 border-[2px] border-[var(--tavus-terminal-black)]/30 text-[10px] font-extrabold tracking-[0.08em] uppercase ${st.cls}`}>
                        {st.label}
                      </span>
                    </li>
                  );
                })}
              </ul>
            </div>
          ) : null}
        </div>
      </div>

      {/* Saved payment methods (display only) */}
      {data && data.payment_methods.length > 0 ? (
        <div className="border-[3px] border-[var(--tavus-terminal-black)] bg-white shadow-[4px_4px_0_0_var(--tavus-terminal-black)]">
          <div className="border-b-[3px] border-[var(--tavus-terminal-black)] px-5 py-3.5 flex items-center gap-2">
            <CreditCard className="w-4 h-4" strokeWidth={2.5} />
            <h2 className="text-sm font-extrabold tracking-[0.08em] uppercase">Payment methods</h2>
          </div>
          <div className="p-5">
            <ul className="space-y-2">
              {data.payment_methods.map((m) => (
                <li
                  key={m.id}
                  className="border-[2.5px] border-[var(--tavus-terminal-black)]/25 p-3 flex items-center justify-between gap-3 flex-wrap"
                >
                  <p className="text-[13px] font-bold">
                    {m.brand || m.kind.replace("_", " ")} {m.last4 ? `···${m.last4}` : ""}
                    <span className="ml-2 text-[10px] font-extrabold uppercase text-[var(--tavus-hardware-gray-8)]">
                      {m.provider}
                    </span>
                  </p>
                  <div className="flex items-center gap-2">
                    {m.is_default ? (
                      <span className="px-2 py-0.5 text-[9px] font-extrabold uppercase border-[2px] border-[var(--tavus-terminal-black)]/40 bg-[var(--tavus-bubbletech-4)]/60">
                        Default
                      </span>
                    ) : null}
                    <button
                      onClick={async () => {
                        await billingApi.detachMethod(m.id).catch(() => undefined);
                        await load();
                      }}
                      className="inline-flex items-center gap-1 text-[11px] font-bold uppercase border-[2px] border-red-700/40 text-red-700 px-2.5 py-1.5 hover:bg-red-50"
                    >
                      <Trash2 className="w-3 h-3" strokeWidth={2.5} />
                      Remove
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function InvoiceRow({ invoice }: { invoice: BillingInvoice }) {
  const [open, setOpen] = useState(false);
  const st = INVOICE_STATUS_STYLES[invoice.status] ?? INVOICE_STATUS_STYLES.open;
  const when = invoice.paid_at ?? invoice.period_start;
  return (
    <li className="border-[2.5px] border-[var(--tavus-terminal-black)]/25">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full p-3 flex items-center justify-between gap-3 flex-wrap text-left hover:bg-[var(--tavus-plastic-2)]/40 transition-colors"
      >
        <div className="min-w-0">
          <p className="text-[13px] font-bold">
            {invoice.number}
            {when ? (
              <span className="ml-2 text-[11px] text-[var(--tavus-hardware-gray-8)] font-mono">
                {new Date(when).toLocaleDateString("en-EG")}
              </span>
            ) : null}
          </p>
          <p className="text-[12px] font-mono text-[var(--tavus-hardware-gray-8)]">
            Zemest {invoice.plan === "pro" ? "Pro" : "Growth"} · monthly
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <p className="text-[13px] font-extrabold">{formatMoney(invoice.amount, invoice.currency)}</p>
          <span className={`px-2.5 py-1 border-[2px] border-[var(--tavus-terminal-black)]/30 text-[10px] font-extrabold tracking-[0.08em] uppercase ${st.cls}`}>
            {st.label}
          </span>
          {invoice.status === "open" && invoice.payment_url ? (
            <Link
              href={invoice.payment_url}
              target="_blank"
              onClick={(e) => e.stopPropagation()}
              className="inline-flex items-center gap-1 px-3 h-8 border-[2px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-coral-1)] text-white text-[10px] font-extrabold uppercase tracking-wide shadow-[2px_2px_0_0_var(--tavus-terminal-black)]"
            >
              <Banknote className="w-3 h-3" />
              Pay
            </Link>
          ) : null}
        </div>
      </button>
      {open ? (
        <div className="border-t-[2px] border-dashed border-[var(--tavus-terminal-black)]/20 p-3 space-y-1">
          {invoice.line_items?.map((item) => (
            <div key={item.description} className="flex items-center justify-between text-[12px]">
              <span className="font-semibold">{item.description}</span>
              <span className="font-mono">{formatMoney(item.amount, item.currency)}</span>
            </div>
          ))}
          {invoice.paid_at ? (
            <p className="text-[11px] font-mono text-[var(--tavus-hardware-gray-8)] pt-1 flex items-center gap-1">
              <Clock className="w-3 h-3" /> Paid {new Date(invoice.paid_at).toLocaleString("en-EG")}
            </p>
          ) : null}
        </div>
      ) : null}
    </li>
  );
}
