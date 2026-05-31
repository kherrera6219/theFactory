"""Phase 2 Fix 1: LogicNode JSON-Schema enforcement at the write boundary.

Covers both halves of the fix:
  * the orchestrator-side validator (``validate_logicnode``) accepts a
    schema-valid node and reports — without raising — on an invalid one, and
  * the pod-worker node builders emit nodes that satisfy the canonical schema,
    so extraction output passes the orchestrator write boundary unchanged.
"""
import importlib
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))
sys.path.insert(0, str(ROOT / "services" / "pod-worker"))

logicnode_schema = importlib.import_module("orchestrator.logicnode_schema")
pod_worker_main = importlib.import_module("pod_worker.main")

SCHEMA_PATH = ROOT / "schemas" / "logicnode.schema.json"


def _valid_node() -> dict[str, Any]:
    return {
        "node_id": "podA.csv.mission-1.abc12345.10",
        "cmd": "csv",
        "payload": {"concept": "csv_reader", "domain": "parsing"},
        "priority": "NORMAL",
        "intent": "Read CSV rows",
        "types": {"in": [], "out": []},
        "provenance": {
            "source_ref": "main.py",
            "snippet_hash": "0" * 64,
            "miner_agent": "AGENT-14-PYTHON",
            "timestamp": "2026-05-31T00:00:00+00:00",
        },
    }


def test_validate_logicnode_accepts_valid_node() -> None:
    errors = logicnode_schema.validate_logicnode(_valid_node(), schema_path=SCHEMA_PATH)
    assert errors == []
    assert logicnode_schema.is_valid_logicnode(_valid_node(), schema_path=SCHEMA_PATH) is True


def test_validate_logicnode_reports_missing_required_fields_without_raising() -> None:
    node = _valid_node()
    del node["provenance"]
    del node["priority"]
    errors = logicnode_schema.validate_logicnode(node, schema_path=SCHEMA_PATH)
    # Validation never raises on a schema violation; it returns error strings.
    assert errors
    joined = " ".join(errors).lower()
    assert "provenance" in joined
    assert "priority" in joined
    assert logicnode_schema.is_valid_logicnode(node, schema_path=SCHEMA_PATH) is False


def test_validate_logicnode_rejects_bad_priority_enum() -> None:
    node = _valid_node()
    node["priority"] = "URGENT"  # not in LOW/NORMAL/HIGH/CRITICAL
    errors = logicnode_schema.validate_logicnode(node, schema_path=SCHEMA_PATH)
    assert any("priority" in e for e in errors)


def test_validate_logicnode_rejects_additional_top_level_property() -> None:
    node = _valid_node()
    node["unexpected"] = "value"
    errors = logicnode_schema.validate_logicnode(node, schema_path=SCHEMA_PATH)
    assert errors  # additionalProperties: false at the top level


def test_pod_worker_build_schema_node_is_schema_valid() -> None:
    node = pod_worker_main._build_schema_node(
        node_id="podA.csv.m-1.deadbeef.3",
        concept_id="csv",
        concept="csv_reader",
        domain="parsing",
        intent="Read CSV rows",
        extraction_language="python",
        target_language="rust",
        source_file="reader.py",
        snippet="def read(): ...",
        agent_id="AGENT-14-PYTHON",
    )
    assert logicnode_schema.validate_logicnode(node, schema_path=SCHEMA_PATH) == []
    # Descriptive fields live in the free-form payload (schema forbids extras).
    assert node["payload"]["concept"] == "csv_reader"
    assert node["payload"]["source_language"] == "python"
    assert len(node["provenance"]["snippet_hash"]) == 64


def test_pod_worker_routing_stub_is_schema_valid() -> None:
    wrapper = pod_worker_main._routing_stub_logicnode(
        mission_id="m-2",
        extraction_language="python",
        target_language="go",
        agent_id="AGENT-14-PYTHON",
    )
    assert logicnode_schema.validate_logicnode(wrapper["node"], schema_path=SCHEMA_PATH) == []


def test_pod_worker_logicnodes_from_extraction_emit_schema_valid_nodes() -> None:
    concept = SimpleNamespace(
        concept_id="csv",
        concept="csv_reader",
        domain="parsing",
        intent="Read CSV rows",
        source_line=12,
        evidence="def read(): ...",
    )
    nodes = pod_worker_main._logicnodes_from_extraction(
        mission_id="m-3",
        target_language="rust",
        extraction_language="python",
        concepts=[concept],
        source_file="reader.py",
        agent_id="AGENT-14-PYTHON",
    )
    assert nodes
    for wrapper in nodes:
        errors = logicnode_schema.validate_logicnode(wrapper["node"], schema_path=SCHEMA_PATH)
        assert errors == []


def test_coerce_schema_node_upgrades_legacy_node() -> None:
    legacy = {
        "concept": "legacy_concept",
        "domain": "legacy",
        "intent": "do thing",
        "node": {"node_name": "legacy.node", "payload": {"foo": "bar"}},
    }
    node = pod_worker_main._coerce_schema_node(
        legacy,
        node_id="podA.legacy.m-4.cafef00d.0",
        extraction_language="python",
        target_language="go",
        agent_id="AGENT-14-PYTHON",
    )
    assert logicnode_schema.validate_logicnode(node, schema_path=SCHEMA_PATH) == []
    # Legacy descriptive fields are folded into payload, not lost.
    assert node["payload"]["foo"] == "bar"
    assert node["payload"]["node_name"] == "legacy.node"


def test_coerce_schema_node_passes_through_already_valid_node() -> None:
    valid = _valid_node()
    wrapper = {"node": valid, "concept": "csv_reader", "domain": "parsing"}
    node = pod_worker_main._coerce_schema_node(
        wrapper,
        node_id="ignored",
        extraction_language="python",
        target_language="go",
        agent_id="AGENT-14-PYTHON",
    )
    # Already schema-valid → returned unchanged.
    assert node is valid
