# ADR - Security Model: API Keys vs JWT/OIDC (2026-03-04)

Date: 2026-03-04  
Document version: 2026.03.04  
Last updated: 2026-04-17  

## Status
Accepted

## Context
- Current runtime uses role-scoped API keys for gateway/orchestrator/service access.
- This model is effective for local-first and service-to-service operation, but enterprise environments require federated identity and short-lived tokens.
- Word-doc and audit reconciliation identified the need for an explicit security-model decision.

## Decision
Adopt a **dual-mode security architecture**:
- Keep API keys as the default local/runtime control plane mechanism.
- Add enterprise JWT/OIDC support at the API Gateway as an optional mode, preserving internal service keys for machine-to-machine traffic.

## Mode Policy
- `api_key` mode (default): local deployments, CI, internal service calls.
- `hybrid` mode: accept JWT/OIDC for external/operator requests and API keys for internal paths.
- `oidc` mode: require JWT/OIDC for operator/public APIs; API keys restricted to internal service identity.

## JWT/OIDC Requirements
1. Issuer/audience validation with JWKS key rotation support.
2. Claim-to-role mapping compatible with existing mutate/read/internal/admin semantics.
3. Short-lived token enforcement and explicit clock-skew controls.
4. Audit logging for authenticated subject (`sub`), issuer, and effective roles.

## Implementation Plan
1. Add gateway auth abstraction with pluggable API-key and JWT validators.
2. Introduce `AUTH_MODE`, `OIDC_ISSUER_URL`, `OIDC_AUDIENCE`, and JWKS cache controls.
3. Add regression tests for role mapping, invalid token handling, and mixed-mode behavior.
4. Update integration guide/runbooks with enterprise onboarding and token troubleshooting.

## Consequences
- Near-term: no breaking auth change for existing local users.
- Enterprise path becomes explicit, testable, and governable.
- Service-to-service hardening remains compatible with current internal key model.
