# Data Classification Policy

Last updated: 2026-03-02

## Purpose

Define mandatory handling controls for all data processed by theFactory.

## Classification Levels

1. `PUBLIC`
- Intended for open sharing.
- Storage: unrestricted.
- Transport: TLS preferred.

2. `INTERNAL`
- Operational data not intended for public release.
- Storage: authenticated systems only.
- Transport: TLS required across service boundaries.

3. `CONFIDENTIAL`
- Customer code, mission payloads, internal artifacts.
- Storage: encrypted at rest and role-restricted access.
- Transport: TLS required.
- Retention: minimum necessary; subject to deletion policy.

4. `RESTRICTED`
- Secrets, keys, credential material, compliance-sensitive records.
- Storage: encrypted secret stores only.
- Transport: TLS + strict access control.
- Access: least privilege with audited access trail.

## Data Mapping (Current)

- Mission payloads and source code: `CONFIDENTIAL`
- Agent telemetry and internal metrics: `INTERNAL`
- API keys and vault secrets: `RESTRICTED`
- Public docs and OpenAPI specs: `PUBLIC`

## Governance Controls

- Access reviews every quarter.
- Retention/deletion jobs enforced in operations pipeline.
- Security incidents involving `CONFIDENTIAL` or `RESTRICTED` data require postmortem review.
