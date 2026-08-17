# PM-led SOW Factory Plan

Document version: 2026.08.17
Last updated: 2026-08-17
Status: Canonical — P0–P4 on `main`; live PORT-through-SOW and failing-QC-blocks-COMPLETE recorded 2026-08-17
Audience: Maintainers, operators, and AI coding agents

This is the execution plan for the end state: a 41-role factory whose **face**
is the PM agent. The user creates **new** software or **imports** existing
software for rework / port / update through that PM, receives a real Statement
of Work (including a factory cost estimate) **before** they approve, then gets
tested, QC'd work saved locally.

**Do not start P1+ until P0 is green.** P0 is wiring and enforcement, not UI.

Companion: `docs/WORK_QUEUE.md` (ordered remaining factory work),
`docs/CURRENT_TODO.md`, `docs/HANDOFF_CURRENT.md`.

## Status of this plan (2026-08-17)

P0–P4 are on `main`. Live proof:
[`docs/evidence/end_state_live_proof_20260817.json`](evidence/end_state_live_proof_20260817.json).

| Claim | Result |
|---|---|
| PORT through an accepted SOW | `mission-dc0c8c4e` `COMPLETE`. Official type `PORT`. Files `go.mod` + `main.go`. |
| Failing factory QC blocks COMPLETE | `mission-8db1af71` stayed `VERIFIED`. `qc_verdict=FAIL`, `MISSION_RUNTIME_QC_BLOCKED`. |

Python QC uses `python -m unittest discover` because `python:3.11-slim`
has no pytest. RQCA probes `SANDBOX_EXECUTOR_URL`, not local `docker info`.

Still owed: Chat ZIP UI walkthrough (the proof used the same `/v1/sows` +
`/v1/missions` APIs Chat Accept calls), spend-cap pause live, failure
injection, provider fallback, EDCP live-bus.

---

## 1. Opinion (locked)

**Yes — put a cost estimate on the SOW before they approve.** Confirm and Start
today is “start the factory,” not “accept the bid.”

The estimate is **honest factory spend** (LLM tokens + wall-clock range + cap),
not a made-up human-agency quote. Inventing “this Snake game is a $12,000
engagement” is fiction. Showing “this run will likely spend $0.40–$0.90 of
Gemini; cap $1.50; we stop and ask if we hit the cap” is a product.

The PM is product + program + sales **for the factory**. They sell a scoped
build the plant can actually deliver.

---

## 2. Standards and best practices this plan follows

Research applied to this design (not cargo-culted). Each item maps to a
concrete rule in §3–§6.

### 2.1 Statement of Work

Sources: Institute of Project Management SOW guidance (2026); GFOA *Developing
a Concise, Yet Comprehensive, Statement of Work* (Feb 2026); commercial SOW
practice (Sirion, Icertis).

| Practice | How we apply it |
|---|---|
| Scope **and** out of scope, both explicit | `out_of_scope[]` is required. Empty out-of-scope is a defect, not a default. |
| Deliverables with acceptance (GFOA DED: purpose, scope, how you know it is done) | Each deliverable has `name`, `artifact_hint`, and maps to at least one acceptance bullet. |
| SMART / testable acceptance | Acceptance criteria must be fail-able. “Mission completes without error” is not enough once a real SOW exists. |
| Change management | Continue-with-PM is a **change order** (delta scope + delta estimate), not a silent new mission. |
| Numbered, referenceable sections | SOW schema uses stable keys so chat, charter, and audit cite the same sections. |
| Simple language | PM prompt: write for the operator, not to impress. No IR/PEP boilerplate. |

The factory SOW is **not** a full ISO/IEC/IEEE 29148 Software Requirements
Specification. IEEE 830 was superseded by **ISO/IEC/IEEE 29148:2018**. That
standard’s quality bar still applies to **acceptance and requirements**:
unambiguous, verifiable, consistent, traceable. We implement a **customer SOW**
(BRS-lite) plus testable acceptance — not a 40-page SRS.

### 2.2 Estimation (Cone of Uncertainty)

Sources: Boehm / McConnell *Cone of Uncertainty* (Construx); SEI software cost
estimation; 2026 buyer playbooks (range estimates, not point estimates).

