# Phase 13 - Security and Compliance Agents

**Status:** Planned  
**Last updated:** 2026-05-18  
**Depends on:** Phase 10 delivery, Phase 11 AIM, Phase 12 equivalence reports

## Validated Entry State

The repo already has useful foundations:

- `AGENT-05-SECURITY` and `AGENT-08-COMPLIANCE` are registered agents with
  persona/model guidance.
- Repo-level security and compliance guidance exists in
  `docs/TESTING_QUALITY_GATES.md` and `docs/COMPLIANCE_EVIDENCE_MAPPING.md`.
- Mission Flow now persists build artifacts, `application_intelligence_map`,
  `equivalence_report`, and audit events.
- Mission Control already renders audit reports, build artifacts, AIM, and
  equivalence evidence.

The missing piece is a mission-local verdict that evaluates the specific output
before completion.

## Updated Implementation Plan

1. Add `security_compliance_report.v1`.
   - Security section: secret-like strings, dangerous imports/APIs, insecure
     patterns, missing artifact/equivalence evidence, high-risk AIM flags.
   - Compliance section: data classification, license/provenance unknowns,
     audit-evidence completeness, regulated-depth warnings.
   - Common fields: `passed`, `blocking`, `risk_level`, `findings`,
     `recommendations`, `evidence_refs`, `source`, `generated_at`.

2. Generate deterministic verdicts first.
   - Use local text/rule checks against `generated_output` and bounded metadata.
   - Do not require Bandit, pip-audit, Trivy, or gitleaks in the runtime path.
   - External scanner outputs can be consumed later as optional evidence.

3. Wire Mission Flow.
   - Run after equivalence verification and before delivery/COMPLETE.
   - Store `metadata["security_compliance_report"]`.
   - Emit one of `MISSION_SECURITY_COMPLIANCE_PASSED`,
     `MISSION_SECURITY_COMPLIANCE_WARNED`, or
     `MISSION_SECURITY_COMPLIANCE_BLOCKED`.
   - Gate COMPLETE only when enforcement is enabled or data classification/depth
     requires blocking.

4. Expose operator evidence.
   - Add chain-trace field.
   - Render a Mission Detail panel.
   - Record audit events and, where appropriate, audit reports using existing
     internal audit-report storage.

## Non-Goals

- Do not replace CI security workflows; this is mission-level evidence.
- Do not claim legal compliance certification. The report is an engineering
  verdict and evidence pointer.
- Do not require external scanners or network access to complete a mission.

## Validation

- Generated output with obvious secret-like text blocks when enforcement is on.
- Missing equivalence report warns or blocks according to policy.
- Low-risk generated output records a pass verdict.
- Chain trace exposes `security_compliance_report`.
- Mission Detail renders the report.
- Targeted pytest and Mission Control typecheck pass.
