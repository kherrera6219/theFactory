# Documentation Standards

Document version: 2026.03.29  
Last updated: 2026-03-29  
Status: Canonical  
Audience: Operators, developers, maintainers, and auditors

This document defines the documentation standard for theFactory. It is the source of truth for how repository documentation is structured, versioned, reviewed, archived, and kept aligned with the live application.

## Standards Basis

The documentation system follows these primary external references:

- Diataxis: organize docs by user need into tutorials, how-to guides, reference, and explanation.
- Google developer documentation style: prefer timeless, prescriptive, globally readable documentation with clear voice and tone.
- Microsoft Writing Style Guide: use active voice, task-first structure, plain language, and scannable headings/lists.
- Write the Docs guide: treat documentation as code, maintain style guidance, and make contribution/update workflows explicit.
- C4 model: standardize architecture visuals using system context, container, component, deployment, and dynamic views.
- OpenAPI 3.1: make API reference documentation contract-driven rather than prose-only.
- WCAG 2.2: ensure user-facing documentation and examples support accessibility requirements.
- NIST SSDF and OWASP ASVS: keep operational, security, and release documentation tied to verified engineering controls.

## Documentation Model

theFactory uses a Diataxis-aligned information architecture:

- Explanation:
  - architecture, diagrams, data flows, standards, roadmap, release posture
- Reference:
  - API documentation, OpenAPI exports, repository build map, environment variable references
- How-to:
  - operations runbooks, deployment/recovery procedures, contributor workflows, testing guides
- Tutorial / getting started:
  - operator onboarding and first-success user instructions

## Canonical Folder Layout

- `README.md`
  - product entry point and high-level orientation
- `docs/DOCUMENTATION_INDEX.md`
  - master documentation map
- `docs/user/`
  - tutorials and operator-facing getting-started material
- `docs/api/` and `docs/openapi/`
  - API reference and machine-readable contracts
- `docs/runbooks/`
  - operational procedures and incident guides
- `docs/evidence/`
  - test, audit, and release qualification evidence
- `docs/archive/`
  - superseded historical material retained for traceability

## Required Metadata for Canonical Docs

Every canonical markdown document must include, near the top of the file:

- document title
- document version
- last updated date
- status
- primary audience

Recommended optional metadata:

- owner or owning team
- review cadence
- source-of-truth statement if the document summarizes generated/runtime-derived state

## Scope and Exceptions

- The full metadata header is required for the current-source documentation set under `docs/`, excluding explicitly historical or generated material.
- Root repository documents such as `README.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, `SECURITY.md`, and `CODE_OF_CONDUCT.md` follow repository-convention formatting rather than the canonical docs header.
- ADRs under `docs/ADR_*.md`, evidence notes under `docs/evidence/`, archive contents under `docs/archive/`, and generated repository maps under `docs/REPOSITORY_BUILD_MAP_*.md` may use simplified historical or generated metadata.
- When a document is intentionally historical but still kept in the live docs tree, mark `Status` clearly as `Reference` or `Historical reference`.

## Writing Rules

- Prefer active voice and imperative phrasing for tasks.
- Prefer present tense for current behavior and explicit dates for changed behavior.
- Avoid vague future-language unless a roadmap section explicitly marks it as planned.
- Use short sections, flat bullet lists, and copy-pasteable commands.
- Label examples clearly and ensure commands match the current codebase and configuration.
- Treat the reader as a global technical audience: avoid slang, culture-specific idioms, and unnecessary jargon.
- Use inclusive, neutral language.
- Do not document features that do not exist in the codebase or validated runtime.

## Diagram Requirements

The canonical diagram set for a production application must include:

- system context diagram
- container diagram
- deployment diagram
- dynamic/runtime sequence diagram
- trust-boundary or identity/access diagram
- data-flow diagrams for critical paths

For theFactory, the minimum current diagram set is:

- `ARCHITECTURE_DIAGRAMS.md`
- `ARCHITECTURE_DATA_FLOWS.md`

## Versioning Rules

- Canonical docs use stable filenames whenever the document is intended to be the current source of truth.
- Historical snapshots, audit outputs, and point-in-time evidence may keep date-stamped filenames.
- Doc versions use `YYYY.MM.DD` format unless a more formal release version exists for the product.
- Material superseded by a canonical stable document must be moved to `docs/archive/` instead of remaining mixed into the live documentation root.

## Review and Update Rules

- Code changes that alter behavior, APIs, runtime topology, configuration, or operator workflows must update the relevant docs in the same change set.
- New commands and environment variables must be reflected in `README.md`, relevant runbooks, and onboarding docs.
- Generated artifacts such as the repository build map must be regenerated when the documented tree materially changes.
- Validation results and documentation claims must be tied to evidence under `docs/evidence/` when they affect release readiness.

## Archive Policy

Move documentation into `docs/archive/` when any of the following are true:

- the document is superseded by a canonical stable document
- it is a dated audit, todo list, wireframe log, or temporary planning artifact no longer used as the live source of truth
- it is imported source material such as `.docx`, raw notes, or legacy specification bundles

Archive moves must preserve:

- original filename
- original date where present
- enough path context to understand where the file came from

## Validation Workflow

Validate the current-source documentation set before merge:

```powershell
python scripts/validate_documentation.py
```

Regenerate the repository map when the tree changes:

```powershell
python scripts/generate_build_map.py
```

## Documentation Quality Gate

Before considering a documentation update complete, verify:

- links resolve within the repo
- commands are runnable against the current codebase
- screenshots or diagrams match the current application state
- API docs align with the current OpenAPI exports
- the document appears in `DOCUMENTATION_INDEX.md`
