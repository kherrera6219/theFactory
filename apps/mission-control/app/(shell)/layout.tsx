import type { ReactNode } from "react";
import Link from "next/link";

import { GlobalSearch } from "../components/global-search";
import { KeyboardShortcuts } from "../components/keyboard-shortcuts";
import { NotificationBell } from "../components/notification-bell";
import { ReconnectBanner } from "../components/reconnect-banner";
import { ShellHeaderMeta } from "../components/shell-header-meta";
import { ShellNav } from "../components/shell-nav";
import { StatusBadge } from "../components/status";

type ShellLayoutProps = {
  children: ReactNode;
};

export default function ShellLayout({ children }: ShellLayoutProps) {
  return (
    <div className="shell">
      {/* Pre-wired for SSE/WebSocket connection state — hidden until Codex wires live transport */}
      <ReconnectBanner isVisible={false} status="retrying" />

      <aside className="shell-sidebar">
        <div className="shell-brand">
          <p className="eyebrow">HolyGrail</p>
          <h2>Mission Control</h2>
          <p className="muted">Enterprise local operator console</p>
        </div>
        <ShellNav />
      </aside>

      <div className="shell-main-column">
        <header className="shell-header">
          <ShellHeaderMeta />
          {/* 5D — Global search center zone */}
          <div className="shell-header-search">
            <GlobalSearch />
          </div>
          <div className="shell-header-actions">
            <StatusBadge
              tone="warning"
              label="Offline-ready — live data requires API keys and a running local runtime"
            >
              Offline-ready
            </StatusBadge>
            {/* 5A — Notification bell */}
            <NotificationBell />
            <Link href="/chat" className="primary-button shell-link-button">
              New Mission
            </Link>
            <Link href="/missions" className="secondary-button shell-link-button">
              Mission Center
            </Link>
          </div>
        </header>

        <main id="main-content" className="shell-main" tabIndex={-1}>
          {children}
        </main>
        <footer className="shell-statusbar">
          <span>Live Transport: Active</span>
          <span>Ctrl+K · Search &nbsp;|&nbsp; Ctrl+? · Shortcuts</span>
        </footer>
      </div>
      <KeyboardShortcuts />
    </div>
  );
}
