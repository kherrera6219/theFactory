"use client";

import { sanitizeErrorForDisplay } from "../lib/security";

type ShellErrorProps = {
  error: Error & { digest?: string };
  reset: () => void;
};

export default function ShellError({ error, reset }: ShellErrorProps) {
  const message = sanitizeErrorForDisplay(
    error.message,
    "An unexpected error occurred while rendering this page.",
  );
  return (
    <div className="page shell-page">
      <section className="panel">
        <h1>Workspace Error</h1>
        <p className="error-box">
          {message}
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
