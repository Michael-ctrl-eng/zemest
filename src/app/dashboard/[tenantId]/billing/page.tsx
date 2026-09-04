"use client";

import { useState, useEffect, useCallback, use } from "react";
import {
  CreditCard,
  Landmark,
  Coins,
  RefreshCw,
  ExternalLink,
  Copy,
  CheckCircle2,
  AlertTriangle,
} from "lucide-react";
import {
  billingApi,
  type BillingPlan,
  type BillingSubscriptionInfo,
  type BillingTransactionItem,
  type SubscribeResponse,
  type RailsResponse,
  type PaymentMethod,
  apiErrorMessage,
} from "@/lib/zemest-api";
import {
  DashHeader,
  TavusButton,
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

const RAIL_LABEL: Record<PaymentMethod, string> = {
  payoneer: "Payoneer",
  paymob: "Paymob",
  usdc_solana: "USDC · Solana",
};

export default function BillingPage({ params }: { params: Promise<{ tenantId: string }> }) {
  const { tenantId } = use(params);
  const [plans, setPlans] = useState<BillingPlan[]>([]);
  const [rails, setRails] = useState<RailsResponse | null>(null);
  const [subscription, setSubscription] = useState<BillingSubscriptionInfo | null>(null);
  const [transactions, setTransactions] = useState<BillingTransactionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyMethod, setBusyMethod] = useState<PaymentMethod | null>(null);
  const [checkout, setCheckout] = useState<SubscribeResponse | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [p, r, s, t] = await Promise.all([
        billingApi.plans(),
        billingApi.rails(),
        billingApi.subscription(tenantId),
        billingApi.transactions(tenantId, 20),
      ]);
      setPlans(p);
      setRails(r);
      setSubscription(s);
      setTransactions(t);
    } catch (err: unknown) {
      setError(apiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [tenantId]);

  useEffect(() => {
    load();
  }, [load]);

  const subscribe = useCallback(
    async (planCode: string, method: PaymentMethod) => {
      setBusyMethod(method);
      setError(null);
      setNotice(null);
      try {
        const res = await billingApi.subscribe(tenantId, planCode, method);
        setCheckout(res);
        if (res.checkout_url) {
          window.open(res.checkout_url, "_blank", "noopener,noreferrer");
        }
        await load();
      } catch (err: unknown) {
        setError(apiErrorMessage(err, "Subscription could not be started"));
      } finally {
        setBusyMethod(null);
      }
    },
    [tenantId, load]
  );

  const usdcCheck = useCallback(async () => {
    setBusyMethod("usdc_solana");
    setError(null);
    setNotice(null);
    try {
      const res = await billingApi.usdcCheck(tenantId);
      if (res.settled_now) {
        setNotice("Payment detected on-chain — your subscription is active.");
        setCheckout(null);
      } else {
        setNotice(
          res.pending_invoice_id
            ? "No matching on-chain payment yet. Detection is automatic after the required confirmations."
            : "No pending USDC invoice."
        );
      }
      await load();
    } catch (err: unknown) {
      setError(apiErrorMessage(err));
    } finally {
      setBusyMethod(null);
    }
  }, [tenantId, load]);

  const cancel = useCallback(
    async (immediate: boolean) => {
      try {
        await billingApi.cancel(tenantId, immediate);
        setNotice(
          immediate
            ? "Subscription canceled immediately."
            : "Cancellation scheduled — you keep every feature until the paid period ends."
        );
        await load();
      } catch (err: unknown) {
        setError(apiErrorMessage(err));
      }
    },
    [tenantId, load]
  );

  const reactivate = useCallback(async () => {
    try {
      await billingApi.reactivate(tenantId);
      setNotice("Scheduled cancellation undone — subscription active.");
      await load();
    } catch (err: unknown) {
      setError(apiErrorMessage(err));
    }
  }, [tenantId, load]);

  if (loading && !subscription) return <LoadingState label="Billing" />;
  if (error && !subscription) return <ErrorState message={error} onRetry={load} />;

  const usdc = checkout?.usdc_instructions ?? null;

  return (
    <div className="space-y-6">
      <DashHeader
        eyebrow="Billing"
        title="Subscription"
        tail="& payments"
        action={
          <TavusButton variant="secondary" onClick={load} title="Refresh">
            <RefreshCw className="w-3.5 h-3.5" />
            Refresh
          </TavusButton>
        }
      />

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

      {/* Current subscription */}
      <WinCard title="Current subscription">
        {subscription && subscription.status !== "none" ? (
          <div className="flex flex-wrap items-center gap-x-8 gap-y-3 text-[13px] font-semibold text-[var(--tavus-terminal-black)]">
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-extrabold tracking-[0.16em] uppercase text-[var(--tavus-hardware-gray-8)]">Status</span>
              <StatusBadge status={subscription.status} />
              {subscription.cancel_at_period_end ? <StatusBadge status="canceled">ends at period end</StatusBadge> : null}
            </div>
            <div>
              <span className="text-[10px] font-extrabold tracking-[0.16em] uppercase text-[var(--tavus-hardware-gray-8)] mr-2">Plan</span>
              {subscription.plan_name ?? "—"}
            </div>
            <div>
              <span className="text-[10px] font-extrabold tracking-[0.16em] uppercase text-[var(--tavus-hardware-gray-8)] mr-2">Rail</span>
              {subscription.payment_method ? RAIL_LABEL[subscription.payment_method] : "—"}
            </div>
            <div>
              <span className="text-[10px] font-extrabold tracking-[0.16em] uppercase text-[var(--tavus-hardware-gray-8)] mr-2">Renews</span>
              {subscription.current_period_end
                ? new Date(subscription.current_period_end).toLocaleDateString("en-EG")
                : "—"}
            </div>
            <div className="flex gap-2 ml-auto">
              {subscription.cancel_at_period_end && subscription.status === "active" ? (
                <TavusButton variant="secondary" onClick={reactivate}>Reactivate</TavusButton>
              ) : subscription.status === "active" ? (
                <TavusButton variant="secondary" onClick={() => cancel(false)}>Cancel at period end</TavusButton>
              ) : null}
            </div>
          </div>
        ) : (
          <EmptyState
            title="No subscription yet"
            hint="Pick a plan below — card (Payoneer), Egyptian rails (Paymob), or USDC crypto."
          />
        )}
      </WinCard>

      {/* Plans + rails */}
      {plans.length > 0 ? (
        <div className="grid gap-4 md:grid-cols-3">
          {plans.map((plan) => (
            <WinCard key={plan.code} title={`${plan.name} · ${plan.price_egp} EGP/mo`}>
              <p className="text-[13px] font-medium text-[var(--tavus-terminal-black)]/80 mb-3">
                {plan.description}
              </p>
              <div className="text-[12px] font-semibold text-[var(--tavus-terminal-black)] space-y-1 mb-4">
                <div>
                  {plan.trial_days > 0 ? `${plan.trial_days}-day free trial · ` : ""}
                  or {plan.price_usdc} USDC/mo
                </div>
                {plan.limits
                  ? Object.entries(plan.limits).map(([k, v]) => (
                      <div key={k} className="text-[var(--tavus-hardware-gray-8)]">
                        {k.replace(/_/g, " ")}: {typeof v === "number" ? v.toLocaleString("en-EG") : v}
                      </div>
                    ))
                  : null}
              </div>
              <div className="space-y-2">
                <RailButton
                  method="payoneer"
                  icon={<CreditCard className="w-3.5 h-3.5" />}
                  caption="Card / wallet · primary"
                  disabled={busyMethod !== null || rails?.rails.find((r) => r.method === "payoneer")?.configured === false}
                  busy={busyMethod === "payoneer"}
                  onClick={() => subscribe(plan.code, "payoneer")}
                />
                <RailButton
                  method="paymob"
                  icon={<Landmark className="w-3.5 h-3.5" />}
                  caption="Egyptian rails · backup"
                  disabled={busyMethod !== null || rails?.rails.find((r) => r.method === "paymob")?.configured === false}
                  busy={busyMethod === "paymob"}
                  onClick={() => subscribe(plan.code, "paymob")}
                />
                <RailButton
                  method="usdc_solana"
                  icon={<Coins className="w-3.5 h-3.5" />}
                  caption={`Crypto · ${plan.price_usdc} USDC`}
                  disabled={busyMethod !== null || rails?.rails.find((r) => r.method === "usdc_solana")?.configured === false}
                  busy={busyMethod === "usdc_solana"}
                  onClick={() => subscribe(plan.code, "usdc_solana")}
                />
              </div>
            </WinCard>
          ))}
        </div>
      ) : null}

      {/* Crypto how-to */}
      <WinCard title="Paying with USDC (Solana) — how it works">
        <ol className="list-decimal list-inside space-y-1.5 text-[13px] font-medium text-[var(--tavus-terminal-black)]/85">
          <li>Pick a plan and choose the <b>USDC · Solana</b> button — we show a one-time deposit address, an exact amount and a reference memo.</li>
          <li>Send <b>exactly that amount</b> of USDC on the <b>Solana network</b> to the deposit address, and put the reference in the transfer memo if your wallet supports it.</li>
          <li>Payment is detected automatically after the required network confirmations — press <b>Check payment</b> to look immediately, or just wait for the hourly sweep.</li>
        </ol>
        <div className="mt-3 text-[12px] font-semibold text-[var(--tavus-hardware-gray-8)]">
          Zemest never holds your private keys and never asks for seed phrases. The treasury only
          watches incoming transfers — wrong amounts cannot activate a plan; contact support to
          sort them out.
        </div>
      </WinCard>

      {/* Active checkout / USDC instructions */}
      {checkout ? (
        <WinCard title={checkout.payment_method === "usdc_solana" ? "USDC payment instructions" : "Complete your payment"}>
          {checkout.payment_method !== "usdc_solana" && checkout.checkout_url ? (
            <div className="space-y-3">
              <p className="text-[13px] font-medium text-[var(--tavus-terminal-black)]/85">
                A secure checkout page was opened in a new tab ({checkout.amount} {checkout.currency} via{" "}
                {RAIL_LABEL[checkout.payment_method]}). Complete the payment there — your subscription
                activates the moment the provider confirms it server-side.
              </p>
              <TavusButton variant="primary" onClick={() => window.open(checkout.checkout_url!, "_blank", "noopener,noreferrer")}>
                <ExternalLink className="w-3.5 h-3.5" />
                Reopen checkout page
              </TavusButton>
            </div>
          ) : null}
          {usdc ? (
            <div className="space-y-3">
              <CopyRow label="Network" value="Solana (USDC)" />
              <CopyRow label="Deposit address" value={usdc.deposit_address} mono />
              <CopyRow label="Exact amount" value={`${usdc.amount_usdc} USDC`} mono />
              <CopyRow label="Reference (memo)" value={usdc.reference_memo} mono />
              <p className="text-[12px] font-semibold text-[var(--tavus-hardware-gray-8)]">
                {usdc.note}
              </p>
              <TavusButton
                variant="primary"
                onClick={usdcCheck}
                disabled={busyMethod !== null}
              >
                {busyMethod === "usdc_solana" ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <CheckCircle2 className="w-3.5 h-3.5" />}
                Check payment now
              </TavusButton>
            </div>
          ) : null}
        </WinCard>
      ) : null}

      {/* Invoice history */}
      <WinCard title="Billing history">
        {transactions.length === 0 ? (
          <EmptyState title="No invoices yet" hint="Your subscription invoices will appear here." />
        ) : (
          <TableShell>
            <thead>
              <tr>
                <Th>Invoice</Th>
                <Th>Rail</Th>
                <Th>Status</Th>
                <Th>Amount</Th>
                <Th>Created</Th>
                <Th>Paid</Th>
              </tr>
            </thead>
            <tbody>
              {transactions.map((t) => (
                <Row key={t.id}>
                  <Td className="font-mono text-[11px]">{t.id.slice(0, 8)}…</Td>
                  <Td>{RAIL_LABEL[t.payment_method] ?? t.payment_method}</Td>
                  <Td><StatusBadge status={t.status} /></Td>
                  <Td>
                    {t.amount} {t.currency}
                    {t.amount_usdc ? ` · ${t.amount_usdc} USDC` : ""}
                  </Td>
                  <Td>{t.created_at ? new Date(t.created_at).toLocaleDateString("en-EG") : "—"}</Td>
                  <Td>{t.paid_at ? new Date(t.paid_at).toLocaleDateString("en-EG") : "—"}</Td>
                </Row>
              ))}
            </tbody>
          </TableShell>
        )}
      </WinCard>
    </div>
  );
}

