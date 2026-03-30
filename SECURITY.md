# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| `main` branch | Yes — active security fixes |
| Release tags `v*` | Yes — backport of critical fixes |
| Feature branches | No |

---

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Please report vulnerabilities via one of the following channels:

1. **GitHub Private Vulnerability Reporting** — use the "Report a vulnerability" button on the [Security tab](../../security/advisories/new) of this repository.
2. **Email** — send details to the repository owners (see CODEOWNERS).

Include in your report:

- Description of the vulnerability
- Component(s) affected (service name, file, line)
- Steps to reproduce or proof-of-concept (where safe to share)
- Potential impact assessment
- Any suggested remediation

We will acknowledge receipt within **48 hours** and aim to provide an initial assessment within **5 business days**.

---

## Security Controls

### Authentication

- All API Gateway and Orchestrator endpoints require an `x-api-key` header.
- Supported auth modes: `api_key`, `hybrid` (OIDC + API key fallback), `oidc`.
- Vault endpoints (`/api/vault`) require an additional `x-vault-admin-key` header.
- No hardcoded or trivially guessable default keys are accepted in production; the process will reject empty admin/worker keys at startup.

### Secret Management

- All credentials are injected via environment variables — never hardcoded.
- Generate all API keys with: `openssl rand -hex 32`
- Optional Hashicorp Vault integration is supported for LLM provider key rotation.
- `.env` files are gitignored. `.env.example` contains only `CHANGE_ME_*` placeholders.

### Container Security

- All service containers run as non-root user `appuser` (uid 10001).
- `no-new-privileges:true` enforced via `security_opt` in Docker Compose.
- All Linux capabilities dropped by default (`cap_drop: ALL`).
- Images based on `python:3.11-slim` (minimal attack surface).

### CI/CD Security Pipeline

The following security scans run on every push and pull request:

| Scan | Tool | Scope |
|------|------|-------|
| SAST | Bandit | Python services and scripts |
| Dependency CVEs | pip-audit | All Python requirements files |
| Dependency CVEs | npm audit | Mission Control (Node) |
| Container CVEs | Trivy | Full filesystem scan |
| Secret detection | Gitleaks | Full git history |
| SBOM | Syft/anchore | Full repository |

Release promotion also depends on signed provenance and policy evaluation:

- CI release-trust job verifies artifact attestations before promotion.
- `make release-evidence-verify` validates the local release-trust evidence bundle structure.
- Production repository settings should require CI, security, and release-trust checks before merge/promotion.

### Network Security

- TLS enforced on Redis and PostgreSQL connections.
- CORS locked to configured `CORS_ALLOW_ORIGINS` (default: localhost only).
- Services communicate over an isolated Docker bridge network (`hgr-network`).
- Only necessary ports are exposed on the host.

### Data Security

- LLM provider API keys are stored in Hashicorp Vault (production) or an ephemeral in-memory store (development only — secrets are lost on restart).
- Audit artifacts can be stored in S3-compatible object storage with configurable retention and legal hold.
- PostgreSQL data encrypted at rest via filesystem encryption (operator responsibility).

---

## Known Limitations

- The in-memory vault backend (default when `VAULT_ADDR` is not set) is **not suitable for production** — secrets are lost on process restart.
- The `LANGGRAPH_FAIL_OPEN=true` default allows mission flow to proceed even if the LangGraph checkpointer is unavailable. Set to `false` in production if checkpoint integrity is required.
- Agent API key isolation (`AGENT_SERVICE_KEY_MODE=strict`) is available but not the default — consider enabling for production deployments.
- Git history cleanup for previously committed TLS key material must be completed outside the working tree before a production release is considered trustworthy.

---

## Vulnerability Disclosure Timeline

1. **Day 0** — Vulnerability reported privately
2. **Day 1–2** — Acknowledgement sent to reporter
3. **Day 3–5** — Initial severity triage and assessment
4. **Day 5–30** — Remediation developed and tested
5. **Day 30–45** — Coordinated disclosure and patch release
6. **Day 45+** — Public CVE disclosure (if applicable)

Critical/high severity vulnerabilities in actively exploited components may be patched on an accelerated timeline.
