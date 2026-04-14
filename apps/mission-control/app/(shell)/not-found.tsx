import Link from "next/link";

export default function NotFound() {
  return (
    <div className="page shell-page">
      <section className="panel">
        <h2>Page Not Found</h2>
        <p className="muted">The requested route does not exist in the local mission control workspace.</p>
        <div className="inline-actions" style={{ marginTop: "12px" }}>
          <Link href="/" className="secondary-button shell-link-button">
            Return to Home
          </Link>
        </div>
      </section>
    </div>
  );
}
