ALTER TABLE missions
ADD COLUMN IF NOT EXISTS project_id TEXT;

UPDATE missions
SET project_id = COALESCE(
    NULLIF(metadata_json->>'project_id', ''),
    CASE
        WHEN NULLIF(metadata_json->>'source', '') IS NOT NULL THEN
            'project-' || regexp_replace(lower(metadata_json->>'source'), '[^a-z0-9._-]+', '-', 'g')
        ELSE
            'project-' || regexp_replace(lower(mission_id), '[^a-z0-9._-]+', '-', 'g')
    END
)
WHERE project_id IS NULL OR project_id = '';

CREATE INDEX IF NOT EXISTS idx_missions_project_updated_at
ON missions (project_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS agent_action_events (
    event_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    mission_id TEXT NOT NULL REFERENCES missions(mission_id) ON DELETE CASCADE,
    agent_id TEXT NOT NULL,
    service_name TEXT NOT NULL,
    event_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'SUCCESS',
    object_type TEXT,
    object_id TEXT,
    tool_name TEXT,
    trace_id TEXT,
    span_id TEXT,
    correlation_id TEXT,
    parent_event_id TEXT,
    started_at TIMESTAMPTZ NOT NULL,
    ended_at TIMESTAMPTZ,
    duration_ms INTEGER,
    payload_summary_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    content_sha256 TEXT,
    blob_ref TEXT,
    prev_event_digest_sha256 TEXT,
    event_digest_sha256 TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_action_events_project_created
ON agent_action_events (project_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_agent_action_events_project_agent_created
ON agent_action_events (project_id, agent_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_agent_action_events_mission_created
ON agent_action_events (mission_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_agent_action_events_tool_created
ON agent_action_events (tool_name, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_agent_action_events_project_digest
ON agent_action_events (project_id, created_at DESC, event_digest_sha256 DESC);
