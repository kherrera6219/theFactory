# Mission Taxonomy

Document version: 2026.08.03
Last updated: 2026-08-03
Status: Canonical
Audience: Operators, maintainers, AI coding agents, and anyone extending the mission surface

The four enums in `services/orchestrator/orchestrator/models.py` — `MissionType`,
`DepthMode`, `OutputMode`, `DataClassification` — are the product's actual
commercial surface. They decide what a mission does, how deeply, what it hands
back, and which compliance gates apply.

**None of them appeared in any design document.** They were invented during
construction, and until this file they were the largest unwritten specification
in the system (audit §5.1, UPG-72). This document is written **from the code**,
not from intent: every behaviour below cites the module that implements it, and
values that currently do nothing are labelled as such rather than described
aspirationally.

**Write this document's rules into any new value before adding one.** The matrix
is 10 × 5 × 8 × 4 = 1,600 nominal combinations; it stays tractable only because
most dimensions are independent and most values are inert.

---

## 1. `MissionType` — what kind of work this is

Ten values. This is the only dimension that changes *which agents run*.

| Value | Intent | AIM? | Perf-sensitive? | CEO routing strategy |
|---|---|---|---|---|
| `BUILD_NEW` | Generate new software from a prompt | ✗ | ✓ | Strongest codegen specialist for the language |
| `IMPORT_MODERNIZE` | Modernise an existing codebase | ✓ | ✓ | Specialist who understands legacy patterns |
| `PORT` | Re-implement source in a different language | ✓ | ✓ | **Two clusters** — extraction then generation |
| `DEBUG_REPAIR` | Locate and fix a defect | ✓ | ✗ | Deepest static-analysis/fault-isolation specialist |
| `SECURITY_HARDEN` | Close security weaknesses | ✓ | ✗ | Security-pattern specialist; Security + Compliance flagged |
| `REDUCE_DEPENDENCIES` | Replace third-party deps with first-party code | ✓ | ✓ | Import-intent specialist; DEPABS flagged |
| `RUN_QC` | Execute quality checks against existing code | ✗ | ✗ | **falls through to `BUILD_NEW`** |
| `ARCHITECTURE_DOCS` | Produce architecture documentation | ✗ | ✗ | **falls through to `BUILD_NEW`** |
| `ANALYZE_ONLY` | Extract understanding, generate nothing | ✓ | ✗ | Richest LogicNode coverage; no codegen |
| `SELF_ANALYZE` | Run the factory against its own codebase | ✗ | ✗ | **falls through to `BUILD_NEW`** |

**Implementing modules**

- **AIM column** — `aim_generator.AIM_REQUIRING_MISSION_TYPES`. A mission of one
  of the six ✓ types gets an Application Intelligence Map generated during
  intake; the other four do not.
- **Perf-sensitive column** — `hw_agent._PERFORMANCE_SENSITIVE_TYPES`. Only
  these four receive hardware-awareness hints.
- **CEO routing strategy** — `llm_delegation/prompts.py` `type_strategy`.
- **Mission mode number** — `mission_flow_v2/base._mission_mode_for_type` maps
  all ten to a stable integer 1–10 for the mission-charter schema. This mapping
  *is* complete; the gaps below are elsewhere.

> ### ⚠ Three mission types have no routing strategy
>
> `RUN_QC`, `ARCHITECTURE_DOCS`, and `SELF_ANALYZE` are absent from
> `type_strategy`, so `type_strategy.get(mission_type, type_strategy["BUILD_NEW"])`
> silently hands the CEO agent **`BUILD_NEW`'s** instruction — "select the pod
> whose language specialist has the strongest code generation capability."
>
> For `RUN_QC` and `ARCHITECTURE_DOCS`, which are not code-generation missions at
> all, that is the wrong instruction rather than a neutral default. It does not
> break the mission — the fallback is valid text and the pipeline completes — so
> the failure mode is *quietly suboptimal routing*, not an error anyone sees.
>
> This is a real gap, recorded rather than silently patched because writing three
> new strategies is a product decision about what those mission types should
> actually do. **Do not add an eleventh mission type without adding its
> strategy.**

