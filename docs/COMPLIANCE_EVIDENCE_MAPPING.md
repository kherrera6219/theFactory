# Compliance Evidence Mapping

Document version: 2026.07.03  
Last updated: 2026-07-03
Status: Canonical  
Audience: Maintainers, auditors, and compliance reviewers

This mapping links production controls to machine-checkable and document evidence for SOC 2 and CMMC-aligned audits.

| Control Domain | Framework | Control Intent | Evidence Artifact(s) |
| --- | --- | --- | --- |
| Access Control | SOC2 CC6 / CMMC AC | Enforce authenticated service mutation access | `services/orchestrator/orchestrator/auth.py`, `services/api-gateway/api_gateway/main.py`, `docs/ADR_SECURITY_MODEL_API_KEY_VS_OIDC_2026-03-04.md` |
| Change Management | SOC2 CC8 / CMMC CM | Require validated release promotion gates | `.github/workflows/ci.yml`, `scripts/promotion_gate.py`, `deploy/promotion-policy.json`, `docs/RELEASE_TRUST_PROMOTION_GATE.md` |
| Vulnerability Mgmt | SOC2 CC7 / CMMC RA | Run automated dependency, SAST, image, secret scans | `.github/workflows/security.yml`, `reports/`, `docs/TESTING_QUALITY_GATES.md`, `docs/RELEASE_TRUST_PROMOTION_GATE.md`, `docs/evidence/phase45_mission_control_convergence_and_final_release_qualification.md` |
| Monitoring & Logging | SOC2 CC7 / CMMC AU | Preserve operational observability and alerting | `deploy/monitoring/**`, `docs/OBSERVABILITY_STACK.md`, `docs/OPERATIONS_RUNBOOK.md` |
| Data Integrity | SOC2 CC3 / CMMC SI | Block mission completion without execution evidence | `services/orchestrator/orchestrator/runtime.py`, `services/orchestrator/orchestrator/langgraph_lifecycle.py`, mission `MISSION_COMPLETION_BLOCKED` events |
| Secure Configuration | SOC2 CC5 / CMMC SC | Harden runtime containers and service channels | `deploy/docker-compose.yaml`, `deploy/redis/redis.conf`, `deploy/redis/redis.prod.conf` |
| Development Quality | SOC2 CC1 / CMMC RM | Maintain test/coverage quality gates | `Makefile`, `pyproject.toml`, `tests/**`, `scripts/check_coverage_thresholds.py` |

Evidence artifact generation:
- Production control status: `python scripts/production_review_audit.py --json`
- Reliability evidence: `docs/evidence/reliability_qualification_baseline_2026-06-26.json` and `docs/evidence/reliability_qualification_baseline_*.json`
- CI attestation artifacts: `reports/promotion-decision*.json`
