# Metrics Source Modules Reference

Document version: 2026.06.13
Last updated: 2026-06-27
Status: Canonical
Audience: Developers and operators

**Source files:**
- `services/orchestrator/orchestrator/data_plane_metrics.py`
- `services/orchestrator/orchestrator/orchestrator_metrics.py`

**Version:** v1.2.0  
**Last updated:** 2026-06-11

Two dedicated modules define all Prometheus metrics exposed by the Orchestrator service. Separating metric definitions from business logic keeps instrumentation auditable — every counter, histogram, and gauge can be reviewed in one place without reading application code.

The broader observability stack (Grafana dashboards, alert rules, log aggregation) is documented in [OBSERVABILITY_STACK.md](OBSERVABILITY_STACK.md). This document covers only the metric definitions themselves.

---

## Module Responsibilities

| Module | Responsibility |
|---|---|
| `data_plane_metrics.py` | Metrics for the data path — mission ingestion, LogicNode flow, storage operations, Protocol Bus activity, and pod worker interactions |
| `orchestrator_metrics.py` | Metrics for the control plane — agent lifecycle, mission state transitions, LLM delegation calls, cost tracking, and system health |

Both modules are imported at Orchestrator startup in `main.py` via the lifespan hook. Metrics are registered with the shared `prometheus_client` registry and exposed at `GET /metrics` on port `8101`.

---

## `data_plane_metrics.py` — Data Plane Metrics

### Counters

| Metric name | Labels | Description |
|---|---|---|
| `factory_missions_received_total` | `mission_type`, `depth_mode` | Incremented on every valid mission intake at the Gateway. |
| `factory_missions_completed_total` | `mission_type`, `output_mode`, `status` | Incremented on terminal state (`COMPLETE` or `FAILED`). `status` is `success` or `failure`. |
| `factory_logicnodes_emitted_total` | `pod_id`, `language_key`, `tag_category` | Incremented per LogicNode emitted to the delta stream by a pod worker. |
| `factory_logicnodes_ingested_total` | `pod_id`, `confidence_band` | Incremented per LogicNode accepted by the internal route. `confidence_band` maps to the four scoring bands (low/medium/high/authoritative). |
| `factory_logicnodes_rejected_total` | `rejection_reason` | Incremented per LogicNode rejected. `rejection_reason` is the error code (`LNODE_001`, `LNODE_002`, etc.). |
| `factory_storage_operations_total` | `operation`, `table`, `status` | Incremented per storage call. `operation` is `insert`/`select`/`update`/`delete`. `status` is `ok` or `error`. |
| `factory_protocol_bus_messages_total` | `stream`, `direction` | Incremented per Protocol Bus message. `stream` is one of the 6 stream names; `direction` is `produce` or `consume`. |
| `factory_artifacts_stored_total` | `artifact_type`, `storage_backend` | Incremented per artifact written to object store. |

### Histograms

| Metric name | Labels | Buckets | Description |
|---|---|---|---|
| `factory_mission_duration_seconds` | `mission_type`, `depth_mode` | `[1, 5, 15, 30, 60, 120, 300, 600]` | End-to-end mission wall time from `INTAKE` to terminal state. |
| `factory_storage_operation_duration_seconds` | `operation`, `table` | `[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0]` | Per-operation storage latency. |
| `factory_logicnode_batch_size` | `pod_id` | `[1, 5, 10, 25, 50, 100, 250, 500]` | Number of LogicNodes in each batch callback from a pod worker. |
| `factory_protocol_bus_message_size_bytes` | `stream` | `[128, 512, 1024, 4096, 16384, 65536]` | Serialised message size on each stream. |

### Gauges

| Metric name | Labels | Description |
|---|---|---|
| `factory_missions_active` | `mission_type` | Current count of missions in non-terminal states. |
| `factory_logicnodes_pending_embedding` | `store` | LogicNodes queued for embedding, per store (`qdrant`/`milvus`/`neo4j`). |
| `factory_storage_pool_connections_active` | `database` | Active connections in the connection pool. |
| `factory_storage_pool_connections_idle` | `database` | Idle connections in the connection pool. |

---

## `orchestrator_metrics.py` — Control Plane Metrics

### Counters

| Metric name | Labels | Description |
|---|---|---|
| `factory_agent_executions_total` | `agent_key`, `tier`, `status` | Incremented per agent execution. `status` is `ok`, `error`, or `timeout`. |
| `factory_mission_state_transitions_total` | `from_state`, `to_state` | Incremented per state machine transition. Invalid transitions are not counted here — they appear in `factory_errors_total`. |
| `factory_llm_calls_total` | `provider`, `model`, `agent_key`, `status` | Incremented per LLM delegation call. `status` is `ok`, `error`, `cost_ceiling_exceeded`, or `fallback_used`. |
| `factory_llm_tokens_total` | `provider`, `model`, `token_type` | Total tokens consumed. `token_type` is `prompt` or `completion`. |
| `factory_llm_cost_usd_total` | `provider`, `model` | Accumulated USD cost from LLM calls. This counter is the source of truth for the cost ledger summary. |
| `factory_lifecycle_recoveries_total` | `recovery_type` | Incremented per lifecycle recovery event (startup rehydration, self-heal). |
| `factory_errors_total` | `error_code`, `component` | Incremented per application error. `component` identifies the module (e.g. `mission_flow_v2`, `agent_runtime`). |
| `factory_rqca_checks_total` | `check_type`, `result` | Incremented per RQCA Agent check. `result` is `pass`, `warn`, or `fail`. |

