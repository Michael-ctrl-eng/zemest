"use client";

import { use, useCallback, useEffect, useState } from "react";
import {
  Facebook,
  Instagram,
  MessageCircle as WhatsAppIcon,
  Loader2,
  Plug,
  PlugZap,
  Unplug,
  Send,
  Copy,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  RefreshCw,
  Link as LinkIcon,
} from "lucide-react";
import {
  channelsApi,
  formatDateTime,
  type ChannelsStatus,
  type ChannelStatus,
} from "@/lib/zemest-api";
import { toast } from "@/components/site/toast";
import {
  DashHeader,
  WinCard,
  TavusButton,
  Field,
  inputClass,
  LoadingState,
  ErrorState,
} from "@/components/site/dash";

type Platform = "messenger" | "instagram" | "whatsapp";

const PLATFORM_META: Record<
  Platform,
  { label: string; icon: typeof Facebook; dot: string; help: string[] }
> = {
  messenger: {
    label: "Messenger",
    icon: Facebook,
    dot: "var(--tavus-bubbletech-1)",
    help: [
      "Facebook → Page settings → New app (or use Meta for Developers) → generate a Page access token with pages_messaging + pages_manage_metadata permissions.",
      "The token is verified live against the Meta Graph API the moment you press Connect — an invalid token shows Meta's own error.",
      "Once connected, every DM your Page receives flows into your Conversations inbox and the agent answers automatically.",
    ],
  },
  instagram: {
    label: "Instagram",
    icon: Instagram,
    dot: "var(--tavus-neon-field-2)",
    help: [
      "Convert your Instagram account to a Professional account (Business), then link it to a Facebook Page.",
      "In Meta for Developers → your app → Instagram → generate a token with instagram_basic + instagram_manage_messages, and paste the IG user ID here.",
      "Story replies, DMs and post comments arrive as conversations — the agent answers in the same dialect the customer used.",
    ],
  },
  whatsapp: {
    label: "WhatsApp",
    icon: WhatsAppIcon,
    dot: "var(--tavus-atomic-glow-1)",
    help: [
      "Create a WhatsApp Business Account in Meta Business Manager, add a phone number, and get its Phone number ID.",
      "Generate a System User access token with whatsapp_business_messaging permission in Meta Business Settings.",
      "The number is verified live — Meta returns the display number and quality rating before anything is saved.",
    ],
  },
};

