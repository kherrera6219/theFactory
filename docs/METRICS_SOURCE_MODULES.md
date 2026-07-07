# Metrics Source Modules Reference

Document version: 2026.07.06
Last updated: 2026-07-06
Status: Canonical
Audience: Developers, Operators

This document was rewritten on 2026-07-03 — the previous version listed ~30 metric names (`http_requests_total`, `missions_created_total`, `sse_connections_active`, `mission_state_transitions_total`, `pod_assignments_total`, `langgraph_executions_total`, `agent_heartbeats_total`, etc.) that don't exist anywhere in the codebase, and inverted the two orchestrator-side modules' actual responsibilities. Every metric below was verified directly against the source.

Updated on 2026-07-06 (Phase 3 documentation-accuracy remediation, closing findings #15/#28 from `FULL_APP_CODE_REVIEW_FINDINGS_2026-07-05.md`): the 2026-07-03 rewrite omitted four modules entirely — `llm_delegation/metrics.py`, `pod-worker/main.py`, `audit-worker/main.py`, and `agent-runtime/main.py` — even though `pod_worker_task_latency_seconds`, `agent_runtime_task_latency_seconds`, `audit_worker_task_latency_seconds`, and `factory_llm_tokens_total` were already referenced by real alert rules and dashboards. All four modules' complete metric sets are now listed below. Also fixed a stale casing mismatch: `factory_missions_active`'s label values were documented in lowercase (`queued`/`running`/`verified`); the real `_ACTIVE_GAUGE_STATES` set and the `MissionStuckInRunning` alert both use uppercase.

## `services/orchestrator/orchestrator/orchestrator_metrics.py`

| Metric | Type | Labels | Purpose |
|---|---|---|---|
| `orchestrator_http_requests_total` | Counter | `method`, `path`, `status_code` | Orchestrator HTTP request count |
| `orchestrator_http_request_duration_seconds` | Histogram | `method`, `path` | Orchestrator HTTP request latency |
| `llm_fallback_total` | Counter | `agent_id`, `reason` | Count of silent LLM fallbacks (see `LLM_DELEGATION.md`) |
| `factory_mission_transitions_total` | Counter | `from_state`, `to_state`, `engine` | Every mission state transition (`engine` is `v2`\|`langgraph`\|`legacy`) |
| `factory_mission_outcomes_total` | Counter | `outcome` (`complete`\|`failed`\|`timeout`) | Terminal mission outcomes |
| `factory_missions_active` | Gauge | `state` (`QUEUED`\|`RUNNING`\|`VERIFIED`) | Currently active missions by state — only these three states are tracked to keep cardinality bounded |
| `factory_mission_duration_seconds` | Histogram | `outcome` | Mission duration from intake to terminal state. Buckets: `(30, 60, 120, 300, 600, 1200, 1800, 3600)` seconds |
| `factory_mission_last_transition_timestamp` | Gauge | (none) | Unix timestamp of the most recent mission transition — consumed by the `MissionStuckInRunning` alert |

All mission-lifecycle metrics are recorded via `record_mission_transition()`, called from `insert_mission_event()` (the authoritative previous→new transition record). The function never raises — a metrics-recording failure is caught and logged, never allowed to break the mission pipeline.

## `services/orchestrator/orchestrator/llm_delegation/metrics.py`

| Metric | Type | Labels | Purpose |
|---|---|---|---|
| `factory_llm_requests_total` | Counter | `provider`, `model`, `agent_id`, `status` (`success`\|`error`\|`timeout`\|`rate_limited`) | Total LLM API requests |
| `factory_llm_request_duration_seconds` | Histogram | `provider`, `model` | LLM API request duration |
| `factory_llm_tokens_total` | Counter | `provider`, `model`, `token_type` (`prompt`\|`completion`) | Total LLM tokens used |
| `factory_llm_estimated_cost_usd_total` | Counter | `provider`, `model` | Estimated total LLM cost in USD |

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

## `services/pod-worker/pod_worker/main.py`

| Metric | Type | Labels | Purpose |
|---|---|---|---|
| `pod_worker_tasks_processed_total` | Counter | `pod_name`, `agent_id` | Total mission events processed by pod worker |
| `pod_worker_tasks_failed_total` | Counter | `pod_name`, `agent_id` | Total mission events failed by pod worker |
| `pod_worker_task_latency_seconds` | Histogram | `pod_name`, `agent_id` | Mission event processing latency for pod worker |
| `pod_worker_concepts_extracted_total` | Counter | `pod_name`, `agent_id`, `language` | Total computational concepts extracted by pod worker |
| `pod_worker_extraction_latency_seconds` | Histogram | `pod_name`, `agent_id` | Source code extraction latency for pod worker |
| `pod_worker_agent_execution_latency_seconds` | Histogram | `pod_name`, `agent_id`, `category` | Agent execution latency for pod worker mission handling |
| `pod_worker_agent_heartbeat_attempts_total` | Counter | `pod_name`, `agent_id`, `status` | Total agent heartbeat attempts emitted by pod worker |
| `pod_worker_binding_skips_total` | Counter | `pod_name`, `reason` | Total missions skipped because agent binding did not match |
| `pod_worker_internal_auth_rejections_total` | Counter | `pod_name` | Total orchestrator internal endpoint auth rejections observed by pod worker |

## `services/audit-worker/audit_worker/main.py`

| Metric | Type | Labels | Purpose |
|---|---|---|---|
| `audit_worker_tasks_processed_total` | Counter | `agent_id`, `event_type` | Total mission events processed by audit worker |
| `audit_worker_tasks_failed_total` | Counter | `agent_id`, `event_type` | Total mission events failed by audit worker |
| `audit_worker_task_latency_seconds` | Histogram | `agent_id`, `event_type` | Mission event processing latency for audit worker |
| `audit_worker_post_audit_latency_seconds` | Histogram | `agent_id`, `status` | Latency for audit-worker writes to orchestrator |

## `services/agent-runtime/agent_runtime/main.py`

| Metric | Type | Labels | Purpose |
|---|---|---|---|
| `agent_runtime_tasks_processed_total` | Counter | `agent_id` | Total mission events processed by dedicated agent runtime |
| `agent_runtime_tasks_failed_total` | Counter | `agent_id` | Total mission events failed by dedicated agent runtime |
| `agent_runtime_task_latency_seconds` | Histogram | `agent_id` | Mission event processing latency for dedicated agent runtime |
| `agent_runtime_execution_latency_seconds` | Histogram | `agent_id`, `category` | Agent execution latency for dedicated agent runtime |
| `agent_runtime_heartbeat_attempts_total` | Counter | `agent_id`, `status` | Total heartbeat attempts emitted by dedicated agent runtime |
| `agent_runtime_circuit_open_total` | Counter | `agent_id` | Total circuit breaker trips for dedicated agent runtime |

## Alert Rules — `deploy/monitoring/prometheus/rules/thefactory-alerts.yml`

Real alert names (verified against the file, not the fictional `GatewayDown`/`PostgresDown`/`HighErrorRate`/`HighP95Latency` a prior version of this document listed): `ApiGatewayDown`, `OrchestratorDown`, `ProtocolBusMcpDown`, `PodWorkerDown`, `AuditWorkerDown`, `ApiGateway5xxRateHigh`, `Orchestrator5xxRateHigh`, `ApiGatewayErrorBudgetBurnFast`/`Slow`, `OrchestratorErrorBudgetBurnFast`/`Slow`, `PodWorkerAgentLatencyP99High`, `DedicatedAgentRuntimeLatencyP99High`, `AuditWorkerAgentLatencyP99High`, `MissionStuckInRunning`, `MissionFailureRateHigh`, `Neo4jAdapterNotReady`, `ObjectStorageAdapterNotReady`, `Neo4jMirrorWriteErrorRateHigh`, `ObjectStorageMirrorWriteErrorRateHigh`, `Neo4jMirrorWriteLatencyP95High`, `ObjectStorageMirrorWriteLatencyP95High`.

## Related Docs

- `OBSERVABILITY_STACK.md` — Grafana dashboards and the alerting pipeline these metrics feed
