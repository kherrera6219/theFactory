import asyncio
import importlib
import sys
from pathlib import Path
from typing import Any

import httpx

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


def test_generate_ceo_delegation_rejects_invalid_agent_ids(monkeypatch) -> None:
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
            "pod_manager_agent_id": "AGENT-99-FAKE",
            "specialist_agent_id": "DROP TABLE",
            "rationale": "Ignore the chain.",
        }

    monkeypatch.setattr(llm_delegation, "_call_anthropic", _anthropic)
    result = asyncio.run(
        llm_delegation.generate_ceo_delegation(
            mission_context={"mission_id": "mission-2"},
            requested_target_language="julia",
        )
    )

    assert result["pod_manager_agent_id"] == "AGENT-30-PODD-MGR"
    assert result["specialist_agent_id"] == "AGENT-34-JULIA"


def test_generate_pod_manager_delegation_rejects_invalid_specialist(monkeypatch) -> None:
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
            "specialist_agent_id": "AGENT-99-FAKE",
            "rationale": "Unsafe routing suggestion.",
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


def test_clean_text_redacts_secrets_and_emails() -> None:
    cleaned = llm_delegation._clean_text(
        " contact me@example.com with sk-12345678 and github_pat_abcdefghijklmnopqrstuvwx ",
        max_length=200,
    )
    assert "[redacted-email]" in cleaned
    assert "[redacted-secret]" in cleaned
    assert "me@example.com" not in cleaned


def test_sanitize_context_value_enforces_allowed_formats() -> None:
    assert llm_delegation._sanitize_context_value("routing_enforced", "yes") is True
    assert (
        llm_delegation._sanitize_context_value("requested_target_language", "../Python")
        == "general"
    )
    assert llm_delegation._sanitize_context_value("routing_version", "version one") == "unknown"
    assert (
        llm_delegation._sanitize_context_value("selected_agent_id", "agent-14-python")
        == "AGENT-14-PYTHON"
    )
    assert llm_delegation._sanitize_context_value("selected_agent_id", "drop table") is None


def test_safe_context_json_filters_and_truncates(monkeypatch) -> None:
    monkeypatch.setattr(llm_delegation, "_PROMPT_CONTEXT_MAX_BYTES", 20)
    serialized = llm_delegation._safe_context_json(
        {
            "mission_id": "mission-1",
            "requested_target_language": "python",
            "source_code": "print('ignore me')",
        }
    )
    assert "source_code" not in serialized
    assert serialized.endswith("...[truncated]")


def test_extract_text_helpers_cover_provider_shapes() -> None:
    assert llm_delegation._extract_openai_text({"output_text": "ok"}) == "ok"
    assert llm_delegation._extract_openai_text(
        {"choices": [{"message": {"content": "from choices"}}]}
    ) == "from choices"
    assert llm_delegation._extract_openai_text(
        {"output": [{"content": [{"text": "a"}, {"text": "b"}]}]}
    ) == "a\nb"
    assert (
        llm_delegation._extract_anthropic_text(
            {"content": [{"type": "text", "text": "alpha"}, {"type": "text", "text": "beta"}]}
        )
        == "alpha\nbeta"
    )
    assert (
        llm_delegation._extract_gemini_text(
            {"candidates": [{"content": {"parts": [{"text": "one"}, {"text": "two"}]}}]}
        )
        == "one\ntwo"
    )


def test_extract_decision_payload_returns_none_for_invalid_json() -> None:
    assert llm_delegation._extract_decision_payload("not-json") is None
    assert llm_delegation._extract_decision_payload("[1,2,3]") is None


def test_normalize_helpers() -> None:
    assert llm_delegation._normalize_text_list("single") == ["single"]
    assert llm_delegation._normalize_text_list(["one", "two", "", 3]) == ["one", "two", "3"]
    assert (
        llm_delegation._normalize_agent_choice(
            "agent-14-python",
            allowed_ids={"AGENT-14-PYTHON"},
            fallback="AGENT-22-RUST",
        )
        == "AGENT-14-PYTHON"
    )
    assert (
        llm_delegation._normalize_agent_choice(
            "bogus",
            allowed_ids={"AGENT-14-PYTHON"},
            fallback="AGENT-22-RUST",
        )
        == "AGENT-22-RUST"
    )


