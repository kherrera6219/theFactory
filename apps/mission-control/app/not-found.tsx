import Link from "next/link";

export default function NotFound() {
  return (
    <main className="standalone-state" aria-labelledby="not-found-title">
      <section className="standalone-state-panel">
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
            Mission Status
          </Link>
        </div>
      </section>
    </main>
  );
}
