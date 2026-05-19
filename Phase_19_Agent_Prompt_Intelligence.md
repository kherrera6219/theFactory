# Phase 19 — Agent Prompt Intelligence and PM Interview Loop

**Status:** Planned
**Last updated:** 2026-05-18
**Depends on:** Phase 15 (token ledger wired), Phase 18 (demo missions green)

---

## Problem

Every agent in the current system is addressed with a single-line role header:
`"You are AGENT-01-PM. Convert the operator request..."`.

The system already has rich per-agent persona data in
`services/orchestrator/orchestrator/agent_personas.py`: education backgrounds,
behavioral traits, working methods, protocol awareness, language-specific
guidance, and tooling references. None of this reaches the LLM at call time.
The persona system is purely cosmetic — used for Mission Control UI display,
not for shaping agent behavior.

Additionally, the PM intake phase is fire-and-forget. The feature contract
produces `clarifying_questions` but they are written into metadata and never
acted on. There is no interview loop — the mission proceeds immediately
regardless of ambiguity. For complex or underspecified prompts this produces
weak contracts and downstream quality degradation that is invisible until the
specialist generates poor output.

---

## Goals

1. Ground every agent LLM call in its full persona — role, traits, methods,
   protocols, language specialization — as a proper `system` prompt.
2. Propagate upstream risk signals (risk notes, uncertainty flags, clarifying
   questions) into downstream agent prompts so each agent inherits context
   from what the prior agent flagged.
3. Add a PM clarification loop: when the feature contract identifies high
   ambiguity, the mission pauses at a new `PM_CLARIFYING` state, surfaces
   questions to the user in Mission Control chat, collects answers, and
   re-generates the contract with that context before the CEO picks it up.
4. Enrich specialist prompts with per-language idioms, risk patterns, and
   tooling guidance from the existing `_LANGUAGE_GUIDANCE` and
   `_LANGUAGE_TOOLING` maps.

---

## Validated Entry State

- `agent_personas.py` contains `build_agent_system_prompt()` and all per-agent
  trait/method/protocol/language data.
- `llm_delegation.py` uses `_build_*_prompt()` helpers that produce a single
  user-turn string. The Anthropic, OpenAI, and Gemini call paths accept a
  `system` parameter but it is currently always empty or absent.
- `generate_pm_feature_contract()` returns `clarifying_questions` in the
  contract dict but nothing downstream reads or acts on them.
- Mission Control chat page has a conversational back-and-forth interface
  already wired to the backend PM endpoint.
- `MissionState` enum in `models.py` defines all current states. A new
  `pm_clarifying` value requires a migration and transition guard addition.

---

## Change 1 — Separate system and user prompts in every agent LLM call

### 1a. Add `system_prompt` parameter to `_call_with_recommendation()`

In `llm_delegation.py`, update the signature:

```python
async def _call_with_recommendation(
    *,
    recommendation: dict[str, Any],
    prompt: str,
    call_context: str,
    system_prompt: str | None = None,
) -> tuple[dict | None, str, str, str]:
```

Pass `system_prompt` through to each provider call:

```python
# _call_openai — add system message before user turn when present
messages = []
if system_prompt:
    messages.append({"role": "system", "content": system_prompt})
messages.append({"role": "user", "content": prompt})

# _call_anthropic — pass as top-level "system" field (Anthropic API)
payload = {
    "model": model,
    "max_tokens": max_tokens,
    "messages": [{"role": "user", "content": prompt}],
}
if system_prompt:
    payload["system"] = system_prompt

# _call_gemini — prepend as system_instruction field
payload = {
    "contents": [{"role": "user", "parts": [{"text": prompt}]}],
}
if system_prompt:
    payload["system_instruction"] = {"parts": [{"text": system_prompt}]}
```

### 1b. Add `build_agent_system_prompt()` call site helper

Add to `llm_delegation.py`:

```python
from .agent_personas import build_agent_system_prompt as _build_persona_prompt

def _system_prompt_for_agent(agent_id: str) -> str | None:
    """Return the full persona system prompt for an agent, or None on failure."""
    try:
        agent = next(
            (a for a in AGENT_REGISTRY if a.agent_id == agent_id), None
        )
        if agent is None:
            return None
        return _build_persona_prompt(agent)
    except Exception:
        return None
```

### 1c. Wire system prompts into every `generate_*` function

Each function already knows its agent ID. Thread `system_prompt` into every
`_call_with_recommendation()` call site:

