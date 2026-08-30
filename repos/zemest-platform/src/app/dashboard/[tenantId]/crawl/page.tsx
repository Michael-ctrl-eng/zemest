"use client";

import { useState } from "react";
import { Globe, Play, FileText, Package, Database, Clock, Search } from "lucide-react";

interface CrawlJob {
  id: string;
  url: string;
  status: "queued" | "running" | "completed" | "failed";
  pages_found: number;
  products_extracted: number;
  started_at: string;
  finished_at: string;
}

const mockJobs: CrawlJob[] = [
  { id: "job1", url: "https://cairosneakers.com", status: "completed", pages_found: 42, products_extracted: 87, started_at: "Aug 27, 09:00 AM", finished_at: "Aug 27, 09:14 AM" },
  { id: "job2", url: "https://cairosneakers.com/sale", status: "completed", pages_found: 18, products_extracted: 34, started_at: "Aug 26, 02:30 PM", finished_at: "Aug 26, 02:38 PM" },
  { id: "job3", url: "https://cairosneakers.com/new", status: "running", pages_found: 12, products_extracted: 8, started_at: "Aug 27, 10:45 AM", finished_at: "—" },
  { id: "job4", url: "https://cairosneakers.com/clearance", status: "failed", pages_found: 0, products_extracted: 0, started_at: "Aug 25, 11:00 AM", finished_at: "Aug 25, 11:02 AM" },
  { id: "job5", url: "https://cairosneakers.com/men", status: "queued", pages_found: 0, products_extracted: 0, started_at: "—", finished_at: "—" },
];

const statusColors: Record<string, string> = {
  queued: "var(--tavus-plastic-2)",
  running: "var(--tavus-atomic-glow-5)",
  completed: "var(--tavus-neon-field-2)",
  failed: "var(--tavus-bubbletech-1)",
};

