import asyncio
import importlib
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

orchestrator_runtime = importlib.import_module("orchestrator.runtime")
orchestrator_settings = importlib.import_module("orchestrator.settings")

runtime = orchestrator_runtime
Settings = orchestrator_settings.Settings


def _settings(**overrides: Any) -> Settings:
    base = dict(
        redis_url="redis://redis:6379/0",
        postgres_url="postgresql://postgres:postgres@postgres:5432/ulr",
        intake_stream="missions.intake",
        state_stream="missions.state",
        max_stream_len=1000,
        consumer_group="orchestrator",
        consumer_name="orchestrator-current",
        auto_transition_enabled=True,
        transition_step_seconds=0.01,
        intake_topic="intake.feature_contract.created",
        default_priority="NORMAL",
        producer_name="orchestrator",
        event_schema_path=ROOT / "schemas" / "event.envelope.schema.json",
        topics_path=ROOT / "protocol" / "topics.yaml",
        admin_api_key="admin-key",
        internal_service_api_key="worker-key",
        readonly_api_key="viewer-key",
        extra_api_keys="operator-key=mutate,read",
        stale_consumer_idle_ms=300_000,
        stale_consumer_reap_interval_seconds=3600,
    )
    base.update(overrides)
    return Settings(**base)


class ReaperRedis:
    def __init__(self, consumers: list[dict[str, Any]]) -> None:
        self._consumers = consumers
        self.xinfo_calls: list[tuple[str, str]] = []
        self.xautoclaim_calls: list[tuple[Any, ...]] = []
        self.delconsumer_calls: list[tuple[str, str, str]] = []

    async def xinfo_consumers(self, stream: str, group: str) -> list[dict[str, Any]]:
        self.xinfo_calls.append((stream, group))
        return self._consumers

    async def xautoclaim(self, stream, group, consumer, **kwargs) -> Any:
        self.xautoclaim_calls.append((stream, group, consumer, kwargs))
        return ("0-0", [], [])

    async def xgroup_delconsumer(self, stream, group, name) -> int:
        self.delconsumer_calls.append((stream, group, name))
        return 0


def test_reap_deletes_idle_consumer_with_no_pending() -> None:
    redis_client = ReaperRedis(
        [{"name": "orchestrator-deadhost", "idle": 600_000, "pending": 0}]
    )
    asyncio.run(runtime.reap_stale_consumers(_settings(), redis_client))

    assert redis_client.delconsumer_calls == [
        ("missions.intake", "orchestrator", "orchestrator-deadhost")
    ]
    assert redis_client.xautoclaim_calls == []


def test_reap_reassigns_then_deletes_consumer_with_pending() -> None:
    redis_client = ReaperRedis(
        [{"name": "orchestrator-deadhost", "idle": 600_000, "pending": 3}]
    )
    asyncio.run(runtime.reap_stale_consumers(_settings(), redis_client))

    assert len(redis_client.xautoclaim_calls) == 1
    stream, group, consumer, kwargs = redis_client.xautoclaim_calls[0]
    assert stream == "missions.intake"
    assert group == "orchestrator"
    assert consumer == "orchestrator-current"
    assert kwargs["min_idle_time"] == 300_000
    assert redis_client.delconsumer_calls == [
        ("missions.intake", "orchestrator", "orchestrator-deadhost")
    ]


def test_reap_leaves_active_consumer_alone() -> None:
    redis_client = ReaperRedis(
        [{"name": "orchestrator-deadhost", "idle": 1000, "pending": 5}]
    )
    asyncio.run(runtime.reap_stale_consumers(_settings(), redis_client))

    assert redis_client.xautoclaim_calls == []
    assert redis_client.delconsumer_calls == []


def test_reap_never_deletes_current_consumer() -> None:
    redis_client = ReaperRedis(
        [{"name": "orchestrator-current", "idle": 600_000, "pending": 0}]
    )
    asyncio.run(runtime.reap_stale_consumers(_settings(), redis_client))

    assert redis_client.delconsumer_calls == []


def test_reap_handles_missing_group() -> None:
    class NoGroupRedis(ReaperRedis):
        async def xinfo_consumers(self, stream: str, group: str):
            raise runtime.ResponseError("NOGROUP no such key")

    redis_client = NoGroupRedis([])
    asyncio.run(runtime.reap_stale_consumers(_settings(), redis_client))
    assert redis_client.delconsumer_calls == []


def test_reap_loop_invokes_reaper_then_sleeps(monkeypatch) -> None:
    redis_client = ReaperRedis(
        [{"name": "orchestrator-deadhost", "idle": 600_000, "pending": 0}]
    )
    app = SimpleNamespace(
        state=SimpleNamespace(
            settings=_settings(),
            redis=redis_client,
            redis_ready=True,
        )
    )

    async def _sleep(_seconds):
        raise asyncio.CancelledError

    monkeypatch.setattr(runtime.asyncio, "sleep", _sleep)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(runtime.stale_consumer_reap_loop(app))

    assert redis_client.delconsumer_calls == [
        ("missions.intake", "orchestrator", "orchestrator-deadhost")
    ]


def test_reap_loop_skips_when_redis_not_ready(monkeypatch) -> None:
    redis_client = ReaperRedis([])
    app = SimpleNamespace(
        state=SimpleNamespace(
            settings=_settings(),
            redis=redis_client,
            redis_ready=False,
        )
    )

    async def _sleep(_seconds):
        raise asyncio.CancelledError

    monkeypatch.setattr(runtime.asyncio, "sleep", _sleep)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(runtime.stale_consumer_reap_loop(app))

    assert redis_client.xinfo_calls == []
