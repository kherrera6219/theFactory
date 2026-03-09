# Word-Doc App Remaining Audit (Updated 2026-03-08 10:49)

## Scope

Audited all 15 `.docx` files (now in `docs/`) plus full codebase inspection.

## High-Level Status

The major runtime gap is now narrower than the earlier Word-doc audit:

- Mission Flow v2 no longer behaves as a placeholder-only sequence. It now records CEO delegation,
  pod-manager assignment, specialist assignment, and specialist planning artifacts in the runtime.
- Mission Control now renders route provenance and stage artifacts for live missions.
- Weekly qualification and promotion gating now include live mission-artifact evidence.
- Release trust now includes cosign signing and verification for the release manifest and SBOM.
- Mission Control secret storage now supports a HashiCorp Vault KV backend with memory fallback.

## Remaining Items

### 1) Full 35 Dedicated-Agent Container Topology
- Compose uses condensed pod workers, not 35 dedicated containers.
- Strategic decision: full topology vs. condensed workers.

### 2) Mission Flow v2 API/UI Phase Rendering
- Runtime enforcement is now present, but API responses still expose the legacy state shape by default.
- Mission Control stepper still follows the Smelt-cycle/v1.1 mapping rather than full 11-phase v2 labels.

### 3) Agent Hierarchy Wiring into Pod-Worker
- `agent_base.py` is standalone. Not yet called in pod-worker mission processing.

### 4) Per-Agent API Key Isolation
- Runtime now supports canonical `AGENT_<NN>_<CODE>_SERVICE_API_KEY` variables plus
  `AGENT_SERVICE_KEY_MODE=shared|strict`.
- `pod-worker` resolves the active mission `agent_id` to a dedicated key for internal mutation
  endpoints.
- `audit-worker` now uses `WORKER_AGENT_ID` and a matching dedicated key for audit writes.
- Orchestrator accepts configured agent-scoped service keys automatically.
- Remaining gap: key rotation/revocation evidence and full 35-container isolation.

### 5) Strict RefinedIR Pipeline (4 sub-items)
- No typed `RefinedIR` Pydantic model, Git-backed store, or build step.

### 6) Milvus Client (1 item)
- Compose image available under `extended-data-plane` profile. No service code connects.

### 7) TLS Hardening
- Postgres `sslmode=verify-full` is still open.
- Redis runtime clients now use `ssl_cert_reqs=required` with CA validation in compose.

### 8) Vault / Secret Management
- HashiCorp Vault KV integration now exists in Mission Control.
- Rotation / TTL enforcement and wider service adoption remain open.

### 9) SLSA / Release Attestation
- Cosign signing and verification now cover the release manifest and SBOM blobs in CI.
- Signed tags / broader provenance coverage remain open.

### 10) Observability
- Synthetic canary and route/artifact qualification are in place.
- SLO burn alerts, DORA metrics, and broader per-agent-ID histograms remain open.
