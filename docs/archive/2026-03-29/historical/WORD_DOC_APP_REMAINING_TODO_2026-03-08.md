# Word-Doc Remaining TODO (Updated 2026-03-09)

> Historical note (2026-03-29): This document predates the current 38-agent runtime. Treat any `35-agent` references below as historical planning terminology unless explicitly updated in a newer canonical document.

## ✅ Recently Completed

- [x] Implement full Mission Flow v2 11-phase runtime engine behind feature flag.
  - `mission_flow_v2.py`: V2_TRANSITIONS, v2_map_state_to_v1(), advance_mission_lifecycle_v2()
  - Feature-flagged via `MISSION_FLOW_V2_ENABLED` (default false)
  - Both legacy and LangGraph paths updated
  - 41 unit tests passing
- [x] Enforce PM -> CEO -> pod-manager -> specialist delegation artifacts inside Mission Flow v2.
  - Runtime now persists CEO delegation, pod-manager assignment, specialist assignment, and specialist plan.
  - `MISSION_SPECIALIST_PLANNED` is emitted before execution and recorded in mission artifacts.
  - Live `mission_artifact_qualification.py` passed against the running stack.
- [x] Add Mission Control route-provenance panel and artifact trace rendering.
  - `/missions/[id]` now renders model/provider/route decisions plus recorded stage artifacts.
- [x] Extend qualification gating with mission-artifact/chain-of-command evidence.
  - Weekly qualification now runs `mission_artifact_qualification.py`.
  - Promotion threshold summary now includes mission artifact evidence.
- [x] Add cosign-based signing and verification for release manifest and SBOM blobs in CI.
- [x] Add Mission Control HashiCorp Vault KV backend option with memory fallback.
  - `vault.ts` supports `VAULT_TOKEN` or AppRole login.
  - Existing `/api/vault*` routes preserved.

- [x] Implement Agent class hierarchy (BaseAgent with execute/validate/report).
  - `agent_base.py`: BaseAgent ABC, 5 category subclasses, 16 specialist subclasses
  - Factory functions: make_agent(), make_specialist_for_language()
  - 85 unit tests passing

- [x] Complete strict container hardening set from checklist.
- [x] Add compose overlay set (`dev`, `staging`, `prod`).
- [x] Add model promotion governance for preview providers/models.
- [x] Publish full legacy profile ID mapping index.
- [x] Automate weekly qualification cadence.
- [x] Move all Word documents to `docs/` folder.
- [x] Implement full 35 dedicated-agent container topology profile.
  - `deploy/docker-compose.full-dedicated-agents.yaml` defines the dedicated runtime profile.
  - `make dedicated-full-up`, `make dedicated-full-down`, and `make dedicated-full-config` added.
  - Compose validation now proves the full 35-agent topology resolves cleanly.
- [x] Wire agent hierarchy into pod-worker mission processing.
  - `pod-worker` now calls the shared `make_agent()` / `make_specialist_for_language()` factory flow.
  - Agent execute/validate/report lifecycle is covered by unit tests.
- [x] Update API + Mission Control to render Mission Flow v2 phases.
  - Mission payloads now expose v2 phase labeling.
  - Mission Control stepper and mission detail views are v2-aware.
- [x] Implement strict `RefinedIR` typed pipeline baseline.
  - `services/pod-worker/pod_worker/refined_ir.py` adds typed Pydantic models.
  - RefinedIR writes now emit content hashes plus best-effort Git commit provenance.
  - `scripts/build_refined_ir_catalog.py` validates stored modules and builds an index.
- [x] Wire Milvus Python client into orchestrator knowledge-path handling.
  - `services/orchestrator/orchestrator/milvus_store.py` provisions the collection, upserts records, and queries mission-scoped knowledge.
  - Orchestrator health/ready/operations payloads now expose `milvus_ready` when enabled.
- [x] Enforce Postgres `sslmode=verify-full` in compose/env templates.
  - Compose now mounts Postgres CA/server cert material and injects `sslrootcert=/run/postgres-certs/ca.crt`.
- [x] Enforce Vault TTL / rotation visibility.
  - Mission Control Vault slots now track `expires_at`, `ttl_seconds`, and `rotation_due`.
  - Expired secrets are blocked when `VAULT_ENFORCE_SLOT_TTL` is enabled.
- [x] Expand signed-tag / release provenance controls.
  - CI now verifies signed `v*` tags, signs release artifacts with cosign, and evaluates promotion policy with signed-tag evidence.
- [x] Add SLO burn alerts, DORA metrics generation, and broader per-agent histograms.
  - Alerting covers fast/slow error-budget burn and per-agent p99 latency.
  - Weekly qualification now generates `docs/evidence/dora_metrics_latest.json`.
  - Metrics now include per-agent histograms for pod-worker, audit-worker, and dedicated agent-runtime.

## Remaining Open Work

- [ ] Enforce per-agent runtime API key isolation.
  Acceptance:
  - Each active agent path authenticates with dedicated key material.
  - Key rotation and revocation tested end-to-end.
  Progress:
  - Runtime now supports canonical `AGENT_<NN>_<CODE>_SERVICE_API_KEY` variables.
  - `pod-worker` resolves agent-scoped keys per mission path; `audit-worker` resolves by `WORKER_AGENT_ID`.
  - Orchestrator now accepts configured agent-scoped service keys automatically.
  - `deploy/docker-compose.prod.yaml` now sets worker services to `AGENT_SERVICE_KEY_MODE=strict`.
  - `deploy/docker-compose.full-dedicated-agents.yaml` now binds dedicated pod managers and specialists
    to their own agent-scoped keys.
  - Local key provisioning now exists via `python scripts/generate_agent_service_keys.py`.
  - Live strict dedicated qualification passed on 2026-03-09 with non-zero pod assignment and LogicNode evidence.
  - Dedicated pod-worker and audit-worker consumers now self-heal their Redis stream groups after Redis restarts.
  Remaining:
  - Rotation and revocation evidence is still missing.
- [x] Redis TLS cert validation (`ssl_cert_reqs=required`) across runtime clients.
- [ ] Complete secret rotation / revocation automation on top of the new Vault TTL controls.
  - TTL visibility and expiry blocking are now implemented.
  - Rotation workflows and service-wide adoption are still pending.


