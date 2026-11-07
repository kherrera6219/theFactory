"""Provider keys must live in the Redis vault store, never in Postgres metadata."""

from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import MagicMock, patch

from orchestrator.mission_vault import (
    VAULT_TTL_SECONDS,
    load_vault,
    scrub_intake_payload_raw,
    split_vault,
    store_vault,
    strip_vault,
    vault_key,
)


class FakeRedis:
    def __init__(self) -> None:
        self.data: dict[str, str] = {}
        self.ttl: dict[str, int] = {}

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.data[key] = value
        if ex:
            self.ttl[key] = ex

    async def get(self, key: str) -> str | None:
        return self.data.get(key)

    async def expire(self, key: str, seconds: int) -> None:
        self.ttl[key] = seconds


def test_split_vault_removes_keys_without_mutating_input() -> None:
    original = {"source": "chat", "vault": {"gemini_api_key": "k", "openai_api_key": ""}}
    clean, vault = split_vault(original)
    assert "vault" not in clean and clean["source"] == "chat"
    assert vault == {"gemini_api_key": "k"}
    assert "vault" in original


def test_strip_vault_is_noop_without_vault() -> None:
    meta = {"a": 1}
    assert strip_vault(meta) is meta
    assert strip_vault({"a": 1, "vault": {"x": "y"}}) == {"a": 1}


def test_store_then_load_round_trips_and_sets_ttl() -> None:
    redis = FakeRedis()
    assert asyncio.run(store_vault(redis, "m1", {"gemini_api_key": "k"})) is True
    assert redis.ttl[vault_key("m1")] == VAULT_TTL_SECONDS
    redis.ttl.clear()
    assert asyncio.run(load_vault(redis, "m1")) == {"gemini_api_key": "k"}
    assert redis.ttl[vault_key("m1")] == VAULT_TTL_SECONDS  # refreshed on use


def test_store_skips_empty_vault_and_missing_redis() -> None:
    assert asyncio.run(store_vault(FakeRedis(), "m1", {})) is False
    assert asyncio.run(store_vault(None, "m1", {"k": "v"})) is False
    assert asyncio.run(load_vault(None, "m1")) == {}
    assert asyncio.run(load_vault(FakeRedis(), "absent")) == {}


def test_redis_failure_never_leaks_secret_in_logs(caplog) -> None:
    class Boom(FakeRedis):
        async def set(self, *args, **kwargs):  # type: ignore[override]
            raise RuntimeError("secret-value-123")

    assert asyncio.run(store_vault(Boom(), "m1", {"k": "secret-value-123"})) is False
    assert "secret-value-123" not in caplog.text


def test_metadata_write_paths_strip_the_vault() -> None:
    from orchestrator import storage_missions
    from orchestrator.models import MissionRecord, MissionState

    record = MissionRecord(
        mission_id="m1",
        prompt="build a thing",
        requested_target_language="python",
        metadata={"vault": {"gemini_api_key": "SECRET"}, "source": "t"},
        state=MissionState.queued,
        created_at="2026-01-01T00:00:00+00:00",
    )
    params = storage_missions._mission_upsert_params(record, "1-0")
    assert "SECRET" not in json.dumps(params, default=str)

    cursor = MagicMock()
    cursor.fetchone.return_value = None
    conn = MagicMock()
    conn.__enter__.return_value.cursor.return_value.__enter__.return_value = cursor
    with patch.object(storage_missions, "get_connection", return_value=conn):
        storage_missions.update_mission_metadata(
            MagicMock(), "m1", {"vault": {"gemini_api_key": "SECRET"}}
        )
    assert "SECRET" not in json.dumps(cursor.execute.call_args.args[1], default=str)


def test_migrate_legacy_vaults_scrubs_only_after_redis_store() -> None:
    from orchestrator import runtime

    redis = FakeRedis()
    with patch.object(
        runtime.storage,
        "list_legacy_vaults",
        return_value=[("m1", {"gemini_api_key": "k"}), ("m2", {})],
    ), patch.object(runtime.storage, "scrub_mission_vaults", return_value=2) as scrub:
        result = asyncio.run(runtime.migrate_legacy_vaults(MagicMock(), redis))
    assert result == 2
    assert json.loads(redis.data[vault_key("m1")]) == {"gemini_api_key": "k"}
    assert scrub.call_args.args[1] == ["m1", "m2"]

    # A failed Redis write must keep the keys in the row rather than losing them.
    with patch.object(
        runtime.storage, "list_legacy_vaults", return_value=[("m3", {"gemini_api_key": "k"})]
    ), patch.object(runtime.storage, "scrub_mission_vaults", return_value=0) as scrub:
        asyncio.run(runtime.migrate_legacy_vaults(MagicMock(), None))
    assert scrub.call_args.args[1] == []


