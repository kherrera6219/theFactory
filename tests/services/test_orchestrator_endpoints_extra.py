import asyncio
import importlib
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

orchestrator_main = importlib.import_module("orchestrator.main")
orchestrator_models = importlib.import_module("orchestrator.models")

MissionEvent = orchestrator_models.MissionEvent
MissionRecord = orchestrator_models.MissionRecord
MissionState = orchestrator_models.MissionState
app = orchestrator_main.app


class _ClosableRedis:
    async def close(self) -> None:
        return None


class _RunningTask:
    def done(self) -> bool:
        return False


def _mission(state: MissionState = MissionState.running) -> MissionRecord:
    return MissionRecord(
        mission_id="mission-1",
        prompt="Build API",
        requested_target_language="python",
        metadata={"source": "test"},
        state=state,
        created_at="2026-03-01T00:00:00+00:00",
    )


async def _db_ready(_: object) -> tuple[bool, bool]:
    return True, True


async def _fetch(_: object, mission_id: str) -> MissionRecord:
    return _mission()


@pytest.fixture(autouse=True)
def _override_auth_dependencies():
    auth_context = orchestrator_main.AuthContext(
        api_key="test-worker-key",
        roles={"admin", "internal", "mutate", "read", "worker"},
    )
    app.dependency_overrides[orchestrator_main.MUTATION_AUTH] = lambda: auth_context
    app.dependency_overrides[orchestrator_main.INTERNAL_AUTH] = lambda: auth_context
    yield
    app.dependency_overrides.clear()


def test_create_mission_endpoint(monkeypatch) -> None:
    monkeypatch.setattr(orchestrator_main, "_ensure_db_ready", _db_ready)
    monkeypatch.setattr(orchestrator_main.storage, "upsert_mission", lambda *_: None)
    monkeypatch.setattr(orchestrator_main.storage, "insert_mission_event", lambda *_: None)
    monkeypatch.setattr(orchestrator_main, "start_lifecycle_task", lambda *_: None)

    emitted: list[str] = []

    async def _emit(*args, **kwargs):
        event_type = kwargs.get("event_type", args[4] if len(args) > 4 else None)
        emitted.append(event_type)

    monkeypatch.setattr(orchestrator_main, "emit_state_event", _emit)

    monkeypatch.setattr(app.state, "redis", _ClosableRedis(), raising=False)
    monkeypatch.setattr(app.state, "protocol_ready", True, raising=False)
    client = TestClient(app)
    response = client.post(
        "/missions",
        headers={"x-api-key": "worker-key"},
        json={"mission_id": "mission-1", "prompt": "Build API", "metadata": {"source": "test"}},
    )
    assert response.status_code == 200
    assert response.json()["state"] == "QUEUED"
    assert emitted == ["MISSION_QUEUED"]


def test_mission_query_endpoints(monkeypatch) -> None:
    monkeypatch.setattr(orchestrator_main, "_ensure_db_ready", _db_ready)
    monkeypatch.setattr(orchestrator_main, "_fetch_existing_mission", _fetch)
    monkeypatch.setattr(orchestrator_main.storage, "fetch_mission", lambda *_: _mission())
    monkeypatch.setattr(orchestrator_main.storage, "list_missions", lambda *_: [_mission()])
    monkeypatch.setattr(
        orchestrator_main.storage,
        "list_mission_events",
        lambda *_: [
            MissionEvent(
                mission_id="mission-1",
                previous_state=MissionState.queued,
                new_state=MissionState.running,
                event_type="MISSION_RUNNING",
                ts="2026-03-01T00:00:00+00:00",
            )
        ],
    )

    client = TestClient(app)
    assert client.get("/missions/mission-1").status_code == 200
    assert client.get("/missions?limit=5").status_code == 200
    events = client.get("/missions/mission-1/events?limit=10")
    assert events.status_code == 200
    assert events.json()[0]["event_type"] == "MISSION_RUNNING"


