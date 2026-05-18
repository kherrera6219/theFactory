# Unified Logic Refinery (ULR) — Single Blueprint

Document version: 2026.03.29
Last updated: 2026-03-29
Status: Archived Legacy

This document is the **single source of truth** for the Unified Logic Refinery starter repo. It consolidates the architecture, contracts, workflows, and implementation plan into one place.

---

## 0) What ULR is

**Unified Logic Refinery (ULR)** is a small, event-driven system that:
- accepts *signals* (human input, tools, sensors, jobs, etc.),
- normalizes them into a consistent **Event envelope**,
- routes them through an **orchestrator** and **pods** (specialized workers),
- produces *artifacts* (decisions, summaries, reports, actions),
- and records lineage for auditability.

The starter repo is intentionally minimal: it includes scaffolding + schemas + a couple services (orchestrator + dashboard). This blueprint defines the rest so you can fill in services gradually without reinventing contracts.

---

## 1) Design principles

1. **Contract-first**: schemas and topics are stable; implementations can change.
2. **Event-sourced-ish**: all meaningful state transitions are emitted as Events.
3. **Idempotent by default**: every consumer must tolerate duplicates.
4. **Small services, clear roles**: orchestrator coordinates; pods do work; ledger records.
5. **Observability as a feature**: every hop emits a traceable event with correlation IDs.

---

## 2) Repository map

- `protocol/topics.yaml` — canonical topic names and intent
- `schemas/*.schema.json` — JSON Schemas for the main payload types
- `services/orchestrator` — FastAPI service (control plane / API + future coordinator loop)
- `services/dashboard` — placeholder UI
- `docker-compose.yml` — local dev wiring (Redis, services, etc.)

> If you add new services, keep them under `services/<name>` and treat `protocol/` + `schemas/` as the public interface.

---

## 3) Core contracts

### 3.1 Event envelope (required for the bus)

**Schema:** `schemas/event.schema.json`

Event fields that MUST be present:
- `id` (uuid-like string)
- `type` (string; semantic type)
- `ts` (ISO-8601 timestamp)
- `source` (producer name, e.g. `intake`, `orchestrator`, `pod-a`)
- `correlation_id` (string; ties a whole run together)
- `causation_id` (string; points to the event that caused this event)
- `payload` (object; must validate against its payload schema when applicable)
- `meta` (object; optional but recommended for trace, tenant, user, etc.)

**Rule:** every service **emits** events using this envelope, even if the payload is small.

### 3.2 Task + TaskResult

**Schemas:**
- `schemas/task.schema.json`
- `schemas/task_result.schema.json`

A `Task` is *work to be done* by a pod.  
A `TaskResult` is the pod’s outcome.

Minimum Task fields:
- `task_id`, `kind`, `input`, `attempt`, `created_at`

Minimum TaskResult fields:
- `task_id`, `status` (`ok|error|retry`), `output`, `metrics`, `completed_at`

**Rule:** pods must be idempotent by `task_id` (safe to re-run the same task).

### 3.3 State snapshot

**Schema:** `schemas/state.schema.json`

A convenience document used by the orchestrator/dashboard to show “where things are”.
It is **not** the source of truth; events are.

---

## 4) Topics (the semantic bus)

**Canonical list:** `protocol/topics.yaml`

Recommended semantics (summary):

- `ulr.signal.ingest`  
  Raw inbound signals after normalization.

- `ulr.state.transition`  
  Every meaningful state change (orchestrator emits).

- `ulr.task.dispatch`  
  Orchestrator dispatches `Task` requests to pods.

- `ulr.task.result`  
  Pods emit `TaskResult`.

- `ulr.ledger.append`  
  Append-only lineage records (what happened, why, from what).

- `ulr.alert`  
  Errors, policy violations, operator attention.

> In local dev, Redis Streams are a good fit. In production, Kafka/NATS/PubSub are typical.

---

## 5) System roles

### 5.1 Orchestrator (control plane + coordinator)

Responsibilities:
- Accept API requests (`/signal`, `/run`, `/health`, etc.)
- Convert inbound signals into Events (`ulr.signal.ingest`)
- Drive a run state machine:
  - decide which pod(s) to invoke,
  - dispatch tasks (`ulr.task.dispatch`),
  - collect results (`ulr.task.result`),
  - emit transitions (`ulr.state.transition`),
  - append lineage (`ulr.ledger.append`)

Non-responsibilities:
- Heavy computation
- Long-running job execution (pods do that)

### 5.2 Pods (workers)

Each pod is a small service with one job:
- consume `ulr.task.dispatch` (filtered by `kind` or routing key)
- perform work
- emit `ulr.task.result` (and optionally intermediate Events)