| Practice | How we apply it |
|---|---|
| No single-point estimate at idea stage | Quote **likely** and **high**, never one dollar figure. |
| Early estimates can be 0.25×–4× | High band is conservative. Cap = `high_usd × 1.5` (configurable). |
| Variability shrinks only when scope shrinks | Estimate is recomputed when the operator edits scope or engagement type. |
| Document the basis | `cost_estimate.basis` records complexity, assumed call graph, model, rate date. |
| Three-point thinking | We expose likely + high + cap (PERT-style), not a fake “exact” bid. |

### 2.3 LLM FinOps / spend control

Sources: LLMOps cost management (visibility, budgets at multiple levels,
graduated response); token-budget practice (1.7–2.0× overhead for retries,
system prompts, context); hard spend limits so a run cannot silently burn.

| Practice | How we apply it |
|---|---|
| Estimate from tokens × published rates | Use `llm_cost_ledger._PRICING` (`gemini-3.7-flash` $0.75 / $3.75 per 1M). |
| Overhead multiplier | Apply **1.7×** on the likely band and **2.0×** on the high band for retries / prompts / context. |
| Budget at mission level | `cap_usd` is the mission token budget. |
| Graduated response | Approach cap → warn in events. Hit cap → pause (do not keep calling). |
| Visibility | CostPanel shows **quoted vs actual vs cap**. Preview PM calls (no mission_id yet) stay unattributed or tagged `preview`. |
| Do not invent labor rates | Forbidden in prompts and UI copy. |

### 2.4 Coding and testing standards (this repo + new modules)

Existing repo rules stay in force (`AGENTS.md`, `docs/TESTING_QUALITY_GATES.md`):

- Code is truth. No fictional agent states in the UI.
- Orchestrator API contract changes need an explicit note in the PR.
- Security controls (replay, dedup, circuit breakers) must not regress.
- Extractor changes need fixture comparison (not in this plan’s P0–P1).
- `ruff` + targeted pytest for Python; `tsc --noEmit` + Vitest for Mission Control.

**Additional rules for new SOW / estimator / persist code:**

| Rule | Why |
|---|---|
| Estimator is **pure** (no I/O) | Deterministic unit tests; no network, no Docker. |
| Persist approved SOW **outside** the 4096-byte mission metadata bag | Launch already sheds context to avoid 422. |
| Intake **must not** regenerate an accepted bid | The signed snapshot is the contract. Intake may add execution notes only. |
| Additive schema | New fields optional for old missions; required for new Accept-SOW launches. |
| Fail closed on missing estimate | Cannot Accept SOW if `cost_estimate` is absent or `pricing_known` is false without an explicit “unpriced, proceed anyway” flag. |
| Tests written **with** the module, not after | Every new public function has a test that failed against the pre-function stub. |

---

## 3. Current gaps (code)

- Chat shows a slim card (title, scope, fake `~6/~12 min`). Full contract
  fields already exist and are hidden (`chat/page.tsx`, `types.ts`).
- Preview contract ≠ persisted contract. `phases_intake.py` regenerates PM.
- Gateway `MissionCreate` drops `mission_type`. Runtime reads
  `metadata.mission_type`, default `BUILD_NEW`. Repo sends unofficial aliases.
- Import is a separate page that `createMission`s without an SOW.
- Cost exists only **after** spend (`CostPanel.tsx`, `llm_cost_ledger.py`).
- Local `.env` may still have `RQCA_ENFORCEMENT_ENABLED=false`.
- PORT two-phase is not injected by compose.

---

## 4. Target UX

Chat is the front door for new **and** import.

1. User describes work or attaches a ZIP.
2. PM asks product/program questions (in/out of scope, success, language).
3. Right panel is a **Statement of Work**: engagement type, in/out of scope,
   deliverables, acceptance, assumptions, risks, **likely / high / cap USD**,
   factory time range.
4. **Accept SOW and start** persists the snapshot, then launches.
5. Factory runs. Tests run. FAIL blocks. Files go to `output/<mission_id>/`.
6. Cost panel: quoted vs actual. Hit cap → pause.

Footnote on every estimate: “This is model spend for this run, not a human
project quote.”

---

## 5. Workstreams

### P0 — Trust and wiring (no SOW UI)

- `.env`: `RQCA_ENFORCEMENT_ENABLED=true`.
- Compose: inject `PORT_TWO_PHASE_ENABLED`.
- Gateway: persist `mission_type`, `output_mode`, `depth_mode`,
  `data_classification` on the record **and** metadata.
- Alias map: `analyze` → `ANALYZE_ONLY`; `update` / `add_feature` /
  `refactor` → `IMPORT_MODERNIZE`; add **Port** → `PORT`.
