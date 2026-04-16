"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

export function LogoutButton() {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);

  async function logout() {
    setSubmitting(true);
    try {
      await fetch("/api/session/logout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
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
