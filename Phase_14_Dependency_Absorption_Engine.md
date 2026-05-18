# Phase 14 - Dependency Absorption Engine

**Status:** Planned  
**Last updated:** 2026-05-18  
**Depends on:** Phase 11 AIM, Phase 12 equivalence, Phase 13 security/compliance

## Validated Entry State

The dependency absorption doctrine is already canonical in
`docs/DEPENDENCY_ABSORPTION_DOCTRINE.md`, and `AGENT-39-DEPABS` exists in the
runtime registry/persona/model matrix. AIM can surface detected dependencies,
and Phase 12 creates equivalence evidence for generated output.

What does not exist yet:

- mission-local dependency inventory
- dependency classifier
- survival justification
- absorption plan/report
- SBOM delta or modified-output packaging tied to dependency decisions

## Updated Implementation Plan

1. Add inventory and classification reports.
   - `dependency_inventory.v1`
   - `dependency_classification_report.v1`
   - `dependency_absorption_report.v1`
   - `dependency_survival_justification.v1`

2. Build inventory from available evidence.
   - AIM `detected_dependencies`
   - source-bundle file manifest and lockfiles/package files when present
   - generated-output dependency lists
   - package metadata from repo/builder review artifacts when present

3. Classify before generating replacements.
   - Categories must match the doctrine: absorb, reimplement, replace, vendor,
     wrap, pin, keep, block.
   - Safety-blocked dependency families must never be auto-absorbed.
   - Platform/runtime/security dependencies default to keep/wrap/pin with
     justification.

4. Gate replacement planning.
   - First implementation may create replacement plans for small, pure, local
     utility dependencies only.
   - Actual modified output requires passing Phase 12 equivalence and Phase 13
     security/compliance checks.
   - No automatic removal of cryptography, auth, TLS, database drivers, cloud SDK
     auth/signing, hardware drivers, or regulated/proprietary dependencies.

5. Expose evidence.
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

- `REDUCE_DEPENDENCIES` mission with source/AIM dependencies creates inventory.
- Safety-blocked dependency is classified as keep/block, not absorb.
- Small pure utility dependency can receive an absorption plan.
- Chain trace exposes dependency reports.
- Mission Detail renders inventory/classification.
- Targeted pytest and Mission Control typecheck pass.
