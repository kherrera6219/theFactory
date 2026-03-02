import Link from "next/link";

export default function NotFound() {
  return (
    <main className="page shell-page">
      <section className="panel">
        <h1>Page Not Found</h1>
        <p className="muted">The requested route does not exist in the local mission control workspace.</p>
        <Link href="/" className="secondary-button shell-link-button">
          Return to Home
        </Link>
      </section>
    </main>
  );
}
