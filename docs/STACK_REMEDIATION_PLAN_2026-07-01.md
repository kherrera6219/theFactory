# Stack Remediation Plan — 2026-07-01

Document version: 2026.07.01
Last updated: 2026-07-01
Status: Active plan
Audience: Maintainers and AI coding agents

Written after a live 20-mission Protocol Bus validation battery surfaced one
real application bug (now fixed and unit-tested) and several live-restart
operational issues. Per explicit direction: **no more live fixes.** This plan
documents every finding, then the fix sequence is: stop the app → fix offline
→ rebuild → bring the stack up once, cleanly → test.

---

## What triggered this

A 20-mission battery was run through the real Mission Control chat UI (one
mission per language specialist, exercising the PM Agent's clarification
dialogue) to validate the Protocol Bus Lane Activation (PBLA) work. All 20
missions reached `COMPLETE`. While inspecting the results, a real routing bug
was found (see below). Rebuilding the orchestrator image to pick up the fix,
and restarting it live, triggered a cascade of environment/credential issues
documented here.

---

## Finding 1 — Pod audit agent misrouting (CONFIRMED BUG, ALREADY FIXED)

**Status: fixed, unit-tested, ready to ship on next rebuild.**

`generate_pod_audit_verdict` in
`services/orchestrator/orchestrator/llm_delegation/generators_artifacts.py`
lower-cased `pod_name` (`"podB"` → `"podb"`) before matching against the
mixed-case `_POD_AUDIT_AGENTS` dict keys (`"podA"`, `"podB"`, `"podC"`,
`"podD"`). The lookup **never matched for any pod**, so every mission silently
fell back to `AGENT-13-PODA-AUDIT` — masked for Pod A only because the default
happens to equal Pod A's own audit agent.

**Live proof:** in the 20-mission battery, all 15 non-Pod-A missions recorded
`pod_audit_verdicts.<pod>.agent_id == "AGENT-13-PODA-AUDIT"` instead of their
own pod's audit agent (`AGENT-19-PODB-AUDIT` / `AGENT-25-PODC-AUDIT` /
`AGENT-31-PODD-AUDIT`). This also means every affected mission's PBLA-01 Delta
emission carried the wrong sender/audit-agent-id.

**Fix (already applied, in the working tree):**
- Added `_POD_AUDIT_AGENTS_BY_LOWER` (case-insensitive lookup) in
  `generators_artifacts.py`; `audit_agent_id` resolution now matches regardless
  of `pod_name` casing.
- Regression test added:
  `tests/services/test_llm_delegation_unit.py::test_generate_pod_audit_verdict_resolves_correct_agent_per_pod`
  (4 parametrized cases, one per pod — all pass).
- Full regression run clean: 163 tests pass across
  `test_llm_delegation_unit.py`, `test_mission_flow_v2.py`,
  `test_mission_flow_v2_phases_build.py`. Ruff clean.

**Action needed:** none beyond the rebuild already planned below — this fix is
already in the working tree and just needs to be committed and baked into the
next orchestrator image build.

---

## Finding 2 — Compose file pairing requirement (PROCESS ERROR, ROOT CAUSE OF THE CASCADE)

**Status: root cause identified; this is what caused Findings 3 and 4.**

This deployment's actual running topology (41 dedicated per-language agent
containers, `TOPOLOGY_MODE=full-dedicated`) is defined by **two compose files
layered together**:

```
docker compose -f deploy/docker-compose.yaml -f deploy/docker-compose.full-dedicated-agents.yaml ...
```

`docker-compose.full-dedicated-agents.yaml` is an **overlay** — it only patches
the `orchestrator` service's environment and *adds* the 41 `agent-XX-*`
services; it does not redefine `api-gateway`, `mission-control`, or the pod
workers at all standalone.

**What went wrong:** the orchestrator rebuild+restart in this session was run
against `docker-compose.yaml` **alone** (single file, no overlay). Because
container names are shared across both file combinations (same project name),
this recreated `orchestrator`, then a subsequent broader `up -d` recreated
`api-gateway`, `mission-control`, `neo4j`, `audit-worker`, and the 4 shared pod
workers **under the base-file topology**, dropping the full-dedicated-agents
overlay's environment entirely (e.g. `TOPOLOGY_MODE`). This is almost
certainly what left several downstream services in an inconsistent state
relative to the 41 still-running dedicated agent containers (which were never
touched and kept their original environment).

**Corrective action taken:** subsequent rebuilds/restarts were redone with the
correct two-file combination, which did restore `orchestrator` and
`api-gateway` to `healthy`. But by that point Findings 3 and 4 had already
surfaced and were not fully resolved live (per the "stop fixing live" directive).

**Action needed:** any future rebuild/restart of this stack **must** use the
two-file form above. This should be captured as a documented convention
(Makefile target or `docs/OPERATIONS_RUNBOOK.md` note) so a partial single-file
command is never the first instinct again. See "Recommended fixes" below.

