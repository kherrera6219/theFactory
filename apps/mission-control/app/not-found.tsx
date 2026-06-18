import Link from "next/link";

import { ShellHeaderMeta } from "./components/shell-header-meta";
import { ShellNav } from "./components/shell-nav";

export default function NotFound() {
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
          <ShellHeaderMeta />
          <div className="shell-header-actions">
            <Link href="/chat" className="primary-button shell-link-button">
              Launch via Chat
            </Link>
            <Link href="/missions" className="secondary-button shell-link-button">
              View Missions
            </Link>
          </div>
        </header>

        <main id="main-content" className="shell-main" tabIndex={-1} aria-labelledby="not-found-title">
          <div className="page shell-page">
            <section className="panel">
              <p className="eyebrow">Mission Control</p>
              <h1 id="not-found-title">Route not found</h1>
              <p className="muted">
                This workspace route is not available. Use the primary console routes to return to live
                mission operations.
              </p>
              <div className="inline-actions">
                <Link href="/" className="primary-button shell-link-button">
                  Return Home
                </Link>
                <Link href="/missions" className="secondary-button shell-link-button">
                  View Missions
                </Link>
              </div>
            </section>
          </div>
        </main>
      </div>
    </div>
  );
}
