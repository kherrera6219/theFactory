"use client";

import { useRouter } from "next/navigation";

import { isOperatorAuthError } from "../lib/operator-auth-error";

/** Renders an "Open Settings" recovery action when `error` looks like an operator-auth failure. */
export function OperatorAuthErrorAction({ error }: { error: string | null | undefined }) {
  const router = useRouter();
  if (!error || !isOperatorAuthError(error)) {
    return null;
  }
  return (
    <div className="inline-actions" style={{ marginTop: "12px" }}>
      <button type="button" className="secondary-button" onClick={() => router.push("/settings")}>
        Open Settings
      </button>
    </div>
  );
}
