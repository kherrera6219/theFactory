from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True)
class PromotionDecision:
    allowed: bool
    reasons: list[str]
    policy_version: int
    ref: str
    ci_status: str
    attestation_verified: bool
    signed_tag_verified: bool
    model_inventory_checked: bool
    qualification_summary_checked: bool
    evaluated_at: str

    def to_json(self) -> str:
        return json.dumps(
            {
                "allowed": self.allowed,
                "reasons": self.reasons,
                "policy_version": self.policy_version,
                "ref": self.ref,
                "ci_status": self.ci_status,
                "attestation_verified": self.attestation_verified,
                "signed_tag_verified": self.signed_tag_verified,
                "model_inventory_checked": self.model_inventory_checked,
                "qualification_summary_checked": self.qualification_summary_checked,
                "evaluated_at": self.evaluated_at,
            },
            indent=2,
        )


def _as_bool(raw: str) -> bool:
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _is_release_tag_ref(ref: str) -> bool:
    return bool(re.match(r"^refs/tags/v\d+\.\d+\.\d+(?:[-+].*)?$", ref.strip()))


def load_policy(path: Path) -> dict:
    if not path.exists():
        raise RuntimeError(f"promotion policy not found: {path}")
    policy = json.loads(path.read_text(encoding="utf-8"))
    for required in ("version", "fail_closed", "allowed_ref_patterns", "requirements"):
        if required not in policy:
            raise RuntimeError(f"promotion policy missing key: {required}")
    return policy