function RailButton({
  method,
  icon,
  caption,
  busy,
  disabled,
  onClick,
}: {
  method: PaymentMethod;
  icon: React.ReactNode;
  caption: string;
  busy?: boolean;
  disabled?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      data-rail={method}
      className="w-full flex items-center gap-2 px-3 h-10 border-[2.5px] border-[var(--tavus-terminal-black)] bg-white text-[var(--tavus-terminal-black)] text-[11px] font-extrabold tracking-[0.08em] uppercase shadow-[2px_2px_0_0_var(--tavus-terminal-black)] transition-all hover:shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 disabled:opacity-40 disabled:pointer-events-none"
    >
      {busy ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : icon}
      <span>{RAIL_LABEL[method]}</span>
      <span className="ml-auto text-[9px] font-bold tracking-normal normal-case text-[var(--tavus-hardware-gray-8)]">
        {caption}
      </span>
    </button>
  );
}

function CopyRow({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="flex items-center gap-3 flex-wrap">
      <span className="w-36 shrink-0 text-[10px] font-extrabold tracking-[0.16em] uppercase text-[var(--tavus-hardware-gray-8)]">
        {label}
      </span>
      <code className={`flex-1 min-w-0 truncate border-2 border-[var(--tavus-terminal-black)]/20 bg-[var(--tavus-plastic-1)] px-3 py-1.5 text-[12px] font-semibold text-[var(--tavus-terminal-black)] ${mono ? "font-mono" : ""}`}>
        {value}
      </code>
      <button
        onClick={async () => {
          try {
            await navigator.clipboard.writeText(value);
            setCopied(true);
            setTimeout(() => setCopied(false), 1500);
          } catch {
            /* clipboard unavailable */
          }
        }}
        className="inline-flex items-center gap-1 px-2 h-8 border-2 border-[var(--tavus-terminal-black)] bg-white text-[10px] font-extrabold tracking-[0.1em] uppercase"
        title="Copy"
      >
        <Copy className="w-3 h-3" />
        {copied ? "Copied" : "Copy"}
      </button>
    </div>
  );
}
