"use client";

import { use, useCallback, useEffect, useMemo, useState } from "react";
import {
  Calendar as CalIcon,
  Clock,
  Facebook,
  Instagram,
  Loader2,
  Plus,
  Trash2,
  XCircle,
  RefreshCw,
  Copy,
  CheckCircle2,
  AlertTriangle,
  CalendarPlus,
  RotateCcw,
  ExternalLink,
} from "lucide-react";
import {
  schedulerApi,
  calendarApi,
  formatDateTime,
  toNumber,
  type ScheduledPostItem,
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

const PLATFORMS = [
  { id: "facebook", label: "Facebook", icon: Facebook },
  { id: "instagram", label: "Instagram", icon: Instagram },
] as const;

const STATUS_STYLES: Record<string, string> = {
  scheduled: "bg-[var(--tavus-bubbletech-4)] border-[var(--tavus-terminal-black)]",
  published: "bg-[var(--tavus-neon-field-2)] text-white border-[var(--tavus-terminal-black)]",
  publishing: "bg-[var(--tavus-atomic-glow-1)] border-[var(--tavus-terminal-black)]",
  failed: "bg-[var(--tavus-coral-1)] text-white border-[var(--tavus-terminal-black)]",
  cancelled: "bg-[var(--tavus-plastic-1)] border-[var(--tavus-terminal-black)]/40",
};

export default function SchedulerPage({ params }: { params: Promise<{ tenantId: string }> }) {
  const { tenantId } = use(params);
  const [posts, setPosts] = useState<ScheduledPostItem[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [calendarToken, setCalendarToken] = useState<string | null>(null);

  // composer state
  const [platform, setPlatform] = useState<"facebook" | "instagram">("facebook");
  const [caption, setCaption] = useState("");
  const [mediaUrl, setMediaUrl] = useState("");
  const [when, setWhen] = useState("");
  const [creating, setCreating] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [r, cal] = await Promise.all([
        schedulerApi.list(tenantId),
        calendarApi.url(tenantId).catch(() => null),
      ]);
      setPosts(r.posts);
      setCalendarToken(cal?.calendar_token ?? null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load scheduled posts");
    } finally {
      setLoading(false);
    }
  }, [tenantId]);

  useEffect(() => {
    load();
  }, [load]);

  // default composer time = now + 1h in local ISO for datetime-local input
  useEffect(() => {
    if (!when) {
      const d = new Date(Date.now() + 60 * 60 * 1000);
      d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
      setWhen(d.toISOString().slice(0, 16));
    }
  }, [when]);

  const stats = useMemo(() => {
    const list = posts ?? [];
    return {
      total: list.length,
      scheduled: list.filter((p) => p.status === "scheduled").length,
      published: list.filter((p) => p.status === "published").length,
      failed: list.filter((p) => p.status === "failed").length,
    };
  }, [posts]);

  async function createPost() {
    if (!caption.trim() || !when) return;
    setCreating(true);
    try {
      const scheduledAt = new Date(when).toISOString(); // local → UTC
      await schedulerApi.create(tenantId, {
        platform,
        caption: caption.trim(),
        media_type: mediaUrl.trim() ? "photo" : "text",
        media_urls: mediaUrl.trim() ? [mediaUrl.trim()] : [],
        scheduled_at: scheduledAt,
      });
      toast.success("Post scheduled — the publisher picks it up at the exact time");
      setCaption("");
      setMediaUrl("");
      await load();
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Could not schedule the post");
    } finally {
      setCreating(false);
    }
  }

  async function cancelPost(p: ScheduledPostItem) {
    try {
      await schedulerApi.cancel(tenantId, p.id);
      toast.success("Post cancelled");
      await load();
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Cancel failed");
    }
  }

  async function removePost(p: ScheduledPostItem) {
    try {
      await schedulerApi.remove(tenantId, p.id);
      toast.success("Post deleted");
      await load();
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Delete failed");
    }
  }

  async function rotateToken() {
    try {
      const r = await calendarApi.rotate(tenantId);
      setCalendarToken(r.calendar_token);
      toast.success("Calendar link rotated — re-subscribe in your calendar app");
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Could not rotate the link");
    }
  }

  const origin = typeof window !== "undefined" ? window.location.origin : "";
  const icsPath = calendarToken ? `/api/calendar/${calendarToken}` : "";

  return (
    <div className="space-y-6">
      <DashHeader
        eyebrow="Scheduler"
        title="Post"
        tail="scheduler"
        action={
          <TavusButton variant="secondary" onClick={load} disabled={loading}>
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} strokeWidth={2.25} />
            Refresh
          </TavusButton>
        }
      />

      <p className="text-sm text-[var(--tavus-hardware-gray-8)] leading-relaxed max-w-3xl">
        Write posts now, publish later. A background worker inside the platform publishes each post
        to your connected Facebook Page or Instagram account at the exact scheduled time — and every
        scheduled post lands in your calendar automatically.
      </p>

      {/* Composer + calendar */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5 items-start">
        <WinCard title="Compose a scheduled post" dot="var(--tavus-bubbletech-1)">
          <div className="p-5 space-y-4">
            <div className="flex gap-2">
              {PLATFORMS.map((p) => (
                <button
                  key={p.id}
                  onClick={() => setPlatform(p.id)}
                  className={`flex-1 h-11 flex items-center justify-center gap-2 border-[2.5px] text-[10px] font-bold tracking-[0.12em] uppercase transition-all ${
                    platform === p.id
                      ? "border-[var(--tavus-terminal-black)] bg-[var(--tavus-terminal-black)] text-white shadow-[3px_3px_0_0_var(--tavus-terminal-black)]"
                      : "border-[var(--tavus-terminal-black)] bg-white text-[var(--tavus-terminal-black)] hover:bg-[var(--tavus-plastic-1)]"
                  }`}
                  type="button"
                >
                  <p.icon className="w-4 h-4" strokeWidth={2.25} />
                  {p.label}
                </button>
              ))}
            </div>

            <Field label="Caption">
              <textarea
                className={`${inputClass} h-auto min-h-[96px] py-2.5 resize-y`}
                value={caption}
                onChange={(e) => setCaption(e.target.value)}
                placeholder="Summer drop — Air Max 90 restocked. DM us your size."
                maxLength={5000}
              />
            </Field>

            <Field label="Image URL (optional — Instagram requires media)">
              <input
                className={inputClass}
                value={mediaUrl}
                onChange={(e) => setMediaUrl(e.target.value)}
                placeholder="https://…/photo.jpg"
                autoComplete="off"
              />
            </Field>

            <Field label="Publish at (your local time)">
              <input
                className={inputClass}
                type="datetime-local"
                value={when}
                onChange={(e) => setWhen(e.target.value)}
              />
            </Field>

            <TavusButton
              variant="primary"
              onClick={createPost}
              disabled={creating || !caption.trim() || !when}
              className="w-full"
            >
              {creating ? (
                <Loader2 className="w-4 h-4 animate-spin" strokeWidth={2.25} />
              ) : (
                <Plus className="w-4 h-4" strokeWidth={2.25} />
              )}
              Schedule post
            </TavusButton>
          </div>
        </WinCard>

        {/* Calendar subscription */}
        <WinCard title="Your schedule, in your calendar" dot="var(--tavus-atomic-glow-1)">
          <div className="p-5 space-y-4">
            <p className="text-sm text-[var(--tavus-hardware-gray-8)] leading-relaxed">
              Subscribe once and every scheduled or published post appears in your calendar
              automatically — Google Calendar, Apple Calendar (iOS + Mac), or Outlook.
            </p>

            {calendarToken ? (
              <>
                <div className="flex items-center gap-3 bg-[var(--tavus-plastic-1)] border-2 border-[var(--tavus-terminal-black)] px-3 py-2">
                  <CalIcon className="w-3.5 h-3.5 shrink-0" strokeWidth={2.25} />
                  <div className="min-w-0 flex-1">
                    <div className="text-[9px] font-extrabold tracking-[0.14em] uppercase text-[var(--tavus-hardware-gray-8)]">
                      Subscription link (ICS)
                    </div>
                    <div className="text-[11px] font-mono font-semibold truncate">
                      {origin}
                      {icsPath}
                    </div>
                  </div>
                  <button
                    onClick={() => {
                      navigator.clipboard
                        .writeText(`${origin}${icsPath}`)
                        .then(() => toast.success("ICS link copied"))
                        .catch(() => toast.error("Copy failed"));
                    }}
                    className="w-8 h-8 flex items-center justify-center border-2 border-[var(--tavus-terminal-black)] bg-white shadow-[2px_2px_0_0_var(--tavus-terminal-black)] hover:shadow-[3px_3px_0_0_var(--tavus-terminal-black)] transition-all shrink-0"
                    aria-label="Copy ICS link"
                    type="button"
                  >
                    <Copy className="w-3.5 h-3.5" strokeWidth={2.25} />
                  </button>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                  <a
                    href={`https://calendar.google.com/calendar/render?cid=${encodeURIComponent(origin + icsPath)}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="h-11 flex items-center justify-center gap-2 border-[2.5px] border-[var(--tavus-terminal-black)] bg-white text-[10px] font-bold tracking-[0.12em] uppercase shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:shadow-[4px_4px_0_0_var(--tavus-terminal-black)] hover:-translate-y-0.5 active:translate-y-0.5 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] transition-all"
                  >
                    <CalendarPlus className="w-4 h-4" strokeWidth={2.25} />
                    Add to Google
                    <ExternalLink className="w-3 h-3" strokeWidth={2.25} />
                  </a>
                  <a
                    href={`webcal://${typeof window !== "undefined" ? window.location.host : ""}${icsPath}`}
                    className="h-11 flex items-center justify-center gap-2 border-[2.5px] border-[var(--tavus-terminal-black)] bg-white text-[10px] font-bold tracking-[0.12em] uppercase shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:shadow-[4px_4px_0_0_var(--tavus-terminal-black)] hover:-translate-y-0.5 active:translate-y-0.5 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] transition-all"
                  >
                    <CalIcon className="w-4 h-4" strokeWidth={2.25} />
                    Add to Apple Calendar
                  </a>
                </div>

                <div className="flex items-center justify-between gap-3 border-t-2 border-dashed border-[var(--tavus-terminal-black)]/15 pt-3">
                  <div className="text-[11px] text-[var(--tavus-hardware-gray-8)] leading-relaxed">
                    Sharing stopped? Rotate the link — old subscribers lose access.
                  </div>
                  <TavusButton variant="secondary" onClick={rotateToken}>
                    <RotateCcw className="w-3.5 h-3.5" strokeWidth={2.25} />
                    Rotate
                  </TavusButton>
                </div>
              </>
            ) : (
              <div className="text-[11px] font-semibold text-[var(--tavus-hardware-gray-8)] border-2 border-dashed border-[var(--tavus-terminal-black)]/20 p-3">
                Calendar link unavailable — retry loading the page.
              </div>
            )}
          </div>
        </WinCard>
      </div>

      {/* Posts list */}
      <WinCard
        title="Scheduled posts"
        dot="var(--tavus-neon-field-2)"
        action={
          <span className="text-[9px] font-extrabold tracking-[0.14em] uppercase text-[var(--tavus-hardware-gray-8)]">
            {stats.scheduled} queued · {stats.published} published · {stats.failed} failed
          </span>
        }
      >
        <div className="p-5">
          {loading && !posts ? (
            <LoadingState label="Loading your schedule" />
          ) : error && !posts ? (
            <ErrorState message={error} onRetry={load} />
          ) : !posts || posts.length === 0 ? (
            <div className="flex flex-col items-center gap-3 py-10 text-center">
              <CalIcon className="w-8 h-8 text-[var(--tavus-hardware-gray-8)]" strokeWidth={2} />
              <div className="text-sm font-bold text-[var(--tavus-terminal-black)]">Nothing scheduled yet</div>
              <div className="text-[11px] text-[var(--tavus-hardware-gray-8)] max-w-sm">
                Compose your first post above — the worker publishes it at the exact minute, and it
                shows up in your subscribed calendar.
              </div>
            </div>
          ) : (
            <div className="space-y-3">
              {posts.map((p) => {
                const PI = p.platform === "instagram" ? Instagram : Facebook;
                return (
                  <div
                    key={p.id}
                    className="flex items-start gap-3 border-2 border-[var(--tavus-terminal-black)] bg-white p-3.5"
                  >
                    <div className="w-9 h-9 border-2 border-[var(--tavus-terminal-black)] bg-[var(--tavus-plastic-1)] flex items-center justify-center shrink-0">
                      <PI className="w-4.5 h-4.5 text-[var(--tavus-terminal-black)]" strokeWidth={2.25} />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2 mb-1">
                        <span
                          className={`text-[9px] font-extrabold tracking-[0.12em] uppercase border-2 px-1.5 py-0.5 ${STATUS_STYLES[p.status] ?? STATUS_STYLES.cancelled}`}
                        >
                          {p.status}
                        </span>
                        <span className="flex items-center gap-1 text-[11px] font-semibold text-[var(--tavus-hardware-gray-8)]">
                          <Clock className="w-3 h-3" strokeWidth={2.25} />
                          {formatDateTime(p.scheduled_at)}
                        </span>
                        {p.ai_generated && (
                          <span className="text-[9px] font-bold tracking-wider uppercase border border-[var(--tavus-terminal-black)]/40 px-1.5 py-0.5">
                            AI
                          </span>
                        )}
                      </div>
                      <div className="text-sm font-semibold text-[var(--tavus-terminal-black)] leading-relaxed line-clamp-2">
                        {p.caption}
                      </div>
                      {p.error_message && (
                        <div className="mt-1.5 flex items-start gap-1.5 text-[11px] font-semibold text-[var(--tavus-coral-1)]">
                          <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-px" strokeWidth={2.25} />
                          <span className="leading-relaxed">{p.error_message}</span>
                        </div>
                      )}
                      {p.status === "published" && p.platform_post_id && (
                        <div className="mt-1 flex items-center gap-1.5 text-[11px] font-semibold text-[var(--tavus-terminal-black)]">
                          <CheckCircle2 className="w-3.5 h-3.5" strokeWidth={2.25} />
                          Published · post {String(p.platform_post_id).slice(0, 18)}
                          {formatDateTime(p.published_at ?? undefined) !== "—" && ` · ${formatDateTime(p.published_at ?? undefined)}`}
                        </div>
                      )}
                    </div>
                    <div className="flex gap-1.5 shrink-0">
                      {p.status === "scheduled" && (
                        <button
                          onClick={() => cancelPost(p)}
                          className="w-8 h-8 flex items-center justify-center border-2 border-[var(--tavus-terminal-black)] bg-white shadow-[2px_2px_0_0_var(--tavus-terminal-black)] hover:bg-[var(--tavus-bubbletech-1)] transition-all"
                          title="Cancel post"
                          type="button"
                        >
                          <XCircle className="w-3.5 h-3.5 text-[var(--tavus-terminal-black)]" strokeWidth={2.25} />
                        </button>
                      )}
                      {p.status !== "published" && (
                        <button
                          onClick={() => removePost(p)}
                          className="w-8 h-8 flex items-center justify-center border-2 border-[var(--tavus-terminal-black)] bg-white shadow-[2px_2px_0_0_var(--tavus-terminal-black)] hover:bg-[var(--tavus-coral-1)] hover:text-white transition-all"
                          title="Delete post"
                          type="button"
                        >
                          <Trash2 className="w-3.5 h-3.5 text-[var(--tavus-terminal-black)]" strokeWidth={2.25} />
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </WinCard>
    </div>
  );
}
