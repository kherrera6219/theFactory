"""Run one live mission end to end and write a durable evidence file.

Produces the artifact `docs/CURRENT_TODO.md` calls S1-01 / UPG-20 evidence: a
mission id, its chain events, the durable records, the build artifact, and --
new since RQCA became functional -- the runtime-QC verdict showing the generated
code was actually executed rather than merely inspected.

    python scripts/capture_live_mission_evidence.py --language go

Requires a live stack. Stop Mission Control first or its polling can exhaust the
gateway's write budget and mission creation returns 429:

    docker stop deploy-mission-control-1

Defaults to Go deliberately. Go is in `_PYTHON_DISSIMILAR_LANGUAGES`, so the
content-signature check is in scope, and it is a compiled language, so a
Python-fallback artifact cannot pass runtime QC. A Python mission proves much
less: Python source passes a Python runtime whether or not the specialist
actually understood the request.
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
ORCHESTRATOR = "http://127.0.0.1:8101"
TIMEOUT = 30.0
API_KEY = resolve_internal_service_api_key()

PROMPTS = {
    "go": (
        "Write a single-file Go command-line program that reads a UTF-8 text file "
        "whose path is given as the first argument, counts how many times each "
        "lowercase word appears, and prints 'word count' pairs one per line sorted "
        "by descending count then ascending word. Exit non-zero with a message on "
        "stderr if the file cannot be read."
    ),
    "rust": (
        "Write a single-file Rust command-line program that reads a UTF-8 text file "
        "whose path is given as the first argument and prints each distinct "
        "lowercase word with its occurrence count, one per line."
    ),
}


def request_json(method: str, path: str, payload: dict | None = None,
                 headers: dict | None = None, base: str = GATEWAY) -> tuple[int, Any]:
    hdrs = {"Accept": "application/json"}
    if API_KEY:
        hdrs["x-api-key"] = API_KEY
    if headers:
        hdrs.update(headers)
    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        hdrs.setdefault("Content-Type", "application/json")
    req = Request(f"{base}{path}", data=body, method=method, headers=hdrs)
    with urlopen(req, timeout=TIMEOUT) as response:
        raw = response.read().decode("utf-8")
        return int(response.status), (json.loads(raw) if raw else None)


def get(path: str) -> Any:
    try:
        return request_json("GET", path)[1]
    except HTTPError as exc:
        return {"_http_error": exc.code}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--language", default="go", choices=sorted(PROMPTS))
    parser.add_argument("--timeout-seconds", type=float, default=1200.0)
    args = parser.parse_args()

    if not API_KEY:
        print("No gateway credential resolved; nothing would be verified.", file=sys.stderr)
        return 2

    status, created = request_json(
        "POST", "/v1/missions",
        payload={
            "prompt": PROMPTS[args.language],
            "requested_target_language": args.language,
            "metadata": {"source": "s1-01-evidence-capture"},
        },
        headers={"Idempotency-Key": f"evidence-{uuid.uuid4().hex}"},
    )
    if status not in {200, 201}:
        print(f"mission creation failed: HTTP {status}: {created!r}", file=sys.stderr)
        return 1
    mission_id = created["mission_id"]
    print(f"mission: {mission_id} ({args.language})", flush=True)

    # CLARIFYING is a deliberate operator hold, not a failure: the PM raises
    # questions with recommended defaults for almost any prompt and parks the
    # mission. Without answering it the mission never reaches the delegation
    # chain and this script would just poll until its timeout -- which is
    # exactly what happened on the first run.
    deadline = time.time() + args.timeout_seconds
    state = ""
    clarified = False
    while time.time() < deadline:
        mission = get(f"/v1/missions/{mission_id}")
        state = str((mission or {}).get("state", "")).upper()

        if state == "CLARIFYING" and not clarified:
            clar_status, clar_body = request_json(
                "POST", f"/missions/{mission_id}/clarify",
                payload={"clarification": (
                    "Proceed with the recommended defaults for every open question. "
                    "ASCII [a-z]+ word extraction on lowercased input, a single space "
                    "between word and count, one pair per line, and a non-zero exit "
                    "with a stderr message when the file cannot be read."
                )},
                base=ORCHESTRATOR,
            )
            if clar_status != 200:
                print(f"clarify failed: HTTP {clar_status}: {clar_body!r}", file=sys.stderr)
                return 1
            clarified = True
            print("  answered PM clarification with defaults", flush=True)
            time.sleep(3.0)
            continue

        if state in {"COMPLETE", "FAILED"}:
            break
        print(f"  state={state or '?'}", flush=True)
        time.sleep(10.0)

    mission = get(f"/v1/missions/{mission_id}")
    metadata = (mission or {}).get("metadata") or {}
    chain = get(f"/v1/missions/{mission_id}/chain-trace")
    evidence = {
        "schema_version": "live_mission_evidence.v1",
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "mission_id": mission_id,
        "requested_target_language": args.language,
        "final_state": str((mission or {}).get("state", "")),
        "chain_events": [
            e.get("event_type") for e in (chain or {}).get("events", [])
            if isinstance(e, dict)
        ],
        "pod_assignment": get(f"/v1/missions/{mission_id}/pod-assignment"),
        "logicnodes_count": len(get(f"/v1/missions/{mission_id}/logicnodes?limit=200") or []),
        "build_artifacts": [
            {k: a.get(k) for k in ("artifact_id", "artifact_type", "size_bytes", "status")}
            for a in (get(f"/v1/missions/{mission_id}/build-artifacts?limit=20") or [])
            if isinstance(a, dict)
        ],
        # The point of this capture since RQCA became functional: proof the
        # generated code was executed, not merely inspected.
        "runtime_qc_report": metadata.get("runtime_qc_report"),
        "equivalence_report": metadata.get("equivalence_report"),
        "generated_output": {
            k: (metadata.get("generated_output") or {}).get(k)
            for k in ("language", "filename", "source", "code_length_chars")
        },
        "pod_manager_routing_correction": metadata.get("pod_manager_routing_correction"),
        "delta_audit_gate": metadata.get("delta_audit_gate"),
    }

    out = ROOT / "docs" / "evidence" / f"s1_01_live_generation_{args.language}_{time.strftime('%Y%m%d')}.json"
    out.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(f"\nwrote {out.relative_to(ROOT)}")
    print(f"  final state : {evidence['final_state']}")
    print(f"  chain events: {len(evidence['chain_events'])}")
    print(f"  artifacts   : {len(evidence['build_artifacts'])}")
    rqc = evidence["runtime_qc_report"] or {}
    print(f"  runtime QC  : {rqc.get('verdict')} / {rqc.get('execution_type')} "
          f"image={rqc.get('base_image')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
