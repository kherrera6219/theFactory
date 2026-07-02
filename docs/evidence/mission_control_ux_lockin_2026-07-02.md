# Mission Control UX Lock-In Evidence

Document version: 2026.07.02
Last updated: 2026-07-02
Status: Current Evidence

Date: 2026-07-02

## Summary

This evidence note records the Mission Control UX lock-in rebuild for PM
clarification, mission-progress visibility, artifact folder discovery, and
follow-up mission continuation.

## Repository-Local Changes

- PM intake now returns and displays actionable clarification questions for
  ambiguous interactive app/game missions, with recommended defaults and an
  edit path before launch.
- Mission Detail now includes a Live Progress panel with clearer working,
  waiting, blocked, retrying, stale, and finished states.
- Generated Output and Build Artifacts panels now show the mission output
  folder path and file status, plus Copy Path, Open Folder, and VS Code actions
  when supported by the local Windows UI process.
- The chat continuation flow now loads prior mission summary, build artifacts,
  delivery summary, and local output-folder status so follow-up missions can
  carry the previous output as project context.
- Backend PM contract normalization now asks clarifying questions for
  underspecified interactive applications and games instead of immediately
  producing a launchable plan.
- Build-artifact completion gating now blocks expected generated-output
  missions from completing without a durable generated output artifact.

## Validation

- `cd apps/mission-control && npm run test -- app/lib/language.test.ts app/lib/smelt-cycle.test.ts app/lib/api-client.test.ts`
  - PASS: 3 files, 36 tests.
- `cd apps/mission-control && npm run build`
  - PASS: Next.js production build includes `/api/local/open-output-folder`,
    `/api/local/open-vscode`, and `/api/local/output-folder-status`.
- `cd apps/mission-control && npm run lint`
  - PASS: TypeScript no-emit check.
- `python -m pytest -q -o addopts='' tests/services/test_llm_delegation_unit.py -k "pm_feature_contract or pm_ambiguity_score" tests/services/test_build_artifacts_unit.py tests/services/test_runtime_unit.py -k "build_artifact or completion_artifacts_ready"`
  - PASS: 19 tests.
- `docker compose --env-file .env -f deploy/docker-compose.yaml -f deploy/docker-compose.full-dedicated-agents.yaml --profile full-dedicated-agents config --services`
  - PASS: compose service graph resolves with the full-dedicated profile.
- `docker compose --env-file .env -f deploy/docker-compose.yaml -f deploy/docker-compose.full-dedicated-agents.yaml build mission-control orchestrator`
  - PASS: `deploy-mission-control:latest` and `deploy-orchestrator:latest`
    rebuilt.

## Remaining Live Proof

The running stack was not restarted as part of this lock-in pass. After restart,
run a new Mission Control browser mission for a small Angular Snake game with a
`start.bat` file and confirm:

- PM clarification appears before launch or the user can proceed with defaults.
- Mission Progress shows live activity instead of appearing hung.
- Generated Output / Build Artifacts expose the real output folder path and
  local open actions.
- Continue with PM preloads the previous mission context for follow-up work.
