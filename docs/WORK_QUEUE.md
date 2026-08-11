# Combined Work Queue

Document version: 2026.08.11
Last updated: 2026-08-11
Status: Canonical execution order
Audience: Maintainers and AI coding agents

One ordered, de-duplicated queue merged from `PRODUCTION_COMPLETION_PLAN.md`,
`docs/HANDOFF_CURRENT.md` (Next Actions), and `docs/CURRENT_TODO.md`. Those
remain the source of detail; this file is the order of work and the single place
that says what is actually next.

Items already verified complete against live source are **not** listed. See the
"Validation against live source" table in `PRODUCTION_COMPLETION_PLAN.md` for
what was dropped and why — Sprints 0.1 and 1.3 were already done, and the
substantive half of 3.1 as well.

## Ordering rationale

Verification integrity comes first. Several downstream exit criteria read "live
suites still green", and that criterion can currently pass having verified
nothing — so the gates get fixed before they are used to certify anything else.
Cheap self-contained hardening follows, then evidence, then features.

---

## Tier 1 — Fix the gates before trusting them

| # | Item | Source | Why first |
|---|---|---|---|
| 1 | Live suite silently skips: `LIVE_HTTP_TIMEOUT_SECONDS` defaults to 4.0s, the probe reads the resulting `OSError` as "stack unreachable", and the run reports **exit 0 having verified nothing** | Handoff NA-3 | Every later evidence item depends on this suite meaning something |
| 2 | Mission Control polling exhausts the gateway rate limit (120/min shared key, ~13 req/poll) so mission creation 429s for every other client | Handoff NA-4 | Blocks running the live suite without stopping the UI |
| 3 | Pin `kotlin` / `scala` / `zig` / `ocaml` sandbox images by digest — no official image, mutable tags, `euantorano/zig:master` moves | Handoff NA-2 | These images are the containment for untrusted generated code |

## Tier 2 — Evidence

| # | Item | Source |
|---|---|---|
| 4 | Sprint 0.2 — durable S1-01 / UPG-20 evidence file under `docs/evidence/` | Plan 0.2 |
| 5 | Sprint 1.1 — multi-mission live proof matrix: UI-driven mission, a PORT/transform, a non-Python language, failure injection, provider fallback | Plan 1.1 |

## Tier 3 — Features and decisions

| # | Item | Source | Note |
|---|---|---|---|
| 6 | Sprint 2.1 — Delta consumer as pod-audit gate (`main.py:505` still `handlers = {"sigma": …}`) | Plan 2.1 | First lane where a down consumer must block a mission |
| 7 | Sprint 1.2 — BUILD_NEW behavioural-equivalence decision | Plan 1.2 | Option 2 is now far cheaper: artifact execution exists for 19 languages |
| 8 | Sprint 3.2 — Repo ZIP import Phases 5–7 (launch guard, knowledge ingestion, context loading) | Plan 3.2 | |
| 9 | Sprint 3.1 — Electron: the three lifecycle decisions + installer/uninstall tests | Plan 3.1 | **Needs user sign-off**, not just code |
| 10 | Sprint 3.3 — operator polish; real LogicNode graph needs a transform mission | Plan 3.3 | |

## Tier 4 — Production hardening and release

| # | Item | Source | Note |
|---|---|---|---|
| 11 | Move sandbox execution out of the orchestrator into `agent-41-rqca` | Handoff NA-5 | The orchestrator currently mounts `/var/run/docker.sock` — effectively host root. Acceptable for local dev, must not ship |
| 12 | C# offline runtime (`dotnet-script` uninstallable with `--network=none`) | Language matrix | Currently an honest DRY_RUN; lowest priority |
| 13 | Sprint 4.1 — measurement before enforcement; ≥20 missions before raising `MISSION_EQUIVALENCE_ENFORCEMENT_ENABLED` | Plan 4.1 | |
| 14 | Sprint 4.2 — final documentation and promotion package | Plan 4.2 | |
| 15 | Resolve the date skew: plan says 2026-08-07, harness says 2026-08-10, container clocks say 2026-08-11 | Plan validation | Evidence filenames are minted by date and the promotion gate consumes them |

---

## Progress

