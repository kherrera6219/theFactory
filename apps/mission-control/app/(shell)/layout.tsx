import type { ReactNode } from "react";
import { cookies } from "next/headers";
import Link from "next/link";
import { redirect } from "next/navigation";

import { KeyboardShortcuts } from "../components/keyboard-shortcuts";
import { LogoutButton } from "../components/logout-button";
import { ReconnectBanner } from "../components/reconnect-banner";
import { ShellHeaderMeta } from "../components/shell-header-meta";
import { ShellNav } from "../components/shell-nav";
import {
  getOperatorSessionFromCookieValue,
  OPERATOR_SESSION_COOKIE_NAME,
} from "../lib/server/operator-session";

type ShellLayoutProps = {
  children: ReactNode;
};

export default async function ShellLayout({ children }: ShellLayoutProps) {
  const cookieStore = await cookies();
  const sessionCookie = cookieStore.get(OPERATOR_SESSION_COOKIE_NAME)?.value;
  if (!getOperatorSessionFromCookieValue(sessionCookie)) {
    redirect("/unlock");
  }

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
            <LogoutButton />
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
