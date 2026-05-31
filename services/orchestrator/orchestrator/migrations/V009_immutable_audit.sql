-- Immutable audit log: revoke DELETE on the compliance-relevant audit tables
-- from the application role so audit records are tamper-evident.
--
-- Retention still works because prune_audit_tables() (V008) is SECURITY DEFINER
-- and runs with the table owner's privileges, not the caller's.
--
-- IMPORTANT: the migration runner connects as the application user, which is
-- usually the table owner. A role can REVOKE its own privileges, but a
-- non-superuser/non-owner cannot revoke privileges it does not control. The
-- statements are wrapped in a DO block that swallows insufficient_privilege so a
-- least-privileged migration role does not fail the boot — in that case a DBA
-- must apply the REVOKEs out of band (documented in docs/OPERATIONS_RUNBOOK.md).
--
-- current_user is used rather than a literal role name because the migration
-- file is executed verbatim (no ${POSTGRES_USER} substitution is available here).

DO $$
BEGIN
  EXECUTE format('REVOKE DELETE ON mission_audit_reports FROM %I', current_user);
  EXECUTE format('REVOKE DELETE ON agent_action_events FROM %I', current_user);
  EXECUTE format('REVOKE DELETE ON llm_usage_events FROM %I', current_user);
EXCEPTION
  WHEN insufficient_privilege THEN
    RAISE NOTICE 'prune REVOKE skipped: current role lacks privilege to revoke DELETE; apply as a superuser/owner (see OPERATIONS_RUNBOOK).';
END $$;

-- Ensure the retention function runs as its definer even if V008 was applied
-- before this clause existed.
ALTER FUNCTION prune_audit_tables(INTEGER) SECURITY DEFINER;
