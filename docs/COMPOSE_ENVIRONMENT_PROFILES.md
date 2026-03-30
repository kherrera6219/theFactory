# Compose Environment Profiles

Document version: 2026.03.29  
Last updated: 2026-03-29  
Status: Canonical  
Audience: Operators, developers, and maintainers

## Purpose

Define the supported compose overlay set for local development, staging qualification, and production release promotion.

## Files

- `deploy/docker-compose.yaml`: shared baseline stack and hardening defaults.
- `deploy/docker-compose.dev.yaml`: local developer profile.
- `deploy/docker-compose.staging.yaml`: pre-production qualification profile.
- `deploy/docker-compose.prod.yaml`: production release profile.

## Commands

- Dev: `docker compose -f deploy/docker-compose.yaml -f deploy/docker-compose.dev.yaml up -d --build`
- Staging: `docker compose -f deploy/docker-compose.yaml -f deploy/docker-compose.staging.yaml up -d --build`
- Prod: `docker compose -f deploy/docker-compose.yaml -f deploy/docker-compose.prod.yaml up -d --build`
- Validation: `make compose-validate`
- Release evidence validation: `make release-evidence-verify`

## Security Baseline

- Internal runtime services run with `cap_drop: [ALL]` and no capability add-backs.
- Internal runtime services use `no-new-privileges:true`.
- Runtime OOM policy defaults to `APP_OOM_SCORE_ADJ=-500`; data services default to `DATA_SERVICE_OOM_SCORE_ADJ=-850`.
- Seccomp policy remains the Docker runtime default in all three overlays. `unconfined` is not an approved setting for any environment.
- Compose files do not carry live fallback secrets. Required API keys and internal auth values must be injected from the shell, CI secret store, or an external secret manager before startup.
- Developer TLS material must be generated locally with `scripts/generate_dev_tls_certs.ps1` or `scripts/generate_dev_tls_certs.sh`; tracked compose assets must not include private keys.

## Repository Administration Requirements

- Enable branch protection on `main` and any release branches/tags with required checks for CI, security, and release-trust workflows.
- Enable GitHub Advanced Security secret scanning and push protection at the repository or organization level.
- Complete git-history scrubbing and key rotation for the previously committed TLS certificate material before any production promotion.

## Environment Deltas

- Dev:
  - `AUTH_MODE=api_key`
  - LangGraph disabled
  - optional `neo4j` and object-storage integrations disabled
- Staging:
  - `AUTH_MODE=hybrid`
  - LangGraph enabled with in-memory checkpointing
  - optional `neo4j` and object-storage integrations enabled for qualification
- Prod:
  - `AUTH_MODE=oidc`
  - LangGraph enabled with Postgres checkpointing
  - optional `neo4j` and object-storage integrations enabled
