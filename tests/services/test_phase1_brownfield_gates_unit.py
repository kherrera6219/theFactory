"""Unit tests for Phase 1 brownfield gates, provider preflight, fallback policy, and timeline."""

from __future__ import annotations

import importlib
import sys
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

llm_cost_ledger = importlib.import_module("orchestrator.llm_cost_ledger")
llm_health = importlib.import_module("orchestrator.llm_delegation.health")
mission_flow_v2 = importlib.import_module("orchestrator.mission_flow_v2")
phases_build = importlib.import_module("orchestrator.mission_flow_v2.phases_build")
phases_delivery = importlib.import_module("orchestrator.mission_flow_v2.phases_delivery")
lifecycle = importlib.import_module("orchestrator.mission_flow_v2.lifecycle")
flow_base = importlib.import_module("orchestrator.mission_flow_v2.base")
orchestrator_main = importlib.import_module("orchestrator.main")
orchestrator_models = importlib.import_module("orchestrator.models")
orchestrator_settings = importlib.import_module("orchestrator.settings")

MissionRecord = orchestrator_models.MissionRecord
MissionState = orchestrator_models.MissionState


def _make_settings(**overrides):
    defaults = {
        "environment": "development",
        "mission_fallback_policy": "auto",
        "provider_preflight_required": False,
        "agent_scaling_enabled": False,
        "agent_scaling_max_instances": 1,
        "agent_scaling_items_per_instance": 5,
        "protocol_bus_enabled": False,
        "knowledge_lake_enabled": False,
        "security_compliance_enabled": False,
        "dependency_absorption_enabled": False,
        "behavioural_equivalence_enabled": False,
        "vc_commit_strategy_enabled": False,
        "integration_tests_enabled": False,
        "compliance_assessment_enabled": False,
        "port_two_phase_enabled": False,
        "delivery_dir": Path("output"),
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_app_state(*, redis_ready: bool = True, db_ready: bool = True):
    return SimpleNamespace(
        state=SimpleNamespace(
            redis_ready=redis_ready,
            db_ready=db_ready,
            protocol_ready=True,
            redis=None,
            protocol_bus_client=None,
        )
    )


def _make_mission(*, state: MissionState = MissionState.specialist_assigned, metadata=None):
    return MissionRecord(
        mission_id="mission-phase1-unit",
        prompt="Extend legacy service safely",
        requested_target_language="python",
        metadata=metadata or {},
        state=state,
        created_at="2026-11-13T00:00:00+00:00",
    )


@pytest.mark.asyncio
async def test_provider_preflight_status_and_redaction(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "secret-gemini-value")
    monkeypatch.setenv("OPENAI_API_KEY", "secret-openai-value")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    class _FakeClient:
        def __init__(self, timeout: float = 4.0) -> None:
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def get(self, url: str, headers=None):  # type: ignore[no-untyped-def]
            if "generativelanguage" in url:
                return SimpleNamespace(status_code=200)
            if "openai" in url:
                return SimpleNamespace(status_code=401)
            raise RuntimeError("network_down")

    result = await llm_health.run_provider_preflight(client_factory=_FakeClient)

    assert result["checked"] is True
    assert result["any_provider_ready"] is True
    assert result["configured_count"] == 2
    assert result["ready_count"] == 1
    assert result["providers"]["gemini"]["ready"] is True
    assert result["providers"]["openai"]["ready"] is False
    assert result["providers"]["openai"]["detail"] == "http_401"
    assert result["providers"]["anthropic"]["detail"] == "missing_api_key"
    assert "secret-gemini-value" not in str(result)
    assert "secret-openai-value" not in str(result)
    assert llm_health.get_provider_preflight_status()["ready_count"] == 1


@pytest.mark.asyncio
async def test_provider_preflight_network_failure_fails_open(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "k1")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    class _BrokenClient:
        def __init__(self, timeout: float = 4.0) -> None:
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def get(self, url: str, headers=None):  # type: ignore[no-untyped-def]
            raise ConnectionError("tls handshake timed out")

    result = await llm_health.run_provider_preflight(client_factory=_BrokenClient)
    assert result["any_provider_ready"] is False
    assert result["providers"]["gemini"]["reachable"] is False
    assert result["providers"]["gemini"]["detail"] == "probe_error:ConnectionError"


def test_readyz_enforces_provider_preflight_when_required(monkeypatch) -> None:
    app = orchestrator_main.app
    client = TestClient(app)
    fake_task = MagicMock()
    fake_task.done.return_value = False
    settings = SimpleNamespace(
        qdrant_enabled=False,
        milvus_enabled=False,
        neo4j_enabled=False,
        object_storage_enabled=False,
        provider_preflight_required=True,
        langgraph_enabled=False,
        langgraph_fail_open=True,
        langgraph_checkpointer="memory",
        langgraph_checkpointer_setup=False,
        langgraph_checkpoint_namespace="",
    )
    monkeypatch.setattr(app.state, "settings", settings, raising=False)
    monkeypatch.setattr(app.state, "redis_ready", True, raising=False)
    monkeypatch.setattr(app.state, "db_ready", True, raising=False)
    monkeypatch.setattr(app.state, "protocol_ready", True, raising=False)
    monkeypatch.setattr(app.state, "consumer_task", fake_task, raising=False)
    monkeypatch.setattr(
        orchestrator_main,
        "ensure_runtime_ready",
        AsyncMock(return_value=(True, True)),
    )
    monkeypatch.setattr(orchestrator_main.object_store, "object_lock_ready", lambda *_a, **_k: True)
    monkeypatch.setitem(llm_health._PROVIDER_PREFLIGHT_STATE, "any_provider_ready", False)

    resp_503 = client.get("/readyz")
    assert resp_503.status_code == 503
    assert resp_503.json()["detail"]["provider_preflight_ready"] is False

    monkeypatch.setitem(llm_health._PROVIDER_PREFLIGHT_STATE, "any_provider_ready", True)
    resp_200 = client.get("/readyz")
    assert resp_200.status_code == 200
    assert resp_200.json()["provider_preflight_ready"] is True


def test_resolve_mission_fallback_policy() -> None:
    assert orchestrator_settings.resolve_mission_fallback_policy(
        "auto", environment="development"
    ) == "warn"
    assert orchestrator_settings.resolve_mission_fallback_policy(
        "auto", environment="production"
    ) == "block"
    assert orchestrator_settings.resolve_mission_fallback_policy(
        "auto", environment="staging"
    ) == "block"
    assert orchestrator_settings.resolve_mission_fallback_policy(
        "allow", environment="production"
    ) == "allow"
    assert orchestrator_settings.resolve_mission_fallback_policy(
        "block", environment="development"
    ) == "block"
    with pytest.raises(ValueError, match="MISSION_FALLBACK_POLICY"):
        orchestrator_settings.resolve_mission_fallback_policy("ignore", environment="development")


@pytest.mark.asyncio
async def test_fallback_policy_block_prevents_gating_and_marks_delivery_degraded() -> None:
    app = _make_app_state()
    settings = _make_settings(environment="production", mission_fallback_policy="block")
    mission = _make_mission(
        state=MissionState.specialist_assigned,
        metadata={
            "mission_type": "BUILD_NEW",
            "assigned_pod_manager_agent_id": "AGENT-12-PODA-MGR",
            "assigned_specialist_agent_id": "AGENT-14-PYTHON",
            "ceo_delegation": {"specialist_agent_id": "AGENT-14-PYTHON"},
            "mission_contract": {"contract_summary": "Fix endpoint", "acceptance_criteria": []},
        },
    )

    with patch("orchestrator.mission_flow_v2.storage") as mock_storage:
        mock_storage.fetch_mission = lambda _s, _mid: mission
        mock_storage.update_mission_metadata = (
            lambda _s, _mid, md: setattr(mission, "metadata", md) or mission
        )
        mock_storage.insert_mission_event = MagicMock()
        with (
            patch.object(
                mission_flow_v2,
                "generate_specialist_plan",
                new=AsyncMock(return_value={"source": "llm", "deliverables": ["a", "b", "c"]}),
            ),
            patch.object(
                mission_flow_v2,
                "generate_code_from_contract",
                new=AsyncMock(
                    return_value={
                        "source": "fallback",
                        "fallback_reason": "provider_timeout",
                        "filename": "app.py",
                        "language": "python",
                        "generated_code": "# fallback\n",
                        "code_length_chars": 11,
                        "model_provider": "fallback",
                        "model": "deterministic",
                    }
                ),
            ),
            patch("orchestrator.mission_flow_v2.record_audit_event", AsyncMock()),
        ):
            prepared = await phases_build._prepare_specialist_plan(
                app=app,
                settings=settings,
                validator=MagicMock(),
                emit_state_event_fn=AsyncMock(),
                mission_id=mission.mission_id,
            )

        assert prepared is True
        assert mission.metadata["generation_degraded"] is True
        assert mission.metadata["generation_degraded_blocked"] is True
        assert any(
            ev["event_type"] == "MISSION_GENERATION_DEGRADED"
            for ev in mission.metadata["chain_trace"]
        )

        can_gate = await lifecycle._advance_running_to_gating(
            app=app,
            settings=settings,
            validator=MagicMock(),
            mission_id=mission.mission_id,
        )
        assert can_gate is False

        can_complete = await lifecycle._advance_verified_to_complete(
            app=app,
            settings=settings,
            validator=MagicMock(),
            emit_state_event_fn=AsyncMock(),
            mission_id=mission.mission_id,
            completion_check_fn=AsyncMock(return_value=(True, {})),
        )
        assert can_complete is False

        with (
            patch.object(
                mission_flow_v2,
                "generate_pm_delivery_summary",
                new=AsyncMock(
                    return_value={
                        "delivery_title": "Degraded output",
                        "delivery_summary": "Fallback generated",
                        "criteria_met": [],
                        "criteria_unmet": ["Real LLM generation required"],
                        "recommendations": ["Configure provider key"],
                        "source": "fallback",
                    }
                ),
            ),
            patch("orchestrator.mission_flow_v2.record_audit_event", AsyncMock()),
        ):
            await phases_delivery._prepare_delivery_summary(
                app=app,
                settings=settings,
                mission=mission,
            )
        assert mission.metadata["delivery_summary"]["degraded"] is True


@pytest.mark.asyncio
async def test_agent_activation_timeline_and_cost_ledger_activations(monkeypatch) -> None:
    md: dict = {}
    flow_base._record_artifact(
        md,
        stage="specialist_plan",
        event_type="SPECIALIST_PLAN_GENERATED",
        agent_id="AGENT-14-PYTHON",
        details={"provider": "openai", "model": "gpt-6.1-terrea", "source": "llm"},
    )
    assert len(md["agent_activations"]) == 1
    assert md["agent_activations"][0]["agent_id"] == "AGENT-14-PYTHON"
    assert md["agent_activations"][0]["model"] == "gpt-6.1-terrea"

    class _Cursor:
        def __init__(self) -> None:
            self._rows = []

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, sql: str, _params):
            if "GROUP BY agent_id" in sql:
                self._rows = [("AGENT-14-PYTHON", "openai", "gpt-6.1-terrea", 100, 50, 150, 0.002, True, 1)]
            elif "SELECT DISTINCT routing_source" in sql:
                self._rows = [("primary",)]
            else:
                self._rows = [
                    (
                        "AGENT-14-PYTHON",
                        "openai",
                        "gpt-6.1-terrea",
                        100,
                        50,
                        150,
                        0.002,
                        True,
                        True,
                        "primary",
                        datetime(2026, 11, 13, 12, 0, tzinfo=UTC),
                    )
                ]

        def fetchall(self):
            return self._rows

    @contextmanager
    def _fake_db_connect(_settings):
        yield SimpleNamespace(cursor=lambda: _Cursor())

    monkeypatch.setattr(llm_cost_ledger, "db_connect", _fake_db_connect)
    usage = await llm_cost_ledger.get_mission_token_usage(
        settings=_make_settings(), mission_id="mission-phase1-unit"
    )
    assert usage["routing_sources"] == ["primary"]
    assert len(usage["activations"]) == 1
    assert usage["activations"][0]["agent_id"] == "AGENT-14-PYTHON"
    assert usage["activations"][0]["model"] == "gpt-6.1-terrea"
    assert usage["activations"][0]["call_succeeded"] is True


def test_live_stack_gate_and_release_workflow_wiring() -> None:
    gate = yaml.safe_load((ROOT / ".github" / "workflows" / "live-stack-gate.yml").read_text())
    steps_env = [step.get("env") or {} for step in gate["jobs"]["live-stack-gate"]["steps"]]
    assert any(
        env.get("LIVE_STACK_ENABLED") == "1" and env.get("LIVE_STACK_REQUIRED") == "1"
        for env in steps_env
    )

    release = yaml.safe_load((ROOT / ".github" / "workflows" / "release.yml").read_text())
    assert "staging-live-gate" in release["jobs"]
    assert "staging-live-gate" in release["jobs"]["publish-images"]["needs"]
    assert "staging-live-gate" in release["jobs"]["release"]["needs"]
