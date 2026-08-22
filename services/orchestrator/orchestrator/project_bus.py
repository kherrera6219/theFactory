"""project_bus.py — Runtime continuity bus for multi-mission projects.

Mirrors the operator discipline (handoff + work ledger + plan authority) so
agents resume project state when a user keeps adding work to the same project.
"""
from __future__ import annotations

import logging
from typing import Any

from .project_identity import resolve_project_id, with_project_identity
from .settings import Settings

LOGGER = logging.getLogger(__name__)


def ensure_project_bus_for_mission(
    settings: Settings,
    *,
    mission_id: str,
    metadata: dict[str, Any],
    feature_contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Bootstrap or load the project bus and attach a snapshot to mission metadata.

    Safe to call multiple times. Does not invent "done" — only seeds open items
    from acceptance criteria when the project has no work items yet.
    """
    from . import storage_projects as sp

    meta = with_project_identity(dict(metadata or {}), mission_id=mission_id)
    project_id = resolve_project_id(meta, mission_id=mission_id)
    project_name = str(meta.get("project_name") or meta.get("source") or project_id)
    source = str(meta.get("source") or "").strip() or None

    try:
        existing = sp.fetch_project(settings, project_id)
        if existing is None:
            sp.upsert_project(
                settings,
                project_id=project_id,
                project_name=project_name,
                source=source,
                status="active",
                metadata={"bootstrapped_by_mission": mission_id},
            )
            sp.upsert_project_handoff(
                settings,
                project_id=project_id,
                current_phase="intake",
                next_action="pm_intake",
                last_mission_id=mission_id,
                plan_revision=0,
                plan_summary=None,
                authority={},
                blockers=[],
                evidence_refs=[],
            )
            _seed_work_items_from_contract(
                settings,
                project_id=project_id,
                mission_id=mission_id,
                feature_contract=feature_contract,
            )
        else:
            sp.upsert_project(
                settings,
                project_id=project_id,
                project_name=project_name,
                source=source or existing.get("source"),
                status="active",
            )
            handoff = sp.fetch_project_handoff(settings, project_id)
            if handoff is None:
                sp.upsert_project_handoff(
                    settings,
                    project_id=project_id,
                    current_phase="intake",
                    next_action="pm_intake",
                    last_mission_id=mission_id,
                )
            else:
                open_items = sp.list_work_items(settings, project_id, status="open", limit=50)
                for item in open_items:
                    if not item.get("mission_id"):
                        sp.upsert_work_item(
                            settings,
                            project_id=project_id,
                            work_item_id=item["work_item_id"],
                            title=item["title"],
                            status="in_progress",
                            source=item.get("source") or "mission",
                            mission_id=mission_id,
                            sort_order=int(item.get("sort_order") or 0),
                            metadata={"claimed_by_mission": mission_id},
                        )
                all_items = sp.list_work_items(settings, project_id, limit=5)
                if not all_items and isinstance(feature_contract, dict):
                    _seed_work_items_from_contract(
                        settings,
                        project_id=project_id,
                        mission_id=mission_id,
                        feature_contract=feature_contract,
                    )

            if isinstance(feature_contract, dict) and feature_contract:
                title = str(feature_contract.get("title") or "").strip()
                criteria = feature_contract.get("acceptance_criteria") or []
                plan_authority = {
                    "feature_contract_title": title,
                    "acceptance_criteria_count": len(criteria)
                    if isinstance(criteria, list)
                    else 0,
                    "mission_id": mission_id,
                }
                sp.upsert_project(
                    settings,
                    project_id=project_id,
                    project_name=project_name,
                    plan_authority=plan_authority,
                )
                prev = sp.fetch_project_handoff(settings, project_id) or {}
                rev = int(prev.get("plan_revision") or 0) + (0 if existing is None else 1)
                sp.upsert_project_handoff(
                    settings,
                    project_id=project_id,
                    current_phase="pm_intake",
                    next_action="build",
                    last_mission_id=mission_id,
                    plan_revision=rev if existing is not None else 0,
                    plan_summary=title or prev.get("plan_summary"),
                    authority=plan_authority,
                    blockers=list(prev.get("blockers") or []),
                    evidence_refs=list(prev.get("evidence_refs") or []),
                )

        bus = sp.load_project_bus(settings, project_id)
        meta["project_id"] = project_id
        meta["project_bus"] = {
            "project_id": project_id,
            "handoff": bus.get("handoff"),
            "open_work_item_count": len(bus.get("open_work_items") or []),
            "open_work_items": [
                {
                    "work_item_id": i.get("work_item_id"),
                    "title": i.get("title"),
                    "status": i.get("status"),
                }
                for i in (bus.get("open_work_items") or [])[:20]
            ],
            "plan_revision": (bus.get("handoff") or {}).get("plan_revision"),
        }
        return meta
    except Exception as exc:  # noqa: BLE001 — bus must not fail the mission
        LOGGER.warning(
            "project_bus ensure failed for mission %s project %s: %s",
            mission_id,
            project_id,
            exc,
        )
        meta["project_id"] = project_id
        meta["project_bus_error"] = type(exc).__name__
        return meta


def finalize_project_bus_for_mission(
    settings: Settings,
    *,
    mission_id: str,
    metadata: dict[str, Any],
    outcome: str = "complete",
    evidence_ref: str | None = None,
) -> dict[str, Any]:
    """Update handoff and ledger after delivery / complete / block.

    Work items are marked done only when outcome is complete.
    """
    from . import storage_projects as sp

    meta = dict(metadata or {})
    project_id = resolve_project_id(meta, mission_id=mission_id)
    outcome_norm = str(outcome or "complete").strip().lower()
    delivery = meta.get("delivery_summary") if isinstance(meta.get("delivery_summary"), dict) else {}
    evidence = evidence_ref or (
        f"mission:{mission_id}:delivery" if delivery else f"mission:{mission_id}:{outcome_norm}"
    )

    try:
        if outcome_norm in {"complete", "delivered", "success"}:
            sp.mark_work_items_done_for_mission(
                settings,
                project_id=project_id,
                mission_id=mission_id,
                evidence_ref=evidence,
            )
            sp.upsert_project_handoff(
                settings,
                project_id=project_id,
                current_phase="delivered",
                next_action="await_follow_on",
                last_mission_id=mission_id,
                plan_summary=str(
                    delivery.get("delivery_title")
                    or (meta.get("feature_contract") or {}).get("title")
                    or ""
                )
                or None,
                authority={"last_outcome": "complete", "mission_id": mission_id},
                blockers=[],
                evidence_refs=[evidence],
            )
            sp.upsert_project(settings, project_id=project_id, status="active")
        elif outcome_norm in {"blocked", "failed", "clarifying"}:
            blockers = [
                {
                    "mission_id": mission_id,
                    "outcome": outcome_norm,
                    "reason": str(
                        meta.get("block_reason") or meta.get("failure_reason") or outcome_norm
                    ),
                }
            ]
            sp.upsert_project_handoff(
                settings,
                project_id=project_id,
                current_phase=outcome_norm,
                next_action="operator_review",
                last_mission_id=mission_id,
                blockers=blockers,
                evidence_refs=[evidence],
                authority={"last_outcome": outcome_norm, "mission_id": mission_id},
            )
            if outcome_norm == "failed":
                sp.upsert_project(settings, project_id=project_id, status="paused")
        else:
            sp.upsert_project_handoff(
                settings,
                project_id=project_id,
                current_phase=outcome_norm,
                next_action="continue",
                last_mission_id=mission_id,
                evidence_refs=[evidence],
            )

        bus = sp.load_project_bus(settings, project_id)
        meta["project_bus"] = {
            "project_id": project_id,
            "handoff": bus.get("handoff"),
            "open_work_item_count": len(bus.get("open_work_items") or []),
            "finalized_outcome": outcome_norm,
        }
        return meta
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning(
            "project_bus finalize failed for mission %s project %s: %s",
            mission_id,
            project_id,
            exc,
        )
        meta["project_bus_finalize_error"] = type(exc).__name__
        return meta


def _seed_work_items_from_contract(
    settings: Settings,
    *,
    project_id: str,
    mission_id: str,
    feature_contract: dict[str, Any] | None,
) -> None:
    from . import storage_projects as sp

    if not isinstance(feature_contract, dict):
        return
    criteria = feature_contract.get("acceptance_criteria") or []
    if not isinstance(criteria, list) or not criteria:
        title = str(feature_contract.get("title") or "").strip()
        if title:
            criteria = [title]
        else:
            return
    for idx, item in enumerate(criteria[:40]):
        title = (
            str(item).strip()
            if not isinstance(item, dict)
            else str(item.get("text") or item.get("title") or item.get("criterion") or "").strip()
        )
        if not title:
            continue
        sp.upsert_work_item(
            settings,
            project_id=project_id,
            title=title[:500],
            status="in_progress",
            source="acceptance_criteria",
            mission_id=mission_id,
            sort_order=idx,
            metadata={"seeded_from": "feature_contract"},
        )
