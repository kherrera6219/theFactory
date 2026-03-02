"use client";

type ShellErrorProps = {
  error: Error & { digest?: string };
  reset: () => void;
};

export default function ShellError({ error, reset }: ShellErrorProps) {
  return (
    <div className="page shell-page">
      <section className="panel">
        <h1>Workspace Error</h1>
        <p className="error-box">
          {error.message || "An unexpected error occurred while rendering this page."}
        </p>
        <p className="help-text">
          Review service health and retry. If the issue persists, capture logs from the local stack.
        </p>
        <button type="button" onClick={reset}>
          Retry Page
        </button>
      </section>
    </div>
  );
}
