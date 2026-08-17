"""P3: spend-cap pause vs warn."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))
sys.path.insert(0, str(ROOT))

from orchestrator.sow_store import check_mission_spend_cap  # noqa: E402


def test_spend_below_warn_threshold_does_not_pause() -> None:
    assert check_mission_spend_cap(actual_usd=0.2, cap_usd=1.0) == "ok"


def test_spend_at_cap_pauses_mission() -> None:
    assert check_mission_spend_cap(actual_usd=1.0, cap_usd=1.0) == "pause"


def test_spend_near_cap_warns() -> None:
    assert check_mission_spend_cap(actual_usd=0.85, cap_usd=1.0) == "warn"


def test_missing_numbers_are_ok() -> None:
    assert check_mission_spend_cap(actual_usd=None, cap_usd=1.0) == "ok"
    assert check_mission_spend_cap(actual_usd=1.0, cap_usd=None) == "ok"