```python
# generate_pm_feature_contract
system = _system_prompt_for_agent("AGENT-01-PM")
parsed, ... = await _call_with_recommendation(
    recommendation=recommendation,
    prompt=pm_prompt,
    call_context="pm feature contract",
    system_prompt=system,
)

# generate_ceo_delegation
system = _system_prompt_for_agent("AGENT-02-CEO")
...

# generate_mission_contract
system = _system_prompt_for_agent("AGENT-02-CEO")
...

# generate_logic_clusters
system = _system_prompt_for_agent("AGENT-02-CEO")
...

# generate_pod_manager_delegation — use resolved pod manager agent ID
system = _system_prompt_for_agent(pod_manager_agent_id)
...

# generate_pod_group_standard — same
system = _system_prompt_for_agent(pod_manager_agent_id)
...

# generate_specialist_plan — use resolved specialist agent ID
system = _system_prompt_for_agent(specialist_agent_id)
...

# generate_code_from_contract — same
system = _system_prompt_for_agent(specialist_agent_id)
...
```

No prompt content changes in this change — only the channel through which
agent identity is conveyed shifts from the user turn to the system prompt.
Existing JSON-only instructions stay in the user turn.

---

## Change 2 — Language-specific specialist prompt enrichment

### 2a. Inject language guidance into specialist prompts

In `_build_specialist_plan_prompt()` and `_build_code_generation_prompt()`,
add language-specific context before the JSON instruction block:

```python
# Add to _build_specialist_plan_prompt():
language_guidance = _LANGUAGE_GUIDANCE.get(language_key, "")
language_tooling = _LANGUAGE_TOOLING.get(language_key, "")

language_context = ""
if language_guidance or language_tooling:
    language_context = (
        f"\nLanguage discipline: {language_guidance}\n"
        f"Tooling references: {language_tooling}\n"
    )

return (
    f"You are {specialist_agent_id}...\n"
    + language_context
    + "Return only JSON...\n"
    + ...
)
```

Import `_LANGUAGE_GUIDANCE` and `_LANGUAGE_TOOLING` from `agent_personas.py`
into `llm_delegation.py`. They are already defined there — this is a single
import addition.

### 2b. Inject language guidance into code generation prompt

Same pattern for `_build_code_generation_prompt()`. The specialist generating
Rust code should be reminded of ownership model correctness; the Java specialist
should be reminded of JVM architecture patterns. This costs ~20 tokens per call
and meaningfully shapes idiomatic output.

---

## Change 3 — Upstream risk propagation

### 3a. Add a risk context helper

```python
def _format_upstream_risks(metadata: dict[str, Any]) -> str:
    """
    Summarize risk signals from upstream agents for injection into
    downstream prompts. Returns an empty string if no signals exist.
    """
    lines = []

    feature_contract = metadata.get("feature_contract") or {}
    fc_risks = feature_contract.get("risk_notes") or []
    fc_questions = feature_contract.get("clarifying_questions") or []
    if fc_risks:
        lines.append("PM risk notes: " + "; ".join(fc_risks[:3]))
    if fc_questions:
        lines.append("PM open questions: " + "; ".join(fc_questions[:3]))

    mission_contract = metadata.get("mission_contract") or {}
    mc_risks = mission_contract.get("risk_notes") or []
    if mc_risks:
        lines.append("CEO risk notes: " + "; ".join(mc_risks[:3]))

    if not lines:
        return ""
    return "\nUpstream risk context:\n" + "\n".join(f"  - {l}" for l in lines) + "\n"
```

### 3b. Inject into CEO, pod manager, and specialist prompts

In `_build_mission_contract_prompt()`, `_build_pod_manager_delegation_prompt()`,
`_build_specialist_plan_prompt()`, and `_build_code_generation_prompt()`, add:

```python
risk_context = _format_upstream_risks(mission_context)
# Insert risk_context into the prompt string before the JSON instruction block
```

Pass `mission_context` (which already contains full metadata) through to the
prompt builders that don't already receive it. `_build_specialist_plan_prompt`
already receives `mission_context` — add the risk injection there first.

---

## Change 4 — PM clarification loop

This is the highest-effort change and the most user-visible. Implement last
within this phase.

### 4a. Add `pm_clarifying` mission state

In `services/orchestrator/orchestrator/models.py`:

```python
class MissionState(str, enum.Enum):
    ...
    pm_clarifying = "PM_CLARIFYING"   # add after queued, before pm_intake
    ...
```

Add transition guard in `VALID_TRANSITIONS`:
```python
MissionState.queued: {MissionState.pm_intake, MissionState.pm_clarifying, MissionState.failed},
MissionState.pm_clarifying: {MissionState.pm_intake, MissionState.failed},
```

Create migration `V007_pm_clarifying_state.sql` — no schema changes needed
(state is a TEXT column), but document the new valid value.

### 4b. Add ambiguity scoring to PM feature contract generation

In `generate_pm_feature_contract()`, after receiving the parsed contract,
compute an ambiguity score:

