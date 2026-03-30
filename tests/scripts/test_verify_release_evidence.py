"""Regression tests for local release-trust evidence verification."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "verify_release_evidence.py"

spec = importlib.util.spec_from_file_location("verify_release_evidence", MODULE_PATH)
assert spec is not None and spec.loader is not None
verify_release_evidence = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = verify_release_evidence
spec.loader.exec_module(verify_release_evidence)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_verify_release_evidence_passes_with_expected_files(tmp_path: Path) -> None:
    manifest = tmp_path / "release-manifest.json"
    attestation = tmp_path / "attestation-verification.txt"
    decision = tmp_path / "promotion-decision.json"
    sbom = tmp_path / "sbom.spdx.json"

    _write_json(manifest, {"artifacts": [{"path": "coverage.xml"}]})
    attestation.write_text("Verified 1 attestation(s).\n", encoding="utf-8")
    _write_json(decision, {"allowed": True, "reasons": []})
    sbom.write_text('{"spdxVersion":"SPDX-2.3"}\n', encoding="utf-8")

    verify_release_evidence.verify_release_evidence(
        release_manifest_file=manifest,
        attestation_verification_file=attestation,
        promotion_decision_file=decision,
        sbom_file=sbom,
        require_allowed=True,
    )


def test_verify_release_evidence_rejects_missing_artifacts_list(tmp_path: Path) -> None:
    manifest = tmp_path / "release-manifest.json"
    attestation = tmp_path / "attestation-verification.txt"
    decision = tmp_path / "promotion-decision.json"
    _write_json(manifest, {"run_id": "1"})
    attestation.write_text("verified\n", encoding="utf-8")
    _write_json(decision, {"allowed": True})

    with pytest.raises(RuntimeError, match="artifacts list"):
        verify_release_evidence.verify_release_evidence(
            release_manifest_file=manifest,
            attestation_verification_file=attestation,
            promotion_decision_file=decision,
        )


def test_verify_release_evidence_rejects_disallowed_promotion_when_required(
    tmp_path: Path,
) -> None:
    manifest = tmp_path / "release-manifest.json"
    attestation = tmp_path / "attestation-verification.txt"
    decision = tmp_path / "promotion-decision.json"
    _write_json(manifest, {"artifacts": []})
    attestation.write_text("verified\n", encoding="utf-8")
    _write_json(decision, {"allowed": False, "reasons": ["blocked"]})

    with pytest.raises(RuntimeError, match="not allowed"):
        verify_release_evidence.verify_release_evidence(
            release_manifest_file=manifest,
            attestation_verification_file=attestation,
            promotion_decision_file=decision,
            require_allowed=True,
        )
