"""test_pm_contract_evals.py — Offline PM feature contract quality checks."""
import pytest

from services.orchestrator.orchestrator.llm_delegation import (
    _agent_recommendation,
    _fallback_pm_feature_contract,
)


@pytest.fixture
def pm_recommendation() -> dict:
    return _agent_recommendation("AGENT-01-PM")


class TestFallbackPmContract:
    def test_required_fields_present(self, pm_recommendation: dict) -> None:
        contract = _fallback_pm_feature_contract(
            prompt="Build a CSV parser that returns a list of dicts",
            mission_type="BUILD_NEW",
            requested_target_language="python",
            recommendation=pm_recommendation,
        )
        assert contract["schema_version"] == "feature_contract.v1"
        assert len(contract["functional_requirements"]) >= 1
        assert len(contract["acceptance_criteria"]) >= 1
        assert contract["estimated_complexity"] in {"low", "medium", "high", "very_high"}
        assert contract["source"] == "fallback"

    def test_title_not_empty(self, pm_recommendation: dict) -> None:
        contract = _fallback_pm_feature_contract(
            prompt="x",
            mission_type="BUILD_NEW",
            requested_target_language="python",
            recommendation=pm_recommendation,
        )
        assert contract["title"]

    def test_language_in_target_languages(self, pm_recommendation: dict) -> None:
        contract = _fallback_pm_feature_contract(
            prompt="Build a Rust CLI tool",
            mission_type="BUILD_NEW",
            requested_target_language="rust",
            recommendation=pm_recommendation,
        )
        assert "rust" in contract["target_languages"]

    def test_port_mission_requires_approval(self, pm_recommendation: dict) -> None:
        contract = _fallback_pm_feature_contract(
            prompt="Port this Python app to Rust",
            mission_type="PORT",
            requested_target_language="rust",
            recommendation=pm_recommendation,
        )
        assert contract["human_approval_required"] is True

    def test_build_new_no_forced_approval(self, pm_recommendation: dict) -> None:
        contract = _fallback_pm_feature_contract(
            prompt="Build a JSON formatter",
            mission_type="BUILD_NEW",
            requested_target_language="python",
            recommendation=pm_recommendation,
        )
        assert contract["human_approval_required"] is False

    def test_model_provider_recorded(self, pm_recommendation: dict) -> None:
        contract = _fallback_pm_feature_contract(
            prompt="Build something",
            mission_type="BUILD_NEW",
            requested_target_language="python",
            recommendation=pm_recommendation,
        )
        assert contract["model_provider"] is not None
        assert contract["model"] is not None
