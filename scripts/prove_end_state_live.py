"""Live proof for the two claims that make this factory unique.

1. ZIP-style import through an accepted SOW as PORT (Python -> Go).
2. A failing factory QC test (stdlib unittest) blocks COMPLETE.

    python scripts/prove_end_state_live.py

Requires the live stack. Stop Mission Control first so its poll cycle cannot
429 mission creation:

    docker stop deploy-mission-control-1
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests" / "services"))
from live_stack_auth import resolve_internal_service_api_key  # noqa: E402

GATEWAY = "http://127.0.0.1:8100"
TIMEOUT = 30.0
API_KEY = resolve_internal_service_api_key()
OUTPUT_ROOT = ROOT / "output"

PORT_SOURCE = """## FILE add.py
import sys

def add(a, b):
    return int(a) + int(b)

def main():
    if len(sys.argv) != 3:
        print("usage: add.py A B", file=sys.stderr)
        return 2
    print(add(sys.argv[1], sys.argv[2]))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
"""


def request_json(
    method: str,
    path: str,
    payload: dict | None = None,
    headers: dict | None = None,
) -> tuple[int, Any]:
    hdrs = {"Accept": "application/json"}
    if API_KEY:
        hdrs["x-api-key"] = API_KEY
    if headers:
        hdrs.update(headers)
    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        hdrs.setdefault("Content-Type", "application/json")
    req = Request(f"{GATEWAY}{path}", data=body, method=method, headers=hdrs)
    try:
        with urlopen(req, timeout=TIMEOUT) as response:  # nosec B310
            raw = response.read().decode("utf-8")
            return int(response.status), (json.loads(raw) if raw else None)
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            parsed = raw
        return int(exc.code), parsed


def get_mission(mission_id: str) -> dict[str, Any]:
    _status, body = request_json("GET", f"/v1/missions/{mission_id}")
    return body if isinstance(body, dict) else {}


def get_chain(mission_id: str) -> dict[str, Any]:
    _status, body = request_json("GET", f"/v1/missions/{mission_id}/chain-trace")
    return body if isinstance(body, dict) else {}


def wait_for_mission(mission_id: str, *, timeout_seconds: float) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    last = ""
    while time.time() < deadline:
        mission = get_mission(mission_id)
        state = str(mission.get("state") or "").upper()
        events = [
            str(item.get("event_type") or "")
            for item in (get_chain(mission_id).get("events") or [])
            if isinstance(item, dict)
        ]
        blocked = "MISSION_RUNTIME_QC_BLOCKED" in events
        report = (mission.get("metadata") or {}).get("runtime_qc_report") or {}
        assessment = report.get("qc_assessment") if isinstance(report.get("qc_assessment"), dict) else {}
        qc_verdict = str(assessment.get("qc_verdict") or "")
        if state != last:
            print(f"  {mission_id} state={state or '?'}", flush=True)
            last = state
        if state in {"COMPLETE", "FAILED", "CANCELLED"} or blocked or (
            state == "VERIFIED" and qc_verdict == "FAIL"
        ):
            return mission
        time.sleep(8.0)
    return get_mission(mission_id)


def sow_contract(title: str, engagement: str, summary: str) -> dict[str, Any]:
    return {
        "schema_version": "feature_contract.v1",
        "title": title,
        "summary": summary,
        "engagement_type": engagement,
        "out_of_scope": ["UI", "network services", "human labor pricing"],
        "deliverables": [
            {"name": "source tree", "artifact_hint": "generated_output"},
            {"name": "runtime QC report", "artifact_hint": "runtime_qc_report"},
        ],
        "acceptance_criteria": [
            "Factory writes local output",
            "Runtime QC records a real verdict",
        ],
        "estimated_complexity": "low",
        "cost_estimate": {
            "likely_usd": 0.35,
            "high_usd": 0.70,
            "cap_usd": 1.05,
            "pricing_known": True,
        },
    }


def port_proof_passed(state: Any, files: list[str] | None) -> bool:
    return str(state or "").upper() == "COMPLETE" and bool(files)


def fail_qc_proof_passed(state: Any, qc_verdict: Any, blocked: bool) -> bool:
    return str(state or "").upper() != "COMPLETE" and (
        str(qc_verdict or "").upper() == "FAIL" or blocked
    )


def create_sow(title: str, engagement: str, summary: str) -> str:
    contract = sow_contract(title, engagement, summary)
    status, body = request_json(
        "POST",
        "/v1/sows",
        payload={"feature_contract": contract, "approved_by": "operator"},
    )
    if status not in {200, 201} or not isinstance(body, dict) or not body.get("sow_id"):
        raise RuntimeError(f"SOW create failed HTTP {status}: {body!r}")
    return str(body["sow_id"])


def create_mission(*, prompt: str, mission_type: str, language: str, source_code: str | None, sow_id: str, extra_metadata: dict[str, Any]) -> str:
    metadata = {
        "source": "end-state-live-proof",
        "sow_id": sow_id,
        "mission_type": mission_type,
        **extra_metadata,
    }
    payload: dict[str, Any] = {
        "prompt": prompt,
        "requested_target_language": language,
        "mission_type": mission_type,
        "metadata": metadata,
    }
    if source_code:
        payload["source_code"] = source_code
    status, body = request_json(
        "POST",
        "/v1/missions",
        payload=payload,
        headers={"Idempotency-Key": f"proof-{uuid.uuid4().hex}"},
    )
    if status not in {200, 201} or not isinstance(body, dict) or not body.get("mission_id"):
        raise RuntimeError(f"mission create failed HTTP {status}: {body!r}")
    return str(body["mission_id"])


def output_files(mission_id: str) -> list[str]:
    mission_dir = OUTPUT_ROOT / mission_id
    if not mission_dir.is_dir():
        return []
    return sorted(
        str(path.relative_to(mission_dir)).replace("\\", "/")
        for path in mission_dir.rglob("*")
        if path.is_file()
    )


def prove_port() -> dict[str, Any]:
    print("=== PORT through accepted SOW ===", flush=True)
    sow_id = create_sow(
        "Port add.py to Go",
        "PORT",
        "Port the imported two-argument adder CLI from Python to Go. Preserve argv usage and exit codes.",
    )
    print(f"  sow_id={sow_id}", flush=True)
    mission_id = create_mission(
        prompt=(
            "Port the attached Python CLI add.py to Go. Keep the same argv contract: "
            "two integer arguments, print the sum, usage on stderr and exit 2 if argc is wrong. "
            "Deliver a Go file tree, not a Python rewrite."
        ),
        mission_type="PORT",
        language="go",
        source_code=PORT_SOURCE,
        sow_id=sow_id,
        extra_metadata={"proof": "zip_port_sow"},
    )
    print(f"  mission={mission_id}", flush=True)
    mission = wait_for_mission(mission_id, timeout_seconds=1500)
    chain = get_chain(mission_id)
    events = [
        str(item.get("event_type") or "")
        for item in (chain.get("events") or [])
        if isinstance(item, dict)
    ]
    files = output_files(mission_id)
    generated = (mission.get("metadata") or {}).get("generated_output") or {}
    return {
        "kind": "port_through_sow",
        "sow_id": sow_id,
        "mission_id": mission_id,
        "final_state": mission.get("state"),
        "official_type": mission.get("mission_type") or (mission.get("metadata") or {}).get("mission_type"),
        "generated_language": generated.get("language"),
        "generated_filename": generated.get("filename"),
        "file_count": generated.get("file_count"),
        "output_files": files,
        "chain_events": events,
        "passed": port_proof_passed(mission.get("state"), files),
    }


def prove_failing_qc() -> dict[str, Any]:
    print("=== failing test blocks COMPLETE ===", flush=True)
    sow_id = create_sow(
        "QC must fail this run",
        "BUILD_NEW",
        "Generate a tiny adder and run factory QC. A planted failing unittest must block delivery.",
    )
    print(f"  sow_id={sow_id}", flush=True)
    mission_id = create_mission(
        prompt=(
            "Write a tiny Python function add(a, b) that returns a+b in adder.py. "
            "Keep the implementation stdlib-only."
        ),
        mission_type="BUILD_NEW",
        language="python",
        source_code=None,
        sow_id=sow_id,
        extra_metadata={
            "proof": "failing_qc_blocks_complete",
            "integration_tests": {
                "schema_version": "integration_tests.v1",
                "framework": "unittest",
                "source": "live-proof-planted-fail",
                "test_filename": "test_adder.py",
                "test_cases": ["intentional fail"],
                "test_code": (
                    "import unittest\n"
                    "class FactoryMustFail(unittest.TestCase):\n"
                    "    def test_factory_must_fail(self):\n"
                    "        self.fail('intentional factory QC fail')\n"
                ),
            },
        },
    )
    print(f"  mission={mission_id}", flush=True)
    mission = wait_for_mission(mission_id, timeout_seconds=1200)
    chain = get_chain(mission_id)
    events = [
        str(item.get("event_type") or "")
        for item in (chain.get("events") or [])
        if isinstance(item, dict)
    ]
    report = (mission.get("metadata") or {}).get("runtime_qc_report") or {}
    assessment = report.get("qc_assessment") if isinstance(report.get("qc_assessment"), dict) else {}
    state = str(mission.get("state") or "").upper()
    qc_verdict = str(assessment.get("qc_verdict") or report.get("verdict") or "")
    blocked = "MISSION_RUNTIME_QC_BLOCKED" in events
    return {
        "kind": "failing_qc_blocks_complete",
        "sow_id": sow_id,
        "mission_id": mission_id,
        "final_state": mission.get("state"),
        "qc_verdict": qc_verdict,
        "execution_verdict": report.get("verdict"),
        "blocked_event": blocked,
        "chain_events": events,
        "passed": fail_qc_proof_passed(state, qc_verdict, blocked),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", choices=("fail-qc", "port", "both"), default="both")
    args = parser.parse_args()
    if not API_KEY:
        print("No gateway credential; nothing would be verified.", file=sys.stderr)
        return 2
    status, health = request_json("GET", "/readyz")
    if status != 200:
        print(f"gateway not ready HTTP {status}: {health!r}", file=sys.stderr)
        return 2

    fail_qc: dict[str, Any] = {}
    port: dict[str, Any] = {}
    if args.only in {"fail-qc", "both"}:
        fail_qc = prove_failing_qc()
    if args.only in {"port", "both"}:
        port = prove_port()
    evidence = {
        "schema_version": "end_state_live_proof.v1",
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "failing_qc": fail_qc,
        "port_through_sow": port,
        "both_passed": bool(
            fail_qc.get("passed") if args.only == "fail-qc"
            else port.get("passed") if args.only == "port"
            else fail_qc.get("passed") and port.get("passed")
        ),
    }
    out = ROOT / "docs" / "evidence" / f"end_state_live_proof_{time.strftime('%Y%m%d')}.json"
    out.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(f"\nwrote {out.relative_to(ROOT)}")
    print(f"  fail QC : state={fail_qc.get('final_state')} verdict={fail_qc.get('qc_verdict')} passed={fail_qc.get('passed')}")
    print(f"  PORT    : state={port.get('final_state')} files={port.get('output_files')} passed={port.get('passed')}")
    return 0 if evidence["both_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