- Live intake: pass `metadata.source_code` / repo summary into
  `generate_pm_feature_contract` (preview already can).
- Prove: broken generated test → FAIL → no COMPLETE.

### P1 — SOW + estimate + Accept

- Additive `feature_contract.v1` fields: `engagement_type`, `out_of_scope[]`,
  `deliverables[]`, `timeline`, `cost_estimate`.
- PM prompt: SOW voice; must fill out-of-scope; must not invent labor dollars.
- Pure estimator: complexity × call graph × ledger rates × 1.7/2.0 overhead.
- Persist approved SOW (orchestrator table or object store + pointer). Set
  charter `approved_at` / `approved_by`.
- Intake **loads** the snapshot; does not regenerate scope.
- Chat: replace slim card with SOW panel. Kill file-count duration.

### P2 — Import through the same PM

- Chat “Attach project (ZIP)” via existing `/api/repo/import` + review.
- Repo page launch goes to chat with archive attached, not a raw
  `createMission` with an unofficial type.
- Specialist `_codegen_context` includes bounded source / AIM / PORT nodes.
- Import/port delivery is a **file tree** when the SOW promised one.
- Prove: ZIP → chat SOW → `IMPORT_MODERNIZE` or `PORT` → COMPLETE →
  `output/<id>/`.

### P3 — Spend control and change orders

- Approach cap → event. Hit cap → pause until operator raises cap.
- Continue-with-PM = change-order SOW (delta scope + delta estimate).
- CostPanel: quoted vs actual vs cap.

### P4 — Ship locally

- Sandbox off orchestrator `docker.sock` onto `sandbox-runner`
  (`SANDBOX_EXECUTOR_URL`). AGENT-41-RQCA still owns the verdict. **Done
  in condensed topology.**
- One live EDCP mission only.
- Deeper PORT/Python first.

**Will not do:** reopen 14→4→1 or LLVM; labor-hour pricing; 41 models per
mission; SOW only in 4 KB metadata; intake rewrite of an accepted bid.

---

## 6. Required new tests (write with the code)

Every new public function below needs a test that is proven to fail against a
stub / pre-change tree (`git stash` or an empty return). Names are the
functions to add; tests live next to existing suites.

### P0 — `tests/services/test_api_gateway_mission_create_types.py` (new)

| Test | Function / behavior |
|---|---|
| `test_gateway_persists_mission_type_on_record_and_metadata` | `MissionCreate` accepts `mission_type`; orchestrator persist body includes it |
| `test_gateway_persists_output_mode_depth_and_classification` | same for the three sibling fields |
| `test_unofficial_repo_aliases_normalize_to_official_enum` | `normalize_mission_type("update") == IMPORT_MODERNIZE`, `"analyze" → ANALYZE_ONLY`, `"port" → PORT` |
| `test_unknown_mission_type_fails_closed_not_build_new` | unknown string does **not** silently become `BUILD_NEW` |
| `test_intake_passes_source_code_into_pm_contract` | `_prepare_pm_intake` calls `generate_pm_feature_contract` with `source_code` when metadata has it |

Also extend `tests/services/test_mission_flow_v2.py` for the source_code
forwarding assertion.

### P1 estimator — `tests/services/test_sow_estimator_unit.py` (new)

Target module: `services/orchestrator/orchestrator/sow_estimator.py` (new).

| Test | Function |
|---|---|
| `test_estimate_uses_ledger_rates_for_gemini_37_flash` | `estimate_mission_cost(...)` matches `_PRICING["gemini"]["gemini-3.7-flash"]` |
| `test_estimate_is_a_range_not_a_point` | returns `likely_usd < high_usd < cap_usd` |
| `test_high_band_applies_2x_overhead` | high includes 2.0× retry/context multiplier |
| `test_likely_band_applies_1_7x_overhead` | likely includes 1.7× |
| `test_unknown_model_sets_pricing_known_false` | no invented rate |
| `test_complexity_scales_call_graph` | `very_high` likely > `low` likely for same type |
| `test_port_engagement_includes_two_phase_calls` | PORT call graph > BUILD_NEW |
| `test_estimator_is_pure_no_io` | no `httpx` / docker / env reads inside the function |
| `test_basis_records_model_and_rate_date` | `basis` is non-empty and cites model id |

### P1 schema / persist — `tests/services/test_sow_document_unit.py` (new)

