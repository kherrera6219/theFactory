# Optional Data-Plane Incident Runbook

Last updated: 2026-03-04

This runbook covers alert response for feature-flagged Neo4j and object-storage adapters.

## Trigger Alerts

- `Neo4jAdapterNotReady`
- `ObjectStorageAdapterNotReady`
- `Neo4jMirrorWriteErrorRateHigh`
- `ObjectStorageMirrorWriteErrorRateHigh`
- `Neo4jMirrorWriteLatencyP95High`
- `ObjectStorageMirrorWriteLatencyP95High`

## Triage

1. Verify runtime flags in orchestrator:
   - `curl http://localhost:8101/health | jq ".neo4j_ready, .object_storage_ready"`
2. Inspect adapter metrics:
   - `curl http://localhost:8101/metrics | rg "orchestrator_optional_adapter_(ready|operations_total|mirror_writes_total|mirror_write_latency_seconds)"`
3. Confirm backing service availability:
   - Neo4j: `docker compose -f deploy/docker-compose.yaml ps neo4j`
   - MinIO: `docker compose -f deploy/docker-compose.yaml ps minio`
4. Check orchestrator logs for adapter errors:
   - `docker compose -f deploy/docker-compose.yaml logs orchestrator --tail 200`

## Mitigation

1. If outage is transient:
   - restart adapter service and orchestrator.
2. If adapter remains unhealthy:
   - disable adapter feature flag temporarily:
     - `NEO4J_ENABLED=false` and/or `OBJECT_STORAGE_ENABLED=false`
   - redeploy orchestrator.
3. Validate recovery:
   - `curl http://localhost:8101/readyz`
   - confirm alert resolves in Alertmanager (`http://localhost:9093`).

## Recovery Verification

1. Submit a mission and confirm no lifecycle regression.
2. For Neo4j-enabled recovery:
   - `GET /v1/missions/{mission_id}/knowledge-graph` returns records (or clean empty if none).
3. For object-storage-enabled recovery:
   - `GET /v1/missions/{mission_id}/audit-artifacts` returns records (or clean empty if none).