### Histograms

| Metric name | Labels | Buckets | Description |
|---|---|---|---|
| `factory_agent_execution_duration_seconds` | `agent_key`, `tier` | `[0.1, 0.5, 1, 2, 5, 10, 30, 60, 90]` | Per-agent execution wall time. The 90s bucket aligns with the LLM delegation wall-time ceiling. |
| `factory_llm_call_duration_seconds` | `provider`, `model` | `[0.5, 1, 2, 5, 10, 20, 30, 60, 90]` | LLM API call latency including retry overhead. |
| `factory_mission_phase_duration_seconds` | `phase` | `[1, 5, 15, 30, 60, 120, 300]` | Time spent in each of the 11 mission flow phases. |

### Gauges

| Metric name | Labels | Description |
|---|---|---|
| `factory_agents_registered` | `tier` | Current count of registered agents per tier. This should be stable at runtime; a drop indicates a registration bug. |
| `factory_agents_running` | `tier` | Agents currently executing (non-idle). |
| `factory_llm_cost_ceiling_remaining_usd` | `scope` | Remaining USD budget before the cost ceiling is enforced. `scope` is `mission` or `global`. |
| `factory_mission_queue_depth` | `priority` | Missions waiting for an available pod. |

---

## Label Cardinality Rules

High-cardinality labels cause Prometheus memory exhaustion. The following rules are enforced in both modules:

1. **No mission IDs, user IDs, or UUIDs as labels.** These are unbounded. Use counters without these labels and cross-reference in logs.
2. **`agent_key` is bounded** — 41 values. Safe as a label.
3. **`model` is bounded** — the number of LLM models in the provider matrix is finite. New models require a metrics review before deployment.
4. **`error_code` is bounded** — all error codes are pre-defined in `ERROR_CODES.md`. Free-form error strings are never used as label values.
5. **`tag_category` on LogicNode metrics uses the 10-category prefix only** — not the full `category:concept` tag string, which has unbounded cardinality.

---

## Grafana Dashboard Mapping

The following Grafana dashboards (defined in `OBSERVABILITY_STACK.md`) consume these metrics:

| Dashboard | Primary metrics consumed |
|---|---|
| **Mission Throughput** | `factory_missions_received_total`, `factory_missions_completed_total`, `factory_mission_duration_seconds`, `factory_missions_active` |
| **LogicNode Flow** | `factory_logicnodes_emitted_total`, `factory_logicnodes_ingested_total`, `factory_logicnodes_rejected_total`, `factory_logicnode_batch_size` |
| **Agent Health** | `factory_agent_executions_total`, `factory_agent_execution_duration_seconds`, `factory_agents_registered`, `factory_agents_running` |
| **LLM Cost & Latency** | `factory_llm_calls_total`, `factory_llm_tokens_total`, `factory_llm_cost_usd_total`, `factory_llm_call_duration_seconds`, `factory_llm_cost_ceiling_remaining_usd` |
| **Storage & Bus** | `factory_storage_operations_total`, `factory_storage_operation_duration_seconds`, `factory_protocol_bus_messages_total`, `factory_storage_pool_connections_active` |
| **Error Rate** | `factory_errors_total`, `factory_rqca_checks_total`, `factory_lifecycle_recoveries_total` |

---

## Metrics-to-Alerting Contract

The following metrics feed the alert rules in `OBSERVABILITY_STACK.md`. Any change to these metric names or label schemas requires a corresponding update to the alert rule definitions before deployment:

| Alert rule | Metric(s) used | Threshold |
|---|---|---|
| `MissionFailureRateHigh` | `factory_missions_completed_total{status="failure"}` | > 5% of completions over 5 min |
| `LLMCostCeilingNear` | `factory_llm_cost_ceiling_remaining_usd{scope="global"}` | < $5.00 remaining |
| `AgentExecutionTimeout` | `factory_agent_executions_total{status="timeout"}` | Any timeout in 1 min |
| `StorageErrorSpike` | `factory_storage_operations_total{status="error"}` | > 10 errors in 2 min |
| `LogicNodeRejectionSpike` | `factory_logicnodes_rejected_total` | > 50 rejections in 5 min |
| `MissionQueueDepthHigh` | `factory_mission_queue_depth` | > 20 queued missions |

---

## Adding a New Metric

1. Decide which module owns the metric: data path → `data_plane_metrics.py`; control plane → `orchestrator_metrics.py`.
2. Choose the correct instrument type: counter for monotonically increasing events, histogram for latency/size distributions, gauge for point-in-time values.
3. Apply the label cardinality rules above before adding any labels.
4. Register the metric using the `prometheus_client` factory functions at module level (not inside a function — registration must happen at import time).
5. Update this document with the new metric in the appropriate table.
6. If the metric feeds an alert rule, update `OBSERVABILITY_STACK.md` and the live Prometheus alert rule file simultaneously.
