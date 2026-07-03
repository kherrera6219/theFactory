import asyncio
import importlib
import sys
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api-gateway"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

api_gateway_main = importlib.import_module("api_gateway.main")
orchestrator_main = importlib.import_module("orchestrator.main")

api_app = api_gateway_main.app
orchestrator_app = orchestrator_main.app


class FakeRedis:
    def __init__(self) -> None:
        self._kv: dict[str, str] = {}
        self.xadd_calls: list[tuple[str, dict[str, str]]] = []

    async def ping(self) -> bool:
        return True

    async def set(self, key: str, value: str, ex: int | None = None, nx: bool = False) -> bool:
        if nx and key in self._kv:
            return False
        self._kv[key] = value
        return True

    async def get(self, key: str) -> str | None:
        return self._kv.get(key)

    async def delete(self, key: str) -> int:
        return 1 if self._kv.pop(key, None) is not None else 0

    async def xadd(
        self,
        stream: str,
        fields: dict[str, str],
        maxlen: int | None = None,
        approximate: bool = False,
    ) -> str:
        self.xadd_calls.append((stream, fields))
        return f"{len(self.xadd_calls)}-0"

    async def incr(self, key: str) -> int:
        current = int(self._kv.get(key, "0"))
        current += 1
        self._kv[key] = str(current)
        return current

    async def expire(self, key: str, seconds: int) -> bool:
        return True

    async def aclose(self) -> None:
        return None

    async def close(self) -> None:
        return None

    async def xread(self, **_kwargs) -> list[tuple[str, list[tuple[str, dict[str, str]]]]]:
        return []


class FakeTask:
    def __init__(self, *, done: bool = False) -> None:
        self._done = done

    def done(self) -> bool:
        return self._done

    def cancel(self) -> None:
        self._done = True

    def __await__(self):
        async def _cancelled():
            raise asyncio.CancelledError

        return _cancelled().__await__()


def _stub_gateway_create(monkeypatch) -> None:
    async def _proxy_post_internal(path: str, *, json_body: dict[str, Any]) -> dict[str, Any]:
        assert path == "/missions"
        return {
            "mission_id": json_body["mission_id"],
            "prompt": json_body["prompt"],
            "requested_target_language": json_body.get("requested_target_language"),
            "metadata": json_body.get("metadata", {}),
            "state": "QUEUED",
            "created_at": json_body["created_at"],
        }

    monkeypatch.setattr(api_gateway_main, "_proxy_post_internal", _proxy_post_internal)


def test_gateway_idempotency_reuses_initial_result(monkeypatch) -> None:
    fake_redis = FakeRedis()
    _stub_gateway_create(monkeypatch)
    monkeypatch.setattr(api_gateway_main, "GATEWAY_ADMIN_BYPASS", True)
    with TestClient(api_app) as client:
        api_app.state.redis = fake_redis
        api_app.state.redis_ready = True

        payload = {
            "prompt": "Build an API for payments",
            "requested_target_language": "python",
            "metadata": {"source": "test"},
        }
        headers = {"Idempotency-Key": "mission-key-123"}

        first = client.post("/v1/missions", json=payload, headers=headers)
        second = client.post("/v1/missions", json=payload, headers=headers)

        assert first.status_code == 201
        assert second.status_code == 201
        assert first.json()["mission_id"] == second.json()["mission_id"]
        assert len(fake_redis.xadd_calls) == 1


def test_gateway_idempotency_rejects_payload_mismatch(monkeypatch) -> None:
    fake_redis = FakeRedis()
    _stub_gateway_create(monkeypatch)
    monkeypatch.setattr(api_gateway_main, "GATEWAY_ADMIN_BYPASS", True)
    with TestClient(api_app) as client:
        api_app.state.redis = fake_redis
        api_app.state.redis_ready = True

        first_payload = {"prompt": "Build service A", "metadata": {"source": "test"}}
        second_payload = {"prompt": "Build service B", "metadata": {"source": "test"}}
        headers = {"Idempotency-Key": "mission-key-xyz"}

        first = client.post("/v1/missions", json=first_payload, headers=headers)
        second = client.post("/v1/missions", json=second_payload, headers=headers)

        assert first.status_code == 201
        assert second.status_code == 409
        assert "different payload" in second.json()["detail"]


