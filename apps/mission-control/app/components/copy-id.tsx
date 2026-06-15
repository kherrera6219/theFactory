"use client";

import { useState } from "react";
import { copyToClipboard } from "../lib/clipboard";

type CopyIdProps = {
  /** The full identifier string to copy to clipboard. */
  id: string;
  /** Optional truncated display form. Defaults to full id. */
  display?: string;
};

/**
 * Renders a technical identifier in monospace with a clipboard copy button.
 * On click: copies to clipboard, shows a ✓ checkmark for 1.5 s, then reverts.
 *
 * Usage:
 *   <CopyId id={mission.mission_id} />
 *   <CopyId id={slot.slotId} display={slot.slotId.slice(0, 12) + "…"} />
 */
export function CopyId({ id, display }: CopyIdProps) {
  const [copied, setCopied] = useState(false);

  async function handleCopy(event: React.MouseEvent) {
    event.stopPropagation();
    const success = await copyToClipboard(id);
    if (success) {
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    }
  }

  return (
    <span className="copy-id-wrap">
      <span className="mono-id copy-id-text" title={id}>
        {display ?? id}
      </span>
      <button
        type="button"
        className="copy-id-btn"
        aria-label={copied ? "Copied!" : `Copy ${id}`}
        title={copied ? "Copied!" : "Copy to clipboard"}
        onClick={handleCopy}
      >
        {copied ? "✓" : "⎘"}
      </button>
    </span>
  );
}
