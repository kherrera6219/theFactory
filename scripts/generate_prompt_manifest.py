"""Generate the prompt-asset integrity manifest (Local-First Security §9).

Computes SHA-256 of each prompt asset's ``template`` field (matching
PromptAsset.__post_init__) and writes ``prompt_assets/manifest.json`` mapping
``prompt_id`` → expected digest. Re-run after any *intentional* prompt edit.

Usage:  python scripts/generate_prompt_manifest.py
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ASSETS_DIR = (
    Path(__file__).resolve().parent.parent
    / "services" / "orchestrator" / "orchestrator" / "prompt_assets"
)
MANIFEST_PATH = ASSETS_DIR / "manifest.json"


def main() -> int:
    manifest: dict[str, str] = {}
    for path in sorted(ASSETS_DIR.glob("*.json")):
        if path.name == "manifest.json":
            continue
        raw = json.loads(path.read_text(encoding="utf-8"))
        prompt_id = str(raw["prompt_id"])
        template = str(raw["template"])
        manifest[prompt_id] = hashlib.sha256(template.encode("utf-8")).hexdigest()

    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {MANIFEST_PATH} with {len(manifest)} entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
