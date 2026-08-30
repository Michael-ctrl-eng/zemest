"use client";

import { Facebook, Instagram, Heart, Eye, MessageCircle, TrendingUp, TrendingDown, ThumbsUp } from "lucide-react";

const fbOverview = [
  { label: "FOLLOWERS", value: "12,420", delta: "+2.1%", up: true },
  { label: "REACH", value: "48,210", delta: "+8.4%", up: true },
  { label: "IMPRESSIONS", value: "62,720", delta: "+5.2%", up: true },
  { label: "ENGAGEMENT", value: "4.8%", delta: "+0.6%", up: true },
];

const igOverview = [
  { label: "FOLLOWERS", value: "8,930", delta: "+1.4%", up: true },
  { label: "REACH", value: "32,140", delta: "+12.0%", up: true },
  { label: "IMPRESSIONS", value: "41,310", delta: "+7.8%", up: true },
  { label: "ENGAGEMENT", value: "6.2%", delta: "-0.3%", up: false },
];

const topPosts = [
  { id: "tp1", platform: "facebook", caption: "New Air Max 90 collection drop!", reach: 12450, likes: 320, comments: 28, shares: 14, posted_at: "Aug 25, 12:00 PM" },
  { id: "tp2", platform: "instagram", caption: "Flash sale 30% off all sneakers", reach: 9820, likes: 410, comments: 35, shares: 8, posted_at: "Aug 24, 06:00 PM" },
  { id: "tp3", platform: "instagram", caption: "Behind the scenes photoshoot", reach: 8410, likes: 528, comments: 42, shares: 11, posted_at: "Aug 23, 03:00 PM" },
  { id: "tp4", platform: "facebook", caption: "Customer review spotlight", reach: 6720, likes: 187, comments: 19, shares: 9, posted_at: "Aug 22, 10:00 AM" },
  { id: "tp5", platform: "instagram", caption: "Brand collab teaser", reach: 5430, likes: 312, comments: 24, shares: 6, posted_at: "Aug 21, 08:00 PM" },
];

const trendBars = [
  { day: "Mon", value: 62 },
  { day: "Tue", value: 75 },
  { day: "Wed", value: 48 },
  { day: "Thu", value: 81 },
  { day: "Fri", value: 92 },
  { day: "Sat", value: 88 },
  { day: "Sun", value: 54 },
];

