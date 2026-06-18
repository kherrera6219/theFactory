"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { listMissions, getOperationsAgents, listOperationsLogicNodes } from "../lib/api-client";
import { humanizeState, formatDateTime } from "../lib/format";
import { NAV_GROUPS } from "../lib/navigation";
import type { MissionRecord } from "../lib/types";

const DEBOUNCE_MS = 180;
const MAX_RESULTS_PER_GROUP = 5;

/** Keyboard shortcuts shown next to nav items. */
const NAV_SHORTCUTS: Record<string, string> = {
  "/": "Ctrl+D",
  "/chat": "Ctrl+N",
  "/missions": "Ctrl+M",
  "/agents": "Ctrl+A",
  "/logicnodes": "Ctrl+L",
  "/protocol-bus": "Ctrl+B",
  "/settings": "Ctrl+,",
};

/** Icons for nav groups. */
const GROUP_ICONS: Record<string, string> = {
  Workflow: "⟳",
  Observability: "◉",
  Configuration: "⚙",
};

type PaletteItem = {
  id: string;
  group: string;
  label: string;
  sublabel?: string;
  shortcut?: string;
  icon?: string;
  href?: string;
  onSelect?: () => void;
};

/**
 * 6C — Command Palette.
 *
 * - Empty query → navigation links + quick actions.
 * - Query ≥ 2 chars → fuzzy-search missions, agents, logic nodes (pre-loaded).
 * - Ctrl+K or custom event "command-palette-open" opens the palette.
 * - Full ARIA listbox pattern; keyboard navigable.
 */
