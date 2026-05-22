"use client";

import { useId, useRef, useState } from "react";

type TooltipProps = {
  /** The explanatory text shown in the bubble. */
  content: string;
  children: React.ReactNode;
  /** Which side the bubble appears on. Defaults to "top". */
  side?: "top" | "bottom";
};

/**
 * 6A — Lightweight CSS tooltip. Shown on hover and focus-within.
 * Use with glossary terms: <Tooltip content={GLOSSARY.LogicNode.definition}>LogicNode</Tooltip>
 *
 * Accessibility: the bubble has role="tooltip" and is associated with the trigger
 * via aria-describedby. The trigger wrapper is inline so it does not break flow text.
 */
export function Tooltip({ content, children, side = "top" }: TooltipProps) {
  const id = useId();
  const [visible, setVisible] = useState(false);
  const hideTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  function show() {
    if (hideTimerRef.current) clearTimeout(hideTimerRef.current);
    setVisible(true);
  }

  function hide() {
    // Small delay so moving the cursor between trigger and bubble doesn't flicker.
    hideTimerRef.current = setTimeout(() => setVisible(false), 120);
  }

  return (
    <span
      className={`tooltip-wrap tooltip-side-${side}`}
      onMouseEnter={show}
      onMouseLeave={hide}
      onFocus={show}
      onBlur={hide}
      aria-describedby={visible ? id : undefined}
    >
      <span className="tooltip-trigger">{children}</span>
      {visible && (
        <span id={id} role="tooltip" className="tooltip-bubble">
          {content}
        </span>
      )}
    </span>
  );
}
