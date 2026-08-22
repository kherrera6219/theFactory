-- Project continuity bus: durable project record, handoff, and work ledger
-- so follow-on missions resume shared state instead of starting blank.

CREATE TABLE IF NOT EXISTS projects (
    project_id TEXT PRIMARY KEY,
    project_name TEXT NOT NULL,
    source TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    plan_authority_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_projects_status_updated
ON projects (status, updated_at DESC);

CREATE TABLE IF NOT EXISTS project_handoff (
    project_id TEXT PRIMARY KEY REFERENCES projects(project_id) ON DELETE CASCADE,
    current_phase TEXT NOT NULL DEFAULT 'intake',
    next_action TEXT NOT NULL DEFAULT 'pm_intake',
    blockers_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    last_mission_id TEXT,
    plan_revision INTEGER NOT NULL DEFAULT 0,
    plan_summary TEXT,
    authority_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    evidence_refs_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS project_work_items (
    work_item_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    source TEXT NOT NULL DEFAULT 'mission',
    mission_id TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    evidence_ref TEXT,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT project_work_items_status_chk
        CHECK (status IN ('open', 'in_progress', 'blocked', 'done'))
);

CREATE INDEX IF NOT EXISTS idx_project_work_items_project_status
ON project_work_items (project_id, status, sort_order);

CREATE INDEX IF NOT EXISTS idx_project_work_items_mission
ON project_work_items (mission_id)
WHERE mission_id IS NOT NULL;
