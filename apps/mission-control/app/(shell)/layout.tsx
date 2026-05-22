import type { ReactNode } from "react";
import Link from "next/link";

import { CommandPalette, CommandPaletteTrigger } from "../components/command-palette";
import { GuidedTour } from "../components/guided-tour";
import { KeyboardShortcuts } from "../components/keyboard-shortcuts";
import { NotificationBell } from "../components/notification-bell";
import { ReconnectBanner } from "../components/reconnect-banner";
import { ShellHeaderMeta } from "../components/shell-header-meta";
import { ShellNav } from "../components/shell-nav";
import { StatusBar } from "../components/status-bar";
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
          {/* 6C — Command palette trigger (replaces raw GlobalSearch input) */}
          <div className="shell-header-search">
            <CommandPaletteTrigger />
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
        {/* 6D — Live status bar replaces static footer */}
        <StatusBar />
      </div>

      {/* 6C — Command palette modal (self-contained, manages own open state) */}
      <CommandPalette />
      {/* 6B — First-visit guided tour */}
      <GuidedTour />
      <KeyboardShortcuts />
    </div>
  );
}
