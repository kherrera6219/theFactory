export type NavItem = {
  href: string;
  label: string;
  description: string;
};

export const NAV_ITEMS: NavItem[] = [
  { href: "/", label: "Home", description: "Launch pad and system health" },
  { href: "/chat", label: "Chat", description: "PM Agent conversation and mission intake" },
  { href: "/missions", label: "Missions", description: "Mission lifecycle control center" },
  { href: "/agents", label: "Agents", description: "Agent and pod monitoring" },
  { href: "/logicnodes", label: "LogicNodes", description: "Logic graph explorer and details" },
  { href: "/semantic-bus", label: "Semantic Bus", description: "Live protocol stream and filters" },
  { href: "/databases", label: "Databases", description: "Database health and diagnostics" },
  { href: "/repo", label: "Repo Import", description: "GitHub import and mission scoping" },
  { href: "/settings", label: "Settings", description: "Local runtime and integration controls" },
];
