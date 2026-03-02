"use client";

import { useEffect, useState } from "react";
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
  { combo: "Ctrl+B", action: "Open Semantic Bus" },
  { combo: "Ctrl+,", action: "Open Settings" },
  { combo: "Ctrl+?", action: "Show shortcut sheet" },
  { combo: "Ctrl+F", action: "Focus search input on page" },
  { combo: "Ctrl+R", action: "Hard refresh current page" },
  { combo: "Space", action: "Toggle Semantic Bus live stream (on /semantic-bus)" },
];

export function KeyboardShortcuts() {
  const router = useRouter();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      const key = event.key.toLowerCase();
      const ctrl = event.ctrlKey || event.metaKey;

      if (ctrl && event.shiftKey && key === "/") {
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
        if (key === " " && pathname === "/semantic-bus") {
          event.preventDefault();
          window.dispatchEvent(new CustomEvent("semantic-bus-toggle-live"));
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
        router.push("/semantic-bus");
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
    }

    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [open, pathname, router]);

  if (!open) {
    return null;
  }

  return (
    <div className="shortcut-sheet-backdrop" role="dialog" aria-modal="true" aria-label="Keyboard shortcuts">
      <div className="shortcut-sheet">
        <div className="panel-title-row">
          <h2>Keyboard Shortcuts</h2>
          <button type="button" className="secondary-button" onClick={() => setOpen(false)}>
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

