# Word-Doc Remaining TODO (2026-03-08)

## P1 - Large / Strategic

- [ ] Implement full Mission Flow v2 11-phase runtime mode behind feature flag.
Acceptance:
  - 11-phase event schema finalized and versioned.
  - API + Mission Control render v2 phases deterministically.
  - v1.1 fallback preserved with migration and rollback path.

- [ ] Implement full 35 dedicated-agent topology profile.
Acceptance:
  - 35 dedicated services defined and health-checked.
  - PM -> CEO -> pod -> specialist routing proven in dedicated profile.
  - load and failure-recovery qualification evidence published.

## P2 - Medium

- [ ] Enforce per-agent runtime API key isolation.
Acceptance:
  - each active agent path authenticates with dedicated key material.
  - key rotation and revocation tested end-to-end.

- [x] Complete strict container hardening set from checklist.
Acceptance:
  - `cap_drop: [ALL]` baseline + minimal `cap_add` exceptions.
  - critical infra `oom_score_adj` policy applied and validated.
  - seccomp policy explicitly documented per environment.

- [x] Add compose overlay set (`dev`, `staging`, `prod`).
Acceptance:
  - `docker compose config` passes for each overlay.
  - env-specific security/runtime deltas documented.

- [x] Add model promotion governance for preview providers/models.
Acceptance:
  - explicit preview->GA promotion checklist and gate.
  - runtime defaults point to approved production model versions.

## P3 - Governance / Hygiene

- [x] Publish full legacy profile ID mapping index (legacy `*-001` -> canonical `AGENT-xx-*`).
Acceptance:
  - one canonical mapping document covers all legacy docx profile references.
  - references from docs index and onboarding docs are updated.

- [x] Automate weekly qualification cadence with release-policy threshold update logic.
Acceptance:
  - scheduled CI job produces evidence snapshots weekly.
  - release policy consumes consecutive-pass thresholds for promotion criteria.