def test_gateway_mission_intake_rejects_non_pm_agent(monkeypatch) -> None:
    fake_redis = FakeRedis()
    _stub_gateway_create(monkeypatch)
    monkeypatch.setattr(api_gateway_main, "GATEWAY_ADMIN_BYPASS", True)
    with TestClient(api_app) as client:
        api_app.state.redis = fake_redis
        api_app.state.redis_ready = True

        response = client.post(
            "/v1/missions",
            json={
                "prompt": "Build service C",
                "requested_target_language": "python",
                "metadata": {"selected_agent_id": "AGENT-02-CEO"},
            },
        )

    assert response.status_code == 422
    assert "must route through AGENT-01-PM" in response.json()["detail"]


def test_gateway_readyz_returns_503_on_dependency_failure(monkeypatch) -> None:
    async def _dependency_status() -> dict[str, bool]:
        return {"orchestrator_healthy": False, "redis_healthy": True}

    monkeypatch.setattr(api_gateway_main, "_dependency_status", _dependency_status)
    client = TestClient(api_app)
    response = client.get("/readyz")
    assert response.status_code == 503
    assert response.json()["detail"]["ready"] is False


def test_gateway_echoes_correlation_id_header(monkeypatch) -> None:
    async def _dependency_status() -> dict[str, bool]:
        return {"orchestrator_healthy": True, "redis_healthy": True}

    monkeypatch.setattr(api_gateway_main, "_dependency_status", _dependency_status)
    client = TestClient(api_app)
    response = client.get("/health", headers={"x-request-id": "gateway-correlation-123"})

    assert response.status_code == 200
    assert response.headers["X-Correlation-Id"] == "gateway-correlation-123"


def test_gateway_stream_state_endpoint(monkeypatch) -> None:
    class StreamRedis(FakeRedis):
        def __init__(self) -> None:
            super().__init__()
            self.read_calls = 0

        async def xread(
            self, **_kwargs
        ) -> list[tuple[str, list[tuple[str, dict[str, str]]]]]:
            self.read_calls += 1
            if self.read_calls == 1:
                return [
                    (
                        "missions.state",
                        [
                            (
                                "1-0",
                                {
                                    "event_type": "MISSION_RUNNING",
                                    "mission_id": "mission-1",
                                    "state": "RUNNING",
                                    "created_at": "2026-03-04T00:00:00+00:00",
                                    "payload": (
                                        '{"mission_id":"mission-1","event_type":"MISSION_RUNNING",'
                                        '"state":"RUNNING"}'
                                    ),
                                    "envelope": (
                                        '{"topic":"fusion.requested","producer":"orchestrator"}'
                                    ),
                                },
                            )
                        ],
                    )
                ]
            raise asyncio.CancelledError

    monkeypatch.setattr(api_gateway_main, "GATEWAY_ADMIN_BYPASS", True)
    stream_redis = StreamRedis()
    with TestClient(api_app) as client:
        api_app.state.redis = stream_redis
        api_app.state.redis_ready = True

        with client.stream(
            "GET",
            "/v1/stream/state?mission_id=mission-1&include_agent_events=false",
        ) as response:
            assert response.status_code == 200
            body = ""
            for chunk in response.iter_text():
                body += chunk
                if "MISSION_RUNNING" in body:
                    break

    assert "event: connected" in body
    assert "event: state_event" in body
    assert "MISSION_RUNNING" in body


def test_gateway_stream_state_endpoint_requires_redis(monkeypatch) -> None:
    monkeypatch.setattr(api_gateway_main, "GATEWAY_ADMIN_BYPASS", True)
    with TestClient(api_app) as client:
        api_app.state.redis = None
        api_app.state.redis_ready = False

        response = client.get("/v1/stream/state")

    assert response.status_code == 503
    assert "redis dependency is not installed" in response.json()["detail"]


