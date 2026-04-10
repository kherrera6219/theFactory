import asyncio
import importlib
import sys
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

orchestrator_main = importlib.import_module("orchestrator.main")
orchestrator_models = importlib.import_module("orchestrator.models")

MissionEvent = orchestrator_models.MissionEvent
MissionRecord = orchestrator_models.MissionRecord
MissionState = orchestrator_models.MissionState
AgentHeartbeatUpsert = orchestrator_models.AgentHeartbeatUpsert


def _mission(
    mission_id: str,
    *,
    state: MissionState = MissionState.running,
    language: str = "python",
    metadata: dict[str, Any] | None = None,
) -> MissionRecord:
    return MissionRecord(
        mission_id=mission_id,
        prompt="Build API",
        requested_target_language=language,
        metadata=metadata or {},
        state=state,
        created_at="2026-03-01T00:00:00+00:00",
    )


def test_parse_iso_datetime_and_route_summary_helpers() -> None:
    assert orchestrator_main._parse_iso_datetime(None) is None
    assert orchestrator_main._parse_iso_datetime("bad") is None
    assert orchestrator_main._parse_iso_datetime("2026-03-01T00:00:00") is None
    parsed = orchestrator_main._parse_iso_datetime("2026-03-01T00:00:00Z")
    assert parsed == datetime(2026, 3, 1, 0, 0, tzinfo=UTC)

    assert orchestrator_main._route_provenance_snapshot("bad", role="ceo") is None
    ceo_snapshot = orchestrator_main._route_provenance_snapshot(
        {
            "source": "llm",
            "llm_route": "primary",
            "model_provider": "openai",
            "model": "gpt-5.3",
            "pod_manager_agent_id": "AGENT-12-PODA-MGR",
            "specialist_agent_id": "AGENT-14-PYTHON",
            "rationale": "match language",
            "mission_context": {"source": "repo-review"},
        },
        role="ceo",
    )
    assert ceo_snapshot["target_agent_id"] == "AGENT-12-PODA-MGR"
    assert ceo_snapshot["mission_source"] == "repo-review"

    pod_manager_snapshot = orchestrator_main._route_provenance_snapshot(
        {
            "source": "llm",
            "llm_route": "primary",
            "model_provider": "anthropic",
            "model": "claude",
            "pod_manager_agent_id": "AGENT-12-PODA-MGR",
            "specialist_agent_id": "AGENT-14-PYTHON",
            "rationale": "delegate specialist",
        },
        role="pod_manager",
    )
    assert pod_manager_snapshot["target_agent_id"] == "AGENT-14-PYTHON"

    specialist_snapshot = orchestrator_main._route_provenance_snapshot(
        {
            "source": "fallback",
            "llm_route": "fallback",
            "model_provider": "offline",
            "model": "deterministic",
            "specialist_agent_id": "AGENT-14-PYTHON",
            "pod_manager_agent_id": "AGENT-12-PODA-MGR",
            "plan_summary": "Implement patch",
            "deliverables": ["patch"],
            "risk_notes": ["none"],
        },
        role="specialist",
    )
    assert specialist_snapshot["plan_summary"] == "Implement patch"

    assert orchestrator_main._artifact_summary({"mission_artifacts": "bad"}) == {}
    assert orchestrator_main._artifact_summary(
        {"mission_artifacts": {"good": {"event_type": "MISSION_RUNNING"}, 3: {"bad": True}}}
    ) == {"good": {"event_type": "MISSION_RUNNING"}}

    assert orchestrator_main._scaling_summary({}) is None
    scaling = orchestrator_main._scaling_summary(
        {
            "scaling_active": True,
            "scaling_decision": {"partition_count": 2},
            "partition_results": {"a": {}, "b": {}},
            "scaling_partition_events_emitted": True,
            "scaling_merge_complete": True,
            "merged_partition_result": {"status": "merged"},
        }
    )
    assert scaling == {
        "active": True,
        "decision": {"partition_count": 2},
        "partition_result_count": 2,
        "partition_events_emitted": True,
        "complete": True,
        "merged_result": {"status": "merged"},
    }


