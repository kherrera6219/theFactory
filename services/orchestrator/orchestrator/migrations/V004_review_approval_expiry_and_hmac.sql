ALTER TABLE review_approvals
ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ;

ALTER TABLE review_approvals
ADD COLUMN IF NOT EXISTS hmac_digest TEXT;

CREATE INDEX IF NOT EXISTS idx_review_approvals_expires_at
ON review_approvals (expires_at);
