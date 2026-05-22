"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";

import { listOperationsAlerts } from "../lib/api-client";
import { formatDateTime } from "../lib/format";
import type { OperationsAlertRecord } from "../lib/types";

const POLL_INTERVAL_MS = 30_000;
const ALERT_FETCH_LIMIT = 50;

/** 5A — Header notification bell with badge count and right-side alert drawer. */
export function NotificationBell() {
  const [alerts, setAlerts] = useState<OperationsAlertRecord[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const drawerRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);

  const openCount = alerts.filter((a) => a.state === "open").length;

  async function load() {
    try {
      const data = await listOperationsAlerts(ALERT_FETCH_LIMIT);
      setAlerts(data);

      // 5A — Native OS notification for new critical open alerts when tab is hidden.
      if (
        typeof Notification !== "undefined" &&
        Notification.permission === "granted" &&
        document.hidden
      ) {
        const critical = data.filter(
          (a) => a.state === "open" && a.severity === "critical",
        );
        for (const alert of critical.slice(0, 2)) {
          new Notification(`⚠ Mission Control — Critical Alert`, {
            body: alert.title,
            tag: alert.alert_id,
          });
        }
      }
    } catch {
      // Silently degrade — bell stays visible, count shows 0.
    } finally {
      setLoading(false);
    }
  }

  // Request notification permission on first open.
  function handleOpen() {
    setIsOpen((current) => !current);
    if (
      typeof Notification !== "undefined" &&
      Notification.permission === "default"
    ) {
      void Notification.requestPermission();
    }
  }

  useEffect(() => {
    void load();
    const interval = window.setInterval(() => void load(), POLL_INTERVAL_MS);
    return () => window.clearInterval(interval);
  }, []);

  // Close drawer on outside click.
  useEffect(() => {
    if (!isOpen) return;
    function handleOutside(e: MouseEvent) {
      if (
        drawerRef.current &&
        !drawerRef.current.contains(e.target as Node) &&
        buttonRef.current &&
        !buttonRef.current.contains(e.target as Node)
      ) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleOutside);
    return () => document.removeEventListener("mousedown", handleOutside);
  }, [isOpen]);

  // Close drawer on Escape.
  useEffect(() => {
    if (!isOpen) return;
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        setIsOpen(false);
        buttonRef.current?.focus();
      }
    }
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [isOpen]);

  return (
    <div className="notif-bell-wrap">
      <button
        ref={buttonRef}
        type="button"
        className="notif-bell-btn"
        aria-label={`Alerts — ${loading ? "loading" : `${openCount} open`}`}
        aria-expanded={isOpen}
        aria-haspopup="dialog"
        onClick={handleOpen}
      >
        <span className="notif-bell-icon" aria-hidden="true">🔔</span>
        {openCount > 0 && (
          <span className="notif-badge" aria-hidden="true">
            {openCount > 9 ? "9+" : openCount}
          </span>
        )}
      </button>

      {isOpen && (
        <div
          ref={drawerRef}
          className="notif-drawer"
          role="dialog"
          aria-label="Alert notifications"
          aria-modal="false"
        >
          <div className="notif-drawer-header">
            <span className="notif-drawer-title">Alerts</span>
            <Link
              href="/alerts"
              className="secondary-button shell-link-button"
              onClick={() => setIsOpen(false)}
            >
              View all
            </Link>
          </div>

          {loading && (
            <p className="muted notif-drawer-empty">Loading alerts…</p>
          )}

          {!loading && alerts.length === 0 && (
            <p className="muted notif-drawer-empty">No alerts — system is healthy.</p>
          )}

          {!loading && alerts.length > 0 && (
            <ul className="notif-alert-list">
              {alerts.slice(0, 10).map((alert) => (
                <li key={alert.alert_id} className={`notif-alert-item sev-${alert.severity}`}>
                  <div className="notif-alert-row">
                    <span className={`notif-sev-pill sev-${alert.severity}`}>
                      {alert.severity.toUpperCase()}
                    </span>
                    <span className={`notif-state-dot state-${alert.state}`} aria-hidden="true" />
                  </div>
                  <p className="notif-alert-title">{alert.title}</p>
                  <p className="notif-alert-meta">
                    {alert.source} · {formatDateTime(alert.created_at)}
                  </p>
                  {alert.recommendation && (
                    <p className="notif-alert-rec">{alert.recommendation}</p>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
