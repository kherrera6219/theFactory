# Production Standards References

Reviewed on 2026-02-28 to guide production hardening for theFactory.

## Security and SDLC

- OWASP API Security Top 10 (2023): https://owasp.org/API-Security/editions/2023/en/0x11-t10/
- NIST SP 800-218 (Secure Software Development Framework): https://csrc.nist.gov/pubs/sp/800/218/final
- NIST SP 800-61r3 (Incident Response): https://csrc.nist.gov/pubs/sp/800/61/r3/final
- SLSA specification (supply-chain levels): https://slsa.dev/spec/v1.2/

## Observability and API Design

- OpenTelemetry signals (metrics/logs/traces): https://opentelemetry.io/docs/concepts/signals/
- Prometheus instrumentation practices: https://prometheus.io/docs/practices/instrumentation/
- OpenAPI 3.1 specification: https://spec.openapis.org/oas/v3.1.0

## Runtime and Platform Reliability

- Kubernetes liveness/readiness/startup probes: https://kubernetes.io/docs/concepts/configuration/liveness-readiness-startup-probes/
- Kubernetes Pod Security Standards: https://kubernetes.io/docs/concepts/security/pod-security-standards/

## Data Plane and Storage Reliability

- Redis Streams consumer groups: https://redis.io/docs/latest/commands/xreadgroup/
- Redis security (ACL, TLS): https://redis.io/docs/latest/operate/oss_and_stack/management/security/
- Redis persistence (RDB/AOF): https://redis.io/docs/latest/operate/oss_and_stack/management/persistence/
- PostgreSQL connection controls: https://www.postgresql.org/docs/current/runtime-config-connection.html
- PostgreSQL WAL archiving and PITR: https://www.postgresql.org/docs/current/continuous-archiving.html
- PostgreSQL TLS: https://www.postgresql.org/docs/current/ssl-tcp.html
- PgBouncer configuration: https://www.pgbouncer.org/config
- Neo4j constraints and integrity rules: https://neo4j.com/docs/cypher-manual/current/constraints/
- Neo4j backup and restore: https://neo4j.com/docs/operations-manual/current/backup-restore/
- Amazon S3 Object Lock (immutable retention): https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html
- Amazon S3 data consistency model: https://docs.aws.amazon.com/AmazonS3/latest/userguide/Welcome.html

## LLM Provider and Model Governance

- OpenAI model catalog: https://platform.openai.com/docs/models
- OpenAI reasoning controls: https://platform.openai.com/docs/guides/reasoning
- OpenAI pricing: https://platform.openai.com/docs/pricing
- Anthropic models overview: https://docs.anthropic.com/en/docs/about-claude/models/overview
- Anthropic Messages API: https://docs.anthropic.com/en/api/messages
- Gemini models catalog: https://ai.google.dev/gemini-api/docs/models
- Gemini thinking guide: https://ai.google.dev/gemini-api/docs/thinking
- Gemini pricing: https://ai.google.dev/gemini-api/docs/pricing