export default function CrawlPage() {
  const [url, setUrl] = useState("");
  const [depth, setDepth] = useState("2");
  const [search, setSearch] = useState("");

  const filtered = mockJobs.filter((j) => !search || j.url.toLowerCase().includes(search.toLowerCase()));

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <div className="inline-flex items-center gap-2 mb-3">
          <span className="w-2 h-2 bg-[var(--tavus-terminal-black)]" />
          <span className="text-[11px] font-bold tracking-[0.2em] uppercase text-[var(--tavus-hardware-gray-8)]">CRAWL & KNOWLEDGE</span>
        </div>
        <h1 className="font-[var(--font-serif-display)] text-3xl sm:text-4xl font-normal tracking-tight text-[var(--tavus-terminal-black)]">
          Knowledge <span className="serif-italic">builder</span>
        </h1>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Start crawl form */}
        <div className="lg:col-span-2 relative bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[6px_6px_0_0_var(--tavus-terminal-black)] overflow-hidden">
          <div className="absolute inset-0 bg-halftone-light opacity-10 pointer-events-none" />
          <div className="win-title-bar relative">
            <span className="w-2.5 h-2.5 bg-[var(--tavus-bubbletech-4)] border border-[var(--tavus-terminal-black)]" />
            <span>START CRAWL</span>
          </div>
          <div className="relative p-5 space-y-4">
            <div>
              <label className="block text-[10px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)] mb-1.5">TARGET URL *</label>
              <div className="relative">
                <Globe className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--tavus-hardware-gray-8)]" />
                <input
                  type="url"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="https://mystore.com"
                  className="w-full h-11 pl-10 pr-3 border-2 border-[var(--tavus-terminal-black)] bg-white text-sm outline-none"
                />
              </div>
            </div>
            <div>
              <label className="block text-[10px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)] mb-1.5">CRAWL DEPTH</label>
              <select value={depth} onChange={(e) => setDepth(e.target.value)} className="w-full h-11 px-3 border-2 border-[var(--tavus-terminal-black)] bg-white text-sm font-bold outline-none">
                <option value="1">1 — Top-level pages only</option>
                <option value="2">2 — Two levels deep (recommended)</option>
                <option value="3">3 — Three levels deep (slow)</option>
                <option value="5">5 — Full site crawl (very slow)</option>
              </select>
            </div>
            <button
              onClick={() => { setUrl(""); setDepth("2"); }}
              className="w-full inline-flex items-center justify-center gap-2 px-5 h-11 border-[3px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-bubbletech-4)] text-[11px] font-extrabold tracking-wider uppercase shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:shadow-[4px_4px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] transition-all"
            >
              <Play className="w-3.5 h-3.5" />
              START CRAWL JOB
            </button>
          </div>
        </div>

        {/* Knowledge base info */}
        <div className="relative bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[6px_6px_0_0_var(--tavus-terminal-black)] overflow-hidden">
          <div className="absolute inset-0 bg-halftone-light opacity-10 pointer-events-none" />
          <div className="win-title-bar relative">
            <span className="w-2.5 h-2.5 bg-[var(--tavus-neon-field-2)] border border-[var(--tavus-terminal-black)]" />
            <span>KNOWLEDGE BASE</span>
          </div>
          <div className="relative p-5 space-y-3">
            <div className="flex items-center gap-2 mb-2">
              <Database className="w-5 h-5 text-[var(--tavus-terminal-black)]" strokeWidth={2} />
              <div className="text-[10px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)]">INDEXED</div>
            </div>
            <KBStat icon={FileText} label="PAGES INDEXED" value="62" color="var(--tavus-bubbletech-4)" />
            <KBStat icon={Package} label="PRODUCTS" value="87" color="var(--tavus-neon-field-2)" />
            <KBStat icon={Clock} label="LAST UPDATE" value="Aug 27, 09:14 AM" color="var(--tavus-atomic-glow-1)" />
            <KBStat icon={Database} label="VECTOR SIZE" value="14.2 MB" color="var(--tavus-floppy-fog-3)" />
            <button className="w-full inline-flex items-center justify-center gap-2 px-4 h-9 border-[3px] border-[var(--tavus-terminal-black)] bg-white text-[10px] font-extrabold tracking-wider uppercase shadow-[2px_2px_0_0_var(--tavus-terminal-black)] hover:shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] transition-all">
              REBUILD INDEX
            </button>
          </div>
        </div>
      </div>

      {/* Jobs table */}
      <div className="relative bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[6px_6px_0_0_var(--tavus-terminal-black)] overflow-hidden">
        <div className="absolute inset-0 bg-halftone-light opacity-10 pointer-events-none" />
        <div className="relative flex items-center gap-3 p-3 border-b-2 border-[var(--tavus-terminal-black)]">
          <div className="win-title-bar p-0 border-0 bg-transparent flex-1">
            <span className="w-2.5 h-2.5 bg-[var(--tavus-terminal-black)] border border-[var(--tavus-terminal-black)]" />
            <span>CRAWL JOBS</span>
          </div>
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[var(--tavus-hardware-gray-8)]" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Filter by URL..."
              className="w-48 h-8 pl-8 pr-2 border-2 border-[var(--tavus-terminal-black)] bg-white text-xs outline-none"
            />
          </div>
        </div>
        <div className="relative overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-[var(--tavus-terminal-black)] text-white">
              <tr>
                <th className="text-left p-3 font-extrabold tracking-wider uppercase text-[10px]">URL</th>
                <th className="text-left p-3 font-extrabold tracking-wider uppercase text-[10px]">STATUS</th>
                <th className="text-center p-3 font-extrabold tracking-wider uppercase text-[10px]">PAGES</th>
                <th className="text-center p-3 font-extrabold tracking-wider uppercase text-[10px]">PRODUCTS</th>
                <th className="text-left p-3 font-extrabold tracking-wider uppercase text-[10px]">STARTED</th>
                <th className="text-left p-3 font-extrabold tracking-wider uppercase text-[10px]">FINISHED</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((j) => (
                <tr key={j.id} className="border-t border-[var(--tavus-terminal-black)]/10 hover:bg-[var(--tavus-plastic-1)]">
                  <td className="p-3 font-mono text-[var(--tavus-terminal-black)] truncate max-w-[260px]">{j.url}</td>
                  <td className="p-3">
                    <span className="inline-block px-2 py-0.5 text-[9px] font-bold tracking-wider uppercase border border-[var(--tavus-terminal-black)] text-white" style={{ background: statusColors[j.status] }}>
                      {j.status}
                    </span>
                  </td>
                  <td className="p-3 text-center font-bold text-[var(--tavus-terminal-black)]">{j.pages_found}</td>
                  <td className="p-3 text-center font-bold text-[var(--tavus-terminal-black)]">{j.products_extracted}</td>
                  <td className="p-3 text-[10px] text-[var(--tavus-hardware-gray-8)] whitespace-nowrap">{j.started_at}</td>
                  <td className="p-3 text-[10px] text-[var(--tavus-hardware-gray-8)] whitespace-nowrap">{j.finished_at}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="relative flex items-center justify-between p-3 border-t-2 border-[var(--tavus-terminal-black)] bg-[var(--tavus-plastic-1)]">
          <div className="text-[10px] font-bold text-[var(--tavus-hardware-gray-8)]">{filtered.length} jobs</div>
          <div className="text-[10px] text-[var(--tavus-hardware-gray-8)]">{filtered.filter((j) => j.status === "running").length} running</div>
        </div>
      </div>
    </div>
  );
}

function KBStat({ icon: Icon, label, value, color }: { icon: React.ElementType; label: string; value: string; color: string }) {
  return (
    <div className="relative bg-[var(--tavus-plastic-1)] border-2 border-[var(--tavus-terminal-black)] p-2.5 overflow-hidden">
      <div className="absolute inset-0 bg-halftone-light opacity-10 pointer-events-none" />
      <div className="relative flex items-center gap-2.5">
        <span className="inline-flex items-center justify-center w-7 h-7 border border-[var(--tavus-terminal-black)] text-white" style={{ background: color }}>
          <Icon className="w-3.5 h-3.5" strokeWidth={2} />
        </span>
        <div>
          <div className="text-[9px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)]">{label}</div>
          <div className="text-sm font-bold text-[var(--tavus-terminal-black)]">{value}</div>
        </div>
      </div>
    </div>
  );
}
