# Architecture Snapshot

## Runtime topology

- API Gateway: mission intake and external contract boundary
- Orchestrator: mission lifecycle state machine and pod coordination
- Dashboard: operational visibility for health and status snapshots
- Worker services: podA/podB/podC/podD + audit worker
- Semantic data plane: Redis, Postgres, Qdrant
- Observability plane: Prometheus, Alertmanager, Grafana, Loki, Promtail

## Contracts

- `schemas/event.envelope.schema.json`: semantic bus envelope
- `schemas/logicnode.schema.json`: extracted language-agnostic logic unit
- `schemas/rir.module.schema.json` and `schemas/rir.fn.schema.json`: refined IR

## Production baseline controls

1. Gateway/orchestrator expose `health`, `readyz`, and `metrics`.
2. Gateway mission intake supports `Idempotency-Key` replay protection.
3. Gateway enforces rate limiting and security response headers.
4. CI/security workflows run lint/test/coverage, dependency/SAST/secret/container scans, and SBOM generation.
5. Operations scripts support predeploy checks, backups, restore, DR drill, and perf smoke.

## Next implementation layers

1. Add token-based auth and scoped external API identities.
2. Add distributed tracing instrumentation and ingestion backend.
3. Add signed release attestations and gated environment promotion.
4. Add long-duration scale tests and capacity thresholds.
