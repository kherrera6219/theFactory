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


# ---------------------------------------------------------------------------
# UPG-30 / UPG-31 — LogicNode schema v2.
#
# The enrichment is additive in both directions: descriptive fields are
# *promoted* to first-class optional properties while `payload` keeps carrying
# every value it carried before, and `types.in`/`types.out` are populated only
# where an AST extractor genuinely recovered a signature.
# ---------------------------------------------------------------------------


def test_node_omitting_every_new_optional_field_still_validates() -> None:
    """Backward compatibility, criterion 1: the pre-UPG-30 shape stays valid.

    Nothing already persisted in ``mission_logicnodes`` may become invalid.
    """
    node = _valid_node()
    for promoted in (
        "domain",
        "concept",
        "confidence",
        "source_language",
        "extraction_method",
        "paradigm",
        "purity",
        "complexity",
        "source_license",
        "tags",
    ):
        assert promoted not in node
    assert logicnode_schema.validate_logicnode(node, schema_path=SCHEMA_PATH) == []


def test_all_new_optional_fields_together_validate() -> None:
    node = _valid_node()
    node.update(
        {
            "domain": "parsing",
            "concept": "csv_reader",
            "confidence": 0.87,
            "source_language": "python",
            "extraction_method": "ast",
            "paradigm": "multi-paradigm",
            "purity": "IMPURE",
            "complexity": 4,
            "source_license": "Apache-2.0",
            "tags": ["io", "csv"],
        }
    )
    assert logicnode_schema.validate_logicnode(node, schema_path=SCHEMA_PATH) == []


def test_promoted_fields_are_constrained_not_free_text() -> None:
    """A promoted field with a bad value must be reported, not silently kept."""
    for field, bad_value in (
        ("confidence", 1.5),  # outside 0..1
        ("extraction_method", "guesswork"),  # not regex|ast
        ("purity", "MAYBE"),  # not PURE|IMPURE|UNKNOWN
        ("complexity", -1),  # negative
        ("tags", "io"),  # must be an array
    ):
        node = _valid_node()
        node[field] = bad_value
        errors = logicnode_schema.validate_logicnode(node, schema_path=SCHEMA_PATH)
        assert errors, f"{field}={bad_value!r} should not validate"


def test_build_schema_node_promotes_fields_without_emptying_payload() -> None:
    """Criterion 3: promoted fields are duplicates, not moves.

    Anything reading ``payload.domain`` today must keep working.
    """
    node = pod_worker_main._build_schema_node(
        node_id="podA.csv.m-4.abc12345.10",
        concept_id="csv",
        concept="csv_reader",
        domain="parsing",
        intent="Read CSV rows",
        extraction_language="python",
        target_language="rust",
        source_file="reader.py",
        snippet="def read(): ...",
        agent_id="AGENT-14-PYTHON",
        extra_payload={"confidence": 0.9, "extraction_method": "ast"},
    )
    assert logicnode_schema.validate_logicnode(node, schema_path=SCHEMA_PATH) == []

    # Promoted to top level ...
    assert node["domain"] == "parsing"
    assert node["concept"] == "csv_reader"
    assert node["source_language"] == "python"
    assert node["confidence"] == 0.9
    assert node["extraction_method"] == "ast"

    # ... and still present in payload, unchanged.
    assert node["payload"]["domain"] == "parsing"
    assert node["payload"]["concept"] == "csv_reader"
    assert node["payload"]["source_language"] == "python"
    assert node["payload"]["confidence"] == 0.9
    assert node["payload"]["extraction_method"] == "ast"


def test_unreserved_fields_are_not_populated_yet() -> None:
    """purity/complexity/paradigm/source_license/tags are schema-reserved only.

    They must stay absent until Phase 4 can derive them honestly — an absent
    field means "not analysed", and emitting a default would be a false claim.
    """
    node = pod_worker_main._build_schema_node(
        node_id="podA.csv.m-5.abc12345.10",
        concept_id="csv",
        concept="csv_reader",
        domain="parsing",
        intent="Read CSV rows",
        extraction_language="python",
        target_language="rust",
        source_file="reader.py",
        snippet="",
        agent_id="AGENT-14-PYTHON",
    )
    for reserved in ("paradigm", "purity", "complexity", "source_license", "tags"):
        assert reserved not in node