- [x] **1 — live-suite silent skip** *(2026-08-11)*. Root cause was not the
  timeout: `localhost` resolves `::1` first on Windows while compose binds IPv4
  only, measured at **2.09s vs 0.02s**, which pushed the first request past the
  4.0s budget. Both suites now default to `127.0.0.1`, share one timeout policy
  via `live_stack_auth` (they had drifted to 4.0s and 30.0s), and every skip
  says **"NOTHING WAS VERIFIED"**. `LIVE_STACK_REQUIRED=1` turns any skip into a
  failure — set it for any run whose output becomes evidence.
  **Live-verified 2026-08-11**: the suite runs with zero env overrides and
  under `LIVE_STACK_REQUIRED=1`; it previously needed a 30s override or it
  skipped green.
- [x] **2 — UI rate-limit exhaustion** *(2026-08-11)*. Read and write traffic
  now use separate Redis buckets: polling a dashboard is not abuse, and
  counting ~13 GETs per cycle against the same 120/min allowance as mission
  creation let one open browser tab 429 every other client. Writes keep the
  tighter budget (`API_RATE_LIMIT_PER_MINUTE`); reads get
  `API_READ_RATE_LIMIT_PER_MINUTE` (600). This separates the buckets, it does
  not relax the write limit.
- [x] **3 — pin non-official sandbox images by digest** *(2026-08-11)*. Seven
  pinned, not the four originally scoped: `mathicsorg/mathics:latest`,
  `denoland/deno:latest` and `euantorano/zig:master` were all floating.
  `test_non_official_sandbox_images_are_pinned_by_digest` fails if one reverts
  to a mutable tag.
- [ ] 4 — S1-01 evidence *(blocked: needs a live stack)*
- [ ] 5 — multi-mission live proof matrix *(blocked: needs a live stack)*
- [x] **6 — Delta consumer gate (EDCP-02a)** *(2026-08-11)*. `handlers` now
  registers `delta`; a consumed verdict is recorded on the mission and
  `_advance_verified_to_complete` refuses COMPLETE without a *passing* one.
  Absence blocks — that is the exit criterion: a **down consumer stalls the
  mission visibly** instead of letting it complete as though audited.
  Correlation is prefix-parsed, never compared for equality. Inert unless
  `EVENT_DRIVEN_CONTROL_PLANE_ENABLED`. Not yet exercised against a live bus
  (stack is down).
- [ ] 7 — BUILD_NEW equivalence decision
- [ ] 8 — repo ZIP Phases 5–7
- [ ] 9 — Electron decisions *(blocked on user sign-off)*
- [ ] 10 — operator polish
- [ ] 11 — sandbox out of the orchestrator
- [ ] 12 — C# offline runtime
- [ ] 13 — measurement before enforcement
- [ ] 14 — release package
- [x] **15 — date skew** *(2026-08-11)*. Resolved: host and container clocks
  agree on **2026-08-11**. Docs written earlier in the session carried
  2026-08-06, taken from a container timestamp read during a long-running
  session; 19 occurrences corrected.

---

## Stack state — 2026-08-11

**Recovered.** 55 containers running; gateway and orchestrator both ready.

Earlier in the session only 6 of 55 were up, the rest exited **137** — almost
certainly Docker Desktop shutting down across the several days this session
spanned, not memory exhaustion (the host has 31 GiB and 28 CPUs allocated).

Diagnostic worth keeping: the orchestrator answered `/livez` in milliseconds
while `/health` and `/readyz` hung for tens of seconds, because both call the
object store and `minio` had died. Docker still reported the container
`healthy` — a stale status, since the healthcheck itself was hanging. "Healthy
but hanging" points at a *dependency* death, not the service's own.

On restart `/readyz` returns 503 until Milvus finishes warming (~1 min); every
other adapter is ready immediately. That is normal, not a fault.

### Verified in the rebuilt image

| | |
|---|---|
| `pypdf` | 6.15.0 (was 6.14.2) |
| `langgraph-checkpoint-postgres` | 3.1.1 (was 3.1.0) |
| Docker CLI | 29.7.2 (was 27.5.1) |
| compose plugin | absent, intended — see the orchestrator Dockerfile |

Disk is the real pressure, not memory: 64 GB reclaimable images and 21 GB build
cache. Worth a `docker system prune` when convenient — not run here, since it
is destructive and was not asked for.
