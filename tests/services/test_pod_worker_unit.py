import asyncio
import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "pod-worker"))

pod_worker_main = importlib.import_module("pod_worker.main")


class DummyResponse:
    def __init__(self, status_code: int, payload: dict[str, Any] | None = None) -> None:
        self.status_code = status_code
        self._payload = payload or {}

    def json(self) -> dict[str, Any]:
        return self._payload


class FakeRedis:
    def __init__(self) -> None:
        self.xadd_calls: list[tuple[str, dict[str, str]]] = []

    async def xadd(self, stream: str, fields: dict[str, str], **kwargs) -> str:
        self.xadd_calls.append((stream, fields))
        return "1-0"


class FakeTask:
    def __init__(self) -> None:
        self.cancel_called = False

    def cancel(self) -> None:
        self.cancel_called = True

    def __await__(self):
        async def _cancelled():
            raise asyncio.CancelledError

        return _cancelled().__await__()


def test_parse_date_time() -> None:
    parsed = pod_worker_main._parse_date_time("2026-03-01T00:00:00Z")
    assert parsed.tzinfo is not None
    with pytest.raises(ValueError):
        pod_worker_main._parse_date_time("2026-03-01T00:00:00")


def test_parse_agent_binding() -> None:
    binding = pod_worker_main._parse_agent_binding("agent-01-pm, AGENT-02-CEO  AGENT-01-PM")
    assert binding == ("AGENT-01-PM", "AGENT-02-CEO")


def test_agent_id_resolution_helpers() -> None:
    assert pod_worker_main._normalize_agent_id(" agent-01-pm ") == "AGENT-01-PM"
    assert pod_worker_main._normalize_agent_id(1) is None

    metadata = {
        "selected_agent_id": "agent-12-poda-mgr",
        "agent": {"id": "AGENT-01-PM"},
    }
    assert pod_worker_main._agent_id_from_metadata(metadata) == "AGENT-12-PODA-MGR"
    assert (
        pod_worker_main._agent_id_from_metadata({"agent": {"id": "agent-01-pm"}})
        == "AGENT-01-PM"
    )
    assert pod_worker_main._agent_id_from_metadata({"agent": "not-a-dict"}) is None
    assert (
        pod_worker_main._agent_id_from_payload({"agent_id": "agent-03-broker"})
        == "AGENT-03-BROKER"
    )
    assert pod_worker_main._agent_id_from_payload({"metadata": metadata}) == "AGENT-12-PODA-MGR"