| Test | Function |
|---|---|
| `test_normalize_rejects_empty_out_of_scope` | `_normalize_feature_contract` / new `_normalize_sow` |
| `test_normalize_requires_deliverable_acceptance_link` | deliverable without a mapped acceptance fails closed or is dropped with a warning field |
| `test_persist_approved_sow_round_trip` | `save_approved_sow` / `load_approved_sow` |
| `test_approved_sow_does_not_fit_in_metadata_budget` | document is stored out-of-band; launch metadata only carries `sow_id` + digest |
| `test_intake_uses_approved_snapshot_not_regenerated_contract` | `_prepare_pm_intake` does not call `generate_pm_feature_contract` for scope when `sow_id` is present |
| `test_intake_may_add_execution_assumptions_only` | extra assumptions append; title/scope/cost do not change |
| `test_accept_without_cost_estimate_is_rejected` | API 422 unless `unpriced_ack=true` |
| `test_charter_approved_at_set_on_accept` | `approved_at` / `approved_by` populated |

### P1 chat UI — `apps/mission-control/app/(shell)/chat/sow-panel.test.ts` (new)

| Test | Behavior |
|---|---|
| `test_sow_panel_renders_out_of_scope_and_estimate` | right panel shows out of scope + likely/cap |
| `test_file_count_duration_heuristic_is_gone` | no `~6 minutes` / `~12 minutes` from `files.length` |
| `test_accept_sends_sow_id_not_full_document_in_metadata` | `createMission` metadata includes `sow_id` |
| `test_cannot_accept_when_estimate_missing` | button disabled / error |
| `test_edit_scope_recomputes_estimate` | changing engagement type refetches estimate |
| `test_labor_dollar_copy_is_not_shown` | footnote present; no “project quote” dollars |

### P2 import-through-PM — extend `test_mission_flow_v2.py` + chat tests

| Test | Behavior |
|---|---|
| `test_chat_zip_attach_sets_official_mission_type` | ZIP + “port” → metadata `PORT` |
| `test_codegen_context_includes_repo_bundle_for_import` | `_codegen_context` has source or AIM nodes when `IMPORT_MODERNIZE` |
| `test_repo_page_launch_redirects_to_chat_not_createMission` | (UI) launch path hits chat with archive token |
| `test_import_delivery_writes_tree_when_sow_lists_multiple_files` | more than one file under `output/<id>/` |

### P3 spend cap — `tests/services/test_sow_spend_cap_unit.py` (new)

| Test | Function |
|---|---|
| `test_spend_below_warn_threshold_does_not_pause` | `check_mission_spend_cap` |
| `test_spend_at_cap_pauses_mission` | state → pause / clarifying-equivalent |
| `test_raise_cap_resumes` | after operator ack |
| `test_cost_panel_quote_vs_actual` | API shape includes `quoted_usd`, `actual_usd`, `cap_usd` |

### P0/P1 regression (existing files)

- `tests/services/test_llm_cost_ledger_unit.py` — estimator must use the same
  rate table (import, do not fork numbers).
- `tests/services/test_llm_delegation_unit.py` — PM prompt contains out-of-scope
  instruction and forbids labor quotes; specified Snake still asks no arcade
  questions.
- `apps/mission-control/app/lib/api-client.test.ts` — `createMission` can send
  `mission_type` and `sow_id`.

---

## 7. Implementation slices (PR-sized)

1. Gateway mission-type persist + alias map + `.env` / compose flags + P0 tests.
2. `sow_estimator.py` + `test_sow_estimator_unit.py` (no UI).
3. SOW normalize + persist + intake honors snapshot + `test_sow_document_unit.py`.
4. Chat SOW panel + Accept + Vitest.
5. Chat ZIP attach + specialist sees source + import delivery tree.
6. Spend cap + quoted vs actual.
7. Sandbox off orchestrator (after 1–4).

---

## 8. Success bar

1. Specified stdlib Snake — **recorded.** SOW with out-of-scope + token
   range; tests run; FAIL blocks COMPLETE (`mission-8db1af71`).
2. Chat + ZIP update — **APIs recorded.** Same `/v1/sows` + `/v1/missions`
   path Chat Accept uses. Chat ZIP UI walkthrough still owed.
3. PORT (small real tree) — **recorded.** `mission-dc0c8c4e` official type
   `PORT`; output `go.mod` + `main.go`.
4. User rejects SOW / edits cap — in code; live walkthrough still owed.
5. Spend approaches cap — in code; live walkthrough still owed.

When 2, 4, and 5 are as boring as 1 and 3, this plan is done.
