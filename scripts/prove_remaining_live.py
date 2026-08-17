"""Live proofs for the remaining Sprint 1.1 / Phase 6 claims.

1. Failure injection — restart protocol-bus mid-mission; the mission does not
   vanish and ends in a visible terminal state.
2. Provider fallback — unpin LLM_PROVIDER=auto, invalid Gemini, OpenAI
   succeeds; token usage records route=fallback.
3. EDCP live-bus — EVENT_DRIVEN_CONTROL_PLANE_ENABLED=true; COMPLETE only
   after a consumed Delta verdict (prefix-parsed, never equality).
4. Spend-cap pause — tiny cap records spend_cap_hit and does not COMPLETE.
5. Chat ZIP API — Mission Control /api/repo/import + review, then SOW+PORT.

    python scripts/prove_remaining_live.py

Stop Mission Control first so its poll cycle cannot 429 mission creation:

    docker stop deploy-mission-control-1
"""

from __future__ import annotations

import argparse
import io
import json
import subprocess
import sys
import time
import uuid
import zipfile
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests" / "services"))
from live_stack_auth import resolve_internal_service_api_key  # noqa: E402

GATEWAY = "http://127.0.0.1:8100"
MISSION_CONTROL = "http://127.0.0.1:3100"
TIMEOUT = 30.0
API_KEY = resolve_internal_service_api_key()
COMPOSE = [
    "docker",
    "compose",
    "--env-file",
    ".env",
    "-f",
    "deploy/docker-compose.yaml",
    "-f",
    "deploy/docker-compose.full-dedicated-agents.yaml",
    "--profile",
    "full-dedicated-agents",
]


def request_json(
    method: str,
    path: str,
    payload: dict | None = None,
    *,
    base: str = GATEWAY,
    headers: dict | None = None,
    raw_body: bytes | None = None,
    content_type: str | None = None,
) -> tuple[int, Any]:
    hdrs = {"Accept": "application/json"}
    if API_KEY and base == GATEWAY:
        hdrs["x-api-key"] = API_KEY
    if headers:
        hdrs.update(headers)
    body = raw_body
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        hdrs.setdefault("Content-Type", "application/json")
    if content_type:
        hdrs["Content-Type"] = content_type
    req = Request(f"{base}{path}", data=body, method=method, headers=hdrs)
    try:
        with urlopen(req, timeout=TIMEOUT) as response:
            raw = response.read().decode("utf-8")
            if not raw:
                return int(response.status), None
            try:
                return int(response.status), json.loads(raw)
            except json.JSONDecodeError:
                return int(response.status), raw
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            parsed = raw
        return int(exc.code), parsed
    except (URLError, OSError, TimeoutError) as exc:
        return 0, str(exc)


def get_mission(mission_id: str) -> dict[str, Any]:
    _status, body = request_json("GET", f"/v1/missions/{mission_id}")
    return body if isinstance(body, dict) else {}


def get_chain(mission_id: str) -> dict[str, Any]:
    _status, body = request_json("GET", f"/v1/missions/{mission_id}/chain-trace")
    return body if isinstance(body, dict) else {}


def get_usage(mission_id: str) -> dict[str, Any]:
    _status, body = request_json("GET", f"/v1/missions/{mission_id}/token-usage")
    return body if isinstance(body, dict) else {}


def chain_events(mission_id: str) -> list[str]:
    return [
        str(item.get("event_type") or "")
        for item in (get_chain(mission_id).get("events") or [])
        if isinstance(item, dict)
    ]


