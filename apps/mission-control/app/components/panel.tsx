import type { ReactNode } from "react";

type PanelProps = {
  title?: string;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
};

export function Panel({ title, actions, children, className }: PanelProps) {
  return (
    <section className={`panel ${className ?? ""}`.trim()}>
      {(title || actions) && (
        <div className="panel-title-row">
          {title ? <h2>{title}</h2> : <span />}
          {actions}
        </div>
      )}
      {children}
    </section>
  );
}
