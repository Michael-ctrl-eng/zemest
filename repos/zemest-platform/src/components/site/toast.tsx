"use client";

import { create } from "zustand";
import { CheckCircle, AlertCircle, Info, X, XCircle } from "lucide-react";
import { useEffect } from "react";

type ToastType = "success" | "error" | "info" | "warning";

interface Toast {
  id: string;
  type: ToastType;
  message: string;
  duration?: number;
}

interface ToastStore {
  toasts: Toast[];
  addToast: (toast: Omit<Toast, "id">) => void;
  removeToast: (id: string) => void;
}

export const useToastStore = create<ToastStore>((set) => ({
  toasts: [],
  addToast: (toast) => {
    const id = Math.random().toString(36).slice(2);
    set((state) => ({ toasts: [...state.toasts, { ...toast, id }] }));
  },
  removeToast: (id) => set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) })),
}));

// Convenience functions
export const toast = {
  success: (message: string) => useToastStore.getState().addToast({ type: "success", message }),
  error: (message: string) => useToastStore.getState().addToast({ type: "error", message }),
  info: (message: string) => useToastStore.getState().addToast({ type: "info", message }),
  warning: (message: string) => useToastStore.getState().addToast({ type: "warning", message }),
};

const icons = {
  success: CheckCircle,
  error: XCircle,
  warning: AlertCircle,
  info: Info,
};

const colors = {
  success: "var(--tavus-neon-field-2)",
  error: "var(--tavus-bubbletech-4)",
  warning: "var(--tavus-atomic-glow-5)",
  info: "var(--tavus-frost-4)",
};

export function ToastContainer() {
  const { toasts, removeToast } = useToastStore();

  return (
    <div className="fixed bottom-4 right-4 z-[100] space-y-2 max-w-sm">
      {toasts.map((t) => (
        <ToastItem key={t.id} toast={t} onClose={() => removeToast(t.id)} />
      ))}
    </div>
  );
}

function ToastItem({ toast, onClose }: { toast: Toast; onClose: () => void }) {
  const Icon = icons[toast.type];

  useEffect(() => {
    const timer = setTimeout(onClose, toast.duration || 4000);
    return () => clearTimeout(timer);
  }, [toast.duration, onClose]);

  return (
    <div className="relative flex items-start gap-3 bg-white border-[3px] border-[var(--tavus-terminal-black)] shadow-[4px_4px_0_0_var(--tavus-terminal-black)] p-3 pr-8 min-w-[280px]">
      <div className="absolute inset-0 bg-halftone-light opacity-10 pointer-events-none" />
      <div className="relative shrink-0">
        <Icon className="w-5 h-5" style={{ color: colors[toast.type] }} strokeWidth={2} />
      </div>
      <div className="relative flex-1">
        <p className="text-sm font-medium text-[var(--tavus-terminal-black)]">{toast.message}</p>
      </div>
      <button onClick={onClose} className="absolute top-2 right-2 text-[var(--tavus-hardware-gray-8)] hover:text-[var(--tavus-terminal-black)]">
        <X className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}
