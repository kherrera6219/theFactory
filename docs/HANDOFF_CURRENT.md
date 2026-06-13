# Current Handoff

Document version: 2026.06.13
Last updated: 2026-06-13
Status: Canonical
Audience: Maintainers, operators, and AI coding agents

This handoff summarizes the current repo state after the 2026-06-13 update
batch. Use this file, `docs/CURRENT_TODO.md`, and
`docs/IMPLEMENTATION_STATUS.md` before consulting archived plans.

## Current State

- Branch: `main`
- Runtime model policy: all 41 agents default to `gemini/gemini-3.5-flash`
  with high thinking.
- Mission Control model selector: ChatGPT 5.5, Claude Opus 4.8, Gemini Flash
  3.5.
- Active docs are indexed in `docs/DOCUMENTATION_INDEX.md`; old roadmap,
  sprint, phased update, release completion, reliability, and dated runtime
  mapping docs were moved to `docs/archive/2026-06-13/`.
- CI production signaling was hardened so production-critical jobs should run
  on `main` pushes instead of showing misleading skips.

## Work Completed Today

| Commit | Summary |
|---|---|
| `1b10d8c` | Route all agents through Gemini Flash 3.5 with high effort and add the Mission Control model selector. |
| `85da8e4` | Refresh active app docs for Gemini-first routing and current status. |
| `7768e16` | Archive superseded planning documents and regenerate the repository build map. |
| `30b4b78` | Align model inventory tests with Gemini-first defaults. |
| `867d3ec` | Run production CI gates on `main` and fail loudly instead of silently skipping. |

## Validation Performed Locally

- Focused backend tests for Gemini-first agent inventory and orchestrator
  operation endpoints passed.
- Broader service tests for `test_llm_delegation_unit.py` and
  `test_orchestrator_endpoints_extra.py` passed.
- Ruff passed for the touched test files.
- Documentation validation passed after docs/index/archive updates.
- GitHub Actions workflow YAML parsed locally after CI hardening.

## Next Operator Actions

1. Check the GitHub Actions run for commit `867d3ec` and confirm all
   production-critical gates run and pass.
2. Start the stack with a real Gemini key and run the live BUILD_NEW proof.
3. Capture evidence under `docs/evidence/`.
4. Update `docs/IMPLEMENTATION_STATUS.md` and `docs/CURRENT_TODO.md` with the
   CI and live-mission results.

## Watch Items

- If `Electron E2E Smoke` is too unstable for normal `main` pushes, do not
  silently skip it. Either fix the test/runtime or explicitly reclassify it as
  non-blocking in `docs/TESTING_QUALITY_GATES.md`.
- Release Trust on `main` records branch deferral; strict promotion policy still
  runs on release tags.
- Archived docs are historical only. Do not resurrect `docs/archive/2026-06-13`
  plans as active work without reconciling them into `docs/CURRENT_TODO.md`.
