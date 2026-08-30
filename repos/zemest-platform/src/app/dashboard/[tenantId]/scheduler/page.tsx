"use client";

import { useState } from "react";
import { Calendar as CalIcon, Pencil, List, BarChart3, Facebook, Instagram, Sparkles, Clock, ChevronLeft, ChevronRight, Check, X } from "lucide-react";

interface Post {
  id: string;
  caption: string;
  platforms: string[];
  media_type: "image" | "video" | "carousel";
  scheduled_at: string;
  status: "scheduled" | "published" | "failed" | "draft";
}

const mockPosts: Post[] = [
  { id: "p1", caption: "New drop alert! Air Max 90 collection now available.", platforms: ["facebook", "instagram"], media_type: "image", scheduled_at: "Aug 28, 12:00 PM", status: "scheduled" },
  { id: "p2", caption: "Flash sale: 30% off all sneakers this weekend only!", platforms: ["instagram"], media_type: "carousel", scheduled_at: "Aug 29, 06:00 PM", status: "scheduled" },
  { id: "p3", caption: "Behind the scenes of our latest photoshoot.", platforms: ["facebook", "instagram"], media_type: "video", scheduled_at: "Aug 27, 03:00 PM", status: "published" },
  { id: "p4", caption: "Customer love - review spotlight!", platforms: ["facebook"], media_type: "image", scheduled_at: "Aug 26, 10:00 AM", status: "published" },
  { id: "p5", caption: "Brand collab teaser coming soon.", platforms: ["instagram"], media_type: "video", scheduled_at: "Aug 25, 08:00 PM", status: "failed" },
];

const statusColors: Record<string, string> = {
  scheduled: "var(--tavus-atomic-glow-5)",
  published: "var(--tavus-neon-field-2)",
  failed: "var(--tavus-bubbletech-1)",
  draft: "var(--tavus-plastic-2)",
};

const monthDays = [
  null, null, null, null, { day: 1, posts: 1 }, { day: 2, posts: 0 }, { day: 3, posts: 0 },
  { day: 4, posts: 0 }, { day: 5, posts: 2 }, { day: 6, posts: 0 }, { day: 7, posts: 1 }, { day: 8, posts: 0 }, { day: 9, posts: 0 }, { day: 10, posts: 0 },
  { day: 11, posts: 1 }, { day: 12, posts: 0 }, { day: 13, posts: 0 }, { day: 14, posts: 2 }, { day: 15, posts: 0 }, { day: 16, posts: 0 }, { day: 17, posts: 0 },
  { day: 18, posts: 0 }, { day: 19, posts: 1 }, { day: 20, posts: 0 }, { day: 21, posts: 0 }, { day: 22, posts: 0 }, { day: 23, posts: 0 }, { day: 24, posts: 0 },
  { day: 25, posts: 1 }, { day: 26, posts: 1 }, { day: 27, posts: 1 }, { day: 28, posts: 2 }, { day: 29, posts: 1 }, { day: 30, posts: 0 }, { day: 31, posts: 0 },
];

const weekDays = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"];

const heatmapHours = ["06:00", "09:00", "12:00", "15:00", "18:00", "21:00"];
const heatmapDays = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"];
// intensity 0-4
const heatmapData: number[][] = [
  [1, 2, 3, 2, 4, 1],
  [1, 2, 4, 3, 4, 2],
  [2, 3, 4, 3, 3, 1],
  [1, 2, 3, 2, 4, 2],
  [1, 3, 4, 4, 4, 3],
  [2, 3, 3, 4, 4, 2],
  [1, 1, 2, 2, 3, 1],
];

const intensityColors = [
  "var(--tavus-plastic-2)",
  "var(--tavus-frost-4)",
  "var(--tavus-bubbletech-3)",
  "var(--tavus-bubbletech-4)",
  "var(--tavus-neon-field-2)",
];