export function CommandPalette() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);

  // Pre-loaded search data
  const [missions, setMissions] = useState<MissionRecord[]>([]);
  const [agents, setAgents] = useState<Array<{ agent_id: string; name: string; state: string; pod: string }>>([]);
  const [logicNodes, setLogicNodes] = useState<Array<{ node_id: string; node_name: string; state: string }>>([]);

  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  // Pre-load data once on mount.
  useEffect(() => {
    void listMissions(100)
      .then(setMissions)
      .catch(() => {});
    void getOperationsAgents({ missionLimit: 50, assignmentLimit: 50, eventLimit: 50 })
      .then((snap) =>
        setAgents(
          snap.agents.map((a) => ({
            agent_id: a.agent_id,
            name: a.name,
            state: a.state,
            pod: a.pod,
          })),
        ),
      )
      .catch(() => {});
    void listOperationsLogicNodes({ limit: 100 })
      .then((nodes) =>
        setLogicNodes(
          nodes.map((n) => ({
            node_id: n.node_id,
            node_name: String(n.node?.node_name ?? n.node_id),
            state: String(n.node?.state ?? "unknown"),
          })),
        ),
      )
      .catch(() => {});
  }, []);

  // Debounce query.
  useEffect(() => {
    const id = window.setTimeout(() => setDebouncedQuery(query), DEBOUNCE_MS);
    return () => window.clearTimeout(id);
  }, [query]);

  // Global Ctrl+K + custom event listener.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key === "k") {
        e.preventDefault();
        setOpen(true);
      }
      if (e.key === "Escape" && open) {
        close();
      }
    }
    function onCustom() {
      setOpen(true);
    }
    document.addEventListener("keydown", onKey);
    document.addEventListener("command-palette-open", onCustom);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("command-palette-open", onCustom);
    };
  }, [open]);

  // Focus input when opened.
  useEffect(() => {
    if (open) {
      setQuery("");
      setDebouncedQuery("");
      setActiveIndex(0);
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [open]);

  // Reset active index when items change.
  useEffect(() => {
    setActiveIndex(0);
  }, [debouncedQuery]);

  function close() {
    setOpen(false);
    setQuery("");
    setDebouncedQuery("");
    setActiveIndex(0);
  }

  // ── Build item list ──────────────────────────────────────────────────────

  const isSearching = debouncedQuery.trim().length >= 2;

  const navItems: PaletteItem[] = useMemo(
    () =>
      NAV_GROUPS.flatMap((group) =>
        group.items.map((item) => ({
          id: `nav-${item.href}`,
          group: group.label,
          label: item.label,
          sublabel: item.description,
          shortcut: NAV_SHORTCUTS[item.href],
          icon: GROUP_ICONS[group.label] ?? "→",
          href: item.href,
        })),
      ),
    [],
  );

  const actionItems: PaletteItem[] = useMemo(
    () => [
      {
        id: "action-shortcuts",
        group: "Actions",
        label: "Open Keyboard Shortcuts",
        sublabel: "See all keyboard shortcuts",
        shortcut: "Ctrl+?",
        icon: "⌨",
        onSelect: () => {
          document.dispatchEvent(new KeyboardEvent("keydown", { key: "?", ctrlKey: true, bubbles: true }));
        },
      },
      {
        id: "action-refresh",
        group: "Actions",
        label: "Refresh Page",
        sublabel: "Hard reload current view",
        shortcut: "Ctrl+R",
        icon: "↺",
        onSelect: () => window.location.reload(),
      },
    ],
    [],
  );

  const searchItems: PaletteItem[] = useMemo(() => {
    const q = debouncedQuery.trim().toLowerCase();
    if (q.length < 2) return [];

    const missionResults: PaletteItem[] = missions
      .filter((m) => {
        const name = String((m.metadata as Record<string, unknown> | undefined)?.name ?? "").toLowerCase();
        return m.mission_id.toLowerCase().includes(q) || name.includes(q) || m.state.toLowerCase().includes(q);
      })
      .slice(0, MAX_RESULTS_PER_GROUP)
      .map((m) => {
        const name = String((m.metadata as Record<string, unknown> | undefined)?.name ?? "");
        return {
          id: `mission-${m.mission_id}`,
          group: "Missions",
          label: name || m.mission_id.slice(0, 12) + "…",
          sublabel: `${humanizeState(m.state)} · ${formatDateTime(m.created_at)}`,
          icon: "◎",
          href: `/missions/detail?id=${m.mission_id}`,
        };
      });

    const agentResults: PaletteItem[] = agents
      .filter(
        (a) =>
          a.name.toLowerCase().includes(q) ||
          a.agent_id.toLowerCase().includes(q) ||
          a.pod.toLowerCase().includes(q),
      )
      .slice(0, MAX_RESULTS_PER_GROUP)
      .map((a) => ({
        id: `agent-${a.agent_id}`,
        group: "Agents",
        label: a.name,
        sublabel: `${a.state} · pod: ${a.pod}`,
        icon: "◈",
        href: "/agents",
      }));

    const nodeResults: PaletteItem[] = logicNodes
      .filter((n) => n.node_name.toLowerCase().includes(q) || n.node_id.toLowerCase().includes(q))
      .slice(0, MAX_RESULTS_PER_GROUP)
      .map((n) => ({
        id: `node-${n.node_id}`,
        group: "Logic Nodes",
        label: n.node_name,
        sublabel: `state: ${n.state}`,
        icon: "◇",
        href: "/logicnodes",
      }));

    return [...missionResults, ...agentResults, ...nodeResults];
  }, [debouncedQuery, missions, agents, logicNodes]);

  const allItems: PaletteItem[] = isSearching ? searchItems : [...navItems, ...actionItems];

  // Group items for rendering.
  const grouped: [string, PaletteItem[]][] = useMemo(() => {
    const map = new Map<string, PaletteItem[]>();
    for (const item of allItems) {
      const bucket = map.get(item.group) ?? [];
      bucket.push(item);
      map.set(item.group, bucket);
    }
    return Array.from(map.entries());
  }, [allItems]);

  // ── Keyboard navigation ──────────────────────────────────────────────────

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((i) => Math.min(i + 1, allItems.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      const item = allItems[activeIndex];
      if (item) selectItem(item);
    } else if (e.key === "Escape") {
      close();
    }
  }

  function selectItem(item: PaletteItem) {
    if (item.href) router.push(item.href);
    else item.onSelect?.();
    close();
  }

  if (!open) return null;

  let flatIndex = -1;

  return (
    <div
      className="cmd-palette-backdrop"
      role="dialog"
      aria-modal="true"
      aria-label="Command palette"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) close();
      }}
    >
      <div className="cmd-palette">
        {/* Search input */}
        <div className="cmd-palette-input-wrap">
          <span className="cmd-palette-icon" aria-hidden="true">⌕</span>
          <input
            ref={inputRef}
            type="text"
            className="cmd-palette-input"
            placeholder={isSearching ? "Search missions, agents, logic nodes…" : "Type to search, or pick a page below…"}
            value={query}
            autoComplete="off"
            spellCheck={false}
            aria-label="Command palette search"
            aria-expanded="true"
            aria-controls="cmd-palette-list"
            aria-activedescendant={allItems[activeIndex] ? `cmd-item-${allItems[activeIndex].id}` : undefined}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
          />
          {query.length > 0 && (
            <button
              type="button"
              className="cmd-palette-clear"
              aria-label="Clear search"
              onClick={() => {
                setQuery("");
                setDebouncedQuery("");
                inputRef.current?.focus();
              }}
            >
              ✕
            </button>
          )}
        </div>

        {/* Results list */}
        <ul
          ref={listRef}
          id="cmd-palette-list"
          role="listbox"
          aria-label="Results"
          className="cmd-palette-results"
        >
          {allItems.length === 0 && isSearching && (
            <li className="cmd-palette-empty" role="option" aria-selected="false">
              No results for &ldquo;{debouncedQuery}&rdquo;
            </li>
          )}

          {grouped.map(([group, items]) => (
            <li key={group} className="cmd-section">
              <span className="cmd-section-label">{group}</span>
              <ul>
                {items.map((item) => {
                  flatIndex++;
                  const itemIndex = flatIndex;
                  const isActive = activeIndex === itemIndex;
                  return (
                    <li key={item.id} role="option" aria-selected={isActive}>
                      <button
                        id={`cmd-item-${item.id}`}
                        type="button"
                        className={`cmd-item${isActive ? " active" : ""}`}
                        onClick={() => selectItem(item)}
                        onMouseEnter={() => setActiveIndex(itemIndex)}
                      >
                        {item.icon && (
                          <span className="cmd-item-icon" aria-hidden="true">
                            {item.icon}
                          </span>
                        )}
                        <span className="cmd-item-body">
                          <span className="cmd-item-label">{item.label}</span>
                          {item.sublabel && (
                            <span className="cmd-item-sublabel">{item.sublabel}</span>
                          )}
                        </span>
                        {item.shortcut && (
                          <kbd className="cmd-item-shortcut">{item.shortcut}</kbd>
                        )}
                      </button>
                    </li>
                  );
                })}
              </ul>
            </li>
          ))}
        </ul>

        {/* Footer hint */}
        <div className="cmd-palette-footer" aria-hidden="true">
          <span>↑↓ Navigate</span>
          <span>↵ Select</span>
          <span>Esc Close</span>
        </div>
      </div>
    </div>
  );
}

/**
 * Trigger button for the shell header. Clicking opens the command palette
 * by firing the custom "command-palette-open" event.
 */
export function CommandPaletteTrigger() {
  function open() {
    document.dispatchEvent(new Event("command-palette-open"));
  }
  return (
    <button type="button" className="cmd-palette-trigger" onClick={open} aria-label="Open command palette (Ctrl+K)">
      <span className="cmd-palette-trigger-icon" aria-hidden="true">⌕</span>
      <span className="cmd-palette-trigger-label">Search…</span>
      <kbd className="cmd-palette-trigger-badge">Ctrl+K</kbd>
    </button>
  );
}
