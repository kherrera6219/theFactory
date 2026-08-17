# Runtime QC and Ephemeral Test Environments

Document version: 2026.08.17
Last updated: 2026-08-17
Status: Canonical (Forward-Looking — Phases 9 and 10)
Audience: Operators, mission designers, agent developers, security reviewers

This document describes how theFactory provisions disposable runtime environments and validates built or patched applications through automated QC sessions.

## Table of Contents

- [Doctrine](#doctrine)
- [Ephemeral Test Environments](#ephemeral-test-environments)
- [AI Runtime QC](#ai-runtime-qc)
- [Safety Defaults](#safety-defaults)
- [Prohibited by Default](#prohibited-by-default)
- [Migration Framework Dispatcher](#migration-framework-dispatcher)
- [Service Roadmap](#service-roadmap)
- [Artifacts Produced](#artifacts-produced)
- [Production Replacement Plan](#production-replacement-plan)

---

## Current Implementation Status (2026-06-18)

Runtime QC is integrated into MissionFlow V2 completion checks. `TESTDATA_AGENT_ENABLED` remains off by default; `RQCA_AGENT_ENABLED` defaults **on**. RQCA no longer requires the testdata agent to run — it uses `_LANGUAGE_RUNTIMES`. When runtime QC is skipped, the orchestrator persists a visible `runtime_qc_report` with `skipped: true`, `verdict: SKIPPED`, `execution_type: not_run`, and a reason such as `RQCA disabled` or `no generated output`. It also records `MISSION_RUNTIME_QC_SKIPPED` once so Mission Detail and event history show that QC was intentionally skipped instead of silently missing. Integration tests are generated **before** the testdata manifest so the sandbox command can be the language test runner. Python uses stdlib `unittest` (`python:3.11-slim` has no pytest). A testdata default `run_command` does not override that. A `started_only` or syntax-only sandbox run is `DRY_RUN` / `ADVISORY`, never `PASS`. Cached `started_only` PASS reports are re-assessed. RQCA probes `SANDBOX_EXECUTOR_URL` (`sandbox-runner`), not local `docker info`. A live FAIL (`mission-8db1af71`) stayed `VERIFIED` / `MISSION_RUNTIME_QC_BLOCKED` and did not COMPLETE.

Enabling full Runtime QC remains a follow-up decision for standard BUILD_NEW missions. Until then, completed missions should show either a real Runtime QC report or an explicit skipped reason.

**Enforcement default (2026-07-03, skip-honesty 2026-08-15, tests-as-QC 2026-08-17):** `rqca_enforcement_enabled` defaults to `true`. A `qc_verdict: FAIL` blocks delivery. `DRY_RUN` / `ADVISORY` / `started_only` / syntax-only never block — those mean "could not judge," not "failed." Generated tests, when present, are the sandbox command. If the agent is **off** while enforcement is on, the skip is not-ready: that pair used to deliver with a decorative flag. A local `.env` may still pin the flag `false`; that is an override, not the shipped default.

## Doctrine

**Run before you ship. Run isolated, not in production.**

A patch that compiles is not a patch that works. A test that passes is not the same as a feature that runs. theFactory validates every meaningful mission by launching the application in a disposable environment, exercising key flows, and capturing evidence.

Two systems make this possible:

1. **Ephemeral Test Environments** — disposable runtime infrastructure (databases, caches, queues) provisioned per mission and torn down on completion.
2. **AI Runtime QC** — automated browser- or emulator-based validation of the running application, performed by a specialist agent.

Together they replace the gap between "tests pass" and "the app actually works."

## Ephemeral Test Environments

### Purpose

Most non-trivial applications need backing services to run: a Postgres database, a Redis cache, an S3 bucket, sometimes more. theFactory provisions these on-demand for each mission, isolated from any production system.

### Behavior

When a mission requires runtime validation:

1. The Application Intelligence Map's `runtime_needs` and `migration_framework` fields are read
2. The Database/TestData Agent (AGENT-40-TESTDATA) generates a Docker Compose profile
3. Required services are started on isolated ports
4. Migrations are run using the detected migration framework
5. Seed data is generated (deterministic fakes, not real data)
6. Health checks verify each service is reachable
7. The application is launched against this isolated infrastructure
8. On completion, the environment is torn down (or preserved on failure for debugging)

### Manifest

The provisioned environment is described by `test_environment_manifest.v1`:

```json
{
  "schema": "test_environment_manifest.v1",
  "mission_id": "mission_uuid",
  "app_name": "customer_portal",
  "migration_framework": "alembic",
  "migration_command": "alembic upgrade head",
  "services": [
    {
      "type": "postgres",
      "name": "app_postgres_test",
      "version": "16",
      "port": 55432,
      "database": "app_test",
      "username": "test_user",
      "seed_required": true,
      "migration_paths": ["./migrations"]
    },
    {
      "type": "redis",
      "name": "app_redis_test",
      "version": "7",
      "port": 56379
    }
  ],
  "lifecycle": {
    "auto_destroy": true,
    "preserve_on_failure": true,
    "max_runtime_minutes": 120
  }
}
```

### Isolation Guarantees

- Services run on dedicated ports separate from production-shaped defaults (e.g. Postgres on 55432 rather than 5432)
- Networks are isolated to the mission's Docker Compose profile
- Volumes are scoped to the mission and destroyed on completion (unless preserve-on-failure triggers)
- Credentials are generated, never reused from production
- No cross-mission data sharing

## AI Runtime QC

### Purpose

A built application must be exercised before it is trusted. Unit tests cover code paths; runtime QC covers the actual user experience. theFactory's Runtime QC Agent (AGENT-41-RQCA) launches the application, navigates key flows, and produces evidence of what worked and what did not.

### First Implementation

The first version uses Playwright-based browser automation. It is a deliberately scoped capability, not unrestricted computer use.

### Responsibilities

- Launch the application in a sandboxed environment
- Open a browser (Chromium, Firefox, or WebKit via Playwright)
- Navigate the key flows identified in the Application Intelligence Map
- Fill forms with deterministic fake data
- Inspect console logs and capture errors
- Inspect network activity and capture failed requests
- Take screenshots at key points
- Optionally record video of the QC session
- Validate the UI against the requirements declared in the Mission Charter
- Run basic accessibility checks (WCAG 2.1 AA — color contrast, ARIA roles, keyboard navigation)
- Record broken flows with screenshots and log evidence
- Produce recommended fixes
- Recommend follow-up bug-fix missions when failures are detected

### Safe Environments

| Environment | Use |
|---|---|
| Docker container with Playwright | Default for web-app QC |
| Disposable VM | When a full OS is required |
| Dev container | Local developer-driven QC |
| Local isolated workspace | Sprint-mode quick checks |
| Mobile emulator | Future phase, not in scope today |

## Safety Defaults

The following defaults apply to every Ephemeral Test Environment and Runtime QC session:

- No production database access from any test environment
- No real customer data (use generated fakes, fixtures, or sanitized snapshots only)
- No real credentials (test environments use generated secrets)
- No real payment transactions
- No real email or SMS delivery (use mocks like MailHog)
- No production endpoints reachable from the test network
- No deployment without explicit operator approval

These defaults can be overridden only with explicit operator action recorded in an approval record.

## Prohibited by Default

Runtime QC sessions are prohibited from:

- Accessing personal files outside the mission workspace
- Browsing unrelated websites
- Using real account credentials
- Accessing production systems
- Making real purchases or payments
- Sending real emails or SMS messages
- Deploying anything

The Runtime QC sandbox is configured to allow only:

- The application under test (local URL)
- Local services in the ephemeral environment
- Mock services within the same Docker network

## Migration Framework Dispatcher

When the test environment provisions a database that requires migrations, the dispatcher selects the correct runner based on the framework detected in the AIM.

| Detected Framework | Runner Command |
|---|---|
| Alembic | `alembic upgrade head` |
| Prisma | `npx prisma migrate deploy` |
| Django | `python manage.py migrate` |
| Rails ActiveRecord | `bundle exec rails db:migrate` |
| Flyway | `flyway migrate` |
| Liquibase | `liquibase update` |
| TypeORM | `npm run typeorm migration:run` |
| Knex | `npx knex migrate:latest` |
| Raw SQL | Apply files in sorted order |
| Unknown | Pause and request operator input |

The dispatcher refuses to proceed when the migration framework cannot be confidently detected. This protects against running incorrect migrations or skipping required setup steps.

## Service Roadmap

The Ephemeral Test Environment Manager supports services in this priority order:

| Priority | Service |
|---|---|
| P0 | PostgreSQL |
| P0 | SQLite |
| P0 | Redis |
| P1 | MySQL / MariaDB |
| P1 | MongoDB |
| P1 | MinIO / S3-compatible storage |
| P2 | SQL Server |
| P2 | Qdrant |
| P2 | Neo4j |
| P3 | RabbitMQ / Kafka |
| P3 | Mock email service (MailHog or equivalent) |
| P3 | Mock SMS service |
| P3 | Mock payment service |

P0 services are required for the first commercial demo. P1 expands enterprise coverage. P2 covers specialty data systems. P3 covers integrations that should default to mocks.

## Artifacts Produced

| Artifact | Produced By | Purpose |
|---|---|---|
| `test_environment_manifest.v1` | TestData Agent | Records the provisioned environment for reproducibility |
| `production_replacement_plan.v1` | TestData Agent | Documents what changes when moving from test to production |
| `runtime_qc_report.v1` | Runtime QC Agent | Records flow-by-flow results, screenshots, console errors |
| Screenshots and video | Runtime QC Agent | Visual evidence in the audit bundle |
| Console and network logs | Runtime QC Agent | Diagnostic evidence in the audit bundle |

## Production Replacement Plan

The factory always documents what must change to move from the test environment to production. This is recorded in `production_replacement_plan.v1`:

```json
{
  "schema": "production_replacement_plan.v1",
  "test_database": "app_postgres_test",
  "production_database_type": "postgres",
  "required_env_vars": [
    "DATABASE_URL",
    "POSTGRES_HOST",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD"
  ],
  "migration_command": "alembic upgrade head",
  "production_notes": [
    "Replace test DATABASE_URL before deployment",
    "Run migrations in staging first",
    "Use managed Postgres in production",
    "Do not ship test seed data"
  ]
}
```

The production replacement plan is included in the mission evidence bundle. It is the operator's checklist for taking the validated test result to production.

## Runtime QC Report Example

```json
{
  "schema": "runtime_qc_report.v1",
  "mission_id": "mission_uuid",
  "app_type": "web",
  "environment": "sandbox_browser_chromium",
  "launch_status": "passed",
  "accessibility_check": "wcag_2_1_aa",
  "tested_flows": [
    {
      "flow": "user_login",
      "status": "failed",
      "evidence": "Login button did not submit form",
      "screenshot_ref": "artifacts/screens/login_failed.png",
      "console_errors": ["POST /api/login returned 500"],
      "network_errors": ["500 /api/login"],
      "severity": "high",
      "recommended_fix": "Check auth route request body parsing"
    }
  ],
  "overall_status": "failed",
  "recommended_next_mission": "bug_fix_regression",
  "video_ref": "artifacts/qc_session.webm"
}
```