def test_build_mission_chain_trace_appends_derived_events_and_sorts() -> None:
    mission = _mission(
        "mission-1",
        metadata={
            "routing_enforced": True,
            "routing_version": "v2",
            "selected_agent_id": "AGENT-14-PYTHON",
            "intake_agent_id": "AGENT-01-PM",
            "executive_agent_id": "AGENT-02-CEO",
            "assigned_pod_manager_agent_id": "AGENT-12-PODA-MGR",
            "assigned_specialist_agent_id": "AGENT-14-PYTHON",
            "ceo_delegation": {"source": "llm", "pod_manager_agent_id": "AGENT-12-PODA-MGR"},
            "pod_manager_delegation": {
                "source": "llm",
                "specialist_agent_id": "AGENT-14-PYTHON",
                "pod_manager_agent_id": "AGENT-12-PODA-MGR",
            },
            "specialist_plan": {
                "source": "fallback",
                "specialist_agent_id": "AGENT-14-PYTHON",
                "pod_manager_agent_id": "AGENT-12-PODA-MGR",
                "plan_summary": "Implement",
            },
            "mission_artifacts": {
                "specialist_planned": {"event_type": "MISSION_SPECIALIST_PLANNED"}
            },
        },
    )

    payload = orchestrator_main._build_mission_chain_trace(
        mission=mission,
        pod_assignment={"pod_name": "podA", "updated_at": "2026-03-01T00:00:03+00:00"},
        logicnodes=[{"node_id": "node-1", "created_at": "2026-03-01T00:00:02+00:00"}],
        events=[
            MissionEvent(
                mission_id="mission-1",
                previous_state=MissionState.verified,
                new_state=MissionState.verified,
                event_type="MISSION_COMPLETION_BLOCKED",
                ts="2026-03-01T00:00:04+00:00",
            )
        ],
        build_artifacts=[{"artifact_id": "artifact-1"}],
    )

    event_types = [event["event_type"] for event in payload["events"]]
    assert event_types[0] == "MISSION_COMPLETION_BLOCKED"
    assert sorted(event_types) == sorted(
        [
            "MISSION_LOGICNODE_WRITTEN",
            "MISSION_POD_ASSIGNED",
            "MISSION_COMPLETION_BLOCKED",
        ]
    )
    assert payload["route_provenance"]["fallback_used"] is True
    assert payload["build_artifacts"] == [{"artifact_id": "artifact-1"}]
    assert (
        payload["artifact_summary"]["specialist_planned"]["event_type"]
        == "MISSION_SPECIALIST_PLANNED"
    )


