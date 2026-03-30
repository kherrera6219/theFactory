CREATE TABLE IF NOT EXISTS review_approvals (
    approval_id TEXT PRIMARY KEY,
    scope TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    summary TEXT NOT NULL,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    receipt_digest TEXT NOT NULL,
    storage_backend TEXT NOT NULL DEFAULT 'postgres',
    approved_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_review_approvals_scope_approved_at
ON review_approvals (scope, approved_at DESC);

CREATE INDEX IF NOT EXISTS idx_review_approvals_fingerprint
ON review_approvals (fingerprint);
