"use client";

type RootErrorProps = {
  error: Error & { digest?: string };
  reset: () => void;
};

export default function RootError({ error, reset }: RootErrorProps) {
  return (
    <main className="page shell-page">
      <section className="panel">
        <h1>Application Error</h1>
        <p className="error-box">{error.message || "Unexpected application failure."}</p>
        <button type="button" onClick={reset}>
          Retry Application
        </button>
      </section>
    </main>
  );
}
