import type { ReactNode } from "react";
import Link from "next/link";

import { KeyboardShortcuts } from "../components/keyboard-shortcuts";
import { ShellNav } from "../components/shell-nav";

type ShellLayoutProps = {
  children: ReactNode;
};

export default function ShellLayout({ children }: ShellLayoutProps) {
  return (
    <div className="shell">
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
          <div className="shell-header-meta">
            <strong>Local Runtime</strong>
            <span className="muted">Windows host • No external auth mode</span>
          </div>
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
          <span>Redis: Connected</span>
          <span>DB: Healthy</span>
          <span>Live Transport: Polling fallback</span>
          <span>Ctrl+? for shortcuts</span>
        </footer>
      </div>
      <KeyboardShortcuts />
    </div>
  );
}
