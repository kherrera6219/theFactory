"""Unit tests for Phase 8: Polyglot Behavioral Equivalence, tree-sitter AST & Signed SBOM/Patch Export."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "shared_runtime"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))
sys.path.insert(0, str(ROOT / "services" / "pod-worker"))

from orchestrator import contract_oracle as co  # noqa: E402
from orchestrator import deploy_exporter as de  # noqa: E402
from orchestrator import equivalence_execution as ee  # noqa: E402
from pod_worker import treesitter_extractor as te  # noqa: E402
from pod_worker.language_extractor import get_extractor  # noqa: E402

from shared_runtime import crypto_signing  # noqa: E402


def test_js_ts_interface_for_oracle_extracts_signatures_without_bodies() -> None:
    ts_code = """
const SECRET_MULTIPLIER = 999;
export function computeDiscount(price: number, rate: number): number {
  return price * (1 - rate) + SECRET_MULTIPLIER - 999;
}
export const formatLabel = (name: string, count: number): string => {
  return `${name}:${count}`;
};
function _internalHelper(x: number): number {
  return x;
}
async function fetchRemote(url: string): Promise<string> {
  return url;
}
"""
    interface = co.interface_for_oracle(
        language="typescript",
        code=ts_code,
        generated_output={"filename": "discount.ts", "usage_example": "deno run discount.ts"},
        artifact_kind="library",
    )
    assert interface["supports_call_vectors"] is True
    fn_names = [fn["name"] for fn in interface["callable_functions"]]
    assert fn_names == ["computeDiscount", "formatLabel"]
    assert interface["callable_functions"][0]["params"] == [
        {"name": "price", "annotation": "number"},
        {"name": "rate", "annotation": "number"},
    ]
    assert interface["callable_functions"][0]["returns"] == "number"
    flattened = repr(interface)
    assert "SECRET_MULTIPLIER" not in flattened
    assert "_internalHelper" not in flattened
    assert "fetchRemote" not in flattened


def test_polyglot_js_ts_behavioural_and_contract_equivalence(monkeypatch) -> None:
    calls: list[dict] = []

    async def _fake_sandbox(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            stdout='__EQV__{"status": "ok", "result": 80}\n',
            stderr="",
            exit_code=0,
            timed_out=False,
            infrastructure_error=None,
        )

    async def _docker_ok(_bin="docker"):
        return True

    monkeypatch.setattr(ee, "run_in_sandbox", _fake_sandbox)
    monkeypatch.setattr(ee, "check_docker_available", _docker_ok)

    rir = {
        "fns": [
            {
                "fn_id": "fn-1",
                "name": "computeDiscount",
                "projection_method": "ast_v1",
                "tests": {
                    "equivalence_vectors": [
                        {
                            "in": {"case": "nominal", "args": {"price": 100, "rate": 0.2}},
                            "out": {"expected": 80, "executable": True},
                        }
                    ]
                },
            }
        ]
    }
    beh_report = asyncio.run(
        ee.run_behavioural_equivalence(
            mission_id="mission-ts-001",
            language="typescript",
            artifact_filename="discount.ts",
            artifact_code="export function computeDiscount(price: number, rate: number): number { return 80; }",
            rir_module=rir,
        )
    )
    assert beh_report["status"] == "passed"
    assert beh_report["equivalence_vectors_passed"] == 1
    assert "deno" in calls[-1]["command"]

    contract_report = asyncio.run(
        ee.run_contract_equivalence(
            mission_id="mission-js-001",
            language="javascript",
            artifact_filename="discount.mjs",
            artifact_code="export function computeDiscount(price, rate) { return 80; }",
            contract_vectors={
                "source": "llm",
                "criteria_total": 1,
                "vectors": [
                    {
                        "vector_id": "cv-1",
                        "kind": "call",
                        "criterion_index": 0,
                        "function": "computeDiscount",
                        "args": [100, 0.2],
                        "expected": 80,
                    }
                ],
            },
        )
    )
    assert contract_report["status"] == "passed"
    assert contract_report["equivalence_vectors_passed"] == 1
    assert calls[-1]["base_image"] == "node:20-slim"


def test_treesitter_extractor_strips_commented_declarations_and_recovers_types() -> None:
    rust_code = """