def test_scrub_intake_payload_raw_strips_vault_from_metadata_and_top_level() -> None:
    raw = json.dumps(
        {
            "mission_id": "m-dlq",
            "vault": {"openai_api_key": "TOP-SECRET"},
            "metadata": {"source": "chat", "vault": {"gemini_api_key": "META-SECRET"}},
        }
    )
    scrubbed = scrub_intake_payload_raw(raw)
    assert "TOP-SECRET" not in scrubbed
    assert "META-SECRET" not in scrubbed
    parsed = json.loads(scrubbed)
    assert parsed["mission_id"] == "m-dlq"
    assert "vault" not in parsed
    assert "vault" not in parsed["metadata"]
    assert parsed["metadata"]["source"] == "chat"

    assert scrub_intake_payload_raw("") == ""
    assert scrub_intake_payload_raw("{not-json-with-vault}") == "{not-json-with-vault}"
    assert scrub_intake_payload_raw('["vault"]') == '["vault"]'
    clean = json.dumps({"mission_id": "m-clean", "metadata": {"source": "chat"}})
    assert scrub_intake_payload_raw(clean) == clean


def test_gateway_create_mission_stores_vault_out_of_band_and_scrubs_transit(monkeypatch) -> None:
    import importlib
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    if str(root / "services" / "api-gateway") not in sys.path:
        sys.path.insert(0, str(root / "services" / "api-gateway"))
    api_gateway_main = importlib.import_module("api_gateway.main")

    class _GatewayRedis(FakeRedis):
        def __init__(self) -> None:
            super().__init__()
            self.xadd_calls: list[tuple[str, dict[str, str]]] = []

        async def ping(self) -> bool:
            return True

        async def set(
            self, key: str, value: str, ex: int | None = None, nx: bool = False
        ) -> Any:
            if nx and key in self.data:
                return False
            await super().set(key, value, ex=ex)
            return True

        async def xadd(self, stream: str, fields: dict[str, str], **_kwargs: Any) -> str:
            self.xadd_calls.append((stream, fields))
            return "1-0"

    redis_client = _GatewayRedis()
    monkeypatch.setattr(api_gateway_main.app.state, "redis", redis_client, raising=False)
    monkeypatch.setattr(api_gateway_main.app.state, "redis_ready", True, raising=False)
    monkeypatch.setattr(api_gateway_main, "GATEWAY_ADMIN_BYPASS", True)
    captured_upstream: dict[str, Any] = {}

    async def _proxy_post_internal(
        _path: str, *, json_body: dict[str, Any], **_kwargs: Any
    ) -> dict[str, Any]:
        captured_upstream["json_body"] = json_body
        return {
            "mission_id": json_body["mission_id"],
            "prompt": json_body["prompt"],
            "requested_target_language": json_body["requested_target_language"],
            "metadata": json_body["metadata"],
            "project_id": json_body.get("project_id"),
            "state": "QUEUED",
            "created_at": json_body["created_at"],
        }

    monkeypatch.setattr(api_gateway_main, "_proxy_post_internal", _proxy_post_internal)
    payload = api_gateway_main.MissionCreate(
        prompt="Build a secure telemetry collector",
        requested_target_language="python",
        metadata={"source": "chat", "vault": {"gemini_api_key": "GATEWAY-SECRET-999"}},
    )

    record = asyncio.run(
        api_gateway_main.create_mission(payload, idempotency_key="idem-vault-check")
    )

    # 1. Stored in mission-vault:<mission_id>
    assert asyncio.run(load_vault(redis_client, record.mission_id)) == {
        "gemini_api_key": "GATEWAY-SECRET-999"
    }
    # 2. Never leaked to upstream POST /missions body, INTAKE_STREAM, idempotency key, or response
    assert "GATEWAY-SECRET-999" not in json.dumps(captured_upstream["json_body"])
    assert "GATEWAY-SECRET-999" not in json.dumps(redis_client.xadd_calls)
    idem_key = api_gateway_main._idempotency_redis_key("idem-vault-check")
    assert "GATEWAY-SECRET-999" not in redis_client.data[idem_key]
    assert "GATEWAY-SECRET-999" not in json.dumps(record.model_dump(mode="json"))


def test_write_intake_dlq_scrubs_vault_secrets() -> None:
    from orchestrator import runtime
    from orchestrator.settings import load_settings

    captured: list[tuple[str, dict[str, Any]]] = []

    class _DlqRedis:
        async def xadd(self, stream: str, fields: dict[str, Any], **_kwargs: Any) -> str:
            captured.append((stream, fields))
            return "1-0"

    settings = load_settings()
    raw_payload = json.dumps(
        {
            "mission_id": "m-dlq-2",
            "metadata": {"vault": {"anthropic_api_key": "DLQ-SECRET-777"}, "source": "api"},
        }
    )
    asyncio.run(
        runtime._write_intake_dlq(
            settings,
            _DlqRedis(),
            "99-0",
            {"envelope": "{}", "payload": raw_payload},
            "validation failed",
        )
    )
    assert len(captured) == 1
    assert "DLQ-SECRET-777" not in json.dumps(captured[0][1])
    parsed = json.loads(captured[0][1]["payload"])
    assert "vault" not in parsed["metadata"]


