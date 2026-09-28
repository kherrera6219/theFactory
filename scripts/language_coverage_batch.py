#!/usr/bin/env python3
"""Submit one BUILD_NEW mission per routed language and report what each proved.

The 2026-08-27 coverage run found that 17 of 20 missions completed without any
correctness evidence. This script re-runs that experiment reproducibly: every
language gets the same small, tightly specified CLI task, so runtime QC and the
contract oracle (WQ7) both have falsifiable acceptance criteria to check.

    python scripts/language_coverage_batch.py submit --batch lang-coverage-2026-09-28
    python scripts/language_coverage_batch.py report --batch lang-coverage-2026-09-28 \\
        [--wait-minutes 60] [--out docs/evidence/lang_coverage_20260928.json]

Submitting creates real missions and makes real LLM calls against the stack's
configured provider. The report never writes to the stack.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests" / "services"))

from live_stack_auth import resolve_internal_service_api_key  # noqa: E402

GATEWAY = "http://127.0.0.1:8100"

#: The 20 routed language keys (TypeScript is a distinct key over the JS specialist).
LANGUAGES = [
    "python", "javascript", "typescript", "ruby", "php",
    "c", "cpp", "rust", "go", "zig",
    "java", "csharp", "scala", "kotlin",
    "r", "matlab", "julia", "mathematica", "haskell", "ocaml",
]

TASK = (
    "Build a small command-line program named sum_integers. It reads "
    "whitespace-separated integers from standard input and prints their sum on "
    "a single line to standard output, then exits with code 0.\n"
    "Acceptance criteria:\n"
    "1. Empty input prints 0.\n"
    "2. The input `1 2 3` prints 6.\n"
    "3. Negative numbers are supported: `-5 10` prints 5.\n"
    "4. Numbers may be separated by spaces, tabs or newlines.\n"
    "5. A token that is not an integer (for example `abc`) prints an error "
    "message to standard error and exits with code 1.\n"
    "Keep the summing logic in its own function and include unit tests for it. "
    "Use only the language's standard library."
)

TERMINAL = {"COMPLETE", "FAILED", "CANCELLED", "VERIFIED", "CLARIFYING"}


def _client() -> httpx.Client:
    return httpx.Client(
        base_url=GATEWAY,
        headers={"x-api-key": resolve_internal_service_api_key()},
        timeout=30.0,
    )


def submit(batch: str) -> int:
    with _client() as client:
        for language in LANGUAGES:
            response = client.post(
                "/v1/missions",
                json={
                    "prompt": TASK,
                    "requested_target_language": language,
                    "metadata": {"source": "language-coverage-batch", "test_batch": batch},
                },
                headers={"Idempotency-Key": f"{batch}-{language}-{uuid.uuid4()}"},
            )
            mission_id = response.json().get("mission_id") if response.status_code < 300 else None
            print(f"{language:12} {response.status_code} {mission_id or response.text[:120]}")
            time.sleep(2)  # stay well inside the gateway's write budget
    return 0


def _missions(client: httpx.Client, batch: str) -> list[dict[str, Any]]:
    response = client.get("/v1/missions", params={"limit": 500})
    response.raise_for_status()
    body = response.json()
    records = body.get("missions", body) if isinstance(body, dict) else body
    return [
        m for m in records
        if isinstance(m, dict) and (m.get("metadata") or {}).get("test_batch") == batch
    ]


def _summarise(mission: dict[str, Any]) -> dict[str, Any]:
    meta = mission.get("metadata") or {}
    qc = meta.get("runtime_qc_report") or {}
    eq = (meta.get("equivalence_report") or {}).get("behavioural") or {}
    generated = meta.get("generated_output") or {}
    return {
        "mission_id": mission.get("mission_id"),
        "language": mission.get("requested_target_language"),
        "state": mission.get("state"),
        "generation_source": generated.get("source"),
        "qc_verdict": qc.get("verdict"),
        "qc_scope": qc.get("verified_scope_detail"),
        "qc_execution": qc.get("execution_type"),
        "qc_image": qc.get("base_image"),
        "qc_reason": qc.get("dry_run_reason") or qc.get("tests_not_run_reason"),
        "behavioural_status": eq.get("status"),
        "behavioural_basis": eq.get("verification_basis"),
        "vectors_passed": eq.get("equivalence_vectors_passed"),
        "vectors_failed": eq.get("equivalence_vectors_failed"),
        "vectors_total": eq.get("equivalence_vectors_total"),
    }


def report(batch: str, wait_minutes: float, out: str | None) -> int:
    deadline = time.monotonic() + wait_minutes * 60
    with _client() as client:
        while True:
            missions = _missions(client, batch)
            done = [m for m in missions if str(m.get("state", "")).upper() in TERMINAL]
            print(f"{datetime.now(UTC):%H:%M:%S} {len(done)}/{len(missions)} settled")
            if missions and len(done) == len(missions) or time.monotonic() > deadline:
                break
            time.sleep(30)
        detailed = []
        for mission in missions:
            full = client.get(f"/v1/missions/{mission['mission_id']}").json()
            detailed.append(_summarise(full if isinstance(full, dict) else mission))

    detailed.sort(key=lambda row: LANGUAGES.index(row["language"]) if row["language"] in LANGUAGES else 99)
    header = f"{'language':12} {'state':10} {'gen':8} {'qc':8} {'scope':12} {'behavioural':12} vectors"
    print(header)
    for row in detailed:
        vectors = f"{row['vectors_passed']}/{row['vectors_total']}" if row["vectors_total"] else "-"
        print(f"{row['language'] or '?':12} {row['state'] or '?':10} {row['generation_source'] or '-':8} "
              f"{row['qc_verdict'] or '-':8} {row['qc_scope'] or '-':12} "
              f"{row['behavioural_status'] or '-':12} {vectors}")
    if out:
        Path(out).write_text(json.dumps({
            "batch": batch,
            "captured_at": datetime.now(UTC).isoformat(),
            "task": TASK,
            "missions": detailed,
        }, indent=2) + "\n", encoding="utf-8")
        print(f"evidence written to {out}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    s = sub.add_parser("submit")
    s.add_argument("--batch", required=True)
    r = sub.add_parser("report")
    r.add_argument("--batch", required=True)
    r.add_argument("--wait-minutes", type=float, default=0)
    r.add_argument("--out")
    args = parser.parse_args()
    if args.command == "submit":
        return submit(args.batch)
    return report(args.batch, args.wait_minutes, args.out)


if __name__ == "__main__":
    raise SystemExit(main())