def test_orchestrator_echoes_correlation_id_header(monkeypatch) -> None:
    async def _runtime_ready(_: object) -> tuple[bool, bool]:
        return True, True

    monkeypatch.setattr(orchestrator_main, "ensure_runtime_ready", _runtime_ready)
    monkeypatch.setattr(orchestrator_main.storage, "count_missions", lambda *_: 0)
    client = TestClient(orchestrator_app)
    response = client.get("/health", headers={"x-request-id": "orchestrator-correlation-123"})

    assert response.status_code == 200
    assert response.headers["X-Correlation-Id"] == "orchestrator-correlation-123"


def test_gateway_metrics_endpoint_exposes_prometheus_payload() -> None:
    client = TestClient(api_app)
    client.get("/")
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "api_gateway_http_requests_total" in response.text


def test_gateway_adds_security_headers() -> None:
    client = TestClient(api_app)
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "default-src 'none'" in response.headers["Content-Security-Policy"]
    assert response.headers["Cache-Control"] == "no-store"


def test_gateway_rate_limit_blocks_excess_requests(monkeypatch) -> None:
    fake_redis = FakeRedis()
    _stub_gateway_create(monkeypatch)
    monkeypatch.setattr(api_gateway_main, "API_RATE_LIMIT_PER_MINUTE", 1)
    monkeypatch.setattr(api_gateway_main, "GATEWAY_ADMIN_BYPASS", True)
    with TestClient(api_app) as client:
        api_app.state.redis = fake_redis
        api_app.state.redis_ready = True

        payload = {
            "prompt": "Build API once",
            "requested_target_language": "python",
            "metadata": {"source": "test"},
        }
        first = client.post("/v1/missions", json=payload)
        second = client.post("/v1/missions", json=payload)

    assert first.status_code == 201
    assert second.status_code == 429


