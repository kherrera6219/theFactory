"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { fetchJson } from "../lib/api-client";

export function LogoutButton() {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);

  async function logout() {
    setSubmitting(true);
    try {
      await fetchJson<{ logged_out: boolean }>("/api/session/logout", {
        method: "POST",
      });
    } finally {
      router.push("/settings");
      router.refresh();
      setSubmitting(false);
    }
  }

  return (
    <button type="button" className="secondary-button" onClick={() => void logout()} disabled={submitting}>
      {submitting ? "Signing out..." : "Sign Out"}
    </button>
  );
}
