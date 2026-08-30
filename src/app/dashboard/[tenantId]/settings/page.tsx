"use client";

import { useState, useEffect, useCallback, use } from "react";
import { ChevronDown, Store, Truck, Facebook, Instagram, MessageCircle as WhatsApp, CreditCard, Code, Loader2, RefreshCw, CheckCircle, AlertTriangle } from "lucide-react";
import { tenantsApi, toNumber, type Tenant } from "@/lib/zemest-api";
import { toast } from "@/components/site/toast";
import {
  DashHeader,
  TavusButton,
  LoadingState,
  ErrorState,
  Field,
  inputClass,
} from "@/components/site/dash";

interface SettingsForm {
  page_name: string;
  website_url: string;
  business_phone: string;
  business_email: string;
  delivery_inside_cairo: string;
  delivery_outside_cairo: string;
  free_delivery_above: string;
}

const EMPTY_FORM: SettingsForm = {
  page_name: "",
  website_url: "",
  business_phone: "",
  business_email: "",
  delivery_inside_cairo: "",
  delivery_outside_cairo: "",
  free_delivery_above: "",
};

function formFromTenant(t: Tenant): SettingsForm {
  return {
    page_name: t.page_name ?? "",
    website_url: t.website_url ?? "",
    business_phone: t.business_phone ?? "",
    business_email: t.business_email ?? "",
    delivery_inside_cairo: t.delivery_inside_cairo === null || t.delivery_inside_cairo === undefined ? "" : String(t.delivery_inside_cairo),
    delivery_outside_cairo: t.delivery_outside_cairo === null || t.delivery_outside_cairo === undefined ? "" : String(t.delivery_outside_cairo),
    free_delivery_above: t.free_delivery_above === null || t.free_delivery_above === undefined ? "" : String(t.free_delivery_above),
  };
}