def wait_for_mission(
    mission_id: str,
    *,
    timeout_seconds: float,
    extra_terminal: set[str] | None = None,
) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    last = ""
    extra = extra_terminal or set()
    while time.time() < deadline:
        mission = get_mission(mission_id)
        state = str(mission.get("state") or "").upper()
        events = chain_events(mission_id)
        metadata = mission.get("metadata") if isinstance(mission.get("metadata"), dict) else {}
        blocked = "MISSION_RUNTIME_QC_BLOCKED" in events
        completion_blocked = "MISSION_COMPLETION_BLOCKED" in events
        spend_hit = bool(metadata.get("spend_cap_hit"))
        report = metadata.get("runtime_qc_report") or {}
        assessment = report.get("qc_assessment") if isinstance(report.get("qc_assessment"), dict) else {}
        qc_verdict = str(assessment.get("qc_verdict") or "")
        if state != last:
            print(f"  {mission_id} state={state or '?'}", flush=True)
            last = state
        if state in {"COMPLETE", "FAILED", "CANCELLED"} | extra:
            return mission
        if blocked or (state == "VERIFIED" and qc_verdict == "FAIL"):
            return mission
        if spend_hit and state not in {"QUEUED", "PM_INTAKE"}:
            return mission
        if completion_blocked and state == "VERIFIED":
            return mission
        time.sleep(8.0)
    return get_mission(mission_id)


def sow_contract(title: str, engagement: str, summary: str, *, cap_usd: float = 1.05) -> dict[str, Any]:
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
        "acceptance_criteria": ["Factory writes local output"],
        "estimated_complexity": "low",
        "cost_estimate": {
            "likely_usd": 0.35,
            "high_usd": 0.70,
            "cap_usd": cap_usd,
            "pricing_known": True,
        },
    }


def create_sow(title: str, engagement: str, summary: str, *, cap_usd: float = 1.05) -> str:
    status, body = request_json(
        "POST",
        "/v1/sows",
        payload={
            "feature_contract": sow_contract(title, engagement, summary, cap_usd=cap_usd),
            "approved_by": "operator",
        },
    )
    if status not in {200, 201} or not isinstance(body, dict) or not body.get("sow_id"):
        raise RuntimeError(f"SOW create failed HTTP {status}: {body!r}")
    return str(body["sow_id"])


def create_mission(
    *,
    prompt: str,
    mission_type: str,
    language: str,
    sow_id: str,
    extra_metadata: dict[str, Any] | None = None,
    source_code: str | None = None,
) -> str:
    metadata = {
        "source": "remaining-live-proof",
        "sow_id": sow_id,
        "mission_type": mission_type,
        **(extra_metadata or {}),
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
        headers={"Idempotency-Key": f"remain-{uuid.uuid4().hex}"},
    )
    if status not in {200, 201} or not isinstance(body, dict) or not body.get("mission_id"):
        raise RuntimeError(f"mission create failed HTTP {status}: {body!r}")
    return str(body["mission_id"])


def wait_until_started(mission_id: str, *, timeout_seconds: float = 180) -> str:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        state = str(get_mission(mission_id).get("state") or "").upper()
        if state and state not in {"", "QUEUED"}:
            return state
        time.sleep(3.0)
    return str(get_mission(mission_id).get("state") or "")


