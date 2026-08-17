# Developer Guide

Document version: 2026.08.17  
Last updated: 2026-08-17  
Status: Canonical  
Audience: Engineers and maintainers

This guide is the developer-facing starting point for working in theFactory repository. It complements [DEVELOPER_ONBOARDING_GUIDE.md](DEVELOPER_ONBOARDING_GUIDE.md) by focusing on day-to-day engineering workflow instead of first-day setup only.

## Start Here

Read these in order:

1. [../README.md](../README.md)
2. [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md)
3. [ARCHITECTURE.md](ARCHITECTURE.md)
4. [ARCHITECTURE_DATA_FLOWS.md](ARCHITECTURE_DATA_FLOWS.md)
5. [REPOSITORY_BUILD_MAP_2026-06-13.md](REPOSITORY_BUILD_MAP_2026-06-13.md)
6. [DOCUMENTATION_STANDARDS.md](DOCUMENTATION_STANDARDS.md)
7. [TESTING_QUALITY_GATES.md](TESTING_QUALITY_GATES.md)

## Core Engineering Workflow

### 1. Run the local stack

```powershell
docker compose -f deploy/docker-compose.yaml up -d
```

### 2. Validate your changes

```powershell
make test
# line ≥80%, branch ≥70%, mixed ≥80%; every critical file ≥80%
make test-ui
make test-ui-e2e
```

### 3. Regenerate and validate docs when structure changes

```powershell
python scripts/generate_build_map.py
python scripts/validate_documentation.py
```

### 4. Update evidence when release-critical behavior changes

- add or update the relevant phase or qualification note under `docs/evidence/`
- update `IMPLEMENTATION_STATUS.md` when shipped defaults or release blockers change
- update `README.md` when commands, topology, or operator-visible behavior changes

## Repository Landmarks

- `apps/mission-control/`
  - Next.js operator console
- `services/`
  - backend services and workers
- `deploy/`
  - compose stack and deployment assets
- `protocol/` and `schemas/`
  - contract and envelope definitions
- `tests/`
  - backend, security, script, and eval coverage
- `docs/`
  - canonical documentation and archive

For the full tree, use [REPOSITORY_BUILD_MAP_2026-06-13.md](REPOSITORY_BUILD_MAP_2026-06-13.md).

## Documentation Expectations

- Follow [DOCUMENTATION_STANDARDS.md](DOCUMENTATION_STANDARDS.md).
- Treat docs as part of the same change set as code.
- Archive superseded planning artifacts instead of leaving them mixed into the live docs root.
- Keep commands runnable and examples truthful to the current codebase.

## Release-Critical Areas

These changes require documentation and evidence updates before merge:

- auth or secret-handling behavior
- mission lifecycle or approval persistence behavior
- build artifact contract or completion gating
- LLM routing, prompt-safety, or eval behavior
- backup, restore, or DR procedures
- operator-facing Mission Control workflows

## Related References

- [DEVELOPER_ONBOARDING_GUIDE.md](DEVELOPER_ONBOARDING_GUIDE.md)
- [TESTING_QUALITY_GATES.md](TESTING_QUALITY_GATES.md)
- [OPERATIONS_RUNBOOK.md](OPERATIONS_RUNBOOK.md)
- [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md)
- [RELEASE_TRUST_PROMOTION_GATE.md](RELEASE_TRUST_PROMOTION_GATE.md)
- [DOCUMENTATION_INDEX.md](DOCUMENTATION_INDEX.md)
