# Prompt Registry and Prompt Assets

Document version: 2026.07.03
Last updated: 2026-07-03
Status: Canonical
Audience: Developers

This document was rewritten on 2026-07-03 — the previous version described a `PromptRegistry` class, a `PromptNotFoundError` exception, a `{AGENT_KEY}_{ROLE}_{VERSION}.txt` naming convention, and a subdirectory taxonomy (`system/`, `mission/`, etc.) — none of which exist. It also omitted the real SHA-256 integrity-manifest feature, which does exist.

## Real Design

`services/orchestrator/orchestrator/prompt_registry.py` is a lightweight in-memory registry, not a class:

```python
@dataclass(frozen=True)
class PromptAsset:
    prompt_id: str
    version: str
    owner_agent_id: str
    template: str
    variables: tuple[str, ...]
    change_note: str
    created_at: str
    sha256: str = field(init=False)  # computed in __post_init__

    def render(self, **kwargs: Any) -> str: ...   # raises ValueError on missing variables
    def to_record(self) -> dict[str, Any]: ...

def register(asset: PromptAsset) -> None: ...
def get(prompt_id: str) -> PromptAsset: ...       # raises KeyError if not registered
def list_prompts() -> list[dict[str, Any]]: ...
def load_prompt_assets(directory: Path | None = None) -> int: ...
```

`load_prompt_assets()` runs once at orchestrator startup, reading every `*.json` file (except `manifest.json`) from `prompt_assets/` and registering it. There is no `PromptNotFoundError` — `get()` raises a plain `KeyError`.

## Asset Files

Prompt assets are flat JSON files under `services/orchestrator/orchestrator/prompt_assets/`, named `{prompt_id}.v{N}.json` (e.g. `ceo_delegation.v1.json`, `pm_feature_contract.v1.json`, `pod_audit_verdict.v1.json`) — no subdirectory taxonomy, no `.txt` extension. Each file's JSON shape maps directly to `PromptAsset`'s fields: `prompt_id`, `version`, `owner_agent_id`, `template`, `variables`, `change_note`, `created_at`.

## Integrity Manifest (SHA-256 Fingerprinting)

An optional `prompt_assets/manifest.json` maps `{prompt_id: expected_sha256}`. When present:
- Each loaded asset's computed SHA-256 (over its template text) is compared against the manifest entry.
- A mismatch is **fail-closed** — the asset is rejected (not registered) and a `SECURITY:` error is logged, not silently accepted.
- `PROMPT_INTEGRITY_ENFORCED=true` additionally requires every asset to *have* a manifest entry — an asset with no manifest record is rejected too under strict mode.
- With no manifest file present at all, loading behaves exactly as it did before the manifest feature existed (no integrity checks, full backward compatibility).

This is the real audit-traceability mechanism this document previously omitted: every LLM call that renders a registered prompt can attach `PromptAsset.sha256`/`version`/`prompt_id` to the chain trace, giving a tamper-evident record of exactly which prompt template produced a given LLM call.

## Adding a New Prompt

1. Create `prompt_assets/{prompt_id}.v1.json` with `prompt_id`, `template`, `variables`, `owner_agent_id`, `change_note`, `created_at`.
2. If an integrity manifest is in use, add the new asset's SHA-256 to `prompt_assets/manifest.json` (compute it the same way `PromptAsset.__post_init__` does: SHA-256 of the raw template string).
3. Reference the asset by `prompt_id` via `prompt_registry.get(prompt_id).render(**variables)` from the generator that needs it.