---

## Finding 3 — Postgres/pgbouncer password mismatch (UNRESOLVED, NEEDS OFFLINE INVESTIGATION)

**Status: root cause not confirmed. Do not guess-fix credentials live.**

After the compose-file correction, `orchestrator`'s `/health` still reports
`db_ready: false` and `/readyz` returns 503, with `pgbouncer` logging:

```
FATAL: password authentication failed for user "postgres"
```

**What was safely confirmed (presence/prefix checks only, no full credential
ever printed):**
- The `postgres` container's own `POSTGRES_PASSWORD` env and the
  `orchestrator` container's `POSTGRES_URL` password **agree with each other**
  (same value) — so orchestrator and postgres are not fighting each other
  directly.
- That agreed-upon value does **not** match what is currently in the
  repo-root `.env` file's `POSTGRES_PASSWORD` (confirmed via first-4-character
  prefix comparison only).
- No `deploy/.env` override file exists; only one `.env` at repo root.
- `POSTGRES_PASSWORD` is not shell-exported in the working session (so it's
  not a shell-env shadowing issue).
- The `postgres` data volume (`deploy_postgres-data`) was created at
  `2026-07-01T02:49:08Z`, i.e. earlier in this session/day — meaning Postgres's
  **on-disk** password was set at that first `initdb` and does not change on
  container recreation as long as the volume persists.

**Leading hypothesis:** `.env`'s `POSTGRES_PASSWORD` was changed (rotated) at
some point *after* the Postgres data volume was first initialized, so the live
database's actual stored credential no longer matches the current `.env`
value. Recreating the `postgres` container does not fix this (Postgres only
applies `POSTGRES_PASSWORD` on first init of an empty data directory).

**Do NOT do any of the following without explicit operator confirmation:**
- Do not run `ALTER USER postgres PASSWORD ...` against the live database
  based on a guess.
- Do not delete/recreate the `deploy_postgres-data` volume — this is
  destructive and would lose any real mission data it holds.
- Do not echo/compare full credential values in any tool output (the harness
  correctly blocked this once already this session).

**Action needed (offline, app stopped):**
1. Confirm with the operator (Kevin) what the *intended* current
   `POSTGRES_PASSWORD` is, and whether the `.env` value or the live database's
   value is the one that should win.
2. If `.env` is correct and the database is stale: while the stack is stopped,
   start only `postgres` (and `pgbouncer` after), connect with the **old**
   (currently-working) credential, and run
   `ALTER USER postgres WITH PASSWORD '<new-value-from-.env>';` — an explicit,
   confirmed, operator-directed action, not a guess.
3. If the database's current credential is correct: update `.env` to match it
   (simpler, zero-downtime, no DB mutation needed).
4. Either way, verify with `docker exec deploy-postgres-1 pg_isready` and a
   real `/readyz` 200 before considering this closed.

---

## Finding 4 — `api-gateway` `INTERNAL_SERVICE_API_KEY` empty at runtime (UNRESOLVED, NEEDS OFFLINE INVESTIGATION)

**Status: root cause not confirmed.**

`api-gateway`'s internal-forwarding routes (e.g. `/v1/missions/{id}/build-artifacts`)
return `503 {"detail": "gateway internal auth is not configured"}`. Runtime
check inside the container confirms `INTERNAL_SERVICE_API_KEY` resolves to an
**empty string** (length 0), even though:
- `.env`'s `INTERNAL_SERVICE_API_KEY` has a real 64-character value.
- The base compose file's substitution is
  `INTERNAL_SERVICE_API_KEY: ${INTERNAL_SERVICE_API_KEY:-}` (empty-string
  fallback) at three call sites (`api-gateway`, `orchestrator`, one more —
  grep hits at lines 340/435/578 of `docker-compose.yaml`).
- The variable is not shell-exported in the working session (ruled out as a
  shadowing cause).
- This was checked **after** the Finding 2 compose-file correction and a
  `--force-recreate` of `api-gateway` specifically, so it is not simply "stale
  container from the wrong compose file" — it persisted even after a clean,
  correctly-composed recreate.

**Action needed (offline, app stopped):**
1. Re-run `docker compose -f deploy/docker-compose.yaml -f
   deploy/docker-compose.full-dedicated-agents.yaml config` (dry-run
   interpolation, no containers) and grep the rendered output for
   `INTERNAL_SERVICE_API_KEY` to see what value compose actually resolves,
   without needing to touch a live container.
2. Check for a `.env.example` vs `.env` key-name drift (e.g. a rename that
   left the base file referencing a variable name that's spelled slightly
   differently in the current `.env`).