def test_langgraph_runtime_payload_and_health_cover_optional_paths(monkeypatch) -> None:
    app = orchestrator_main.app
    original_settings = app.state.settings
    original_redis = getattr(app.state, "redis", None)
    original_consumer_task = getattr(app.state, "consumer_task", None)
    original_protocol_ready = getattr(app.state, "protocol_ready", False)
    original_langgraph_setup_done = getattr(
        app.state, "langgraph_postgres_checkpointer_setup_done", False
    )
    original_bootstrapped = getattr(app.state, "lifecycle_recovery_bootstrapped", False)
    original_recovered_count = getattr(app.state, "lifecycle_recovery_recovered_count", 0)
    original_scanned_count = getattr(app.state, "lifecycle_recovery_scanned_count", 0)
    original_last_at = getattr(app.state, "lifecycle_recovery_last_at", None)
    original_last_error = getattr(app.state, "lifecycle_recovery_last_error", None)
    try:
        app.state.settings = replace(
            app.state.settings,
            qdrant_enabled=True,
            milvus_enabled=True,
            neo4j_enabled=True,
            object_storage_enabled=True,
        )
        app.state.langgraph_postgres_checkpointer_setup_done = True
        app.state.lifecycle_recovery_bootstrapped = True
        app.state.lifecycle_recovery_recovered_count = 2
        app.state.lifecycle_recovery_scanned_count = 4
        app.state.lifecycle_recovery_last_at = "2026-03-01T00:00:00+00:00"
        app.state.lifecycle_recovery_last_error = None
        app.state.consumer_task = SimpleNamespace(done=lambda: False)
        app.state.protocol_ready = True

        async def _aclose() -> None:
            return None

        app.state.redis = SimpleNamespace(
            ping=lambda: (_ for _ in ()).throw(RuntimeError("redis down")),
            aclose=_aclose,
        )

        payload = orchestrator_main._langgraph_runtime_payload(app)
        assert payload["langgraph_enabled"] == app.state.settings.langgraph_enabled
        assert payload["lifecycle_recovery_recovered_count"] == 2

        async def _runtime_ready(_app: Any) -> tuple[bool, bool]:
            return True, True

        monkeypatch.setattr(orchestrator_main, "ensure_runtime_ready", _runtime_ready)
        monkeypatch.setattr(
            orchestrator_main.storage,
            "count_missions",
            lambda *_args: (_ for _ in ()).throw(RuntimeError("db down")),
        )
        monkeypatch.setattr(orchestrator_main.qdrant_store, "qdrant_ready", lambda *_: True)
        monkeypatch.setattr(orchestrator_main.milvus_store, "milvus_ready", lambda *_: False)
        monkeypatch.setattr(orchestrator_main.neo4j_store, "neo4j_ready", lambda *_: True)
        monkeypatch.setattr(orchestrator_main.object_store, "object_storage_ready", lambda *_: True)

        client = TestClient(app)
        health = client.get("/health")

        assert health.status_code == 200
        body = health.json()
        assert body["db_ready"] is False
        assert body["redis_healthy"] is False
        assert body["qdrant_ready"] is True
        assert body["milvus_ready"] is False
        assert body["neo4j_ready"] is True
        assert body["object_storage_ready"] is True
    finally:
        app.state.settings = original_settings
        app.state.redis = original_redis
        app.state.consumer_task = original_consumer_task
        app.state.protocol_ready = original_protocol_ready
        app.state.langgraph_postgres_checkpointer_setup_done = original_langgraph_setup_done
        app.state.lifecycle_recovery_bootstrapped = original_bootstrapped
        app.state.lifecycle_recovery_recovered_count = original_recovered_count
        app.state.lifecycle_recovery_scanned_count = original_scanned_count
        app.state.lifecycle_recovery_last_at = original_last_at
        app.state.lifecycle_recovery_last_error = original_last_error


def test_readyz_covers_optional_dependency_failures(monkeypatch) -> None:
    app = orchestrator_main.app
    original_settings = app.state.settings
    original_consumer_task = getattr(app.state, "consumer_task", None)
    original_protocol_ready = getattr(app.state, "protocol_ready", False)
    try:
        app.state.settings = replace(
            app.state.settings,
            qdrant_enabled=True,
            milvus_enabled=True,
            neo4j_enabled=True,
            object_storage_enabled=True,
        )
        app.state.protocol_ready = True
        app.state.consumer_task = SimpleNamespace(done=lambda: False)

        async def _runtime_ready(_app: Any) -> tuple[bool, bool]:
            return True, True

        monkeypatch.setattr(orchestrator_main, "ensure_runtime_ready", _runtime_ready)
        monkeypatch.setattr(orchestrator_main.qdrant_store, "qdrant_ready", lambda *_: False)
        monkeypatch.setattr(orchestrator_main.milvus_store, "milvus_ready", lambda *_: True)
        monkeypatch.setattr(orchestrator_main.neo4j_store, "neo4j_ready", lambda *_: True)
        monkeypatch.setattr(orchestrator_main.object_store, "object_storage_ready", lambda *_: True)

        client = TestClient(app)
        response = client.get("/readyz")
        assert response.status_code == 503
        assert response.json()["detail"]["qdrant_ready"] is False
    finally:
        app.state.settings = original_settings
        app.state.consumer_task = original_consumer_task
        app.state.protocol_ready = original_protocol_ready


