import type { ReactNode } from "react";

type PanelProps = {
  id?: string;
  title?: string;
  /** One-line explanation shown under the title. */
  description?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
};

export function Panel({ id, title, description, actions, children, className }: PanelProps) {
  return (
    <section id={id} className={`panel ${className ?? ""}`.trim()} aria-labelledby={title ? `panel-title-${title.replace(/\s+/g, "-").toLowerCase()}` : undefined}>
      {(title || actions) && (
        <div className="panel-title-row">
          {title ? <h2 id={`panel-title-${title.replace(/\s+/g, "-").toLowerCase()}`}>{title}</h2> : <span />}
          {actions}
        </div>
      )}
      {description ? <p className="panel-description muted">{description}</p> : null}
      {children}
    </section>
  );
}
