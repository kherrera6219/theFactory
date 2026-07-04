# Metrics Source Modules Reference

Document version: 2026.07.03
Last updated: 2026-07-03
Status: Canonical
Audience: Developers, Operators

This document was rewritten on 2026-07-03 — the previous version listed ~30 metric names (`http_requests_total`, `missions_created_total`, `sse_connections_active`, `mission_state_transitions_total`, `pod_assignments_total`, `langgraph_executions_total`, `agent_heartbeats_total`, etc.) that don't exist anywhere in the codebase, and inverted the two orchestrator-side modules' actual responsibilities. Every metric below was verified directly against the source.

## `services/orchestrator/orchestrator/orchestrator_metrics.py`

| Metric | Type | Labels | Purpose |
|---|---|---|---|
| `orchestrator_http_requests_total` | Counter | `method`, `path`, `status_code` | Orchestrator HTTP request count |
| `orchestrator_http_request_duration_seconds` | Histogram | `method`, `path` | Orchestrator HTTP request latency |
| `llm_fallback_total` | Counter | `agent_id`, `reason` | Count of silent LLM fallbacks (see `LLM_DELEGATION.md`) |
| `factory_mission_transitions_total` | Counter | `from_state`, `to_state`, `engine` | Every mission state transition (`engine` is `v2`\|`langgraph`\|`legacy`) |
| `factory_mission_outcomes_total` | Counter | `outcome` (`complete`\|`failed`\|`timeout`) | Terminal mission outcomes |
| `factory_missions_active` | Gauge | `state` (`queued`\|`running`\|`verified`) | Currently active missions by state — only these three states are tracked to keep cardinality bounded |
| `factory_mission_duration_seconds` | Histogram | `outcome` | Mission duration from intake to terminal state. Buckets: `(30, 60, 120, 300, 600, 1200, 1800, 3600)` seconds |
| `factory_mission_last_transition_timestamp` | Gauge | (none) | Unix timestamp of the most recent mission transition — consumed by the `MissionStuckInRunning` alert |

All mission-lifecycle metrics are recorded via `record_mission_transition()`, called from `insert_mission_event()` (the authoritative previous→new transition record). The function never raises — a metrics-recording failure is caught and logged, never allowed to break the mission pipeline.

## `services/orchestrator/orchestrator/data_plane_metrics.py`

Covers **optional adapters only** (Neo4j, object storage/MinIO) — not the core mission pipeline:

| Metric | Type | Labels | Purpose |
|---|---|---|---|
| `orchestrator_optional_adapter_enabled` | Gauge | `adapter` | Whether an optional adapter is enabled in settings (1/0) |
| `orchestrator_optional_adapter_ready` | Gauge | `adapter` | Whether an optional adapter is currently ready (1/0) |
| `orchestrator_optional_adapter_operations_total` | Counter | `adapter`, `operation`, `status` | Optional adapter operation count |
| `orchestrator_optional_adapter_operation_latency_seconds` | Histogram | `adapter`, `operation` | Optional adapter operation latency |
| `orchestrator_optional_adapter_mirror_writes_total` | Counter | `adapter`, `artifact`, `status` | Mirror-write count to optional adapters (e.g. writing a LogicNode to both Postgres and Neo4j) |
| `orchestrator_optional_adapter_mirror_write_latency_seconds` | Histogram | `adapter`, `artifact` | Mirror-write latency |
| `object_storage_legal_hold_fallback_total` | Counter | (none) | Times a legal-hold write was refused rather than written unprotected, because the bucket doesn't support Object Lock |

## `services/api-gateway/api_gateway/main.py` (inline, not a separate module)

| Metric | Type | Labels | Purpose |
|---|---|---|---|
| `api_gateway_http_requests_total` | Counter | `method`, `path`, `status_code` | Gateway HTTP request count |
| `api_gateway_http_request_duration_seconds` | Histogram | `method`, `path` | Gateway HTTP request latency |
| `api_gateway_live_stream_connections_total` | Counter | (none) | Total SSE live-stream connections accepted |
| `api_gateway_live_stream_events_total` | Counter | `event_type` | Events emitted on the live stream |
| `api_gateway_live_stream_errors_total` | Counter | `reason` | Live-stream errors observed |
| `factory_auth_failures_total` | Counter | `reason` (`invalid_key`\|`expired_token`\|`insufficient_role`\|`missing_auth`), `route_prefix` | Authentication failures, gateway-side |

## Alert Rules — `deploy/monitoring/prometheus/rules/thefactory-alerts.yml`

Real alert names (verified against the file, not the fictional `GatewayDown`/`PostgresDown`/`HighErrorRate`/`HighP95Latency` a prior version of this document listed): `ApiGatewayDown`, `OrchestratorDown`, `ProtocolBusMcpDown`, `PodWorkerDown`, `AuditWorkerDown`, `ApiGateway5xxRateHigh`, `Orchestrator5xxRateHigh`, `ApiGatewayErrorBudgetBurnFast`/`Slow`, `OrchestratorErrorBudgetBurnFast`/`Slow`, `PodWorkerAgentLatencyP99High`, `DedicatedAgentRuntimeLatencyP99High`, `AuditWorkerAgentLatencyP99High`, `MissionStuckInRunning`, `MissionFailureRateHigh`, `Neo4jAdapterNotReady`, `ObjectStorageAdapterNotReady`, `Neo4jMirrorWriteErrorRateHigh`, `ObjectStorageMirrorWriteErrorRateHigh`, `Neo4jMirrorWriteLatencyP95High`, `ObjectStorageMirrorWriteLatencyP95High`.

## Related Docs

- `OBSERVABILITY_STACK.md` — Grafana dashboards and the alerting pipeline these metrics feed
