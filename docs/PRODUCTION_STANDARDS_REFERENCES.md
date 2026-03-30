# Production Standards References

Document version: 2026.03.29  
Last updated: 2026-03-29  
Status: Canonical  
Audience: Maintainers, auditors, security reviewers, and technical leads

Official external standards and primary-source guidance used to drive completion planning, production hardening, AI governance, and release qualification for theFactory.

## Security and Secure SDLC

- NIST Cybersecurity Framework 2.0
  - https://www.nist.gov/cyberframework
- NIST SP 800-218, Secure Software Development Framework (SSDF) Version 1.1
  - https://csrc.nist.gov/pubs/sp/800/218/final
- NIST SP 800-61 Rev. 3, Incident Response Recommendations and Considerations for Cybersecurity Risk Management
  - https://csrc.nist.gov/pubs/sp/800/61/r3/final
- NIST SP 800-34 Rev. 1, Contingency Planning Guide for Federal Information Systems
  - https://nvlpubs.nist.gov/nistpubs/legacy/sp/nistspecialpublication800-34r1.pdf
- CISA Secure by Design
  - https://www.cisa.gov/securebydesign
- NCSC secure build and deployment pipeline guidance
  - https://www.ncsc.gov.uk/collection/developers-collection/principles/secure-the-build-and-deployment-pipeline

## Application and API Security

- OWASP Top 10 (2021)
  - https://owasp.org/www-project-top-ten/
- OWASP API Security Top 10 (2023)
  - https://owasp.org/API-Security/editions/2023/en/0x11-t10/
- OWASP ASVS
  - https://owasp.org/www-project-application-security-verification-standard/
- OpenAPI 3.1 specification
  - https://spec.openapis.org/oas/v3.1.0

## AI Governance, Safety, and Evaluation

- NIST AI Risk Management Framework 1.0
  - https://www.nist.gov/itl/ai-risk-management-framework
- NIST AI RMF Playbook
  - https://airc.nist.gov/AI_RMF_Knowledge_Base/AI_RMF
- NIST AI 600-1, Generative AI Profile
  - https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-generative-artificial-intelligence
- OWASP Top 10 for LLM Applications
  - https://owasp.org/www-project-top-10-for-large-language-model-applications/
- NCSC Guidelines for Secure AI System Development
  - https://www.ncsc.gov.uk/collection/guidelines-secure-ai-system-development
- NCSC Secure Deployment guidance for AI systems
  - https://www.ncsc.gov.uk/collection/guidelines-secure-ai-system-development/guidelines/secure-deployment

## Supply Chain, Release Trust, and Provenance

- SLSA
  - https://slsa.dev/
- GitHub artifact attestations
  - https://docs.github.com/en/actions/security-for-github-actions/using-artifact-attestations/using-artifact-attestations-to-establish-provenance-for-builds
- GitHub dependency review
  - https://docs.github.com/code-security/supply-chain-security/understanding-your-software-supply-chain/about-dependency-review
- GitHub secret scanning
  - https://docs.github.com/code-security/secret-scanning/introduction/about-secret-scanning

## Observability and Reliability

- OpenTelemetry concepts and signals
  - https://opentelemetry.io/docs/concepts/signals/
- OpenTelemetry semantic conventions
  - https://opentelemetry.io/docs/specs/semconv/
- Prometheus instrumentation practices
  - https://prometheus.io/docs/practices/instrumentation/

## Data Stores, Durability, and Recovery

- Redis Streams consumer groups
  - https://redis.io/docs/latest/commands/xreadgroup/
- Redis security
  - https://redis.io/docs/latest/operate/oss_and_stack/management/security/
- Redis persistence
  - https://redis.io/docs/latest/operate/oss_and_stack/management/persistence/
- PostgreSQL continuous archiving and point-in-time recovery
  - https://www.postgresql.org/docs/current/continuous-archiving.html
- PostgreSQL TLS
  - https://www.postgresql.org/docs/current/ssl-tcp.html
- PgBouncer configuration
  - https://www.pgbouncer.org/config
- Neo4j backup and restore
  - https://neo4j.com/docs/operations-manual/current/backup-restore/
- Amazon S3 Object Lock
  - https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html

## Frontend Quality and Accessibility

- Web Content Accessibility Guidelines (WCAG)
  - https://www.w3.org/WAI/standards-guidelines/wcag/
- Playwright best practices
  - https://playwright.dev/docs/best-practices

## Documentation and Architecture Communication

- Diataxis
  - https://diataxis.fr/
- Microsoft Writing Style Guide
  - https://learn.microsoft.com/en-us/style-guide/welcome/
- Google developer documentation style guide
  - https://developers.google.com/style
- Write the Docs software documentation guide
  - https://www.writethedocs.org/guide/
- C4 model
  - https://c4model.com/

## LLM Provider References

- OpenAI models
  - https://platform.openai.com/docs/models
- OpenAI reasoning guide
  - https://platform.openai.com/docs/guides/reasoning
- Anthropic Claude models overview
  - https://docs.anthropic.com/en/docs/about-claude/models/overview
- Anthropic Messages API
  - https://docs.anthropic.com/en/api/messages
- Gemini models
  - https://ai.google.dev/gemini-api/docs/models
- Gemini thinking guide
  - https://ai.google.dev/gemini-api/docs/thinking
