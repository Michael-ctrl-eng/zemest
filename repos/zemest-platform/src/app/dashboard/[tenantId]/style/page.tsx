"use client";

import { useState } from "react";
import { Sparkles, Upload, FileArchive, RefreshCw, Palette, Type, MessageSquare, Hash, Languages, BookOpen, Quote } from "lucide-react";

const styleProfile = {
  tone: "Friendly and helpful",
  formality: 65,
  greeting_patterns: ["Ahlan wa sahlan!", "Welcome back!", "Hi there, how can I help?"],
  emoji_frequency: "moderate",
  top_emojis: ["heart_eyes", "thumbs_up", "fire", "sparkles", "smile"],
  language_mix: "60% Arabic (Egyptian) / 40% English",
  top_vocabulary: ["in stock", "best price", "guaranteed", "fast shipping", "limited offer"],
  personality_summary: "Warm, energetic Egyptian retail assistant that uses playful Arabic-English mix and light emoji to keep customers engaged.",
};

const channelInstructions = [
  { channel: "Facebook", note: "Export your Page inbox as ZIP from Meta Business Settings > Inbox." },
  { channel: "Instagram", note: "Download message archive via Instagram > Settings > Privacy > Data Download." },
  { channel: "WhatsApp", note: "Export chat from WhatsApp > Chat Info > Export Chat (without media recommended)." },
];

const frequencyColors: Record<string, string> = {
  none: "var(--tavus-plastic-2)",
  low: "var(--tavus-frost-4)",
  moderate: "var(--tavus-atomic-glow-5)",
  high: "var(--tavus-neon-field-2)",
};

