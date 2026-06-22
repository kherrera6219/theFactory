-- Legacy SQLite traceability starter schema.
-- Active runtime ledger tables are managed by Postgres migrations in services/orchestrator/orchestrator/migrations.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS artifacts (
  artifact_id TEXT PRIMARY KEY,
  kind TEXT NOT NULL,            -- e.g., logicnode, rir.fn, rir.module
  registry_ref TEXT NOT NULL,    -- registry://...
  created_ts TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sources (
  source_id INTEGER PRIMARY KEY AUTOINCREMENT,
  artifact_id TEXT NOT NULL,
  kind TEXT NOT NULL,            -- docs|repo
  ref TEXT NOT NULL,
  hash TEXT NOT NULL,
  FOREIGN KEY (artifact_id) REFERENCES artifacts(artifact_id)
);

CREATE TABLE IF NOT EXISTS custody (
  custody_id INTEGER PRIMARY KEY AUTOINCREMENT,
  artifact_id TEXT NOT NULL,
  agent TEXT NOT NULL,
  action TEXT NOT NULL,          -- MINED|VERIFIED|REJECTED|FUSED|BUILT|DEPLOYED
  ts TEXT NOT NULL,
  details_json TEXT,
  FOREIGN KEY (artifact_id) REFERENCES artifacts(artifact_id)
);

CREATE TABLE IF NOT EXISTS audit_runs (
  audit_id TEXT PRIMARY KEY,
  artifact_id TEXT NOT NULL,
  auditor TEXT NOT NULL,
  status TEXT NOT NULL,          -- PASS|FAIL
  ts TEXT NOT NULL,
  report_json TEXT,
  FOREIGN KEY (artifact_id) REFERENCES artifacts(artifact_id)
);