def test_review_approval_internal_endpoints(monkeypatch) -> None:
    monkeypatch.setattr(orchestrator_main, "_ensure_db_ready", _db_ready)
    monkeypatch.setattr(
        orchestrator_main.storage,
        "upsert_review_approval",
        lambda *_args: {
            "approval_id": "repo-approval-f1234567890abcdef",
            "scope": "repo",
            "fingerprint": "f1234567890abcdef",
            "summary": "Repository review approved for mission launch.",
            "metadata": {"request_id": "repo-review-001"},
            "receipt_digest": "digest-001",
            "storage_backend": "postgres",
            "approved_at": "2026-03-29T00:00:00+00:00",
            "updated_at": "2026-03-29T00:00:00+00:00",
        },
    )
    monkeypatch.setattr(
        orchestrator_main.storage,
        "get_review_approval",
        lambda *_args: {
            "approval_id": "repo-approval-f1234567890abcdef",
            "scope": "repo",
            "fingerprint": "f1234567890abcdef",
            "summary": "Repository review approved for mission launch.",
            "metadata": {"request_id": "repo-review-001"},
            "receipt_digest": "digest-001",
            "storage_backend": "postgres",
            "approved_at": "2026-03-29T00:00:00+00:00",
            "updated_at": "2026-03-29T00:00:00+00:00",
        },
    )

    client = TestClient(app)
    created = client.post(
        "/internal/review-approvals",
        headers={"x-api-key": "worker-key"},
        json={
            "scope": "repo",
            "fingerprint": "f1234567890abcdef",
            "summary": "Repository review approved for mission launch.",
            "metadata": {"request_id": "repo-review-001"},
        },
    )
    assert created.status_code == 200
    assert created.json()["storage_backend"] == "postgres"
    assert created.json()["record_path"].startswith("orchestrator://review-approvals/")

    fetched = client.get(
        "/internal/review-approvals/repo-approval-f1234567890abcdef",
        headers={"x-api-key": "worker-key"},
    )
    assert fetched.status_code == 200
    assert fetched.json()["receipt_digest"] == "digest-001"


def test_build_mission_chain_trace_exposes_route_provenance() -> None:
    mission = MissionRecord(
        mission_id="mission-1",
        prompt="Build API",
        requested_target_language="python",
        metadata={
            "routing_enforced": True,
            "routing_version": "v2",
            "selected_agent_id": "AGENT-14-PYTHON",
            "assigned_pod_manager_agent_id": "AGENT-12-PODA-MGR",
            "assigned_specialist_agent_id": "AGENT-14-PYTHON",
            "ceo_delegation": {
                "source": "llm",
                "llm_route": "primary",
                "model_provider": "anthropic",
                "model": "claude-3-5-sonnet",
                "pod_manager_agent_id": "AGENT-12-PODA-MGR",
                "specialist_agent_id": "AGENT-14-PYTHON",
            },
            "pod_manager_delegation": {
                "source": "llm",
                "llm_route": "primary",
                "model_provider": "openai",
                "model": "gpt-5.2-mini",
                "pod_manager_agent_id": "AGENT-12-PODA-MGR",
                "specialist_agent_id": "AGENT-14-PYTHON",
            },
            "specialist_plan": {
                "source": "fallback",
                "llm_route": "fallback",
                "model_provider": "openai",
                "model": "gpt-5.2-mini",
                "specialist_agent_id": "AGENT-14-PYTHON",
                "pod_manager_agent_id": "AGENT-12-PODA-MGR",
                "plan_summary": "Implement and validate the requested change.",
                "deliverables": ["Patch"],
                "risk_notes": ["Fallback route used."],
            },
            "mission_artifacts": {
                "specialist_planned": {
                    "event_type": "MISSION_SPECIALIST_PLANNED",
                    "agent_id": "AGENT-14-PYTHON",
                }
            },
            "chain_trace": [
                {
                    "event_type": "MISSION_SPECIALIST_PLANNED",
                    "agent_id": "AGENT-14-PYTHON",
                    "ts": "2026-03-01T00:00:00+00:00",
                }
            ],
        },
        state=MissionState.running,
        created_at="2026-03-01T00:00:00+00:00",
    )

    payload = orchestrator_main._build_mission_chain_trace(
        mission=mission,
        pod_assignment={"pod_name": "podA"},
        logicnodes=[{"node_id": "node-1", "created_at": "2026-03-01T00:00:01+00:00"}],
        events=[],
    )

    assert payload["route_provenance"]["fallback_used"] is True
    assert payload["route_provenance"]["ceo"]["target_agent_id"] == "AGENT-12-PODA-MGR"
    assert payload["route_provenance"]["specialist"]["plan_summary"].startswith("Implement")
    assert (
        payload["artifact_summary"]["specialist_planned"]["event_type"]
        == "MISSION_SPECIALIST_PLANNED"
    )


