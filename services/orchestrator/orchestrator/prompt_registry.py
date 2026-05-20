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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)
PROMPT_ASSETS_DIR = Path(__file__).resolve().parent / "prompt_assets"

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


def load_prompt_assets(directory: Path | None = None) -> int:
    """Load all .json prompt asset files from directory into the registry.

    Returns the number of assets successfully loaded.
    Called once at orchestrator startup.
    """
    target = directory or PROMPT_ASSETS_DIR
    if not target.is_dir():
        LOGGER.warning("Prompt assets directory not found: %s", target)
        return 0

    loaded = 0
    for path in sorted(target.glob("*.json")):
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
            register(asset)
            loaded += 1
            LOGGER.info(
                "Loaded prompt asset %s v%s (sha256: %s…)",
                asset.prompt_id, asset.version, asset.sha256[:12],
            )
        except (KeyError, TypeError, ValueError) as exc:
            LOGGER.warning("Failed to load prompt asset %s: %s", path.name, exc)

    LOGGER.info("Prompt registry: %d assets loaded from %s", loaded, target)
    return loaded