export default function SchedulerPage() {
  const [tab, setTab] = useState<"calendar" | "composer" | "posts" | "insights">("calendar");

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <div className="inline-flex items-center gap-2 mb-3">
          <span className="w-2 h-2 bg-[var(--tavus-terminal-black)]" />
          <span className="text-[11px] font-bold tracking-[0.2em] uppercase text-[var(--tavus-hardware-gray-8)]">SCHEDULER</span>
        </div>
        <h1 className="font-[var(--font-serif-display)] text-3xl sm:text-4xl font-normal tracking-tight text-[var(--tavus-terminal-black)]">
          Social <span className="serif-italic">scheduler</span>
        </h1>
      </div>

      {/* Tabs */}
      <div className="flex flex-wrap gap-2">
        {[
          { id: "calendar", label: "CALENDAR", icon: CalIcon },
          { id: "composer", label: "COMPOSER", icon: Pencil },
          { id: "posts", label: "POSTS", icon: List },
          { id: "insights", label: "INSIGHTS", icon: BarChart3 },
        ].map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id as typeof tab)}
            className={`inline-flex items-center gap-2 px-4 h-9 border-[3px] border-[var(--tavus-terminal-black)] text-[11px] font-extrabold tracking-wider uppercase transition-all ${
              tab === t.id ? "bg-[var(--tavus-bubbletech-4)] shadow-[2px_2px_0_0_var(--tavus-terminal-black)]" : "bg-white"
            }`}
          >
            <t.icon className="w-3.5 h-3.5" />
            {t.label}
          </button>
        ))}
      </div>

      {tab === "calendar" && <CalendarTab />}
      {tab === "composer" && <ComposerTab />}
      {tab === "posts" && <PostsTab />}
      {tab === "insights" && <InsightsTab />}
    </div>
  );
}