### Aliases accepted at intake

`routes/internal.py` normalises several spellings before the enum is applied —
e.g. `QC` → `RUN_QC`, `ARCHITECTURE` → `ARCHITECTURE_DOCS`. Aliases are an
intake convenience; the canonical value is what is stored and matched.

---

## 2. `DepthMode` — how much rigour

Five values. Maps onto the mission-charter schema's depth vocabulary
(`mission_flow_v2/base._schema_depth_mode`).

| Value | Charter depth | Distinct behaviour |
|---|---|---|
| `SPRINT` | `quick_scan` | — |
| `STANDARD` | `standard` | Default when unset |
| `PRODUCTION` | `deep_audit` | — |
| `REGULATED` | `deep_audit` | **Forces human approval** before completion |
| `AUTONOMOUS_LONG_RUN` | `autonomous_long_run` | — |

**Only `REGULATED` changes runtime behaviour.** `security_compliance.py` treats
it as requiring human approval, exactly as it treats a `TIER_3_REGULATED` data
classification.

`PRODUCTION` and `REGULATED` **collapse to the same charter value**
(`deep_audit`) and differ only in that approval gate. `SPRINT`,
`STANDARD`, and `AUTONOMOUS_LONG_RUN` are currently labels: they are recorded,
surfaced in the charter, and carry no other consequence. Do not describe them to
users as changing how much work is done — today they do not.

---

## 3. `OutputMode` — what comes back

Eight values collapsing to three charter shapes
(`mission_flow_v2/base._schema_output_mode`).

| Value | Charter shape | Build artifact expected? |
|---|---|---|
| `ANALYZE_ONLY` | `report_only` | **No** |
| `PLAN_ONLY` | `report_only` | **No** |
| `RUN_QC` | `report_only` | **No** |
| `PATCH_PROPOSAL` | `patch_files` | Yes |
| `APPLY_PATCH` | `patch_files` | Yes |
| `FULL_BUILD` | `full_branch` | Yes |
| `DEPENDENCY_REDUCTION` | `full_branch` | Yes · triggers dependency absorption |
| `FULL_TRANSFORMATION` | `full_branch` | Yes |

**The artifact-expectation column is load-bearing.** `build_artifacts.py`
suppresses the generated-output completion gate for report-shaped modes, so an
`ANALYZE_ONLY` mission legitimately completes with no durable artifact while a
`FULL_BUILD` mission that produces none is blocked.

`DEPENDENCY_REDUCTION` is one of two triggers for dependency absorption
(`dependency_absorption.py`); the other is `MissionType.REDUCE_DEPENDENCIES`.
Either alone is sufficient.

> **Note on stale strings.** `build_artifacts.py` also accepts `REPORT_ONLY`,
> `REPORT`, and `ANALYZE` in its suppression set. **None is an `OutputMode`
> value.** They are defensive tolerance for older or externally-supplied
> metadata, not part of this taxonomy. Do not add them to the enum on the
> strength of that check.

---

## 4. `DataClassification` — regulatory handling

Four tiers. **Only the highest does anything.**

| Value | Behaviour |
|---|---|
| `TIER_0_PUBLIC` | None |
| `TIER_1_INTERNAL` | None |
| `TIER_2_SENSITIVE` | None |
| `TIER_3_REGULATED` | Adds a `data_classification_review` compliance check (advisory) **and forces human approval** before completion |

This is the "single binary gate" that
[DATA_CLASSIFICATION_POLICY.md](DATA_CLASSIFICATION_POLICY.md) describes: in
practice the system asks *is this mission regulated, yes or no*. The four-tier
shape exists in the enum and in the UI; three of the four tiers are
indistinguishable at runtime.

If your organisation needs genuine tier-differentiated retention, access control,
or incident response, **that must be built or enforced procedurally** — selecting
`TIER_2_SENSITIVE` today does not cause the system to treat the mission
differently from `TIER_0_PUBLIC`.

The api-gateway once tagged sensitive missions with the invented string
`TIER_2_RESTRICTED`, which matched no enum value and silently disabled
classification handling. That bug is fixed; it is noted here because it is
exactly the failure this document exists to prevent — **use the enum, never a
hand-written string.**

