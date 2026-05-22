"use client";

import { useEffect, useState } from "react";
import { getOperationsSummary } from "../lib/api-client";
import { useLastRefreshed } from "../lib/use-last-refreshed";

const POLL_MS = 15_000;

/** Terminal mission states that do not count toward "active". */
const TERMINAL_STATES = new Set(["FAILED", "VERIFIED", "CANCELLED", "COMPLETE", "COMPLETED"]);

function countActive(stateCounts: Record<string, number>): number {
  return Object.entries(stateCounts)
    .filter(([state]) => !TERMINAL_STATES.has(state.toUpperCase()))
    .reduce((sum, [, count]) => sum + count, 0);
}

function countHealthyServices(runtime: Record<string, boolean | null | undefined>): {
  healthy: number;
  total: number;
} {
  const values = Object.values(runtime).filter((v) => v !== null && v !== undefined);
  const healthy = values.filter(Boolean).length;
  return { healthy, total: values.length };
}

/**
 * 6D — Live status bar.
 *
 * Polls OperationsSummary every 15s and shows:
 *  - Active mission count (with live/offline indicator dot)
 *  - Healthy service count out of total runtime services
 *  - Time since last successful sync
 *
 * Keyboard shortcut hints are always shown on the right.
 */
export function StatusBar() {
  const [activeMissions, setActiveMissions] = useState<number | null>(null);
  const [services, setServices] = useState<{ healthy: number; total: number } | null>(null);
  const [lastSyncAt, setLastSyncAt] = useState<string | null>(null);
  const lastSyncLabel = useLastRefreshed(lastSyncAt);

  useEffect(() => {
    async function load() {
      try {
        const summary = await getOperationsSummary();
        setActiveMissions(countActive(summary.mission_state_counts));
        setServices(countHealthyServices(summary.runtime as Record<string, boolean | null | undefined>));
        setLastSyncAt(new Date().toISOString());
      } catch {
        // Offline — leave existing values, dot turns grey.
        setLastSyncAt(null);
      }
    }

    void load();
    const id = window.setInterval(() => void load(), POLL_MS);
    return () => window.clearInterval(id);
  }, []);

  const isLive = lastSyncAt !== null;

  return (
    <footer className="shell-statusbar">
      {/* Left: runtime health */}
      <div className="statusbar-left">
        <span
          className={`statusbar-dot${isLive ? " live" : " offline"}`}
          aria-label={isLive ? "Runtime online" : "Runtime offline"}
        />
        {activeMissions !== null ? (
          <span>
            {activeMissions} active mission{activeMissions !== 1 ? "s" : ""}
          </span>
        ) : (
          <span className="muted">Offline</span>
        )}
        {services && (
          <span className="statusbar-services muted">
            · {services.healthy}/{services.total} services healthy
          </span>
        )}
        {isLive && lastSyncLabel && (
          <span className="statusbar-sync muted">· synced {lastSyncLabel}</span>
        )}
      </div>

      {/* Right: keyboard hints */}
      <div className="statusbar-right">
        <span>Ctrl+K · Command Palette</span>
        <span className="statusbar-divider" aria-hidden="true">|</span>
        <span>Ctrl+? · Shortcuts</span>
      </div>
    </footer>
  );
}
