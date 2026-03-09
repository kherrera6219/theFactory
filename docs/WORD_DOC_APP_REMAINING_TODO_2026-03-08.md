# Word-Doc Remaining TODO (Updated 2026-03-08)

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

## P1 — Large / Strategic (Still Open)

- [ ] Implement full 35 dedicated-agent container topology profile.
  Acceptance:
  - 35 dedicated services defined and health-checked.
  - PM -> CEO -> pod -> specialist routing proven in dedicated profile.
  - Load and failure-recovery qualification evidence published.

- [ ] Wire agent hierarchy into pod-worker mission processing.
  Acceptance:
  - `make_agent()` factory called in pod-worker lifecycle
  - Agent execute/validate/report lifecycle proven end-to-end

- [ ] Update API + Mission Control to render v2 phases.
  Acceptance:
  - API returns v2 state values when v2 is enabled (with v1.1 compat mapping)
  - Mission Control stepper renders 11 v2 phases

## P2 — Medium (Still Open)

- [ ] Enforce per-agent runtime API key isolation.
  Acceptance:
  - Each active agent path authenticates with dedicated key material.
  - Key rotation and revocation tested end-to-end.
  Progress:
  - Runtime now supports canonical `AGENT_<NN>_<CODE>_SERVICE_API_KEY` variables.
  - `pod-worker` resolves agent-scoped keys per mission path; `audit-worker` resolves by `WORKER_AGENT_ID`.
  - Orchestrator now accepts configured agent-scoped service keys automatically.
  - `deploy/docker-compose.prod.yaml` now sets worker services to `AGENT_SERVICE_KEY_MODE=strict`.
  Remaining:
  - Rotation and revocation evidence is still missing.
  - Full 35-agent dedicated topology still needs to consume these keys in isolated containers.

- [ ] Implement strict `RefinedIR` Pydantic model + pipeline.
  - Typed extraction output instead of raw dicts.
  - Git-backed LogicNode content-addressed store.
  - Formal `RefinedIR → binary` compilation step.

- [ ] Wire Milvus Python client in at least one service.
  - Connect to compose `milvus` service from orchestrator or pod-worker.
  - Collection schema, health probe, and basic similarity search.

## P3 — Infrastructure / Security (Still Open)

- [ ] Postgres `sslmode=verify-full` on all connection strings.
- [x] Redis TLS cert validation (`ssl_cert_reqs=required`) across runtime clients.
- [ ] Dynamic secret rotation / TTL enforcement on top of the new Vault backend.
- [ ] Signed tags / release provenance expansion beyond current cosign blob signing.
- [ ] SLO error-budget burn alerts + DORA metrics.
- [ ] Broaden per-agent-ID Prometheus histograms beyond pod-worker runtime metrics.