export default function InsightsPage() {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <div className="inline-flex items-center gap-2 mb-3">
          <span className="w-2 h-2 bg-[var(--tavus-terminal-black)]" />
          <span className="text-[11px] font-bold tracking-[0.2em] uppercase text-[var(--tavus-hardware-gray-8)]">INSIGHTS</span>
        </div>
        <h1 className="font-[var(--font-serif-display)] text-3xl sm:text-4xl font-normal tracking-tight text-[var(--tavus-terminal-black)]">
          Performance <span className="serif-italic">insights</span>
        </h1>
      </div>

      {/* Overview cards side by side */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Facebook */}
        <div className="relative bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[6px_6px_0_0_var(--tavus-terminal-black)] overflow-hidden">
          <div className="absolute inset-0 bg-halftone-light opacity-10 pointer-events-none" />
          <div className="win-title-bar relative">
            <span className="w-2.5 h-2.5 bg-[var(--tavus-bubbletech-4)] border border-[var(--tavus-terminal-black)]" />
            <span className="inline-flex items-center gap-1.5"><Facebook className="w-3 h-3" /> FACEBOOK · LAST 30 DAYS</span>
          </div>
          <div className="relative p-4 grid grid-cols-2 gap-3">
            {fbOverview.map((s) => (
              <OverviewStat key={s.label} {...s} icon={s.label === "ENGAGEMENT" ? Heart : s.label === "REACH" ? Eye : s.label === "IMPRESSIONS" ? TrendingUp : ThumbsUp} />
            ))}
          </div>
        </div>

        {/* Instagram */}
        <div className="relative bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[6px_6px_0_0_var(--tavus-terminal-black)] overflow-hidden">
          <div className="absolute inset-0 bg-halftone-light opacity-10 pointer-events-none" />
          <div className="win-title-bar relative">
            <span className="w-2.5 h-2.5 bg-[var(--tavus-neon-field-2)] border border-[var(--tavus-terminal-black)]" />
            <span className="inline-flex items-center gap-1.5"><Instagram className="w-3 h-3" /> INSTAGRAM · LAST 30 DAYS</span>
          </div>
          <div className="relative p-4 grid grid-cols-2 gap-3">
            {igOverview.map((s) => (
              <OverviewStat key={s.label} {...s} icon={s.label === "ENGAGEMENT" ? Heart : s.label === "REACH" ? Eye : s.label === "IMPRESSIONS" ? TrendingUp : ThumbsUp} />
            ))}
          </div>
        </div>
      </div>

      {/* Trends placeholder */}
      <div className="relative bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[6px_6px_0_0_var(--tavus-terminal-black)] overflow-hidden">
        <div className="absolute inset-0 bg-halftone-light opacity-10 pointer-events-none" />
        <div className="win-title-bar relative">
          <span className="w-2.5 h-2.5 bg-[var(--tavus-atomic-glow-1)] border border-[var(--tavus-terminal-black)]" />
          <span>WEEKLY ENGAGEMENT TREND</span>
        </div>
        <div className="relative p-5">
          <div className="flex items-end justify-between gap-3 h-44 border-b-2 border-[var(--tavus-terminal-black)]/20">
            {trendBars.map((b) => (
              <div key={b.day} className="flex-1 flex flex-col items-center justify-end gap-2">
                <div
                  className="w-full border-2 border-[var(--tavus-terminal-black)] bg-[var(--tavus-bubbletech-4)]"
                  style={{ height: `${b.value}%` }}
                />
                <div className="text-[10px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)]">{b.day}</div>
              </div>
            ))}
          </div>
          <div className="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-2">
            <MiniMetric label="PEAK DAY" value="Friday" />
            <MiniMetric label="AVG REACH" value="71.4%" />
            <MiniMetric label="GROWTH" value="+8.4%" />
            <MiniMetric label="FORECAST" value="Stable" />
          </div>
        </div>
      </div>

      {/* Top posts */}
      <div className="relative bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[6px_6px_0_0_var(--tavus-terminal-black)] overflow-hidden">
        <div className="absolute inset-0 bg-halftone-light opacity-10 pointer-events-none" />
        <div className="win-title-bar relative">
          <span className="w-2.5 h-2.5 bg-[var(--tavus-neon-field-2)] border border-[var(--tavus-terminal-black)]" />
          <span>TOP POSTS</span>
        </div>
        <div className="relative overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-[var(--tavus-terminal-black)] text-white">
              <tr>
                <th className="text-left p-3 font-extrabold tracking-wider uppercase text-[10px]">CAPTION</th>
                <th className="text-left p-3 font-extrabold tracking-wider uppercase text-[10px]">PLATFORM</th>
                <th className="text-center p-3 font-extrabold tracking-wider uppercase text-[10px]">REACH</th>
                <th className="text-center p-3 font-extrabold tracking-wider uppercase text-[10px]">LIKES</th>
                <th className="text-center p-3 font-extrabold tracking-wider uppercase text-[10px]">COMMENTS</th>
                <th className="text-center p-3 font-extrabold tracking-wider uppercase text-[10px]">SHARES</th>
                <th className="text-left p-3 font-extrabold tracking-wider uppercase text-[10px]">POSTED AT</th>
              </tr>
            </thead>
            <tbody>
              {topPosts.map((p) => (
                <tr key={p.id} className="border-t border-[var(--tavus-terminal-black)]/10 hover:bg-[var(--tavus-plastic-1)]">
                  <td className="p-3 max-w-[260px] truncate text-[var(--tavus-terminal-black)] font-bold">{p.caption}</td>
                  <td className="p-3">
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 text-[9px] font-bold tracking-wider uppercase border border-[var(--tavus-terminal-black)] text-white" style={{ background: p.platform === "facebook" ? "var(--tavus-bubbletech-4)" : "var(--tavus-neon-field-2)" }}>
                      {p.platform === "facebook" ? <Facebook className="w-2.5 h-2.5" /> : <Instagram className="w-2.5 h-2.5" />}
                      {p.platform === "facebook" ? "FB" : "IG"}
                    </span>
                  </td>
                  <td className="p-3 text-center font-bold text-[var(--tavus-terminal-black)]">{p.reach.toLocaleString()}</td>
                  <td className="p-3 text-center text-[var(--tavus-terminal-black)]">{p.likes}</td>
                  <td className="p-3 text-center text-[var(--tavus-terminal-black)]">{p.comments}</td>
                  <td className="p-3 text-center text-[var(--tavus-terminal-black)]">{p.shares}</td>
                  <td className="p-3 text-[10px] text-[var(--tavus-hardware-gray-8)] whitespace-nowrap">{p.posted_at}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="relative flex items-center justify-between p-3 border-t-2 border-[var(--tavus-terminal-black)] bg-[var(--tavus-plastic-1)]">
          <div className="text-[10px] font-bold text-[var(--tavus-hardware-gray-8)]">{topPosts.length} top posts</div>
          <div className="text-[10px] text-[var(--tavus-hardware-gray-8)]">Total reach: {topPosts.reduce((a, p) => a + p.reach, 0).toLocaleString()}</div>
        </div>
      </div>
    </div>
  );
}

function OverviewStat({ label, value, delta, up, icon: Icon }: { label: string; value: string; delta: string; up: boolean; icon: React.ElementType }) {
  return (
    <div className="relative bg-[var(--tavus-plastic-1)] border-2 border-[var(--tavus-terminal-black)] p-3 overflow-hidden">
      <div className="absolute inset-0 bg-halftone-light opacity-10 pointer-events-none" />
      <div className="relative flex items-center justify-between mb-2">
        <Icon className="w-4 h-4 text-[var(--tavus-terminal-black)]" strokeWidth={2} />
        <span className="text-[9px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)]">{label}</span>
      </div>
      <div className="relative text-xl font-bold text-[var(--tavus-terminal-black)]">{value}</div>
      <div className={`relative text-[10px] font-bold flex items-center gap-0.5 ${up ? "text-[var(--tavus-neon-field-4)]" : "text-[var(--tavus-bubbletech-4)]"}`}>
        {up ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
        {delta}
      </div>
    </div>
  );
}

function MiniMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-[var(--tavus-plastic-1)] border-2 border-[var(--tavus-terminal-black)] p-2">
      <div className="text-[9px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)]">{label}</div>
      <div className="text-sm font-bold text-[var(--tavus-terminal-black)]">{value}</div>
    </div>
  );
}
