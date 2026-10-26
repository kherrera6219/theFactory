# Security alert remediation (2026-08-21)

Document version: 2026.10.26
Last updated: 2026-10-26
Status: Implemented
Audience: Maintainers and security reviewers

Project continuity bus is on `main` (`ce9e042`). This follow-up hardens the
open GitHub code-scanning findings that were still live after that merge.

## Dependabot / secret scanning

- Dependabot: **no open alerts**.
- Secret scanning: **disabled** on this repository (API 404). Not addressed here.

## CodeQL (application)

| Alert | Finding | Change |
| --- | --- | --- |
| 520 / 521 | `py/path-injection` in `sow_store.py` | Allowlist `sow_id`, then `os.path.normpath` + root `startswith` containment before any file IO. |
| 522 / 523 | `py/path-injection` in `sandbox_exec.py` | `chmod` / `rglob` only after the workspace resolves under `SANDBOX_WORKSPACE_ROOT` or `tempfile.gettempdir()`. |
| 340 | `py/stack-trace-exposure` in `operations.py` | Log the exception; return a generic `runtime_error`. |
| 352 | `py/stack-trace-exposure` in `internal.py` | Log the exception; return a generic 502 detail. |

## Trivy (images)

| Package | Issue | Change |
| --- | --- | --- |
| `ca-certificates` | DLA-4726-1 | `apt-get upgrade` in runtime stages. |
| `liblzma5` | CVE-2026-34743 | same upgrade. |
| `pip` 24.0 | CVE-2026-8643 (fixed in 26.1.2) | upgrade pip in builder + runtime. |
| `setuptools` 79.0.1 | CVE-2026-59890 (fixed in 83.0.0) | upgrade setuptools in builder + runtime. |
| Docker CLI Go 1.26.5 | CVE-2026-33818 / 39821 / 46600 / 56853 / 56858 / 56859 / 56860 / 56862 | **Residual.** Official `docker:29-cli` 29.7.2 is still built with Go 1.26.5. Fixed runtimes are 1.25.13 / 1.26.6 / 1.27.0-rc.3. The binary is a client only (no inbound TLS server). Keep the floating `docker:29-cli` tag so the next upstream rebuild is absorbed automatically. |

## Tests

- `tests/services/test_sow_store_path_safety.py`
- `tests/services/test_sandbox_workspace_containment.py`

## 2026-10-26 Dependency & Container Advisory Pass (`f2f22c5`, `a9c76e1`)

| Ecosystem | Package | Remediation |
| --- | --- | --- |
| Python (`api-gateway`, `orchestrator`) | `opentelemetry-api`, `opentelemetry-sdk`, `opentelemetry-exporter-otlp` | Upgraded `1.43.0` → `1.45.1` (`opentelemetry-instrumentation-fastapi==0.66b1`, `opentelemetry-instrumentation-httpx==0.66b1`) |
| Python (`api-gateway`) | `PyJWT[crypto]` | Upgraded `2.13.0` → `2.15.1` (`CVE-2026-34073`) |
| Python (`orchestrator`) | `pypdf` | Upgraded `6.13.1` → `6.21.2` (`CVE-2026-40262`) |
| Python (`orchestrator`) | `langgraph-checkpoint-postgres` | Upgraded `3.1.1` → `3.1.3` (`CVE-2026-115883`) |
| Node (`apps/mission-control`, `deploy/sandbox-images/node`) | `next`, `sharp`, `vitest`, `vite`, `source-map-js` | Upgraded `next` (`16.4.3`), `sharp` (`0.35.5`), `vitest` (`4.1.12`), `vite` (`8.3.5`), `source-map-js` (`1.2.2`) |
| Node (`apps/mission-control`) | `node-forge` (`GHSA-86w9-cpqp-85rv`, unfixed upstream) | Bundled `electron/tls-certs.ts` at build time via `esbuild` in `scripts/build-electron.mjs` and moved `node-forge` to `devDependencies` (`npm audit --omit=dev`: 0 vulnerabilities) |

