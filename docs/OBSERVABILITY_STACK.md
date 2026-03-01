# Observability Stack

Baseline observability bundle for local production-like validation.

## Components

- Prometheus (`:9090`) for metrics
- Alertmanager (`:9093`) for alert routing
- Grafana (`:3001`) for dashboards
- Loki (`:3101`) + Promtail for log aggregation

## Start and Stop

From repo root:

- Start: `docker compose -f deploy/docker-compose.monitoring.yaml up -d`
- Stop: `docker compose -f deploy/docker-compose.monitoring.yaml down -v`

## Included Config

- Prometheus scrape config: `deploy/monitoring/prometheus/prometheus.yml`
- Alert rules: `deploy/monitoring/prometheus/rules/thefactory-alerts.yml`
- Alertmanager routes: `deploy/monitoring/alertmanager/alertmanager.yml`
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
