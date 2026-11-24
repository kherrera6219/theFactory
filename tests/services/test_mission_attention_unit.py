"""Shared "internal mission" / "completion blocked" rules and the alert built on them."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

importlib.import_module("orchestrator.main")  # resolves the routes import cycle
attention = importlib.import_module("orchestrator.mission_attention")
operations = importlib.import_module("orchestrator.routes.operations")

_BLOCKED = {"last_chain_event_type": "MISSION_COMPLETION_BLOCKED"}


def test_system_missions_are_recognised() -> None:
    assert attention.is_system_mission("__knowledge_lake__")
    assert attention.is_system_mission("system-knowledge-lake")
    assert not attention.is_system_mission("mission-123")
    assert not attention.is_system_mission(None)


def test_completion_blocked_only_while_not_terminal() -> None:
    assert attention.is_completion_blocked("VERIFIED", _BLOCKED)
    assert not attention.is_completion_blocked("COMPLETE", _BLOCKED)
    assert not attention.is_completion_blocked("FAILED", _BLOCKED)
    assert not attention.is_completion_blocked("VERIFIED", {"last_chain_event_type": "MISSION_DELIVERED"})
    assert not attention.is_completion_blocked("VERIFIED", None)


def _alerts(**kwargs):
    base = dict(
        redis_ready=True,
        db_ready=True,
        protocol_ready=True,
        consumer_running=True,
        state_counts={},
        blocked_completion_count=0,
        limit=50,
    )
    base.update(kwargs)
    return operations._build_operational_alerts(**base)


def test_blocked_alert_names_missions_and_keeps_its_first_seen_time() -> None:
    alerts = _alerts(
        blocked_completion_count=5,
        blocked_mission_ids=["mission-a", "mission-b"],
        blocked_since="2026-11-24T03:03:55+00:00",
    )
    (alert,) = [a for a in alerts if a["alert_id"] == "missions-completion-blocked"]
    assert alert["mission_ids"] == ["mission-a", "mission-b"]
    assert alert["title"] == "2 missions are blocked before completion"
    assert alert["created_at"] == "2026-11-24T03:03:55+00:00"


def test_blocked_alert_clears_when_no_mission_is_still_blocked() -> None:
    # Old block events in the recent window must not keep the alert open.
    alerts = _alerts(blocked_completion_count=7, blocked_mission_ids=[])
    assert not [a for a in alerts if a["alert_id"] == "missions-completion-blocked"]