---

## 5. Valid combinations

The four dimensions are **independent**: any `MissionType` can carry any
`DepthMode`, `OutputMode`, and `DataClassification`, and nothing rejects a
combination. That is a deliberate simplicity, but a few pairings are
contradictory in practice and should be avoided or normalised at intake:

| Combination | Why it is contradictory | What actually happens |
|---|---|---|
| `ANALYZE_ONLY` type + `FULL_BUILD` output | The type generates nothing; the output demands an artifact | The completion gate expects an artifact that will never exist |
| `BUILD_NEW` + `ANALYZE_ONLY` output | Generation runs, then its output is not required | Mission completes; generated code may not be surfaced as an artifact |
| `RUN_QC` type + `FULL_TRANSFORMATION` output | QC inspects, it does not transform | Falls through to `BUILD_NEW` routing (§1) and expects an artifact |

**These are not enforced.** The safest coherent defaults are:

| MissionType | Natural OutputMode |
|---|---|
| `BUILD_NEW` | `FULL_BUILD` |
| `IMPORT_MODERNIZE`, `PORT` | `FULL_TRANSFORMATION` |
| `DEBUG_REPAIR`, `SECURITY_HARDEN` | `PATCH_PROPOSAL` or `APPLY_PATCH` |
| `REDUCE_DEPENDENCIES` | `DEPENDENCY_REDUCTION` |
| `ANALYZE_ONLY`, `ARCHITECTURE_DOCS`, `SELF_ANALYZE` | `ANALYZE_ONLY` or `PLAN_ONLY` |
| `RUN_QC` | `RUN_QC` |

---

## 6. Which gates a mission passes

Independent of the taxonomy, every mission producing generated output passes:

- **Equivalence (correctness)** — contract conformance; advisory by default
- **Equivalence (behavioural)** — execution against Phase 4 vectors; opt-in via
  `MISSION_EQUIVALENCE_PYTHON_EXECUTION_ENABLED`, advisory
- **Security compliance** — **blocking by default**
- **Runtime QC (RQCA)** — **blocking by default**

`REGULATED` depth or `TIER_3_REGULATED` classification adds a human-approval
requirement on top.

---

## 7. Before adding an eleventh value

Adding to any enum is cheap; the cost lands in the places that switch on it.
Check every one:

| Dimension | Must be updated |
|---|---|
| `MissionType` | `models.py` · `_mission_mode_for_type` · `type_strategy` (**the gap in §1 exists because this was skipped**) · `AIM_REQUIRING_MISSION_TYPES` if analysis is needed · `_PERFORMANCE_SENSITIVE_TYPES` if relevant · intake aliases in `routes/internal.py` · Mission Control labels · this document |
| `DepthMode` | `models.py` · `_schema_depth_mode` · approval logic in `security_compliance.py` if it should gate · this document |
| `OutputMode` | `models.py` · `_schema_output_mode` · the artifact-expectation set in `build_artifacts.py` (**omitting it silently means "artifact required"**) · this document |
| `DataClassification` | `models.py` · `security_compliance.py` · [DATA_CLASSIFICATION_POLICY.md](DATA_CLASSIFICATION_POLICY.md) · this document |

**A value that is added to `models.py` and nowhere else is not a feature — it is
a label that an operator can select and that changes nothing.** Three such values
already exist in `DataClassification` and three in `DepthMode`; that is the
current honest state, not a target to grow.

## Related

- [ADR_DESIGN_RECONCILIATION_2026-08-01.md](ADR_DESIGN_RECONCILIATION_2026-08-01.md) — row 19 records this taxonomy as Implemented-but-undesigned
- [MODELS_AND_DOMAIN_SCHEMA.md](MODELS_AND_DOMAIN_SCHEMA.md) — the enums' field-level definitions
- [DATA_CLASSIFICATION_POLICY.md](DATA_CLASSIFICATION_POLICY.md) — what classification does and does not enforce
- [WHAT_THEFACTORY_IS_AND_IS_NOT.md](WHAT_THEFACTORY_IS_AND_IS_NOT.md) — product boundaries