def test_update_state_and_internal_endpoints(monkeypatch) -> None:
    monkeypatch.setattr(orchestrator_main, "_ensure_db_ready", _db_ready)
    monkeypatch.setattr(orchestrator_main, "_fetch_existing_mission", _fetch)
    monkeypatch.setattr(
        app.state,
        "settings",
        replace(
            app.state.settings,
            milvus_enabled=True,
            neo4j_enabled=True,
            object_storage_enabled=True,
        ),
        raising=False,
    )

    responses = [None, _mission(MissionState.failed)]

    def _transition(*_args):
        return responses.pop(0)

    monkeypatch.setattr(orchestrator_main.storage, "transition_mission_state", _transition)
    monkeypatch.setattr(
        orchestrator_main,
        "emit_state_event",
        lambda *_args, **_kwargs: asyncio.sleep(0),
    )
    monkeypatch.setattr(app.state, "redis", _ClosableRedis(), raising=False)
    monkeypatch.setattr(app.state, "protocol_ready", True, raising=False)

    monkeypatch.setattr(
        orchestrator_main.storage,
        "upsert_logicnode",
        lambda *_: {"mission_id": "mission-1", "node_id": "node-1"},
    )
    monkeypatch.setattr(
        orchestrator_main.storage,
        "list_logicnodes",
        lambda *_: [{"mission_id": "mission-1", "node_id": "node-1"}],
    )
    monkeypatch.setattr(
        orchestrator_main.storage,
        "get_pod_assignment",
        lambda *_: {
            "mission_id": "mission-1",
            "pod_name": "podA",
            "metadata": {"source": "test"},
            "assigned_at": "2026-03-01T00:00:00+00:00",
            "updated_at": "2026-03-01T00:00:00+00:00",
        },
    )
    monkeypatch.setattr(
        orchestrator_main.storage,
        "list_mission_events",
        lambda *_: [
            MissionEvent(
                mission_id="mission-1",
                previous_state=MissionState.queued,
                new_state=MissionState.queued,
                event_type="MISSION_CEO_DELEGATED",
                ts="2026-03-01T00:00:00+00:00",
            )
        ],
    )
    monkeypatch.setattr(
        orchestrator_main.storage,
        "upsert_knowledge",
        lambda *_: {"mission_id": "mission-1", "knowledge_id": "k-1"},
    )
    monkeypatch.setattr(
        orchestrator_main.storage,
        "list_knowledge",
        lambda *_: [{"mission_id": "mission-1", "knowledge_id": "k-1"}],
    )
    qdrant_upserts: list[tuple[object, ...]] = []
    milvus_upserts: list[tuple[object, ...]] = []
    neo4j_knowledge_upserts: list[tuple[object, ...]] = []
    neo4j_audit_upserts: list[tuple[object, ...]] = []
    object_storage_writes: list[tuple[object, ...]] = []
    monkeypatch.setattr(
        orchestrator_main.qdrant_store,
        "upsert_knowledge",
        lambda *args: qdrant_upserts.append(args),
    )
    monkeypatch.setattr(
        orchestrator_main.qdrant_store,
        "list_knowledge",
        lambda *_: [{"mission_id": "mission-1", "knowledge_id": "k-qdrant"}],
    )
    monkeypatch.setattr(
        orchestrator_main.milvus_store,
        "upsert_knowledge",
        lambda *args: milvus_upserts.append(args),
    )
    monkeypatch.setattr(
        orchestrator_main.milvus_store,
        "list_knowledge",
        lambda *_: [{"mission_id": "mission-1", "knowledge_id": "k-milvus"}],
    )
    monkeypatch.setattr(
        orchestrator_main.neo4j_store,
        "upsert_knowledge",
        lambda *args: neo4j_knowledge_upserts.append(args),
    )
    monkeypatch.setattr(
        orchestrator_main.neo4j_store,
        "upsert_audit_report",
        lambda *args: neo4j_audit_upserts.append(args),
    )
    monkeypatch.setattr(
        orchestrator_main.object_store,
        "put_audit_report",
        lambda *args: object_storage_writes.append(args),
    )
    monkeypatch.setattr(
        orchestrator_main.neo4j_store,
        "list_mission_graph",
        lambda *_: [
            {
                "relation_type": "HAS_KNOWLEDGE",
                "target_labels": ["Knowledge"],
                "target_properties": {"knowledge_id": "k-1"},
            }
        ],
    )
    monkeypatch.setattr(
        orchestrator_main.object_store,
        "list_audit_artifacts",
        lambda *_: [
            {
                "bucket": "mission-audit-artifacts",
                "key": "missions/mission-1/audit-reports/a-1.json",
                "size_bytes": 123,
                "etag": "etag123",
                "last_modified": "2026-03-03T00:00:00+00:00",
                "url": "http://minio:9000/mission-audit-artifacts/missions/mission-1/audit-reports/a-1.json",
            }
        ],
    )
    monkeypatch.setattr(
        orchestrator_main.storage,
        "upsert_audit_report",
        lambda *_: {"mission_id": "mission-1", "audit_id": "a-1"},
    )
    monkeypatch.setattr(
        orchestrator_main.storage,
        "list_audit_reports",
        lambda *_: [{"mission_id": "mission-1", "audit_id": "a-1"}],
    )
    monkeypatch.setattr(
        orchestrator_main.storage,
        "list_build_artifacts",
        lambda *_: [
            {
                "mission_id": "mission-1",
                "artifact_id": "source-bundle-package",
                "artifact_type": "source_bundle_package",
                "stage": "package",
                "status": "SUCCESS",
                "storage_backend": "database",
                "storage_ref": "database://missions/mission-1/build-artifacts/source-bundle-package",
                "digest_sha256": "abc123",
                "size_bytes": 123,
                "manifest": {"file_count": 1},
                "verification": {"verified": True},
                "build_log": "build complete",
                "artifact_text": None,
                "created_at": "2026-03-01T00:00:00+00:00",
                "updated_at": "2026-03-01T00:00:00+00:00",
            }
        ],
    )
    monkeypatch.setattr(
        orchestrator_main.storage,
        "get_build_artifact",
        lambda *_: {
            "mission_id": "mission-1",
            "artifact_id": "source-bundle-package",
            "artifact_type": "source_bundle_package",
            "stage": "package",
            "status": "SUCCESS",
            "storage_backend": "database",
            "storage_ref": "database://missions/mission-1/build-artifacts/source-bundle-package",
            "digest_sha256": "abc123",
            "size_bytes": 123,
            "manifest": {"file_count": 1},
            "verification": {"verified": True},
            "build_log": "build complete",
            "artifact_text": "## FILE app.py\nprint('a')\n",
            "created_at": "2026-03-01T00:00:00+00:00",
            "updated_at": "2026-03-01T00:00:00+00:00",
        },
    )
    monkeypatch.setattr(
        orchestrator_main.storage,
        "upsert_agent_heartbeat",
        lambda *_: {
            "agent_id": "AGENT-01-PM",
            "state": "RUNNING",
            "queue_depth": 1,
            "workload_pct": 55,
            "active_mission_ids": ["mission-1"],
            "metadata": {"source": "test"},
            "last_heartbeat": "2026-03-01T00:00:00+00:00",
            "updated_at": "2026-03-01T00:00:00+00:00",
            "previous_state": "IDLE",
            "state_changed": True,
        },
    )

    client = TestClient(app)
    conflict = client.post(
        "/missions/mission-1/state",
        headers={"x-api-key": "worker-key"},
        json={"new_state": "FAILED"},
    )
    assert conflict.status_code == 409

    success = client.post(
        "/missions/mission-1/state",
        headers={"x-api-key": "worker-key"},
        json={"new_state": "FAILED"},
    )
    assert success.status_code == 200

    assert (
        client.post(
            "/internal/logicnodes",
            headers={"x-api-key": "worker-key"},
            json={"mission_id": "mission-1", "node_id": "node-1", "node": {"a": 1}},
        ).status_code
        == 200
    )
    assert (
        client.get(
            "/internal/missions/mission-1/logicnodes?limit=5",
            headers={"x-api-key": "worker-key"},
        ).status_code
        == 200
    )
    chain_trace_response = client.get(
        "/internal/missions/mission-1/chain-trace",
        headers={"x-api-key": "worker-key"},
    )
    assert chain_trace_response.status_code == 200
    assert chain_trace_response.json()["mission_id"] == "mission-1"
    assert (
        chain_trace_response.json()["build_artifacts"][0]["artifact_id"]
        == "source-bundle-package"
    )
    assert (
        client.post(
            "/internal/knowledge",
            headers={"x-api-key": "worker-key"},
            json={"mission_id": "mission-1", "knowledge_id": "k-1", "content": {"b": 2}},
        ).status_code
        == 200
    )
    knowledge_response = client.get(
        "/internal/missions/mission-1/knowledge?limit=5",
        headers={"x-api-key": "worker-key"},
    )
    assert knowledge_response.status_code == 200
    assert knowledge_response.json()[0]["knowledge_id"] == "k-qdrant"
    assert qdrant_upserts
    assert milvus_upserts
    assert neo4j_knowledge_upserts
    graph_response = client.get(
        "/internal/missions/mission-1/knowledge-graph?limit=5",
        headers={"x-api-key": "worker-key"},
    )
    assert graph_response.status_code == 200
    assert graph_response.json()[0]["relation_type"] == "HAS_KNOWLEDGE"
    assert (
        client.post(
            "/internal/audit-reports",
            headers={"x-api-key": "worker-key"},
            json={
                "mission_id": "mission-1",
                "audit_id": "a-1",
                "status": "PASS",
                "report": {"score": 1},
            },
        ).status_code
        == 200
    )
    assert neo4j_audit_upserts
    assert object_storage_writes
    assert (
        client.get(
            "/internal/missions/mission-1/audit-reports?limit=5",
            headers={"x-api-key": "worker-key"},
        ).status_code
        == 200
    )
    artifacts_response = client.get(
        "/internal/missions/mission-1/audit-artifacts?limit=5",
        headers={"x-api-key": "worker-key"},
    )
    assert artifacts_response.status_code == 200
    assert artifacts_response.json()[0]["key"].endswith("/a-1.json")
    build_artifacts_response = client.get(
        "/internal/missions/mission-1/build-artifacts?limit=5",
        headers={"x-api-key": "worker-key"},
    )
    assert build_artifacts_response.status_code == 200
    assert build_artifacts_response.json()[0]["artifact_id"] == "source-bundle-package"
    build_artifact_response = client.get(
        "/internal/missions/mission-1/build-artifacts/source-bundle-package",
        headers={"x-api-key": "worker-key"},
    )
    assert build_artifact_response.status_code == 200
    assert build_artifact_response.json()["artifact_text"].startswith("## FILE app.py")
    metrics_response = client.get("/metrics")
    assert metrics_response.status_code == 200
    assert "orchestrator_optional_adapter_mirror_writes_total" in metrics_response.text
    assert "orchestrator_optional_adapter_mirror_write_latency_seconds" in metrics_response.text
    assert (
        client.post(
            "/internal/agents/heartbeat",
            headers={"x-api-key": "worker-key"},
            json={
                "agent_id": "AGENT-01-PM",
                "state": "RUNNING",
                "queue_depth": 1,
                "workload_pct": 55,
                "active_mission_ids": ["mission-1"],
                "metadata": {"source": "test"},
            },
        ).status_code
        == 200
    )


