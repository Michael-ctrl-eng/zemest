"use client";

import { useState, useEffect } from "react";

/**
 * Debounce a value — useful for search inputs.
 * Returns the debounced value after the specified delay.
 * Per PDF spec: 300ms default.
 */
export function useDebounce<T>(value: T, delay: number = 300): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    const handler = setTimeout(() => setDebouncedValue(value), delay);
    return () => clearTimeout(handler);
  }, [value, delay]);

  return debouncedValue;
}
