# Data Classification Policy

Document version: 2026.03.29  
Last updated: 2026-03-29  
Status: Canonical  
Audience: Operators, developers, maintainers, and security reviewers

## Table of Contents

- [Purpose and Scope](#purpose-and-scope)
- [Classification Levels](#classification-levels)
- [Data Inventory](#data-inventory)
- [Handling Controls by Level](#handling-controls-by-level)
- [Access Control Matrix](#access-control-matrix)
- [Retention and Deletion](#retention-and-deletion)
- [Incident Response](#incident-response)
- [Compliance Alignment](#compliance-alignment)

---

## Purpose and Scope

This policy defines mandatory handling controls for all data created, processed, stored, or transmitted by theFactory. It applies to:

- All runtime services (api-gateway, orchestrator, pod-worker, audit-worker, protocol-bus-mcp, dashboard)
- All data stores (PostgreSQL, Redis, Qdrant, Neo4j, MinIO/S3)
- All operators, developers, and automated systems with access to the platform
- All environments (development, staging, production)

---

## Classification Levels

### Level 1 — PUBLIC

**Definition:** Information intended for unrestricted external sharing.

**Examples:** OpenAPI specifications, architecture documentation, public changelogs.

**Controls:**
- Storage: unrestricted
- Transport: TLS preferred, not required
- Access: no authentication required
- Retention: indefinite

---

### Level 2 — INTERNAL

**Definition:** Operational information not intended for public release. Disclosure would cause minimal harm but violates confidentiality expectations.

**Examples:** Agent telemetry, system metrics, internal operational dashboards, log aggregates.

**Controls:**
- Storage: authenticated systems only
- Transport: TLS required across all service boundaries
- Access: operator-role authentication required
- Retention: 90 days (logs), indefinite for aggregated metrics

---

### Level 3 — CONFIDENTIAL

**Definition:** Customer-originated or mission-specific data. Unauthorized disclosure could cause significant harm to the customer or the platform.

**Examples:** Mission prompts, source code submitted for analysis, extracted LogicNodes, pod assignments, audit artifacts, LangGraph checkpoint state.

**Controls:**
- Storage: encrypted at rest; role-restricted access (operator+)
- Transport: TLS required; data must not appear in plain-text logs
- Access: least-privilege; explicit need-to-know
- Retention: mission lifecycle + 90 days post-completion; deletable on request
- Handling: must not be stored in `.env` files, CI logs, or error messages

---

### Level 4 — RESTRICTED

**Definition:** Credential material, secret keys, compliance-sensitive records. Unauthorized access directly enables security compromise.

**Examples:** API keys (gateway, internal service, vault), OIDC client secrets, PostgreSQL credentials, Redis passwords, LLM provider API keys, SBOM signing keys.

**Controls:**
- Storage: encrypted secret stores only (local vault, environment variables in `.env`; never in source code)
- Transport: TLS required; not transmitted in query strings, URL paths, or log output
- Access: absolute least privilege; audited access trail required
- Rotation: API keys rotated on any suspected compromise; provider keys rotated quarterly
- Incident: Any confirmed exposure triggers immediate rotation and incident review

---

## Data Inventory

| Data Type | Level | Storage Location | Handling Notes |
|-----------|-------|-----------------|---------------|
| Mission prompts and source code | CONFIDENTIAL | PostgreSQL (`state_graph`) | No plain-text logging |
| LogicNodes and extracted concepts | CONFIDENTIAL | PostgreSQL (`logicnode_registry`, `knowledge_lake`) | Role-restricted |
| Pod assignments | CONFIDENTIAL | PostgreSQL (`state_graph`) | Role-restricted |
| LangGraph checkpoint state | CONFIDENTIAL | PostgreSQL (checkpointer table) | Encrypted connection |
| Audit artifacts | CONFIDENTIAL | PostgreSQL (`traceability_ledger`) + optional MinIO | Legal-hold eligible |
| Agent telemetry and heartbeats | INTERNAL | Redis (TTL-bounded) + PostgreSQL | 90-day retention |
| System metrics (Prometheus) | INTERNAL | Prometheus TSDB | 30-day default retention |
| Container logs | INTERNAL | Loki | 90-day retention |
| Distributed traces | INTERNAL | Jaeger | 7-day default retention |
| API keys (gateway, service) | RESTRICTED | `.env` / Docker secrets | Never logged |
| LLM provider API keys | RESTRICTED | `.env` / local vault | Never committed |
| OIDC secrets | RESTRICTED | `.env` / secret manager | Rotated quarterly |
| OpenAPI specs | PUBLIC | `docs/openapi/` | Unrestricted |
| Architecture docs | PUBLIC | `docs/` | Unrestricted |

---

## Handling Controls by Level

| Control | PUBLIC | INTERNAL | CONFIDENTIAL | RESTRICTED |
|---------|--------|----------|-------------|------------|
| Encryption at rest | — | Recommended | **Required** | **Required** |
| Encryption in transit (TLS) | Preferred | **Required** | **Required** | **Required** |
| Authentication required | No | **Required** | **Required** | **Required** |
| Logging (contains data) | OK | Aggregates only | **Prohibited** | **Prohibited** |
| Inclusion in error responses | OK | No | **Prohibited** | **Prohibited** |
| Commitment to source control | OK | Config only | **Prohibited** | **Prohibited** |
| Cross-environment transfer | OK | Controlled | Restricted | **Prohibited** |

---

## Access Control Matrix

| Role | PUBLIC | INTERNAL | CONFIDENTIAL | RESTRICTED |
|------|--------|----------|-------------|------------|
| `admin` | ✅ | ✅ | ✅ | Read-only (audit) |
| `operator` | ✅ | ✅ | ✅ Limited | ❌ |
| `reader` | ✅ | ✅ Read-only | Metadata only | ❌ |
| `worker` | ✅ | Write (own) | Write (own mission) | ❌ |
| Unauthenticated | ✅ | ❌ | ❌ | ❌ |

---

## Retention and Deletion

| Data Type | Retention Period | Deletion Trigger |
|-----------|-----------------|-----------------|
| Mission payloads | 90 days post-completion | Customer request or expiry |
| Source code artifacts | 90 days post-completion | Customer request or expiry |
| LogicNodes | 90 days post-mission close | Mission deletion cascade |
| LangGraph checkpoints | Mission duration + 7 days | Auto-cleanup job |
| Audit records (traceability ledger) | 1 year (legal-hold eligible) | Legal review + approval |
| Agent telemetry (Redis) | TTL: 24 hours | Automatic key expiry |
| Prometheus metrics | 30 days | TSDB retention policy |
| Logs (Loki) | 90 days | Log retention policy |
| Distributed traces (Jaeger) | 7 days | Trace retention policy |
| Backup files | 14 days (daily) / 8 weeks (weekly) | Automated cleanup |
| SBOM artifacts | 1 year | Release archival policy |

---

## Incident Response

### Confidential Data Exposure

1. **Contain:** Immediately revoke access to the exposed data path or API key
2. **Assess:** Determine what data was exposed, for how long, and to whom
3. **Notify:** Notify the platform security owner within 1 hour; customer notification within 24 hours if mission data is involved
4. **Remediate:** Rotate credentials, patch the exposure vector, audit logs
5. **Review:** Postmortem within 5 business days; findings documented in `docs/evidence/`

### Restricted Data Exposure (API Keys / Secrets)

1. **Rotate immediately:** All affected keys must be rotated within 15 minutes of discovery
2. **Audit:** Check access logs for evidence of unauthorized use
3. **Scan:** Run gitleaks on repository history to verify no other exposures exist
4. **Review:** Postmortem required regardless of severity

### Reporting

Security incidents should be reported to the platform owner immediately and documented in the incident log.

---

## Compliance Alignment

| Framework | Relevant Controls | Status |
|-----------|------------------|--------|
| **NIST CSF** | PR.DS-1 (data at rest), PR.DS-2 (data in transit), PR.AC-4 (access permissions) | Baseline implemented |
| **NIST AI RMF** | GOVERN-1.1 (data governance), MAP-5.2 (data provenance) | Addressed via audit trail |
| **ISO/IEC 27001** | A.8.2 (classification), A.8.3 (handling), A.9.4 (access control) | Baseline implemented |
| **OWASP ASVS** | V8 (data protection), V9 (communication security) | Baseline implemented |
| **SOC2 CC6** | Logical and physical access controls | Partial — RBAC implemented; formal evidence mapping pending |
