import asyncio
import importlib
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

llm_delegation = importlib.import_module("orchestrator.llm_delegation")


def test_extract_decision_payload_parses_json_block() -> None:
    parsed = llm_delegation._extract_decision_payload(
        (
            "text before "
            "{\"pod_manager_agent_id\":\"AGENT-12-PODA-MGR\","
            "\"specialist_agent_id\":\"AGENT-14-PYTHON\"}"
        )
    )
    assert parsed is not None
    assert parsed["pod_manager_agent_id"] == "AGENT-12-PODA-MGR"


def test_fallback_delegation_uses_language_mapping() -> None:
    recommendation = {"provider": "anthropic", "model": "claude-sonnet"}
    fallback = llm_delegation._fallback_delegation(
        requested_target_language="rust",
        mission_context={"mission_id": "mission-1"},
        recommendation=recommendation,
    )
    assert fallback["pod_manager_agent_id"] == "AGENT-18-PODB-MGR"
    assert fallback["specialist_agent_id"] == "AGENT-22-RUST"
    assert fallback["source"] == "fallback"


def test_generate_ceo_delegation_falls_back_when_provider_call_missing(monkeypatch) -> None:
    monkeypatch.setattr(
        llm_delegation,
        "_ceo_recommendation",
        lambda: {"provider": "openai", "model": "gpt"},
    )

    async def _no_result(
        _model: str,
        _prompt: str,
        *,
        call_context: str,
    ) -> dict[str, Any] | None:
        assert call_context
        return None

    monkeypatch.setattr(llm_delegation, "_call_openai", _no_result)
    result = asyncio.run(
        llm_delegation.generate_ceo_delegation(
            mission_context={"mission_id": "mission-1"},
            requested_target_language="java",
        )
    )
    assert result["source"] == "fallback"
    assert result["pod_manager_agent_id"] == "AGENT-24-PODC-MGR"


def test_generate_ceo_delegation_uses_llm_result(monkeypatch) -> None:
    monkeypatch.setattr(
        llm_delegation,
        "_ceo_recommendation",
        lambda: {"provider": "anthropic", "model": "claude-sonnet"},
    )

    async def _anthropic(
        _model: str,
        _prompt: str,
        *,
        call_context: str,
    ) -> dict[str, Any] | None:
        assert call_context
        return {
            "pod_manager_agent_id": "AGENT-30-PODD-MGR",
            "specialist_agent_id": "AGENT-34-JULIA",
            "rationale": "Math workload route.",
        }

    monkeypatch.setattr(llm_delegation, "_call_anthropic", _anthropic)
    result = asyncio.run(
        llm_delegation.generate_ceo_delegation(
            mission_context={"mission_id": "mission-2"},
            requested_target_language="julia",
        )
    )
    assert result["source"] == "llm"
    assert result["pod_manager_agent_id"] == "AGENT-30-PODD-MGR"
    assert result["specialist_agent_id"] == "AGENT-34-JULIA"


def test_generate_pod_manager_delegation_uses_llm_result(monkeypatch) -> None:
    monkeypatch.setattr(
        llm_delegation,
        "_agent_recommendation",
        lambda _agent_id: {"provider": "openai", "model": "gpt-5.2-pro"},
    )

    async def _openai(
        _model: str,
        _prompt: str,
        *,
        call_context: str,
    ) -> dict[str, Any] | None:
        assert "pod-manager delegation" in call_context
        return {
            "specialist_agent_id": "AGENT-22-RUST",
            "rationale": "Pod B specialist route.",
        }

    monkeypatch.setattr(llm_delegation, "_call_openai", _openai)
    result = asyncio.run(
        llm_delegation.generate_pod_manager_delegation(
            mission_context={"mission_id": "mission-3"},
            requested_target_language="rust",
            pod_manager_agent_id="AGENT-18-PODB-MGR",
            default_specialist_agent_id="AGENT-22-RUST",
        )
    )
    assert result["source"] == "llm"
    assert result["pod_manager_agent_id"] == "AGENT-18-PODB-MGR"
    assert result["specialist_agent_id"] == "AGENT-22-RUST"


def test_generate_specialist_plan_falls_back_when_provider_call_missing(monkeypatch) -> None:
    monkeypatch.setattr(
        llm_delegation,
        "_agent_recommendation",
        lambda _agent_id: {"provider": "gemini", "model": "gemini-3.1-pro-preview"},
    )

    async def _no_result(
        _model: str,
        _prompt: str,
        *,
        call_context: str,
    ) -> dict[str, Any] | None:
        assert "specialist planning" in call_context
        return None

    monkeypatch.setattr(llm_delegation, "_call_gemini", _no_result)
    result = asyncio.run(
        llm_delegation.generate_specialist_plan(
            mission_context={"mission_id": "mission-4", "requested_target_language": "python"},
            requested_target_language="python",
            specialist_agent_id="AGENT-14-PYTHON",
            pod_manager_agent_id="AGENT-12-PODA-MGR",
        )
    )
    assert result["source"] == "fallback"
    assert result["specialist_agent_id"] == "AGENT-14-PYTHON"
    assert len(result["deliverables"]) >= 1
