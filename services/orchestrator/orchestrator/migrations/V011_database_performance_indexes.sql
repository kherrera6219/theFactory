-- V011: Performance indexes for the internal application database.
--
-- * mission_knowledge / mission_logicnodes keep language and domain inside
--   JSONB (content_json / node_json), so these are expression indexes.
-- * list_recent_logicnodes orders the whole table by created_at DESC with no
--   mission filter; a standalone created_at index avoids a full sort.
-- * project-scoped mission listing filters on (project_id, state).
--
-- Created WITHOUT CONCURRENTLY because migrations.py executes each file as a
-- single batch on an autocommit connection (implicit transaction block).

CREATE INDEX IF NOT EXISTS idx_mission_knowledge_language
  ON mission_knowledge ((content_json ->> 'language'), created_at DESC);

CREATE INDEX IF NOT EXISTS idx_mission_logicnodes_domain
  ON mission_logicnodes ((node_json ->> 'domain'), created_at DESC);

CREATE INDEX IF NOT EXISTS idx_mission_logicnodes_created_at
  ON mission_logicnodes (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_missions_project_state
  ON missions (project_id, state, created_at DESC);
