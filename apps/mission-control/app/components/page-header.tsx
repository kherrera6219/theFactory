import type { ReactNode } from "react";

type PageHeaderProps = {
  eyebrow: string;
  title: string;
  description: string;
  actions?: ReactNode;
  compact?: boolean;
};

export function PageHeader({ eyebrow, title, description, actions, compact = false }: PageHeaderProps) {
  if (compact) {
    return (
      <div className="page-header-compact hero">
        <div className="page-header-compact-main">
          <p className="eyebrow">{eyebrow}</p>
          <h1>{title}</h1>
          {description && <p className="muted">{description}</p>}
        </div>
        {actions ? <div className="page-hero-actions">{actions}</div> : null}
      </div>
    );
  }

  return (
    <section className="panel hero page-hero">
      <div className="page-hero-main">
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {actions ? <div className="page-hero-actions">{actions}</div> : null}
    </section>
  );
}