def _load_json(path: Path | None) -> dict[str, object] | None:
    if path is None:
        return None
    if not path.exists():
        raise RuntimeError(f"required JSON file not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"expected JSON object in {path}")
    return payload


def _evaluate_model_governance(
    policy: dict,
    model_inventory: dict[str, object] | None,
) -> list[str]:
    requirements = policy.get("requirements") or {}
    governance = requirements.get("model_governance") or {}
    if not isinstance(governance, dict) or not governance:
        return []

    reasons: list[str] = []
    require_inventory = bool(governance.get("require_inventory", False))
    if require_inventory and model_inventory is None:
        return ["model inventory is required but was not provided"]
    if model_inventory is None:
        return []

    blocked_stages = {
        str(stage).strip().lower()
        for stage in governance.get("blocked_lifecycle_stages", [])
        if str(stage).strip()
    }
    allowlist = {
        str(model).strip().lower()
        for model in governance.get("allowlist_models", [])
        if str(model).strip()
    }
    agents = model_inventory.get("agents")
    if not isinstance(agents, list):
        return ["model inventory missing agents list"]

    for agent in agents:
        if not isinstance(agent, dict):
            continue
        agent_id = str(agent.get("agent_id", "")).strip() or "unknown-agent"
        model = str(agent.get("model", "")).strip()
        lifecycle = str(agent.get("lifecycle", "")).strip().lower()
        if model and model.lower() not in allowlist:
            approved = bool(agent.get("production_approved", False))
            if lifecycle in blocked_stages or not approved:
                reasons.append(f"{agent_id} primary route {model} is not production approved")

        fallback_model = str(agent.get("fallback_model", "")).strip()
        fallback_lifecycle = str(agent.get("fallback_lifecycle", "")).strip().lower()
        fallback_approved = bool(agent.get("fallback_production_approved", True))
        if fallback_model and fallback_model.lower() not in allowlist:
            if fallback_lifecycle in blocked_stages or not fallback_approved:
                reasons.append(
                    f"{agent_id} fallback route {fallback_model} is not production approved"
                )

    return reasons


def _evaluate_qualification_summary(
    policy: dict,
    qualification_summary: dict[str, object] | None,
) -> list[str]:
    requirements = policy.get("requirements") or {}
    gates = requirements.get("qualification_gates") or {}
    if not isinstance(gates, dict) or not gates:
        return []

    require_summary = bool(gates.get("required", False))
    if require_summary and qualification_summary is None:
        return ["qualification summary is required but was not provided"]
    if qualification_summary is None:
        return []

    reasons: list[str] = []
    if not bool(qualification_summary.get("passed", False)):
        for reason in qualification_summary.get("failure_reasons", []):
            reasons.append(f"qualification summary: {reason}")
        if not reasons:
            reasons.append("qualification summary reports failure")

    suites = qualification_summary.get("suites")
    if not isinstance(suites, dict):
        return reasons + ["qualification summary missing suites object"]

    for suite_name, suite_policy in (gates.get("suites") or {}).items():
        if not isinstance(suite_policy, dict) or not bool(suite_policy.get("required", False)):
            continue
        suite_report = suites.get(suite_name)
        if not isinstance(suite_report, dict):
            reasons.append(f"missing required qualification suite: {suite_name}")
            continue
        if not bool(suite_report.get("passed", False)):
            reasons.append(f"required qualification suite failed: {suite_name}")

    return reasons


def evaluate_promotion(
    *,
    policy: dict,
    ref: str,
    ci_status: str,
    attestation_verified: bool,
    signed_tag_verified: bool = False,
    model_inventory: dict[str, object] | None = None,
    qualification_summary: dict[str, object] | None = None,
) -> PromotionDecision:
    reasons: list[str] = []
    patterns = policy.get("allowed_ref_patterns") or []
    if not any(re.match(pattern, ref) for pattern in patterns):
        reasons.append(f"ref '{ref}' does not match allowed promotion patterns")

    requirements = policy.get("requirements") or {}
    required_ci_status = str(requirements.get("ci_status", "")).strip().lower()
    if required_ci_status and ci_status.strip().lower() != required_ci_status:
        reasons.append(
            f"ci_status '{ci_status}' does not satisfy required status '{required_ci_status}'"
        )

    required_attestation = bool(requirements.get("attestation_verified", False))
    if required_attestation and not attestation_verified:
        reasons.append("attestation verification is required but not satisfied")
    require_signed_tag = bool(requirements.get("signed_tag_verified", False))
    if require_signed_tag and _is_release_tag_ref(ref) and not signed_tag_verified:
        reasons.append("signed release tag verification is required but not satisfied")

    reasons.extend(_evaluate_model_governance(policy, model_inventory))
    reasons.extend(_evaluate_qualification_summary(policy, qualification_summary))

    fail_closed = bool(policy.get("fail_closed", True))
    allowed = not reasons if fail_closed else True

    return PromotionDecision(
        allowed=allowed,
        reasons=reasons,
        policy_version=int(policy.get("version", 0)),
        ref=ref,
        ci_status=ci_status,
        attestation_verified=attestation_verified,
        signed_tag_verified=signed_tag_verified,
        model_inventory_checked=model_inventory is not None,
        qualification_summary_checked=qualification_summary is not None,
        evaluated_at=datetime.now(UTC).isoformat(),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate promotion gate policy.")
    parser.add_argument(
        "--policy-file",
        default="deploy/promotion-policy.json",
        help="Path to promotion policy JSON.",
    )
    parser.add_argument("--ref", required=True, help="Git ref under evaluation.")
    parser.add_argument("--ci-status", required=True, help="CI status value.")
    parser.add_argument(
        "--attestation-verified",
        required=True,
        help="Whether attestation verification succeeded (true/false).",
    )
    parser.add_argument(
        "--signed-tag-verified",
        default="false",
        help="Whether signed release-tag verification succeeded (true/false).",
    )
    parser.add_argument(
        "--output-file",
        required=True,
        help="Path for promotion decision JSON output.",
    )
    parser.add_argument(
        "--model-inventory-file",
        default="",
        help="Optional machine-readable agent model inventory JSON.",
    )
    parser.add_argument(
        "--qualification-summary-file",
        default="",
        help="Optional qualification summary JSON consumed by promotion policy.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    policy = load_policy(Path(args.policy_file))
    decision = evaluate_promotion(
        policy=policy,
        ref=args.ref,
        ci_status=args.ci_status,
        attestation_verified=_as_bool(args.attestation_verified),
        signed_tag_verified=_as_bool(args.signed_tag_verified),
        model_inventory=(
            _load_json(Path(args.model_inventory_file))
            if str(args.model_inventory_file).strip()
            else None
        ),
        qualification_summary=(
            _load_json(Path(args.qualification_summary_file))
            if str(args.qualification_summary_file).strip()
            else None
        ),
    )
    output_path = Path(args.output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(decision.to_json() + "\n", encoding="utf-8")
    if decision.allowed:
        print("PASS: promotion gate policy satisfied")
        return 0
    print("FAIL: promotion gate policy rejected promotion")
    for reason in decision.reasons:
        print(f"- {reason}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
