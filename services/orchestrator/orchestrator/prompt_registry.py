"""prompt_registry.py — Versioned prompt asset management.

Provides a lightweight in-memory registry of versioned prompt assets.
Each asset is a frozen dataclass carrying the prompt template, required
variable names, version, owner agent, and content hash.

Assets are loaded from JSON files in prompt_assets/ at orchestrator startup.
Once loaded, every LLM call that uses a registered prompt attaches the asset
ID, version, and SHA-256 digest to the chain trace for full auditability.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)
PROMPT_ASSETS_DIR = Path(__file__).resolve().parent / "prompt_assets"
# Optional integrity manifest: { "<prompt_id>": "<expected_sha256>", ... }.
# When present, an asset whose computed SHA-256 does not match its manifest entry is
# rejected (fail-closed) rather than registered — tamper detection per Security §9.
PROMPT_MANIFEST_PATH = PROMPT_ASSETS_DIR / "manifest.json"

_REGISTRY: dict[str, "PromptAsset"] = {}


@dataclass(frozen=True)
class PromptAsset:
    prompt_id: str
    version: str
    owner_agent_id: str
    template: str
    variables: tuple[str, ...]
    change_note: str
    created_at: str
    sha256: str = field(init=False)

    def __post_init__(self) -> None:
        digest = hashlib.sha256(self.template.encode("utf-8")).hexdigest()
        object.__setattr__(self, "sha256", digest)

    def render(self, **kwargs: Any) -> str:
        missing = [v for v in self.variables if v not in kwargs]
        if missing:
            raise ValueError(
                f"Prompt {self.prompt_id!r} missing required variables: {missing}"
            )
        return self.template.format(**kwargs)

    def to_record(self) -> dict[str, Any]:
        return {
            "prompt_id": self.prompt_id,
            "version": self.version,
            "owner_agent_id": self.owner_agent_id,
            "sha256": self.sha256,
            "created_at": self.created_at,
            "change_note": self.change_note,
            "variable_count": len(self.variables),
        }


def register(asset: PromptAsset) -> None:
    """Register a prompt asset. Overwrites any previous asset with the same ID."""
    _REGISTRY[asset.prompt_id] = asset
    LOGGER.debug("Registered prompt asset %s v%s", asset.prompt_id, asset.version)


def get(prompt_id: str) -> PromptAsset:
    """Return a registered prompt asset by ID. Raises KeyError if not found."""
    if prompt_id not in _REGISTRY:
        raise KeyError(f"Prompt asset not registered: {prompt_id!r}")
    return _REGISTRY[prompt_id]


def list_prompts() -> list[dict[str, Any]]:
    """Return summary records for all registered prompt assets."""
    return [asset.to_record() for asset in _REGISTRY.values()]


def _load_integrity_manifest(directory: Path) -> dict[str, str]:
    """Load the optional {prompt_id: expected_sha256} integrity manifest.

    Returns an empty dict when no manifest exists (back-compat: load behaves as before
    until a manifest is generated). A malformed manifest is treated as empty + warned.
    """
    manifest_path = directory / "manifest.json"
    if not manifest_path.is_file():
        return {}
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            return {str(k): str(v) for k, v in raw.items()}
    except (ValueError, OSError) as exc:
        LOGGER.warning("Prompt integrity manifest unreadable (%s); skipping checks", exc)
    return {}


def load_prompt_assets(directory: Path | None = None) -> int:
    """Load all .json prompt asset files from directory into the registry.

    Returns the number of assets successfully loaded.
    Called once at orchestrator startup.

    Integrity: if ``manifest.json`` is present, each asset's computed SHA-256 must match
    its manifest entry. A mismatch is **fail-closed** — the asset is rejected (not
    registered) and a security warning is logged. ``PROMPT_INTEGRITY_ENFORCED=true``
    additionally requires every asset to *have* a manifest entry.
    """
    target = directory or PROMPT_ASSETS_DIR
    if not target.is_dir():
        LOGGER.warning("Prompt assets directory not found: %s", target)
        return 0

    manifest = _load_integrity_manifest(target)
    strict = os.getenv("PROMPT_INTEGRITY_ENFORCED", "false").strip().lower() in {
        "1", "true", "yes", "on",
    }

    loaded = 0
    for path in sorted(target.glob("*.json")):
        if path.name == "manifest.json":
            continue
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            asset = PromptAsset(
                prompt_id=str(raw["prompt_id"]),
                version=str(raw.get("version", "1.0.0")),
                owner_agent_id=str(raw.get("owner_agent_id", "")),
                template=str(raw["template"]),
                variables=tuple(raw.get("variables") or []),
                change_note=str(raw.get("change_note", "")),
                created_at=str(raw.get("created_at", "")),
            )
            expected = manifest.get(asset.prompt_id)
            if expected is not None and expected != asset.sha256:
                LOGGER.error(
                    "SECURITY: prompt asset %s failed integrity check "
                    "(expected sha256 %s…, got %s…); rejecting",
                    asset.prompt_id, expected[:12], asset.sha256[:12],
                )
                continue
            if expected is None and strict:
                LOGGER.error(
                    "SECURITY: prompt asset %s has no manifest entry and "
                    "PROMPT_INTEGRITY_ENFORCED is on; rejecting",
                    asset.prompt_id,
                )
                continue
            register(asset)
            loaded += 1
            LOGGER.info(
                "Loaded prompt asset %s v%s (sha256: %s…%s)",
                asset.prompt_id, asset.version, asset.sha256[:12],
                ", integrity-verified" if expected is not None else "",
            )
        except (KeyError, TypeError, ValueError) as exc:
            LOGGER.warning("Failed to load prompt asset %s: %s", path.name, exc)

    LOGGER.info("Prompt registry: %d assets loaded from %s", loaded, target)
    return loaded