```python
def _pm_ambiguity_score(contract: dict[str, Any], prompt: str) -> float:
    """
    Return a 0.0–1.0 ambiguity score for a feature contract.
    High score = PM is uncertain and questions should be asked before proceeding.
    """
    score = 0.0
    # Unanswered clarifying questions
    questions = contract.get("clarifying_questions") or []
    score += min(len(questions) * 0.15, 0.45)
    # Risk notes present
    risks = contract.get("risk_notes") or []
    score += min(len(risks) * 0.10, 0.20)
    # Very short prompt = underspecified
    if len(prompt.strip()) < 60:
        score += 0.20
    # Complexity is high/very_high but requirements are thin
    complexity = contract.get("estimated_complexity", "medium")
    reqs = contract.get("functional_requirements") or []
    if complexity in {"high", "very_high"} and len(reqs) <= 2:
        score += 0.20
    # human_approval_required flag set by PM
    if contract.get("human_approval_required"):
        score += 0.10
    return min(score, 1.0)
```

Add `ambiguity_score` to the returned contract dict.

### 4c. Pause mission at `PM_CLARIFYING` when ambiguity is high

In `_prepare_pm_intake()` in `mission_flow_v2.py`:

```python
PM_CLARIFY_THRESHOLD = float(os.getenv("PM_CLARIFY_THRESHOLD", "0.55"))
PM_CLARIFY_ENABLED = _setting_bool(settings, "pm_clarify_enabled", False)

ambiguity = feature_contract.get("ambiguity_score", 0.0)
questions = feature_contract.get("clarifying_questions") or []

if PM_CLARIFY_ENABLED and ambiguity >= PM_CLARIFY_THRESHOLD and questions:
    metadata["pm_clarification_pending"] = True
    metadata["pm_clarification_questions"] = questions
    metadata["pm_ambiguity_score"] = ambiguity
    metadata["feature_contract"] = feature_contract

    append_chain_event(
        metadata,
        event_type="MISSION_PM_CLARIFYING",
        agent_id=PM_AGENT_ID,
        details={
            "ambiguity_score": ambiguity,
            "question_count": len(questions),
            "questions": questions,
        },
    )
    # Persist and transition to PM_CLARIFYING — do not advance to CEO_DELEGATED
    await asyncio.to_thread(
        storage.update_mission_state,
        settings,
        mission_id,
        MissionState.pm_clarifying,
    )
    return  # Hold here — resume when answers arrive
```

### 4d. Add clarification answer endpoint

In `services/orchestrator/orchestrator/routes/internal.py`, add:

```python
@router.post("/missions/{mission_id}/pm-clarification")
async def submit_pm_clarification(
    mission_id: str,
    body: PMClarificationRequest,
    ...
):
    """
    Accept user answers to PM clarifying questions and resume
    the mission from PM_CLARIFYING state.
    """
    mission = storage.get_mission(settings, mission_id)
    if mission.state != MissionState.pm_clarifying:
        raise HTTPException(400, "Mission is not in PM_CLARIFYING state")

    metadata = with_chain_defaults(mission.metadata, mission.requested_target_language)
    prior_questions = metadata.get("pm_clarification_questions") or []
    answers = body.answers  # list[str] aligned to prior_questions

    # Rebuild feature contract with answers appended to original prompt
    enriched_prompt = _build_enriched_prompt(
        original_prompt=mission.prompt,
        questions=prior_questions,
        answers=answers,
    )
    feature_contract = await generate_pm_feature_contract(
        prompt=enriched_prompt,
        mission_type=metadata.get("mission_type", "BUILD_NEW"),
        depth_mode=metadata.get("depth_mode", "STANDARD"),
        output_mode=metadata.get("output_mode", "FULL_BUILD"),
        requested_target_language=mission.requested_target_language,
    )
    metadata["feature_contract"] = feature_contract
    metadata["pm_clarification_answers"] = answers
    metadata["pm_clarification_pending"] = False

    append_chain_event(
        metadata,
        event_type="MISSION_PM_CLARIFICATION_RECEIVED",
        agent_id=PM_AGENT_ID,
        details={"answer_count": len(answers)},
    )
    # Advance to pm_intake so the normal flow picks up from here
    await asyncio.to_thread(
        storage.update_mission_state,
        settings,
        mission_id,
        MissionState.pm_intake,
    )
    storage.update_mission_metadata(settings, mission_id, metadata)
    return {"status": "resumed", "mission_id": mission_id}


def _build_enriched_prompt(
    original_prompt: str,
    questions: list[str],
    answers: list[str],
) -> str:
    if not questions or not answers:
        return original_prompt
    qa_lines = []
    for q, a in zip(questions, answers):
        qa_lines.append(f"Q: {q}\nA: {a}")
    qa_block = "\n".join(qa_lines)
    return (
        f"{original_prompt}\n\n"
        f"Additional context from operator:\n{qa_block}"
    )
```

