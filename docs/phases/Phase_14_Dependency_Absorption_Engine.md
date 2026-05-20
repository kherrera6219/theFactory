# Phase 14 - Dependency Absorption Engine

**Status:** Implemented
**Last updated:** 2026-05-18  
**Depends on:** Phase 11 AIM, Phase 12 equivalence, Phase 13 security/compliance

## Validated Entry State

The dependency absorption doctrine is already canonical in
`docs/DEPENDENCY_ABSORPTION_DOCTRINE.md`, and `AGENT-39-DEPABS` exists in the
runtime registry/persona/model matrix. AIM can surface detected dependencies,
and Phase 12 creates equivalence evidence for generated output.

Implemented in this phase:

- mission-local dependency inventory
- deterministic dependency classifier
- survival justification metadata
- advisory absorption report and small-utility replacement plans
- chain-trace/API exposure and Mission Control rendering

Still intentionally not implemented:

- SBOM delta or modified-output packaging tied to dependency decisions
- broad automatic dependency removal
- runtime call-site rewrite or dependency deletion

## Implemented Behavior

1. Added inventory and classification reports.
   - `dependency_inventory.v1`
   - `dependency_classification_report.v1`
   - `dependency_absorption_report.v1`
   - `dependency_survival_justification.v1`

2. Inventory is built from available evidence.
   - AIM `detected_dependencies`
   - source-bundle file manifest and lockfiles/package files when present
   - generated-output dependency lists
   - package metadata from repo/builder review artifacts when present

3. Classification runs before any replacement planning.
   - Categories must match the doctrine: absorb, reimplement, replace, vendor,
     wrap, pin, keep, block.
   - Safety-blocked dependency families must never be auto-absorbed.
   - Platform/runtime/security dependencies default to keep/wrap/pin with
     justification.

4. Replacement planning is gated.
   - First implementation may create replacement plans for small, pure, local
     utility dependencies only.
   - Actual modified output requires passing Phase 12 equivalence and Phase 13
     security/compliance checks.
   - No automatic removal of cryptography, auth, TLS, database drivers, cloud SDK
     auth/signing, hardware drivers, or regulated/proprietary dependencies.

5. Evidence is exposed.
   - Store reports in metadata.
   - Emit `MISSION_DEPENDENCY_INVENTORY_CREATED`,
     `MISSION_DEPENDENCY_CLASSIFIED`, and when applicable
     `MISSION_DEPENDENCY_ABSORPTION_PLANNED`.
   - Render dependency inventory/classification in Mission Control.

## Non-Goals

- Do not implement broad automatic dependency removal in the first Phase 14
  slice.
- Do not produce SBOM deltas without concrete before/after artifact evidence.
- Do not call a dependency absorbed without equivalence and security/compliance
  evidence.

## Validation

- [x] `REDUCE_DEPENDENCIES`/source/AIM dependency evidence creates inventory.
- [x] Safety-blocked dependency is classified as keep/wrap/pin/block, not absorb.
- [x] Small pure utility dependency can receive an advisory absorption plan.
- [x] Chain trace exposes dependency reports.
- [x] Mission Detail renders inventory/classification.
- [x] Targeted pytest, ruff, Mission Control lint, and Mission Control unit tests pass.