def test_get_knowledge_falls_back_to_postgres_when_qdrant_returns_empty(monkeypatch) -> None:
    monkeypatch.setattr(orchestrator_main, "_ensure_db_ready", _db_ready)
    monkeypatch.setattr(orchestrator_main, "_fetch_existing_mission", _fetch)
    monkeypatch.setattr(orchestrator_main.qdrant_store, "list_knowledge", lambda *_: [])
    monkeypatch.setattr(
        orchestrator_main.storage,
        "list_knowledge",
        lambda *_: [{"mission_id": "mission-1", "knowledge_id": "k-postgres"}],
    )

    client = TestClient(app)
    response = client.get(
        "/internal/missions/mission-1/knowledge?limit=5",
        headers={"x-api-key": "worker-key"},
    )

    assert response.status_code == 200
    assert response.json()[0]["knowledge_id"] == "k-postgres"


def test_get_knowledge_falls_back_to_milvus_when_qdrant_returns_empty(monkeypatch) -> None:
    monkeypatch.setattr(orchestrator_main, "_ensure_db_ready", _db_ready)
    monkeypatch.setattr(orchestrator_main, "_fetch_existing_mission", _fetch)
    monkeypatch.setattr(
        app.state,
        "settings",
        replace(app.state.settings, milvus_enabled=True),
        raising=False,
    )
    monkeypatch.setattr(orchestrator_main.qdrant_store, "list_knowledge", lambda *_: [])
    monkeypatch.setattr(
        orchestrator_main.milvus_store,
        "list_knowledge",
        lambda *_: [{"mission_id": "mission-1", "knowledge_id": "k-milvus"}],
    )
    monkeypatch.setattr(
        orchestrator_main.storage,
        "list_knowledge",
        lambda *_: [{"mission_id": "mission-1", "knowledge_id": "k-postgres"}],
    )

    client = TestClient(app)
    response = client.get(
        "/internal/missions/mission-1/knowledge?limit=5",
        headers={"x-api-key": "worker-key"},
    )

    assert response.status_code == 200
    assert response.json()[0]["knowledge_id"] == "k-milvus"


