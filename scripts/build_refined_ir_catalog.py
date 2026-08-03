from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "pod-worker"))

from pod_worker.refined_ir import RefinedIRModule, catalog_record_for  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate stored RefinedIR artifacts and build an index."
    )
    parser.add_argument(
        "--store-root",
        default="artifacts/refined-ir",
        help="Directory containing mission-scoped RefinedIR module JSON files.",
    )
    parser.add_argument(
        "--output-file",
        default="artifacts/refined-ir/index.json",
        help="Path for generated RefinedIR index JSON.",
    )
    return parser.parse_args()


def _resolve_cli_path(raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return ROOT / path


def main() -> int:
    args = parse_args()
    store_root = _resolve_cli_path(args.store_root)
    output_file = _resolve_cli_path(args.output_file)
    records: list[dict[str, object]] = []

    for artifact_path in sorted(store_root.rglob("*.rir.module.json")):
        payload = json.loads(artifact_path.read_text(encoding="utf-8"))
        module = RefinedIRModule.model_validate(payload)
        # Record shape is shared with the pod-worker write path
        # (refined_ir.update_refined_ir_catalog) so a full rebuild and an
        # incremental update produce identical entries (UPG-43).
        records.append(
            catalog_record_for(
                module,
                relative_path=artifact_path.relative_to(store_root).as_posix(),
            )
        )

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps({"artifacts": records}, indent=2) + "\n", encoding="utf-8")
    output_label = (
        output_file.relative_to(ROOT).as_posix()
        if output_file.is_relative_to(ROOT)
        else str(output_file)
    )
    print(f"indexed {len(records)} RefinedIR artifacts into {output_label}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