export default function StylePage() {
  const [channel, setChannel] = useState("facebook");
  const [dragOver, setDragOver] = useState(false);
  const [fileName, setFileName] = useState<string | null>(null);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <div className="inline-flex items-center gap-2 mb-3">
          <span className="w-2 h-2 bg-[var(--tavus-terminal-black)]" />
          <span className="text-[11px] font-bold tracking-[0.2em] uppercase text-[var(--tavus-hardware-gray-8)]">STYLE LEARNING</span>
        </div>
        <h1 className="font-[var(--font-serif-display)] text-3xl sm:text-4xl font-normal tracking-tight text-[var(--tavus-terminal-black)]">
          Brand <span className="serif-italic">voice</span>
        </h1>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Style profile */}
        <div className="lg:col-span-2 relative bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[6px_6px_0_0_var(--tavus-terminal-black)] overflow-hidden">
          <div className="absolute inset-0 bg-halftone-light opacity-10 pointer-events-none" />
          <div className="win-title-bar relative">
            <span className="w-2.5 h-2.5 bg-[var(--tavus-bubbletech-4)] border border-[var(--tavus-terminal-black)]" />
            <span>CURRENT STYLE PROFILE</span>
          </div>
          <div className="relative p-5 space-y-5">
            {/* Personality summary */}
            <div className="relative bg-[var(--tavus-plastic-1)] border-2 border-[var(--tavus-terminal-black)] p-4 overflow-hidden">
              <div className="absolute inset-0 bg-halftone-light opacity-10 pointer-events-none" />
              <div className="relative flex items-center gap-2 mb-2">
                <Sparkles className="w-4 h-4" strokeWidth={2} />
                <span className="text-[10px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)]">PERSONALITY</span>
              </div>
              <p className="relative font-[var(--font-serif-display)] text-base text-[var(--tavus-terminal-black)] italic">
                &ldquo;{styleProfile.personality_summary}&rdquo;
              </p>
            </div>

            {/* Stats */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <ProfileStat icon={Palette} label="TONE" value={styleProfile.tone} color="var(--tavus-bubbletech-4)" />
              <ProfileStat icon={Type} label="EMOJI FREQUENCY" value={styleProfile.emoji_frequency.toUpperCase()} color={frequencyColors[styleProfile.emoji_frequency]} />
              <ProfileStat icon={Languages} label="LANGUAGE MIX" value={styleProfile.language_mix} color="var(--tavus-atomic-glow-1)" />
              <ProfileStat icon={Hash} label="TOP EMOJIS (AS TEXT)" value={styleProfile.top_emojis.join(" · ")} color="var(--tavus-neon-field-2)" />
            </div>

            {/* Formality bar */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-[10px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)]">FORMALITY LEVEL</span>
                <span className="text-[10px] font-bold text-[var(--tavus-terminal-black)]">{styleProfile.formality}%</span>
              </div>
              <div className="h-3 bg-[var(--tavus-plastic-2)] border-2 border-[var(--tavus-terminal-black)] overflow-hidden">
                <div className="h-full bg-[var(--tavus-bubbletech-4)]" style={{ width: `${styleProfile.formality}%` }} />
              </div>
              <div className="flex justify-between text-[9px] text-[var(--tavus-hardware-gray-8)] mt-1">
                <span>CASUAL</span>
                <span>FORMAL</span>
              </div>
            </div>

            {/* Greeting patterns */}
            <div>
              <div className="flex items-center gap-2 mb-2">
                <MessageSquare className="w-3.5 h-3.5" strokeWidth={2} />
                <span className="text-[10px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)]">GREETING PATTERNS</span>
              </div>
              <div className="flex flex-wrap gap-2">
                {styleProfile.greeting_patterns.map((g) => (
                  <span key={g} className="inline-block px-2 py-1 text-xs border-2 border-[var(--tavus-terminal-black)] bg-white">{g}</span>
                ))}
              </div>
            </div>

            {/* Top vocabulary */}
            <div>
              <div className="flex items-center gap-2 mb-2">
                <BookOpen className="w-3.5 h-3.5" strokeWidth={2} />
                <span className="text-[10px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)]">TOP VOCABULARY</span>
              </div>
              <div className="flex flex-wrap gap-2">
                {styleProfile.top_vocabulary.map((v) => (
                  <span key={v} className="inline-block px-2 py-1 text-xs font-mono border-2 border-[var(--tavus-terminal-black)] bg-[var(--tavus-plastic-2)]">{v}</span>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Upload column */}
        <div className="space-y-5">
          <div className="relative bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[6px_6px_0_0_var(--tavus-terminal-black)] overflow-hidden">
            <div className="absolute inset-0 bg-halftone-light opacity-10 pointer-events-none" />
            <div className="win-title-bar relative">
              <span className="w-2.5 h-2.5 bg-[var(--tavus-neon-field-2)] border border-[var(--tavus-terminal-black)]" />
              <span>UPLOAD CHAT HISTORY</span>
            </div>
            <div className="relative p-5 space-y-4">
              <div>
                <label className="block text-[10px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)] mb-1.5">CHANNEL</label>
                <select value={channel} onChange={(e) => setChannel(e.target.value)} className="w-full h-10 px-3 border-2 border-[var(--tavus-terminal-black)] bg-white text-sm font-bold outline-none">
                  <option value="facebook">Facebook</option>
                  <option value="instagram">Instagram</option>
                  <option value="whatsapp">WhatsApp</option>
                </select>
              </div>
              <div>
                <label className="block text-[10px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)] mb-1.5">ZIP ARCHIVE</label>
                <div
                  onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                  onDragLeave={() => setDragOver(false)}
                  onDrop={(e) => {
                    e.preventDefault();
                    setDragOver(false);
                    if (e.dataTransfer.files[0]) setFileName(e.dataTransfer.files[0].name);
                  }}
                  className={`relative border-2 border-dashed border-[var(--tavus-terminal-black)] bg-[var(--tavus-plastic-1)] p-6 text-center cursor-pointer transition-all ${dragOver ? "bg-[var(--tavus-bubbletech-4)]" : ""}`}
                >
                  <FileArchive className="w-8 h-8 mx-auto mb-2 text-[var(--tavus-terminal-black)]" strokeWidth={2} />
                  <div className="text-[11px] font-bold tracking-wider uppercase text-[var(--tavus-terminal-black)]">
                    {fileName ? fileName : "DROP ZIP HERE"}
                  </div>
                  <div className="text-[9px] text-[var(--tavus-hardware-gray-8)] mt-1">or click to browse</div>
                  <input
                    type="file"
                    accept=".zip"
                    className="absolute inset-0 opacity-0 cursor-pointer"
                    onChange={(e) => setFileName(e.target.files?.[0]?.name ?? null)}
                  />
                </div>
              </div>
              <button
                disabled={!fileName}
                className="w-full inline-flex items-center justify-center gap-2 px-4 h-10 border-[3px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-bubbletech-4)] text-[11px] font-extrabold tracking-wider uppercase shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:shadow-[4px_4px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] transition-all disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:translate-x-0 disabled:hover:translate-y-0"
              >
                <Upload className="w-3.5 h-3.5" />
                UPLOAD
              </button>
            </div>
          </div>

          {/* Per-platform instructions */}
          <div className="relative bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[6px_6px_0_0_var(--tavus-terminal-black)] overflow-hidden">
            <div className="absolute inset-0 bg-halftone-light opacity-10 pointer-events-none" />
            <div className="win-title-bar relative">
              <span className="w-2.5 h-2.5 bg-[var(--tavus-atomic-glow-1)] border border-[var(--tavus-terminal-black)]" />
              <span>UPLOAD INSTRUCTIONS</span>
            </div>
            <div className="relative p-4 space-y-3">
              {channelInstructions.map((c) => (
                <div key={c.channel} className="border-l-[3px] border-[var(--tavus-terminal-black)] pl-3">
                  <div className="text-[10px] font-bold tracking-wider uppercase text-[var(--tavus-terminal-black)] mb-0.5 flex items-center gap-1">
                    <Quote className="w-3 h-3" />
                    {c.channel}
                  </div>
                  <div className="text-[11px] text-[var(--tavus-hardware-gray-8)] leading-snug">{c.note}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Rebuild button */}
          <button className="w-full inline-flex items-center justify-center gap-2 px-4 h-12 border-[3px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-neon-field-2)] text-white text-[11px] font-extrabold tracking-wider uppercase shadow-[4px_4px_0_0_var(--tavus-terminal-black)] hover:shadow-[5px_5px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[2px_2px_0_0_var(--tavus-terminal-black)] transition-all">
            <RefreshCw className="w-4 h-4" />
            REBUILD STYLE PROFILE
          </button>
        </div>
      </div>
    </div>
  );
}

function ProfileStat({ icon: Icon, label, value, color }: { icon: React.ElementType; label: string; value: string; color: string }) {
  return (
    <div className="relative bg-[var(--tavus-plastic-1)] border-2 border-[var(--tavus-terminal-black)] p-3 overflow-hidden">
      <div className="absolute inset-0 bg-halftone-light opacity-10 pointer-events-none" />
      <div className="relative flex items-center gap-2 mb-1.5">
        <span className="inline-flex items-center justify-center w-6 h-6 border border-[var(--tavus-terminal-black)] text-white" style={{ background: color }}>
          <Icon className="w-3 h-3" strokeWidth={2} />
        </span>
        <span className="text-[9px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)]">{label}</span>
      </div>
      <div className="relative text-xs font-bold text-[var(--tavus-terminal-black)]">{value}</div>
    </div>
  );
}
