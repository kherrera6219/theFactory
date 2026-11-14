"""Generate or verify docs/LANGUAGE_MATURITY.md from live orchestrator runtime tables."""

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
    format_language_maturity_markdown,
    write_language_maturity_doc,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        default=str(REPO_ROOT / "docs" / "LANGUAGE_MATURITY.md"),
        help="Destination Markdown file path.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if the generated output does not match the file on disk.",
    )
    args = parser.parse_args(argv)

    target = Path(args.output)
    expected = format_language_maturity_markdown()
    if args.check:
        if not target.is_file():
            print(f"Missing generated file: {target}", file=sys.stderr)
            return 1
        actual = target.read_text(encoding="utf-8")
        if actual != expected:
            print(
                f"Stale language maturity matrix at {target}; run scripts/generate_language_maturity.py",
                file=sys.stderr,
            )
            return 1
        print(f"Language maturity matrix up to date: {target}")
        return 0

    write_language_maturity_doc(target)
    print(f"Wrote {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