Examples of pod “kinds”:
- `classify_signal`
- `extract_entities`
- `retrieve_context`
- `synthesize_plan`
- `execute_action`
- `summarize_run`

### 5.3 Ledger (lineage + audit)

Append-only store that records:
- what was decided
- which inputs contributed
- which outputs were produced
- who/what initiated actions

Local dev: Redis Stream or SQLite.  
Production: Postgres (append tables) or an event store.

### 5.4 Registry (optional but recommended)

A service (or config file) that lists:
- available pods
- supported `Task.kind`
- version + health + routing info

This allows dynamic routing and graceful degradation.

### 5.5 Dashboard

Reads state snapshots and/or streams to visualize:
- runs in progress
- tasks, retries
- errors and alerts
- lineage traces (correlation_id drill-down)

---

## 6) Orchestrator state machine (reference)

A run is keyed by `correlation_id`.

States (suggested):
1. `RECEIVED` — signal accepted and normalized
2. `ROUTED` — orchestrator chose a workflow path
3. `DISPATCHED` — tasks sent to pods
4. `COLLECTING` — awaiting results
5. `COMPLETED` — final artifact produced
6. `FAILED` — terminal failure (after retries / policy block)

Transitions:
- Every transition emits `ulr.state.transition` with:
  - `from`, `to`, `reason`, `ts`, `correlation_id`

Retry policy (starter default):
- up to 3 attempts per task
- exponential backoff (pods or orchestrator; pick one and be consistent)
- `TaskResult.status == "retry"` triggers re-dispatch with `attempt+1`

Idempotency:
- Orchestrator must not dispatch the *same* `task_id` twice unless retrying.
- Pods must treat `task_id` as idempotency key.

---

## 7) API surface (starter-friendly)

Orchestrator service (FastAPI) endpoints (recommended):

- `GET /health`  
  Liveness/readiness.

- `POST /signal`  
  Body: arbitrary JSON (signal).  
  Response: `{correlation_id, accepted: true}`.  
  Side effect: emit `ulr.signal.ingest`.

- `GET /runs/{correlation_id}`  
  Returns current snapshot state (best-effort).

- `POST /runs/{correlation_id}/cancel`  
  Attempts to cancel (best-effort). Emits a transition.

Dashboard:
- `GET /`  
  simple HTML page (starter).

---

## 8) Storage and local dev wiring

### 8.1 Redis (recommended local backbone)

Use Redis Streams for topics:
- stream name == topic
- consumer groups per service

State snapshots:
- Redis Hash or JSON by key `run:{correlation_id}`

Ledger:
- Redis Stream `ulr.ledger.append` and/or persistent DB later

### 8.2 Docker compose

Local dev should include:
- `redis`
- `orchestrator`
- `dashboard`
- (optional) `pod-a`, `pod-b`, etc.

---

## 9) Security & policy guardrails

Minimum:
- Input size limits on `/signal`
- Basic auth / API key for non-local deployments
- Never log secrets in `payload`
- Emit `ulr.alert` on schema validation errors, repeated failures, or blocked actions

If you later add “action execution” pods:
- require allow-lists for external domains
- include a policy check step before execution
- record every action in the ledger (with inputs + outputs)

---

## 10) Observability

Required fields in `meta`:
- `trace_id` (or reuse correlation_id)
- `service` and `version`
- `env` (`local|staging|prod`)

Metrics to capture:
- task latency per kind
- run completion rate
- retries per kind
- event throughput

Logs:
- include `correlation_id` on every line

---

## 11) Implementation plan (practical sequence)

1. **Keep contracts stable**: do not break schemas/topics without versioning.
2. Add a small **bus adapter** to orchestrator (Redis Streams) to publish/consume events.
3. Implement a single **pod** (e.g. `classify_signal`) that consumes tasks and returns results.
4. Implement orchestrator loop:
   - on ingest: create a run, dispatch a task, await result, mark completed.
5. Add ledger append (even if just another stream).
6. Expand to multiple pods and branching workflows.

---

## 12) Versioning

- Schemas: introduce `v` in `meta` or version file names (`event.v1.schema.json`) when you need breaking changes.
- Topics: keep stable; if breaking, use suffix: `ulr.task.dispatch.v2`.

---

## 13) Appendix: validation rules

- Every event MUST validate against `event.schema.json`.
- If `payload` is a Task, it MUST validate against `task.schema.json`.
- If `payload` is a TaskResult, it MUST validate against `task_result.schema.json`.
- State snapshots MUST validate against `state.schema.json` (best-effort).

---

### Done

This file replaces scattered “blueprints”. If something is not specified elsewhere, **this file wins**.
