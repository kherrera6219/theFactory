"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { NAV_ITEMS } from "../lib/navigation";

export function ShellNav() {
  const pathname = usePathname();

  return (
    <nav aria-label="Primary">
      <ul className="shell-nav-list">
        {NAV_ITEMS.map((item) => {
          const isActive =
            pathname === item.href ||
            (item.href !== "/" && pathname.startsWith(`${item.href}/`));
          return (
            <li key={item.href}>
              <Link
                href={item.href}
                className={`shell-nav-item ${isActive ? "active" : ""}`}
                aria-current={isActive ? "page" : undefined}
              >
                <span className="shell-nav-label">{item.label}</span>
                <span className="shell-nav-description">{item.description}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