export default function SettingsPage({ params }: { params: Promise<{ tenantId: string }> }) {
  const { tenantId } = use(params);
  const [form, setForm] = useState<SettingsForm>(EMPTY_FORM);
  const [loaded, setLoaded] = useState<Tenant | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const [open, setOpen] = useState<string>("business");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const t = await tenantsApi.get(tenantId);
      setLoaded(t);
      setForm(formFromTenant(t));
      setSavedAt(null);
      setSaveError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load settings");
    } finally {
      setLoading(false);
    }
  }, [tenantId]);

  useEffect(() => {
    load();
  }, [load]);

  function setField<K extends keyof SettingsForm>(key: K, value: string) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function handleSave() {
    if (!form.page_name.trim()) {
      setSaveError("Page name is required.");
      return;
    }
    setSaving(true);
    setSaveError(null);
    try {
      const updated = await tenantsApi.update(tenantId, {
        page_name: form.page_name.trim(),
        website_url: form.website_url.trim() || null,
        business_phone: form.business_phone.trim() || null,
        business_email: form.business_email.trim() || null,
        delivery_inside_cairo: form.delivery_inside_cairo.trim() === "" ? null : Number(form.delivery_inside_cairo),
        delivery_outside_cairo: form.delivery_outside_cairo.trim() === "" ? null : Number(form.delivery_outside_cairo),
        free_delivery_above: form.free_delivery_above.trim() === "" ? null : Number(form.free_delivery_above),
      });
      if (updated) {
        setLoaded(updated);
        setForm(formFromTenant(updated));
      } else {
        // 204 No Content — re-fetch to sync the form with stored values
        await load();
        setSavedAt(null);
      }
      setSavedAt(new Date().toLocaleTimeString("en-EG", { hour: "2-digit", minute: "2-digit" }));
      toast.success("Settings saved successfully.");
    } catch (err: unknown) {
      setSaveError(err instanceof Error ? err.message : "Failed to save settings");
      toast.error("Failed to save settings.");
    } finally {
      setSaving(false);
    }
  }

  const dirty = loaded !== null && JSON.stringify(form) !== JSON.stringify(formFromTenant(loaded));

  return (
    <div className="space-y-6">
      {/* Header */}
      <DashHeader
        eyebrow="Settings"
        title="Business"
        tail="settings"
        action={
          <button
            onClick={load}
            title="Reload"
            aria-label="Reload"
            className="inline-flex items-center justify-center w-11 h-11 border-[3px] border-[var(--tavus-terminal-black)] bg-white shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:shadow-[4px_4px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] transition-all"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} strokeWidth={2.5} />
          </button>
        }
      />

      {/* Error state */}
      {error ? <ErrorState message={error} onRetry={load} /> : null}

      {/* Loading state */}
      {loading ? <LoadingState label="Loading settings" /> : null}

      {!loading && !error ? (
        <>
          {/* Saved confirmation */}
          {savedAt && !saveError ? (
            <div className="flex items-center gap-3 border-[3px] border-[var(--tavus-signal-green-2)] bg-[var(--tavus-signal-green)]/15 p-4">
              <CheckCircle className="w-5 h-5 text-[var(--tavus-terminal-black)] shrink-0" strokeWidth={2.5} />
              <div className="text-sm font-bold text-[var(--tavus-terminal-black)]">
                Settings saved at {savedAt}. Your AI agent uses these values immediately.
              </div>
            </div>
          ) : null}

          {/* Save error */}
          {saveError ? (
            <div className="flex items-center gap-3 border-[3px] border-[var(--tavus-coral-1)] bg-[var(--tavus-coral-3)]/40 p-4">
              <AlertTriangle className="w-5 h-5 text-[var(--tavus-terminal-black)] shrink-0" strokeWidth={2.5} />
              <div className="text-sm font-bold text-[var(--tavus-terminal-black)]">{saveError}</div>
            </div>
          ) : null}

          {/* Save bar */}
          <div className="flex items-center gap-3 flex-wrap">
            <TavusButton onClick={handleSave} disabled={saving || !dirty} className="h-11 px-5">
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
              {saving ? "Saving…" : "Save changes"}
            </TavusButton>
            <TavusButton
              onClick={() => loaded && setForm(formFromTenant(loaded))}
              disabled={!dirty || saving}
              variant="secondary"
              className="h-11 px-5"
            >
              Discard
            </TavusButton>
            {dirty ? (
              <span className="text-[10px] font-bold tracking-[0.14em] uppercase text-[var(--tavus-atomic-glow-3)]">Unsaved changes</span>
            ) : null}
          </div>

          <div className="space-y-3">
            {/* Business settings */}
            <SettingsSection
              id="business"
              label="BUSINESS SETTINGS"
              icon={Store}
              color="var(--tavus-bubbletech-4)"
              open={open === "business"}
              onToggle={() => setOpen(open === "business" ? "" : "business")}
            >
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <Field label="PAGE NAME *">
                  <input
                    type="text"
                    value={form.page_name}
                    onChange={(e) => setField("page_name", e.target.value)}
                    placeholder="My Store"
                    className={inputClass}
                  />
                </Field>
                <Field label="WEBSITE URL">
                  <input
                    type="url"
                    value={form.website_url}
                    onChange={(e) => setField("website_url", e.target.value)}
                    placeholder="https://mystore.com"
                    className={inputClass}
                  />
                </Field>
                <Field label="BUSINESS EMAIL">
                  <input
                    type="email"
                    value={form.business_email}
                    onChange={(e) => setField("business_email", e.target.value)}
                    placeholder="business@mystore.com"
                    className={inputClass}
                  />
                </Field>
                <Field label="BUSINESS PHONE">
                  <input
                    type="tel"
                    value={form.business_phone}
                    onChange={(e) => setField("business_phone", e.target.value)}
                    placeholder="01XXXXXXXXX"
                    className={inputClass}
                  />
                </Field>
              </div>
              <p className="text-[10px] font-medium text-[var(--tavus-hardware-gray-8)]">
                These details are used by your AI agent when customers ask about the business.
              </p>
            </SettingsSection>

            {/* Delivery pricing */}
            <SettingsSection
              id="delivery"
              label="DELIVERY PRICING"
              icon={Truck}
              color="var(--tavus-neon-field-2)"
              open={open === "delivery"}
              onToggle={() => setOpen(open === "delivery" ? "" : "delivery")}
            >
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <Field label="INSIDE CAIRO (EGP)">
                  <input
                    type="number"
                    value={form.delivery_inside_cairo}
                    onChange={(e) => setField("delivery_inside_cairo", e.target.value)}
                    placeholder="35"
                    className={inputClass}
                  />
                </Field>
                <Field label="OUTSIDE CAIRO (EGP)">
                  <input
                    type="number"
                    value={form.delivery_outside_cairo}
                    onChange={(e) => setField("delivery_outside_cairo", e.target.value)}
                    placeholder="60"
                    className={inputClass}
                  />
                </Field>
                <Field label="FREE DELIVERY ABOVE (EGP)">
                  <input
                    type="number"
                    value={form.free_delivery_above}
                    onChange={(e) => setField("free_delivery_above", e.target.value)}
                    placeholder="300"
                    className={inputClass}
                  />
                </Field>
              </div>
              <p className="text-[10px] font-medium text-[var(--tavus-hardware-gray-8)]">
                Shipping charges are auto-calculated from these values when your agent creates orders. Leave free-delivery empty to disable.
              </p>
              {form.free_delivery_above.trim() !== "" ? (
                <div className="relative bg-[var(--tavus-plastic-1)] border-[2px] border-[var(--tavus-terminal-black)] p-3 overflow-hidden">
                  <div className="absolute inset-0 bg-halftone-light opacity-[0.35] pointer-events-none" />
                  <div className="relative text-[11px] font-bold text-[var(--tavus-terminal-black)]">
                    Orders above {toNumber(form.free_delivery_above).toLocaleString()} EGP ship free —{" "}
                    {loaded && (loaded.delivery_inside_cairo !== form.delivery_inside_cairo || loaded.delivery_outside_cairo !== form.delivery_outside_cairo)
                      ? "will apply once saved."
                      : "currently active."}
                  </div>
                </div>
              ) : null}
            </SettingsSection>

            {/* Integrations — honest not-yet-available state */}
            <SettingsSection
              id="integrations"
              label="CHANNELS & INTEGRATIONS"
              icon={Facebook}
              color="var(--tavus-frost-4)"
              open={open === "integrations"}
              onToggle={() => setOpen(open === "integrations" ? "" : "integrations")}
            >
              <div className="relative bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[4px_4px_0_0_var(--tavus-terminal-black)] p-8 text-center overflow-hidden">
                <div className="absolute inset-0 bg-halftone-light opacity-[0.35] pointer-events-none" />
                <div className="relative">
                  <div className="win-title-bar mb-6">
                    <span className="w-2.5 h-2.5 bg-[var(--tavus-frost-4)] border border-[var(--tavus-terminal-black)]" />
                    <span>NOT CONNECTED YET</span>
                    <span className="ml-auto flex gap-1">
                      <span className="w-2.5 h-2.5 border border-[var(--tavus-terminal-black)]" />
                    </span>
                  </div>
                  <h3 className="font-serif text-2xl mb-3 text-[var(--tavus-terminal-black)]">
                    Channels <span className="serif-italic">coming soon</span>
                  </h3>
                  <p className="text-xs font-medium text-[var(--tavus-hardware-gray-8)] max-w-md mx-auto mb-5">
                    Facebook, Instagram and WhatsApp connections, payment methods and the order API are not configurable from here yet.
                    They become available once the integration ships.
                  </p>
                  <div className="flex items-center justify-center gap-3 flex-wrap">
                    <span className="inline-flex items-center gap-1.5 px-3 py-1.5 border-2 border-[var(--tavus-terminal-black)] bg-[var(--tavus-plastic-1)] text-[10px] font-bold tracking-[0.12em] uppercase text-[var(--tavus-hardware-gray-8)]">
                      <Facebook className="w-3.5 h-3.5" strokeWidth={2.25} /> Facebook
                    </span>
                    <span className="inline-flex items-center gap-1.5 px-3 py-1.5 border-2 border-[var(--tavus-terminal-black)] bg-[var(--tavus-plastic-1)] text-[10px] font-bold tracking-[0.12em] uppercase text-[var(--tavus-hardware-gray-8)]">
                      <Instagram className="w-3.5 h-3.5" strokeWidth={2.25} /> Instagram
                    </span>
                    <span className="inline-flex items-center gap-1.5 px-3 py-1.5 border-2 border-[var(--tavus-terminal-black)] bg-[var(--tavus-plastic-1)] text-[10px] font-bold tracking-[0.12em] uppercase text-[var(--tavus-hardware-gray-8)]">
                      <WhatsApp className="w-3.5 h-3.5" strokeWidth={2.25} /> WhatsApp
                    </span>
                    <span className="inline-flex items-center gap-1.5 px-3 py-1.5 border-2 border-[var(--tavus-terminal-black)] bg-[var(--tavus-plastic-1)] text-[10px] font-bold tracking-[0.12em] uppercase text-[var(--tavus-hardware-gray-8)]">
                      <CreditCard className="w-3.5 h-3.5" strokeWidth={2.25} /> Payments
                    </span>
                    <span className="inline-flex items-center gap-1.5 px-3 py-1.5 border-2 border-[var(--tavus-terminal-black)] bg-[var(--tavus-plastic-1)] text-[10px] font-bold tracking-[0.12em] uppercase text-[var(--tavus-hardware-gray-8)]">
                      <Code className="w-3.5 h-3.5" strokeWidth={2.25} /> Order API
                    </span>
                  </div>
                </div>
              </div>
            </SettingsSection>
          </div>
        </>
      ) : null}
    </div>
  );
}