def test_gateway_builder_preview_offline(monkeypatch) -> None:
    monkeypatch.setattr(api_gateway_main, "LLM_PROVIDER", "offline")
    monkeypatch.setattr(api_gateway_main, "OPENAI_API_KEY", "")
    monkeypatch.setattr(api_gateway_main, "GATEWAY_ADMIN_BYPASS", True)

    with TestClient(api_app) as client:
        response = client.post(
            "/v1/builder/preview",
            json={
                "request": "Add incident trend chart to alerts page",
                "constraints": ["Keep existing routes", "No schema migrations"],
                "view_mode": "desktop",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "offline"
    assert payload["plan"]
    assert payload["diff_summary"]


def test_gateway_builder_preview_openai(monkeypatch) -> None:
    class DummyResponse:
        def __init__(self, status_code: int, payload: dict[str, Any]) -> None:
            self.status_code = status_code
            self._payload = payload

        def json(self) -> dict[str, Any]:
            return self._payload

    class FakeClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(
            self,
            url: str,
            json: dict[str, Any],
            headers: dict[str, str],
        ) -> DummyResponse:
            return DummyResponse(
                200,
                {
                    "output_text": "\n".join(
                        [
                            "Implement builder preview API wiring.",
                            "Add frontend rendering for generated plan sections.",
                            "Cover route behavior with tests.",
                        ]
                    )
                },
            )

    monkeypatch.setattr(api_gateway_main, "LLM_PROVIDER", "openai")
    monkeypatch.setattr(api_gateway_main, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(api_gateway_main.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(api_gateway_main, "GATEWAY_ADMIN_BYPASS", True)

    with TestClient(api_app) as client:
        response = client.post(
            "/v1/builder/preview",
            json={"request": "Wire builder preview end-to-end", "view_mode": "tablet"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "openai"
    assert payload["diff_summary"][0] == "Implement builder preview API wiring."


def test_gateway_builder_helpers_cover_branching() -> None:
    assert api_gateway_main._normalize_builder_text("  keep   this\nclean ") == "keep this clean"
    assert api_gateway_main._collect_distinct_lines("- one\n- one\n* two\nthree", 3) == [
        "one",
        "two",
        "three",
    ]

    preview_request = api_gateway_main.BuilderPreviewRequest(
        request="Implement mission review workflow",
        constraints=["No schema changes", "Keep backward compatibility"],
        view_mode="mobile",
    )
    preview = api_gateway_main._build_offline_builder_preview(
        preview_request,
        source="offline",
        notice="offline preview",
    )
    assert preview["source"] == "offline"
    assert preview["notice"] == "offline preview"
    assert preview["plan"]

    extracted_from_output = api_gateway_main._extract_openai_text(
        {
            "output": [
                {
                    "content": [
                        {"text": "first line"},
                        {"text": "second line"},
                    ]
                }
            ]
        }
    )
    assert extracted_from_output == "first line\nsecond line"

    extracted_from_choices = api_gateway_main._extract_openai_text(
        {"choices": [{"message": {"content": "from choices"}}]}
    )
    assert extracted_from_choices == "from choices"

    # Regression: a refusal content block carries its text under "refusal",
    # not "text" -- a refusal-only response used to silently extract to None.
    extracted_from_refusal = api_gateway_main._extract_openai_text(
        {
            "output": [
                {
                    "content": [
                        {"type": "refusal", "refusal": "I can't help with that."},
                    ]
                }
            ]
        }
    )
    assert extracted_from_refusal == "I can't help with that."

    extracted_from_anthropic = api_gateway_main._extract_anthropic_text(
        {
            "content": [
                {"type": "thinking", "text": "internal"},
                {"type": "text", "text": "anthropic line"},
            ]
        }
    )
    assert extracted_from_anthropic == "anthropic line"

    extracted_from_gemini = api_gateway_main._extract_gemini_text(
        {
            "candidates": [
                {"content": {"parts": [{"text": "gemini line one"}, {"text": "line two"}]}}
            ]
        }
    )
    assert extracted_from_gemini == "gemini line one\nline two"
    assert api_gateway_main._is_gemini_3_model("gemini-3-flash-preview") is True
    assert api_gateway_main._is_gemini_3_model("gemini-3.1-pro-preview") is True
    assert api_gateway_main._is_gemini_3_model("gemini-2.5-pro") is False
    # Regression: a hardcoded "3.1-"/"3.5-" prefix allowlist missed plausible
    # future minor releases like "gemini-3.0-pro" and the bare "gemini-3"
    # model id, silently routing them to the legacy thinkingBudget config
    # instead of Gemini 3's thinkingLevel config.
    assert api_gateway_main._is_gemini_3_model("gemini-3.0-pro") is True
    assert api_gateway_main._is_gemini_3_model("gemini-3") is True
    assert api_gateway_main._is_gemini_3_model("gemini-30-ultra") is False
    assert api_gateway_main._to_gemini_thinking_level("minimal") == "low"
    assert api_gateway_main._to_gemini_thinking_level("medium") == "medium"
    assert api_gateway_main._to_gemini_thinking_level("xhigh") == "high"


def test_gateway_builder_preview_openai_missing_key(monkeypatch) -> None:
    monkeypatch.setattr(api_gateway_main, "LLM_PROVIDER", "openai")
    monkeypatch.setattr(api_gateway_main, "OPENAI_API_KEY", "")
    monkeypatch.setattr(api_gateway_main, "GATEWAY_ADMIN_BYPASS", True)

    with TestClient(api_app) as client:
        response = client.post(
            "/v1/builder/preview",
            json={"request": "Add comparison panel to dashboard"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "offline"
    assert "provider not configured" in payload["notice"]


def test_gateway_builder_preview_anthropic_missing_key(monkeypatch) -> None:
    monkeypatch.setattr(api_gateway_main, "LLM_PROVIDER", "anthropic")
    monkeypatch.setattr(api_gateway_main, "ANTHROPIC_API_KEY", "")
    monkeypatch.setattr(api_gateway_main, "GATEWAY_ADMIN_BYPASS", True)

    with TestClient(api_app) as client:
        response = client.post(
            "/v1/builder/preview",
            json={"request": "Add architecture review timeline"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "offline"
    assert "provider not configured" in payload["notice"]


def test_gateway_builder_preview_gemini_missing_key(monkeypatch) -> None:
    monkeypatch.setattr(api_gateway_main, "LLM_PROVIDER", "gemini")
    monkeypatch.setattr(api_gateway_main, "GEMINI_API_KEY", "")
    monkeypatch.setattr(api_gateway_main, "GATEWAY_ADMIN_BYPASS", True)

    with TestClient(api_app) as client:
        response = client.post(
            "/v1/builder/preview",
            json={"request": "Add architecture review timeline"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "offline"
    assert "provider not configured" in payload["notice"]


def test_gateway_builder_preview_openai_fallback(monkeypatch) -> None:
    async def _openai_preview(_payload, **_kwargs) -> None:
        return None

    monkeypatch.setattr(api_gateway_main, "LLM_PROVIDER", "openai")
    monkeypatch.setattr(api_gateway_main, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(api_gateway_main, "_openai_builder_preview", _openai_preview)
    monkeypatch.setattr(api_gateway_main, "GATEWAY_ADMIN_BYPASS", True)

    with TestClient(api_app) as client:
        response = client.post(
            "/v1/builder/preview",
            json={"request": "Generate regression checklist"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "openai-fallback"
    assert "Live LLM request failed" in payload["notice"]


def test_gateway_openai_builder_preview_helper(monkeypatch) -> None:
    class DummyResponse:
        def __init__(self, status_code: int, payload: dict[str, Any]) -> None:
            self.status_code = status_code
            self._payload = payload

        def json(self) -> dict[str, Any]:
            return self._payload

    class FakeClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(
            self,
            url: str,
            json: dict[str, Any],
            headers: dict[str, str],
        ) -> DummyResponse:
            return DummyResponse(
                200,
                {
                    "output": [
                        {
                            "content": [
                                {"text": "Improve validation and data flow."},
                                {"text": "Add endpoint tests for all branches."},
                            ]
                        }
                    ]
                },
            )

    monkeypatch.setattr(api_gateway_main, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(api_gateway_main.httpx, "AsyncClient", FakeClient)

    payload = api_gateway_main.BuilderPreviewRequest(
        request="Design builder endpoint",
        constraints=["No breaking API changes"],
        view_mode="desktop",
    )
    result = asyncio.run(
        api_gateway_main._openai_builder_preview(
            payload,
            model="gpt-5.5",
            reasoning_effort="high",
        )
    )
    assert result is not None
    assert result["source"] == "openai"


def test_gateway_builder_preview_anthropic(monkeypatch) -> None:
    class DummyResponse:
        def __init__(self, status_code: int, payload: dict[str, Any]) -> None:
            self.status_code = status_code
            self._payload = payload

        def json(self) -> dict[str, Any]:
            return self._payload

    class FakeClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(
            self,
            url: str,
            json: dict[str, Any],
            headers: dict[str, str],
        ) -> DummyResponse:
            return DummyResponse(
                200,
                {
                    "content": [
                        {"type": "text", "text": "Build agent assignment dashboard."},
                        {"type": "text", "text": "Add regression tests for route fallback."},
                    ]
                },
            )

    monkeypatch.setattr(api_gateway_main, "LLM_PROVIDER", "anthropic")
    monkeypatch.setattr(api_gateway_main, "ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(api_gateway_main.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(api_gateway_main, "GATEWAY_ADMIN_BYPASS", True)

    with TestClient(api_app) as client:
        response = client.post(
            "/v1/builder/preview",
            json={"request": "Produce rollout plan", "view_mode": "desktop"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "anthropic"
    assert payload["diff_summary"][0] == "Build agent assignment dashboard."


def test_gateway_builder_preview_gemini(monkeypatch) -> None:
    class DummyResponse:
        def __init__(self, status_code: int, payload: dict[str, Any]) -> None:
            self.status_code = status_code
            self._payload = payload

        def json(self) -> dict[str, Any]:
            return self._payload

    class FakeClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(
            self,
            url: str,
            params: dict[str, str],
            json: dict[str, Any],
            headers: dict[str, str],
        ) -> DummyResponse:
            return DummyResponse(
                200,
                {
                    "candidates": [
                        {
                            "content": {
                                "parts": [
                                    {"text": "Create protocol bus review panel."},
                                    {"text": "Keep route contracts unchanged."},
                                ]
                            }
                        }
                    ]
                },
            )

    monkeypatch.setattr(api_gateway_main, "LLM_PROVIDER", "gemini")
    monkeypatch.setattr(api_gateway_main, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(api_gateway_main.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(api_gateway_main, "GATEWAY_ADMIN_BYPASS", True)

    with TestClient(api_app) as client:
        response = client.post(
            "/v1/builder/preview",
            json={"request": "Build semantic panel", "view_mode": "tablet"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "gemini"
    assert payload["diff_summary"][0] == "Create protocol bus review panel."


def test_gateway_internal_operations_routes(monkeypatch) -> None:
    calls: list[tuple[str, dict[str, Any] | None]] = []

    async def _proxy_get_internal(path: str, *, params: dict[str, Any] | None = None) -> Any:
        calls.append((path, params))
        if path in {
            "/internal/operations/summary",
            "/internal/operations/agents",
            "/internal/operations/agent-integrations",
            "/internal/missions/mission-1/pod-assignment",
            "/internal/missions/mission-1/chain-trace",
            "/internal/missions/mission-1/build-artifacts/source-bundle-package",
        }:
            return {"path": path, "ok": True}
        return [{"path": path, "params": params}]

    monkeypatch.setattr(api_gateway_main, "_proxy_get_internal", _proxy_get_internal)
    monkeypatch.setattr(api_gateway_main, "GATEWAY_ADMIN_BYPASS", True)

    with TestClient(api_app) as client:
        assert client.get("/v1/missions/mission-1/pod-assignment").status_code == 200
        assert client.get("/v1/missions/mission-1/chain-trace").status_code == 200
        assert client.get("/v1/missions/mission-1/logicnodes?limit=4").status_code == 200
        assert client.get("/v1/missions/mission-1/knowledge?limit=3").status_code == 200
        assert client.get("/v1/missions/mission-1/knowledge-graph?limit=3").status_code == 200
        assert client.get("/v1/missions/mission-1/audit-reports?limit=2").status_code == 200
        assert client.get("/v1/missions/mission-1/audit-artifacts?limit=2").status_code == 200
        assert client.get("/v1/missions/mission-1/build-artifacts?limit=2").status_code == 200
        assert (
            client.get("/v1/missions/mission-1/build-artifacts/source-bundle-package").status_code
            == 200
        )

        assert client.get("/v1/operations/summary").status_code == 200
        assert (
            client.get(
                "/v1/operations/agents?mission_limit=120&assignment_limit=80&event_limit=60"
            ).status_code
            == 200
        )
        assert client.get("/v1/operations/events?limit=10").status_code == 200
        assert client.get("/v1/operations/agent-events?limit=11").status_code == 200
        assert client.get("/v1/operations/agent-integrations").status_code == 200
        assert (
            client.get("/v1/operations/logicnodes?limit=9&mission_id=mission-1").status_code
            == 200
        )
        assert client.get("/v1/operations/pod-assignments?limit=8").status_code == 200
        assert client.get("/v1/operations/projects?limit=7").status_code == 200
        assert client.get("/v1/operations/alerts?limit=6").status_code == 200

    assert ("/internal/missions/mission-1/pod-assignment", None) in calls
    assert ("/internal/missions/mission-1/chain-trace", None) in calls
    assert ("/internal/missions/mission-1/logicnodes", {"limit": 4}) in calls
    assert ("/internal/missions/mission-1/knowledge", {"limit": 3}) in calls
    assert ("/internal/missions/mission-1/knowledge-graph", {"limit": 3}) in calls
    assert ("/internal/missions/mission-1/audit-reports", {"limit": 2}) in calls
    assert ("/internal/missions/mission-1/audit-artifacts", {"limit": 2}) in calls
    assert ("/internal/missions/mission-1/build-artifacts", {"limit": 2}) in calls
    assert ("/internal/missions/mission-1/build-artifacts/source-bundle-package", None) in calls
    assert ("/internal/operations/summary", None) in calls
    assert (
        "/internal/operations/agents",
        {"mission_limit": 120, "assignment_limit": 80, "event_limit": 60},
    ) in calls
    assert ("/internal/operations/events", {"limit": 10}) in calls
    assert ("/internal/operations/agent-events", {"limit": 11}) in calls
    assert ("/internal/operations/agent-integrations", None) in calls
    assert ("/internal/operations/logicnodes", {"limit": 9, "mission_id": "mission-1"}) in calls
    assert ("/internal/operations/pod-assignments", {"limit": 8}) in calls
    assert ("/internal/operations/projects", {"limit": 7}) in calls
    assert ("/internal/operations/alerts", {"limit": 6}) in calls


def test_orchestrator_readyz_reports_ready(monkeypatch) -> None:
    async def _runtime_ready(_: Any) -> tuple[bool, bool]:
        return True, True

    monkeypatch.setattr(orchestrator_main, "ensure_runtime_ready", _runtime_ready)
    monkeypatch.setattr(orchestrator_main.qdrant_store, "qdrant_ready", lambda *_: True)
    monkeypatch.setattr(orchestrator_main.milvus_store, "milvus_ready", lambda *_: True)
    monkeypatch.setattr(orchestrator_main.neo4j_store, "neo4j_ready", lambda *_: True)
    monkeypatch.setattr(orchestrator_main.object_store, "object_storage_ready", lambda *_: True)
    with TestClient(orchestrator_app) as client:
        orchestrator_app.state.protocol_ready = True
        orchestrator_app.state.consumer_task = FakeTask(done=False)
        response = client.get("/readyz")

    assert response.status_code == 200
    assert response.json()["ready"] is True
    assert response.json()["langgraph_enabled"] is False
    assert response.json()["langgraph_checkpointer"] == "none"
    assert "lifecycle_recovery_bootstrapped" in response.json()
    assert "lifecycle_recovery_recovered_count" in response.json()


def test_orchestrator_readyz_returns_503_when_consumer_not_running(monkeypatch) -> None:
    async def _runtime_ready(_: Any) -> tuple[bool, bool]:
        return True, True

    monkeypatch.setattr(orchestrator_main, "ensure_runtime_ready", _runtime_ready)
    monkeypatch.setattr(orchestrator_main.qdrant_store, "qdrant_ready", lambda *_: True)
    monkeypatch.setattr(orchestrator_main.milvus_store, "milvus_ready", lambda *_: True)
    monkeypatch.setattr(orchestrator_main.neo4j_store, "neo4j_ready", lambda *_: True)
    monkeypatch.setattr(orchestrator_main.object_store, "object_storage_ready", lambda *_: True)
    with TestClient(orchestrator_app) as client:
        orchestrator_app.state.protocol_ready = True
        orchestrator_app.state.consumer_task = FakeTask(done=True)
        response = client.get("/readyz")

    assert response.status_code == 503
    assert response.json()["detail"]["consumer_running"] is False
    assert response.json()["detail"]["langgraph_enabled"] is False
    assert response.json()["detail"]["langgraph_checkpointer"] == "none"
    assert "lifecycle_recovery_bootstrapped" in response.json()["detail"]
    assert "lifecycle_recovery_recovered_count" in response.json()["detail"]