3. Check whether `docker-compose.full-dedicated-agents.yaml` sets
   `INTERNAL_SERVICE_API_KEY` to empty anywhere for `api-gateway`
   specifically (the earlier grep only confirmed it patches `orchestrator`'s
   environment and the per-agent `SERVICE_API_KEY` fallback chains — it was
   not fully checked for an `api-gateway:` block override).
4. Fix in the compose/env layer (not by hand-editing a running container), then
   verify via `docker compose config` before restarting anything.

---

## Finding 5 — Host port collisions with unrelated foreign projects (NOT A BUG — INFORMATIONAL)

**Status: confirmed not-a-bug. No code or config change required.**

During the `up -d` sequence, `minio` (port 9000) and `neo4j` (port 7474)
failed to bind with "port is already allocated". Investigated via `docker
inspect` (image, compose labels, mount paths — no data touched):

| Container | Actual owner | Port |
|---|---|---|
| `devonz-minio` | `C:\software\Devonz\database\docker-compose.yml` (project `database`) | 9000 |
| `devonz-neo4j` | same, project `database` | 7474 |
| `ukg-neo4j` | `C:\software\DataLogicEngine\docker-compose.yml` (project `datalogicengine`) | 7474 (mapped to 7476 there, not colliding) |

These are **genuinely independent, currently-active projects** on this
machine — not old/renamed copies of theFactory. The `devonz-*` / `ukg-*`
naming has no relationship to Holygrail/theFactory's own naming conventions.
**Do not remove them.**

Both `minio` (object storage, `OBJECT_STORAGE_ENABLED`) and `neo4j`
(`NEO4J_ENABLED`) are feature-flagged optional adapters in theFactory already
— the app runs without them; only object-storage/graph-relationship features
degrade. This session simply skipped bringing them up
(`--scale minio=0 --scale neo4j=0`) to avoid the conflict.

**Recommended fix (low priority, optional):** theFactory's compose already
supports host-port overrides for other services
(`${ORCHESTRATOR_HOST_PORT}`, `${MISSION_CONTROL_HOST_PORT}`, etc.) — confirm
`minio`/`neo4j` have equivalent `${MINIO_HOST_PORT}` /
`${NEO4J_HOST_PORT}` overrides in `docker-compose.yaml`, and if so, set
non-default values in `.env` (e.g. `9010`, `7480`) so this machine can run
theFactory and the other two projects side by side without the operator
needing to remember to skip services on every startup.

---

## Recommended fix sequence (per explicit direction: no live fixes)

1. **Stop the app cleanly.** `docker compose -f deploy/docker-compose.yaml -f
   deploy/docker-compose.full-dedicated-agents.yaml stop` (stop, not `down
   -v` — preserves all volumes/data; nothing destructive).
2. **Fix Finding 3 (Postgres password)** per the operator-confirmed path above
   — decide which value wins, and only run `ALTER USER` if explicitly
   confirmed, with the stack's Postgres started standalone for that one
   operation.
3. **Fix Finding 4 (`INTERNAL_SERVICE_API_KEY`)** by inspecting `docker compose
   config` output (no running containers needed) and correcting the compose
   layer.
4. **Confirm Finding 1's fix is committed** (it already is, in the working
   tree — this plan does not add new code changes for it).
5. **Rebuild** `orchestrator` and `api-gateway` images using the two-file
   compose combination:
   ```
   docker compose -f deploy/docker-compose.yaml -f deploy/docker-compose.full-dedicated-agents.yaml build orchestrator api-gateway
   ```
6. **Bring the stack up once, cleanly**, correctly paired, skipping only the
   two foreign-port-conflicted optional services if their override ports (per
   Finding 5) aren't set yet:
   ```
   docker compose -f deploy/docker-compose.yaml -f deploy/docker-compose.full-dedicated-agents.yaml up -d
   ```
7. **Test:**
   - `/readyz` on orchestrator and api-gateway both return 200.
   - Full fleet health check (0 unhealthy, 0 stuck-`Created`).
   - Re-run the pod-audit-agent regression test live: submit one Pod B/C/D
     mission via chat and confirm `pod_audit_verdicts.<pod>.agent_id` matches
     the pod's own audit agent (not `AGENT-13-PODA-AUDIT`).
   - Fetch build-artifacts for a couple of the 20 already-completed battery
     missions to confirm the `api-gateway` internal-auth fix actually resolved
     Finding 4.

## Definition of done

- [ ] Finding 3 resolved and verified (`/readyz` 200, no FATAL auth in logs)
- [ ] Finding 4 resolved and verified (`build-artifacts` endpoint returns 200)
- [ ] Finding 1's fix confirmed present in the rebuilt image
- [ ] Full fleet healthy after a single clean `up -d` with the correct
      two-file compose combination
- [ ] One live Pod B/C/D mission confirms the audit-agent fix end-to-end
- [ ] `docs/OPERATIONS_RUNBOOK.md` (or equivalent) updated with the two-file
      compose convention so this is not rediscovered the hard way again