def test_orchestrator_artifact_download_and_gateway_evidence_proxy_routes(monkeypatch) -> None:
    import importlib
    import io
    import sys
    import zipfile
    from pathlib import Path
    from types import SimpleNamespace

    from fastapi import Request

    root = Path(__file__).resolve().parents[2]
    if str(root / "services" / "api-gateway") not in sys.path:
        sys.path.insert(0, str(root / "services" / "api-gateway"))
    api_gateway_main = importlib.import_module("api_gateway.main")
    from orchestrator import main as orch_main
    from orchestrator.models import MissionRecord, MissionState
    from orchestrator.routes import missions as orch_missions
    from orchestrator.settings import load_settings

    fake_mission = MissionRecord(
        mission_id="mission-art-1",
        prompt="Build multi-file app",
        requested_target_language="python",
        metadata={},
        state=MissionState.complete,
        created_at="2026-11-06T00:00:00+00:00",
    )
    bundle_text = "## FILE: src/app.py\nprint('ok')\n## FILE: tests/test_app.py\ndef test_ok():\n    assert True\n"
    fake_artifact = {
        "mission_id": "mission-art-1",
        "artifact_id": "art-1",
        "stage": "DELIVERY",
        "artifact_type": "generated_code",
        "language": "python",
        "adapter": "python- toolchain",
        "status": "VERIFIED",
        "exit_code": 0,
        "timed_out": False,
        "command": ["python", "-m", "py_compile"],
        "stdout": "",
        "stderr": "",
        "artifact_path": "src/app.py",
        "artifact_text": bundle_text,
        "verification": {"verified": True},
        "created_at": "2026-11-06T00:00:00+00:00",
    }

    async def _ensure_db_ready(_app: Any) -> tuple[bool, bool]:
        return True, True

    async def _fetch_existing(_app: Any, _mid: str) -> MissionRecord:
        return fake_mission

    monkeypatch.setattr(orch_main, "_ensure_db_ready", _ensure_db_ready)
    monkeypatch.setattr(orch_main, "_fetch_existing_mission", _fetch_existing)
    monkeypatch.setattr(
        orch_missions.storage,
        "list_build_artifacts",
        lambda _s, _m, _l: [fake_artifact],
    )
    fake_app = SimpleNamespace(state=SimpleNamespace(settings=load_settings()))
    fake_req = Request(
        {"type": "http", "method": "GET", "path": "/missions/mission-art-1/artifact", "headers": [], "app": fake_app}
    )

    json_res = asyncio.run(
        orch_missions.download_mission_artifact(
            fake_req, "mission-art-1", artifact_id=None, artifact_type=None, format="json"
        )
    )
    assert json_res.artifact_id == "art-1"

    raw_res = asyncio.run(
        orch_missions.download_mission_artifact(
            fake_req, "mission-art-1", artifact_id=None, artifact_type=None, format="raw"
        )
    )
    assert raw_res.media_type.startswith("text/plain")
    assert b"## FILE: src/app.py" in raw_res.body

    zip_res = asyncio.run(
        orch_missions.download_mission_artifact(
            fake_req, "mission-art-1", artifact_id=None, artifact_type=None, format="zip"
        )
    )
    assert zip_res.media_type == "application/zip"
    with zipfile.ZipFile(io.BytesIO(zip_res.body), "r") as zf:
        names = set(zf.namelist())
        assert {"src/app.py", "tests/test_app.py", "manifest.json"} <= names
        manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
        assert manifest["file_count"] == 2

    # Verify gateway evidence routes proxy to /internal/missions/{id}/...
    proxied_paths: list[str] = []

    async def _fake_proxy_get(path: str, *, params: dict[str, Any] | None = None) -> Any:
        proxied_paths.append(path)
        return []

    monkeypatch.setattr(api_gateway_main, "GATEWAY_ADMIN_BYPASS", True)
    monkeypatch.setattr(api_gateway_main, "_proxy_get_internal", _fake_proxy_get)
    from fastapi.testclient import TestClient

    with TestClient(api_gateway_main.app) as client:
        for suffix in (
            "logicnodes",
            "knowledge",
            "audit-reports",
            "audit-artifacts",
            "audit-events",
            "build-artifacts",
        ):
            resp = client.get(f"/v1/missions/m-1/{suffix}")
            assert resp.status_code == 200
            assert proxied_paths[-1] == f"/internal/missions/m-1/{suffix}"

