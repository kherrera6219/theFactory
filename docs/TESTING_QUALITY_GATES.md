# Testing and Quality Gates

Last updated: 2026-03-02

## Purpose

This document defines automated quality gates for theFactory and the specific coverage guarantees required for the multi-agent core.

## Standard Validation Commands

- `make validate`
- `make lint`
- `make test`

`make test` runs:

- `pytest --cov=services --cov-report=term-missing --cov-report=xml --cov-fail-under=80`
- `python scripts/check_coverage_thresholds.py ...`

## Coverage Policy

Global threshold:

- `services` total coverage must remain `>= 80%`.

Core multi-agent threshold:

- The following files are gated at `100%`:
- `services/orchestrator/orchestrator/protocol.py`
- `services/orchestrator/orchestrator/runtime.py`
- `services/orchestrator/orchestrator/agent_personas.py`
- `services/orchestrator/orchestrator/agent_integrations.py`
- `services/orchestrator/orchestrator/agent_registry.py`
- `services/semantic-bus-mcp/semantic_bus/mcp_server.py`
- `services/pod-worker/pod_worker/main.py`
- `services/audit-worker/audit_worker/main.py`

This policy is enforced in:

- `Makefile` (`make test`)
- `.github/workflows/ci.yml` (`Test with Coverage`)

## Security and Reliability Expectations for Core Files

The coverage policy above exists to protect enterprise-critical runtime guarantees:

- strict protocol and envelope validation,
- authenticated sender and API-key checks,
- bounded recipient routing controls,
- graceful error handling and non-leaking operational failures,
- retry/timeouts for internal service calls,
- deterministic Redis lifecycle and readiness behavior.

## Notes

- Generated `coverage.xml` is used as input for threshold validation.
- If core thresholds fail, CI fails the build.
