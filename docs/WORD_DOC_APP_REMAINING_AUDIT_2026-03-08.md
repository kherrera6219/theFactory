# Word-Doc App Remaining Audit (Updated 2026-03-09 21:25)

## Scope

Audited all 15 `.docx` files (now in `docs/`) plus full codebase inspection.

## High-Level Status

Most of the former Word-doc gaps are now implemented in code and validated:

- Mission Flow v2 artifacts, chain trace persistence, and Mission Control v2 rendering are live.
- The dedicated-agent profile now resolves a full 35-agent container topology.
- Pod-worker now executes through the shared agent hierarchy rather than treating `agent_base.py`
  as a detached library.
- RefinedIR now has typed models, content-hash/Git provenance, and a build/index step.
- Orchestrator now connects to Milvus when enabled and exposes readiness for it.
- Compose/env templates now enforce Postgres `sslmode=verify-full` and Redis CA validation.
- Mission Control Vault slots now enforce TTL expiry and surface rotation warnings.
- CI now includes signed-tag verification, cosign release artifacts, weekly DORA generation,
  and SLO/per-agent latency observability.

## Remaining Items

### 1) Per-Agent API Key Isolation
- Runtime now supports canonical `AGENT_<NN>_<CODE>_SERVICE_API_KEY` variables plus
  `AGENT_SERVICE_KEY_MODE=shared|strict`.
- `pod-worker` resolves the active mission `agent_id` to a dedicated key for internal mutation
  endpoints.
- `audit-worker` now uses `WORKER_AGENT_ID` and a matching dedicated key for audit writes.
- Orchestrator accepts configured agent-scoped service keys automatically.
- Remaining gap: provisioning 35 distinct live secrets plus rotation/revocation evidence.

### 2) Enterprise Secret Operations
- Mission Control now surfaces `expires_at`, `ttl_seconds`, and `rotation_due`.
- Expired in-memory/Vault-backed secrets are blocked when TTL enforcement is on.
- Remaining gap: automated rotation workflows and broader service adoption outside Mission Control.

### 3) Live Rollout Drift
- The checked-in compose/env templates now carry the TLS and strict-mode settings.
- Existing long-running local containers may still reflect older env values until the stack is
  recreated with the updated compose inputs.
