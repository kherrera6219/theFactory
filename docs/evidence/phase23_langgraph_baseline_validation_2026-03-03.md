# Phase 23 Validation - LangGraph Baseline (2026-03-03)

## Objective
Begin LangGraph orchestration adoption with a production-safe baseline:
- feature-flagged execution,
- fail-open fallback to legacy lifecycle,
- regression test coverage and quality gates.

## Online Research Inputs (Authoritative)
- LangGraph overview: <https://docs.langchain.com/oss/python/langgraph/overview>
- LangGraph persistence/checkpointing: <https://docs.langchain.com/oss/python/langgraph/persistence>
- LangGraph durable execution and thread/checkpointer model: <https://docs.langchain.com/oss/python/langgraph/durable-execution>
- Package baseline used for dependency pinning: <https://pypi.org/project/langgraph/>

## Implemented Baseline
- Added `services/orchestrator/orchestrator/langgraph_lifecycle.py`:
  - graph-based mission lifecycle (`QUEUED -> RUNNING -> VERIFIED -> COMPLETE`)
  - optional checkpointer mode (`none`, `memory`)
  - thread-id config via `LANGGRAPH_THREAD_PREFIX`
  - fail-open behavior controlled by `LANGGRAPH_FAIL_OPEN`
- Integrated runtime handoff in `services/orchestrator/orchestrator/runtime.py`:
  - LangGraph path first
  - legacy transition engine fallback preserved
- Added settings/env controls:
  - `LANGGRAPH_ENABLED`
  - `LANGGRAPH_FAIL_OPEN`
  - `LANGGRAPH_CHECKPOINTER`
  - `LANGGRAPH_THREAD_PREFIX`

## Validation Commands and Results
1. `python -m ruff check services tests scripts`
   - Result: pass
2. `python -m pytest -q`
   - Result: pass (`239 passed`)
3. `python -m pytest --cov=services --cov-report=term-missing --cov-report=xml --cov-fail-under=80`
   - Result: pass (`84.98%` global)
4. `python scripts/check_coverage_thresholds.py ...`
   - Result: pass (required `100%` module thresholds intact, including `runtime.py`)
5. `powershell -ExecutionPolicy Bypass -File scripts/debug_sweep.ps1`
   - Result: pass (schema/tests/compose/health/readyz/metrics/log checks)

## Next Step
Add Postgres-backed LangGraph checkpointing and live recovery qualification behind existing feature flags.
