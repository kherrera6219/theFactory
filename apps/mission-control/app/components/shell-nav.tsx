"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { NAV_GROUPS } from "../lib/navigation";

export function ShellNav() {
  const pathname = usePathname();

  function isActive(href: string): boolean {
    if (href === "/") return pathname === "/";
    // Match the nav item when we're on the item's page or any sub-page
    // (e.g. /missions/[id] should highlight the Missions nav item).
    return pathname === href || pathname.startsWith(`${href}/`);
  }

  return (
    <nav aria-label="Primary">
      {NAV_GROUPS.map((group, groupIndex) => (
        <div key={group.label} className="shell-nav-group">
          {groupIndex > 0 && (
            <hr className="shell-nav-divider" aria-hidden="true" />
          )}
          <span className="shell-nav-group-label" aria-hidden="true">
            {group.label}
          </span>
          <ul className="shell-nav-list">
            {group.items.map((item) => {
              const active = isActive(item.href);
              return (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    className={`shell-nav-item ${active ? "active" : ""}`}
                    aria-current={active ? "page" : undefined}
                  >
                    <span className="shell-nav-label">{item.label}</span>
                    <span className="shell-nav-description">{item.description}</span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </nav>
  );
}
