export function OperatorUnlockForm() {
  return (
    <div className="unlock-panel panel">
      <p className="eyebrow">Mission Control</p>
      <h1>Operator Session Ready</h1>
      <p className="muted">
        Local Mission Control starts unlocked. Configure provider and runtime keys below; no separate
        operator unlock key is required for this local console.
      </p>
      <div className="inline-actions">
        <span className="status-badge status-badge--healthy">Unlocked</span>
        <span className="muted">Session bypass is enabled for local operation.</span>
      </div>
    </div>
  );
}
