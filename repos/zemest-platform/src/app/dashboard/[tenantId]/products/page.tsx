"use client";

import { useState } from "react";
import { Search, Plus, Upload, Link as LinkIcon, ChevronDown, X } from "lucide-react";

const mockProducts = [
  { id: "p1", name: "Air Max 90 - White", name_ar: "نايك إير ماكس 90 - أبيض", price: 850, stock: "in_stock", category: "Sneakers", source: "manual", attributes: { color: "white", size: "42" } },
  { id: "p2", name: "Air Force 1 - Black", name_ar: "", price: 1200, stock: "in_stock", category: "Sneakers", source: "facebook", attributes: {} },
  { id: "p3", name: "Nike Air Jordan 1", name_ar: "نايك إير جوردان 1", price: 3000, stock: "limited", category: "Sneakers", source: "crawl", attributes: { color: "red", size: "43" } },
  { id: "p4", name: "Adidas Stan Smith", name_ar: "", price: 800, stock: "out_of_stock", category: "Sneakers", source: "url", attributes: {} },
  { id: "p5", name: "Puma Suede Classic", name_ar: "بوما سويد كلاسيك", price: 600, stock: "in_stock", category: "Sneakers", source: "owner", attributes: {} },
];

const stockColors: Record<string, string> = {
  in_stock: "var(--tavus-neon-field-2)",
  out_of_stock: "var(--tavus-bubbletech-4)",
  limited: "var(--tavus-atomic-glow-5)",
};

