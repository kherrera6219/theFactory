HOLY GRAIL REFINERY
DEVELOPMENT STANDARDS, BEST PRACTICES & GUIDELINES
Coding 
Strategy  ·
  
Debugging  ·
  
Versioning  ·
  
Documentation  ·
  
Security  ·
  Architecture
Version 
1.0  |
  February 
2026  |
  
Confidential  |
  Author: Kevin Herrera
About This Document
This document defines the authoritative standards, best practices, and guidelines that govern all software development on the Holy Grail 
Refinery — a
 35-agent AI-powered software engineering system built on 
LangGraph
, Redis Semantic Bus, Docker, and a 5-database architecture. These standards apply to all human and AI-generated code, agent implementations, infrastructure configurations, and documentation artifacts. Every developer, AI coding assistant (Codex, Claude Code), and contributing agent must follow these guidelines.
1. CODING STRATEGY
1.1 Core Design Principles
⚡ RULE: Every design decision must be justified against these 5 principles. If it violates more than one, it does not ship.
Principle
What It Means in HGR
How to Enforce It
Single Responsibility
Each agent does ONE job. AGENT-PY-001 extracts Python 
LogicNodes
 and nothing else. No agent holds dual responsibilities.
Code review gate: reject any agent with >1 primary function
Open/Closed
Agent base classes are open for extension, closed for modification. New capabilities = new subclass, not edits to 
BaseAgent
.
BaseAgent
 is protected. PRs touching it require ARCH-001 sign-off.
Liskov
 Substitution
