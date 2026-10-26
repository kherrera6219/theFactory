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


def _mock_conn_with_cursor(fetchone_val=None, fetchall_val=None, rowcount=0):
    from contextlib import contextmanager
    from unittest.mock import MagicMock

    cur = MagicMock()
    cur.fetchone.return_value = fetchone_val
    cur.fetchall.return_value = fetchall_val if fetchall_val is not None else []
    cur.rowcount = rowcount

    conn = MagicMock()

    @contextmanager
    def _cursor_cm():
        yield cur

    conn.cursor.side_effect = _cursor_cm

    @contextmanager
    def _conn_cm():
        yield conn

    return _conn_cm, cur


def test_storage_projects_crud_and_bus():
    from datetime import UTC, datetime

    from orchestrator import storage_projects

    settings = SimpleNamespace()
    now = datetime.now(UTC)

    proj_row = (
        "project-alpha",
        "Alpha",
        "user",
        "active",
        {"owner": "pm"},
        {"env": "dev"},
        now,
        now,
    )
    conn_cm, _ = _mock_conn_with_cursor(fetchone_val=proj_row)
    with patch("orchestrator.storage_projects.get_connection", side_effect=conn_cm):
        res = storage_projects.upsert_project(
            settings,
            project_id="Alpha",
            project_name="Alpha",
            source="user",
            status="active",
            plan_authority={"owner": "pm"},
            metadata={"env": "dev"},
        )
        assert res["project_id"] == "project-alpha"
        assert res["project_name"] == "Alpha"
        assert res["plan_authority"] == {"owner": "pm"}

        fetched = storage_projects.fetch_project(settings, "Alpha")
        assert fetched is not None
        assert fetched["project_id"] == "project-alpha"

    conn_none, _ = _mock_conn_with_cursor(fetchone_val=None)
    with patch("orchestrator.storage_projects.get_connection", side_effect=conn_none):
        assert storage_projects.fetch_project(settings, "missing") is None
        assert storage_projects.fetch_project_handoff(settings, "missing") is None

    handoff_row = (
        "project-alpha",
        "smelt",
        "compile",
        ["b1"],
        "mission-1",
        2,
        "summary",
        {"lead": "ceo"},
        ["ref-1"],
        now,
    )
    conn_hand, _ = _mock_conn_with_cursor(fetchone_val=handoff_row)
    with patch("orchestrator.storage_projects.get_connection", side_effect=conn_hand):
        h = storage_projects.upsert_project_handoff(
            settings,
            project_id="Alpha",
            current_phase="smelt",
            next_action="compile",
            blockers=["b1"],
            last_mission_id="mission-1",
            plan_revision=2,
            plan_summary="summary",
            authority={"lead": "ceo"},
            evidence_refs=["ref-1"],
        )
        assert h["current_phase"] == "smelt"
        assert h["plan_revision"] == 2
        h2 = storage_projects.fetch_project_handoff(settings, "Alpha")
        assert h2 is not None
        assert h2["last_mission_id"] == "mission-1"

    wi_row = (
        "wi-123",
        "project-alpha",
        "Build API",
        "open",
        "mission",
        "mission-1",
        1,
        "ev-1",
        {"k": "v"},
        now,
        now,
    )
    conn_wi, _ = _mock_conn_with_cursor(
        fetchone_val=wi_row, fetchall_val=[wi_row], rowcount=3
    )
    with patch("orchestrator.storage_projects.get_connection", side_effect=conn_wi):
        wi = storage_projects.upsert_work_item(
            settings,
            project_id="Alpha",
            title="Build API",
            work_item_id="wi-123",
            status="open",
            source="mission",
            mission_id="mission-1",
            sort_order=1,
            evidence_ref="ev-1",
            metadata={"k": "v"},
        )
        assert wi["work_item_id"] == "wi-123"

        items_filtered = storage_projects.list_work_items(
            settings, "Alpha", status="open", limit=10
        )
        assert len(items_filtered) == 1

        items_all = storage_projects.list_work_items(
            settings, "Alpha", status=None, limit=10
        )
        assert len(items_all) == 1

        count = storage_projects.mark_work_items_done_for_mission(
            settings,
            project_id="Alpha",
            mission_id="mission-1",
            evidence_ref="ev-done",
        )
        assert count == 3

        assert (
            storage_projects.mark_work_items_done_for_mission(
                settings,
                project_id="Alpha",
                mission_id="mission-1",
                only_statuses=("invalid-status",),
            )
            == 0
        )

    with (
        patch(
            "orchestrator.storage_projects.fetch_project",
            return_value={"project_id": "project-alpha"},
        ),
        patch(
            "orchestrator.storage_projects.fetch_project_handoff",
            return_value={"current_phase": "smelt"},
        ),
        patch(
            "orchestrator.storage_projects.list_work_items",
            return_value=[
                {"work_item_id": "wi-1", "status": "open"},
                {"work_item_id": "wi-2", "status": "done"},
            ],
        ),
    ):
        bus = storage_projects.load_project_bus(settings, "Alpha")
        assert bus["project_id"] == "project-alpha"
        assert len(bus["open_work_items"]) == 1

    assert (
        storage_projects.resolve_project_id_for_mission({"project_id": "Alpha"}, "m-1")
        == "project-alpha"
    )
