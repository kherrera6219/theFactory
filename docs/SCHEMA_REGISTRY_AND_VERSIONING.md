# Schema Registry and Versioning

Document version: 2026.07.03
Last updated: 2026-07-03
Status: Canonical (Governance)
Audience: Service developers, agent developers, schema authors, integrators

This document defines how theFactory manages the lifecycle of JSON schemas: how they are stored, referenced, versioned, evolved, and retired. It applies to event envelopes, mission artifacts, IR node types, audit records, and any other structured data exchanged between services.

## Table of Contents

- [Why Governance Matters](#why-governance-matters)
- [Schema Registry Layout](#schema-registry-layout)
- [Schema Naming Convention](#schema-naming-convention)
- [Versioning Rules](#versioning-rules)
- [Backward and Forward Compatibility](#backward-and-forward-compatibility)
- [Authoring a New Schema](#authoring-a-new-schema)
- [Evolving an Existing Schema](#evolving-an-existing-schema)
- [Deprecation and Retirement](#deprecation-and-retirement)
- [Validation and CI Gates](#validation-and-ci-gates)
- [Standards Basis](#standards-basis)

---

## Why Governance Matters

Schemas are the contracts between services. theFactory has multiple long-running services (api-gateway, orchestrator, pod-worker, audit-worker, protocol-bus-mcp, mission-control) that exchange structured messages. Without governance:

- Producers add fields and break consumers
- Consumers reject unknown fields and break producers
- Old artifacts in the audit ledger become unreadable
- Migration paths to new versions become impossible
- Plugins and integrations cannot rely on stable contracts

This document is the rulebook that prevents those failure modes.

## Schema Registry Layout

All schemas live in `/schemas/` at the repository root.

```
schemas/
  event.envelope.schema.json
  logicnode.schema.json
  mission_charter.v1.json
  mission_charter.v1.schema.json
  rir.fn.schema.json
  rir.module.schema.json
```

This is the current, actual contents of `/schemas/` as of 2026-07-03 — a prior version of this list included ~20 additional schema files (AIM, dependency-absorption, RIR concept nodes, workspace/patch/test-environment manifests, approval records, evidence bundles) that were never implemented. Several of those artifacts exist as plain dicts with a `schema_version` string key instead of a registered JSON Schema file (e.g. the Application Intelligence Map — see `APPLICATION_INTELLIGENCE_MAP.md`'s "Schema Reference" section). If one of those artifact types needs a real JSON Schema in the future, add it here and follow the naming convention below; don't assume the file already exists based on an older version of this document.

Schemas in `docs/archive/` are historical reference only. They are not consumed at runtime.

## Schema Naming Convention

Every schema file follows the pattern:

```
{snake_case_name}.{version}.schema.json
```

or, for the legacy event-envelope-style files already in the repo:

```
{snake_case_name}.schema.json   (versioned via the schema_version field within)
```

The `version` segment in the filename is `v1`, `v2`, etc. — major-version only. Minor changes within a major version do not change the filename.

## Versioning Rules

theFactory schemas use **semantic versioning constrained to the major version in the filename**:

- **`v1` to `v1` (in-place):** Backward-compatible additions. New optional fields. New enum values that consumers tolerate. Field documentation updates.
- **`v1` to `v2` (new file):** Breaking changes. Renamed fields, removed fields, type changes, required-field additions, semantic changes.

A `schema_version` field within each instance records the specific minor version. Producers stamp it; consumers may inspect it but must not reject based on it (forward compatibility).

| Change Type | Action |
|---|---|
| Add an optional field | In-place edit |
| Add a required field | New version (`v2`) |
| Remove a field | New version (`v2`) |
| Rename a field | New version (`v2`) |
| Change a field's type | New version (`v2`) |
| Add a new enum value | In-place edit |
| Remove an enum value | New version (`v2`) |
| Tighten a regex pattern | New version (`v2`) |
| Loosen a regex pattern | In-place edit |
| Add documentation | In-place edit |

## Backward and Forward Compatibility

**Producer rules:**

- Producers always emit the latest minor version they support
- Producers stamp `schema_version` (or equivalent identifier) on every emitted instance
- Producers MUST NOT remove fields without bumping the major version
- Producers MUST NOT change field types without bumping the major version

**Consumer rules:**

- Consumers MUST tolerate unknown fields (forward compatibility)
- Consumers MUST NOT reject instances that contain extra fields not in the consumer's schema view
- Consumers SHOULD log a warning when they encounter `schema_version` greater than what they understand
- Consumers MAY validate against the major-version schema they were built against
- Consumers MUST handle both `v1` and `v2` of a schema during a migration window (typically 90 days)

**Validation:**

- Strict validation is performed only at trust boundaries (api-gateway intake, builder review)
- Internal consumers use lenient validation that accepts unknown fields
- Test fixtures cover both strict and lenient paths

## Authoring a New Schema

When adding a new schema:

1. Create the file under `/schemas/{name}.v1.schema.json`
2. Use JSON Schema Draft 2020-12 (`"$schema": "https://json-schema.org/draft/2020-12/schema"`)
3. Include a `$id` URI for the schema (used by event envelopes for reference)
4. Include `title`, `description`, `type`, and `properties`
5. Mark required fields explicitly via `required`
6. Include a `schema_version` property (string, semver-like)
7. Add example instances under `examples`
8. Run `scripts/validate_schemas.py` to confirm structural validity
9. Add a test fixture under `tests/fixtures/schemas/{name}/`
10. Register in `DOCUMENTATION_INDEX.md` if it has operator-facing documentation
11. Open a PR with the schema and at least one consumer or producer reference

CI gates (see below) block merges that introduce structurally invalid schemas or that add a new schema without a fixture.

## Evolving an Existing Schema

For backward-compatible (in-place) changes:

1. Edit the schema file directly
2. Bump the `schema_version` minor version in the schema's metadata
3. Update fixtures to demonstrate the new fields
4. Update consumer code if it should opt into new fields
5. PR review confirms the change is non-breaking

For breaking changes:

1. Create a new file `{name}.v2.schema.json`
2. Keep `{name}.v1.schema.json` in place during the migration window
3. Update producers to dual-emit during migration if downstream consumers haven't migrated
4. Mark `v1` as deprecated in `DOCUMENTATION_INDEX.md`
5. Migrate consumers one at a time with feature flags if needed
6. Once all consumers are on `v2`, remove `v1` after the migration window closes

## Deprecation and Retirement

A schema version is deprecated for one full release cycle (typically 90 days, minimum 30 days) before retirement.

**Deprecation announcement:**

- Update the schema file to add a `"deprecated": true` flag at the top level
- Add a deprecation notice to `DOCUMENTATION_INDEX.md`
- Emit a deprecation warning in producers and consumers
- Open a tracking issue for migration progress

**Retirement (removal):**

- Confirm zero producers and zero consumers reference the deprecated version
- Confirm no active artifacts in the audit ledger reference the deprecated version (or migrate them)
- Move the deprecated schema to `docs/archive/schemas/`
- Update `DOCUMENTATION_INDEX.md`
- Add a CHANGELOG entry

## Validation and CI Gates

The following gates run in CI for every PR that touches `/schemas/` or any code that references schemas:

| Gate | Purpose |
|---|---|
| `scripts/validate_schemas.py` | Structural validity of every schema |
| Fixture round-trip | Each schema has a fixture; the fixture validates against the schema |
| Producer reference check | Every schema is referenced by at least one producer |
| Consumer reference check | Every schema is referenced by at least one consumer |
| Backward-compatibility check | An in-place edit does not introduce breaking changes |
| Documentation check | Schemas with operator-facing semantics appear in `DOCUMENTATION_INDEX.md` |

The `validate_documentation.py` script catches drift between `/schemas/` and the documentation index.

## Standards Basis

theFactory's schema governance follows these external references:

- **JSON Schema Draft 2020-12** — the schema dialect
- **Semantic Versioning 2.0.0** — versioning rules
- **AsyncAPI 2.6** — for documenting event-bus topology and message bindings
- **OpenAPI 3.1** — for documenting REST API contracts (which embed schema fragments)
- **Confluent Schema Registry compatibility patterns** — backward and forward compatibility definitions

These references are listed for traceability and should be cited in ADRs that propose schema-related changes.
