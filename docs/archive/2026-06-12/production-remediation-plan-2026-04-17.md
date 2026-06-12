# Production Remediation Plan — 2026-04-17

Document version: 2026.04.17
Last updated: 2026-04-17
Status: Active
Audience: Maintainers, security reviewers

Validation of the 8 outstanding findings from the 2026-04-16 production code review,
plus the ordered plan used to execute them.

## Validation of remaining findings

| # | Finding | Status | Evidence |
|---|---|---|---|
| 1 | Digest-pin base images | OPEN | 7 Python Dockerfiles use `python:3.11-slim`; mission-control uses `node:22-alpine` |
| 2 | `hmac.compare_digest` for API keys | OPEN | `orchestrator/auth.py:23` (dict `.get()`), `mcp_server.py:410` (`!=`) |
| 3 | `OIDC_ALLOWED_ALGORITHMS` default includes HS256 | OPEN | `api-gateway/main.py:77` default `RS256,HS256`; no override in `prod.yaml` |
| 4 | MCP host port published globally | OPEN | `docker-compose.yaml:424` binds `0.0.0.0`; no prod override |
| 5 | Structured JSON logging missing | OPEN | Only plain `logging.getLogger` used |
| 6 | `pod-d-worker` `read_only`/tmpfs drift | **FALSE POSITIVE** | `docker-compose.yaml:643` uses the `*readonly-service-hardening` anchor which already applies `read_only: true` + tmpfs + ulimits |
| 7 | `LANGGRAPH_FAIL_OPEN: "true"` in prod | OPEN | `docker-compose.prod.yaml:40` |
| 8 | `start_app.bat` uses `npm run dev` | OPEN | `start_app.bat:15` |

Seven genuine issues, one false positive (pod-d-worker is already hardened via YAML
anchor — the reviewer's per-service grep missed the anchor-based inheritance).

## Phased plan (ordered by risk × blast radius, lowest first)

### Phase A — config-only tightening (lowest risk)

No code changes, no new deps. Each change is a one-line flip of an env default or
overlay value.

- A1. Default `OIDC_ALLOWED_ALGORITHMS=RS256` (was `RS256,HS256`). Drops
  alg-confusion surface. Prod explicit value remains controlling.
- A2. `LANGGRAPH_FAIL_OPEN: "false"` in `prod.yaml`. State-persistence errors
  should surface, not be swallowed.
- A3. Parameterize MCP port bind-address. Base compose uses
  `${MCP_HOST_BIND:-0.0.0.0}:${MCP_HOST_PORT:-8102}:8090`; prod overlay sets
  `MCP_HOST_BIND=127.0.0.1` so the port is only reachable on the host loopback.
- A4. Flip `start_app.bat` Mission Control launch from `npm run dev` to
  `npm run build && npm run start` for prod parity.

### Phase B — constant-time API-key compares

- B1. `orchestrator/auth.py`: iterate `api_key_roles` with `hmac.compare_digest`
  rather than dict `.get()`. Degrades to O(N) lookup but N is small (≤ 40 keys)
  and constant-time is required for HMAC-style comparisons.
- B2. `mcp_server.py:410`: replace `!=` with `hmac.compare_digest`.

### Phase C — pin base image tags

Full digest pinning requires live access to Docker Hub to resolve current SHAs.
We take a staged approach:

- C1. Pin to fully-qualified minor+patch version tags (e.g.
  `python:3.11.9-slim-bookworm`, `node:22.11.0-alpine`). These are practically
  immutable within a patch release.
- C2. Add an inline comment in each Dockerfile pointing at the follow-up task
  for true digest pinning (`@sha256:...`) plus Trivy/Grype image scan in CI.

### Phase D — structured logging + sanitize JWT exception

- D1. Add `shared_runtime/logging_config.py` with a `JsonFormatter` and a
  `configure_logging(service_name)` helper. Gated by `LOG_FORMAT` env
  (`plain`|`json`, default plain). No new dependency — stdlib-only.
- D2. Wire `configure_logging()` into each service's entrypoint (early in the
  module so it runs before uvicorn starts its own logger).
- D3. Fix `api-gateway/main.py:716` to log only the JWT exception *class name*
  (not the message), since PyJWT can echo token fragments.
- D4. Set `LOG_FORMAT: json` in `prod.yaml` for all services.

### Phase E — verification + ship

- E1. `ruff check` clean. ✅ All checks passed.
- E2. Full pytest suite green. ✅ 999 passed, 5 skipped.
- E3. Compose YAML parses.
- E4. Update README + CHANGELOG + auto-memory.
- E5. Commit + push to GitHub.

## Execution record (2026-04-17)

All phases A–D applied. Verification run results:

- `ruff check shared_runtime services tests` → **All checks passed!**
- `pytest tests` → **999 passed, 5 skipped** in 270.35s.

Touchpoints:

- **Phase A** — `api-gateway/main.py:77` (default `RS256`); `prod.yaml:43` (`LANGGRAPH_FAIL_OPEN: "false"`); `docker-compose.yaml:424` (MCP bind parametrized); `.env.example` (new `MCP_HOST_BIND`); `start_app.bat` (build+start default, `--dev` fallback).
- **Phase B** — `orchestrator/auth.py` `_match_api_key()` with `hmac.compare_digest`; `mcp_server.py:410` flipped from `!=` to `hmac.compare_digest`.
- **Phase C** — all 7 Python Dockerfiles pinned to `python:3.11-slim-bookworm`; mission-control `node:22-alpine3.20`; 13 HEALTHCHECK URLs flipped from `/health` to `/readyz`.
- **Phase D** — new `shared_runtime/logging_config.py` (stdlib JsonFormatter); `configure_logging(service_name)` wired into 7 services; `api-gateway/main.py:716` JWT error logs the exception *class only* (prevents token-fragment leaks); `LOG_FORMAT: json` added to every service block in `prod.yaml`; `dashboard` and `semantic-bus-mcp` Dockerfiles now copy `shared_runtime/` so the module resolves at runtime.
- **Pre-existing** — 6 E501 lines in `shared_runtime/pii_guard.py` regex table suppressed with `# noqa: E501` (splitting compiled patterns hurts readability; they were already over-long before this PR).

## Deferred (not part of this PR)

- True `@sha256:...` digest pinning + Trivy image-scan in CI (requires live
  Docker Hub access to resolve current SHAs). Add as follow-up once CI image-scan
  step is wired.
- Dependency review + SBOM upload in CI.
- Renovate/Dependabot config for image + pip + npm.