use std::collections::HashMap;

/*
pub fn commented_out_ghost(x: i32) -> i32 {
    return x;
}
*/
// pub fn line_commented_ghost(y: i32) -> i32 { y }

pub struct Ledger {
    pub balance: i64,
}

pub fn apply_delta(current: i64, delta: i64) -> i64 {
    if delta == 0 {
        return current;
    }
    return current + delta;
}
"""
    symbols = te.extract_treesitter_symbols(rust_code, "rust")
    assert symbols["success"] is True
    fn_names = [fn["name"] for fn in symbols["functions"]]
    assert fn_names == ["apply_delta"]
    assert "commented_out_ghost" not in fn_names
    assert "line_commented_ghost" not in fn_names
    assert symbols["functions"][0]["arg_types"] == ["i64", "i64"]
    assert symbols["functions"][0]["return_type"] == "i64"
    assert [cls["name"] for cls in symbols["classes"]] == ["Ledger"]

    # Also verify get_extractor("rust") honours comment-stripping
    extractor = get_extractor("rust")
    result = extractor.extract(rust_code)
    assert [f.name for f in result.functions] == ["apply_delta"]


def test_generate_unified_patch_bundle_and_signed_cyclonedx_sbom(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ARTIFACT_SIGNING_KEY_PATH", str(tmp_path / "keys" / "signing.key"))
    monkeypatch.setenv("ARTIFACT_SIGNING_KEY_SOURCE", "auto")
    source_bundle = "## FILE src/app.py\ndef greet():\n    return 'hi'\n"
    generated_bundle = {
        "filename": "src/app.py",
        "language": "python",
        "dependencies": ["fastapi==0.115.0", "pydantic==2.9.0"],
        "code": (
            "## FILE src/app.py\ndef greet(name: str = 'world'):\n    return f'hello {name}'\n"
            "## FILE tests/test_app.py\ndef test_greet():\n    assert True\n"
        ),
    }
    patch = de.generate_unified_patch_bundle("mission-patch-001", source_bundle, generated_bundle)
    assert "--- a/src/app.py" in patch
    assert "+++ b/src/app.py" in patch
    assert "+def greet(name: str = 'world'):" in patch
    assert "+++ b/tests/test_app.py" in patch

    sbom = de.generate_cyclonedx_sbom(
        mission_id="mission-sbom-001",
        generated_output=generated_bundle,
        sbom_delta={"remaining": ["uvicorn==0.30.0"]},
    )
    assert sbom["bomFormat"] == "CycloneDX"
    assert sbom["specVersion"] == "1.5"
    comp_names = {c["name"] for c in sbom["components"]}
    assert {"fastapi", "pydantic", "uvicorn"} <= comp_names
    props = {p["name"]: p["value"] for p in sbom["metadata"]["properties"]}
    assert props["thefactory:mission_id"] == "mission-sbom-001"
    assert props["thefactory:signed"] == "true"
    assert props["thefactory:signing_algorithm"] == "ECDSA-P256-SHA256"
    assert len(props["thefactory:signature"]) >= 32
    assert len(props["thefactory:artifact_sha256"]) == 64

    sig_record = sbom["metadata"]["signature_record"]
    sbom_core = {
        "bomFormat": sbom["bomFormat"],
        "specVersion": sbom["specVersion"],
        "serialNumber": sbom["serialNumber"],
        "version": sbom["version"],
        "components": sbom["components"],
    }
    assert crypto_signing.verify_payload(json.dumps(sbom_core, sort_keys=True), sig_record) is True
