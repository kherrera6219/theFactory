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
                "evaluated_at": self.evaluated_at,
            },
            indent=2,
        )


def _as_bool(raw: str) -> bool:
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def load_policy(path: Path) -> dict:
    if not path.exists():
        raise RuntimeError(f"promotion policy not found: {path}")
    policy = json.loads(path.read_text(encoding="utf-8"))
    for required in ("version", "fail_closed", "allowed_ref_patterns", "requirements"):
        if required not in policy:
            raise RuntimeError(f"promotion policy missing key: {required}")
    return policy


def evaluate_promotion(
    *,
    policy: dict,
    ref: str,
    ci_status: str,
    attestation_verified: bool,
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

    fail_closed = bool(policy.get("fail_closed", True))
    allowed = not reasons if fail_closed else True

    return PromotionDecision(
        allowed=allowed,
        reasons=reasons,
        policy_version=int(policy.get("version", 0)),
        ref=ref,
        ci_status=ci_status,
        attestation_verified=attestation_verified,
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
        "--output-file",
        required=True,
        help="Path for promotion decision JSON output.",
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
