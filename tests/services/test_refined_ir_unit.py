import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "pod-worker"))

from pod_worker.refined_ir import (  # noqa: E402
    RefinedIRModule,
    build_refined_ir_module,
    write_refined_ir_module,
)


def _logicnode() -> dict[str, object]:
    return {
        "node_id": "podA.core.mission-1",
        "concept": "map_collection",
        "domain": "list_operations",
        "node": {
            "node_name": "list_operations.map_collection",
            "source_language": "python",
            "target_language": "python",
            "payload": {
                "concept": "map_collection",
                "domain": "list_operations",
                "intent": "transform",
                "confidence": 0.91,
            },
        },
    }


def test_build_refined_ir_module_validates_schema_shape() -> None:
    module = build_refined_ir_module(
        mission_id="mission-1",
        agent_id="AGENT-14-PYTHON",
        source_language="python",
        target_language="python",
        logicnodes=[_logicnode()],
        source_ref="mission://mission-1",
    )
    assert isinstance(module, RefinedIRModule)
    assert module.module["mission_id"] == "mission-1"
    assert len(module.fns) == 1
    assert module.fns[0].tests.equivalence_vectors[0].out["concept"] == "map_collection"


def test_write_refined_ir_module_persists_catalog_file(tmp_path: Path) -> None:
    module = build_refined_ir_module(
        mission_id="mission-1",
        agent_id="AGENT-14-PYTHON",
        source_language="python",
        target_language="python",
        logicnodes=[_logicnode()],
        source_ref="mission://mission-1",
    )
    record = write_refined_ir_module(
        module,
        store_root=tmp_path,
        mission_id="mission-1",
        agent_id="AGENT-14-PYTHON",
    )
    payload = json.loads(record.path.read_text(encoding="utf-8"))
    assert record.relative_path == "missions/mission-1/agent-14-python.rir.module.json"
    assert payload["module"]["agent_id"] == "AGENT-14-PYTHON"