def test_confidence_is_clamped_into_schema_range() -> None:
    """An out-of-range extractor confidence must not produce an invalid node."""
    node = pod_worker_main._build_schema_node(
        node_id="podA.csv.m-6.abc12345.10",
        concept_id="csv",
        concept="csv_reader",
        domain="parsing",
        intent="",
        extraction_language="python",
        target_language="rust",
        source_file="reader.py",
        snippet="",
        agent_id="AGENT-14-PYTHON",
        extra_payload={"confidence": 4.2},
    )
    assert node["confidence"] == 1.0
    assert logicnode_schema.validate_logicnode(node, schema_path=SCHEMA_PATH) == []


def test_types_are_populated_from_an_enclosing_ast_signature() -> None:
    """Criterion 2: AST-backed languages carry non-empty types."""
    concept = SimpleNamespace(
        concept_id="csv",
        concept="csv_reader",
        domain="parsing",
        intent="Read CSV rows",
        source_line=12,
        evidence="total = a + b",
        extraction_method="ast",
        confidence=0.9,
    )
    function = SimpleNamespace(
        name="add", line=10, signature="def add(a: int, b: int) -> int",
        arg_types=("int", "int"), return_type="int",
    )
    nodes = pod_worker_main._logicnodes_from_extraction(
        mission_id="m-7",
        target_language="rust",
        extraction_language="python",
        concepts=[concept],
        source_file="reader.py",
        agent_id="AGENT-14-PYTHON",
        functions=[function],
    )
    node = nodes[0]["node"]
    assert logicnode_schema.validate_logicnode(node, schema_path=SCHEMA_PATH) == []
    assert node["types"] == {"in": ["int", "int"], "out": ["int"]}
    # Machine-readable provenance for the types, not just prose.
    assert node["payload"]["types_source"] == "ast_signature:add"


def test_types_stay_empty_when_the_extractor_recovered_no_signature() -> None:
    """Regex-only languages keep empty arrays — and that is now informative."""
    concept = SimpleNamespace(
        concept_id="csv", concept="csv_reader", domain="parsing",
        intent="", source_line=12, evidence="", extraction_method="regex",
    )
    function = SimpleNamespace(
        name="add", line=10, signature="function add(a, b)",
        arg_types=(), return_type=None,
    )
    nodes = pod_worker_main._logicnodes_from_extraction(
        mission_id="m-8", target_language="rust", extraction_language="javascript",
        concepts=[concept], source_file="reader.js", agent_id="AGENT-15-JS",
        functions=[function],
    )
    node = nodes[0]["node"]
    assert node["types"] == {"in": [], "out": []}
    assert "types_source" not in node["payload"]


def test_concept_above_the_first_function_gets_no_types() -> None:
    """The correlation must not guess: a module-level concept has no enclosing
    function, so it must not inherit the types of a function defined later."""
    concept = SimpleNamespace(
        concept_id="imp", concept="import", domain="module_patterns",
        intent="", source_line=1, evidence="", extraction_method="ast",
    )
    function = SimpleNamespace(
        name="add", line=10, signature="def add(a: int) -> int",
        arg_types=("int",), return_type="int",
    )
    nodes = pod_worker_main._logicnodes_from_extraction(
        mission_id="m-9", target_language="rust", extraction_language="python",
        concepts=[concept], source_file="reader.py", agent_id="AGENT-14-PYTHON",
        functions=[function],
    )
    assert nodes[0]["node"]["types"] == {"in": [], "out": []}


def test_correlation_picks_the_innermost_enclosing_function() -> None:
    functions = [
        SimpleNamespace(name="first", line=1, signature="", arg_types=("str",), return_type="str"),
        SimpleNamespace(name="second", line=20, signature="", arg_types=("int",), return_type="int"),
    ]
    assert pod_worker_main._enclosing_function_for_line(functions, 25).name == "second"
    assert pod_worker_main._enclosing_function_for_line(functions, 5).name == "first"
    assert pod_worker_main._enclosing_function_for_line(functions, 20).name == "second"
    assert pod_worker_main._enclosing_function_for_line(functions, 0) is None
    assert pod_worker_main._enclosing_function_for_line(functions, None) is None
    assert pod_worker_main._enclosing_function_for_line([], 25) is None


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
