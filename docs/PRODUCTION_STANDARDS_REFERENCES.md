# Production Standards References

Last updated: 2026-03-02

Official sources used to guide production hardening and runtime governance for theFactory.

## Security and SDLC

- NIST Cybersecurity Framework 2.0:
  - https://www.nist.gov/cyberframework
- NIST AI Risk Management Framework 1.0:
  - https://www.nist.gov/itl/ai-risk-management-framework
- NIST SP 800-218 (Secure Software Development Framework):
  - https://csrc.nist.gov/pubs/sp/800/218/final
- NIST SP 800-61 Rev.3 (Incident Response Recommendations):
  - https://csrc.nist.gov/pubs/sp/800/61/r3/final
- NIST SP 800-53 Rev.5 (and Rev.5.2 update announcement):
  - https://www.nist.gov/news-events/news/2025/09/nist-updates-privacy-and-security-guidelines-safeguard-federal-systems
- OWASP API Security Top 10 (2023):
  - https://owasp.org/API-Security/editions/2023/en/0x11-t10/
- OWASP Top 10 (2021):
  - https://owasp.org/www-project-top-ten/
- OWASP ASVS v5:
  - https://owasp.org/www-project-application-security-verification-standard/
- ISO/IEC 27001:
  - https://www.iso.org/standard/27001
- ISO/IEC 42001:
  - https://www.iso.org/standard/81230.html
- SLSA specification:
  - https://slsa.dev/spec/v1.2/

## Observability and API Design

- OpenTelemetry signals:
  - https://opentelemetry.io/docs/concepts/signals/
- Prometheus instrumentation practices:
  - https://prometheus.io/docs/practices/instrumentation/
- OpenAPI 3.1 specification:
  - https://spec.openapis.org/oas/v3.1.0

## Runtime and Platform Reliability

- Kubernetes liveness/readiness/startup probes:
  - https://kubernetes.io/docs/concepts/configuration/liveness-readiness-startup-probes/
- Kubernetes Pod Security Standards:
  - https://kubernetes.io/docs/concepts/security/pod-security-standards/

## Data Plane and Storage Reliability

- Redis Streams consumer groups:
  - https://redis.io/docs/latest/commands/xreadgroup/
- Redis security:
  - https://redis.io/docs/latest/operate/oss_and_stack/management/security/
- Redis persistence:
  - https://redis.io/docs/latest/operate/oss_and_stack/management/persistence/
- PostgreSQL connection controls:
  - https://www.postgresql.org/docs/current/runtime-config-connection.html
- PostgreSQL WAL archiving and PITR:
  - https://www.postgresql.org/docs/current/continuous-archiving.html
- PostgreSQL TLS:
  - https://www.postgresql.org/docs/current/ssl-tcp.html
- PgBouncer configuration:
  - https://www.pgbouncer.org/config
- Neo4j constraints:
  - https://neo4j.com/docs/cypher-manual/current/constraints/
- Neo4j backup and restore:
  - https://neo4j.com/docs/operations-manual/current/backup-restore/
- Amazon S3 Object Lock:
  - https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html
- Amazon S3 consistency model:
  - https://docs.aws.amazon.com/AmazonS3/latest/userguide/Welcome.html

## LLM Provider and Model Governance

- OpenAI model catalog:
  - https://platform.openai.com/docs/models
- OpenAI reasoning controls:
  - https://platform.openai.com/docs/guides/reasoning
- OpenAI pricing:
  - https://platform.openai.com/docs/pricing
- Anthropic models overview:
  - https://docs.anthropic.com/en/docs/about-claude/models/overview
- Anthropic Messages API:
  - https://docs.anthropic.com/en/api/messages
- Gemini models catalog:
  - https://ai.google.dev/gemini-api/docs/models
- Gemini thinking guide:
  - https://ai.google.dev/gemini-api/docs/thinking
- Gemini pricing:
  - https://ai.google.dev/gemini-api/docs/pricing
