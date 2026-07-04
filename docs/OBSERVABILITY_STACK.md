# Observability Stack

Document version: 2026.07.03  
Last updated: 2026-07-03  
Status: Canonical  
Audience: Operators, maintainers, and SRE/DevOps reviewers

## Table of Contents

- [Component Overview](#component-overview)
- [Quick Start](#quick-start)
- [Metrics Catalog](#metrics-catalog)
- [Alert Rules](#alert-rules)
- [Distributed Tracing](#distributed-tracing)
- [Log Aggregation](#log-aggregation)
- [Dashboards](#dashboards)
- [Pager / Incident Routing](#pager--incident-routing)
- [Configuration Files](#configuration-files)
- [Validation Checklist](#validation-checklist)

---

## Component Overview

| Component | Port | Purpose |
|-----------|------|---------|
| **Prometheus** | 9090 | Metrics collection, alerting, TSDB |
| **Grafana** | 3001 | Dashboards and visualization (credentials via `GRAFANA_ADMIN_USER`/`GRAFANA_ADMIN_PASSWORD` env vars — `docker-compose.monitoring.yaml` explicitly never defaults to admin/admin) |
| **Alertmanager** | 9093 | Alert routing and pager dispatch |
| **Loki** | 3101 | Centralized log aggregation |
| **Promtail** | — | Log shipping agent (runs alongside services) |
| **Jaeger** | 16686 | Distributed trace collection and search |

---

## Quick Start

```bash
# Start monitoring stack
docker compose -f deploy/docker-compose.monitoring.yaml up -d

# Stop and clean up
docker compose -f deploy/docker-compose.monitoring.yaml down -v

# Via make
make monitor-up
make monitor-down
```

Verify all components are up:

```bash
# Prometheus
curl http://localhost:9090/-/ready

# Alertmanager
curl http://localhost:9093/-/ready

# Grafana
curl http://localhost:3001/api/health

# Jaeger
curl http://localhost:16686/
```

---

## Metrics Catalog

**Corrected 2026-07-03** — the metric names below were fictional in a prior version of this document (`http_requests_total`, `missions_created_total`, `sse_connections_active`, `mission_state_transitions_total`, `pod_assignments_total`, `langgraph_executions_total`, `agent_heartbeats_total` do not exist). See `METRICS_SOURCE_MODULES.md` for the full, source-verified list; the tables below are a summary.

### API Gateway Metrics (`:8100/metrics`)

| Metric | Type | Description |
|--------|------|-------------|
| `api_gateway_http_requests_total` | Counter | Total HTTP requests by method, path, status_code |
| `api_gateway_http_request_duration_seconds` | Histogram | Request latency distribution |
| `api_gateway_live_stream_connections_total` | Counter | Total SSE live-stream connections accepted |
| `api_gateway_live_stream_events_total` | Counter | SSE events emitted, by event_type |
| `api_gateway_live_stream_errors_total` | Counter | Live-stream errors observed, by reason |
| `factory_auth_failures_total` | Counter | Auth failures by reason and route_prefix |

### Orchestrator Metrics (`:8101/metrics`)

| Metric | Type | Description |
|--------|------|-------------|
| `orchestrator_http_requests_total` | Counter | Total HTTP requests by method, path, status_code |
| `orchestrator_http_request_duration_seconds` | Histogram | Request latency distribution |
| `llm_fallback_total` | Counter | Silent LLM fallbacks by agent_id and reason |
| `factory_mission_transitions_total` | Counter | Mission state transitions by from_state/to_state/engine |
| `factory_mission_outcomes_total` | Counter | Terminal mission outcomes (complete/failed/timeout) |
| `factory_missions_active` | Gauge | Active missions by state (queued/running/verified) |
| `factory_mission_duration_seconds` | Histogram | Mission duration from intake to terminal state |
| `factory_mission_last_transition_timestamp` | Gauge | Unix timestamp of the most recent transition (feeds `MissionStuckInRunning`) |

### Optional Data-Plane Metrics (when `MILVUS_ENABLED`, `NEO4J_ENABLED`, or `OBJECT_STORAGE_ENABLED`)

| Metric | Type | Description |
|--------|------|-------------|
| `orchestrator_optional_adapter_enabled{adapter}` | Gauge | 1 if adapter is configured |
| `orchestrator_optional_adapter_ready{adapter}` | Gauge | 1 if adapter is reachable |
| `orchestrator_optional_adapter_operations_total{adapter,operation,status}` | Counter | Operations by adapter and outcome |
| `orchestrator_optional_adapter_operation_latency_seconds{adapter,operation}` | Histogram | Operation latency |
| `orchestrator_optional_adapter_mirror_writes_total{adapter,artifact,status}` | Counter | Mirror write outcomes |
| `orchestrator_optional_adapter_mirror_write_latency_seconds{adapter,artifact}` | Histogram | Mirror write latency |

### Pod Worker Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `pod_worker_concepts_extracted_total{pod_name,agent_id,language}` | Counter | Concepts extracted per language |
| `pod_worker_extraction_latency_seconds{pod_name,agent_id}` | Histogram | Extraction processing time |
| `pod_worker_task_latency_seconds{pod_name,agent_id}` | Histogram | Per-agent mission handling latency |
| `pod_worker_binding_skips_total{pod_name,reason}` | Counter | Agent binding mismatches skipped |
| `pod_worker_internal_auth_rejections_total{pod_name}` | Counter | 401/403 responses from orchestrator |

### Audit Worker / Dedicated Runtime Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `audit_worker_task_latency_seconds{agent_id,event_type}` | Histogram | Per-agent audit-processing latency |
| `audit_worker_post_audit_latency_seconds{agent_id,status}` | Histogram | Audit write latency to orchestrator |
| `agent_runtime_task_latency_seconds{agent_id}` | Histogram | Dedicated runtime per-agent latency |
| `agent_runtime_execution_latency_seconds{agent_id,category}` | Histogram | Dedicated runtime execution latency |

---

## Alert Rules

Configured in `deploy/monitoring/prometheus/rules/thefactory-alerts.yml`.

### Core Service Alerts

**Corrected 2026-07-03** — `GatewayDown`, `RedisDown`, `PostgresDown`, `HighErrorRate`, and `HighP95Latency` did not exist in `thefactory-alerts.yml`; the real alert names are below.

| Alert | Severity | Condition | Runbook |
|-------|----------|-----------|---------|
| `ApiGatewayDown` | critical | api-gateway health endpoint unreachable | `OPERATIONS_RUNBOOK.md` |
| `OrchestratorDown` | critical | orchestrator health endpoint unreachable | `OPERATIONS_RUNBOOK.md` |
| `ProtocolBusMcpDown` | critical | protocol-bus-mcp health endpoint unreachable | `runbooks/protocol_bus_incident_runbook.md` |
| `PodWorkerDown` | critical | pod-worker health endpoint unreachable | `OPERATIONS_RUNBOOK.md` |
| `AuditWorkerDown` | critical | audit-worker health endpoint unreachable | `OPERATIONS_RUNBOOK.md` |
| `ApiGateway5xxRateHigh` | high | api-gateway 5xx error rate elevated | `OPERATIONS_RUNBOOK.md` |
| `Orchestrator5xxRateHigh` | high | orchestrator 5xx error rate elevated | `OPERATIONS_RUNBOOK.md` |
| `MissionStuckInRunning` | high | `factory_mission_last_transition_timestamp` stale while a mission remains in `RUNNING` | `OPERATIONS_RUNBOOK.md` |
| `MissionFailureRateHigh` | high | `factory_mission_outcomes_total{outcome="failed"}` rate elevated | `OPERATIONS_RUNBOOK.md` |

### Optional Data-Plane Alerts

| Alert | Severity | Condition | Runbook |
|-------|----------|-----------|---------|
| `Neo4jAdapterNotReady` | high | `orchestrator_optional_adapter_ready{adapter="neo4j"} == 0` for > 2m | `optional_data_plane_incident_runbook.md` |
| `ObjectStorageAdapterNotReady` | high | `orchestrator_optional_adapter_ready{adapter="object_storage"} == 0` for > 2m | `optional_data_plane_incident_runbook.md` |
| `Neo4jMirrorWriteErrorRateHigh` | high | Mirror write error rate > 5% for > 5m | `optional_data_plane_incident_runbook.md` |
| `ObjectStorageMirrorWriteErrorRateHigh` | high | Mirror write error rate > 5% for > 5m | `optional_data_plane_incident_runbook.md` |
| `Neo4jMirrorWriteLatencyP95High` | high | p95 latency > 2s for > 5m | `optional_data_plane_incident_runbook.md` |
| `ObjectStorageMirrorWriteLatencyP95High` | high | p95 latency > 2s for > 5m | `optional_data_plane_incident_runbook.md` |

### SLO / Per-Agent Alerts

| Alert | Severity | Condition | Runbook |
|-------|----------|-----------|---------|
| `ApiGatewayErrorBudgetBurnFast` | critical | Fast error-budget burn threshold exceeded | `OPERATIONS_RUNBOOK.md` |
| `ApiGatewayErrorBudgetBurnSlow` | high | Slow error-budget burn threshold exceeded | `OPERATIONS_RUNBOOK.md` |
| `OrchestratorErrorBudgetBurnFast` | critical | Fast error-budget burn threshold exceeded | `OPERATIONS_RUNBOOK.md` |
| `OrchestratorErrorBudgetBurnSlow` | high | Slow error-budget burn threshold exceeded | `OPERATIONS_RUNBOOK.md` |
| `PodWorkerAgentLatencyP99High` | high | Per-agent pod-worker p99 latency exceeds threshold | `OPERATIONS_RUNBOOK.md` |
| `DedicatedAgentRuntimeLatencyP99High` | high | Dedicated runtime p99 latency exceeds threshold | `OPERATIONS_RUNBOOK.md` |
| `AuditWorkerAgentLatencyP99High` | high | Audit worker per-agent p99 latency exceeds threshold | `OPERATIONS_RUNBOOK.md` |

All `critical` and `high` alerts route to the pager webhook receiver in Alertmanager.

---

## Distributed Tracing

### Instrumented Services

| Service | Status |
|---------|--------|
| api-gateway | ✅ OTel OTLP traces to Jaeger |
| orchestrator | ✅ OTel OTLP traces to Jaeger |
| pod-worker | ✅ OTel OTLP traces to Jaeger |
| audit-worker | ✅ OTel OTLP traces to Jaeger |
| protocol-bus-mcp | ✅ OTel OTLP traces to Jaeger |
| dashboard | ✅ OTel OTLP traces to Jaeger |
| agent-runtime | ✅ OTel OTLP traces to Jaeger when the full dedicated profile is active |

### OTel Configuration

Each instrumented service sets:
```bash
OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://jaeger:4317
OTEL_SERVICE_NAME=<service-name>
```

Configured via `configure_tracing(app, service_name="<name>")` in each service's `main.py`.

### Using Jaeger

1. Open Jaeger UI: `http://localhost:16686`
2. Select service from dropdown (api-gateway · orchestrator · pod-worker · audit-worker · protocol-bus-mcp · dashboard · agent-runtime)
3. Search by `mission_id` tag to trace a specific mission end-to-end
4. View spans across service boundaries to identify latency contributors

---

## Log Aggregation

### Loki + Promtail

Promtail ships container logs from Docker's log driver to Loki. All service logs are queryable in Grafana via the **Explore → Loki** data source.

**Useful LogQL queries:**

```logql
# All errors from api-gateway
{container="api-gateway"} |= "error"

# Mission creation events
{container="orchestrator"} |= "mission" |= "created"

# Pod worker extraction events
{container="pod-worker"} |= "extracted"

# All 5xx responses
{job="theFactory"} |= "HTTP 5"
```

---

## Dashboards

### theFactory Overview (`thefactory-overview.json`)

The provisioned Grafana dashboard includes:

| Panel | Metric |
|-------|--------|
| Request rate (req/s) | `rate(api_gateway_http_requests_total[5m])` |
| p95 latency | `histogram_quantile(0.95, rate(api_gateway_http_request_duration_seconds_bucket[5m]))` |
| Error rate | `rate(api_gateway_http_requests_total{status_code=~"5.."}[5m]) / rate(api_gateway_http_requests_total[5m])` |
| Error Budget Burn (x) | Fast/slow burn-rate queries for gateway + orchestrator |
| Active missions | Mission state gauge |
| Agent heartbeat age | Latest heartbeat timestamps |
| Optional data-plane mirror writes | `rate(orchestrator_optional_adapter_mirror_writes_total[5m])` |
| Pod worker extraction rate | `rate(pod_worker_concepts_extracted_total[5m])` |
| Per-Agent Task p99 (s) | `topk(10, histogram_quantile(0.99, ... pod_worker_task_latency_seconds_bucket ...))` |
| Dedicated Runtime Agent p99 (s) | `topk(10, histogram_quantile(0.99, ... agent_runtime_task_latency_seconds_bucket ...))` |

### Qualification Evidence

- Weekly qualification emits `docs/evidence/dora_metrics_latest.json`.
- Promotion and qualification gating consume the same observability evidence set used by CI.

### Importing Additional Dashboards

Grafana dashboards are auto-provisioned from:
`deploy/monitoring/grafana/provisioning/dashboards/json/`

Add new JSON dashboard files there and restart the monitoring stack.

---

## Pager / Incident Routing

### Alert Flow

```
Prometheus Alert Rules
       ↓ (fires)
  Alertmanager
       ↓ (routes by severity)
  severity=critical|high → pager receiver
  severity=low|info     → default receiver (silent/log)
       ↓
  PAGER_WEBHOOK_URL (configurable)
```

### Configuration

Set `PAGER_WEBHOOK_URL` in the monitoring stack environment:

```bash
# In .env or monitoring compose env
PAGER_WEBHOOK_URL=https://your-pagerduty-or-slack-webhook-url
```

Verify routing is configured:

```bash
docker compose -f deploy/docker-compose.monitoring.yaml exec alertmanager \
  printenv PAGER_WEBHOOK_URL

curl http://localhost:9093/api/v2/receivers
```

Alertmanager config: `deploy/monitoring/alertmanager/alertmanager.yml`

---

## Configuration Files

| File | Purpose |
|------|---------|
| `deploy/monitoring/prometheus/prometheus.yml` | Scrape targets for all services |
| `deploy/monitoring/prometheus/rules/thefactory-alerts.yml` | Alert rules |
| `deploy/monitoring/alertmanager/alertmanager.yml` | Alert routing and receivers |
| `deploy/monitoring/grafana/provisioning/datasources/datasources.yml` | Prometheus + Loki data sources |
| `deploy/monitoring/grafana/provisioning/dashboards/dashboards.yml` | Dashboard provisioning config |
| `deploy/monitoring/grafana/provisioning/dashboards/json/thefactory-overview.json` | Main dashboard |

---

## Validation Checklist

Run after starting the monitoring stack:

- [ ] `curl http://localhost:9090/-/ready` returns `200`
- [ ] `curl http://localhost:9093/-/ready` returns `200`
- [ ] Grafana loads at `http://localhost:3001` and shows `theFactory Overview` dashboard
- [ ] `curl http://localhost:8100/metrics` returns Prometheus-format metrics
- [ ] `curl http://localhost:8101/metrics` returns Prometheus-format metrics
- [ ] Jaeger UI at `http://localhost:16686` shows the instrumented services for the active profile
- [ ] `PAGER_WEBHOOK_URL` is set for pager routing
- [ ] At least one test alert fired and delivered (use Alertmanager `/api/v2/alerts` to inject)
