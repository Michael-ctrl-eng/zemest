"use client";

import { Package, Search, Inbox } from "lucide-react";

interface EmptyStateProps {
  icon?: React.ElementType;
  title: string;
  description?: string;
  action?: React.ReactNode;
}

export function EmptyState({ icon: Icon = Inbox, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-12 px-4 text-center">
      <div className="w-16 h-16 border-[3px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-plastic-2)] flex items-center justify-center mb-4">
        <Icon className="w-8 h-8 text-[var(--tavus-hardware-gray-8)]" strokeWidth={1.5} />
      </div>
      <h3 className="font-[var(--font-serif-display)] text-xl font-normal text-[var(--tavus-terminal-black)]">{title}</h3>
      {description && <p className="mt-2 text-sm text-[var(--tavus-hardware-gray-8)] max-w-sm">{description}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

/** Pre-configured empty states for common entities */
export function NoProducts({ onAdd }: { onAdd?: () => void }) {
  return (
    <EmptyState
      icon={Package}
      title="No products yet"
      description="Add your first product to start letting your agent check inventory."
      action={
        onAdd ? (
          <button onClick={onAdd} className="inline-flex items-center gap-2 px-5 h-10 border-[3px] border-[var(--tavus-terminal-black)] bg-[var(--tavus-bubbletech-4)] text-[11px] font-extrabold tracking-wider uppercase shadow-[2px_2px_0_0_var(--tavus-terminal-black)] hover:shadow-[3px_3px_0_0_var(--tavus-terminal-black)] hover:-translate-x-0.5 hover:-translate-y-0.5 active:translate-x-1 active:translate-y-1 active:shadow-[1px_1px_0_0_var(--tavus-terminal-black)] transition-all">
            ADD PRODUCT
          </button>
        ) : null
      }
    />
  );
}

export function NoOrders() {
  return <EmptyState icon={Inbox} title="No orders yet" description="Orders will appear here once customers start buying through your agent." />;
}

export function NoCustomers() {
  return <EmptyState icon={Search} title="No customers found" description="Customers will appear here once they start chatting with your agent." />;
}

export function NoSearchResults({ query }: { query: string }) {
  return <EmptyState icon={Search} title="No results found" description={`No results for "${query}". Try a different search term.`} />;
}
