# Migration Guide

## `semantic-bus` → `protocol-bus` rename (#190)

The communications bus service was renamed from **semantic-bus** to **protocol-bus**
to match its actual behavior. Message routing is performed by lexical channel-string
concatenation (`protocol:{proto}:{recipient|broadcast}`), not semantic/embedding-based
matching. The old name implied a capability the service does not have.

> Note: this rename targets the *communications bus* only. Components that perform
> genuine semantic work (LogicNode extraction, Refined-IR, the pod-worker extraction
> engine) are unaffected and keep their "semantic" terminology.

### What changed

| Area | Before | After |
|---|---|---|
| Service directory | `services/semantic-bus-mcp/` | `services/protocol-bus-mcp/` |
| Python package | `semantic_bus` | `protocol_bus` |
| Docker Compose service | `semantic-bus-mcp` | `protocol-bus-mcp` |
| Docker network host | `semantic-bus-mcp:8090` | `protocol-bus-mcp:8090` |
| Prometheus job / target | `semantic-bus-mcp` | `protocol-bus-mcp` |
| Prometheus metric prefix | `semantic_bus_mcp_*` | `protocol_bus_mcp_*` |
| Alert rule | `SemanticBusMcpDown` | `ProtocolBusMcpDown` |
| Mission Control UI route | `/semantic-bus` | `/protocol-bus` |
| Schema title | `SemanticBusEventEnvelope` | `ProtocolBusEventEnvelope` |
| Runbook | `docs/runbooks/semantic_bus_incident_runbook.md` | `docs/runbooks/protocol_bus_incident_runbook.md` |

The HTTP API surface (`/send`, `/dlq`, `/health`, `/readyz`, `/metrics`), ports (`8090`
internal, `8102` host), environment variables (`MCP_*`), and the six-protocol channel
naming (`protocol:{proto}:{recipient}`) are **unchanged**.

### Action required for external integrators

- Update any container/network references from `semantic-bus-mcp` to `protocol-bus-mcp`.
- Update Prometheus/Grafana queries that reference `semantic_bus_mcp_*` metric names or
  the `job="semantic-bus-mcp"` label to their `protocol_bus_mcp_*` / `protocol-bus-mcp`
  equivalents.
- Update bookmarks/links pointing at the Mission Control `/semantic-bus` page.

No payload, schema-field, or wire-protocol changes are required.

### Reserved schema field

`SigmaPayload.embedding_ref` remains in the schema but is **reserved for future semantic
routing**. It is not computed, stored, or matched anywhere today. Do not rely on it.
