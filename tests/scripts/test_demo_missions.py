"""Regression tests for Phase 18 demo mission harness."""

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "demo_missions.py"

spec = importlib.util.spec_from_file_location("demo_missions", MODULE_PATH)
assert spec is not None and spec.loader is not None
demo_missions = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = demo_missions
spec.loader.exec_module(demo_missions)


def test_build_demo_missions_covers_required_modes() -> None:
    demos = demo_missions.build_demo_missions()
    passed, failures = demo_missions.validate_demo_specs(demos)

    assert passed is True
    assert failures == []
    mission_types = {
        demo["payload"]["metadata"]["mission_type"]
        for demo in demos
    }
    assert {"BUILD_NEW", "ANALYZE_ONLY", "IMPORT_MODERNIZE"} <= mission_types
    assert any(
        demo["payload"]["metadata"].get("secondary_mission_type") == "DEBUG_REPAIR"
        for demo in demos
    )


def test_validate_demo_specs_rejects_missing_source_for_analysis() -> None:
    demos = demo_missions.build_demo_missions()
    demos[1]["payload"].pop("source_code")

    passed, failures = demo_missions.validate_demo_specs(demos)

    assert passed is False
    assert any("source_code required" in reason for reason in failures)


def test_run_dry_writes_passed_manifest_shape() -> None:
    report = demo_missions.run_dry(demo_missions.build_demo_missions())

    assert report["schema_version"] == "phase18_demo_missions.v1"
    assert report["run_mode"] == "dry"
    assert report["passed"] is True
    assert len(report["demos"]) == 3


def test_run_live_submits_each_demo_and_evaluates_chain(monkeypatch) -> None:
    created_missions: list[str] = []

    def fake_request_json(method: str, url: str, **kwargs):  # type: ignore[no-untyped-def]
        if method == "GET" and url.endswith("/readyz"):
            return 200, {"ready": True}
        if method == "POST" and url.endswith("/v1/missions"):
            mission_id = f"mission-{len(created_missions) + 1}"
            created_missions.append(mission_id)
            return 201, {"mission_id": mission_id}
        if method == "GET" and url.endswith("/chain-trace"):
            return 200, {
                "events": [
                    {"event_type": "MISSION_PM_INTAKE"},
                    {"event_type": "MISSION_CEO_DELEGATED"},
                    {"event_type": "MISSION_POD_MANAGER_ASSIGNED"},
                    {"event_type": "MISSION_SPECIALIST_ASSIGNED"},
                ]
            }
        if method == "GET" and "logicnodes" in url:
            return 200, [{"node_id": "n-1"}]
        if method == "GET" and "build-artifacts" in url:
            return 200, [{"artifact_id": "a-1"}]
        raise AssertionError(f"unexpected request {method} {url}")

    monkeypatch.setattr(demo_missions, "_request_json", fake_request_json)
    monkeypatch.setattr(
        demo_missions,
        "_wait_for_terminal_state",
        lambda **kwargs: ("COMPLETE", {"state": "COMPLETE"}),
    )

    args = SimpleNamespace(
        gateway_base_url="http://localhost:8100",
        timeout_seconds=1.0,
        mission_timeout_seconds=1.0,
        poll_seconds=0.01,
        required_chain_events=list(demo_missions.DEFAULT_REQUIRED_CHAIN_EVENTS),
    )
    report = demo_missions.run_live(args, demo_missions.build_demo_missions())

    assert report["passed"] is True
    assert len(created_missions) == 3
    assert all(result["passed"] for result in report["demos"])
