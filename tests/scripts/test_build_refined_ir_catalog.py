from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "pod-worker"))

from pod_worker.refined_ir import build_refined_ir_module, write_refined_ir_module  # noqa: E402


def test_build_refined_ir_catalog_indexes_store(tmp_path: Path) -> None:
    store_root = tmp_path / "refined-ir"
    module = build_refined_ir_module(
        mission_id="mission-1",
        agent_id="AGENT-14-PYTHON",
        source_language="python",
        target_language="python",
        logicnodes=[
            {
                "node_id": "podA.core.mission-1",
                "concept": "map_collection",
                "domain": "list_operations",
                "node": {
                    "node_name": "list_operations.map_collection",
                    "payload": {"concept": "map_collection", "domain": "list_operations"},
                },
            }
        ],
        source_ref="mission://mission-1",
    )
    write_refined_ir_module(
        module,
        store_root=store_root,
        mission_id="mission-1",
        agent_id="AGENT-14-PYTHON",
    )

    output_file = tmp_path / "index.json"
    store_arg = (
        str(store_root.relative_to(ROOT)) if store_root.is_relative_to(ROOT) else str(store_root)
    )
    output_arg = (
        str(output_file.relative_to(ROOT))
        if output_file.is_relative_to(ROOT)
        else str(output_file)
    )
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "build_refined_ir_catalog.py"),
            "--store-root",
            store_arg,
            "--output-file",
            output_arg,
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert "indexed 1 RefinedIR artifacts" in completed.stdout
    assert payload["artifacts"][0]["agent_id"] == "AGENT-14-PYTHON"
