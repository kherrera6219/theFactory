CREATE TABLE IF NOT EXISTS mission_build_artifacts (
    id BIGSERIAL PRIMARY KEY,
    mission_id TEXT NOT NULL REFERENCES missions(mission_id) ON DELETE CASCADE,
    artifact_id TEXT NOT NULL,
    artifact_type TEXT NOT NULL,
    stage TEXT NOT NULL,
    status TEXT NOT NULL,
    storage_backend TEXT NOT NULL DEFAULT 'database',
    storage_ref TEXT,
    digest_sha256 TEXT,
    size_bytes BIGINT NOT NULL DEFAULT 0,
    manifest_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    verification_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    build_log TEXT NOT NULL DEFAULT '',
    artifact_text TEXT,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (mission_id, artifact_id)
);

CREATE INDEX IF NOT EXISTS idx_mission_build_artifacts_mission_updated
ON mission_build_artifacts (mission_id, updated_at DESC);