def test_build_non_pod_heartbeat_payloads_routes_support_agents() -> None:
    payloads = orchestrator_main._build_non_pod_heartbeat_payloads(
        runtime={
            "redis_ready": True,
            "db_ready": True,
            "protocol_ready": True,
            "consumer_running": True,
        },
        missions=[
            _mission("mission-active-python", state=MissionState.running, language="python"),
            _mission("mission-active-go", state=MissionState.queued, language="go"),
            _mission("mission-verified", state=MissionState.verified, language="typescript"),
            _mission("mission-complete", state=MissionState.complete, language="rust"),
        ],
    )

    tester = next(payload for payload in payloads if payload.agent_id == "AGENT-10-TESTER")
    deploy = next(payload for payload in payloads if payload.agent_id == "AGENT-11-DEPLOY")
    hardware = next(payload for payload in payloads if payload.agent_id == "AGENT-09-HW")
    pm = next(payload for payload in payloads if payload.agent_id == "AGENT-01-PM")

    assert "mission-verified" in tester.active_mission_ids
    assert "mission-complete" in deploy.active_mission_ids
    assert "mission-active-go" in hardware.active_mission_ids
    assert "mission-active-python" in pm.active_mission_ids


def test_emit_agent_telemetry_event_publishes_error_priority_payload() -> None:
    writes: list[tuple[str, dict[str, Any], int, bool]] = []

    class _Redis:
        async def xadd(
            self,
            stream: str,
            fields: dict[str, Any],
            maxlen: int | None = None,
            approximate: bool = False,
        ) -> str:
            writes.append((stream, fields, maxlen, approximate))
            return "1-0"

    validator_calls: list[dict[str, Any]] = []

    class _Validator:
        def validate(self, envelope: dict[str, Any]) -> None:
            validator_calls.append(envelope)

    app = SimpleNamespace(
        state=SimpleNamespace(
            envelope_validator=_Validator(),
            redis=_Redis(),
            protocol_ready=True,
            redis_ready=True,
            settings=SimpleNamespace(state_stream="missions.state", max_stream_len=42),
        )
    )
    record = {
        "agent_id": "AGENT-14-PYTHON",
        "state": "ERROR",
        "queue_depth": 2,
        "workload_pct": 80,
        "active_mission_ids": ["mission-1"],
        "last_heartbeat": "2026-03-01T00:00:00+00:00",
        "metadata": {"producer": "worker-runtime"},
    }

    asyncio.run(
        orchestrator_main._emit_agent_telemetry_event(
            app,
            record=record,
            event_type="AGENT_STATE_CHANGED",
        )
    )

    assert validator_calls[0]["priority"] == "HIGH"
    assert validator_calls[0]["producer"] == "worker-runtime"
    assert writes[0][0] == "missions.state"
    assert writes[0][2] == 42


def test_upsert_agent_heartbeat_handles_emit_failures(monkeypatch) -> None:
    app = SimpleNamespace(state=SimpleNamespace(settings=SimpleNamespace()))
    payload = AgentHeartbeatUpsert(agent_id="AGENT-01-PM", state="RUNNING")

    monkeypatch.setattr(
        orchestrator_main.storage,
        "upsert_agent_heartbeat",
        lambda *_args: {"agent_id": "AGENT-01-PM", "state_changed": True},
    )

    async def _emit(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("stream unavailable")

    monkeypatch.setattr(orchestrator_main, "_emit_agent_telemetry_event", _emit)

    record = asyncio.run(
        orchestrator_main._upsert_agent_heartbeat(
            app,
            payload,
            emit_stream_event=True,
        )
    )

    assert record["agent_id"] == "AGENT-01-PM"
