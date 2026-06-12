# Prompt Registry and Prompt Assets

Document version: 2026.06.11  
Last updated: 2026-06-11  
Status: Canonical  
Audience: Developers, agent contributors, and LLM integration engineers

---

## Purpose

The prompt registry and prompt assets layer is the system's **prompt engineering surface** — the component responsible for storing, versioning, resolving, and serving the structured text instructions that drive all 41 agents in the orchestrator. It sits between agent persona definitions (`agent_personas.py`) and live LLM API calls (`llm_delegation/`), functioning as a centralized vault that ensures every agent always executes with the correct, tested prompt at the correct version.

---

## Code Location

| File / Directory | Description |
|---|---|
| `services/orchestrator/orchestrator/prompt_registry.py` | Registry class: registers, resolves, and validates prompt assets by agent key and version |
| `services/orchestrator/orchestrator/prompt_assets/` | Directory: stores all raw prompt asset files consumed by the registry |

---

## Architecture Overview

The prompt layer operates as a **read-at-runtime, write-at-deploy** system. Prompt assets are authored and committed to the repository; the registry reads them at orchestrator startup and makes them available to agents via a keyed lookup interface. No prompt text is written at runtime — this is intentional to ensure auditability and reproducibility.

```
Agent Persona (agent_personas.py)
        │
        │  requests prompt by agent_key + version
        ▼
  PromptRegistry (prompt_registry.py)
        │
        │  resolves from
        ▼
  prompt_assets/
     ├── system/          # System-level persona scaffolds
     ├── mission/         # Mission-phase instructions
     ├── verification/    # Audit and verification agent prompts
     └── pod/             # Pod-worker language-extraction prompts
        │
        ▼
  LLM Delegation Layer (llm_delegation/)
```

---

## Prompt Asset Conventions

All prompt assets follow these conventions:

- **File format:** Plain text (`.txt`) or Markdown (`.md`). Structured templates use `{{variable}}` placeholder syntax.
- **Naming convention:** `{AGENT_KEY}_{ROLE}_{VERSION}.txt` — e.g., `AGENT-05-ARCH_system_v1.txt`.
- **Versioning:** Version is embedded in the filename. The registry resolves the highest available version unless an explicit version pin is provided by the calling agent.
- **No secrets in prompt assets:** API keys, credentials, or environment-specific values must never be embedded in prompt files. Use placeholder tokens resolved at runtime via environment configuration.
- **Prompt drift detection:** The registry computes a SHA-256 fingerprint of each loaded asset at startup and emits a structured log entry. Any change to a prompt asset between deployments is detectable via the audit log.

---

## PromptRegistry API

### `get(agent_key: str, role: str = "system", version: str | None = None) -> str`

Returns the prompt text for the given agent key and role. If `version` is `None`, the latest registered version is returned.

```python
from orchestrator.prompt_registry import PromptRegistry

registry = PromptRegistry()
text = registry.get("AGENT-05-ARCH", role="system")
```

### `register(agent_key: str, role: str, version: str, content: str) -> None`

Registers a prompt programmatically. Primarily used in tests and fixture loading; production prompts are always file-backed.

### `list_assets() -> list[dict]`

Returns a manifest of all registered assets with keys, roles, versions, and SHA-256 fingerprints. Used by the audit worker to include the prompt manifest in the chain-of-custody evidence bundle.

---

## Integration Points

| Consumer | How it uses the registry |
|---|---|
| `agent_base.py` | Calls `registry.get(self.agent_key, role="system")` to populate the system message on every LLM call |
| `mission_flow_v2/` | Fetches mission-phase instructions (role=`"mission"`) for phase-specific agent context |
| `audit_events.py` | Reads `list_assets()` at mission completion to embed the prompt manifest in the evidence bundle |
| `rqca_agent.py` | Loads verification prompts (role=`"verification"`) for its QC pass |

---

## Adding or Updating a Prompt Asset

1. Create or edit the `.txt` file in the appropriate `prompt_assets/` subdirectory following the naming convention.
2. Bump the version suffix if modifying an existing prompt (e.g., `_v1.txt` → `_v2.txt`). **Do not edit a versioned file in place** — this breaks audit reproducibility.
3. Run `pytest services/orchestrator/tests/test_prompt_registry.py` to confirm the registry loads and fingerprints the new asset correctly.
4. Commit the new asset file and any updated tests together.

---

## Relationship to Agent Personas

Agent personas (`agent_personas.py`) define the **identity, capability profile, and LLM routing recommendation** for each agent. Prompt assets define the **actual instructions** that agent executes. A persona without a matching prompt asset will raise a `PromptNotFoundError` at startup. The registry validates coverage for all 41 registered agents during the orchestrator boot sequence.

---

## Audit Traceability

Every mission's evidence bundle includes:

- **Prompt manifest:** agent key, role, version, and SHA-256 fingerprint for every prompt invoked during the mission
- **Prompt delta log:** any fingerprint changes detected since the previous mission (useful for regression attribution)

This ensures that a mission output can always be traced back to the exact prompt text that produced it.

---

## See Also

- [LLM_DELEGATION.md](LLM_DELEGATION.md) — provider-aware LLM routing that consumes resolved prompts
- [AGENT_PERSONA_STANDARDS_EVIDENCE_2026-03-02.md](AGENT_PERSONA_STANDARDS_EVIDENCE_2026-03-02.md) — persona definitions and evidence model
- [AGENT_LLM_PROVIDER_MODEL_MATRIX_2026-03-02.md](AGENT_LLM_PROVIDER_MODEL_MATRIX_2026-03-02.md) — model matrix referenced during prompt construction
- [APPLICATION_INTELLIGENCE_MAP.md](APPLICATION_INTELLIGENCE_MAP.md) — AIM artifact that prompt assets contribute to