def test_internal_operations_endpoints(monkeypatch) -> None:
    monkeypatch.setattr(orchestrator_main, "_ensure_db_ready", _db_ready)
    monkeypatch.setattr(orchestrator_main, "_fetch_existing_mission", _fetch)

    async def _runtime_ready(_: object) -> tuple[bool, bool]:
        return True, True

    monkeypatch.setattr(orchestrator_main, "ensure_runtime_ready", _runtime_ready)
    monkeypatch.setattr(
        orchestrator_main.storage,
        "mission_state_counts",
        lambda *_: {"RUNNING": 2, "FAILED": 1},
    )
    monkeypatch.setattr(
        orchestrator_main.storage,
        "list_pod_assignments",
        lambda *_: [
            {
                "mission_id": "mission-1",
                "pod_name": "podA",
                "metadata": {"source": "test"},
                "assigned_at": "2026-03-01T00:00:00+00:00",
                "updated_at": "2026-03-01T00:00:00+00:00",
            }
        ],
    )
    monkeypatch.setattr(
        orchestrator_main.storage,
        "list_recent_mission_events",
        lambda *_: [
            MissionEvent(
                mission_id="mission-1",
                previous_state=MissionState.queued,
                new_state=MissionState.running,
                event_type="MISSION_RUNNING",
                ts="2026-03-01T00:00:00+00:00",
            )
        ],
    )
    monkeypatch.setattr(
        orchestrator_main.storage,
        "list_missions",
        lambda *_: [
            _mission(MissionState.running),
            MissionRecord(
                mission_id="mission-2",
                prompt="Deploy",
                requested_target_language="java",
                metadata={"source": "test"},
                state=MissionState.complete,
                created_at="2026-03-01T00:01:00+00:00",
            ),
        ],
    )
    monkeypatch.setattr(
        orchestrator_main.storage,
        "list_recent_logicnodes",
        lambda *_: [{"mission_id": "mission-1", "node_id": "node-1", "node": {"a": 1}}],
    )
    monkeypatch.setattr(
        orchestrator_main.storage,
        "list_agent_heartbeats",
        lambda *_: [
            {
                "agent_id": "AGENT-01-PM",
                "state": "RUNNING",
                "queue_depth": 1,
                "workload_pct": 55,
                "active_mission_ids": ["mission-1"],
                "metadata": {"source": "test"},
                "last_heartbeat": "2026-03-01T00:00:00+00:00",
                "updated_at": "2026-03-01T00:00:00+00:00",
            }
        ],
    )
    monkeypatch.setattr(
        orchestrator_main.storage,
        "list_recent_agent_events",
        lambda *_: [
            {
                "event_id": 1,
                "agent_id": "AGENT-01-PM",
                "previous_state": "IDLE",
                "new_state": "RUNNING",
                "event_type": "AGENT_STATE_CHANGED",
                "payload": {"queue_depth": 1},
                "created_at": "2026-03-01T00:00:00+00:00",
            }
        ],
    )
    monkeypatch.setattr(
        orchestrator_main.storage,
        "list_logicnodes",
        lambda *_: [{"mission_id": "mission-1", "node_id": "node-2", "node": {"b": 2}}],
    )
    monkeypatch.setattr(
        orchestrator_main.storage,
        "summarize_projects",
        lambda *_: [
            {
                "project_id": "project-sourceA",
                "source": "sourceA",
                "mission_count": 4,
                "failed_count": 1,
                "complete_count": 2,
                "status": "paused",
                "last_updated_at": "2026-03-01T00:00:00+00:00",
            }
        ],
    )

    monkeypatch.setattr(app.state, "protocol_ready", True, raising=False)
    monkeypatch.setattr(app.state, "consumer_task", _RunningTask(), raising=False)

    client = TestClient(app)
    headers = {"x-api-key": "worker-key"}

    summary = client.get("/internal/operations/summary", headers=headers)
    assert summary.status_code == 200
    assert summary.json()["runtime"]["consumer_running"] is True
    assert summary.json()["runtime"]["langgraph_enabled"] is False
    assert summary.json()["runtime"]["langgraph_checkpointer"] == "none"
    assert "lifecycle_recovery_bootstrapped" in summary.json()["runtime"]
    assert "lifecycle_recovery_recovered_count" in summary.json()["runtime"]
    assert summary.json()["pod_assignment_counts"]["podA"] == 1

    agents = client.get(
        "/internal/operations/agents?mission_limit=100&assignment_limit=100&event_limit=100",
        headers=headers,
    )
    assert agents.status_code == 200
    payload = agents.json()
    assert payload["total_agents"] == 38
    assert len(payload["agents"]) == 38
    assert payload["runtime"]["consumer_running"] is True
    assert payload["runtime"]["langgraph_enabled"] is False
    assert payload["runtime"]["langgraph_checkpointer"] == "none"
    assert "lifecycle_recovery_bootstrapped" in payload["runtime"]
    assert "lifecycle_recovery_recovered_count" in payload["runtime"]
    assert any(record["agent_id"] == "AGENT-01-PM" for record in payload["agents"])
    persona_sections = {
        "job_role",
        "education_certifications",
        "traits_skills",
        "methods_procedures",
        "tools",
        "master_instruction",
        "protocol",
        "api_configuration",
        "standards_alignment",
        "evidence_sources",
    }
    assert all("persona_profile" in record for record in payload["agents"])
    assert all(persona_sections.issubset(record["persona_profile"]) for record in payload["agents"])
    master_instructions = {
        record["persona_profile"]["master_instruction"] for record in payload["agents"]
    }
    assert len(master_instructions) == 38
    assert all(record["persona_profile"]["standards_alignment"] for record in payload["agents"])
    assert all(record["persona_profile"]["evidence_sources"] for record in payload["agents"])
    evidence_urls = [
        source["url"]
        for record in payload["agents"]
        for source in record["persona_profile"]["evidence_sources"]
    ]
    assert all(url.startswith("https://") for url in evidence_urls)
    evidence_orgs = {
        source["organization"]
        for record in payload["agents"]
        for source in record["persona_profile"]["evidence_sources"]
    }
    assert {"NIST", "OWASP", "ISO/IEC"}.issubset(evidence_orgs)

    events = client.get("/internal/operations/events?limit=5", headers=headers)
    assert events.status_code == 200
    assert events.json()[0]["event_type"] == "MISSION_RUNNING"

    agent_events = client.get("/internal/operations/agent-events?limit=5", headers=headers)
    assert agent_events.status_code == 200
    assert agent_events.json()[0]["event_type"] == "AGENT_STATE_CHANGED"

    integrations = client.get("/internal/operations/agent-integrations", headers=headers)
    assert integrations.status_code == 200
    integration_payload = integrations.json()
    assert integration_payload["total_agents"] == 38
    assert integration_payload["persona_profile_framework"] == "8-part-v1"
    assert "job_role" in integration_payload["persona_profile_sections"]
    assert "redis" in integration_payload["data_systems"]
    assert "postgresql" in integration_payload["data_systems"]
    assert "qdrant" in integration_payload["implemented_data_plane"]
    assert integration_payload["reserved_data_plane"] == []
    assert "neo4j" in integration_payload["feature_flagged_data_plane"]
    assert "object_storage" in integration_payload["feature_flagged_data_plane"]
    assert "milvus" in integration_payload["feature_flagged_data_plane"]
    assert integration_payload["planned_data_plane"] == []
    assert integration_payload["llm_provider_counts"]["openai"] > 0
    assert integration_payload["llm_provider_counts"]["anthropic"] > 0
    assert integration_payload["llm_provider_counts"]["gemini"] > 0
    assert any(record["agent_id"] == "AGENT-01-PM" for record in integration_payload["agents"])
    assert all("llm_recommendation" in record for record in integration_payload["agents"])
    assert all("persona_profile" in record for record in integration_payload["agents"])
    assert all(
        "evidence_sources" in record["persona_profile"] for record in integration_payload["agents"]
    )

    logicnodes_all = client.get("/internal/operations/logicnodes?limit=5", headers=headers)
    assert logicnodes_all.status_code == 200
    assert logicnodes_all.json()[0]["node_id"] == "node-1"

    logicnodes_mission = client.get(
        "/internal/operations/logicnodes?limit=5&mission_id=mission-1",
        headers=headers,
    )
    assert logicnodes_mission.status_code == 200
    assert logicnodes_mission.json()[0]["node_id"] == "node-2"

    assignments = client.get("/internal/operations/pod-assignments?limit=5", headers=headers)
    assert assignments.status_code == 200
    assert assignments.json()[0]["pod_name"] == "podA"

    projects = client.get("/internal/operations/projects?limit=5", headers=headers)
    assert projects.status_code == 200
    assert projects.json()[0]["project_id"] == "project-sourceA"

    alerts = client.get("/internal/operations/alerts?limit=5", headers=headers)
    assert alerts.status_code == 200
    assert alerts.json()[0]["alert_id"] == "missions-failed-present"


