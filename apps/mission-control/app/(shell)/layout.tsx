import type { ReactNode } from "react";
import Link from "next/link";

import { KeyboardShortcuts } from "../components/keyboard-shortcuts";
import { ReconnectBanner } from "../components/reconnect-banner";
import { ShellHeaderMeta } from "../components/shell-header-meta";
import { ShellNav } from "../components/shell-nav";

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
          <div className="shell-header-actions">
            <Link href="/chat" className="secondary-button shell-link-button">
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
          <span>Ctrl+? for shortcuts</span>
        </footer>
      </div>
      <KeyboardShortcuts />
    </div>
  );
}
