CREATE TABLE IF NOT EXISTS llm_usage_events (
    id BIGSERIAL PRIMARY KEY,
    mission_id TEXT NOT NULL REFERENCES missions(mission_id) ON DELETE CASCADE,
    agent_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    estimated_cost_usd NUMERIC(12, 8),
    pricing_known BOOLEAN NOT NULL DEFAULT FALSE,
    call_succeeded BOOLEAN NOT NULL DEFAULT TRUE,
    routing_source TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_llm_usage_events_mission
ON llm_usage_events (mission_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_llm_usage_events_agent
ON llm_usage_events (agent_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_llm_usage_events_provider_model
ON llm_usage_events (provider, model);