Any language specialist can substitute for another at the protocol level — same Alpha/Beta message interface.
Integration tests verify all specialists handle identical message shapes.
Interface Segregation
Agents only subscribe to the protocols they need. A Compliance Agent never subscribes to Protocol Beta.
Redis channel subscriptions documented per agent. Audited in CI.
Dependency Inversion
Agents depend on the Redis Semantic Bus abstraction, never on each other directly. No agent imports another agent's module.
Linter rule: no cross-agent imports. CI blocks violations.
DRY (Don't Repeat Yourself)
LogicNode
 schema defined once (schema v2.0). All 35 agents reference that single source of truth.
JSON 
schema
 
file
 in /
schemas
/. 
Import it. Never redefine it.
Defense in Depth
Multiple validation layers: agent → Semantic Bus schema → Audit Agent → Traceability Ledger. No single point of failure.
Audit agent mandatory in pipeline. 
Cannot
 skip the Delta protocol gate.
1.2 Language & Framework Standards
The Holy Grail Refinery uses a polyglot stack. Each layer has a prescribed language. Do not deviate without an Architecture Decision Record (ADR).
Layer / Component
Prescribed Language & Version
Agent Microservices
Python 3.11+ — type hints required, async/await throughout
Mission Control UI
TypeScript 5+ / React 18+ — strict mode enabled
Semantic Bus Client
Python 3.11+ — no raw Redis calls, use 
SemanticBus
 class
Infrastructure / CI
Shell (Bash 5+) + YAML — no Python in CI where shell suffices
Database Migrations
Python (
Alembic) —
 never 
run
 raw SQL manually in production
Docker / Compose
Docker Compose v2 — Compose files are infrastructure as code
Agent Profiles
YAML (canonical) + Markdown (human-
readable) —
 both must stay in sync
LogicNode
 Schema
JSON Schema (Draft 
7) —
 single source of truth in /schemas/
1.3 Python Coding Standards
Formatting & Style
PEP 8 compliance is mandatory — enforced by ruff and enforced in CI (zero warnings = green build)
Line length: 88 characters (Black default)
All code formatted with Black before 
commit —
 pre-commit hook enforces this
Import ordering: 
stdlib
 → third-party → local, separated by blank lines (
isort
 enforced)
Type Safety
Type hints required on ALL function signatures — parameters and return types
Pydantic
 v2 models for all data structures crossing agent boundaries (messages, 
LogicNodes
, tasks)
mypy
 strict mode — 
no Any
 types without explicit comment justification
TypedDict
 for 
dicts
 that won't become full 
Pydantic
 models
✅ CORRECT: async def 
extract_
logicnodes
(
self, source: str, language: Language) → 
list[
LogicNode
]
❌ WRONG:   async def 
extract(
self, source, 
language)  #
 No types = PR rejected
Async Patterns
All agent operations are async — never use synchronous I/O in an agent
Use 
asyncio.gather
() for parallel operations — never sequential await in a loop
Timeout every external call with 
asyncio.wait
_
for
(
) — default 30s for LLM calls, 5s for Redis
Background tasks via 
asyncio.create
_
task
(
) with proper cancellation handling
Error Handling
Specific exceptions over bare except — catch the narrowest exception that makes sense
All exceptions logged with full context (
agent_id
, 
mission_id
, 
trace_id
) before re-
raise
 or recovery
Never swallow exceptions silently — log and 
decide:
 retry, dead-letter, or escalate
Custom exception hierarchy in /
exceptions/ —
 
HGRBaseException
 → 
ProtocolException
 → 
LogicNodeException
# CORRECT exception pattern
try:
    result = await 
self.semantic
_
bus.publish
(message)
except 
ProtocolException
 as e:
    
self.logger
.
error
(
'Protocol publish failed', extra
={
'agent': 
self.agent
_id
, 'trace': 
e.trace
_
id
})
    await 
self.dead
_letter_
queue.push
(message, reason=str(e))
    raise
1.4 TypeScript / React Coding Standards (Mission Control UI)
TypeScript strict mode: strict: true in 
tsconfig.json
 — no exceptions
No any
 type — use unknown and narrow it, or define the proper interface
React functional components only — no class components
Custom hooks for all stateful logic — keeps components as pure rendering functions
ESLint
 
with @
typescript-eslint/recommended + react-hooks/rules-of-hooks enforced in CI
Prettier for formatting — same philosophy as Black on the Python side
API layer isolated in /
api
/ —
 components never call 
fetch(
) directly
All WebSocket connections to Semantic Bus UI adapter managed in a single hook: 
useSemanticBus
(
)
1.5 Agent Base Class Requirements
Every agent MUST extend 
BaseAgent
. The following methods must be implemented:
Method
Requirement
initialize(
)
Called on agent startup. Load config, connect to Redis
, initialize
 DB pool. Must complete in <5s.
process_
task
(
task: Task)
Core logic. Must return 
TaskResult
. Must handle all exceptions internally.
handle_protocol_
message
(
msg: Message)
Entry point for all Semantic Bus messages. Route by protocol type.
health_
check
(
)
Returns 
HealthStatus
. Called by SRE Agent every 60s. Must respond in <1s.
shutdown(
)
Graceful cleanup. Drain in-flight tasks, close connections, flush logs. Must complete in <30s.
1.6 Anti-Patterns: What We Never Do
⚠️ These patterns are caught by code review and CI. Repeated violations require remediation sprint.
Anti-Pattern
Why It's Banned in HGR
Direct agent-to-agent imports
Destroys isolation. All communication is Semantic Bus only.
Hardcoded API keys or credentials
Security critical. Use vault. Zero tolerance — auto-revoke + incident report.
Synchronous I/O in agent code
Blocks the event loop. Degrades entire pod performance.
Magic numbers / strings
Use named constants. 
LogicNode
 schema version = LOGICNODE_SCHEMA_VERSION, not '2.0'.
God functions (>50 lines)
Violates SRP. Break into focused private methods.
Print statements in production code
Use structured logger. self.logger.info/warning/error always.
Direct SQL queries outside DAL
All DB access through Data Access Layer. Never raw psycopg2 in agent code.
Mutable default arguments
Classic Python footgun. def 
fn
(
data: list = None): data = data or []
Storing code in agent memory between missions
Privacy violation. Each mission's code is ephemeral.
Skipping Audit Agent gate via direct CEO merge
Bypasses 0.0001% tolerance requirement. Never allowed in production flow.
2. DEBUGGING STANDARDS
2.1 Structured Logging — The Foundation of Debugging
All debugging in HGR starts with logs. We use structured JSON logging throughout. Every log entry must carry the standard context 
fields
 so logs are 
queryable
 and 
correlatable
 across 35 agents.
Required Log Fields
Field
Description & Example
agent_id
Which agent produced this log — AGENT-PY-001
mission_id
UUID of the current mission — correlates all logs for a given job
trace_id
End-to-end trace ID flowing through all protocols
level
DEBUG | INFO | WARNING | ERROR | CRITICAL
timestamp
ISO-8601 with milliseconds — 2026-02-28T14:32:01.234Z
event
Short 
snake_case
 description — 
logicnode_extracted
, 
protocol_publish_failed
duration_ms
For any timed operation — included on completion events
error_code
Structured error code when level is ERROR — SCHEMA_VALIDATION_FAILED
# Standard log pattern
self.logger.info(
'
logicnode_extracted
', extra
={
    '
agent
_id
': 
self.agent
_id
,
    '
mission
_id
': 
self.mission
_id
,
    '
trace
_id
': 
self.trace
_id
,
    '
logicnode
_id
': ln.id,
    '
source
_language
': 
ln.source
_language
,
    '
duration
_ms
': 
elapsed_ms
})
2.2 Log Levels — When to Use What
Level
When to Use
DEBUG
Detailed execution trace — step-by-step inside algorithms. OFF in production by default. Enable per-agent via env var.
INFO
Normal business events — mission started, 
LogicNode
 extracted, protocol message sent. These tell the story of what happened.
WARNING
Unexpected but handled situations — retry #2 of 6 on DLQ, API rate limit approaching 80%, non-critical schema version mismatch.
ERROR
Failed operation that was caught and handled — message sent to DLQ, extraction failed for one file (mission continues).
CRITICAL
System-level failure — database connection lost, Redis unreachable, agent cannot start. SRE Agent alerted immediately.
2.3 Distributed Tracing — Following a Mission Across All Agents
Because a single mission touches 10-20 agents across 6 protocols, traditional debugging fails. We use distributed tracing to follow the full execution path.
Every mission starts with a unique 
trace_id
 generated by PM Agent at intake
trace_id
 is passed in every message envelope's 
metadata.trace
_id
 field — it never changes for the life of a mission
Every agent forwards 
trace_id
 to all child messages it produces
Jaeger / Zipkin UI: search by 
trace_id
 to see the full execution tree across all agents
Correlation in logs: grep/query for 
trace_id
 in centralized log store to see all events in order
🔍 DEBUGGING WORKFLOW: Mission is behaving wrong → get 
trace_id
 from PM Agent log → search in Jaeger → identify the agent/protocol step where behavior diverges → drill into that agent's logs with 
trace_id
 filter.
2.4 Debugging Runbook by Failure Type
Failure Type
Debugging Steps
Agent not responding to messages
1. docker 
ps
 — is container running? 2. docker logs {agent} — any startup errors? 3. Redis SUBSCRIBE {channel} — are messages arriving at bus? 4. 
health_check
 
endpoint — /
health returns 200? 5. Check DLQ for undelivered messages to this agent
LogicNode
 quality failing audit
1. Pull the failing 
LogicNode
 from Registry by ID 2. Compare intent field vs source code semantics manually 3. Check which Audit test case failed (AUDIT-CORRECTNESS vs AUDIT-PERF) 4. Reproduce with isolated test: feed same source to specialist in debug mode 5. Check language specialist's prompt template for the failing language
Protocol message not delivered
1. Check Redis XLEN {stream} — is the stream growing? 2. Check DLQ: LLEN 
dlq
:{
protocol
}:{
recipient} 3. Check retry count in message — has it exhausted 6 attempts? 4. Check recipient agent is subscribed: PUBSUB CHANNELS {protocol}* 5. Check message schema — does it pass schema validation?
Database connection errors
1. docker exec 
hgr-postgres
 
pg_isready
 2. Check connection pool exhaustion: SELECT 
count(
*) FROM 
pg_stat_activity
 3. Check 
max_connections
 setting matches total agent pool sizes 4. Look for long-running queries: SELECT * FROM 
pg_stat_activity
 WHERE state='active' 5. Check disk space: 
df
 -h
Mission stuck / not completing
1. Get 
trace_id
 from PM Agent 2. In Jaeger: find the last completed span 3. The agent after the last completed span is stuck 4. Check that agent's container logs 5. If timeout: the previous agent may not have sent the completion message — check DLQ
Unexpected LLM output
1. Enable DEBUG logging 
on
 the specialist agent 2. Check the full prompt sent to LLM (logged at DEBUG level) 3. Check temperature setting — should be 0.2 for code agents 4. Check context window — is the source file too large? 5. Test with isolated repro: same prompt, same model, same temperature
2.5 Debug Environment Setup
Local debug mode: LOG_LEVEL=DEBUG docker-compose up {service} — enables verbose output for one agent
Redis monitor: 
redis
-cli MONITOR — streams all Redis commands in real-time (use sparingly in prod)
Protocol sniffing: subscribe to 
redis
 channel with 
redis
-cli SUBSCRIBE 
hgr
:{
protocol} to see live messages
Database query profiling: SET 
log_min_duration_statement
 = 100 in PostgreSQL to log slow queries
Agent interactive debug: docker exec -it {container} python -c 'import agent; 
agent.debug
_
mode
(
)'
Isolated agent test: 
pytest
 tests/agents/test_{
agent_id
}.
py
 -v -s — -s shows live 
stdout
3. VERSIONING STANDARDS
3.1 Semantic Versioning — System & Components
The Holy Grail Refinery follows Semantic Versioning 2.0 (
MAJOR.MINOR.PATCH
) for all 
versioned
 artifacts. Understanding what constitutes each increment is critical because this is a distributed system — a breaking change in one component can cascade.
Version Part
What Triggers It in HGR
MAJOR (X.0.0)
Breaking changes: 
LogicNode
 schema major version bump, Protocol message shape changes that aren't backward-compatible, 
BaseAgent
 API changes, Database schema changes requiring data migration with no backward 
compat
.
MINOR (0.X.0)
New capabilities, backward compatible: new agent added to a pod, new protocol field added (optional), new 
LogicNode
 property added (optional), new database table, new API endpoint, new feature flag.
PATCH (0.0.X)
Bug fixes, performance improvements, no API changes: bug fix in 
LogicNode
 extraction logic, retry count adjustment, log level correction, documentation updates, test additions.
3.2 Git Branching Strategy
HGR uses a structured branching model with protected branches and mandatory review gates.
Branch
Purpose
Rules
main
Production-ready code only
Protected. No direct push. PR required. All CI must pass. 1 reviewer minimum.
develop
Integration branch for next release
Protected. No direct push. PR required. CI must pass.
feature/{
ticket-
id}-{
description}
New feature development
Branch from develop. Max lifetime: 2 weeks before mandatory rebase.
fix/{
ticket-
id}-{
description}
Bug fixes
Branch from main for hotfixes, develop for normal fixes.
agent/{
agent-
id}-{
description}
New agent implementation
Branch from develop. Named after the agent being built.
docs/{
description}
Documentation only changes
Branch from develop. CI skips tests (docs only). Fast 
merge
.
release/{
version}
Release preparation
Branch from develop. Only bug fixes and version bumps 
allowed
 here.
3.3 Commit Message 
Standard
HGR enforces Conventional Commits. A CI hook rejects non-conforming commit messages. Every commit tells a story readable 
in
 git log.
FORMAT
:  <
type>(<scope>): <description
>  [
optional body] [optional footer: BREAKING CHANGE / Closes #issue]
Type
When to Use
feat
New feature — new agent, new protocol message type, new API endpoint
fix
Bug fix — corrects existing behavior without adding new capability
docs
Documentation only — no code changes, just docs/comments/profiles
test
Adding or correcting tests — no production code changes
refactor
Code restructure without feature change or bug fix
perf
Performance improvement — same behavior, faster execution
chore
Build system, CI config, dependency updates — no production code
agent
Agent profile additions or updates — use for 8-part profile changes
schema
LogicNode
 schema or protocol schema changes — high visibility type
security
Security fix — gets expedited review and immediate release
# GOOD commit messages
feat(agent/pod-a): add Go language specialist AGENT-GO-001
fix(
semantic-bus
): retry logic not resetting backoff on successful reconnect
schema(
logicnode
): add optional 
performance_hints
 field to v2.1
security(secrets): rotate API key vault encryption to AES-256-GCM
# BAD commit messages (CI will reject)
fix stuff
WIP
updated agent
3.4 Agent Profile Versioning
Agent profiles are living documents. Every change must be tracked with the profile's own version field and a changelog entry.
Profile version field: version: 
MAJOR.MINOR.PATCH
 in the profile YAML header
MAJOR: Changes to agent's core identity, jurisdictional scope, or communication protocols
MINOR: New skills, updated credentials, additional SOPs
PATCH: Wording corrections, reference updates, formatting
Quarterly self-update mechanism: agents review and update their own profiles Q1/Q2/Q3/Q4
Profile changelog entry required: date, version, what changed, why
3.5 
LogicNode
 Schema Versioning
The 
LogicNode
 schema is the core data contract of HGR. Schema versioning is critical because 35 agents all produce and consume 
LogicNodes
.
Schema lives in /schemas/
logicnode
-v{MAJOR
}.{
MINOR
}.
json
 — never overwrite a published version
Protocol version field in every 
LogicNode
: 
schema_version
: '2.1'
Agents support current version + 1 previous major version (backward compatibility window)
Breaking schema changes require IS Agent Sigma broadcast with 48-hour migration window
Schema change process: Draft → ADR → Review → Broadcast (Sigma) → Adoption monitoring → Old version sunset at >99% adoption
3.6 Database Migration Versioning
Alembic for all PostgreSQL migrations — no ad-hoc SQL scripts
Migration files are numbered sequentially and describe the change: 0012_add_logicnode_performance_hints.py
Every migration must have both 
upgrade(
) and 
downgrade(
) functions — rollback must always be possible
Migrations tested in docker-
compose.test.yml
 before merging to develop
Never modify a migration that has been applied to production — add a new one
Migration status tracked in 
alembic_version
 table — checked by CI before deployment
4. DOCUMENTATION REQUIREMENTS
4.1 The Documentation Philosophy
Documentation in HGR is not optional and not secondary. It is a first-class artifact produced alongside code. The rule: if it isn't documented, it doesn't exist. This applies to agents, protocols, schemas, decisions, and operational procedures.
📝 STANDARD: A PR that adds code without documentation is incomplete. The reviewer will request documentation before merge, not after.
4.2 Code Documentation Standards
Python Docstrings
All public functions, methods, and classes require Google-style docstrings
Include: summary, 
Args
, Returns, Raises sections — all four whenever applicable
Private methods (_name) require a one-line comment explaining why, not what
Complex algorithms require inline comments explaining the approach and non-obvious decisions
def 
extract_
logicnodes
(
self, source: str, language: Language) -> 
list[
LogicNode
]:
    """Extract semantic 
LogicNodes
 from source code.
    Parses source code to identify discrete computational units and
    captures their intent, inputs, outputs, and side effects as 
LogicNodes
.
    Uses LLM-assisted semantic extraction, not AST-only parsing.
    
Args
:
        source: Raw source code string to analyze.
        language: The programming language 
enum
 for parser selection.
    Returns:
        List of 
LogicNode
 objects. May be empty if source has no extractable units.
    Raises:
        
ExtractionException
: If LLM call fails after max retries.
        
SchemaValidationException
: If extracted data fails 
LogicNode
 schema.
    """
4.3 Agent Profile Documentation
All 35 agents must maintain complete 8-part profiles. These are the living specification documents for each agent's behavior, capabilities, and protocols.
Profile Part
Required Contents
Part 1: Core Identity
Agent ID, Name, Tier, Operational Status, Pod Assignment, Reports To, Context Window, API Access
Part 2: Job Role & Education
Real-world job title equivalent, degrees/certifications, years of experience, specialization areas
Part 3: Traits & Skills
Personality characteristics, technical skills, programming languages, frameworks, methodologies
Part 4: Methods & SOPs
Step-by-step procedures for all primary tasks, decision trees, escalation paths
Part 5: Tools
Primary and secondary tools, database access scope, external APIs, permissions
Part 6: Master Instruction
The complete system prompt / behavioral directive for the LLM core — the agent's brain
Part 7: API Configuration
Model name, temperature, context window, API key env var, rate limit handling
Part 8: Professional Grounding
Industry certifications, internal HGR certifications, continuing education requirements
⚠️ Profiles must be reviewed quarterly. An outdated profile (>90 days without review) is flagged in the Documentation Health dashboard.
4.4 Architecture Decision Records (ADRs)
Every significant technical decision — choosing a technology, changing an architectural pattern, deprecating a component — requires an ADR. ADRs live in /docs/
adrs
/. They are numbered sequentially and never deleted.
ADR Template
Section
What to Write
ADR-###
 Title
One clear sentence naming the decision — ADR-012: Use Redis Streams for Semantic Bus Persistence
Date & Status
Date written. Status: Proposed | Accepted | Deprecated | Superseded by ADR-###
Context
The problem, constraints, and forces that 
made a decision
 necessary
Decision
Exactly what was decided, stated clearly and unambiguously
Rationale
Why this option was chosen over alternatives — evidence, benchmarks, trade-off analysis
Consequences — Positive
Expected benefits delivered by this decision
Consequences — Negative
Trade-offs accepted. Be honest. Hidden costs surface here.
Alternatives Considered
Other options evaluated and why each was rejected
4.5 API Documentation
Every API endpoint documented in 
OpenAPI
 3.0 format — autogenerated from 
FastAPI
 decorators
Request/response schemas documented with examples — not just field names
Error responses documented: all possible HTTP status codes and 
error_code
 values
Authentication requirements documented at endpoint level
Deprecation notices: deprecated endpoints marked with x-deprecated: true and sunset date
API docs 
auto-published
 to /docs/ endpoint in development mode
4.6 Protocol Documentation
Each of the 6 communication protocols (Alpha, Beta, Delta, Sigma, Omega, Rho) requires:
Full message schema in JSON Schema format with all required and optional fields
Sequence diagrams showing message flow for the 3 most common use cases
Decision tree: when to use this protocol vs alternatives
Error scenarios and expected handling
Version history with backward compatibility notes
Test fixtures: canonical valid message examples used in integration tests
4.7 Operational Documentation
Document Type
Required Content
Update Frequency
System Startup Runbook
Step-by-step from cold 
boot
 to all agents healthy. Estimated time. Validation command for each step.
Every release
Troubleshooting Guide
Top 20 failure scenarios. Diagnosis commands. Resolution steps. Escalation path.
After each incident
Disaster Recovery Runbook
Full restoration procedure. Tested quarterly. RTO and RPO targets confirmed.
Quarterly after DR test
Monitoring Dashboard Guide
What 
each
 metric 
means.
 Alert thresholds. Expected baseline ranges. Action for each alert.
When thresholds change
Agent Onboarding Guide
How to add a new agent: profile creation, Docker config, Semantic Bus registration, testing.
When process changes
Database Maintenance Guide
Vacuum schedules, index rebuilds, backup verification, connection pool monitoring.
Annually + after incidents
4.8 README Requirements
Every directory in the repository that contains a non-trivial component requires a README.md. It must include:
What this component does (2-3 sentences)
How to run it locally (exact commands)
How to run its tests (exact commands)
Key configuration variables and their defaults
Links to relevant ADRs and spec documents
Known issues or limitations (if any)
5. TESTING STANDARDS
5.1 The Test Pyramid
HGR follows a strict test pyramid. 
The majority of
 tests are fast unit tests. A smaller number of integration tests. A minimal but critical set of end-to-end tests. Inversion of this pyramid is a code quality debt item.
Layer
Standards & Targets
Unit Tests (many, fast)
Target: 90%+ code coverage on all agent modules. Each test tests ONE behavior. Mocked dependencies (Redis, DB, LLM calls). Must run in <5ms per test. Live in tests/unit/. No docker required.
Integration Tests (fewer, medium)
Test component interactions: Redis pub/sub, DB read/write, API endpoints, protocol message flows. Use docker-
compose.test.yml
. Full suite <30 minutes. 100% pass rate required for 
merge
 to develop.
End-to-End / System Tests (few, slow)
Full mission execution from PM Agent intake to delivery. Exercises all 7 Smelt-Cycle phases. Runs in full Docker environment. Required before every release. The golden path test.
Audit Tests (special, formal)
0.0001% tolerance: 999 of 1000 test 
LogicNodes
 must pass. Run by AUDIT-CORRECTNESS-001 and AUDIT-PERF-001. Cannot be skipped. Part of the Delta protocol gate in production.
Load Tests (scheduled, slow)
Concurrent mission simulation. Verify DLQ stays empty under normal load. Run weekly in staging. Failure triggers architecture review.
5.2 Test Naming Convention
# PATTERN: 
test_{
what_is_being_
tested
}_
{
condition}_{
expected_outcome
}
def test_python_specialist_extract_logicnodes_valid_source_returns_nonempty_
list(
):
def 
test_semantic_bus_publish_redis_unavailable_routes_to_
dlq
(
):
def test_logicnode_schema_validation_missing_intent_field_raises_schema_
exception(
):
5.3 Test Data Management
Fixtures in /tests/
fixtures/ —
 organized by agent and scenario
Golden files: expected 
LogicNode
 outputs for known inputs — any deviation is a test failure
Test databases seeded from /tests/fixtures/databases/ — never use production data in tests
Synthetic code samples in /tests/fixtures/
source_
code
/{language}/ —
 one file per language per scenario
No real customer code ever enters the test suite — synthetic only
6. SECURITY STANDARDS
6.1 Secrets Management
🚨 ZERO TOLERANCE: Any secret (API key, password, token) committed to Git triggers immediate incident: rotate the secret, audit access logs, incident report filed. No exceptions.
All secrets in encrypted vault — never in .env files committed to repo (
only .
env
.example
 with placeholders)
API keys injected at runtime via vault client — never hard-coded, never in Docker ENV in plaintext
Each agent has its own API key — no shared credentials between agents
Gitleaks
 runs in CI on every commit to pre-main branches — blocks merge on detection
Secret rotation schedule: LLM API keys quarterly, DB passwords monthly, internal tokens as needed
6.2 Container Security
All containers run as non-root users — USER 
hgr:hgr
 in every 
Dockerfile
Read-only root filesystem where possible — volumes mounted for writable paths
Trivy
 scan on every Docker image build in CI — CRITICAL/HIGH CVEs block merge
Base images: python:3.11-slim (agents), node:20-alpine (
UI) —
 minimal attack surface
No SSH, no 
cron
, no unnecessary packages in production images
Image digest pinning in docker-
compose.yml
 — 
no :latest
 tags in production
6.3 Network Security
All agents on 
hgr
-network bridge — no external exposure except Mission Control UI
PostgreSQL and Redis ports NOT exposed to host in production (only in dev/test)
All inter-agent communication through Redis Semantic Bus — no direct HTTP between agents
TLS required for any future external API endpoints
Code submitted by users never leaves local network — API Broker enforces this at ingress
6.4 OWASP Top 10 Compliance
Input validation on all Semantic Bus message fields before processing — schema validator rejects malformed input
SQL injection prevention: parameterized queries only through Alembic / 
SQLAlchemy
 ORM
Sensitive data exposure prevention: no user code in log output, no PII in 
LogicNodes
Broken authentication prevention: vault-managed keys, no anonymous API access
Security misconfiguration prevention: environment-specific configs, no debug mode in production
Dependency vulnerability management: Safety/pip-audit weekly, auto-PR for security patches
7. CI/CD PIPELINE STANDARDS
7.1 Pipeline Stages (Non-
Negotiable
 
Sequence
)
Every PR to develop or main must pass all stages in order. A failure in any stage blocks the next stage. There are no bypasses.
Stage
What Runs
Pass Criteria
1. Validate
Linting (ruff), type checking (
mypy
), import ordering (
isort
), formatting (Black/Prettier), commit message format
Zero warnings. All formatting checks pass.
2. Build
Docker image builds for all modified agents and services. Multi-stage builds. Layer caching.
All images 
build
 successfully. No build errors or warnings.
3. Unit Test
Full 
pytest
 unit 
suite
 with coverage measurement. Mocked dependencies.
90%+ coverage. Zero test failures. <
5 minute
 runtime.
4. Integration Test
Docker Compose test environment. Protocol tests, DB tests, API tests.
100% pass rate. <
30 minute
 runtime.
5. Security Scan
Bandit (SAST), Safety (dependencies), 
Trivy
 (containers), 
Gitleaks
 (secrets)
No CRITICAL/HIGH issues. Zero secrets detected.
6. Build Artifacts
Tag Docker images with git SHA + version. Push to registry.
Images tagged and available. Manifest published.
7. Deploy to Staging
Automated deploy to AW1 staging environment. Docker Compose up.
All containers 
healthy
. Smoke tests pass.
8. E2E Test
Full mission golden path test in staging. All 7 Smelt-Cycle phases.
Mission completes. 
LogicNodes
 produced. Delivery confirmed.
9. Deploy to Production
MANUAL GATE: Kevin approves. Docker Compose up with blue-green strategy.
All agents 
healthy
. Zero DLQ depth. Metrics normal.
7.2 Deployment Strategy
Blue-Green deployment: new version (green) started alongside current (
blue) —
 traffic switched after green is healthy
Health check grace period: 60 seconds for agents to initialize before health check enforced
Automatic rollback: if health checks fail within 5 minutes of 
deploy
, blue environment restored automatically
Zero downtime for Mission Control UI: rolling update with at least 1 replica always serving
Database migrations run before agent deployment — backward compatible migrations only for zero-downtime
Post-deployment monitoring: 15-minute heightened alert sensitivity after every production deploy
8. ARCHITECTURE STANDARDS
8.1 The Non-Negotiable Architecture Rules
Rule
Detail
Semantic Bus Only
All agent-to-agent communication through Redis Semantic Bus. Zero direct calls. Zero HTTP between agents. Zero shared memory.
One Database Owner per Data
Each database has a designated owner agent. Others query through the owner's API, not directly. Prevents schema drift.
Stateless Agents
Agent containers hold zero state between missions. All state in databases. Enables safe restart of any agent at any time.
Idempotent Operations
Producing the same 
LogicNode
 twice = same result. Mission 
replay
 safe. Database writes use 
upsert
 with deterministic IDs.
Audit Before Fusion
No 
LogicNode
 enters the Master Logic Stream without passing the Delta protocol Audit gate. No exceptions. No overrides.
Private UKG
UKG reasoning runs locally on AW1. No UKG data, queries, or responses leave the local network. Isolated from all external logging.
Config Over Code
Agent behavior tunable via config without code changes. Temperature, timeout, retry count, model selection all in config.
Fail Fast, Fail Loudly
Errors surface immediately with full context. No silent degradation. SRE Agent alerted within 60 seconds of any CRITICAL event.
8.2 Performance Targets
Metric
Target
LogicNode
 extraction latency (single file)
< 30 seconds per source file
Audit gate evaluation time
< 10 seconds per 
LogicNode
Semantic Bus message end-to-end latency
< 500ms (95th percentile)
Mission Control UI response time
< 200ms for status queries
Agent health check response time
< 1 second
Agent startup time
< 5 seconds
Database query time (P95)
< 100ms for 
LogicNode
 lookups
Full mission completion (10 files, 3 languages)
< 10 minutes
System availability target
99.9% (43 min downtime/month max)
9. CODE REVIEW STANDARDS
9.1 What Every Reviewer Must Check
Review Category
Specific Checks
Correctness
Does it do what the ticket says? Are edge cases handled? Does it pass all its tests?
Security
No secrets. No SQL injection risk. No sensitive data in logs. Input validation present.
Architecture compliance
No direct agent imports. Uses 
SemanticBus
 class, not raw Redis. Extends 
BaseAgent
.
Type safety
All function signatures typed. No bare Any. 
Pydantic
 models for cross-boundary data.
Error handling
Specific exceptions. All caught exceptions logged with context. No silent swallowing.
Documentation
Docstrings on public methods. README updated if behavior changed. ADR created if significant decision made.
Tests
New code has new tests. Tests are meaningful, not just coverage padding. Test names follow convention.
Performance
No N+1 queries. No synchronous I/O in agents. 
asyncio.gather
() for parallel work.
9.2 Review SLAs
First review response within 24 hours of PR submission
PR author responds to review comments within 48 hours
Maximum 2 review rounds before escalation to ARCH-001
Agent profile PRs: reviewed by Kevin (owner) within 48 hours
Security PRs: expedited — 
4 hour
 first response target
Hotfix PRs: 1 hour response target, deploy within 2 hours of approval
10. QUICK REFERENCE CARD
Print this page and keep it visible during development.
What You're Doing
The Standard
Naming a branch
feature/{ticket}-{
short-desc} | fix/{
ticket}-{
short-desc} | agent/{agent-
id}-{
desc}
Writing a commit
feat|fix|docs|test|refactor|perf|chore|agent|schema|security(scope): description
Adding a public function
Google-style docstring: summary + 
Args
 + Returns + Raises
Writing a 
type
 signature
ALL parameters and return type annotated — no bare Any
Catching an exception
Specific exception type + log with 
agent_id
, 
mission_id
, 
trace_id
 + 
decide:
 retry/DLQ/escalate
Communicating between agents
Publish to Redis Semantic Bus. 
Choose
 
protocol
: Alpha/Beta/Delta/Sigma/Omega/Rho
Accessing a database
Through the Data Access 
Layer —
 never raw psycopg2 in agent code
Making an architectural decision
Write an ADR in /docs/
adrs
/ before writing the code
Changing the 
LogicNode
 schema
Draft → ADR → Review → Sigma broadcast → 48h window → monitor adoption
Adding a new agent
Create 8-part profile → Docker config → Semantic Bus registration → unit + integration tests → PR
Storing a secret
Vault only. 
Never .env
 committed. Never env var in compose file. Report if you find one.
Running CI locally
pre-commit run --all-files then 
pytest
 tests/unit/ before pushing
Debugging a stuck mission
Get 
trace_id
 → Jaeger UI → find last span → check that agent's logs with 
trace_id
 filter
LogicNode
 extraction failing audit
Pull failing LN from Registry → compare intent to source → check which audit test → reproduce isolated
Holy Grail Refinery — Development Standards 
v1.0  |
  
Confidential  |
  Kevin 
Herrera  |
  Feb 2026