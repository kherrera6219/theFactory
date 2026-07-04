# Application Intelligence Map

Document version: 2026.04.25
Last updated: 2026-04-25
Status: Canonical (Forward-Looking — Phase 2)
Audience: Operators, mission designers, agent developers, integrators

This document describes the Application Intelligence Map (AIM) — the comprehensive read-only analysis artifact theFactory produces before changing, reducing dependencies, porting, or running a target application.

## Table of Contents

- [Purpose](#purpose)
- [Doctrine](#doctrine)
- [When the AIM Is Produced](#when-the-aim-is-produced)
- [What the AIM Contains](#what-the-aim-contains)
- [Schema Reference](#schema-reference)
- [Mission Control Display](#mission-control-display)
- [Recommended Missions Output](#recommended-missions-output)
- [How Other Phases Consume the AIM](#how-other-phases-consume-the-aim)
- [Read-Only Guarantees](#read-only-guarantees)

---

## Purpose

Before theFactory changes any code, it must understand the target application. The Application Intelligence Map is the single comprehensive artifact that captures everything the factory needs to know about a target repository before any subsequent phase begins.

The AIM is generated once per mission at the start of analysis. All downstream phases — dependency analysis, absorption planning, patch planning, test environment provisioning, runtime QC, transformation planning — consume it as their primary input.

## Doctrine

**Understand before you change.**

A mission that modifies a repository without producing an Application Intelligence Map is not a valid theFactory mission. The AIM is the contract between the factory and the operator: this is what the factory believes the application is, before any work begins.

Operators must approve the AIM in Production and Regulated depth modes before subsequent phases proceed.

## When the AIM Is Produced

The AIM is produced in Phase 2 of the mission lifecycle, immediately after intake and charter approval. It runs entirely read-only — the factory makes no modifications during AIM generation.

Mission types that always produce an AIM:

- Import and modernize an existing repo
- Port an application
- Debug or repair a repo
- Security harden a repo
- Reduce dependencies and code bloat
- Run and QC a built app
- Generate architecture and documentation only
- Analyze only

The "build a new application from scratch" mission produces a related but different artifact: a target architecture plan rather than an AIM of an existing source.

## What the AIM Contains

### Repository

- Name, size, language mix, frameworks
- Package managers and lock files
- Build system
- Deployment model
- Data classification assessment (Tier 0–3, see [`SENSITIVE_CODE_HANDLING_POLICY.md`](SENSITIVE_CODE_HANDLING_POLICY.md))

### Architecture

- Entry points (main, server start, CLI commands)
- Modules and component layout
- API routes (REST, GraphQL, gRPC)
- UI routes
- Database schemas
- Authentication and session model
- Background jobs and scheduled tasks
- External integrations
- Event bus and message broker usage

### Runtime Needs

- Databases (Postgres, MySQL, MongoDB, etc.)
- Caches (Redis, Memcached)
- Queues (RabbitMQ, Kafka, SQS)
- Object storage (S3, MinIO)
- Vector databases (Qdrant, Milvus, Pinecone)
- Graph databases (Neo4j)
- Required environment variables
- Required secrets
- Local services required for development

### Migration Framework

- Detected framework (Alembic, Prisma, Flyway, Liquibase, Django, Rails, raw SQL, TypeORM, Knex, unknown)
- Migration paths (directories or files)
- Migration command (the actual run command)
- Migration runner confidence score

### Dependency Surface

- Direct dependencies
- Transitive dependencies
- Unused dependencies
- Vulnerable dependencies (CVE list)
- Abandoned dependencies (no recent maintainer activity)
- License-risk dependencies
- Lightly-used dependencies
- Likely-absorbable dependencies

### Quality

- Test coverage
- Broken tests
- Lint and type-check status
- Dependency risks summary
- Security findings summary
- Documentation gaps
- API contract coverage

### Portability

- OS-specific assumptions
- Hardcoded paths
- Native dependencies
- Runtime assumptions
- Packaging constraints

### Compliance Signals

- PII handling detection
- Payment processing detection
- Authentication patterns detection
- Risk of sensitive-data logging
- Regulated data indicators (HIPAA, PCI, CUI hints)

### Recommended Missions

The AIM concludes with recommended next missions based on detected risk and opportunity:

- Security hardening
- Dependency absorption
- Code bloat reduction
- Runtime QC
- Test repair
- Platform port
- Architecture refactor
- Documentation generation
- API contract testing

## Schema Reference

The AIM is a plain dict produced by `generate_aim()`/`_extract_all_languages()` in `aim_generator.py` (`"schema_version": "aim.v1"`) — there is currently no standalone JSON Schema file for it under `schemas/` (unlike LogicNodes, RIR modules, and mission charters, which do have dedicated schema files; see [`SCHEMA_REGISTRY_AND_VERSIONING.md`](SCHEMA_REGISTRY_AND_VERSIONING.md) for what's actually registered). The field shape is defined by the dict keys `aim_generator.py` itself constructs and consumes; unknown fields are tolerated by consumers (forward-compatibility).

## Mission Control Display

In Mission Control, the AIM appears as a dedicated panel after analysis completes. Example layout:

```
Application Intelligence
───────────────────────────────────────────────────
Primary Language:        Python
Secondary Language:      TypeScript
Frameworks:              FastAPI, Next.js
Runtime Services:        PostgreSQL, Redis
Migration Framework:     Alembic (high confidence)
Data Classification:     Tier 1 — Internal
───────────────────────────────────────────────────
Dependency Risk:         High
Absorbable Dependencies: 11
Transitive Removable:    47
Vulnerable Dependencies: 4
License-Risk Deps:       1
───────────────────────────────────────────────────
Repo Risk:               Medium
Security Risk:           High
Portability Risk:        Low
Test Health:             Partial
Compliance Signals:      Auth patterns detected
───────────────────────────────────────────────────
Recommended Path:        Security hardening →
                         Dependency reduction →
                         Runtime QC
```

The operator approves the AIM (Gate 2) before subsequent phases proceed in Production and Regulated depth modes.

## Recommended Missions Output

The AIM produces a prioritized list of recommended missions. Each recommendation includes:

- Mission type (from the mission mode list)
- Predicted depth mode
- Estimated agents required
- Expected duration class (sprint / standard / production)
- Expected impact (security risk reduction, dependency reduction, etc.)

The operator may accept, decline, or modify recommendations. Accepted recommendations become the next set of mission charters.

## How Other Phases Consume the AIM

| Phase | Consumes |
|---|---|
| Dependency Intelligence | Dependency surface, license signals, vulnerability list |
| Dependency Absorption | Dependency surface, framework detection, target language |
| Refined IR Expansion | Architecture map, entry points, module layout |
| Patch Planning | API contract surface, files affected, risk assessment |
| Workspace Isolation | Source-tree layout, build system, package managers |
| Ephemeral Test Environments | Runtime needs, migration framework, env vars and secrets |
| Runtime QC | Entry points, UI routes, expected flows, accessibility hints |
| Audit Evidence Bundle | All AIM fields included as the analysis baseline |

The AIM is the upstream source for all of these. If a downstream phase needs information not in the AIM, that information is added to the AIM schema, not fetched separately.

## Read-Only Guarantees

The AIM generation phase is strictly read-only. The factory:

- Does not modify any file in the target repository
- Does not install dependencies in the operator's environment
- Does not execute the target application
- Does not call external services on the application's behalf
- Does not write to any database used by the target application

Read-only is enforced by isolating AIM generation in a workspace that mounts the source as read-only and provides only analysis tooling. Any phase that needs to execute, install, or modify is a downstream phase with its own approval gate.
