# Observability Stack

Last updated: 2026-03-03

Baseline observability bundle for local production-like validation.

## Components

- Prometheus (`:9090`) for metrics
- Alertmanager (`:9093`) for alert routing
- Grafana (`:3001`) for dashboards
- Loki (`:3101`) + Promtail for log aggregation
- Jaeger (`:16686`) for distributed tracing

## Start and Stop

From repo root:

- Start: `docker compose -f deploy/docker-compose.monitoring.yaml up -d`
- Stop: `docker compose -f deploy/docker-compose.monitoring.yaml down -v`

## Included Config

- Prometheus scrape config: `deploy/monitoring/prometheus/prometheus.yml`
- Alert rules: `deploy/monitoring/prometheus/rules/thefactory-alerts.yml`
- Alertmanager routes: `deploy/monitoring/alertmanager/alertmanager.yml`
- Release-time tracing endpoint wiring: `deploy/docker-compose.yaml` (`OTEL_EXPORTER_OTLP_TRACES_ENDPOINT`)
- Grafana provisioning:
  - `deploy/monitoring/grafana/provisioning/datasources/datasources.yml`
  - `deploy/monitoring/grafana/provisioning/dashboards/dashboards.yml`
  - `deploy/monitoring/grafana/provisioning/dashboards/json/thefactory-overview.json`

## Validation

1. Ensure app stack is up: `docker compose -f deploy/docker-compose.yaml up -d`.
2. Start monitoring stack.
3. Open Grafana and verify `theFactory Overview` dashboard.
4. Confirm metrics endpoints:
   - `http://localhost:8100/metrics`
   - `http://localhost:8101/metrics`
5. Confirm tracing endpoint:
   - Jaeger UI: `http://localhost:16686`
6. Confirm pager routing configuration:
   - Alertmanager: `http://localhost:9093`
   - Verify `PAGER_WEBHOOK_URL` is set in environment for monitoring stack.