def test_service_api_key_resolution_prefers_agent_specific_values(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_14_PYTHON_SERVICE_API_KEY", "python-agent-key")
    monkeypatch.setattr(
        pod_worker_main,
        "AGENT_SERVICE_API_KEYS",
        "AGENT-15-JAVASCRIPT=js-agent-key",
    )
    monkeypatch.setattr(pod_worker_main, "AGENT_SERVICE_KEY_MODE", "shared")

    assert pod_worker_main._service_api_key_for_agent("AGENT-14-PYTHON") == "python-agent-key"
    assert pod_worker_main._service_api_key_for_agent("AGENT-15-JAVASCRIPT") == "js-agent-key"
    assert pod_worker_main._service_api_key_for_agent("AGENT-12-PODA-MGR") == "worker-key"


def test_service_api_key_resolution_raises_in_strict_mode(monkeypatch) -> None:
    monkeypatch.delenv("AGENT_14_PYTHON_SERVICE_API_KEY", raising=False)
    monkeypatch.setattr(pod_worker_main, "AGENT_SERVICE_API_KEYS", "")
    monkeypatch.setattr(pod_worker_main, "AGENT_SERVICE_KEY_MODE", "strict")

    with pytest.raises(RuntimeError):
        pod_worker_main._service_api_key_for_agent("AGENT-14-PYTHON")


def test_validate_envelope_and_build(monkeypatch) -> None:
    schema = {
        "required": [
            "event_id",
            "topic",
            "timestamp",
            "producer",
            "correlation_id",
            "payload_ref",
            "schema",
            "priority",
        ],
        "additionalProperties": False,
        "properties": {
            "event_id": {"type": "string"},
            "topic": {"type": "string"},
            "timestamp": {"type": "string"},
            "producer": {"type": "string"},
            "correlation_id": {"type": "string"},
            "payload_ref": {"type": "string", "pattern": "^registry://"},
            "schema": {"type": "string"},
            "priority": {"type": "string", "enum": ["NORMAL", "HIGH"]},
        },
    }
    monkeypatch.setattr(pod_worker_main, "_load_event_schema", lambda: schema)
    monkeypatch.setattr(pod_worker_main, "_load_topics", lambda: {"cluster.assigned.podA"})

    envelope = {
        "event_id": "evt-1",
        "topic": "cluster.assigned.podA",
        "timestamp": "2026-03-01T00:00:00+00:00",
        "producer": "pod-worker-podA",
        "correlation_id": "mission-1",
        "payload_ref": "registry://missions/mission-1",
        "schema": "pod.assignment.v1",
        "priority": "NORMAL",
    }
    pod_worker_main._validate_envelope(envelope)

    envelope["priority"] = "LOW"
    with pytest.raises(pod_worker_main.ProtocolValidationError):
        pod_worker_main._validate_envelope(envelope)

    monkeypatch.setattr(pod_worker_main, "_validate_envelope", lambda e: None)
    built = pod_worker_main._build_envelope(
        "cluster.assigned.podA",
        "mission-1",
        "registry://missions/mission-1",
        "pod.assignment.v1",
    )
    assert built["topic"] == "cluster.assigned.podA"


def test_validate_envelope_failure_paths(monkeypatch) -> None:
    schema = {
        "required": [
            "event_id",
            "topic",
            "timestamp",
            "producer",
            "correlation_id",
            "payload_ref",
            "schema",
            "priority",
        ],
        "additionalProperties": False,
        "properties": {
            "event_id": {"type": "string"},
            "topic": {"type": "string"},
            "timestamp": {"type": "string"},
            "producer": {"type": "string"},
            "correlation_id": {"type": "string"},
            "payload_ref": {"type": "string", "pattern": "^registry://"},
            "schema": {"type": "string"},
            "priority": {"type": "string", "enum": ["NORMAL", "HIGH"]},
        },
    }
    monkeypatch.setattr(pod_worker_main, "_load_event_schema", lambda: schema)
    monkeypatch.setattr(pod_worker_main, "_load_topics", lambda: {"cluster.assigned.podA"})

    envelope = {
        "event_id": "evt-1",
        "topic": "cluster.assigned.podA",
        "timestamp": "2026-03-01T00:00:00+00:00",
        "producer": "pod-worker-podA",
        "correlation_id": "mission-1",
        "payload_ref": "registry://missions/mission-1",
        "schema": "pod.assignment.v1",
        "priority": "NORMAL",
    }

    invalid = dict(envelope)
    invalid["unexpected"] = "value"
    with pytest.raises(pod_worker_main.ProtocolValidationError):
        pod_worker_main._validate_envelope(invalid)

    invalid = dict(envelope)
    invalid["topic"] = "unknown.topic"
    with pytest.raises(pod_worker_main.ProtocolValidationError):
        pod_worker_main._validate_envelope(invalid)

    invalid = dict(envelope)
    invalid["payload_ref"] = "http://bad"
    with pytest.raises(pod_worker_main.ProtocolValidationError):
        pod_worker_main._validate_envelope(invalid)

    invalid = dict(envelope)
    invalid["timestamp"] = "2026-03-01T00:00:00"
    with pytest.raises(pod_worker_main.ProtocolValidationError):
        pod_worker_main._validate_envelope(invalid)

    invalid = dict(envelope)
    invalid["producer"] = 1
    with pytest.raises(pod_worker_main.ProtocolValidationError):
        pod_worker_main._validate_envelope(invalid)


def test_publish_event(monkeypatch) -> None:
    redis_client = FakeRedis()
    monkeypatch.setattr(
        pod_worker_main,
        "_build_envelope",
        lambda **kwargs: {"event_id": "evt-1", "topic": kwargs["topic"]},
    )

    asyncio.run(
        pod_worker_main._publish_event(
            redis_client,
            "cluster.assigned.podA",
            "mission-1",
            {"mission_id": "mission-1"},
        )
    )
    assert redis_client.xadd_calls


def test_ensure_group_busygroup_and_error(monkeypatch) -> None:
    class BusyRedis:
        async def xgroup_create(self, **kwargs):
            raise pod_worker_main.ResponseError("BUSYGROUP already exists")

    asyncio.run(pod_worker_main._ensure_group(BusyRedis()))

    class ErrorRedis:
        async def xgroup_create(self, **kwargs):
            raise pod_worker_main.ResponseError("other error")

    with pytest.raises(pod_worker_main.ResponseError):
        asyncio.run(pod_worker_main._ensure_group(ErrorRedis()))


def test_has_assignment(monkeypatch) -> None:
    async def _not_found(*_args, **_kwargs):
        return DummyResponse(404)

    async def _error(*_args, **_kwargs):
        return DummyResponse(500)

    async def _ok(*_args, **_kwargs):
        return DummyResponse(200, {"pod_name": "podA"})

    monkeypatch.setattr(pod_worker_main, "_request", _not_found)
    assert asyncio.run(pod_worker_main._has_assignment("mission-1")) is False
    monkeypatch.setattr(pod_worker_main, "_request", _error)
    assert asyncio.run(pod_worker_main._has_assignment("mission-1")) is False
    monkeypatch.setattr(pod_worker_main, "_request", _ok)
    assert asyncio.run(pod_worker_main._has_assignment("mission-1")) is True


def test_fetch_mission_agent_id_and_binding_match(monkeypatch) -> None:
    async def _request_ok(*_args, **_kwargs):
        return DummyResponse(200, {"metadata": {"agent_id": "agent-12-poda-mgr"}})

    monkeypatch.setattr(pod_worker_main, "_request", _request_ok)
    assert asyncio.run(pod_worker_main._fetch_mission_agent_id("mission-1")) == "AGENT-12-PODA-MGR"

    async def _request_top_level(*_args, **_kwargs):
        return DummyResponse(200, {"agent_id": "agent-24-podc-mgr"})

    monkeypatch.setattr(pod_worker_main, "_request", _request_top_level)
    assert asyncio.run(pod_worker_main._fetch_mission_agent_id("mission-1")) == "AGENT-24-PODC-MGR"

    monkeypatch.setattr(pod_worker_main, "AGENT_BINDING_SET", frozenset({"AGENT-12-PODA-MGR"}))
    assert (
        asyncio.run(
            pod_worker_main._mission_matches_agent_binding(
                "mission-1",
                {"metadata": {"agent_id": "AGENT-12-PODA-MGR"}},
            )
        )
        is True
    )


def test_mission_binding_mismatch_and_unresolved(monkeypatch) -> None:
    monkeypatch.setattr(pod_worker_main, "AGENT_BINDING_SET", frozenset({"AGENT-12-PODA-MGR"}))

    async def _request_not_found(*_args, **_kwargs):
        return DummyResponse(404)

    monkeypatch.setattr(pod_worker_main, "_request", _request_not_found)
    assert asyncio.run(pod_worker_main._fetch_mission_agent_id("mission-1")) is None
    assert (
        asyncio.run(
            pod_worker_main._mission_matches_agent_binding(
                "mission-1",
                {"metadata": {"agent_id": "AGENT-18-PODB-MGR"}},
            )
        )
        is False
    )
    assert asyncio.run(pod_worker_main._mission_matches_agent_binding("mission-1", {})) is False

    monkeypatch.setattr(pod_worker_main, "AGENT_BINDING_SET", frozenset())
    assert asyncio.run(pod_worker_main._mission_matches_agent_binding("mission-1", {})) is True

    async def _request_not_dict(*_args, **_kwargs):
        return DummyResponse(200, {"items": []})

    class NotDictResponse(DummyResponse):
        def json(self):
            return ["bad-payload"]

    async def _request_bad_json(*_args, **_kwargs):
        return NotDictResponse(200)

    monkeypatch.setattr(pod_worker_main, "_request", _request_not_dict)
    assert asyncio.run(pod_worker_main._fetch_mission_agent_id("mission-1")) is None
    monkeypatch.setattr(pod_worker_main, "_request", _request_bad_json)
    assert asyncio.run(pod_worker_main._fetch_mission_agent_id("mission-1")) is None


def test_request_uses_httpx_client(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    class FakeResponse:
        status_code = 200

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def request(self, *_args, **kwargs):
            captured.update(kwargs)
            return FakeResponse()

    monkeypatch.setattr(pod_worker_main.httpx, "AsyncClient", lambda timeout: FakeClient())
    monkeypatch.setenv("AGENT_14_PYTHON_SERVICE_API_KEY", "python-agent-key")
    response = asyncio.run(
        pod_worker_main._request(
            "POST",
            "/internal/logicnodes",
            json_body={"mission_id": "mission-1"},
            params={"a": 1},
            agent_id="AGENT-14-PYTHON",
        )
    )
    assert response.status_code == 200
    assert captured["headers"]["x-api-key"] == "python-agent-key"
    assert captured["headers"]["x-agent-id"] == "AGENT-14-PYTHON"


def test_request_validation_and_retry_error_paths(monkeypatch) -> None:
    with pytest.raises(ValueError):
        asyncio.run(pod_worker_main._request("GET", "internal/missions"))

    class ErrorClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def request(self, *_args, **_kwargs):
            raise pod_worker_main.httpx.HTTPError("network down")

    monkeypatch.setattr(pod_worker_main.httpx, "AsyncClient", lambda timeout: ErrorClient())
    with pytest.raises(pod_worker_main.httpx.HTTPError):
        asyncio.run(pod_worker_main._request("GET", "/internal/missions/test"))


def test_request_raises_runtime_when_no_attempts(monkeypatch) -> None:
    monkeypatch.setattr(pod_worker_main, "REQUEST_MAX_RETRIES", 0)

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def request(self, *_args, **_kwargs):
            return DummyResponse(200)

    monkeypatch.setattr(pod_worker_main.httpx, "AsyncClient", lambda timeout: FakeClient())
    with pytest.raises(RuntimeError):
        asyncio.run(pod_worker_main._request("GET", "/internal/missions/test"))


def test_request_returns_last_response_after_retryable_statuses(monkeypatch) -> None:
    responses = [DummyResponse(500), DummyResponse(429), DummyResponse(500)]

    class RetryClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def request(self, *_args, **_kwargs):
            return responses.pop(0)

    monkeypatch.setattr(pod_worker_main.httpx, "AsyncClient", lambda timeout: RetryClient())
    monkeypatch.setattr(pod_worker_main, "REQUEST_MAX_RETRIES", 3)
    response = asyncio.run(pod_worker_main._request("GET", "/internal/missions/test"))
    assert response.status_code == 500


def test_request_tracks_internal_auth_rejection(monkeypatch) -> None:
    class AuthRejectedClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def request(self, *_args, **_kwargs):
            return DummyResponse(403, {"detail": "forbidden"})

    monkeypatch.setattr(pod_worker_main.httpx, "AsyncClient", lambda timeout: AuthRejectedClient())
    monkeypatch.setattr(pod_worker_main, "REQUEST_MAX_RETRIES", 1)
    monkeypatch.setattr(pod_worker_main, "INTERNAL_AUTH_FAILURES", 0)
    monkeypatch.setattr(pod_worker_main, "LAST_INTERNAL_AUTH_STATUS", None)

    response = asyncio.run(pod_worker_main._request("GET", "/internal/missions/test"))
    assert response.status_code == 403
    assert pod_worker_main.INTERNAL_AUTH_FAILURES == 1
    assert pod_worker_main.LAST_INTERNAL_AUTH_STATUS == 403


def test_handle_running_mission_branches(monkeypatch) -> None:
    redis_client = FakeRedis()
    payload = {
        "mission_id": "mission-1",
        "requested_target_language": "python",
        "state": "RUNNING",
    }

    async def _has_assignment_false(_mission_id: str) -> bool:
        return False

    calls: list[tuple[str, str]] = []

    async def _request(method: str, path: str, **kwargs):
        calls.append((method, path))
        if path == "/internal/pod-assignment":
            return DummyResponse(200, {"ok": True})
        return DummyResponse(200, {"ok": True})

    published: list[str] = []

    async def _publish(redis_obj, topic: str, mission_id: str, payload_obj: dict[str, Any]):
        published.append(topic)

    monkeypatch.setattr(pod_worker_main, "_has_assignment", _has_assignment_false)
    monkeypatch.setattr(pod_worker_main, "_request", _request)
    monkeypatch.setattr(pod_worker_main, "_publish_event", _publish)
    monkeypatch.setattr(pod_worker_main, "AGENT_BINDING_SET", frozenset())

    asyncio.run(pod_worker_main._handle_running_mission(redis_client, payload))
    assert ("POST", "/internal/pod-assignment") in calls
    assert len(published) == 2

    async def _request_conflict(method: str, path: str, **kwargs):
        if path == "/internal/pod-assignment":
            return DummyResponse(409)
        return DummyResponse(200)

    published.clear()
    monkeypatch.setattr(pod_worker_main, "_request", _request_conflict)
    asyncio.run(pod_worker_main._handle_running_mission(redis_client, payload))
    assert len(published) == 2

    asyncio.run(pod_worker_main._handle_running_mission(redis_client, {"mission_id": ""}))
    asyncio.run(
        pod_worker_main._handle_running_mission(
            redis_client,
            {"mission_id": "mission-1", "requested_target_language": "rust"},
        )
    )

    asyncio.run(
        pod_worker_main._handle_running_mission(
            redis_client,
            {"mission_id": "mission-1"},
        )
    )

    async def _has_assignment_true(_mission_id: str) -> bool:
        return True

    monkeypatch.setattr(pod_worker_main, "_has_assignment", _has_assignment_true)
    published.clear()
    asyncio.run(pod_worker_main._handle_running_mission(redis_client, payload))
    assert len(published) == 2

    async def _request_failure(method: str, path: str, **kwargs):
        if path == "/internal/pod-assignment":
            return DummyResponse(500)
        return DummyResponse(200)

    monkeypatch.setattr(pod_worker_main, "_has_assignment", _has_assignment_false)
    monkeypatch.setattr(pod_worker_main, "_request", _request_failure)
    asyncio.run(pod_worker_main._handle_running_mission(redis_client, payload))


def test_handle_running_mission_skips_empty_target_for_non_default_pod(monkeypatch) -> None:
    redis_client = FakeRedis()
    monkeypatch.setattr(pod_worker_main, "POD_NAME", "podB")
    called = {"has_assignment": False}

    async def _has_assignment(_mission_id: str) -> bool:
        called["has_assignment"] = True
        return False

    monkeypatch.setattr(pod_worker_main, "_has_assignment", _has_assignment)
    monkeypatch.setattr(pod_worker_main, "AGENT_BINDING_SET", frozenset())
    asyncio.run(pod_worker_main._handle_running_mission(redis_client, {"mission_id": "mission-1"}))
    assert called["has_assignment"] is False


def test_handle_running_mission_skips_when_binding_mismatch(monkeypatch) -> None:
    redis_client = FakeRedis()
    monkeypatch.setattr(pod_worker_main, "AGENT_BINDING_SET", frozenset({"AGENT-12-PODA-MGR"}))
    called = {"has_assignment": False}

    async def _has_assignment(_mission_id: str) -> bool:
        called["has_assignment"] = True
        return False

    monkeypatch.setattr(pod_worker_main, "_has_assignment", _has_assignment)
    payload = {
        "mission_id": "mission-1",
        "requested_target_language": "python",
        "metadata": {"agent_id": "AGENT-18-PODB-MGR"},
    }
    asyncio.run(pod_worker_main._handle_running_mission(redis_client, payload))
    assert called["has_assignment"] is False


def test_handle_running_mission_with_source_extraction(monkeypatch) -> None:
    redis_client = FakeRedis()
    payload = {
        "mission_id": "mission-1",
        "requested_target_language": "python",
        "source_code": "def add(a, b):\n    return a + b\n",
        "state": "RUNNING",
    }
    monkeypatch.setattr(pod_worker_main, "AGENT_BINDING_SET", frozenset())

    async def _has_assignment_false(_mission_id: str) -> bool:
        return False

    calls: list[tuple[str, str, dict[str, Any]]] = []

    async def _request(method: str, path: str, **kwargs):
        calls.append((method, path, kwargs))
        if method == "GET" and path == "/internal/missions/mission-1/knowledge":
            return DummyResponse(
                200,
                [
                    {
                        "knowledge_id": "docs.python.bootstrap",
                        "content": {
                            "kind": "bootstrap_documentation",
                            "language": "python",
                            "combined_text": "python docs",
                        },
                    }
                ],
            )
        return DummyResponse(200, {"ok": True})

    published: list[str] = []

    async def _publish(redis_obj, topic: str, mission_id: str, payload_obj: dict[str, Any]):
        _ = redis_obj
        _ = mission_id
        _ = payload_obj
        published.append(topic)

    class FakeConcept:
        concept_id = "dyn-001"
        domain = "list_operations"
        concept = "map_collection"
        intent = "transform"
        confidence = 0.91
        source_line = 1
        evidence = "map pattern"

    class FakeExtractor:
        def extract(
            self,
            source_code: str,
            focus_domains: list[str] | None = None,
            doc_context: str | None = None,
        ):
            _ = source_code
            _ = focus_domains
            assert doc_context == "python docs"
            return SimpleNamespace(
                summary={"language": "python", "concepts_found": 1},
                concepts=[FakeConcept()],
                # Real ExtractionResult always carries a functions list; the
                # stub mirrors that so the UPG-31 signature path is exercised
                # rather than silently skipped.
                functions=[],
            )

    monkeypatch.setattr(pod_worker_main, "_has_assignment", _has_assignment_false)
    monkeypatch.setattr(pod_worker_main, "_request", _request)
    monkeypatch.setattr(pod_worker_main, "_publish_event", _publish)
    monkeypatch.setattr(pod_worker_main, "get_extractor", lambda _language: FakeExtractor())

    asyncio.run(pod_worker_main._handle_running_mission(redis_client, payload))
    assert any(path == "/internal/pod-assignment" for _, path, _ in calls)
    logicnode_calls = [entry for entry in calls if entry[1] == "/internal/logicnodes"]
    assert len(logicnode_calls) == 1
    node_id = logicnode_calls[0][2]["json_body"]["node_id"]
    assert node_id.startswith("podA.")
    assert ".mission-1." in node_id
    assert node_id.endswith(".1")
    assert len(published) == 2


def test_logicnodes_from_extraction_node_id_is_unique_per_occurrence() -> None:
    """Same concept at different files/lines must yield distinct node_ids.

    Regression for the node_id collision where f"{POD}.{concept}.{mission}" caused
    multiple occurrences to collapse to one row via ON CONFLICT upsert.
    """

    def _concept(line: int) -> SimpleNamespace:
        return SimpleNamespace(
            concept_id="dyn-001",
            domain="list_operations",
            concept="map_collection",
            intent="transform",
            confidence=0.91,
            source_line=line,
            evidence="map pattern",
        )

    # Same concept, same line, but two different source files.
    nodes_file_a = pod_worker_main._logicnodes_from_extraction(
        mission_id="mission-1",
        target_language="python",
        extraction_language="python",
        concepts=[_concept(1)],
        source_file="src/a.py",
    )
    nodes_file_b = pod_worker_main._logicnodes_from_extraction(
        mission_id="mission-1",
        target_language="python",
        extraction_language="python",
        concepts=[_concept(1)],
        source_file="src/b.py",
    )
    # Same file, same concept, two different lines.
    nodes_two_lines = pod_worker_main._logicnodes_from_extraction(
        mission_id="mission-1",
        target_language="python",
        extraction_language="python",
        concepts=[_concept(1), _concept(7)],
        source_file="src/a.py",
    )

    id_a = nodes_file_a[0]["node_id"]
    id_b = nodes_file_b[0]["node_id"]
    id_line1, id_line7 = (n["node_id"] for n in nodes_two_lines)

    # Distinct files -> distinct ids; distinct lines -> distinct ids.
    assert id_a != id_b
    assert id_line1 != id_line7
    # Same file + same line -> identical id (deterministic, upsert-safe dedupe).
    assert id_a == id_line1
    # Format remains backwards-compatible: prefix is still POD.concept.mission.*
    assert id_a.startswith("podA.dyn-001.mission-1.")
    assert id_a.endswith(".1")


def test_health_function() -> None:
    class PingRedis:
        async def ping(self) -> bool:
            return True

    pod_worker_main.app.state.redis = PingRedis()
    pod_worker_main.app.state.processed = 3
    pod_worker_main.app.state.errors = 1
    pod_worker_main.INTERNAL_AUTH_FAILURES = 2
    pod_worker_main.LAST_INTERNAL_AUTH_STATUS = 403
    result = asyncio.run(pod_worker_main.health())
    assert result["ok"] is True
    assert result["processed"] == 3
    assert result["internal_auth_failures"] == 2
    assert result["last_internal_auth_status"] == 403
    assert "agent_binding" in result
    assert "agent_service_key_mode" in result
    assert "configured_agent_service_keys" in result


def test_readyz_function() -> None:
    class PingRedis:
        async def ping(self) -> bool:
            return True

    pod_worker_main.app.state.redis = PingRedis()
    result = asyncio.run(pod_worker_main.readyz())
    assert result["ready"] is True


def test_readyz_function_unavailable() -> None:
    class DownRedis:
        async def ping(self) -> bool:
            raise RuntimeError("down")

    pod_worker_main.app.state.redis = DownRedis()
    with pytest.raises(pod_worker_main.HTTPException) as exc:
        asyncio.run(pod_worker_main.readyz())
    assert exc.value.status_code == 503


def test_health_function_handles_ping_exception() -> None:
    class DownRedis:
        async def ping(self) -> bool:
            raise RuntimeError("down")

    pod_worker_main.app.state.redis = DownRedis()
    pod_worker_main.app.state.processed = 1
    pod_worker_main.app.state.errors = 1
    result = asyncio.run(pod_worker_main.health())
    assert result["ok"] is False


def test_readyz_none_and_not_ready() -> None:
    pod_worker_main.app.state.redis = None
    with pytest.raises(pod_worker_main.HTTPException):
        asyncio.run(pod_worker_main.readyz())

    class FalseRedis:
        async def ping(self) -> bool:
            return False

    pod_worker_main.app.state.redis = FalseRedis()
    with pytest.raises(pod_worker_main.HTTPException):
        asyncio.run(pod_worker_main.readyz())


def test_metrics_endpoint() -> None:
    response = asyncio.run(pod_worker_main.metrics())
    assert response.status_code == 200
    assert response.media_type


def test_lifespan_shutdown_paths(monkeypatch) -> None:
    class RedisWithAclose:
        def __init__(self) -> None:
            self.closed = False

        async def ping(self) -> bool:
            return True

        async def aclose(self) -> None:
            self.closed = True

    redis_client = RedisWithAclose()
    fake_task = FakeTask()

    class RedisModule:
        @staticmethod
        def from_url(url: str, decode_responses: bool = True):
            _ = url
            _ = decode_responses
            return redis_client

    async def _ensure_group(_redis):
        return None

    def _create_task(coro):
        coro.close()
        return fake_task

    monkeypatch.setattr(pod_worker_main, "redis", RedisModule)
    monkeypatch.setattr(pod_worker_main, "_ensure_group", _ensure_group)
    monkeypatch.setattr(pod_worker_main.asyncio, "create_task", _create_task)

    app = SimpleNamespace(state=SimpleNamespace())

    async def _run():
        async with pod_worker_main.lifespan(app):
            assert app.state.consumer_task is fake_task

    asyncio.run(_run())
    assert fake_task.cancel_called is True
    assert redis_client.closed is True


def test_lifespan_close_awaitable(monkeypatch) -> None:
    class RedisWithClose:
        def __init__(self) -> None:
            self.closed = False

        async def ping(self) -> bool:
            return True

        def close(self):
            async def _close():
                self.closed = True

            return _close()

    redis_client = RedisWithClose()
    fake_task = FakeTask()

    class RedisModule:
        @staticmethod
        def from_url(url: str, decode_responses: bool = True):
            _ = url
            _ = decode_responses
            return redis_client

    async def _ensure_group(_redis):
        return None

    def _create_task(coro):
        coro.close()
        return fake_task

    monkeypatch.setattr(pod_worker_main, "redis", RedisModule)
    monkeypatch.setattr(pod_worker_main, "_ensure_group", _ensure_group)
    monkeypatch.setattr(pod_worker_main.asyncio, "create_task", _create_task)

    app = SimpleNamespace(state=SimpleNamespace())

    async def _run():
        async with pod_worker_main.lifespan(app):
            pass

    asyncio.run(_run())
    assert redis_client.closed is True


def test_lifespan_shutdown_with_no_task_and_no_close(monkeypatch) -> None:
    class RedisNoClose:
        async def ping(self) -> bool:
            return True

    redis_client = RedisNoClose()

    class RedisModule:
        @staticmethod
        def from_url(url: str, decode_responses: bool = True):
            _ = url
            _ = decode_responses
            return redis_client

    async def _ensure_group(_redis):
        return None

    def _create_task(coro):
        coro.close()
        return None

    monkeypatch.setattr(pod_worker_main, "redis", RedisModule)
    monkeypatch.setattr(pod_worker_main, "_ensure_group", _ensure_group)
    monkeypatch.setattr(pod_worker_main.asyncio, "create_task", _create_task)

    app = SimpleNamespace(state=SimpleNamespace())

    async def _run():
        async with pod_worker_main.lifespan(app):
            assert app.state.consumer_task is None

    asyncio.run(_run())


def test_lifespan_shutdown_with_sync_close(monkeypatch) -> None:
    class RedisSyncClose:
        def __init__(self) -> None:
            self.closed = False

        async def ping(self) -> bool:
            return True

        def close(self) -> None:
            self.closed = True

    redis_client = RedisSyncClose()

    class RedisModule:
        @staticmethod
        def from_url(url: str, decode_responses: bool = True):
            _ = url
            _ = decode_responses
            return redis_client

    async def _ensure_group(_redis):
        return None

    def _create_task(coro):
        coro.close()
        return None

    monkeypatch.setattr(pod_worker_main, "redis", RedisModule)
    monkeypatch.setattr(pod_worker_main, "_ensure_group", _ensure_group)
    monkeypatch.setattr(pod_worker_main.asyncio, "create_task", _create_task)

    app = SimpleNamespace(state=SimpleNamespace())

    async def _run():
        async with pod_worker_main.lifespan(app):
            pass

    asyncio.run(_run())
    assert redis_client.closed is True


def test_loaders_raise_when_files_missing(monkeypatch, tmp_path: Path) -> None:
    missing_schema = tmp_path / "missing-schema.json"
    missing_topics = tmp_path / "missing-topics.yaml"
    monkeypatch.setattr(pod_worker_main, "EVENT_SCHEMA_PATH", missing_schema)
    monkeypatch.setattr(pod_worker_main, "TOPICS_PATH", missing_topics)

    with pytest.raises(pod_worker_main.ProtocolValidationError):
        pod_worker_main._load_event_schema()
    with pytest.raises(pod_worker_main.ProtocolValidationError):
        pod_worker_main._load_topics()


def test_load_topics_rejects_empty_config(monkeypatch, tmp_path: Path) -> None:
    topics_path = tmp_path / "topics.yaml"
    topics_path.write_text("topics:\n  none: true\n", encoding="utf-8")
    monkeypatch.setattr(pod_worker_main, "TOPICS_PATH", topics_path)
    with pytest.raises(pod_worker_main.ProtocolValidationError):
        pod_worker_main._load_topics()


def test_loaders_success_paths(monkeypatch, tmp_path: Path) -> None:
    schema_path = tmp_path / "event.envelope.schema.json"
    topics_path = tmp_path / "topics.yaml"
    schema_path.write_text(json.dumps({"properties": {}}), encoding="utf-8")
    topics_path.write_text(
        "- cluster.assigned.podA\nignored\n- pod.standard.ready\n", encoding="utf-8"
    )
    monkeypatch.setattr(pod_worker_main, "EVENT_SCHEMA_PATH", schema_path)
    monkeypatch.setattr(pod_worker_main, "TOPICS_PATH", topics_path)

    schema = pod_worker_main._load_event_schema()
    topics = pod_worker_main._load_topics()
    assert "properties" in schema
    assert "cluster.assigned.podA" in topics
    assert "pod.standard.ready" in topics


def test_validate_envelope_missing_required_and_additional_properties_allowed(monkeypatch) -> None:
    schema = {
        "required": [
            "event_id",
            "topic",
            "timestamp",
            "producer",
            "correlation_id",
            "payload_ref",
            "schema",
            "priority",
        ],
        "additionalProperties": True,
        "properties": {
            "event_id": {"type": "string"},
            "topic": {"type": "string"},
            "timestamp": {"type": "string"},
            "producer": {"type": "string"},
            "correlation_id": {"type": "string"},
            "payload_ref": {"type": "string", "pattern": "^registry://"},
            "schema": {"type": "string"},
            "priority": {"type": "string", "enum": ["NORMAL", "HIGH"]},
        },
    }
    monkeypatch.setattr(pod_worker_main, "_load_event_schema", lambda: schema)
    monkeypatch.setattr(pod_worker_main, "_load_topics", lambda: {"cluster.assigned.podA"})

    base = {
        "event_id": "evt-1",
        "topic": "cluster.assigned.podA",
        "timestamp": "2026-03-01T00:00:00+00:00",
        "producer": "pod-worker-podA",
        "correlation_id": "mission-1",
        "payload_ref": "registry://missions/mission-1",
        "schema": "pod.assignment.v1",
        "priority": "NORMAL",
    }

    missing = dict(base)
    del missing["event_id"]
    with pytest.raises(pod_worker_main.ProtocolValidationError):
        pod_worker_main._validate_envelope(missing)

    with_extra = dict(base)
    with_extra["unexpected"] = "allowed"
    pod_worker_main._validate_envelope(with_extra)


def test_health_when_redis_not_configured() -> None:
    pod_worker_main.app.state.redis = None
    pod_worker_main.app.state.processed = 0
    pod_worker_main.app.state.errors = 0
    payload = asyncio.run(pod_worker_main.health())
    assert payload["ok"] is False


def test_handle_partition_ready_submits_partition_results(monkeypatch) -> None:
    redis_client = FakeRedis()
    payload = {
        "mission_id": "mission-1",
        "requested_target_language": "python",
        "state": "RUNNING",
        "agent_id": "AGENT-14-PYTHON",
        "partition": {
            "partition_id": "p0-test",
            "instance_index": 0,
            "assigned_items": ["app.py"],
        },
    }
    monkeypatch.setattr(pod_worker_main, "AGENT_BINDING_SET", frozenset())

    async def _matches(_mission_id: str, _payload: dict[str, Any]) -> bool:
        return True

    async def _fetch_snapshot(_mission_id: str) -> dict[str, Any]:
        return {
            "metadata": {
                "source_code": "## FILE app.py\nprint('a')\n\n## FILE other.py\nprint('b')\n",
                "scaling_active": True,
            }
        }

    calls: list[tuple[str, str, dict[str, Any]]] = []

    async def _request(method: str, path: str, **kwargs):
        calls.append((method, path, kwargs))
        if method == "GET" and path == "/internal/missions/mission-1/knowledge":
            return DummyResponse(
                200,
                [
                    {
                        "knowledge_id": "docs.python.bootstrap",
                        "content": {
                            "kind": "bootstrap_documentation",
                            "language": "python",
                            "combined_text": "python docs",
                        },
                    }
                ],
            )
        return DummyResponse(200, {"ok": True})

    published: list[str] = []

    async def _publish(_redis_obj, topic: str, _mission_id: str, _payload_obj: dict[str, Any]):
        published.append(topic)

    class FakeConcept:
        concept_id = "dyn-001"
        domain = "list_operations"
        concept = "map_collection"
        intent = "transform"
        confidence = 0.91
        source_line = 1
        evidence = "map pattern"

    class FakeExtractor:
        def extract(
            self,
            source_code: str,
            focus_domains: list[str] | None = None,
            doc_context: str | None = None,
        ):
            _ = focus_domains
            assert doc_context == "python docs"
            assert "other.py" not in source_code
            return SimpleNamespace(
                summary={"language": "python", "concepts_found": 1},
                concepts=[FakeConcept()],
                # Real ExtractionResult always carries a functions list; the
                # stub mirrors that so the UPG-31 signature path is exercised
                # rather than silently skipped.
                functions=[],
            )

    monkeypatch.setattr(pod_worker_main, "_mission_matches_agent_binding", _matches)
    monkeypatch.setattr(pod_worker_main, "_fetch_mission_snapshot", _fetch_snapshot)
    monkeypatch.setattr(pod_worker_main, "_request", _request)
    monkeypatch.setattr(pod_worker_main, "_publish_event", _publish)
    monkeypatch.setattr(pod_worker_main, "get_extractor", lambda _language: FakeExtractor())

    asyncio.run(pod_worker_main._handle_partition_ready(redis_client, payload))

    partition_posts = [
        entry
        for entry in calls
        if entry[1] == "/internal/missions/mission-1/partition-results"
    ]
    assert len(partition_posts) == 1
    logicnode_posts = [entry for entry in calls if entry[1] == "/internal/logicnodes"]
    assert logicnode_posts
    assert logicnode_posts[0][2]["json_body"]["node_id"].endswith(".p0-test")
    assert published == ["pod.standard.ready"]


def test_fetch_doc_context_includes_repo_summary_and_bounded_chunks(monkeypatch) -> None:
    """Repo ZIP Import Phase 7: specialist context must include repo_summary
    (unfiltered by language) and up to _MAX_REPO_CHUNK_CONTEXT_RECORDS
    repo_source_chunk records, alongside the existing bootstrap_documentation
    behavior."""
    records = [
        {"content": {"kind": "bootstrap_documentation", "language": "python", "combined_text": "python docs"}},
        {"content": {"kind": "bootstrap_documentation", "language": "java", "combined_text": "java docs"}},
        {"content": {"kind": "repo_summary", "combined_text": "Repository: sample. Top languages: Python."}},
        {"content": {"kind": "repo_source_chunk", "path": "app.py", "combined_text": "print('hi')"}},
        {"content": {"kind": "unrelated_kind", "combined_text": "should be ignored"}},
    ]

    async def _request_ok(*_args, **_kwargs):
        return DummyResponse(200, records)

    monkeypatch.setattr(pod_worker_main, "_request", _request_ok)

    context = asyncio.run(pod_worker_main._fetch_doc_context("mission-1", "python"))

    assert context is not None
    assert "python docs" in context
    assert "java docs" not in context  # language-filtered, matches existing behavior
    assert "Repository: sample. Top languages: Python." in context
    assert "print('hi')" in context
    assert "should be ignored" not in context


def test_fetch_doc_context_bounds_repo_chunk_count(monkeypatch) -> None:
    chunk_records = [
        {
            "content": {
                "kind": "repo_source_chunk",
                "path": f"file{i}.py",
                "combined_text": f"chunk-{i}",
            }
        }
        for i in range(pod_worker_main._MAX_REPO_CHUNK_CONTEXT_RECORDS + 5)
    ]

    async def _request_ok(*_args, **_kwargs):
        return DummyResponse(200, chunk_records)

    monkeypatch.setattr(pod_worker_main, "_request", _request_ok)

    context = asyncio.run(pod_worker_main._fetch_doc_context("mission-1", "python"))

    assert context is not None
    included = [f"chunk-{i}" in context for i in range(pod_worker_main._MAX_REPO_CHUNK_CONTEXT_RECORDS + 5)]
    assert sum(included) == pod_worker_main._MAX_REPO_CHUNK_CONTEXT_RECORDS


def test_fetch_doc_context_returns_none_on_error_response(monkeypatch) -> None:
    async def _request_error(*_args, **_kwargs):
        return DummyResponse(500)

    monkeypatch.setattr(pod_worker_main, "_request", _request_error)

    assert asyncio.run(pod_worker_main._fetch_doc_context("mission-1", "python")) is None