function CalendarTab() {
  return (
    <div className="relative bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[6px_6px_0_0_var(--tavus-terminal-black)] overflow-hidden">
      <div className="absolute inset-0 bg-halftone-light opacity-10 pointer-events-none" />
      <div className="win-title-bar relative">
        <span className="w-2.5 h-2.5 bg-[var(--tavus-bubbletech-4)] border border-[var(--tavus-terminal-black)]" />
        <span>AUGUST 2026</span>
        <div className="ml-auto flex items-center gap-1">
          <button className="inline-flex items-center justify-center w-6 h-6 border border-[var(--tavus-terminal-black)] bg-white">
            <ChevronLeft className="w-3.5 h-3.5" />
          </button>
          <button className="inline-flex items-center justify-center w-6 h-6 border border-[var(--tavus-terminal-black)] bg-white">
            <ChevronRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
      <div className="relative p-4">
        <div className="grid grid-cols-7 gap-1 mb-1">
          {weekDays.map((d) => (
            <div key={d} className="text-center text-[9px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)] py-1">{d}</div>
          ))}
        </div>
        <div className="grid grid-cols-7 gap-1">
          {monthDays.map((cell, i) => (
            <div
              key={i}
              className={`aspect-square border-2 border-[var(--tavus-terminal-black)]/15 p-1.5 ${cell ? "bg-white" : "bg-[var(--tavus-plastic-2)]"}`}
            >
              {cell && (
                <div className="flex flex-col h-full">
                  <div className="text-[10px] font-bold text-[var(--tavus-terminal-black)]">{cell.day}</div>
                  {cell.posts > 0 && (
                    <div className="mt-auto flex flex-wrap gap-0.5">
                      {Array.from({ length: cell.posts }).map((_, idx) => (
                        <span key={idx} className="w-1.5 h-1.5 bg-[var(--tavus-bubbletech-4)] border border-[var(--tavus-terminal-black)]" />
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
        <div className="mt-4 flex items-center gap-4 text-[10px] text-[var(--tavus-hardware-gray-8)]">
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 bg-[var(--tavus-bubbletech-4)] border border-[var(--tavus-terminal-black)]" />
            SCHEDULED POST
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 bg-[var(--tavus-neon-field-2)] border border-[var(--tavus-terminal-black)]" />
            PUBLISHED
          </div>
        </div>
      </div>
    </div>
  );
}

function ComposerTab() {
  const [platforms, setPlatforms] = useState<string[]>(["facebook", "instagram"]);
  const [caption, setCaption] = useState("");
  const [mediaType, setMediaType] = useState("image");
  const [scheduledAt, setScheduledAt] = useState("");

  const togglePlatform = (p: string) => {
    setPlatforms((prev) => (prev.includes(p) ? prev.filter((x) => x !== p) : [...prev, p]));
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
      <div className="lg:col-span-2 relative bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[6px_6px_0_0_var(--tavus-terminal-black)] overflow-hidden">
        <div className="absolute inset-0 bg-halftone-light opacity-10 pointer-events-none" />
        <div className="win-title-bar relative">
          <span className="w-2.5 h-2.5 bg-[var(--tavus-bubbletech-4)] border border-[var(--tavus-terminal-black)]" />
          <span>COMPOSE POST</span>
        </div>
        <div className="relative p-5 space-y-4">
          {/* Platform multi-select */}
          <div>
            <label className="block text-[10px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)] mb-1.5">PLATFORMS *</label>
            <div className="flex flex-wrap gap-2">
              {[
                { id: "facebook", label: "Facebook", icon: Facebook, color: "var(--tavus-bubbletech-4)" },
                { id: "instagram", label: "Instagram", icon: Instagram, color: "var(--tavus-neon-field-2)" },
              ].map((p) => {
                const selected = platforms.includes(p.id);
                return (
                  <button
                    key={p.id}
                    onClick={() => togglePlatform(p.id)}
                    className={`inline-flex items-center gap-2 px-3 h-9 border-[3px] border-[var(--tavus-terminal-black)] text-[11px] font-bold tracking-wider uppercase transition-all ${
                      selected ? "shadow-[2px_2px_0_0_var(--tavus-terminal-black)]" : "bg-white opacity-50"
                    }`}
                    style={{ background: selected ? p.color : "white" }}
                  >
                    {selected ? <Check className="w-3.5 h-3.5" /> : <X className="w-3.5 h-3.5" />}
                    <p.icon className="w-3.5 h-3.5" />
                    {p.label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Caption */}
          <div>
            <label className="block text-[10px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)] mb-1.5">CAPTION</label>
            <textarea
              value={caption}
              onChange={(e) => setCaption(e.target.value)}
              rows={5}
              placeholder="Write your caption..."
              className="w-full p-3 border-2 border-[var(--tavus-terminal-black)] bg-white text-sm outline-none resize-none"
            />
            <div className="text-[9px] text-[var(--tavus-hardware-gray-8)] mt-1 text-right">{caption.length} / 2200</div>
          </div>

          {/* Media type + schedule */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-[10px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)] mb-1.5">MEDIA TYPE</label>
              <select value={mediaType} onChange={(e) => setMediaType(e.target.value)} className="w-full h-10 px-3 border-2 border-[var(--tavus-terminal-black)] bg-white text-sm font-bold outline-none">
                <option value="image">Image</option>
                <option value="video">Video / Reel</option>
                <option value="carousel">Carousel</option>
              </select>
            </div>
            <div>
              <label className="block text-[10px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)] mb-1.5">SCHEDULE DATE & TIME</label>
              <input
                type="datetime-local"
                value={scheduledAt}
                onChange={(e) => setScheduledAt(e.target.value)}
                className="w-full h-10 px-3 border-2 border-[var(--tavus-terminal-black)] bg-white text-sm outline-none"
              />
            </div>
          </div>

          {/* AI Generate */}
          <div className="relative bg-[var(--tavus-plastic-1)] border-2 border-[var(--tavus-terminal-black)] p-3 overflow-hidden">
            <div className="absolute inset-0 bg-halftone-light opacity-10 pointer-events-none" />
            <div className="relative flex items-center gap-2 mb-2">
              <Sparkles className="w-4 h-4 text-[var(--tavus-terminal-black)]" strokeWidth={2} />
              <span className="text-[10px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)]">AI CAPTION ASSISTANT</span>
            </div>
            <button className="relative w-full inline-flex items-center justify-center gap-2 px-4 h-10 border-[3px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-neon-field-2)] text-white text-[11px] font-extrabold tracking-wider uppercase shadow-[2px_2px_0_0_var(--tavus-terminal-black)] hover:shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] transition-all">
              <Sparkles className="w-3.5 h-3.5" />
              GENERATE WITH AI
            </button>
          </div>

          <button
            disabled={!caption || platforms.length === 0}
            className="w-full inline-flex items-center justify-center gap-2 px-5 h-11 border-[3px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-bubbletech-4)] text-[11px] font-extrabold tracking-wider uppercase shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:shadow-[4px_4px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] transition-all disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:translate-x-0 disabled:hover:translate-y-0"
          >
            <Clock className="w-3.5 h-3.5" />
            SCHEDULE POST
          </button>
        </div>
      </div>

      {/* Preview */}
      <div className="relative bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[6px_6px_0_0_var(--tavus-terminal-black)] overflow-hidden h-fit">
        <div className="absolute inset-0 bg-halftone-light opacity-10 pointer-events-none" />
        <div className="win-title-bar relative">
          <span className="w-2.5 h-2.5 bg-[var(--tavus-neon-field-2)] border border-[var(--tavus-terminal-black)]" />
          <span>PREVIEW</span>
        </div>
        <div className="relative p-4 space-y-3">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 border-2 border-[var(--tavus-terminal-black)] bg-[var(--tavus-bubbletech-4)] flex items-center justify-center font-extrabold text-xs">CS</div>
            <div>
              <div className="text-sm font-bold text-[var(--tavus-terminal-black)]">Cairo Sneakers Store</div>
              <div className="text-[10px] text-[var(--tavus-hardware-gray-8)]">Sponsored · {scheduledAt || "Not scheduled"}</div>
            </div>
          </div>
          <div className="aspect-square bg-[var(--tavus-plastic-2)] border-2 border-[var(--tavus-terminal-black)] flex items-center justify-center">
            <span className="text-[10px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)]">{mediaType.toUpperCase()} PREVIEW</span>
          </div>
          <div className="text-sm text-[var(--tavus-terminal-black)]">
            {caption || <span className="text-[var(--tavus-hardware-gray-8)] italic">Your caption will appear here...</span>}
          </div>
          <div className="flex items-center gap-2 pt-2 border-t-2 border-[var(--tavus-terminal-black)]/10">
            {platforms.map((p) => (
              <span key={p} className="inline-flex items-center justify-center w-6 h-6 border border-[var(--tavus-terminal-black)] text-white" style={{ background: p === "facebook" ? "var(--tavus-bubbletech-4)" : "var(--tavus-neon-field-2)" }}>
                {p === "facebook" ? <Facebook className="w-3 h-3" /> : <Instagram className="w-3 h-3" />}
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function PostsTab() {
  return (
    <div className="relative bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[6px_6px_0_0_var(--tavus-terminal-black)] overflow-hidden">
      <div className="absolute inset-0 bg-halftone-light opacity-10 pointer-events-none" />
      <div className="win-title-bar relative">
        <span className="w-2.5 h-2.5 bg-[var(--tavus-bubbletech-4)] border border-[var(--tavus-terminal-black)]" />
        <span>SCHEDULED & PUBLISHED POSTS</span>
      </div>
      <div className="relative overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-[var(--tavus-terminal-black)] text-white">
            <tr>
              <th className="text-left p-3 font-extrabold tracking-wider uppercase text-[10px]">CAPTION</th>
              <th className="text-left p-3 font-extrabold tracking-wider uppercase text-[10px]">PLATFORMS</th>
              <th className="text-left p-3 font-extrabold tracking-wider uppercase text-[10px]">MEDIA</th>
              <th className="text-left p-3 font-extrabold tracking-wider uppercase text-[10px]">SCHEDULED AT</th>
              <th className="text-left p-3 font-extrabold tracking-wider uppercase text-[10px]">STATUS</th>
            </tr>
          </thead>
          <tbody>
            {mockPosts.map((p) => (
              <tr key={p.id} className="border-t border-[var(--tavus-terminal-black)]/10 hover:bg-[var(--tavus-plastic-1)]">
                <td className="p-3 max-w-[300px] truncate text-[var(--tavus-terminal-black)]">{p.caption}</td>
                <td className="p-3">
                  <div className="flex items-center gap-1">
                    {p.platforms.map((pl) => (
                      <span key={pl} className="inline-flex items-center justify-center w-6 h-6 border border-[var(--tavus-terminal-black)] text-white" style={{ background: pl === "facebook" ? "var(--tavus-bubbletech-4)" : "var(--tavus-neon-field-2)" }}>
                        {pl === "facebook" ? <Facebook className="w-3 h-3" /> : <Instagram className="w-3 h-3" />}
                      </span>
                    ))}
                  </div>
                </td>
                <td className="p-3 text-[var(--tavus-hardware-gray-8)] uppercase text-[10px] font-bold">{p.media_type}</td>
                <td className="p-3 text-[10px] text-[var(--tavus-hardware-gray-8)] whitespace-nowrap">{p.scheduled_at}</td>
                <td className="p-3">
                  <span className="inline-block px-2 py-0.5 text-[9px] font-bold tracking-wider uppercase border border-[var(--tavus-terminal-black)] text-white" style={{ background: statusColors[p.status] }}>
                    {p.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="relative flex items-center justify-between p-3 border-t-2 border-[var(--tavus-terminal-black)] bg-[var(--tavus-plastic-1)]">
        <div className="text-[10px] font-bold text-[var(--tavus-hardware-gray-8)]">{mockPosts.length} posts</div>
        <div className="text-[10px] text-[var(--tavus-hardware-gray-8)]">{mockPosts.filter((p) => p.status === "scheduled").length} scheduled</div>
      </div>
    </div>
  );
}

function InsightsTab() {
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
        {/* FB overview */}
        <div className="relative bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[6px_6px_0_0_var(--tavus-terminal-black)] overflow-hidden">
          <div className="absolute inset-0 bg-halftone-light opacity-10 pointer-events-none" />
          <div className="win-title-bar relative">
            <span className="w-2.5 h-2.5 bg-[var(--tavus-bubbletech-4)] border border-[var(--tavus-terminal-black)]" />
            <span>FACEBOOK · LAST 30 DAYS</span>
          </div>
          <div className="relative p-4 grid grid-cols-2 gap-2">
            <InsightStat label="FOLLOWERS" value="12.4k" delta="+2.1%" />
            <InsightStat label="REACH" value="48.2k" delta="+8.4%" />
            <InsightStat label="IMPRESSIONS" value="62.7k" delta="+5.2%" />
            <InsightStat label="ENGAGEMENT" value="4.8%" delta="+0.6%" />
          </div>
        </div>
        {/* IG overview */}
        <div className="relative bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[6px_6px_0_0_var(--tavus-terminal-black)] overflow-hidden">
          <div className="absolute inset-0 bg-halftone-light opacity-10 pointer-events-none" />
          <div className="win-title-bar relative">
            <span className="w-2.5 h-2.5 bg-[var(--tavus-neon-field-2)] border border-[var(--tavus-terminal-black)]" />
            <span>INSTAGRAM · LAST 30 DAYS</span>
          </div>
          <div className="relative p-4 grid grid-cols-2 gap-2">
            <InsightStat label="FOLLOWERS" value="8.9k" delta="+1.4%" />
            <InsightStat label="REACH" value="32.1k" delta="+12.0%" />
            <InsightStat label="IMPRESSIONS" value="41.3k" delta="+7.8%" />
            <InsightStat label="ENGAGEMENT" value="6.2%" delta="+1.1%" />
          </div>
        </div>
      </div>

      {/* Best time heatmap */}
      <div className="relative bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[6px_6px_0_0_var(--tavus-terminal-black)] overflow-hidden">
        <div className="absolute inset-0 bg-halftone-light opacity-10 pointer-events-none" />
        <div className="win-title-bar relative">
          <span className="w-2.5 h-2.5 bg-[var(--tavus-atomic-glow-1)] border border-[var(--tavus-terminal-black)]" />
          <span>BEST TIME TO POST · ENGAGEMENT HEATMAP</span>
        </div>
        <div className="relative p-4 overflow-x-auto">
          <div className="min-w-[480px]">
            <div className="grid gap-1" style={{ gridTemplateColumns: `60px repeat(${heatmapHours.length}, 1fr)` }}>
              <div></div>
              {heatmapHours.map((h) => (
                <div key={h} className="text-center text-[9px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)] pb-1">{h}</div>
              ))}
              {heatmapDays.map((d, di) => (
                <>
                  <div key={d} className="text-[9px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)] flex items-center">{d}</div>
                  {heatmapData[di].map((intensity, hi) => (
                    <div
                      key={`${di}-${hi}`}
                      className="aspect-square border border-[var(--tavus-terminal-black)]/20"
                      style={{ background: intensityColors[intensity] }}
                      title={`${d} ${heatmapHours[hi]} — intensity ${intensity}`}
                    />
                  ))}
                </>
              ))}
            </div>
            <div className="mt-4 flex items-center gap-2 text-[9px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)]">
              <span>LOW</span>
              {intensityColors.map((c, i) => (
                <span key={i} className="w-5 h-3 border border-[var(--tavus-terminal-black)] text-white/20" style={{ background: c }} />
              ))}
              <span>HIGH</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function InsightStat({ label, value, delta }: { label: string; value: string; delta: string }) {
  const positive = delta.startsWith("+");
  return (
    <div className="relative bg-[var(--tavus-plastic-1)] border-2 border-[var(--tavus-terminal-black)] p-2.5 overflow-hidden">
      <div className="absolute inset-0 bg-halftone-light opacity-10 pointer-events-none" />
      <div className="relative text-[9px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)]">{label}</div>
      <div className="relative text-lg font-bold text-[var(--tavus-terminal-black)]">{value}</div>
      <div className={`relative text-[10px] font-bold ${positive ? "text-[var(--tavus-neon-field-4)]" : "text-[var(--tavus-bubbletech-4)]"}`}>{delta}</div>
    </div>
  );
}
