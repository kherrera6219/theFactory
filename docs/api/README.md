# API Reference

Document version: 2026.03.29  
Last updated: 2026-03-29  
Status: Canonical  
Audience: Integrators, developers, operators, and auditors

`theFactory` ships two primary HTTP APIs backed by FastAPI:

- API Gateway: `http://localhost:8100`
- Orchestrator internal API: `http://localhost:8101`

## Interactive Docs

When the services are running, FastAPI serves interactive docs by default:

- Gateway Swagger UI: `http://localhost:8100/docs`
- Gateway OpenAPI JSON: `http://localhost:8100/openapi.json`
- Orchestrator Swagger UI: `http://localhost:8101/docs`
- Orchestrator OpenAPI JSON: `http://localhost:8101/openapi.json`

## Versioned Specs In Repo

Committed OpenAPI snapshots are stored here:

- [../openapi/api-gateway.v1.json](../openapi/api-gateway.v1.json)
- [../openapi/orchestrator.v1.json](../openapi/orchestrator.v1.json)

Regenerate snapshots after route/schema changes:

```powershell
python scripts/export_openapi.py
```

Check committed snapshots without rewriting them:

```powershell
python scripts/export_openapi.py --check
```

`make validate` runs the non-mutating check so route/spec drift fails before
merge.

## Main Gateway Surfaces

- `POST /v1/missions`
- `GET /v1/missions`
- `GET /v1/missions/{mission_id}`
- `GET /v1/missions/{mission_id}/build-artifacts`
- `GET /v1/missions/{mission_id}/build-artifacts/{artifact_id}`
- `POST /v1/missions/{mission_id}/state`
- `GET /v1/stream/state`
- `GET /v1/operations/summary`
- `GET /v1/operations/agents`
- `GET /v1/operations/logicnodes`
- `GET /v1/operations/projects`

## Auth Modes

The gateway supports:

- `api_key`
- `hybrid`
- `oidc`

See [../API_INTEGRATION_GUIDE.md](../API_INTEGRATION_GUIDE.md) and [../ADR_SECURITY_MODEL_API_KEY_VS_OIDC_2026-03-04.md](../ADR_SECURITY_MODEL_API_KEY_VS_OIDC_2026-03-04.md) for integration details and route protection expectations.

## Notes

- Mutation routes are rate-limited and idempotency-aware.
- Internal orchestration routes require explicit service credentials.
- Gateway and orchestrator routes accept `x-request-id` or `x-correlation-id` and echo the resolved value as `X-Correlation-Id`.
- Review-based Mission Control flows use local Next.js API routes first, then forward validated bundles and durable approval records into orchestrator-backed runtime storage.
- Source-bundle missions now expose a real stored build/package artifact contract through both gateway and orchestrator APIs.
