-- Audit-table retention support.
--
-- The append-only audit tables (mission_state_events, agent_runtime_events,
-- agent_action_events, llm_usage_events) grow unbounded. This migration adds a
-- created_at index where one is missing and a SECURITY DEFINER prune function so
-- a periodic maintenance job can delete rows older than a retention window.
--
-- NOTE: indexes are created WITHOUT CONCURRENTLY on purpose. The migration
-- runner (migrations.py) executes each file as a single statement batch on an
-- autocommit connection, which Postgres treats as one implicit transaction;
-- CREATE INDEX CONCURRENTLY is not allowed inside a transaction block. The other
-- audit tables already carry composite (col, created_at DESC) indexes from
-- V001/V005/V007, so only agent_action_events and llm_usage_events need a
-- standalone created_at index for cheap retention range scans.

CREATE INDEX IF NOT EXISTS idx_llm_usage_events_created_at
  ON llm_usage_events (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_agent_action_events_created_at
  ON agent_action_events (created_at DESC);

-- Retention policy: delete rows older than the retention window from every
-- append-only audit table and report how many rows each delete removed.
--
-- Declared SECURITY DEFINER so it runs with the privileges of the owning role.
-- This lets the function still prune after V009 revokes DELETE on the audit
-- tables from the application role (see V009_immutable_audit.sql).
CREATE OR REPLACE FUNCTION prune_audit_tables(retention_days INTEGER DEFAULT 90)
RETURNS TABLE(table_name TEXT, rows_deleted BIGINT) AS $$
BEGIN
  -- mission_state_events timestamps its rows with `ts` (see V001), not created_at.
  DELETE FROM mission_state_events WHERE ts < NOW() - (retention_days || ' days')::INTERVAL;
  GET DIAGNOSTICS rows_deleted = ROW_COUNT;
  table_name := 'mission_state_events';
  RETURN NEXT;

  DELETE FROM agent_runtime_events WHERE created_at < NOW() - (retention_days || ' days')::INTERVAL;
  GET DIAGNOSTICS rows_deleted = ROW_COUNT;
  table_name := 'agent_runtime_events';
  RETURN NEXT;

  DELETE FROM agent_action_events WHERE created_at < NOW() - (retention_days || ' days')::INTERVAL;
  GET DIAGNOSTICS rows_deleted = ROW_COUNT;
  table_name := 'agent_action_events';
  RETURN NEXT;

  DELETE FROM llm_usage_events WHERE created_at < NOW() - (retention_days || ' days')::INTERVAL;
  GET DIAGNOSTICS rows_deleted = ROW_COUNT;
  table_name := 'llm_usage_events';
  RETURN NEXT;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
