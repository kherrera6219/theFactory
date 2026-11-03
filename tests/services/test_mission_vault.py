"""Provider keys must live in the Redis vault store, never in Postgres metadata."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import MagicMock, patch

from orchestrator.mission_vault import (
    VAULT_TTL_SECONDS,
    load_vault,
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
