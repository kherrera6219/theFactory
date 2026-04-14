"use client";

import { usePathname } from "next/navigation";

import { NAV_ITEMS } from "../lib/navigation";

export function ShellHeaderMeta() {
  const pathname = usePathname();
  const activeItem = NAV_ITEMS.find(
    (item) => pathname === item.href || pathname.startsWith(item.href + "/"),
  );
  const pageLabel = activeItem?.label ?? "Mission Control";

  return (
    <div className="shell-header-meta">
      <strong>Local Runtime — {pageLabel}</strong>
      <span className="muted">Enterprise operator console</span>
    </div>
  );
}