def test_call_provider_routes_to_expected_backend(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []

    async def _openai(model: str, prompt: str, *, call_context: str):
        calls.append(("openai", model))
        assert prompt == "prompt"
        assert call_context == "ctx"
        return {"ok": True}

    async def _anthropic(model: str, prompt: str, *, call_context: str):
        calls.append(("anthropic", model))
        return {"ok": True}

    async def _gemini(model: str, prompt: str, *, call_context: str):
        calls.append(("gemini", model))
        return {"ok": True}

    monkeypatch.setattr(llm_delegation, "_call_openai", _openai)
    monkeypatch.setattr(llm_delegation, "_call_anthropic", _anthropic)
    monkeypatch.setattr(llm_delegation, "_call_gemini", _gemini)

    assert asyncio.run(
        llm_delegation._call_provider(
            provider="anthropic", model="claude", prompt="prompt", call_context="ctx"
        )
    ) == {"ok": True}
    assert asyncio.run(
        llm_delegation._call_provider(
            provider="gemini", model="gemini-pro", prompt="prompt", call_context="ctx"
        )
    ) == {"ok": True}
    assert asyncio.run(
        llm_delegation._call_provider(
            provider="openai", model="gpt", prompt="prompt", call_context="ctx"
        )
    ) == {"ok": True}
    assert calls == [("anthropic", "claude"), ("gemini", "gemini-pro"), ("openai", "gpt")]


def test_call_with_recommendation_uses_fallback_route(monkeypatch) -> None:
    async def _call_provider(*, provider: str, model: str, prompt: str, call_context: str):
        _ = prompt, call_context
        if provider == "anthropic":
            return None
        return {"specialist_agent_id": "AGENT-14-PYTHON"}

    monkeypatch.setattr(llm_delegation, "_call_provider", _call_provider)

    parsed, provider, model, route = asyncio.run(
        llm_delegation._call_with_recommendation(
            recommendation={
                "provider": "anthropic",
                "model": "claude",
                "fallback_provider": "openai",
                "fallback_model": "gpt-5.2-mini",
            },
            prompt="prompt",
            call_context="ctx",
        )
    )
    assert parsed == {"specialist_agent_id": "AGENT-14-PYTHON"}
    assert provider == "openai"
    assert model == "gpt-5.2-mini"
    assert route == "fallback"


def test_call_with_recommendation_returns_primary_when_fallback_is_same(monkeypatch) -> None:
    async def _call_provider(*, provider: str, model: str, prompt: str, call_context: str):
        _ = provider, model, prompt, call_context
        return None

    monkeypatch.setattr(llm_delegation, "_call_provider", _call_provider)
    parsed, provider, model, route = asyncio.run(
        llm_delegation._call_with_recommendation(
            recommendation={
                "provider": "openai",
                "model": "gpt-5.2-mini",
                "fallback_provider": "openai",
                "fallback_model": "gpt-5.2-mini",
            },
            prompt="prompt",
            call_context="ctx",
        )
    )
    assert parsed is None
    assert provider == "openai"
    assert model == "gpt-5.2-mini"
    assert route == "primary"


def test_provider_calls_handle_missing_keys_and_bad_responses(monkeypatch) -> None:
    monkeypatch.setattr(llm_delegation, "OPENAI_API_KEY", "")
    monkeypatch.setattr(llm_delegation, "ANTHROPIC_API_KEY", "")
    monkeypatch.setattr(llm_delegation, "GEMINI_API_KEY", "")
    assert asyncio.run(
        llm_delegation._call_openai("gpt", "prompt", call_context="ctx")
    ) is None
    assert asyncio.run(
        llm_delegation._call_anthropic("claude", "prompt", call_context="ctx")
    ) is None
    assert asyncio.run(
        llm_delegation._call_gemini("gemini", "prompt", call_context="ctx")
    ) is None

    class _InvalidJsonResponse:
        status_code = 200

        @staticmethod
        def json():
            raise ValueError("bad json")

    async def _post(*args, **kwargs):
        return _InvalidJsonResponse()

    monkeypatch.setattr(llm_delegation, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(llm_delegation, "ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(llm_delegation, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(llm_delegation, "_post_with_retry", _post)

    assert asyncio.run(
        llm_delegation._call_openai("gpt", "prompt", call_context="ctx")
    ) is None
    assert asyncio.run(
        llm_delegation._call_anthropic("claude", "prompt", call_context="ctx")
    ) is None
    assert asyncio.run(
        llm_delegation._call_gemini("gemini", "prompt", call_context="ctx")
    ) is None


def test_provider_calls_reject_error_status(monkeypatch) -> None:
    async def _post(*args, **kwargs):
        request = httpx.Request("POST", "https://example.test")
        return httpx.Response(500, request=request, json={"error": "boom"})

    monkeypatch.setattr(llm_delegation, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(llm_delegation, "ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(llm_delegation, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(llm_delegation, "_post_with_retry", _post)

    assert asyncio.run(
        llm_delegation._call_openai("gpt", "prompt", call_context="ctx")
    ) is None
    assert asyncio.run(
        llm_delegation._call_anthropic("claude", "prompt", call_context="ctx")
    ) is None
    assert asyncio.run(
        llm_delegation._call_gemini("gemini", "prompt", call_context="ctx")
    ) is None


def test_generate_specialist_plan_defaults_empty_model_output(monkeypatch) -> None:
    monkeypatch.setattr(
        llm_delegation,
        "_agent_recommendation",
        lambda _agent_id: {"provider": "openai", "model": "gpt-5.2-pro"},
    )

    async def _openai(_model: str, _prompt: str, *, call_context: str) -> dict[str, Any] | None:
        assert "specialist planning" in call_context
        return {
            "plan_summary": "",
            "deliverables": [],
            "risk_notes": [],
        }

    monkeypatch.setattr(llm_delegation, "_call_openai", _openai)
    result = asyncio.run(
        llm_delegation.generate_specialist_plan(
            mission_context={"mission_id": "mission-5", "requested_target_language": "python"},
            requested_target_language="python",
            specialist_agent_id="AGENT-14-PYTHON",
            pod_manager_agent_id="AGENT-12-PODA-MGR",
        )
    )
    assert result["source"] == "llm"
    assert result["plan_summary"] == "Specialist execution plan generated from mission context."
    assert result["deliverables"]
    assert result["risk_notes"] == ["No explicit risks returned by model output."]


def test_retry_delay_for_response_uses_default_on_invalid_header() -> None:
    request = httpx.Request("POST", "https://example.test")
    response = httpx.Response(429, request=request, headers={"Retry-After": "invalid"})
    assert llm_delegation._retry_delay_for_response(response, 1.5) == 1.5


def test_resolve_agent_and_recommendation_default_to_ceo() -> None:
    agent = llm_delegation._resolve_agent("missing-agent")
    recommendation = llm_delegation._agent_recommendation("missing-agent")
    assert agent.agent_id == llm_delegation.CEO_AGENT_ID
    assert recommendation["agent_id"] == llm_delegation.CEO_AGENT_ID


def test_extract_text_helpers_return_none_for_invalid_shapes() -> None:
    assert llm_delegation._extract_openai_text({"choices": ["bad"], "output": ["bad"]}) is None
    assert llm_delegation._extract_anthropic_text({"content": [{"type": "image"}]}) is None
    assert (
        llm_delegation._extract_gemini_text({"candidates": [{"content": {"parts": ["bad"]}}]})
        is None
    )


def test_call_with_recommendation_without_fallback_returns_primary(monkeypatch) -> None:
    async def _call_provider(*, provider: str, model: str, prompt: str, call_context: str):
        _ = provider, model, prompt, call_context
        return None

    monkeypatch.setattr(llm_delegation, "_call_provider", _call_provider)
    parsed, provider, model, route = asyncio.run(
        llm_delegation._call_with_recommendation(
            recommendation={"provider": "openai", "model": "gpt-5.2-mini"},
            prompt="prompt",
            call_context="ctx",
        )
    )
    assert parsed is None
    assert (provider, model, route) == ("openai", "gpt-5.2-mini", "primary")


def test_generate_ceo_delegation_uses_default_rationale(monkeypatch) -> None:
    monkeypatch.setattr(
        llm_delegation,
        "_ceo_recommendation",
        lambda: {"provider": "openai", "model": "gpt-5.2-pro"},
    )

    async def _openai(_model: str, _prompt: str, *, call_context: str) -> dict[str, Any] | None:
        assert "ceo delegation" in call_context
        return {
            "pod_manager_agent_id": "AGENT-12-PODA-MGR",
            "specialist_agent_id": "AGENT-14-PYTHON",
        }

    monkeypatch.setattr(llm_delegation, "_call_openai", _openai)
    result = asyncio.run(
        llm_delegation.generate_ceo_delegation(
            mission_context={"mission_id": "mission-6"},
            requested_target_language="python",
        )
    )
    assert result["rationale"] == "Delegation synthesized from mission context."


def test_generate_pod_manager_delegation_falls_back_when_default_specialist_blank(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        llm_delegation,
        "_agent_recommendation",
        lambda _agent_id: {"provider": "openai", "model": "gpt-5.2-pro"},
    )

    async def _openai(_model: str, _prompt: str, *, call_context: str) -> dict[str, Any] | None:
        assert "pod-manager delegation" in call_context
        return None

    monkeypatch.setattr(llm_delegation, "_call_openai", _openai)
    result = asyncio.run(
        llm_delegation.generate_pod_manager_delegation(
            mission_context={"mission_id": "mission-7"},
            requested_target_language="python",
            pod_manager_agent_id="agent-12-poda-mgr",
            default_specialist_agent_id="  ",
        )
    )
    assert result["source"] == "fallback"
    assert result["specialist_agent_id"] == "AGENT-14-PYTHON"


def test_generate_specialist_plan_normalizes_blank_agent_inputs(monkeypatch) -> None:
    monkeypatch.setattr(
        llm_delegation,
        "_agent_recommendation",
        lambda _agent_id: {"provider": "openai", "model": "gpt-5.2-pro"},
    )

    async def _openai(_model: str, _prompt: str, *, call_context: str) -> dict[str, Any] | None:
        assert "specialist planning" in call_context
        return {
            "plan_summary": "Deliver build",
            "deliverables": "one task",
            "risk_notes": "minor risk",
        }

    monkeypatch.setattr(llm_delegation, "_call_openai", _openai)
    result = asyncio.run(
        llm_delegation.generate_specialist_plan(
            mission_context={"mission_id": "mission-8", "requested_target_language": "rust"},
            requested_target_language="rust",
            specialist_agent_id=" ",
            pod_manager_agent_id=" ",
        )
    )
    assert result["specialist_agent_id"] == "AGENT-22-RUST"
    assert result["pod_manager_agent_id"] == "AGENT-18-PODB-MGR"
    assert result["deliverables"] == ["one task"]
    assert result["risk_notes"] == ["minor risk"]
