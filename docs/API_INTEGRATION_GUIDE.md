# API Integration Guide

Last updated: 2026-03-04

## Core Endpoints

Gateway base: `http://localhost:8100`

- `POST /v1/missions`
- `GET /v1/missions`
- `GET /v1/missions/{mission_id}`
- `GET /v1/missions/{mission_id}/events`
- `POST /v1/missions/{mission_id}/state`
- `GET /v1/operations/summary`
- `GET /v1/operations/agents`
- `GET /v1/operations/agent-integrations`

Semantic Bus MCP base: `http://localhost:8102`

- `POST /send`
- `GET /health`
- `GET /metrics`
- `GET /dlq?protocol=<alpha|beta|delta|sigma|omega|rho>`

## Authentication

- Mission state mutation uses `x-api-key`.
- MCP message publish uses:
  - `x-api-key` (MCP service key)
  - `x-agent-id` (must match message sender)

### Security ADR Alignment

Canonical auth decision record:
- `docs/ADR_SECURITY_MODEL_API_KEY_VS_OIDC_2026-03-04.md`

Accepted runtime policy:
1. `api_key` mode (current default): API-key auth for local/single-tenant operation.
2. `hybrid` mode (planned): JWT/OIDC for operator/public API requests plus API-key internal service flows.
3. `oidc` mode (planned): JWT/OIDC required for operator/public APIs; API keys limited to internal service identity.

Current implementation baseline remains API-key-first; JWT/OIDC is a planned enterprise extension path.

## Mission Intake Example

```bash
curl -X POST http://localhost:8100/v1/missions \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: sample-1" \
  -d "{\"prompt\":\"Build a service\",\"requested_target_language\":\"python\",\"metadata\":{\"source\":\"api-guide\"}}"
```

## MCP Send Example

```bash
curl -X POST http://localhost:8102/send \
  -H "Content-Type: application/json" \
  -H "x-api-key: mcp-local-key" \
  -H "x-agent-id: AGENT-02-CEO" \
  -d "{\"schema_version\":\"v1\",\"protocol\":\"alpha\",\"sender\":\"AGENT-02-CEO\",\"recipient\":\"AGENT-12-PODA-MGR\",\"priority\":\"high\",\"payload\":{\"schema_version\":\"v1\",\"priority\":\"high\",\"target_pod\":\"podA\",\"directive_type\":\"mission_assignment\",\"directive\":{\"mission_id\":\"mission-1\"}}}"
```

## Error Conventions

- `400`: malformed JSON or bad request shape.
- `413`: payload exceeds 1MB limit.
- `422`: schema validation failed.
- `503`: dependency unavailable (typically Redis).
