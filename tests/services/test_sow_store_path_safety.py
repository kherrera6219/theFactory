"""Path-containment tests for approved SOW snapshots."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
ORCH = ROOT / "services" / "orchestrator"
if str(ORCH) not in sys.path:
    sys.path.insert(0, str(ORCH))


def test_load_approved_sow_rejects_traversal(tmp_path: Path) -> None:
    from orchestrator.sow_store import load_approved_sow, save_approved_sow

    settings = SimpleNamespace(delivery_dir=str(tmp_path))
    document = save_approved_sow(
        settings,
        {
            "out_of_scope": ["no extra infra"],
            "deliverables": ["login"],
            "cost_estimate": {"pricing_known": True},
        },
    )
    loaded = load_approved_sow(settings, document["sow_id"])
    assert loaded is not None
    assert loaded["sow_id"] == document["sow_id"]

    assert load_approved_sow(settings, "../etc/passwd") is None
    assert load_approved_sow(settings, document["sow_id"] + "/../secret") is None
    assert load_approved_sow(settings, "sow-missing") is None