export default function ChannelsPage({ params }: { params: Promise<{ tenantId: string }> }) {
  const { tenantId } = use(params);
  const [status, setStatus] = useState<ChannelsStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setStatus(await channelsApi.status(tenantId));
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load channel status");
    } finally {
      setLoading(false);
    }
  }, [tenantId]);

  useEffect(() => {
    load();
  }, [load]);

  const origin = typeof window !== "undefined" ? window.location.origin : "https://your-domain.com";

  return (
    <div className="space-y-6">
      <DashHeader
        eyebrow="Channels"
        title="Connect your"
        tail="accounts"
        action={
          <TavusButton variant="secondary" onClick={load} disabled={loading}>
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} strokeWidth={2.25} />
            Refresh status
          </TavusButton>
        }
      />

      <p className="text-sm text-[var(--tavus-hardware-gray-8)] leading-relaxed max-w-3xl">
        Connect your Facebook Page, Instagram professional account, and WhatsApp Business number.
        Credentials are validated live against the Meta Graph API before anything is saved, messages
        arrive through signed webhooks, and the agent answers automatically — 24/7.
      </p>

      {loading && !status ? (
        <WinCard title="Loading channels">
          <div className="p-6">
            <LoadingState label="Checking live connection status" />
          </div>
        </WinCard>
      ) : error && !status ? (
        <ErrorState message={error} onRetry={load} />
      ) : status ? (
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-5 items-start">
          {(["messenger", "instagram", "whatsapp"] as Platform[]).map((p) => (
            <ChannelCard
              key={p}
              platform={p}
              tenantId={tenantId}
              st={status.platforms[p]}
              onConnected={load}
            />
          ))}
        </div>
      ) : null}

      {/* Webhook setup */}
      {status && (
        <WinCard
          title="Webhook configuration"
          dot="var(--tavus-hardware-gray-8)"
          action={
            <span className="text-[9px] font-extrabold tracking-[0.14em] uppercase text-[var(--tavus-hardware-gray-8)]">
              Meta App dashboard → webhooks
            </span>
          }
        >
          <div className="p-5 space-y-4">
            <p className="text-sm text-[var(--tavus-hardware-gray-8)] leading-relaxed">
              Paste these callback URLs into your Meta App dashboard → Webhooks (one per product).
              The platform answers Meta&apos;s verification challenge automatically and validates
              the <code className="text-[11px] font-mono bg-[var(--tavus-plastic-1)] px-1 py-0.5 border border-[var(--tavus-terminal-black)]">X-Hub-Signature-256</code> HMAC on
              every event.
            </p>
            <div className="space-y-2.5">
              {Object.entries(status.webhook_urls).map(([platform, path]) => (
                <div
                  key={platform}
                  className="flex items-center gap-3 bg-[var(--tavus-plastic-1)] border-2 border-[var(--tavus-terminal-black)] px-3 py-2"
                >
                  <LinkIcon className="w-3.5 h-3.5 shrink-0 text-[var(--tavus-terminal-black)]" strokeWidth={2.25} />
                  <div className="min-w-0 flex-1">
                    <div className="text-[9px] font-extrabold tracking-[0.14em] uppercase text-[var(--tavus-hardware-gray-8)]">
                      {platform} callback URL
                    </div>
                    <div className="text-[11px] font-mono font-semibold text-[var(--tavus-terminal-black)] truncate">
                      {origin}
                      {path}
                    </div>
                  </div>
                  <CopyButton text={`${origin}${path}`} />
                </div>
              ))}
            </div>
            <div className="text-[11px] text-[var(--tavus-hardware-gray-8)] leading-relaxed border-t-2 border-dashed border-[var(--tavus-terminal-black)]/15 pt-3">
              Verify token: set <code className="font-mono">FB_VERIFY_TOKEN</code> on the server and use
              the same value in the Meta dashboard. Event signatures use{" "}
              <code className="font-mono">FB_APP_SECRET</code> — unsigned traffic is rejected.
            </div>
          </div>
        </WinCard>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Per-platform card                                                   */
/* ------------------------------------------------------------------ */

function ChannelCard({
  platform,
  tenantId,
  st,
  onConnected,
}: {
  platform: Platform;
  tenantId: string;
  st: ChannelStatus;
  onConnected: () => void;
}) {
  const meta = PLATFORM_META[platform];
  const Icon = meta.icon;
  const [token, setToken] = useState("");
  const [idField, setIdField] = useState("");
  const [busy, setBusy] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; msg: string } | null>(null);

  const connected = st.connected;

  async function connect() {
    setBusy(true);
    try {
      if (platform === "messenger") {
        const r = await channelsApi.connectMessenger(tenantId, token.trim(), idField.trim() || undefined);
        toast.success(`Connected ${r.page_name ?? meta.label}${r.webhook_subscribed ? " — webhook subscribed" : ""}`);
      } else if (platform === "instagram") {
        const r = await channelsApi.connectInstagram(tenantId, idField.trim(), token.trim());
        toast.success(`Connected Instagram ${r.username ? `@${r.username}` : ""}`);
      } else {
        const r = await channelsApi.connectWhatsapp(tenantId, idField.trim(), token.trim());
        toast.success(`Connected WhatsApp ${r.display_phone_number ?? ""} (${r.verified_name ?? ""})`);
      }
      setToken("");
      setIdField("");
      onConnected();
    } catch (err: unknown) {
      // The backend surfaces Meta's REAL Graph API error — show it verbatim
      toast.error(err instanceof Error ? err.message : "Connection failed");
    } finally {
      setBusy(false);
    }
  }

  async function disconnect() {
    setBusy(true);
    try {
      await channelsApi.disconnect(tenantId, platform);
      toast.success(`${meta.label} disconnected`);
      setTestResult(null);
      onConnected();
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Disconnect failed");
    } finally {
      setBusy(false);
    }
  }

  async function sendTest() {
    setBusy(true);
    setTestResult(null);
    try {
      await channelsApi.test(tenantId, platform);
      setTestResult({ ok: true, msg: "Test message sent through the platform API — check the chat." });
    } catch (err: unknown) {
      setTestResult({ ok: false, msg: err instanceof Error ? err.message : "Test failed" });
    } finally {
      setBusy(false);
    }
  }

  const idLabel =
    platform === "messenger" ? "Page ID (optional — auto-resolved)" : platform === "instagram" ? "Instagram user ID" : "Phone number ID";

  return (
    <WinCard
      title={meta.label}
      dot={connected ? "var(--tavus-neon-field-2)" : "var(--tavus-coral-1)"}
      action={
        <span className="flex items-center gap-1.5 text-[9px] font-extrabold tracking-[0.14em] uppercase">
          {connected ? (
            <>
              <CheckCircle2 className="w-3 h-3 text-[var(--tavus-terminal-black)]" strokeWidth={2.5} />
              <span className="text-[var(--tavus-terminal-black)]">Connected</span>
            </>
          ) : (
            <>
              <XCircle className="w-3 h-3 text-[var(--tavus-coral-1)]" strokeWidth={2.5} />
              <span className="text-[var(--tavus-coral-1)]">Not connected</span>
            </>
          )}
        </span>
      }
      className="w-full"
    >
      <div className="p-5 space-y-4">
        {/* Account info when connected */}
        {connected ? (
          <div className="flex items-center gap-3 border-2 border-[var(--tavus-terminal-black)] bg-[var(--tavus-plastic-1)] p-3">
            <div className="w-10 h-10 border-2 border-[var(--tavus-terminal-black)] bg-white flex items-center justify-center shrink-0 overflow-hidden">
              {st.avatar ? (
                <img src={st.avatar} alt="" className="w-full h-full object-cover" />
              ) : (
                <Icon className="w-5 h-5 text-[var(--tavus-terminal-black)]" strokeWidth={2.25} />
              )}
            </div>
            <div className="min-w-0 flex-1">
              <div className="text-sm font-bold text-[var(--tavus-terminal-black)] truncate">
                {st.account_name ?? meta.label}
              </div>
              <div className="text-[10px] font-semibold text-[var(--tavus-hardware-gray-8)] truncate">
                {platform === "whatsapp"
                  ? `${st.display_phone_number ?? ""} · ${st.verified_name ?? ""}`
                  : st.followers != null
                    ? `${st.followers.toLocaleString()} followers`
                    : (st.category ?? "Account")}
              </div>
              {st.connected_at && (
                <div className="text-[9px] font-medium text-[var(--tavus-hardware-gray-8)]">
                  Since {formatDateTime(st.connected_at)}
                </div>
              )}
            </div>
            {st.quality_rating && (
              <span className="text-[9px] font-extrabold tracking-wider uppercase border border-[var(--tavus-terminal-black)] px-1.5 py-0.5 bg-white shrink-0">
                {st.quality_rating}
              </span>
            )}
          </div>
        ) : null}

        {/* Live error (revoked token etc.) */}
        {st.error && (
          <div className="flex items-start gap-2 border-2 border-[var(--tavus-coral-1)] bg-[var(--tavus-coral-1)]/5 p-3">
            <AlertTriangle className="w-4 h-4 text-[var(--tavus-coral-1)] shrink-0 mt-0.5" strokeWidth={2.25} />
            <div className="text-[11px] font-semibold text-[var(--tavus-terminal-black)] leading-relaxed">
              Connection check failed: {st.error}
            </div>
          </div>
        )}

        {/* Connect form / connected actions */}
        {connected ? (
          <div className="space-y-3">
            <div className="flex gap-2">
              <TavusButton variant="secondary" onClick={sendTest} disabled={busy} className="flex-1">
                {busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" strokeWidth={2.25} /> : <Send className="w-3.5 h-3.5" strokeWidth={2.25} />}
                Send test message
              </TavusButton>
              <TavusButton variant="danger" onClick={disconnect} disabled={busy}>
                <Unplug className="w-3.5 h-3.5" strokeWidth={2.25} />
                Disconnect
              </TavusButton>
            </div>
            {testResult && (
              <div
                className={`text-[11px] font-semibold leading-relaxed border-2 p-2.5 ${
                  testResult.ok
                    ? "border-[var(--tavus-terminal-black)] bg-[var(--tavus-plastic-1)]"
                    : "border-[var(--tavus-coral-1)] bg-[var(--tavus-coral-1)]/5"
                } text-[var(--tavus-terminal-black)]`}
              >
                {testResult.msg}
              </div>
            )}
          </div>
        ) : (
          <div className="space-y-3">
            <Field label={idLabel}>
              <input
                className={inputClass}
                value={idField}
                onChange={(e) => setIdField(e.target.value)}
                placeholder={platform === "messenger" ? "e.g. 10238471…" : platform === "instagram" ? "e.g. 17841400…" : "e.g. 10551237…"}
                autoComplete="off"
              />
            </Field>
            <Field label="Access token">
              <input
                className={inputClass}
                type="password"
                value={token}
                onChange={(e) => setToken(e.target.value)}
                placeholder="Paste the token from Meta Business / Graph API Explorer"
                autoComplete="off"
              />
            </Field>
            <TavusButton variant="primary" onClick={connect} disabled={busy || !token.trim() || (platform !== "messenger" && !idField.trim())} className="w-full">
              {busy ? <Loader2 className="w-4 h-4 animate-spin" strokeWidth={2.25} /> : <PlugZap className="w-4 h-4" strokeWidth={2.25} />}
              Connect {meta.label}
            </TavusButton>
          </div>
        )}

        {/* How-to */}
        <details className="group border-t-2 border-dashed border-[var(--tavus-terminal-black)]/15 pt-3">
          <summary className="flex items-center gap-1.5 text-[10px] font-extrabold tracking-[0.14em] uppercase text-[var(--tavus-hardware-gray-8)] cursor-pointer select-none">
            <Plug className="w-3 h-3" strokeWidth={2.25} />
            How to get these credentials
          </summary>
          <ul className="mt-2.5 space-y-2">
            {meta.help.map((h, i) => (
              <li key={i} className="flex gap-2 text-[11px] leading-relaxed text-[var(--tavus-hardware-gray-8)]">
                <span className="font-mono font-bold text-[var(--tavus-terminal-black)] shrink-0">{i + 1}.</span>
                <span>{h}</span>
              </li>
            ))}
          </ul>
        </details>
      </div>
    </WinCard>
  );
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setCopied(true);
          setTimeout(() => setCopied(false), 1600);
        } catch {
          toast.error("Could not copy — select the text manually");
        }
      }}
      className="w-8 h-8 flex items-center justify-center border-2 border-[var(--tavus-terminal-black)] bg-white shadow-[2px_2px_0_0_var(--tavus-terminal-black)] hover:shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:-translate-y-0.5 active:translate-y-0.5 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] transition-all shrink-0"
      aria-label="Copy URL"
      type="button"
    >
      {copied ? (
        <CheckCircle2 className="w-3.5 h-3.5 text-[var(--tavus-terminal-black)]" strokeWidth={2.5} />
      ) : (
        <Copy className="w-3.5 h-3.5 text-[var(--tavus-terminal-black)]" strokeWidth={2.25} />
      )}
    </button>
  );
}
