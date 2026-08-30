"use client";

import { useState, useEffect, useCallback, use } from "react";
import { Search, Plus, ChevronDown, Package, AlertTriangle, RefreshCw, Loader2, X } from "lucide-react";
import { productsApi, egp, toNumber, type Product } from "@/lib/zemest-api";
import {
  WinCard,
  StatusBadge,
  DashHeader,
  TavusButton,
  TableShell,
  Th,
  Td,
  Row,
  LoadingState,
  ErrorState,
  EmptyState,
  Field,
  inputClass,
  labelClass,
} from "@/components/site/dash";

function getStock(p: Product): number | null {
  const attrStock = (p.attributes as Record<string, unknown> | undefined)?.stock;
  const stock = attrStock ?? (p as { stock?: unknown }).stock;
  const n = toNumber(stock as string | number | null | undefined);
  return stock === undefined || stock === null || stock === "" ? null : n;
}

function stockBadge(stock: number | null): { label: string; status: string } {
  if (stock === null) return { label: "NO STOCK DATA", status: "unknown" };
  if (stock <= 0) return { label: "OUT OF STOCK", status: "out_of_stock" };
  if (stock <= 5) return { label: `${stock} LEFT`, status: "low_stock" };
  return { label: `${stock} IN STOCK`, status: "in_stock" };
}

export default function ProductsPage({ params }: { params: Promise<{ tenantId: string }> }) {
  const { tenantId } = use(params);
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [sourceFilter, setSourceFilter] = useState("all");
  const [showModal, setShowModal] = useState(false);
  const [expandedRow, setExpandedRow] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await productsApi.list(tenantId);
      setProducts(res?.products ?? []);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load products");
    } finally {
      setLoading(false);
    }
  }, [tenantId]);

  useEffect(() => {
    load();
  }, [load]);

  const filtered = products.filter((p) => {
    const matchSearch = !search || p.name.toLowerCase().includes(search.toLowerCase());
    const matchSource = sourceFilter === "all" || p.source === sourceFilter;
    return matchSearch && matchSource;
  });

  const sources = Array.from(new Set(products.map((p) => p.source).filter(Boolean))) as string[];

  return (
    <div className="space-y-6">
      {/* Header */}
      <DashHeader
        eyebrow="Products"
        title="Product"
        tail="catalog"
        action={
          <>
            <button
              onClick={load}
              title="Refresh"
              aria-label="Refresh"
              className="inline-flex items-center justify-center w-11 h-11 border-[3px] border-[var(--tavus-terminal-black)] bg-white shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:shadow-[4px_4px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] transition-all"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} strokeWidth={2.5} />
            </button>
            <TavusButton onClick={() => setShowModal(true)}>
              <Plus className="w-4 h-4" strokeWidth={2.5} /> Add product
            </TavusButton>
          </>
        }
      />

      {/* Error state */}
      {error ? <ErrorState message={error} onRetry={load} /> : null}

      {/* Loading state */}
      {loading ? <LoadingState label="Loading products" /> : null}

      {/* Empty state */}
      {!loading && !error && products.length === 0 ? (
        <WinCard title="No products yet" dot="var(--tavus-atomic-glow-1)">
          <EmptyState
            icon={<Package className="w-6 h-6" strokeWidth={2} />}
            title="Add your first product"
            hint="Your AI agent needs a catalog to sell from. Add products manually, or crawl your website from the Knowledge builder."
            action={
              <TavusButton onClick={() => setShowModal(true)}>
                <Plus className="w-4 h-4" strokeWidth={2.5} /> Add product
              </TavusButton>
            }
          />
        </WinCard>
      ) : null}

      {/* Products table */}
      {!loading && !error && products.length > 0 ? (
        <>
          {/* Filters */}
          <div className="flex flex-wrap gap-3">
            <div className="relative flex-1 min-w-[200px]">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--tavus-hardware-gray-8)]" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search products..."
                className="w-full h-10 pl-10 pr-3 bg-white border-[2.5px] border-[var(--tavus-terminal-black)] text-sm font-semibold text-[var(--tavus-terminal-black)] placeholder:text-[var(--tavus-hardware-gray-8)]/60 placeholder:font-medium focus:outline-none focus:shadow-[3px_3px_0_0_var(--tavus-terminal-black)] transition-shadow"
              />
            </div>
            <select
              value={sourceFilter}
              onChange={(e) => setSourceFilter(e.target.value)}
              className="h-10 px-3 bg-white border-[2.5px] border-[var(--tavus-terminal-black)] text-sm font-semibold text-[var(--tavus-terminal-black)] cursor-pointer"
            >
              <option value="all">All Sources</option>
              {sources.map((s) => (
                <option key={s} value={s}>
                  {s.charAt(0).toUpperCase() + s.slice(1)}
                </option>
              ))}
            </select>
          </div>

          <WinCard title="Products" dot="var(--tavus-bubbletech-4)">
            <TableShell>
              <thead>
                <tr>
                  <Th>Name</Th>
                  <Th>Price</Th>
                  <Th>Stock</Th>
                  <Th>Source</Th>
                  <Th className="text-right">Attributes</Th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((p) => {
                  const stock = getStock(p);
                  const badge = stockBadge(stock);
                  const attrs = (p.attributes as Record<string, unknown> | undefined) ?? {};
                  return (
                    <FragmentRow
                      key={p.id}
                      product={p}
                      stock={stock}
                      badge={badge}
                      attrs={attrs}
                      expanded={expandedRow === p.id}
                      onToggle={() => setExpandedRow(expandedRow === p.id ? null : p.id)}
                    />
                  );
                })}
                {filtered.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="p-8 text-center text-sm font-semibold text-[var(--tavus-hardware-gray-8)]">
                      No products match your filters.
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </TableShell>
            <div className="relative flex items-center justify-between px-4 py-3 border-t-[2px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-plastic-1)]">
              <div className="text-[10px] font-bold tracking-[0.14em] uppercase text-[var(--tavus-hardware-gray-8)]">
                {filtered.length} of {products.length} products
              </div>
              <div className="text-[10px] font-bold text-[var(--tavus-hardware-gray-8)]">
                {products.filter((p) => (getStock(p) ?? 0) > 0).length} in stock
              </div>
            </div>
          </WinCard>
        </>
      ) : null}

      {/* Add Product Modal */}
      {showModal ? <AddProductModal tenantId={tenantId} onClose={() => setShowModal(false)} onCreated={load} /> : null}
    </div>
  );
}