export default function ProductsPage() {
  const [search, setSearch] = useState("");
  const [sourceFilter, setSourceFilter] = useState("all");
  const [stockFilter, setStockFilter] = useState("all");
  const [showModal, setShowModal] = useState(false);
  const [expandedRow, setExpandedRow] = useState<string | null>(null);

  const filtered = mockProducts.filter((p) => {
    const matchSearch = !search || p.name.toLowerCase().includes(search.toLowerCase());
    const matchSource = sourceFilter === "all" || p.source === sourceFilter;
    const matchStock = stockFilter === "all" || p.stock === stockFilter;
    return matchSearch && matchSource && matchStock;
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <div className="inline-flex items-center gap-2 mb-3">
            <span className="w-2 h-2 bg-[var(--tavus-terminal-black)]" />
            <span className="text-[11px] font-bold tracking-[0.2em] uppercase text-[var(--tavus-hardware-gray-8)]">PRODUCTS</span>
          </div>
          <h1 className="font-[var(--font-serif-display)] text-3xl sm:text-4xl font-normal tracking-tight text-[var(--tavus-terminal-black)]">
            Product <span className="serif-italic">catalog</span>
          </h1>
        </div>
        <div className="flex gap-2">
          <button className="inline-flex items-center gap-2 px-3 h-9 border-[3px] border-[var(--tavus-terminal-black)] bg-white text-[11px] font-extrabold tracking-wider uppercase shadow-[2px_2px_0_0_var(--tavus-terminal-black)] hover:shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] transition-all">
            <Upload className="w-3.5 h-3.5" />
            CSV
          </button>
          <button className="inline-flex items-center gap-2 px-3 h-9 border-[3px] border-[var(--tavus-terminal-black)] bg-white text-[11px] font-extrabold tracking-wider uppercase shadow-[2px_2px_0_0_var(--tavus-terminal-black)] hover:shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] transition-all">
            <LinkIcon className="w-3.5 h-3.5" />
            URL
          </button>
          <button
            onClick={() => setShowModal(true)}
            className="inline-flex items-center gap-2 px-3 h-9 border-[3px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-bubbletech-4)] text-[11px] font-extrabold tracking-wider uppercase shadow-[2px_2px_0_0_var(--tavus-terminal-black)] hover:shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] transition-all"
          >
            <Plus className="w-3.5 h-3.5" />
            ADD
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--tavus-hardware-gray-8)]" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search products..."
            className="w-full h-10 pl-10 pr-3 border-2 border-[var(--tavus-terminal-black)] bg-white text-sm outline-none"
          />
        </div>
        <select value={sourceFilter} onChange={(e) => setSourceFilter(e.target.value)} className="h-10 px-3 border-2 border-[var(--tavus-terminal-black)] bg-white text-sm font-bold">
          <option value="all">All Sources</option>
          <option value="manual">Manual</option>
          <option value="url">URL Import</option>
          <option value="crawl">Crawl</option>
          <option value="facebook">Facebook</option>
          <option value="owner">Owner</option>
        </select>
        <select value={stockFilter} onChange={(e) => setStockFilter(e.target.value)} className="h-10 px-3 border-2 border-[var(--tavus-terminal-black)] bg-white text-sm font-bold">
          <option value="all">All Stock</option>
          <option value="in_stock">In Stock</option>
          <option value="limited">Limited</option>
          <option value="out_of_stock">Out of Stock</option>
        </select>
      </div>

      {/* Products table */}
      <div className="relative bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[6px_6px_0_0_var(--tavus-terminal-black)] overflow-hidden">
        <div className="absolute inset-0 bg-halftone-light opacity-10 pointer-events-none" />
        <div className="relative overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-[var(--tavus-terminal-black)] text-white">
              <tr>
                <th className="text-left p-3 font-extrabold tracking-wider uppercase text-[10px]">NAME</th>
                <th className="text-left p-3 font-extrabold tracking-wider uppercase text-[10px]">PRICE</th>
                <th className="text-left p-3 font-extrabold tracking-wider uppercase text-[10px]">STOCK</th>
                <th className="text-left p-3 font-extrabold tracking-wider uppercase text-[10px]">SOURCE</th>
                <th className="p-3 font-extrabold tracking-wider uppercase text-[10px]"></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((p) => (
                <>
                  <tr key={p.id} className="border-t border-[var(--tavus-terminal-black)]/10 hover:bg-[var(--tavus-plastic-1)]">
                    <td className="p-3">
                      <div className="font-bold text-[var(--tavus-terminal-black)]">{p.name}</div>
                      {p.name_ar && <div className="text-[11px] text-[var(--tavus-hardware-gray-8)]" dir="rtl">{p.name_ar}</div>}
                    </td>
                    <td className="p-3 font-bold text-[var(--tavus-terminal-black)]">{p.price} EGP</td>
                    <td className="p-3">
                      <span className="inline-block px-2 py-0.5 text-[9px] font-bold tracking-wider uppercase border border-[var(--tavus-terminal-black)] text-white" style={{ background: stockColors[p.stock] }}>
                        {p.stock.replace("_", " ")}
                      </span>
                    </td>
                    <td className="p-3 text-[var(--tavus-hardware-gray-8)]">{p.source}</td>
                    <td className="p-3 text-right">
                      <button onClick={() => setExpandedRow(expandedRow === p.id ? null : p.id)} className="inline-flex items-center justify-center w-7 h-7 border border-[var(--tavus-terminal-black)]">
                        <ChevronDown className={`w-3.5 h-3.5 transition-transform ${expandedRow === p.id ? "rotate-180" : ""}`} />
                      </button>
                    </td>
                  </tr>
                  {expandedRow === p.id && (
                    <tr className="bg-[var(--tavus-plastic-1)]">
                      <td colSpan={5} className="p-4">
                        <div className="text-[10px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)] mb-2">ATTRIBUTES</div>
                        {Object.keys(p.attributes).length > 0 ? (
                          <div className="grid grid-cols-3 gap-2">
                            {Object.entries(p.attributes).map(([k, v]) => (
                              <div key={k} className="bg-white border border-[var(--tavus-terminal-black)] px-2 py-1">
                                <span className="text-[9px] font-bold uppercase text-[var(--tavus-hardware-gray-8)]">{k}:</span>
                                <span className="ml-1 text-[var(--tavus-terminal-black)]">{v}</span>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <div className="text-xs text-[var(--tavus-hardware-gray-8)]">No custom attributes</div>
                        )}
                        <div className="flex gap-2 mt-3">
                          <button className="px-3 h-8 border-2 border-[var(--tavus-terminal-black)] bg-white text-[10px] font-bold uppercase">EDIT</button>
                          <button className="px-3 h-8 border-2 border-[var(--tavus-terminal-black)] bg-[var(--tavus-bubbletech-4)] text-[10px] font-bold uppercase">DELETE</button>
                        </div>
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>
        </div>
        {/* Pagination */}
        <div className="relative flex items-center justify-between p-3 border-t-2 border-[var(--tavus-terminal-black)] bg-[var(--tavus-plastic-1)]">
          <div className="text-[10px] font-bold text-[var(--tavus-hardware-gray-8)]">{filtered.length} products</div>
          <div className="flex items-center gap-2">
            <button className="px-2 h-7 border border-[var(--tavus-terminal-black)] bg-white text-[10px] font-bold">PREV</button>
            <span className="text-[10px] font-bold">1 / 1</span>
            <button className="px-2 h-7 border border-[var(--tavus-terminal-black)] bg-white text-[10px] font-bold">NEXT</button>
          </div>
        </div>
      </div>

      {/* Add Product Modal */}
      {showModal && <AddProductModal onClose={() => setShowModal(false)} />}
    </div>
  );
}

function AddProductModal({ onClose }: { onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[var(--tavus-terminal-black)]/50">
      <div className="relative w-full max-w-lg bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[8px_8px_0_0_var(--tavus-terminal-black)] overflow-hidden max-h-[90vh] overflow-y-auto">
        <div className="absolute inset-0 bg-halftone-light opacity-10 pointer-events-none" />
        <div className="win-title-bar relative">
          <span className="w-2.5 h-2.5 bg-[var(--tavus-bubbletech-4)] border border-[var(--tavus-terminal-black)]" />
          <span>ADD PRODUCT</span>
          <button onClick={onClose} className="ml-auto">X</button>
        </div>
        <div className="relative p-5 space-y-4">
          <div>
            <label className="block text-[10px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)] mb-1">NAME *</label>
            <input type="text" className="w-full h-10 px-3 border-2 border-[var(--tavus-terminal-black)] bg-white text-sm outline-none" />
          </div>
          <div>
            <label className="block text-[10px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)] mb-1">ARABIC NAME</label>
            <input type="text" dir="rtl" className="w-full h-10 px-3 border-2 border-[var(--tavus-terminal-black)] bg-white text-sm outline-none" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-[10px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)] mb-1">PRICE (EGP) *</label>
              <input type="number" className="w-full h-10 px-3 border-2 border-[var(--tavus-terminal-black)] bg-white text-sm outline-none" />
            </div>
            <div>
              <label className="block text-[10px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)] mb-1">DISCOUNT PRICE</label>
              <input type="number" className="w-full h-10 px-3 border-2 border-[var(--tavus-terminal-black)] bg-white text-sm outline-none" />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-[10px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)] mb-1">CATEGORY</label>
              <input type="text" className="w-full h-10 px-3 border-2 border-[var(--tavus-terminal-black)] bg-white text-sm outline-none" />
            </div>
            <div>
              <label className="block text-[10px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)] mb-1">STOCK STATUS</label>
              <select className="w-full h-10 px-3 border-2 border-[var(--tavus-terminal-black)] bg-white text-sm outline-none">
                <option value="in_stock">In Stock</option>
                <option value="limited">Limited</option>
                <option value="out_of_stock">Out of Stock</option>
              </select>
            </div>
          </div>
          <div>
            <label className="block text-[10px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)] mb-1">DESCRIPTION</label>
            <textarea rows={2} className="w-full p-2 border-2 border-[var(--tavus-terminal-black)] bg-white text-sm outline-none resize-none" />
          </div>
          <div>
            <label className="block text-[10px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)] mb-1">IMAGE URL</label>
            <input type="url" className="w-full h-10 px-3 border-2 border-[var(--tavus-terminal-black)] bg-white text-sm outline-none" />
          </div>
          <div>
            <label className="block text-[10px] font-bold tracking-wider uppercase text-[var(--tavus-hardware-gray-8)] mb-1">CUSTOM ATTRIBUTES</label>
            <div className="space-y-2">
              <div className="flex gap-2">
                <input type="text" placeholder="key (e.g. color)" className="flex-1 h-9 px-2 border-2 border-[var(--tavus-terminal-black)] bg-white text-sm outline-none" />
                <input type="text" placeholder="value (e.g. white)" className="flex-1 h-9 px-2 border-2 border-[var(--tavus-terminal-black)] bg-white text-sm outline-none" />
                <button className="w-9 h-9 border-2 border-[var(--tavus-terminal-black)] bg-white text-sm">X</button>
              </div>
              <button className="text-[11px] font-bold uppercase text-[var(--tavus-terminal-black)] underline">+ ADD ATTRIBUTE</button>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-full inline-flex items-center justify-center gap-2 px-5 h-11 border-[3px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-bubbletech-4)] text-[11px] font-extrabold tracking-wider uppercase shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:shadow-[4px_4px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] transition-all"
          >
            SAVE PRODUCT
          </button>
        </div>
      </div>
    </div>
  );
}