Add `PMClarificationRequest` Pydantic model:
```python
class PMClarificationRequest(BaseModel):
    answers: list[str]
```

Expose through API gateway at `POST /v1/missions/{mission_id}/pm-clarification`.

### 4e. Mission Control UI — clarification panel

In Mission Control mission detail page, when `mission.state === "PM_CLARIFYING"`:

```tsx
{mission.state === "PM_CLARIFYING" && metadata.pm_clarification_questions && (
  <ClarificationPanel
    questions={metadata.pm_clarification_questions}
    missionId={mission.mission_id}
    onSubmit={async (answers) => {
      await fetch(`/api/missions/${mission.mission_id}/pm-clarification`, {
        method: "POST",
        body: JSON.stringify({ answers }),
        headers: { "Content-Type": "application/json" },
      });
      // Poll mission state — it will advance to pm_intake then ceo_delegated
    }}
  />
)}
```

`ClarificationPanel` renders each question with a text input, a submit button,
and a note that answering is optional — the user can also skip to let the
mission proceed with the current contract.

Add a skip endpoint `POST /v1/missions/{mission_id}/pm-clarification/skip` that
clears `pm_clarification_pending` and advances to `pm_intake` with the existing
contract unchanged.

---

## Settings

Add to `services/orchestrator/orchestrator/settings.py` and `.env.example`:

```bash
# Phase 19 — Agent Prompt Intelligence
PM_CLARIFY_ENABLED=false          # Enable PM clarification loop
PM_CLARIFY_THRESHOLD=0.55         # Ambiguity score threshold (0.0–1.0)
```

Both default to off/permissive so existing behavior is fully preserved until
the operator enables them.

---

## Non-Goals

- Do not change the JSON schema of any existing agent output — only the system
  prompt channel and language enrichment change.
- Do not add multi-turn conversation history to non-PM agents in this phase.
  The clarification loop is PM-only.
- Do not block missions by default when `PM_CLARIFY_ENABLED=false`. The feature
  is opt-in.
- Do not change the agent model routing matrix — persona prompts ride on top of
  existing model assignments.
- Do not implement agent-to-agent clarification (e.g., specialist asking CEO
  a follow-up). That is a future phase.

---

## Validation

### Change 1 — System prompts
- [ ] `_call_with_recommendation()` accepts and passes `system_prompt` for all
      three providers (OpenAI, Anthropic, Gemini).
- [ ] PM, CEO, pod manager, and specialist LLM calls all send a non-empty system
      prompt in unit tests with a mocked provider.
- [ ] `_system_prompt_for_agent("AGENT-01-PM")` returns a non-empty string.
- [ ] `_system_prompt_for_agent("AGENT-UNKNOWN-999")` returns `None` without
      raising.

### Change 2 — Language enrichment
- [ ] `_build_specialist_plan_prompt()` for `language="rust"` includes rust
      ownership/lifetime guidance text.
- [ ] `_build_specialist_plan_prompt()` for `language="java"` includes JVM
      architecture text.
- [ ] `_build_specialist_plan_prompt()` for an unknown language produces no
      language context block (no KeyError).

### Change 3 — Risk propagation
- [ ] A feature contract with 2 risk notes and 2 clarifying questions produces
      a non-empty `_format_upstream_risks()` string.
- [ ] That string appears in the mission contract prompt and specialist plan
      prompt for the same mission.
- [ ] An empty feature contract (fallback) produces an empty risk context string
      with no error.

### Change 4 — PM clarification loop
- [ ] With `PM_CLARIFY_ENABLED=false` (default): no behavior change, existing
      tests pass unchanged.
- [ ] With `PM_CLARIFY_ENABLED=true` and a high-ambiguity prompt: mission
      transitions to `PM_CLARIFYING` state.
- [ ] `GET /v1/missions/{id}` for a `PM_CLARIFYING` mission exposes
      `pm_clarification_questions` in metadata.
- [ ] `POST /v1/missions/{id}/pm-clarification` with answers advances mission
      to `pm_intake` and re-generates the feature contract with enriched prompt.
- [ ] `POST /v1/missions/{id}/pm-clarification/skip` advances mission to
      `pm_intake` with original contract unchanged.
- [ ] Chain trace for a clarified mission includes `MISSION_PM_CLARIFYING` and
      `MISSION_PM_CLARIFICATION_RECEIVED` events.
- [ ] Mission Control renders the clarification panel when state is
      `PM_CLARIFYING`.
- [ ] `python -m pytest -q` passes on all touched files.
- [ ] `python -m ruff check services/orchestrator tests/services` passes.
- [ ] `npm --prefix apps/mission-control run lint` passes.
- [ ] `npm --prefix apps/mission-control run test` passes.
