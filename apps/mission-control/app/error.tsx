"use client";

import { sanitizeErrorForDisplay } from "./lib/security";

type RootErrorProps = {
  error: Error & { digest?: string };
  reset: () => void;
};

export default function RootError({ error, reset }: RootErrorProps) {
  const message = sanitizeErrorForDisplay(error.message, "Unexpected application failure.");
  return (
    <div className="page shell-page">
      <section className="panel">
        <h1>Application Error</h1>
        <p className="error-box">{message}</p>
        <button type="button" onClick={reset}>
          Retry Application
        </button>
      </section>
    </div>
  );
}
