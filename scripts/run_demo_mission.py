#!/usr/bin/env python3
"""
run_demo_mission.py — theFactory end-to-end demo mission validator

Usage (from repo root after `make up`):
    python scripts/run_demo_mission.py
    python scripts/run_demo_mission.py --prompt "Build a Python HTTP health-check server"
    python scripts/run_demo_mission.py --language javascript --timeout 300
    python scripts/run_demo_mission.py --dry-run   # validate connectivity only

Exit codes:
    0 — mission reached COMPLETE with generated output
    1 — mission failed or timed out
    2 — connectivity / config error (stack not up, API key missing)
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from datetime import UTC, datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

API_BASE = "http://localhost:8100"

DEMO_PROMPTS = {
    "python": (
        "Build a Python function called `fetch_weather(city: str) -> dict` that calls "
        "the Open-Meteo free API (no key required) for the given city's current "
        "temperature and wind speed. Return a dict with keys: city, temperature_c, "
        "wind_speed_kmh, fetched_at (ISO timestamp). Include docstring and type hints."
    ),
    "javascript": (
        "Build a JavaScript/Node.js module that exports a function `slugify(text)` "
        "which converts a string to a URL-safe slug: lowercase, spaces to hyphens, "
        "strip non-alphanumeric characters. Include JSDoc and at least 3 usage examples."
    ),
    "typescript": (
        "Build a TypeScript utility module that exports `parseEnv<T>(schema: Record<string, "
        "'string'|'number'|'boolean'>) => T` which reads process.env, validates and coerces "
        "values according to the schema, and throws a descriptive error listing all missing "
        "or invalid keys. Include full type annotations."
    ),
}

POLL_INTERVAL = 3       # seconds between state polls
TERMINAL_STATES = {"COMPLETE", "FAILED"}
SUCCESS_STATE = "COMPLETE"

# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _request(
    method: str,
    path: str,
    *,
    body: dict | None = None,
    api_key: str,
    timeout: float = 15.0,
) -> tuple[int, Any]:
    url = f"{API_BASE}{path}"
    data = json.dumps(body, separators=(",", ":")).encode() if body is not None else None
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-API-Key": api_key,
    }
    req = Request(url, data=data, method=method, headers=headers)
    try:
        with urlopen(req, timeout=timeout) as resp:  # nosec B310
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else {}
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(raw)
        except Exception:
            return exc.code, {"error": raw[:200]}
    except URLError as exc:
        return 0, {"error": str(exc)}


def _get(path: str, *, api_key: str, timeout: float = 10.0) -> tuple[int, Any]:
    return _request("GET", path, api_key=api_key, timeout=timeout)


def _post(path: str, body: dict, *, api_key: str, timeout: float = 30.0) -> tuple[int, Any]:
    return _request("POST", path, body=body, api_key=api_key, timeout=timeout)


# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------

def check_connectivity(api_key: str) -> list[str]:
    """Return list of failing checks. Empty list = all good."""
    failures: list[str] = []

    for name, path in [
        ("api-gateway /readyz", "/readyz"),
        ("orchestrator (via gateway) /health", "/health"),
    ]:
        status, body = _get(path, api_key=api_key)
        if status == 0:
            failures.append(f"{name}: UNREACHABLE — is the stack running? (`make up`)")
        elif status >= 400:
            failures.append(f"{name}: HTTP {status} — {body}")

    if not failures:
        # Check LLM provider is not offline
        status, body = _get("/health", api_key=api_key)
        if isinstance(body, dict):
            llm = body.get("llm_provider", "offline")
            if llm == "offline":
                failures.append(
                    "LLM provider is 'offline' — set OPENAI_API_KEY or ANTHROPIC_API_KEY in .env "
                    "and restart: `make down && make up`"
                )

    return failures


# ---------------------------------------------------------------------------
# Mission lifecycle
# ---------------------------------------------------------------------------

def submit_mission(
    prompt: str,
    language: str,
    api_key: str,
) -> str | None:
    mission_id = f"demo-{uuid.uuid4().hex[:12]}"
    payload = {
        "mission_id": mission_id,
        "prompt": prompt,
        "requested_target_language": language,
        "mission_type": "BUILD_NEW",
        "depth_mode": "STANDARD",
        "output_mode": "FULL_BUILD",
        "data_classification": "TIER_0_PUBLIC",
        "created_at": datetime.now(UTC).isoformat(),
    }
    status, body = _post("/v1/missions", payload, api_key=api_key)
    if status in (200, 201):
        print(f"  ✅ Mission submitted: {mission_id}")
        return mission_id
    print(f"  ❌ Submission failed: HTTP {status} — {body}")
    return None


def poll_mission(
    mission_id: str,
    api_key: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    """Poll until terminal state or timeout. Returns final mission record."""
    deadline = time.monotonic() + timeout_seconds
    last_state = ""
    spinner = ["|", "/", "-", "\\"]
    tick = 0

    while time.monotonic() < deadline:
        status, body = _get(f"/v1/missions/{mission_id}", api_key=api_key)
        if status == 0:
            print("\r  ⚠ gateway unreachable, retrying...", end="", flush=True)
            time.sleep(POLL_INTERVAL)
            continue

        if not isinstance(body, dict):
            time.sleep(POLL_INTERVAL)
            continue

        state = str(body.get("state", "")).upper()
        if state != last_state:
            elapsed = timeout_seconds - (deadline - time.monotonic())
            print(f"\r  [{elapsed:>5.0f}s] State: {state:<24}", flush=True)
            last_state = state

        if state in TERMINAL_STATES:
            return body

        tick += 1
        print(
            f"\r  [{timeout_seconds - (deadline - time.monotonic()):>5.0f}s] "
            f"{spinner[tick % 4]} {state:<24}",
            end="",
            flush=True,
        )
        time.sleep(POLL_INTERVAL)

    print()
    return {"state": "TIMEOUT", "mission_id": mission_id}


def fetch_chain_trace(mission_id: str, api_key: str) -> dict[str, Any]:
    status, body = _get(f"/v1/missions/{mission_id}/chain-trace", api_key=api_key)
    if status == 200 and isinstance(body, dict):
        return body
    return {}


def fetch_artifacts(mission_id: str, api_key: str) -> list[dict[str, Any]]:
    status, body = _get(f"/v1/missions/{mission_id}/artifacts", api_key=api_key)
    if status == 200 and isinstance(body, list):
        return body
    return []


# ---------------------------------------------------------------------------
# Result reporting
# ---------------------------------------------------------------------------

def print_section(title: str) -> None:
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}")


def report_result(
    mission_id: str,
    mission: dict[str, Any],
    chain_trace: dict[str, Any],
    artifacts: list[dict[str, Any]],
    elapsed: float,
) -> bool:
    state = str(mission.get("state", "UNKNOWN")).upper()
    success = state == SUCCESS_STATE

    print_section("MISSION RESULT")
    print(f"  Mission ID : {mission_id}")
    print(f"  Final state: {state}")
    print(f"  Elapsed    : {elapsed:.1f}s")
    print(f"  Result     : {'✅ PASS' if success else '❌ FAIL'}")

    # Chain trace summary
    meta = mission.get("metadata") or {}
    print_section("CHAIN TRACE SUMMARY")

    feature_contract = meta.get("feature_contract") or {}
    if feature_contract:
        print(f"  PM Feature Contract  : ✅  ({feature_contract.get('mission_type','?')})")
        crit = feature_contract.get("acceptance_criteria") or []
        print(f"  Acceptance criteria  : {len(crit)}")
    else:
        print("  PM Feature Contract  : ❌  (not produced)")

    mission_contract = meta.get("mission_contract") or {}
    if mission_contract:
        nodes = mission_contract.get("logicnode_requirements") or []
        print(f"  CEO Refined-IR Contract: ✅  ({len(nodes)} LogicNode requirements)")
    else:
        print("  CEO Refined-IR Contract: ❌  (not produced)")

    generated = meta.get("generated_output") or {}
    if generated:
        lang = generated.get("language","?")
        fname = generated.get("filename","?")
        chars = generated.get("code_length_chars", 0)
        source = generated.get("source","?")
        print(f"  Generated output     : ✅  {fname} ({lang}, {chars} chars, source={source})")

        if source == "fallback":
            print("  ⚠  Output is a FALLBACK placeholder — LLM call failed.")
            print("     Check that OPENAI_API_KEY or ANTHROPIC_API_KEY is set in .env")
    else:
        print("  Generated output     : ❌  (not produced)")

    delivery = meta.get("delivery_summary") or {}
    if delivery:
        print(f"  PM Delivery Summary  : ✅  \"{delivery.get('delivery_title','?')}\"")
        met = delivery.get("criteria_met") or []
        unmet = delivery.get("criteria_unmet") or []
        print(f"    Criteria met: {len(met)}, unmet: {len(unmet)}")
    else:
        print("  PM Delivery Summary  : ❌  (not produced)")

    fetch_result = meta.get("fetch_result") or {}
    if fetch_result:
        langs = fetch_result.get("indexed_languages") or []
        print(f"  FETCH / Knowledge    : ✅  indexed {langs}")
    else:
        print("  FETCH / Knowledge    : ❌  (not run)")

    # Artifacts
    print_section("BUILD ARTIFACTS")
    if artifacts:
        for art in artifacts[:5]:
            atype = art.get("artifact_type","?")
            astage = art.get("stage","?")
            astatus = art.get("status","?")
            digest = (art.get("digest_sha256") or "")[:12]
            print(f"  [{astatus:>8}]  {atype:<28}  stage={astage}  sha256={digest}...")
    else:
        print("  No artifacts found")

    # Generated code preview
    if generated and generated.get("source") != "fallback":
        code = str(generated.get("generated_code") or "").strip()
        if code:
            print_section("GENERATED CODE PREVIEW (first 30 lines)")
            for i, line in enumerate(code.splitlines()[:30], 1):
                print(f"  {i:3}│ {line}")
            if len(code.splitlines()) > 30:
                print(f"  ... ({len(code.splitlines()) - 30} more lines)")

    # Failure diagnosis
    if not success:
        print_section("FAILURE DIAGNOSIS")
        error = meta.get("error") or mission.get("error") or ""
        if error:
            print(f"  Error: {error}")
        if state == "TIMEOUT":
            print("  Mission timed out — the pipeline may have stalled.")
            print("  Check: docker compose logs orchestrator | tail -50")
        elif state == "FAILED":
            events = chain_trace.get("events") or []
            fail_events = [e for e in events if "FAIL" in str(e.get("event_type","")).upper()]
            for ev in fail_events[-3:]:
                print(f"  {ev.get('event_type')} — {ev.get('details',{})}")

    print()
    return success


# ---------------------------------------------------------------------------
# Evidence file
# ---------------------------------------------------------------------------

def write_evidence(
    mission_id: str,
    mission: dict[str, Any],
    artifacts: list[dict[str, Any]],
    elapsed: float,
    success: bool,
    prompt: str,
    language: str,
) -> str:
    evidence = {
        "run_at": datetime.now(UTC).isoformat(),
        "mission_id": mission_id,
        "prompt": prompt,
        "language": language,
        "elapsed_seconds": round(elapsed, 2),
        "final_state": mission.get("state"),
        "passed": success,
        "generated_output_present": bool((mission.get("metadata") or {}).get("generated_output")),
        "delivery_summary_present": bool((mission.get("metadata") or {}).get("delivery_summary")),
        "fetch_result_present": bool((mission.get("metadata") or {}).get("fetch_result")),
        "artifact_count": len(artifacts),
        "artifacts": [
            {
                "type": a.get("artifact_type"),
                "stage": a.get("stage"),
                "status": a.get("status"),
                "digest": (a.get("digest_sha256") or "")[:16],
            }
            for a in artifacts
        ],
    }
    ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    path = f"docs/evidence/demo_mission_{ts}.json"
    try:
        import os
        os.makedirs("docs/evidence", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(evidence, f, indent=2)
        return path
    except Exception as exc:
        print(f"  ⚠ Could not write evidence file: {exc}")
        return ""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    global API_BASE
    import os

    parser = argparse.ArgumentParser(description="theFactory end-to-end demo mission runner")
    parser.add_argument("--prompt", default="", help="Mission prompt (default: built-in demo)")
    parser.add_argument("--language", default="python", choices=list(DEMO_PROMPTS), help="Target language")
    parser.add_argument("--timeout", type=int, default=240, help="Poll timeout seconds (default 240)")
    parser.add_argument("--api-key", default="", help="API key (default: ORCHESTRATOR_ADMIN_API_KEY env)")
    parser.add_argument("--api-base", default="", help=f"API base URL (default: {API_BASE})")
    parser.add_argument("--dry-run", action="store_true", help="Check connectivity only, don't submit")
    args = parser.parse_args()

    if args.api_base:
        API_BASE = args.api_base.rstrip("/")

    api_key = (
        args.api_key
        or os.getenv("ORCHESTRATOR_ADMIN_API_KEY")
        or os.getenv("DEMO_API_KEY")
    )
    if not api_key:
        print(
            "ERROR: no API key found — pass --api-key, or set "
            "ORCHESTRATOR_ADMIN_API_KEY or DEMO_API_KEY. No placeholder "
            "credential is used."
        )
        return 1
    prompt = args.prompt or DEMO_PROMPTS.get(args.language, DEMO_PROMPTS["python"])

    print("=" * 60)
    print("  theFactory — End-to-End Demo Mission")
    print("=" * 60)
    print(f"  API base : {API_BASE}")
    print(f"  Language : {args.language}")
    print(f"  Timeout  : {args.timeout}s")
    print(f"  Prompt   : {prompt[:80]}{'...' if len(prompt) > 80 else ''}")
    print()

    # Pre-flight
    print_section("PRE-FLIGHT CHECKS")
    failures = check_connectivity(api_key)
    if failures:
        for f in failures:
            print(f"  ❌ {f}")
        print()
        print("  Stack startup: make tls-certs && make up")
        print("  Then set API keys in .env and restart.")
        return 2
    print("  ✅ Gateway reachable")
    print("  ✅ Orchestrator reachable")
    print("  ✅ LLM provider configured")

    if args.dry_run:
        print("\n  --dry-run: connectivity OK, skipping mission submission.")
        return 0

    # Submit
    print_section("SUBMITTING MISSION")
    t_start = time.monotonic()
    mission_id = submit_mission(prompt, args.language, api_key)
    if not mission_id:
        return 2

    # Poll
    print_section("POLLING MISSION STATE")
    mission = poll_mission(mission_id, api_key, args.timeout)
    elapsed = time.monotonic() - t_start

    # Fetch supporting data
    chain_trace = fetch_chain_trace(mission_id, api_key)
    artifacts = fetch_artifacts(mission_id, api_key)

    # Report
    success = report_result(mission_id, mission, chain_trace, artifacts, elapsed)

    # Write evidence
    ev_path = write_evidence(mission_id, mission, artifacts, elapsed, success, prompt, args.language)
    if ev_path:
        print(f"  Evidence written: {ev_path}")

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
