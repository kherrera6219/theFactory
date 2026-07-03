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


def test_build_refined_ir_module_falls_back_to_concept_when_node_name_missing() -> None:
    # Regression: node_name is opportunistic, not a required LogicNode field.
    # When node_payload is a dict but omits "node_name" entirely,
    # str(node_payload.get("node_name")) used to evaluate str(None) -- the
    # literal string "None" -- instead of falling back to `concept`.
    logicnode = _logicnode()
    del logicnode["node"]["node_name"]

    module = build_refined_ir_module(
        mission_id="mission-1",
        agent_id="AGENT-14-PYTHON",
        source_language="python",
        target_language="python",
        logicnodes=[logicnode],
        source_ref="mission://mission-1",
    )

    assert module.fns[0].name == "map_collection"
    assert module.fns[0].name != "None"


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


def test_write_refined_ir_module_signs_artifact(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv(
        "ARTIFACT_SIGNING_KEY_PATH", str(tmp_path / "keys" / "artifact.key")
    )
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
    from shared_runtime.crypto_signing import SIGNATURE_SUFFIX, verify_artifact

    sidecar = Path(str(record.path) + SIGNATURE_SUFFIX)
    assert sidecar.exists()
    assert verify_artifact(record.path) is True


def test_write_refined_ir_module_signing_failure_is_non_fatal(
    tmp_path: Path, monkeypatch
) -> None:
    # Force sign_artifact to blow up; the write must still succeed.
    import shared_runtime.crypto_signing as cs

    def _boom(*_a, **_k):
        raise RuntimeError("keystore unavailable")

    monkeypatch.setattr(cs, "sign_artifact", _boom)
    module = build_refined_ir_module(
        mission_id="mission-2",
        agent_id="AGENT-14-PYTHON",
        source_language="python",
        target_language="python",
        logicnodes=[_logicnode()],
        source_ref="mission://mission-2",
    )
    record = write_refined_ir_module(
        module,
        store_root=tmp_path,
        mission_id="mission-2",
        agent_id="AGENT-14-PYTHON",
    )
    assert record.path.exists()


def test_refined_ir_module_matches_canonical_json_schemas() -> None:
    from jsonschema import Draft202012Validator, RefResolver

    schema_dir = ROOT / 'schemas'
    fn_schema = json.loads(
        (schema_dir / 'rir.fn.schema.json').read_text(encoding='utf-8')
    )
    module_schema = json.loads(
        (schema_dir / 'rir.module.schema.json').read_text(encoding='utf-8')
    )
    module = build_refined_ir_module(
        mission_id='mission-1',
        agent_id='AGENT-14-PYTHON',
        source_language='python',
        target_language='python',
        logicnodes=[_logicnode()],
        source_ref='mission://mission-1',
    )
    payload = module.model_dump(by_alias=True)
    resolver = RefResolver.from_schema(
        module_schema, store={'rir.fn.schema.json': fn_schema}
    )
    module_errors = sorted(
        Draft202012Validator(
            module_schema, resolver=resolver
        ).iter_errors(payload),
        key=lambda error: list(error.path),
    )
    fn_errors = sorted(
        Draft202012Validator(fn_schema).iter_errors(payload['fns'][0]),
        key=lambda error: list(error.path),
    )
    assert module_errors == []
    assert fn_errors == []