def test_partition_results_endpoint_restarts_lifecycle_when_scaling_complete(monkeypatch) -> None:
    monkeypatch.setattr(orchestrator_main, "_ensure_db_ready", _db_ready)
    monkeypatch.setattr(orchestrator_main, "_fetch_existing_mission", _fetch)

    started: list[str] = []

    monkeypatch.setattr(
        orchestrator_main.storage,
        "record_partition_result",
        lambda *_: MissionRecord(
            mission_id="mission-1",
            prompt="Build API",
            requested_target_language="python",
            metadata={
                "scaling_merge_complete": True,
                "partition_results": {"p0": {"partition_id": "p0"}},
                "merged_partition_result": {"partition_count": 1},
            },
            state=MissionState.running,
            created_at="2026-03-01T00:00:00+00:00",
        ),
    )
    monkeypatch.setattr(
        orchestrator_main,
        "start_lifecycle_task",
        lambda _app, mission_id: started.append(mission_id),
    )

    client = TestClient(app)
    response = client.post(
        "/internal/missions/mission-1/partition-results",
        headers={"x-api-key": "worker-key"},
        json={"partition_id": "p0", "agent_id": "AGENT-14-PYTHON", "instance_index": 0},
    )

    assert response.status_code == 200
    assert response.json()["scaling_complete"] is True
    assert started == ["mission-1"]
