CREATE TABLE IF NOT EXISTS missions (
    mission_id TEXT PRIMARY KEY,
    prompt TEXT NOT NULL,
    requested_target_language TEXT,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    state TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source_stream_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_missions_state_created_at
ON missions (state, created_at DESC);

CREATE TABLE IF NOT EXISTS mission_state_events (
    event_id BIGSERIAL PRIMARY KEY,
    mission_id TEXT NOT NULL REFERENCES missions(mission_id) ON DELETE CASCADE,
    previous_state TEXT,
    new_state TEXT NOT NULL,
    event_type TEXT NOT NULL,
    ts TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_mission_state_events_mission_ts
ON mission_state_events (mission_id, ts DESC);

CREATE TABLE IF NOT EXISTS mission_pod_assignments (
    mission_id TEXT PRIMARY KEY REFERENCES missions(mission_id) ON DELETE CASCADE,
    pod_name TEXT NOT NULL,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    assigned_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS mission_logicnodes (
    id BIGSERIAL PRIMARY KEY,
    mission_id TEXT NOT NULL REFERENCES missions(mission_id) ON DELETE CASCADE,
    node_id TEXT NOT NULL,
    node_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    UNIQUE (mission_id, node_id)
);

CREATE INDEX IF NOT EXISTS idx_mission_logicnodes_mission_created
ON mission_logicnodes (mission_id, created_at DESC);

CREATE TABLE IF NOT EXISTS mission_knowledge (
    id BIGSERIAL PRIMARY KEY,
    mission_id TEXT NOT NULL REFERENCES missions(mission_id) ON DELETE CASCADE,
    knowledge_id TEXT NOT NULL,
    content_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    UNIQUE (mission_id, knowledge_id)
);

CREATE INDEX IF NOT EXISTS idx_mission_knowledge_mission_created
ON mission_knowledge (mission_id, created_at DESC);

CREATE TABLE IF NOT EXISTS mission_audit_reports (
    id BIGSERIAL PRIMARY KEY,
    mission_id TEXT NOT NULL REFERENCES missions(mission_id) ON DELETE CASCADE,
    audit_id TEXT NOT NULL,
    status TEXT NOT NULL,
    report_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL,
    UNIQUE (mission_id, audit_id)
);

CREATE INDEX IF NOT EXISTS idx_mission_audit_reports_mission_created
ON mission_audit_reports (mission_id, created_at DESC);

CREATE TABLE IF NOT EXISTS agent_runtime_heartbeats (
    agent_id TEXT PRIMARY KEY,
    state TEXT NOT NULL,
    queue_depth INTEGER NOT NULL DEFAULT 0,
    workload_pct INTEGER NOT NULL DEFAULT 0,
    active_mission_ids_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    last_heartbeat TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_runtime_heartbeats_last
ON agent_runtime_heartbeats (last_heartbeat DESC);

CREATE TABLE IF NOT EXISTS agent_runtime_events (
    id BIGSERIAL PRIMARY KEY,
    agent_id TEXT NOT NULL,
    previous_state TEXT,
    new_state TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_runtime_events_agent_created
ON agent_runtime_events (agent_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_agent_runtime_events_created
ON agent_runtime_events (created_at DESC);
