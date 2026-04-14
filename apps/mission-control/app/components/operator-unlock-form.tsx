"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

export function OperatorUnlockForm() {
  const router = useRouter();
  const [adminKey, setAdminKey] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function unlock() {
    if (adminKey.trim().length < 12) {
      setError("Enter the Mission Control admin key to continue.");
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      const response = await fetch("/api/session/unlock", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ admin_key: adminKey.trim() }),
      });
      const payload = (await response.json()) as { detail?: string };
      if (!response.ok) {
        throw new Error(payload.detail || "Mission Control unlock failed.");
      }
      router.push("/missions");
      router.refresh();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Mission Control unlock failed.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="unlock-panel panel">
      <p className="eyebrow">Mission Control</p>
      <h1>Operator Unlock</h1>
      <p className="muted">
        Enter the configured Mission Control admin key to create a short-lived operator session.
      </p>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void unlock();
        }}
      >
        <label htmlFor="operator-admin-key">Admin key</label>
        <input
          id="operator-admin-key"
          type="password"
          autoComplete="current-password"
          value={adminKey}
          onChange={(event) => setAdminKey(event.target.value)}
          placeholder="MISSION_CONTROL_ADMIN_KEY"
        />
        <div className="inline-actions">
          <button type="submit" disabled={submitting}>
            {submitting ? "Unlocking..." : "Unlock Mission Control"}
          </button>
        </div>
      </form>
      {error && <p className="error-box">{error}</p>}
    </div>
  );
}
