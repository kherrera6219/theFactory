"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { listMissions, getOperationsAgents, listOperationsLogicNodes } from "../lib/api-client";
import { humanizeState, formatDateTime } from "../lib/format";
import type { MissionRecord } from "../lib/types";

type SearchResult = {
  id: string;
  label: string;
  sublabel: string;
  href: string;
  group: "Missions" | "Agents" | "Logic Nodes";
};

const DEBOUNCE_MS = 200;
const MAX_RESULTS_PER_GROUP = 4;

/** 5D — Global search bar for the shell header. 200ms debounced, keyboard-navigable dropdown. */
export function GlobalSearch() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [isOpen, setIsOpen] = useState(false);
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [missions, setMissions] = useState<MissionRecord[]>([]);
  const [agents, setAgents] = useState<Array<{ agent_id: string; name: string; state: string; pod: string }>>([]);
  const [logicNodes, setLogicNodes] = useState<Array<{ node_id: string; node_name: string; state: string }>>([]);
  const [activeIndex, setActiveIndex] = useState(-1);
  const inputRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLUListElement>(null);

  // Debounce query changes.
  useEffect(() => {
    const id = window.setTimeout(() => setDebouncedQuery(query), DEBOUNCE_MS);
    return () => window.clearTimeout(id);
  }, [query]);

  // Pre-load data once so search is instant.
  useEffect(() => {
    void listMissions(100)
      .then(setMissions)
      .catch(() => {});
    void getOperationsAgents({ missionLimit: 50, assignmentLimit: 50, eventLimit: 50 })
      .then((snap) => setAgents(snap.agents.map((a) => ({ agent_id: a.agent_id, name: a.name, state: a.state, pod: a.pod }))))
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

  const results: SearchResult[] = useMemo(() => {
    const q = debouncedQuery.trim().toLowerCase();
    if (q.length < 2) return [];

    const missionResults: SearchResult[] = missions
      .filter((m) => {
        const name = String((m.metadata as Record<string, unknown> | undefined)?.name ?? "").toLowerCase();
        return m.mission_id.toLowerCase().includes(q) || name.includes(q) || m.state.toLowerCase().includes(q);
      })
      .slice(0, MAX_RESULTS_PER_GROUP)
      .map((m) => {
        const name = String((m.metadata as Record<string, unknown> | undefined)?.name ?? "");
        return {
          id: m.mission_id,
          label: name || m.mission_id.slice(0, 12) + "…",
          sublabel: `${humanizeState(m.state)} · ${formatDateTime(m.created_at)}`,
          href: `/missions/detail?id=${m.mission_id}`,
          group: "Missions" as const,
        };
      });

    const agentResults: SearchResult[] = agents
      .filter((a) => a.name.toLowerCase().includes(q) || a.agent_id.toLowerCase().includes(q) || a.pod.toLowerCase().includes(q))
      .slice(0, MAX_RESULTS_PER_GROUP)
      .map((a) => ({
        id: a.agent_id,
        label: a.name,
        sublabel: `${a.state} · pod: ${a.pod}`,
        href: `/agents`,
        group: "Agents" as const,
      }));

    const logicNodeResults: SearchResult[] = logicNodes
      .filter((n) => n.node_name.toLowerCase().includes(q) || n.node_id.toLowerCase().includes(q))
      .slice(0, MAX_RESULTS_PER_GROUP)
      .map((n) => ({
        id: n.node_id,
        label: n.node_name,
        sublabel: `state: ${n.state}`,
        href: `/logicnodes`,
        group: "Logic Nodes" as const,
      }));

    return [...missionResults, ...agentResults, ...logicNodeResults];
  }, [debouncedQuery, missions, agents, logicNodes]);

  const groups = useMemo(() => {
    const map = new Map<string, SearchResult[]>();
    for (const r of results) {
      const bucket = map.get(r.group) ?? [];
      bucket.push(r);
      map.set(r.group, bucket);
    }
    return Array.from(map.entries());
  }, [results]);

  useEffect(() => {
    setActiveIndex(-1);
  }, [debouncedQuery]);

  function handleKeyDown(e: React.KeyboardEvent) {
    if (!isOpen) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((i) => Math.min(i + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((i) => Math.max(i - 1, -1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (activeIndex >= 0 && results[activeIndex]) {
        router.push(results[activeIndex].href);
        closeSearch();
      }
    } else if (e.key === "Escape") {
      closeSearch();
    }
  }

  function closeSearch() {
    setIsOpen(false);
    setQuery("");
    setDebouncedQuery("");
    setActiveIndex(-1);
  }

  // Ctrl+K to focus
  useEffect(() => {
    function handleGlobal(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key === "k") {
        e.preventDefault();
        inputRef.current?.focus();
        setIsOpen(true);
      }
    }
    document.addEventListener("keydown", handleGlobal);
    return () => document.removeEventListener("keydown", handleGlobal);
  }, []);

  // Close on outside click.
  useEffect(() => {
    if (!isOpen) return;
    function handleOutside(e: MouseEvent) {
      if (
        inputRef.current?.closest(".global-search-wrap") &&
        !inputRef.current.closest(".global-search-wrap")!.contains(e.target as Node)
      ) {
        closeSearch();
      }
    }
    document.addEventListener("mousedown", handleOutside);
    return () => document.removeEventListener("mousedown", handleOutside);
  }, [isOpen]);

  let flatIndex = -1;

  return (
    <div className="global-search-wrap" role="search">
      <input
        ref={inputRef}
        type="search"
        className="global-search-input"
        placeholder="Search missions, agents, nodes… (Ctrl+K)"
        value={query}
        aria-label="Global search"
        aria-expanded={isOpen && results.length > 0}
        aria-controls="global-search-dropdown"
        aria-autocomplete="list"
        autoComplete="off"
        onChange={(e) => {
          setQuery(e.target.value);
          setIsOpen(e.target.value.length >= 2);
        }}
        onFocus={() => {
          if (query.length >= 2) setIsOpen(true);
        }}
        onKeyDown={handleKeyDown}
      />

      {isOpen && results.length > 0 && (
        <ul
          ref={dropdownRef}
          id="global-search-dropdown"
          className="global-search-dropdown"
          role="listbox"
          aria-label="Search results"
        >
          {groups.map(([group, groupResults]) => (
            <li key={group} className="global-search-group">
              <span className="global-search-group-label">{group}</span>
              <ul>
                {groupResults.map((result) => {
                  flatIndex++;
                  const itemIndex = flatIndex;
                  return (
                    <li key={result.id} role="option" aria-selected={activeIndex === itemIndex}>
                      <button
                        type="button"
                        className={`global-search-result${activeIndex === itemIndex ? " active" : ""}`}
                        onClick={() => {
                          router.push(result.href);
                          closeSearch();
                        }}
                        onMouseEnter={() => setActiveIndex(itemIndex)}
                      >
                        <span className="global-search-label">{result.label}</span>
                        <span className="global-search-sublabel">{result.sublabel}</span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            </li>
          ))}
        </ul>
      )}

      {isOpen && debouncedQuery.length >= 2 && results.length === 0 && (
        <div className="global-search-empty">
          No results for &ldquo;{debouncedQuery}&rdquo;
        </div>
      )}
    </div>
  );
}