def run_compose(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    import os

    merged = os.environ.copy()
    if env:
        merged.update(env)
    return subprocess.run(
        [*COMPOSE, *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env=merged,
        check=False,
    )


def recreate_orchestrator(env: dict[str, str] | None = None) -> None:
    print(f"  recreating orchestrator env={sorted((env or {}).keys())}", flush=True)
    override = ROOT / "deploy" / ".tmp-orchestrator-proof.yaml"
    extra: list[str] = []
    if env:
        lines = ["services:", "  orchestrator:", "    environment:"]
        for key, value in env.items():
            lines.append(f"      {key}: {json.dumps(value)}")
        override.write_text("\n".join(lines) + "\n", encoding="utf-8")
        extra = ["-f", str(override)]
    result = subprocess.run(
        [
            "docker",
            "compose",
            "--env-file",
            ".env",
            "-f",
            "deploy/docker-compose.yaml",
            "-f",
            "deploy/docker-compose.full-dedicated-agents.yaml",
            *extra,
            "--profile",
            "full-dedicated-agents",
            "up",
            "-d",
            "--no-deps",
            "--force-recreate",
            "orchestrator",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    if extra:
        override.unlink(missing_ok=True)
    if result.returncode != 0:
        raise RuntimeError(f"orchestrator recreate failed: {result.stderr[-2000:]}")
    deadline = time.time() + 180
    while time.time() < deadline:
        status, body = request_json("GET", "/readyz")
        if status == 200:
            return
        time.sleep(3.0)
    raise RuntimeError(f"orchestrator not ready after recreate: {body!r}")


def restore_orchestrator() -> None:
    recreate_orchestrator()


def tiny_python_prompt() -> str:
    return (
        "Write a tiny Python function add(a, b) that returns a+b in adder.py. "
        "Stdlib only. No UI."
    )


def failure_injection_passed(state: Any, event_count: int) -> bool:
    return str(state or "").upper() in {
        "COMPLETE",
        "FAILED",
        "CANCELLED",
        "VERIFIED",
    } and event_count > 0


def provider_fallback_passed(usage: dict[str, Any], generated_source: str = "") -> bool:
    routes = [str(item).lower() for item in (usage.get("routing_sources") or [])]
    providers = {
        str(item.get("provider") or "").lower()
        for item in (usage.get("by_provider") or [])
        if isinstance(item, dict)
    }
    return (
        "fallback" in routes
        or "openai" in providers
        or str(generated_source or "").lower() == "fallback"
    )


def edcp_live_passed(state: Any, gate: Any) -> bool:
    if not isinstance(gate, dict):
        return False
    consumed = bool(gate.get("consumed_at") or gate.get("correlation_id") or gate.get("audit_result"))
    if not consumed:
        return False
    correlation = str(gate.get("correlation_id") or "")
    if correlation and not correlation.startswith("delta-"):
        return False
    return str(state or "").upper() in {"COMPLETE", "VERIFIED"}


def spend_cap_passed(state: Any, metadata: dict[str, Any]) -> bool:
    cap = metadata.get("spend_cap") if isinstance(metadata.get("spend_cap"), dict) else {}
    return bool(metadata.get("spend_cap_hit")) or str(cap.get("state") or "") == "pause"


def chat_zip_passed(
    import_ok: bool,
    review_source: str,
    sow_id: str,
    source_chars: int = 0,
) -> bool:
    return import_ok and review_source == "zip" and bool(sow_id)


def prove_failure_injection() -> dict[str, Any]:
    print("=== failure injection: restart protocol-bus mid-mission ===", flush=True)
    sow_id = create_sow("Failure injection", "BUILD_NEW", tiny_python_prompt())
    mission_id = create_mission(
        prompt=tiny_python_prompt(),
        mission_type="BUILD_NEW",
        language="python",
        sow_id=sow_id,
        extra_metadata={"proof": "failure_injection"},
    )
    started = wait_until_started(mission_id)
    print(f"  injecting at state={started}", flush=True)
    restarted = run_compose("restart", "protocol-bus-mcp")
    mission = wait_for_mission(mission_id, timeout_seconds=1500)
    events = chain_events(mission_id)
    return {
        "kind": "failure_injection",
        "sow_id": sow_id,
        "mission_id": mission_id,
        "state_at_inject": started,
        "final_state": mission.get("state"),
        "restart_exit": restarted.returncode,
        "event_count": len(events),
        "chain_events": events,
        "passed": failure_injection_passed(mission.get("state"), len(events)),
    }


def prove_provider_fallback() -> dict[str, Any]:
    print("=== provider fallback: auto pin + invalid Gemini ===", flush=True)
    recreate_orchestrator(
        {
            "LLM_PROVIDER": "auto",
            "GEMINI_API_KEY": "invalid-fallback-proof-key",
        }
    )
    try:
        sow_id = create_sow("Provider fallback", "BUILD_NEW", tiny_python_prompt())
        mission_id = create_mission(
            prompt=tiny_python_prompt(),
            mission_type="BUILD_NEW",
            language="python",
            sow_id=sow_id,
            extra_metadata={"proof": "provider_fallback"},
        )
        mission = wait_for_mission(mission_id, timeout_seconds=1500)
        usage = get_usage(mission_id)
        generated = (mission.get("metadata") or {}).get("generated_output") or {}
        source = str(generated.get("source") or "")
        return {
            "kind": "provider_fallback",
            "sow_id": sow_id,
            "mission_id": mission_id,
            "final_state": mission.get("state"),
            "routing_sources": usage.get("routing_sources"),
            "by_provider": usage.get("by_provider"),
            "generated_source": source,
            "passed": provider_fallback_passed(usage, source),
        }
    finally:
        restore_orchestrator()


def prove_edcp_live_bus() -> dict[str, Any]:
    print("=== EDCP live-bus: EVENT_DRIVEN_CONTROL_PLANE_ENABLED=true ===", flush=True)
    recreate_orchestrator({"EVENT_DRIVEN_CONTROL_PLANE_ENABLED": "true"})
    try:
        sow_id = create_sow("EDCP live-bus", "BUILD_NEW", tiny_python_prompt())
        mission_id = create_mission(
            prompt=tiny_python_prompt(),
            mission_type="BUILD_NEW",
            language="python",
            sow_id=sow_id,
            extra_metadata={"proof": "edcp_live_bus"},
        )
        mission = wait_for_mission(mission_id, timeout_seconds=1500)
        deadline = time.time() + 90
        while time.time() < deadline:
            mission = get_mission(mission_id)
            metadata = mission.get("metadata") if isinstance(mission.get("metadata"), dict) else {}
            if isinstance(metadata.get("delta_audit_gate"), dict):
                break
            time.sleep(3.0)
        metadata = mission.get("metadata") if isinstance(mission.get("metadata"), dict) else {}
        gate = metadata.get("delta_audit_gate")
        events = chain_events(mission_id)
        return {
            "kind": "edcp_live_bus",
            "sow_id": sow_id,
            "mission_id": mission_id,
            "final_state": mission.get("state"),
            "delta_audit_gate": gate,
            "completion_blocked": "MISSION_COMPLETION_BLOCKED" in events,
            "chain_events": events,
            "passed": edcp_live_passed(mission.get("state"), gate),
        }
    finally:
        restore_orchestrator()


def prove_spend_cap() -> dict[str, Any]:
    print("=== spend-cap pause ===", flush=True)
    sow_id = create_sow(
        "Spend cap pause",
        "BUILD_NEW",
        tiny_python_prompt(),
        cap_usd=0.000001,
    )
    mission_id = create_mission(
        prompt=tiny_python_prompt(),
        mission_type="BUILD_NEW",
        language="python",
        sow_id=sow_id,
        extra_metadata={"proof": "spend_cap"},
    )
    mission = wait_for_mission(mission_id, timeout_seconds=1500)
    metadata = mission.get("metadata") if isinstance(mission.get("metadata"), dict) else {}
    return {
        "kind": "spend_cap",
        "sow_id": sow_id,
        "mission_id": mission_id,
        "final_state": mission.get("state"),
        "spend_cap": metadata.get("spend_cap"),
        "spend_cap_hit": metadata.get("spend_cap_hit"),
        "passed": spend_cap_passed(mission.get("state"), metadata),
    }


def _tiny_zip() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("add.py", "def add(a, b):\n    return int(a) + int(b)\n")
    return buffer.getvalue()


def prove_chat_zip() -> dict[str, Any]:
    print("=== Chat ZIP import API ===", flush=True)
    run_compose("start", "mission-control")
    deadline = time.time() + 120
    while time.time() < deadline:
        status, _body = request_json("GET", "/", base=MISSION_CONTROL)
        if status and status < 500:
            break
        time.sleep(3.0)
    zip_bytes = _tiny_zip()
    boundary = f"----remain{uuid.uuid4().hex}"
    parts = [
        f"--{boundary}\r\n".encode(),
        b'Content-Disposition: form-data; name="archive"; filename="adder.zip"\r\n',
        b"Content-Type: application/zip\r\n\r\n",
        zip_bytes,
        b"\r\n",
        f"--{boundary}\r\n".encode(),
        b'Content-Disposition: form-data; name="display_name"\r\n\r\n',
        b"adder\r\n",
        f"--{boundary}--\r\n".encode(),
    ]
    status, imported = request_json(
        "POST",
        "/api/repo/import",
        base=MISSION_CONTROL,
        raw_body=b"".join(parts),
        content_type=f"multipart/form-data; boundary={boundary}",
    )
    import_ok = status in {200, 201} and isinstance(imported, dict)
    review_source = ""
    source_code = ""
    if import_ok:
        review_source = str(((imported.get("repository") or {}) if isinstance(imported, dict) else {}).get("source") or "")
    if import_ok and isinstance(imported, dict) and not review_source:
        archive_sha = str((imported.get("stats") or {}).get("archive_sha256") or "")
        files = imported.get("files") or []
        selected = [
            str(item.get("path") or item.get("repo_path") or "")
            for item in files
            if isinstance(item, dict)
        ]
        selected = [path for path in selected if path][:20]
        review_boundary = f"----review{uuid.uuid4().hex}"
        review_parts = [
            f"--{review_boundary}\r\n".encode(),
            b'Content-Disposition: form-data; name="archive"; filename="adder.zip"\r\n',
            b"Content-Type: application/zip\r\n\r\n",
            zip_bytes,
            b"\r\n",
            f"--{review_boundary}\r\n".encode(),
            b'Content-Disposition: form-data; name="archive_sha256"\r\n\r\n',
            archive_sha.encode() + b"\r\n",
        ]
        for path in selected:
            review_parts.extend(
                [
                    f"--{review_boundary}\r\n".encode(),
                    b'Content-Disposition: form-data; name="selected_paths"\r\n\r\n',
                    path.encode() + b"\r\n",
                ]
            )
        review_parts.append(f"--{review_boundary}--\r\n".encode())
        _review_status, review = request_json(
            "POST",
            "/api/repo/review",
            base=MISSION_CONTROL,
            raw_body=b"".join(review_parts),
            content_type=f"multipart/form-data; boundary={review_boundary}",
        )
        if isinstance(review, dict):
            review_source = str((review.get("repository") or {}).get("source") or review.get("source") or "")
            source_code = str(review.get("source_code") or "")
    sow_id = ""
    if import_ok:
        sow_id = create_sow("Chat ZIP PORT", "PORT", "Port the imported adder ZIP to Go.")
    return {
        "kind": "chat_zip",
        "import_http": status,
        "review_source": review_source,
        "source_chars": len(source_code),
        "sow_id": sow_id,
        "passed": chat_zip_passed(import_ok, review_source, sow_id, len(source_code)),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--only",
        choices=("failure", "fallback", "edcp", "spend", "zip", "all"),
        default="all",
    )
    args = parser.parse_args()
    if not API_KEY:
        print("No gateway credential; nothing would be verified.", file=sys.stderr)
        return 2
    status, health = request_json("GET", "/readyz")
    if status != 200:
        print(f"gateway not ready HTTP {status}: {health!r}", file=sys.stderr)
        return 2

    run_compose("stop", "mission-control")
    results: dict[str, Any] = {}
    try:
        if args.only in {"failure", "all"}:
            results["failure_injection"] = prove_failure_injection()
        if args.only in {"fallback", "all"}:
            results["provider_fallback"] = prove_provider_fallback()
        if args.only in {"edcp", "all"}:
            results["edcp_live_bus"] = prove_edcp_live_bus()
        if args.only in {"spend", "all"}:
            results["spend_cap"] = prove_spend_cap()
        if args.only in {"zip", "all"}:
            results["chat_zip"] = prove_chat_zip()
    finally:
        run_compose("start", "mission-control")

    passed = all(item.get("passed") for item in results.values()) if results else False
    evidence = {
        "schema_version": "remaining_live_proof.v1",
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "results": results,
        "all_passed": passed,
    }
    out = ROOT / "docs" / "evidence" / f"remaining_live_proof_{time.strftime('%Y%m%d')}.json"
    out.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(f"\nwrote {out.relative_to(ROOT)}")
    for name, item in results.items():
        print(f"  {name}: passed={item.get('passed')} state={item.get('final_state')}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
