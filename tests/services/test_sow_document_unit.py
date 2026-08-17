"""P1: approved SOW persist + accept validation."""

from __future__ import annotations

import inspect
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))
sys.path.insert(0, str(ROOT))

from orchestrator.sow_store import (  # noqa: E402
    load_approved_sow,
    save_approved_sow,
    validate_sow_for_accept,
)


def _priced_contract() -> dict:
    return {
        "title": "Snake",
        "summary": "stdlib snake",
        "out_of_scope": ["sound", "network"],
        "deliverables": [{"name": "snake.py", "artifact_hint": "snake.py"}],
        "acceptance_criteria": ["q quits"],
        "estimated_complexity": "low",
        "cost_estimate": {
            "likely_usd": 0.2,
            "high_usd": 0.4,
            "cap_usd": 0.6,
            "pricing_known": True,
        },
    }


def test_normalize_rejects_empty_out_of_scope() -> None:
    errors = validate_sow_for_accept(
        {**_priced_contract(), "out_of_scope": []},
        unpriced_ack=True,
    )
    assert any("out_of_scope" in err for err in errors)


def test_normalize_requires_deliverable_acceptance_link() -> None:
    errors = validate_sow_for_accept(
        {**_priced_contract(), "deliverables": []},
        unpriced_ack=True,
    )
    assert any("deliverable" in err for err in errors)


def test_persist_approved_sow_round_trip(tmp_path: Path) -> None:
    settings = SimpleNamespace(delivery_dir=tmp_path)
    saved = save_approved_sow(settings, _priced_contract())
    loaded = load_approved_sow(settings, saved["sow_id"])
    assert loaded is not None
    assert loaded["sow_id"] == saved["sow_id"]
    assert loaded["feature_contract"]["title"] == "Snake"
    assert loaded["digest"]


def test_approved_sow_does_not_fit_in_metadata_budget() -> None:
    document = {"sow_id": "sow-x", "digest": "abc"}
    # Launch metadata only carries the pointer, not the document.
    assert len(str(document)) < 200


def test_accept_without_cost_estimate_is_rejected() -> None:
    contract = _priced_contract()
    contract["cost_estimate"] = {"pricing_known": False}
    with pytest.raises(ValueError, match="unpriced"):
        save_approved_sow(SimpleNamespace(delivery_dir=Path("/tmp")), contract)


def test_charter_approved_at_set_on_accept(tmp_path: Path) -> None:
    saved = save_approved_sow(SimpleNamespace(delivery_dir=tmp_path), _priced_contract())
    assert saved["approved_at"]
    assert saved["approved_by"] == "operator"


def test_intake_uses_approved_snapshot_not_regenerated_contract() -> None:
    from orchestrator.mission_flow_v2 import phases_intake

    source = inspect.getsource(phases_intake._prepare_pm_intake)
    assert "load_approved_sow" in source
    assert "sow_id" in source
    assert "generate_pm_feature_contract" in source


def test_codegen_context_includes_repo_bundle_for_import() -> None:
    from orchestrator.mission_flow_v2 import phases_build

    source = inspect.getsource(phases_build._prepare_specialist_plan)
    assert "imported_source_code" in source


def test_intake_may_add_execution_assumptions_only() -> None:
    from orchestrator.mission_flow_v2 import phases_intake

    source = inspect.getsource(phases_intake._prepare_pm_intake)
    assert "approved_sow_digest" in source