function SettingsSection({
  id,
  label,
  icon: Icon,
  color,
  open,
  onToggle,
  children,
}: {
  id: string;
  label: string;
  icon: React.ElementType;
  color: string;
  open: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="relative bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[4px_4px_0_0_var(--tavus-terminal-black)] overflow-hidden">
      <div className="absolute inset-0 bg-halftone-light opacity-[0.35] pointer-events-none" />
      <button
        onClick={onToggle}
        aria-expanded={open}
        aria-controls={`section-${id}`}
        className="relative w-full flex items-center gap-3 p-4 text-left hover:bg-[var(--tavus-plastic-1)] transition-colors"
      >
        <span className="inline-flex items-center justify-center w-8 h-8 border-2 border-[var(--tavus-terminal-black)]" style={{ background: color }}>
          <Icon className="w-4 h-4 text-[var(--tavus-terminal-black)]" strokeWidth={2} />
        </span>
        <span className="text-[12px] font-extrabold tracking-[0.14em] uppercase text-[var(--tavus-terminal-black)] flex-1 text-left">{label}</span>
        <ChevronDown className={`w-4 h-4 text-[var(--tavus-terminal-black)] transition-transform ${open ? "rotate-180" : ""}`} strokeWidth={2.5} />
      </button>
      {open ? (
        <div id={`section-${id}`} className="relative p-5 pt-0 space-y-3">
          {children}
        </div>
      ) : null}
    </div>
  );
}
