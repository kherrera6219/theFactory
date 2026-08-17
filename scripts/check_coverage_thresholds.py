from __future__ import annotations

import argparse
import sys
from pathlib import PurePosixPath

from defusedxml import ElementTree as ET


def _normalize(path: str) -> str:
    return str(PurePosixPath(path.replace("\\", "/")))


def _parse_module_thresholds(items: list[str]) -> dict[str, float]:
    thresholds: dict[str, float] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(
                f"invalid --module-threshold value: {item!r} (expected path=threshold)"
            )
        path, value = item.split("=", 1)
        normalized = _normalize(path.strip())
        thresholds[normalized] = float(value.strip())
    return thresholds


def _find_module_rate(file_rates: dict[str, float], module: str) -> float | None:
    direct_candidates = [module]
    if module.startswith("services/"):
        direct_candidates.append(module[len("services/") :])

    for candidate in direct_candidates:
        if candidate in file_rates:
            return file_rates[candidate]

    for candidate in direct_candidates:
        for path, rate in file_rates.items():
            if path.endswith(candidate):
                return rate
    return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate global and selected module coverage thresholds from coverage.xml."
    )
    parser.add_argument(
        "--coverage-file",
        default="coverage.xml",
        help="Path to Cobertura XML coverage report (default: coverage.xml).",
    )
    parser.add_argument(
        "--global-threshold",
        type=float,
        default=80.0,
        help="Minimum mixed (line+branch) coverage percentage.",
    )
    parser.add_argument(
        "--line-threshold",
        type=float,
        default=80.0,
        help="Minimum global line coverage percentage.",
    )
    parser.add_argument(
        "--branch-threshold",
        type=float,
        default=70.0,
        help="Minimum global branch coverage percentage.",
    )
    parser.add_argument(
        "--module-threshold",
        action="append",
        default=[],
        help="Per-module line-rate threshold in the form path=percent (repeatable).",
    )
    args = parser.parse_args()

    module_thresholds = _parse_module_thresholds(args.module_threshold)
    root = ET.parse(args.coverage_file).getroot()

    lines_valid = int(root.attrib.get("lines-valid", "0"))
    lines_covered = int(root.attrib.get("lines-covered", "0"))
    branches_valid = int(root.attrib.get("branches-valid", "0"))
    branches_covered = int(root.attrib.get("branches-covered", "0"))

    line_percent = (lines_covered / lines_valid) * 100.0 if lines_valid > 0 else 0.0
    branch_percent = (
        (branches_covered / branches_valid) * 100.0 if branches_valid > 0 else 100.0
    )
    if branches_valid > 0:
        global_denominator = lines_valid + branches_valid
        global_numerator = lines_covered + branches_covered
    else:
        global_denominator = lines_valid
        global_numerator = lines_covered
    global_percent = (
        (global_numerator / global_denominator) * 100.0 if global_denominator > 0 else 0.0
    )

    failures: list[str] = []
    print(f"Line coverage: {line_percent:.2f}% (threshold {args.line_threshold:.2f}%)")
    print(f"Branch coverage: {branch_percent:.2f}% (threshold {args.branch_threshold:.2f}%)")
    print(f"Mixed coverage: {global_percent:.2f}% (threshold {args.global_threshold:.2f}%)")
    if line_percent < args.line_threshold:
        failures.append(
            f"line coverage {line_percent:.2f}% is below threshold {args.line_threshold:.2f}%"
        )
    if branch_percent < args.branch_threshold:
        failures.append(
            f"branch coverage {branch_percent:.2f}% is below threshold {args.branch_threshold:.2f}%"
        )
    if global_percent < args.global_threshold:
        failures.append(
            f"mixed coverage {global_percent:.2f}% is below threshold {args.global_threshold:.2f}%"
        )

    file_rates: dict[str, float] = {}
    for class_node in root.findall(".//class"):
        filename = class_node.attrib.get("filename")
        if not filename:
            continue
        file_rates[_normalize(filename)] = float(class_node.attrib.get("line-rate", "0.0")) * 100.0

    for module, threshold in sorted(module_thresholds.items()):
        module_percent = _find_module_rate(file_rates, module)
        if module_percent is None:
            failures.append(f"module not found in coverage report: {module}")
            continue
        print(f"Module coverage: {module} => {module_percent:.2f}% (threshold {threshold:.2f}%)")
        if module_percent < threshold:
            failures.append(
                "module coverage "
                f"{module_percent:.2f}% is below threshold {threshold:.2f}% for {module}"
            )

    if failures:
        print("Coverage threshold check failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("Coverage threshold check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
