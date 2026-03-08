import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "promotion_gate.py"

spec = importlib.util.spec_from_file_location("promotion_gate", MODULE_PATH)
assert spec is not None and spec.loader is not None
promotion_gate = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = promotion_gate
spec.loader.exec_module(promotion_gate)


def _policy() -> dict:
    return {
        "version": 2,
        "fail_closed": True,
        "allowed_ref_patterns": [
            r"^refs/heads/main$",
            r"^refs/tags/v\d+\.\d+\.\d+(?:[-+].*)?$",
        ],
        "requirements": {
            "ci_status": "success",
            "attestation_verified": True,
            "model_governance": {
                "require_inventory": True,
                "blocked_lifecycle_stages": ["preview", "experimental", "rolling"],
                "allowlist_models": [],
            },
            "qualification_gates": {
                "required": True,
                "suites": {
                    "operator_route_oidc_matrix": {"required": True},
                    "dedicated_agent_canary_trend": {"required": True},
                },
            },
        },
    }


def test_evaluate_promotion_allows_main_with_valid_inputs() -> None:
    decision = promotion_gate.evaluate_promotion(
        policy=_policy(),
        ref="refs/heads/main",
        ci_status="success",
        attestation_verified=True,
        model_inventory={
            "agents": [
                {
                    "agent_id": "AGENT-01-PM",
                    "model": "claude-sonnet-4-6",
                    "lifecycle": "stable",
                    "production_approved": True,
                    "fallback_model": "",
                    "fallback_lifecycle": "none",
                    "fallback_production_approved": True,
                }
            ]
        },
        qualification_summary={
            "passed": True,
            "failure_reasons": [],
            "suites": {
                "operator_route_oidc_matrix": {"passed": True},
                "dedicated_agent_canary_trend": {"passed": True},
            },
        },
    )
    assert decision.allowed is True
    assert decision.reasons == []


def test_evaluate_promotion_blocks_invalid_ref() -> None:
    decision = promotion_gate.evaluate_promotion(
        policy=_policy(),
        ref="refs/heads/feature/nope",
        ci_status="success",
        attestation_verified=True,
        model_inventory={"agents": []},
        qualification_summary={
            "passed": True,
            "failure_reasons": [],
            "suites": {
                "operator_route_oidc_matrix": {"passed": True},
                "dedicated_agent_canary_trend": {"passed": True},
            },
        },
    )
    assert decision.allowed is False
    assert any("does not match allowed promotion patterns" in reason for reason in decision.reasons)


def test_evaluate_promotion_blocks_missing_attestation() -> None:
    decision = promotion_gate.evaluate_promotion(
        policy=_policy(),
        ref="refs/tags/v1.2.3",
        ci_status="success",
        attestation_verified=False,
        model_inventory={"agents": []},
        qualification_summary={
            "passed": True,
            "failure_reasons": [],
            "suites": {
                "operator_route_oidc_matrix": {"passed": True},
                "dedicated_agent_canary_trend": {"passed": True},
            },
        },
    )
    assert decision.allowed is False
    assert any("attestation verification is required" in reason for reason in decision.reasons)


def test_evaluate_promotion_blocks_preview_models() -> None:
    decision = promotion_gate.evaluate_promotion(
        policy=_policy(),
        ref="refs/heads/main",
        ci_status="success",
        attestation_verified=True,
        model_inventory={
            "agents": [
                {
                    "agent_id": "AGENT-30-PODD-MGR",
                    "model": "gemini-3.1-pro-preview",
                    "lifecycle": "preview",
                    "production_approved": False,
                    "fallback_model": "gpt-5.2-pro",
                    "fallback_lifecycle": "stable",
                    "fallback_production_approved": True,
                }
            ]
        },
        qualification_summary={
            "passed": True,
            "failure_reasons": [],
            "suites": {
                "operator_route_oidc_matrix": {"passed": True},
                "dedicated_agent_canary_trend": {"passed": True},
            },
        },
    )
    assert decision.allowed is False
    assert any("not production approved" in reason for reason in decision.reasons)


def test_evaluate_promotion_blocks_failed_qualification_suite() -> None:
    decision = promotion_gate.evaluate_promotion(
        policy=_policy(),
        ref="refs/heads/main",
        ci_status="success",
        attestation_verified=True,
        model_inventory={"agents": []},
        qualification_summary={
            "passed": False,
            "failure_reasons": ["operator_route_oidc_matrix: latest qualification failed"],
            "suites": {
                "operator_route_oidc_matrix": {"passed": False},
                "dedicated_agent_canary_trend": {"passed": True},
            },
        },
    )
    assert decision.allowed is False
    assert any("qualification summary" in reason for reason in decision.reasons)


def test_load_policy_validates_required_keys(tmp_path: Path) -> None:
    policy_file = tmp_path / "policy.json"
    policy_file.write_text(json.dumps({"version": 1}), encoding="utf-8")
    try:
        promotion_gate.load_policy(policy_file)
        raise AssertionError("expected RuntimeError for missing keys")
    except RuntimeError as exc:
        assert "missing key" in str(exc)


def test_main_writes_decision_file(tmp_path: Path, monkeypatch) -> None:
    policy_file = tmp_path / "promotion-policy.json"
    policy_file.write_text(json.dumps(_policy()), encoding="utf-8")
    model_inventory = tmp_path / "model-inventory.json"
    model_inventory.write_text(
        json.dumps(
            {
                "agents": [
                    {
                        "agent_id": "AGENT-01-PM",
                        "model": "claude-sonnet-4-6",
                        "lifecycle": "stable",
                        "production_approved": True,
                        "fallback_model": "",
                        "fallback_lifecycle": "none",
                        "fallback_production_approved": True,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    qualification_summary = tmp_path / "qualification-summary.json"
    qualification_summary.write_text(
        json.dumps(
            {
                "passed": True,
                "failure_reasons": [],
                "suites": {
                    "operator_route_oidc_matrix": {"passed": True},
                    "dedicated_agent_canary_trend": {"passed": True},
                },
            }
        ),
        encoding="utf-8",
    )
    output_file = tmp_path / "decision.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "promotion_gate.py",
            "--policy-file",
            str(policy_file),
            "--ref",
            "refs/heads/main",
            "--ci-status",
            "success",
            "--attestation-verified",
            "true",
            "--model-inventory-file",
            str(model_inventory),
            "--qualification-summary-file",
            str(qualification_summary),
            "--output-file",
            str(output_file),
        ],
    )
    exit_code = promotion_gate.main()
    assert exit_code == 0
    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["allowed"] is True
    assert payload["ref"] == "refs/heads/main"
