"use client";

import { useEffect, useId, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";

type ShortcutEntry = {
  combo: string;
  action: string;
};

const SHORTCUTS: ShortcutEntry[] = [
  { combo: "Ctrl+N", action: "Open PM Agent Chat" },
  { combo: "Ctrl+D", action: "Open Home / Launch Pad" },
  { combo: "Ctrl+M", action: "Open Missions" },
  { combo: "Ctrl+A", action: "Open Agents" },
  { combo: "Ctrl+L", action: "Open LogicNodes" },
  { combo: "Ctrl+B", action: "Open Protocol Bus" },
  { combo: "Ctrl+,", action: "Open Settings" },
  { combo: "Ctrl+?", action: "Show shortcut sheet" },
  { combo: "Ctrl+G", action: "Reopen guided tour" },
  { combo: "Ctrl+F", action: "Focus search input on page" },
  { combo: "Ctrl+R", action: "Hard refresh current page" },
  { combo: "Space", action: "Toggle Protocol Bus live stream (on /protocol-bus)" },
];

export function KeyboardShortcuts() {
  const router = useRouter();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const dialogTitleId = useId();
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const closeButtonRef = useRef<HTMLButtonElement | null>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      const key = event.key.toLowerCase();
      const ctrl = event.ctrlKey || event.metaKey;

      if (ctrl && key === "?") {
        event.preventDefault();
        setOpen((current) => !current);
        return;
      }
      if (key === "escape" && open) {
        event.preventDefault();
        setOpen(false);
        return;
      }
      if (!ctrl) {
        if (key === " " && pathname === "/protocol-bus") {
          event.preventDefault();
          window.dispatchEvent(new CustomEvent("protocol-bus-toggle-live"));
        }
        return;
      }

      if (key === "n") {
        event.preventDefault();
        router.push("/chat");
        return;
      }
      if (key === "d") {
        event.preventDefault();
        router.push("/");
        return;
      }
      if (key === "m") {
        event.preventDefault();
        router.push("/missions");
        return;
      }
      if (key === "a") {
        event.preventDefault();
        router.push("/agents");
        return;
      }
      if (key === "l") {
        event.preventDefault();
        router.push("/logicnodes");
        return;
      }
      if (key === "b") {
        event.preventDefault();
        router.push("/protocol-bus");
        return;
      }
      if (key === ",") {
        event.preventDefault();
        router.push("/settings");
        return;
      }
      if (key === "f") {
        event.preventDefault();
        const target = document.querySelector<HTMLInputElement>(
          'input[type="search"], input[placeholder*="Search"], input[placeholder*="search"]',
        );
        target?.focus();
        return;
      }
      if (key === "r") {
        event.preventDefault();
        window.location.reload();
      }
      if (key === "g") {
        event.preventDefault();
        document.dispatchEvent(new Event("guided-tour-open"));
      }
    }

    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [open, pathname, router]);

  useEffect(() => {
    if (!open) {
      return undefined;
    }

    previousFocusRef.current =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
    closeButtonRef.current?.focus();

    function onDialogKeyDown(event: KeyboardEvent) {
      if (event.key !== "Tab") {
        return;
      }

      const focusable = dialogRef.current?.querySelectorAll<HTMLElement>(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
      );
      if (!focusable || focusable.length === 0) {
        event.preventDefault();
        closeButtonRef.current?.focus();
        return;
      }

      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      const active = document.activeElement;

      if (event.shiftKey && active === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && active === last) {
        event.preventDefault();
        first.focus();
      }
    }

    window.addEventListener("keydown", onDialogKeyDown);
    return () => {
      window.removeEventListener("keydown", onDialogKeyDown);
      previousFocusRef.current?.focus();
    };
  }, [open]);

  if (!open) {
    return null;
  }

  return (
    <div
      className="shortcut-sheet-backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby={dialogTitleId}
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) {
          setOpen(false);
        }
      }}
    >
      <div ref={dialogRef} className="shortcut-sheet">
        <div className="panel-title-row">
          <h2 id={dialogTitleId}>Keyboard Shortcuts</h2>
          <button
            ref={closeButtonRef}
            type="button"
            className="secondary-button"
            onClick={() => setOpen(false)}
          >
            Close
          </button>
        </div>
        <ul className="summary-list">
          {SHORTCUTS.map((entry) => (
            <li key={entry.combo}>
              <strong>{entry.combo}</strong>
              <span>{entry.action}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
