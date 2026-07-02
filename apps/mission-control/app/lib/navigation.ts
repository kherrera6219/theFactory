export type NavItem = {
  href: string;
  label: string;
  description: string;
};

export type NavGroup = {
  label: string;
  items: NavItem[];
};

/**
 * Grouped navigation structure. Each group renders with a muted section label
 * and a hairline divider. The flat NAV_ITEMS export is derived from this for
 * any code that still needs a flat list (e.g., active-path matching).
 */
export const NAV_GROUPS: NavGroup[] = [
  {
    label: "Workflow",
    items: [
      { href: "/", label: "Home", description: "Launch pad and system health" },
      { href: "/chat", label: "Chat", description: "PM Agent conversation and mission intake" },
      { href: "/builder", label: "Builder", description: "Guided mission builder with review preview" },
      { href: "/missions", label: "Missions", description: "Mission lifecycle control center" },
      { href: "/projects", label: "Projects", description: "Operations projects and audit trail" },
      { href: "/missions/history", label: "Mission History", description: "Full archive under mission operations" },
    ],
  },
  {
    label: "Observability",
    items: [
      { href: "/agents", label: "Agents", description: "Agent and pod monitoring" },
      { href: "/logicnodes", label: "LogicNodes", description: "Logic graph explorer and details" },
      { href: "/protocol-bus", label: "Protocol Bus", description: "Live protocol stream and filters" },
      { href: "/alerts", label: "Alerts", description: "System alerts and health events" },
      { href: "/performance", label: "Performance", description: "Mission throughput and latency metrics" },
    ],
  },
  {
    label: "Configuration",
    items: [
      { href: "/databases", label: "Databases", description: "Database health and diagnostics" },
      { href: "/repo", label: "Repo Import", description: "Local ZIP import and mission scoping" },
      { href: "/audit", label: "Audit Log", description: "Chronological system activity and event log" },
      { href: "/settings", label: "Settings", description: "Local runtime and integration controls" },
    ],
  },
];

/** Flat list derived from NAV_GROUPS — use for active-path matching and any
 *  code that iterates all nav items without needing group context. */
export const NAV_ITEMS: NavItem[] = NAV_GROUPS.flatMap((group) => group.items);
