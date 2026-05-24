import type { ReactNode } from "react";

type PanelProps = {
  title?: string;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
};

export function Panel({ title, actions, children, className }: PanelProps) {
  return (
    <section className={`panel ${className ?? ""}`.trim()} aria-labelledby={title ? `panel-title-${title.replace(/\s+/g, "-").toLowerCase()}` : undefined}>
      {(title || actions) && (
        <div className="panel-title-row">
          {title ? <h2 id={`panel-title-${title.replace(/\s+/g, "-").toLowerCase()}`}>{title}</h2> : <span />}
          {actions}
        </div>
      )}
      {children}
    </section>
  );
}
