from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

REQUIRED_FIELDS = [
    "run_timestamp_utc",
    "base_url",
    "readiness_endpoints",
    "readiness_failure_counts_by_endpoint",
    "mission_error_samples",
    "readiness_failure_samples",
    "recovery_probe",
    "failure_injection",
    "thresholds",
    "passed",
    "failure_reasons",
]


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _load_payload(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise RuntimeError(f"reliability evidence file not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("reliability evidence must be a JSON object")
    return payload


def verify_reliability_evidence(
    *,
    evidence_file: Path,
    require_passed: bool = True,
) -> dict[str, object]:
    payload = _load_payload(evidence_file)
    missing_fields = [field for field in REQUIRED_FIELDS if field not in payload]
    if missing_fields:
        raise RuntimeError(
            "reliability evidence missing required fields: " + ", ".join(missing_fields)
        )

    _require(isinstance(payload["run_timestamp_utc"], str), "run_timestamp_utc must be a string")
    _require(isinstance(payload["base_url"], str) and payload["base_url"], "base_url is required")
    _require(
        isinstance(payload["readiness_endpoints"], list)
        and all(isinstance(endpoint, str) and endpoint for endpoint in payload["readiness_endpoints"]),
        "readiness_endpoints must be a non-empty string list",
    )
    _require(
        isinstance(payload["readiness_failure_counts_by_endpoint"], dict),
        "readiness_failure_counts_by_endpoint must be an object",
    )
    _require(
        isinstance(payload["mission_error_samples"], list),
        "mission_error_samples must be a list",
    )
    _require(
        isinstance(payload["readiness_failure_samples"], list),
        "readiness_failure_samples must be a list",
    )
    _require(isinstance(payload["recovery_probe"], dict), "recovery_probe must be an object")
    _require(
        isinstance(payload["failure_injection"], dict),
        "failure_injection must be an object",
    )
    _require(isinstance(payload["thresholds"], dict), "thresholds must be an object")
    _require(isinstance(payload["passed"], bool), "passed must be a boolean")
    _require(isinstance(payload["failure_reasons"], list), "failure_reasons must be a list")
    if require_passed and not payload["passed"]:
        raise RuntimeError("reliability evidence did not pass qualification thresholds")

    return {
        "evidence_file": str(evidence_file),
        "run_timestamp_utc": payload["run_timestamp_utc"],
        "base_url": payload["base_url"],
        "readiness_endpoints": payload["readiness_endpoints"],
        "passed": payload["passed"],
        "verified": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify reliability qualification evidence contains current Phase 10 fields.",
    )
    parser.add_argument("--evidence-file", required=True, type=Path)
    parser.add_argument(
        "--allow-failed",
        action="store_true",
        help="Validate evidence shape even when qualification thresholds failed",
    )
    parser.add_argument("--output-file", type=Path)
    args = parser.parse_args()

    try:
        result = verify_reliability_evidence(
            evidence_file=args.evidence_file,
            require_passed=not args.allow_failed,
        )
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc

    if args.output_file is not None:
        args.output_file.parent.mkdir(parents=True, exist_ok=True)
        args.output_file.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
