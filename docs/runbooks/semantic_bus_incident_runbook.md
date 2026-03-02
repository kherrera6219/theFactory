# Semantic Bus Incident Runbook

Last updated: 2026-03-02

## Scope

Operational response for Redis/MCP message-routing incidents.

## Detection Signals

- `SemanticBusMcpDown` alert.
- `PodWorkerDown` or `AuditWorkerDown` alerts.
- Rising DLQ depth from `/dlq` endpoint.

## Triage Steps

1. Check core service health:
   - `curl http://localhost:8102/health`
   - `curl http://localhost:8100/health`
   - `curl http://localhost:8101/health`
2. Inspect compose state:
   - `docker compose -f deploy/docker-compose.yaml ps`
3. Inspect MCP logs:
   - `docker compose -f deploy/docker-compose.yaml logs semantic-bus-mcp --tail 200`
4. Inspect Redis status:
   - `docker compose -f deploy/docker-compose.yaml logs redis --tail 200`

## Recovery Actions

1. Restart MCP service:
   - `docker compose -f deploy/docker-compose.yaml restart semantic-bus-mcp`
2. If Redis unhealthy, restart redis and dependent workers:
   - `docker compose -f deploy/docker-compose.yaml restart redis pod-a-worker pod-b-worker pod-c-worker pod-d-worker audit-worker`
3. Validate recovery:
   - `curl http://localhost:8102/health`
   - `curl http://localhost:8102/dlq?protocol=alpha`

## Post-Incident

- Record incident timeline and root cause.
- Capture message loss risk window and recovery confirmation.
- Create follow-up task for automation if manual step was required.
