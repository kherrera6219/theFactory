/**
 * ReconnectBanner — displays a fixed top-of-page warning when the live
 * connection to the orchestrator is lost or degraded (retrying/stale).
 *
 * Once WebSocket/SSE is wired, the parent shell layout can drive
 * `status` and `isVisible` from the connection state. For now it is
 * pre-wired and ready — hidden by default.
 *
 * CSS classes `.reconnect-banner`, `.reconnect-banner.stale`, and
 * `.reconnect-banner-spinner` are defined in globals.css.
 */

type ReconnectStatus = "retrying" | "stale";

type ReconnectBannerProps = {
  /** Whether to show the banner. */
  isVisible: boolean;
  /** "retrying" = amber warning; "stale" = red error. */
  status?: ReconnectStatus;
};

export function ReconnectBanner({ isVisible, status = "retrying" }: ReconnectBannerProps) {
  if (!isVisible) {
    return null;
  }

  const message =
    status === "stale"
      ? "Live connection lost — data may be out of date."
      : "Reconnecting to live stream…";

  return (
    <div
      role="alert"
      aria-live="assertive"
      aria-atomic="true"
      className={`reconnect-banner${status === "stale" ? " stale" : ""}`}
    >
      <span className="reconnect-banner-spinner" aria-hidden="true" />
      <span>{message}</span>
    </div>
  );
}
