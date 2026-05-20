CREATE TABLE IF NOT EXISTS mission_runtime_qc (
    id BIGSERIAL PRIMARY KEY,
    mission_id TEXT NOT NULL REFERENCES missions(mission_id) ON DELETE CASCADE,
    execution_type TEXT NOT NULL,
    verdict TEXT NOT NULL,
    qc_verdict TEXT,
    exit_code INTEGER,
    language TEXT,
    filename TEXT,
    base_image TEXT,
    stdout_preview TEXT,
    stderr_preview TEXT,
    execution_result_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    qc_assessment_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_mission_runtime_qc_mission_created
ON mission_runtime_qc (mission_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_mission_runtime_qc_verdict
ON mission_runtime_qc (verdict, qc_verdict);

CREATE TABLE IF NOT EXISTS mission_testdata_manifests (
    id BIGSERIAL PRIMARY KEY,
    mission_id TEXT NOT NULL REFERENCES missions(mission_id) ON DELETE CASCADE,
    manifest_json JSONB NOT NULL,
    language TEXT,
    base_image TEXT,
    test_framework TEXT,
    source TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_mission_testdata_manifests_mission_created
ON mission_testdata_manifests (mission_id, created_at DESC);
