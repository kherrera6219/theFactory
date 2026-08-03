"""Phase 4 (UPG-40..43) — real Refined-IR projection.

Before this phase `build_refined_ir_module` emitted a schema-valid artifact
carrying no semantic content: exactly one synthetic `EXTRACT_CONCEPT` op per
function, `purity` derived from whether an unrelated string was truthy, inputs
and outputs that restated the mission's languages rather than the function's
signature, and "equivalence vectors" that restated the node's own identifiers
and therefore could never fail.

These tests pin the four things that changed, and — just as importantly — that
the templated path still works unchanged for languages where no signature is
recoverable.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, RefResolver

ROOT = Path(__file__).resolve().parents[2]
# pod_worker.main imports orchestrator.agent_base, so both service roots are
# needed — matching tests/services/test_logicnode_schema.py.
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))
sys.path.insert(0, str(ROOT / "services" / "pod-worker"))

import pod_worker.main as pod_worker_main  # noqa: E402
from pod_worker.refined_ir import (  # noqa: E402
    build_refined_ir_module,
    catalog_record_for,
    update_refined_ir_catalog,
    write_refined_ir_module,
)

SCHEMA_DIR = ROOT / "schemas"

PY_SOURCE = '''
def classify(score: float, threshold: float) -> str:
    normalized = score / 100.0
    if normalized > threshold:
        label = "high"
    else:
        label = "low"
    return label


def persist(path: str, rows: list) -> bool:
    with open(path, "w") as handle:
        for row in rows:
            handle.write(str(row))
    return True
'''


@pytest.fixture(scope="module")
def rir_validator() -> Draft202012Validator:
    module_schema = json.loads((SCHEMA_DIR / "rir.module.schema.json").read_text("utf-8"))
    fn_schema = json.loads((SCHEMA_DIR / "rir.fn.schema.json").read_text("utf-8"))
    resolver = RefResolver(
        base_uri="", referrer=module_schema, store={"rir.fn.schema.json": fn_schema}
    )
    return Draft202012Validator(module_schema, resolver=resolver)


def _module_from(source: str, *, language: str = "python", monkeypatch=None):
    extractor = pod_worker_main._get_extractor(language)
    result = extractor.extract(source, focus_domains=None)
    logicnodes = pod_worker_main._logicnodes_from_extraction(
        mission_id="mission-phase4",
        target_language=language,
        extraction_language=language,
        concepts=result.concepts,
        source_file="demo.py",
        agent_id="AGENT-14-PYTHON",
        functions=result.functions,
    )
    return build_refined_ir_module(
        mission_id="mission-phase4",
        agent_id="AGENT-14-PYTHON",
        source_language=language,
        target_language=language,
        logicnodes=logicnodes,
        source_ref="demo.py",
    )


@pytest.fixture
def ast_module(monkeypatch):
    """A module projected from real Python AST data."""
    monkeypatch.setattr(pod_worker_main, "PYTHON_AST_EXTRACTOR_ENABLED", True)
    return _module_from(PY_SOURCE)


# --- UPG-40: the honesty field --------------------------------------------


def test_every_module_carries_a_projection_method(ast_module) -> None:
    """Criterion 1. A consumer reading the JSON must be able to tell a real
    projection from a templated one without reading documentation."""
    assert ast_module.projection_method in ("templated_v1", "ast_v1", "mixed_v1")
    for fn in ast_module.fns:
        assert fn.projection_method in ("templated_v1", "ast_v1")


def test_ast_backed_module_reports_ast_v1(ast_module) -> None:
    assert ast_module.projection_method == "ast_v1"
    assert ast_module.module["ast_projected_fn_count"] == len(ast_module.fns)


def test_regex_only_language_still_reports_templated_v1() -> None:
    """The templated path is retained, not removed — it is the honest answer
    for languages whose extractors recover no signature."""
    module = _module_from("SELECT 1;\n", language="sql")
    assert module.projection_method == "templated_v1"
    for fn in module.fns:
        assert fn.projection_method == "templated_v1"
        # The original templated shape is preserved exactly.
        assert [p.name for p in fn.inputs] == ["source"]
        assert [p.name for p in fn.outputs] == ["intent"]
        assert [op.opcode for op in fn.ops] == ["EXTRACT_CONCEPT"]


# --- UPG-41: real content --------------------------------------------------


def test_inputs_and_outputs_match_the_real_signature(ast_module) -> None:
    """Criterion 2 (second half). Previously inputs were always
    [{name: "source", type: <source_language>}] regardless of the function."""
    classify = next(f for f in ast_module.fns if "float" in [p.type for p in f.inputs])
    assert [p.type for p in classify.inputs] == ["float", "float"]
    assert [p.type for p in classify.outputs] == ["str"]
    assert [p.name for p in classify.inputs] == ["arg0", "arg1"]


def test_ops_are_a_real_statement_sequence(ast_module) -> None:
    """Criterion 2 (first half). Previously every function had exactly one op."""
    assert any(len(fn.ops) > 1 for fn in ast_module.fns)
    classify = next(f for f in ast_module.fns if len(f.ops) > 1)
    opcodes = [op.opcode for op in classify.ops]
    assert "EXTRACT_CONCEPT" not in opcodes
    assert "RETURN" in opcodes
    assert "BRANCH" in opcodes


def test_purity_differs_between_a_pure_and_an_impure_function(ast_module) -> None:
    """Criterion 3. Previously purity was
    `"IMPURE" if payload.get("intent") else "PURE"` — decided by whether an
    unrelated string happened to be truthy."""
    purities = {fn.purity for fn in ast_module.fns}
    assert "PURE" in purities
    assert "IMPURE" in purities


def test_impure_function_reports_the_specific_effect(ast_module) -> None:
    impure = next(f for f in ast_module.fns if f.purity == "IMPURE")
    assert "io.filesystem" in impure.effects
    assert "logicnode_recorded" not in impure.effects


def test_unknown_purity_is_representable() -> None:
    """A function calling something unresolvable must be able to say
    "not determined" rather than being forced to claim PURE."""
    from pod_worker.ast_extractor import extract_python_ast

    result = extract_python_ast("def f(x):\n    return helper(x)\n")
    assert result.functions[0].purity == "UNKNOWN"
    assert result.functions[0].side_effects == ()


# --- UPG-42: real equivalence vectors --------------------------------------


def test_vectors_contain_real_argument_values_not_identifier_restatements(
    ast_module,
) -> None:
    """Criterion 4. The old vector was
    {"in": {"node_id":…, "source_language":…}, "out": {"concept":…, "domain":…}}
    — comparing a node to itself, which can never fail."""
    classify = next(f for f in ast_module.fns if len(f.inputs) == 2)
    vectors = classify.tests.equivalence_vectors
    assert len(vectors) > 1
    for vector in vectors:
        payload = vector.model_dump(by_alias=True)
        assert "node_id" not in payload["in"]
        assert "args" in payload["in"]
        assert set(payload["in"]["args"]) == {"arg0", "arg1"}
        assert payload["out"]["executable"] is True


def test_vectors_do_not_invent_an_expected_output(ast_module) -> None:
    """`expected` stays null until Phase 5 executes the artifact. Inventing one
    would recreate the "cannot fail" problem in a new form."""
    classify = next(f for f in ast_module.fns if len(f.inputs) == 2)
    for vector in classify.tests.equivalence_vectors:
        assert vector.model_dump(by_alias=True)["out"]["expected"] is None


def test_non_executable_vectors_are_flagged_for_phase_5() -> None:
    module = _module_from("SELECT 1;\n", language="sql")
    for fn in module.fns:
        for vector in fn.tests.equivalence_vectors:
            assert vector.model_dump(by_alias=True)["out"]["executable"] is False


def test_unsupported_parameter_type_drops_the_vector_rather_than_guessing() -> None:
    """A type with no known sample must not get an invented value — the vector
    would then fail for reasons unrelated to the code under test."""
    from pod_worker.refined_ir import _NO_SAMPLE, _sample_value_for_type

    assert _sample_value_for_type("CustomDomainObject", "nominal") is _NO_SAMPLE
    assert _sample_value_for_type("", "nominal") is _NO_SAMPLE
    assert _sample_value_for_type("int", "nominal") == 2
    assert _sample_value_for_type("List[int]", "nominal") == [1, 2, 3]
    assert _sample_value_for_type("[Int]", "nominal") == [1, 2, 3]
    assert _sample_value_for_type("String[]", "nominal") == [1, 2, 3]


# --- Schema conformance and the golden lock --------------------------------


def test_ast_module_validates_against_both_rir_schemas(ast_module, rir_validator) -> None:
    """Criterion 5 (schema half)."""
    rir_validator.validate(ast_module.model_dump(by_alias=True))


def test_templated_module_still_validates(rir_validator) -> None:
    """Backward compatibility: the pre-Phase-4 shape is still valid."""
    rir_validator.validate(_module_from("SELECT 1;\n", language="sql").model_dump(by_alias=True))


def test_module_written_before_upg40_still_validates(rir_validator) -> None:
    """`projection_method` is optional, so an artifact already on disk from
    before this phase does not become invalid."""
    payload = _module_from("SELECT 1;\n", language="sql").model_dump(by_alias=True)
    payload.pop("projection_method")
    for fn in payload["fns"]:
        fn.pop("projection_method")
    rir_validator.validate(payload)


def test_golden_ast_v1_projection_shape_is_locked(ast_module) -> None:
    """Criterion 5 (golden half). Locks the *shape* of an ast_v1 projection —
    field presence and derivation, not brittle exact values."""
    fn = next(f for f in ast_module.fns if f.projection_method == "ast_v1" and f.inputs)
    assert fn.fn_id
    assert fn.purity in ("PURE", "IMPURE", "UNKNOWN")
    assert all(p.type for p in fn.inputs)
    assert all(op.op_id.startswith(fn.fn_id) for op in fn.ops)
    assert "ast_derived_signature" in fn.tests.properties
    assert fn.preconditions and all("is of type" in p for p in fn.preconditions)
    assert fn.provenance.sources and fn.provenance.chain_of_custody


# --- UPG-43: the catalog ---------------------------------------------------


def test_catalog_is_populated_when_a_module_is_written(ast_module, tmp_path) -> None:
    """Criterion 6. `artifacts/refined-ir/index.json` sat at `{"artifacts": []}`
    while signed modules accumulated, because nothing invoked the builder."""
    write_refined_ir_module(
        ast_module, store_root=tmp_path, mission_id="m-1", agent_id="AGENT-14-PYTHON"
    )
    index = json.loads((tmp_path / "index.json").read_text("utf-8"))
    assert len(index["artifacts"]) == 1
    assert index["artifacts"][0]["projection_method"] == "ast_v1"
    assert index["artifacts"][0]["mission_id"] == "mission-phase4"


def test_catalog_upserts_rather_than_duplicating(ast_module, tmp_path) -> None:
    for _ in range(3):
        write_refined_ir_module(
            ast_module, store_root=tmp_path, mission_id="m-1", agent_id="AGENT-14-PYTHON"
        )
    index = json.loads((tmp_path / "index.json").read_text("utf-8"))
    assert len(index["artifacts"]) == 1


def test_corrupt_catalog_is_rebuilt_rather_than_failing_the_mission(
    ast_module, tmp_path
) -> None:
    (tmp_path).mkdir(parents=True, exist_ok=True)
    (tmp_path / "index.json").write_text("{not json", encoding="utf-8")
    update_refined_ir_catalog(tmp_path, ast_module, relative_path="missions/m/x.json")
    index = json.loads((tmp_path / "index.json").read_text("utf-8"))
    assert len(index["artifacts"]) == 1


def test_catalog_record_shape_is_shared_with_the_rebuild_script(ast_module) -> None:
    """The write path and scripts/build_refined_ir_catalog.py must not drift."""
    record = catalog_record_for(ast_module, relative_path="missions/m/x.json")
    assert set(record) == {
        "path",
        "mission_id",
        "agent_id",
        "source_language",
        "target_language",
        "function_count",
        "projection_method",
        "ast_projected_fn_count",
    }
