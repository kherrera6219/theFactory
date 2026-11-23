"""Generate or verify docs/LANGUAGE_MATURITY.md and the Mission Control maturity JSON.

Both outputs are rendered from the live orchestrator runtime tables. The JSON is
what the Mission Control maturity badge reads, so the UI and the doc cannot drift.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ORCHESTRATOR_PKG_ROOT = REPO_ROOT / "services" / "orchestrator"
POD_WORKER_PKG_ROOT = REPO_ROOT / "services" / "pod-worker"
for _p in (str(REPO_ROOT), str(ORCHESTRATOR_PKG_ROOT), str(POD_WORKER_PKG_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from orchestrator.language_maturity import (  # noqa: E402
    format_language_maturity_json,
    format_language_maturity_markdown,
    write_language_maturity_doc,
    write_language_maturity_json,
)

DEFAULT_JSON_OUTPUT = (
    REPO_ROOT / "apps" / "mission-control" / "app" / "lib" / "language-maturity.generated.json"
)


def _check(target: Path, expected: str) -> bool:
    if not target.is_file():
        print(f"Missing generated file: {target}", file=sys.stderr)
        return False
    if target.read_text(encoding="utf-8") != expected:
        print(
            f"Stale language maturity output at {target}; run scripts/generate_language_maturity.py",
            file=sys.stderr,
        )
        return False
    print(f"Language maturity output up to date: {target}")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        default=str(REPO_ROOT / "docs" / "LANGUAGE_MATURITY.md"),
        help="Destination Markdown file path.",
    )
    parser.add_argument(
        "--json-output",
        default=str(DEFAULT_JSON_OUTPUT),
        help="Destination JSON file path consumed by the Mission Control maturity badge.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if either generated output does not match the file on disk.",
    )
    args = parser.parse_args(argv)

    md_target = Path(args.output)
    json_target = Path(args.json_output)
    if args.check:
        md_ok = _check(md_target, format_language_maturity_markdown())
        json_ok = _check(json_target, format_language_maturity_json())
        return 0 if (md_ok and json_ok) else 1

    write_language_maturity_doc(md_target)
    write_language_maturity_json(json_target)
    print(f"Wrote {md_target}")
    print(f"Wrote {json_target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
