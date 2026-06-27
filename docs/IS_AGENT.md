# IS Agent — Integration Specialist

Last updated: 2026-06-27

Document version: 2026.06.11  
Status: Canonical  
Audience: Developers, architects, and operators

## Overview

`is_agent.py` (21 KB, `services/orchestrator/orchestrator/is_agent.py`) implements **AGENT-IS**, the Integration Specialist. The IS Agent is the orchestrator's primary boundary-crossing worker. It is responsible for all interactions with external systems, third-party APIs, and inter-service communication that take place during a mission. It is the only agent class permitted to open outbound network connections during live mission execution.

## Responsibilities

| Responsibility | Description |
|---|---|
| External API invocation | Constructs, signs, and executes HTTP/gRPC calls to external services on behalf of mission workers |
| Response normalization | Maps heterogeneous external response shapes to internal `IntegrationResult` dataclass |
| Retry and circuit-break | Applies exponential backoff and circuit-breaker state machine before signalling failure to the mission flow |
| Credential injection | Pulls short-lived credentials from the key-isolation layer (`AGENT_SERVICE_KEY_ISOLATION.md`) — never reads env vars directly |
| Audit event emission | Emits an `INTEGRATION_CALLED` and `INTEGRATION_RESULT` event pair to the audit stream for every external call |
| Timeout enforcement | Enforces a per-integration wall-time ceiling; exceeded calls are cancelled and reported as `INTEGRATION_TIMEOUT` |

## Code Location

```
services/orchestrator/orchestrator/is_agent.py   # 21 KB — agent class and integration runners
```

**Related files:**

| File | Relationship |
|---|---|
| `agent_base.py` | Parent class — IS Agent extends `AgentBase` |
| `agent_integrations.py` | Integration catalogue — maps integration keys to endpoint configs |
| `audit_events.py` | Audit event schema consumed by IS Agent |
| `AGENT_SERVICE_KEY_ISOLATION.md` | Key-isolation policy that IS Agent enforces |
| `SENSITIVE_CODE_HANDLING_POLICY.md` | Governs which integrations are permitted for sensitive missions |

## Architecture: Integration Call Flow

```
Mission Flow v2
     │
     ▼
 IS Agent.execute(integration_key, payload)
     │
     ├─► credential_resolver()        ← key-isolation layer
     │
     ├─► IntegrationCatalogue.get()   ← agent_integrations.py
     │         returns: endpoint, method, auth_scheme, timeout_ms
     │
     ├─► circuit_breaker.check()      ← per-key state machine
     │
     ├─► HTTP/gRPC call (with retry)
     │
     ├─► response_normalizer()
     │         returns: IntegrationResult(status, body, latency_ms, integration_key)
     │
     └─► audit_emitter.emit(INTEGRATION_CALLED, INTEGRATION_RESULT)
```

## Key Dataclass: `IntegrationResult`

```python
@dataclass
class IntegrationResult:
    integration_key: str        # e.g. "GITHUB_PUSH", "NPM_RESOLVE"
    status: Literal["ok", "error", "timeout", "circuit_open"]
    body: dict | str | None
    latency_ms: int
    attempt_count: int          # number of attempts before success or final failure
    error_detail: str | None
```

## Retry Policy

- **Max attempts:** 3 (configurable via `settings.py` → `IS_AGENT_MAX_RETRY`)
- **Backoff:** `100ms × 2^attempt` with ±20% jitter
- **Circuit-breaker threshold:** 5 consecutive failures opens the circuit for 60 seconds
- **Wall-time ceiling:** 30 seconds per integration call (overrideable per integration key)

## Adding a New Integration

1. Add the integration key and endpoint config to `agent_integrations.py` (see [AGENT_INTEGRATIONS](./IS_AGENT.md#integration-catalogue))
2. Add required credential keys to `AGENT_SERVICE_KEY_ISOLATION.md`
3. Add a `DATA_CLASSIFICATION` tag to `DATA_CLASSIFICATION_POLICY.md` if the integration touches PII or secrets
4. Write a test in `tests/unit/test_is_agent.py` covering the happy path and timeout path
5. If the integration targets a sensitive-code host, register it in `SENSITIVE_CODE_HANDLING_POLICY.md`

## Integration Catalogue

The full integration catalogue lives in `agent_integrations.py`. The IS Agent
looks up each call by its `integration_key` string at runtime — it never
hardcodes endpoint URLs. This section remains the docs reference until a
dedicated generated catalogue is added.

## Operational Notes

- IS Agent calls are visible in the Grafana **Integration Latency** dashboard panel.
- Circuit-breaker state is stored in Redis under key `is_agent:circuit:<integration_key>`. Manually reset with `DEL is_agent:circuit:<key>` if a false-open occurs after an upstream incident.
- Audit events for IS Agent are tagged `agent_class=IS` and can be filtered in the evidence bundle.