function FragmentRow({
  product,
  stock,
  badge,
  attrs,
  expanded,
  onToggle,
}: {
  product: Product;
  stock: number | null;
  badge: { label: string; status: string };
  attrs: Record<string, unknown>;
  expanded: boolean;
  onToggle: () => void;
}) {
  return (
    <>
      <Row>
        <Td>
          <div className="font-bold text-[var(--tavus-terminal-black)]">{product.name}</div>
          {!product.is_active ? (
            <div className="text-[10px] font-bold tracking-[0.12em] uppercase text-[var(--tavus-coral-1)]">inactive</div>
          ) : null}
        </Td>
        <Td className="font-bold whitespace-nowrap tabular-nums">{egp(product.price)}</Td>
        <Td>
          <StatusBadge status={badge.status}>{badge.label}</StatusBadge>
        </Td>
        <Td className="font-semibold text-[var(--tavus-hardware-gray-8)] capitalize">{product.source || "—"}</Td>
        <Td className="text-right">
          <button
            onClick={onToggle}
            title="Toggle attributes"
            aria-label="Toggle attributes"
            className="inline-flex items-center justify-center w-8 h-8 border-[2px] border-[var(--tavus-terminal-black)] bg-white hover:bg-[var(--tavus-plastic-2)] transition-colors"
          >
            <ChevronDown className={`w-3.5 h-3.5 transition-transform ${expanded ? "rotate-180" : ""}`} strokeWidth={2.5} />
          </button>
        </Td>
      </Row>
      {expanded ? (
        <Row className="bg-[var(--tavus-plastic-1)]">
          <td colSpan={5} className="px-4 py-4">
            <div className="text-[9px] font-extrabold tracking-[0.18em] uppercase text-[var(--tavus-hardware-gray-8)] mb-2">Attributes</div>
            {Object.keys(attrs).length > 0 ? (
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                {Object.entries(attrs).map(([k, v]) => (
                  <div key={k} className="bg-white border-[1.5px] border-[var(--tavus-terminal-black)] px-2 py-1">
                    <span className="text-[9px] font-bold uppercase tracking-[0.1em] text-[var(--tavus-hardware-gray-8)]">{k}:</span>
                    <span className="ml-1 text-[var(--tavus-terminal-black)] font-semibold">{String(v)}</span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-xs font-medium text-[var(--tavus-hardware-gray-8)]">No custom attributes</div>
            )}
          </td>
        </Row>
      ) : null}
    </>
  );
}

function AddProductModal({ tenantId, onClose, onCreated }: { tenantId: string; onClose: () => void; onCreated: () => void }) {
  const [name, setName] = useState("");
  const [price, setPrice] = useState("");
  const [stock, setStock] = useState("");
  const [category, setCategory] = useState("");
  const [description, setDescription] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSave() {
    if (!name.trim() || !price.trim()) {
      setError("Name and price are required.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await productsApi.create(tenantId, {
        name: name.trim(),
        price: Number(price),
        ...(stock.trim() !== "" ? { stock: Number(stock) } : {}),
        ...(category.trim() !== "" ? { category: category.trim() } : {}),
        ...(description.trim() !== "" ? { description: description.trim() } : {}),
      });
      onCreated();
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create product");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[var(--tavus-terminal-black)]/50">
      <div className="relative w-full max-w-lg border-[3px] border-[var(--tavus-terminal-black)] shadow-[8px_8px_0_0_var(--tavus-terminal-black)] bg-white overflow-hidden max-h-[90vh] overflow-y-auto scrollbar-thin">
        <div className="absolute inset-0 bg-halftone-light opacity-[0.35] pointer-events-none" />
        <div className="win-title-bar relative justify-between">
          <span className="flex items-center gap-2 min-w-0">
            <span className="w-2.5 h-2.5 bg-[var(--tavus-bubbletech-4)] border border-[var(--tavus-terminal-black)] shrink-0" />
            <span className="truncate">Add product</span>
          </span>
          <button
            onClick={onClose}
            aria-label="Close"
            title="Close"
            className="shrink-0 inline-flex items-center justify-center w-6 h-6 border-[2px] border-[var(--tavus-terminal-black)] bg-white text-[var(--tavus-terminal-black)] hover:bg-[var(--tavus-coral-3)]/50 transition-colors"
          >
            <X className="w-3.5 h-3.5" strokeWidth={2.5} />
          </button>
        </div>
        <div className="relative p-5 space-y-4">
          {error ? (
            <div className="flex items-center gap-2 border-[2.5px] border-[var(--tavus-coral-1)] bg-[var(--tavus-coral-3)]/40 text-[var(--tavus-terminal-black)] px-3 py-2 text-[12px] font-bold">
              <AlertTriangle className="w-4 h-4 shrink-0" strokeWidth={2.5} />
              {error}
            </div>
          ) : null}
          <Field label="Name *">
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Air Max 90 White"
              className={inputClass}
            />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Price (EGP) *">
              <input
                type="number"
                min="0"
                step="0.01"
                value={price}
                onChange={(e) => setPrice(e.target.value)}
                placeholder="1850"
                className={inputClass}
              />
            </Field>
            <Field label="Stock">
              <input type="number" min="0" value={stock} onChange={(e) => setStock(e.target.value)} placeholder="10" className={inputClass} />
            </Field>
          </div>
          <Field label="Category">
            <input
              type="text"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              placeholder="Sneakers"
              className={inputClass}
            />
          </Field>
          <div>
            <label className={labelClass} htmlFor="product-description">
              Description
            </label>
            <textarea
              id="product-description"
              rows={2}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Premium leather sneakers…"
              className="w-full p-3 bg-white border-[2.5px] border-[var(--tavus-terminal-black)] text-sm font-semibold text-[var(--tavus-terminal-black)] placeholder:text-[var(--tavus-hardware-gray-8)]/60 placeholder:font-medium focus:outline-none focus:shadow-[3px_3px_0_0_var(--tavus-terminal-black)] transition-shadow resize-none"
            />
          </div>
          <TavusButton onClick={handleSave} disabled={loading} className="w-full h-11">
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" strokeWidth={2.5} />}
            {loading ? "Saving…" : "Save product"}
          </TavusButton>
        </div>
      </div>
    </div>
  );
}
