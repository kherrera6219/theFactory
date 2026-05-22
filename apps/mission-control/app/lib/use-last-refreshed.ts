"use client";

import { useEffect, useState } from "react";

/**
 * Returns a human-readable time-since string that updates every 5 seconds.
 * Pass `null` when no data has been fetched yet.
 *
 * Examples: "just now", "12s ago", "3m ago", "1h ago"
 */
export function useLastRefreshed(timestamp: string | null): string | null {
  const [label, setLabel] = useState<string | null>(null);

  useEffect(() => {
    if (!timestamp) {
      setLabel(null);
      return undefined;
    }

    function compute() {
      if (!timestamp) return;
      const diff = Math.max(0, Math.floor((Date.now() - new Date(timestamp).getTime()) / 1000));
      if (diff < 10) {
        setLabel("just now");
      } else if (diff < 60) {
        setLabel(`${diff}s ago`);
      } else if (diff < 3600) {
        setLabel(`${Math.floor(diff / 60)}m ago`);
      } else {
        setLabel(`${Math.floor(diff / 3600)}h ago`);
      }
    }

    compute();
    const id = window.setInterval(compute, 5000);
    return () => window.clearInterval(id);
  }, [timestamp]);

  return label;
}
