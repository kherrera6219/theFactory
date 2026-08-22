"""Unit tests for project continuity bus helpers (no live Postgres)."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
ORCH = ROOT / "services" / "orchestrator"
if str(ORCH) not in sys.path:
    sys.path.insert(0, str(ORCH))


def test_normalize_and_resolve_project_id():
    from orchestrator.project_identity import normalize_project_id, resolve_project_id

    assert normalize_project_id("My App") == "project-my-app"
    assert resolve_project_id({"project_id": "project-foo"}) == "project-foo"
    assert resolve_project_id({}, mission_id="mission-abc").startswith("project-")


def test_ensure_project_bus_bootstraps_new_project():
    from orchestrator import project_bus

    settings = SimpleNamespace()
    feature_contract = {
        "title": "Add login",
        "acceptance_criteria": ["User can log in", "Session expires"],
    }

    with (
        patch("orchestrator.storage_projects.fetch_project", return_value=None),
        patch("orchestrator.storage_projects.upsert_project") as up_proj,
        patch("orchestrator.storage_projects.upsert_project_handoff") as up_hand,
        patch("orchestrator.storage_projects.upsert_work_item") as up_wi,
        patch(
            "orchestrator.storage_projects.load_project_bus",
            return_value={
                "handoff": {"plan_revision": 0, "next_action": "pm_intake"},
                "open_work_items": [
                    {
                        "work_item_id": "wi-1",
                        "title": "User can log in",
                        "status": "in_progress",
                    }
                ],
            },
        ),
    ):
        meta = project_bus.ensure_project_bus_for_mission(
            settings,
            mission_id="mission-1",
            metadata={"source": "demo-app"},
            feature_contract=feature_contract,
        )

    assert meta["project_id"] == "project-demo-app"
    assert meta["project_bus"]["open_work_item_count"] == 1
    assert up_proj.called
    assert up_hand.called
    assert up_wi.call_count >= 2


def test_finalize_marks_done_only_on_complete():
    from orchestrator import project_bus

    settings = SimpleNamespace()
    with (
        patch(
            "orchestrator.storage_projects.mark_work_items_done_for_mission", return_value=2
        ) as mark,
        patch("orchestrator.storage_projects.upsert_project_handoff") as up_hand,
        patch("orchestrator.storage_projects.upsert_project"),
        patch(
            "orchestrator.storage_projects.load_project_bus",
            return_value={
                "handoff": {"current_phase": "delivered"},
                "open_work_items": [],
            },
        ),
    ):
        meta = project_bus.finalize_project_bus_for_mission(
            settings,
            mission_id="mission-1",
            metadata={
                "project_id": "project-demo-app",
                "delivery_summary": {"delivery_title": "Done"},
            },
            outcome="complete",
        )

    assert mark.called
    assert meta["project_bus"]["finalized_outcome"] == "complete"
    assert up_hand.called


def test_finalize_blocked_does_not_mark_done():
    from orchestrator import project_bus

    settings = SimpleNamespace()
    with (
        patch("orchestrator.storage_projects.mark_work_items_done_for_mission") as mark,
        patch("orchestrator.storage_projects.upsert_project_handoff") as up_hand,
        patch("orchestrator.storage_projects.upsert_project"),
        patch(
            "orchestrator.storage_projects.load_project_bus",
            return_value={"handoff": {}, "open_work_items": [{"status": "open"}]},
        ),
    ):
        project_bus.finalize_project_bus_for_mission(
            settings,
            mission_id="mission-2",
            metadata={"project_id": "project-x", "block_reason": "qc failed"},
            outcome="blocked",
        )

    mark.assert_not_called()
    assert up_hand.called
