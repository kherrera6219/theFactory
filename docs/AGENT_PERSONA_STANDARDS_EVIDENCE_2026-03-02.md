# Agent Persona Standards Evidence

Document version: 2026.03.29  
Last updated: 2026-06-27
Status: Reference  
Audience: Operators, developers, maintainers, and auditors

> Current note (2026-06-13): This evidence reference is aligned to the current 41-agent runtime.

Date: 2026-03-02

## Purpose

Define production-grade external standards used to enrich agent persona profiles with role mappings and source-linked evidence.

## Source Catalog (Authoritative Links)

| Source ID | Organization | Standard | Version | URL |
|---|---|---|---|---|
| `nist-csf-2.0` | NIST | Cybersecurity Framework | 2.0 | https://www.nist.gov/cyberframework |
| `nist-ai-rmf-1.0` | NIST | AI Risk Management Framework | 1.0 | https://www.nist.gov/itl/ai-risk-management-framework |
| `nist-sp-800-218` | NIST | Secure Software Development Framework | 1.1 | https://csrc.nist.gov/pubs/sp/800/218/final |
| `nist-sp-800-53r5` | NIST | Security and Privacy Controls | Rev.5 / Rev.5.2 update | https://www.nist.gov/news-events/news/2025/09/nist-updates-privacy-and-security-guidelines-safeguard-federal-systems |
| `nist-sp-800-61r3` | NIST | Incident Response Recommendations | Rev.3 | https://csrc.nist.gov/pubs/sp/800/61/r3/final |
| `owasp-top-10-2021` | OWASP | Top 10 Web Application Security Risks | 2021 | https://owasp.org/www-project-top-ten/ |
| `owasp-asvs-v5` | OWASP | Application Security Verification Standard | 5.0 | https://owasp.org/www-project-application-security-verification-standard/ |
| `iso-iec-27001-2022` | ISO/IEC | Information Security Management | 2022 | https://www.iso.org/standard/27001 |
| `iso-iec-42001-2023` | ISO/IEC | AI Management Systems | 2023 | https://www.iso.org/standard/81230.html |

## Role Mapping Strategy

All 41 agents receive:
- `nist-csf-2.0`
- `nist-ai-rmf-1.0`
- `iso-iec-42001-2023`

Category-specific additions:
- `support`: `nist-sp-800-53r5`
- `pod_manager`: `nist-sp-800-218`
- `pod_audit`: `nist-sp-800-218`, `owasp-asvs-v5`
- `specialist`: `nist-sp-800-218`, `owasp-asvs-v5`

Agent-specific additions:
- `SECURITY`: `owasp-top-10-2021`, `nist-sp-800-61r3`, `iso-iec-27001-2022`
- `TESTER`: `owasp-top-10-2021`, `nist-sp-800-61r3`
- `COMPLIANCE`: `iso-iec-27001-2022`, `owasp-asvs-v5`
- `VC`: `nist-sp-800-218`
- `DEPLOY`: `nist-sp-800-218`, `iso-iec-27001-2022`
- `BROKER`: `iso-iec-27001-2022`
- `ACCOUNTANT`: `iso-iec-27001-2022`
- `IS`: `iso-iec-27001-2022`
- `CEO`: `nist-sp-800-218`
- `PM`: `nist-sp-800-218`

## Runtime Contract Impact

`persona_profile` now includes:
- `standards_alignment`: framework-level role mappings and focus areas.
- `evidence_sources`: source links, organization, version, applicability, and verification date.

This data is available in:
- `GET /internal/operations/agents`
- `GET /internal/operations/agent-integrations`
- `GET /v1/operations/agents`
- `GET /v1/operations/agent-integrations`


