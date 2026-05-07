import type { ReactNode } from "react";

export type StatusTone = "healthy" | "warning" | "critical" | "neutral" | "info";

const TONE_LABELS: Record<StatusTone, string> = {
  healthy: "Healthy",
  warning: "Degraded",
  critical: "Offline",
  neutral: "Unknown",
  info: "Info",
};

type StatusBadgeProps = {
  tone: StatusTone;
  children?: ReactNode;
  label?: string;
};

export function StatusBadge({ tone, children, label }: StatusBadgeProps) {
  const text = children ?? TONE_LABELS[tone];
  return (
    <span className={`status-badge ${tone}`} role="status" aria-label={label ?? String(text)}>
      <span className="status-badge-dot" aria-hidden="true" />
      <span className="status-badge-text">{text}</span>
    </span>
  );
}

type SystemMessageProps = {
  tone: Exclude<StatusTone, "healthy" | "neutral"> | "success";
  title: string;
  children?: ReactNode;
  action?: ReactNode;
};

export function SystemMessage({ tone, title, children, action }: SystemMessageProps) {
  return (
    <div className={`system-message ${tone}`} role={tone === "critical" ? "alert" : "status"}>
      <div>
        <strong>{title}</strong>
        {children ? <div className="system-message-body">{children}</div> : null}
      </div>
      {action ? <div className="system-message-action">{action}</div> : null}
    </div>
  );
}

type EmptyStateProps = {
  title: string;
  children: ReactNode;
  action?: ReactNode;
  compact?: boolean;
};

export function EmptyState({ title, children, action, compact = false }: EmptyStateProps) {
  return (
    <div className={`empty-state ${compact ? "compact" : ""}`.trim()}>
      <div className="empty-state-marker" aria-hidden="true" />
      <div className="empty-state-copy">
        <h3>{title}</h3>
        <div className="muted">{children}</div>
        {action ? <div className="empty-state-action">{action}</div> : null}
      </div>
    </div>
  );
}

type MetricCardProps = {
  label: string;
  value: ReactNode;
  tone?: StatusTone;
  detail?: string;
  loading?: boolean;
};

export function MetricCard({ label, value, tone = "neutral", detail, loading = false }: MetricCardProps) {
  return (
    <article className={`metric-card ${tone}`}>
      <div className="metric-card-header">
        <h3>{label}</h3>
        <span className={`metric-dot ${tone}`} aria-hidden="true" />
      </div>
      {loading ? (
        <span className="skeleton-line skeleton-metric" aria-hidden="true" />
      ) : (
        <p>{value}</p>
      )}
      {detail ? <span className="metric-detail">{detail}</span> : null}
    </article>
  );
}
