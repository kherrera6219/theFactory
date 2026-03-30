from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise RuntimeError(f"required file not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"expected JSON object in {path}")
    return payload


def _require_text(path: Path, *, contains: str | None = None) -> None:
    if not path.exists():
        raise RuntimeError(f"required file not found: {path}")
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise RuntimeError(f"required file is empty: {path}")
    if contains and contains not in text:
        raise RuntimeError(f"required text '{contains}' not found in {path}")


def verify_release_evidence(
    *,
    release_manifest_file: Path,
    attestation_verification_file: Path,
    promotion_decision_file: Path,
    sbom_file: Path | None = None,
    require_allowed: bool = False,
) -> None:
    manifest = _load_json(release_manifest_file)
    if not isinstance(manifest.get("artifacts"), list):
        raise RuntimeError("release manifest missing artifacts list")

    _require_text(attestation_verification_file)

    promotion = _load_json(promotion_decision_file)
    if "allowed" not in promotion:
        raise RuntimeError("promotion decision missing allowed field")
    if require_allowed and not bool(promotion.get("allowed", False)):
        raise RuntimeError("promotion decision is not allowed")

    if sbom_file is not None:
        _require_text(sbom_file)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate local release-trust evidence artifacts.")
    parser.add_argument(
        "--release-manifest-file",
        default="reports/release-manifest.json",
        help="Path to the generated release manifest JSON.",
    )
    parser.add_argument(
        "--attestation-verification-file",
        default="reports/attestation-verification.txt",
        help="Path to the gh attestation verification output.",
    )
    parser.add_argument(
        "--promotion-decision-file",
        default="reports/promotion-decision.json",
        help="Path to the promotion decision JSON.",
    )
    parser.add_argument(
        "--sbom-file",
        default="",
        help="Optional path to the SBOM file expected by the release bundle.",
    )
    parser.add_argument(
        "--require-allowed",
        action="store_true",
        help="Fail unless the promotion decision is allowed=true.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    verify_release_evidence(
        release_manifest_file=Path(args.release_manifest_file),
        attestation_verification_file=Path(args.attestation_verification_file),
        promotion_decision_file=Path(args.promotion_decision_file),
        sbom_file=Path(args.sbom_file) if str(args.sbom_file).strip() else None,
        require_allowed=args.require_allowed,
    )
    print("PASS: release evidence is present and structurally valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
