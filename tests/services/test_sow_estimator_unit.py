"""P1: factory-run cost estimator — range, ledger rates, no I/O."""

from __future__ import annotations

import ast
import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))
sys.path.insert(0, str(ROOT))

from orchestrator import sow_estimator  # noqa: E402
from orchestrator.llm_cost_ledger import _estimate_cost  # noqa: E402


def test_estimate_uses_ledger_rates_for_gemini_37_flash() -> None:
    estimate = sow_estimator.estimate_mission_cost(
        mission_type="BUILD_NEW",
        complexity="medium",
        provider="gemini",
        model="gemini-3.7-flash",
    )
    assert estimate["pricing_known"] is True
    unit, known = _estimate_cost("gemini", "gemini-3.7-flash", 1000, 1000)
    assert known is True
    assert unit == 0.0045
    assert estimate["model"] == "gemini-3.7-flash"


def test_estimate_is_a_range_not_a_point() -> None:
    estimate = sow_estimator.estimate_mission_cost(complexity="medium")
    assert estimate["likely_usd"] < estimate["high_usd"] < estimate["cap_usd"]


def test_high_band_applies_2x_overhead() -> None:
    estimate = sow_estimator.estimate_mission_cost(complexity="medium")
    # reverse out scale: high / 2.0 == raw; likely / 1.7 == raw
    raw_from_high = estimate["high_usd"] / sow_estimator.HIGH_OVERHEAD
    raw_from_likely = estimate["likely_usd"] / sow_estimator.LIKELY_OVERHEAD
    assert abs(raw_from_high - raw_from_likely) < 1e-6
    assert abs(estimate["cap_usd"] - estimate["high_usd"] * sow_estimator.CAP_FACTOR) < 1e-6


def test_likely_band_applies_1_7x_overhead() -> None:
    assert sow_estimator.LIKELY_OVERHEAD == 1.7


def test_unknown_model_sets_pricing_known_false() -> None:
    estimate = sow_estimator.estimate_mission_cost(model="not-a-priced-model-xyz")
    assert estimate["pricing_known"] is False
    assert estimate["likely_usd"] is None
    assert estimate["cap_usd"] is None


def test_complexity_scales_call_graph() -> None:
    low = sow_estimator.estimate_mission_cost(complexity="low")
    high = sow_estimator.estimate_mission_cost(complexity="very_high")
    assert high["likely_usd"] > low["likely_usd"]


def test_port_engagement_includes_two_phase_calls() -> None:
    build = sow_estimator.estimate_mission_cost(mission_type="BUILD_NEW")
    port = sow_estimator.estimate_mission_cost(mission_type="PORT")
    assert port["likely_usd"] > build["likely_usd"]
    assert len(sow_estimator._call_graph_for("PORT")) > len(
        sow_estimator._call_graph_for("BUILD_NEW")
    )


def test_estimator_is_pure_no_io() -> None:
    source = inspect.getsource(sow_estimator.estimate_mission_cost)
    tree = ast.parse(source)
    forbidden = {"open", "urlopen", "httpx", "docker", "getenv", "Path"}
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert names.isdisjoint(forbidden)


def test_basis_records_model_and_rate_date() -> None:
    estimate = sow_estimator.estimate_mission_cost(model="gemini-3.7-flash")
    assert "gemini-3.7-flash" in estimate["basis"]
    assert estimate["pricing_as_of"]
