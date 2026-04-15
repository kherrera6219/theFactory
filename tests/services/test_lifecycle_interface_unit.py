"""
Unit tests for lifecycle_interface.py.

Verifies:
  1. get_lifecycle_engine() returns the correct adapter for every flag combination.
  2. All three engine classes satisfy the LifecycleEngine Protocol at runtime.
  3. Engine selection priority: v2 > LangGraph > Legacy.
  4. LegacyV1Engine dispatches the correct event-type strings.
  5. LangGraphEngine falls through to LegacyV1Engine when LangGraph declines.
"""
from __future__ import annotations

import asyncio
import importlib
import sys
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

lifecycle_interface = importlib.import_module("orchestrator.lifecycle_interface")
orchestrator_settings = importlib.import_module("orchestrator.settings")

LifecycleEngine = lifecycle_interface.LifecycleEngine
MissionFlowV2Engine = lifecycle_interface.MissionFlowV2Engine
LangGraphEngine = lifecycle_interface.LangGraphEngine
LegacyV1Engine = lifecycle_interface.LegacyV1Engine
get_lifecycle_engine = lifecycle_interface.get_lifecycle_engine
Settings = orchestrator_settings.Settings


def _settings(**overrides: Any) -> Settings:
    root = ROOT
    base = dict(
        redis_url="redis://redis:6379/0",
        postgres_url="postgresql://postgres:postgres@postgres:5432/ulr",
        intake_stream="missions.intake",
        state_stream="missions.state",
        max_stream_len=1000,
        consumer_group="orchestrator",
        consumer_name="orchestrator-test",
        auto_transition_enabled=True,
        transition_step_seconds=0.0,
        intake_topic="intake.feature_contract.created",
        default_priority="NORMAL",
        producer_name="orchestrator",
        event_schema_path=root / "schemas" / "event.envelope.schema.json",
        topics_path=root / "protocol" / "topics.yaml",
        admin_api_key="admin-key",
        internal_service_api_key="worker-key",
        readonly_api_key="viewer-key",
        extra_api_keys="",
    )
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Protocol satisfaction
# ---------------------------------------------------------------------------


class TestProtocolSatisfaction:
    def test_v2_engine_satisfies_protocol(self):
        assert isinstance(MissionFlowV2Engine(), LifecycleEngine)

    def test_langgraph_engine_satisfies_protocol(self):
        assert isinstance(LangGraphEngine(), LifecycleEngine)

    def test_legacy_engine_satisfies_protocol(self):
        assert isinstance(LegacyV1Engine(), LifecycleEngine)

    def test_all_engines_have_advance_coroutine(self):
        for cls in (MissionFlowV2Engine, LangGraphEngine, LegacyV1Engine):
            engine = cls()
            assert asyncio.iscoroutinefunction(engine.advance), (
                f"{cls.__name__}.advance must be a coroutine function"
            )


# ---------------------------------------------------------------------------
# Factory: flag-driven engine selection
# ---------------------------------------------------------------------------


class TestGetLifecycleEngine:
    def test_v2_enabled_returns_v2_engine(self):
        s = _settings(mission_flow_v2_enabled=True, langgraph_enabled=False)
        assert isinstance(get_lifecycle_engine(s), MissionFlowV2Engine)

    def test_v2_enabled_takes_priority_over_langgraph(self):
        s = _settings(mission_flow_v2_enabled=True, langgraph_enabled=True)
        assert isinstance(get_lifecycle_engine(s), MissionFlowV2Engine)

    def test_v2_disabled_langgraph_enabled_returns_langgraph_engine(self):
        s = _settings(mission_flow_v2_enabled=False, langgraph_enabled=True)
        assert isinstance(get_lifecycle_engine(s), LangGraphEngine)

    def test_both_disabled_returns_legacy_engine(self):
        s = _settings(mission_flow_v2_enabled=False, langgraph_enabled=False)
        assert isinstance(get_lifecycle_engine(s), LegacyV1Engine)

    def test_default_settings_returns_v2_engine(self):
        # mission_flow_v2_enabled defaults to True in Settings
        s = _settings()
        assert isinstance(get_lifecycle_engine(s), MissionFlowV2Engine)


# ---------------------------------------------------------------------------
# MissionFlowV2Engine: delegates to advance_mission_lifecycle_v2
# ---------------------------------------------------------------------------


class TestMissionFlowV2Engine:
    @pytest.mark.asyncio
    async def test_delegates_to_v2_function(self):
        engine = MissionFlowV2Engine()
        app = _make_app(_settings())

        with patch(
            "orchestrator.mission_flow_v2.advance_mission_lifecycle_v2",
            new_callable=AsyncMock,
        ) as mock_v2:
            await engine.advance(app, "mission-abc")

        mock_v2.assert_awaited_once()
        call_kwargs = mock_v2.call_args.kwargs
        assert call_kwargs["mission_id"] == "mission-abc"
        assert call_kwargs["app"] is app


# ---------------------------------------------------------------------------
# LangGraphEngine: falls through to LegacyV1Engine when declined
# ---------------------------------------------------------------------------


class TestLangGraphEngine:
    @pytest.mark.asyncio
    async def test_falls_through_to_legacy_when_declined(self):
        engine = LangGraphEngine()
        app = _make_app(_settings(mission_flow_v2_enabled=False, langgraph_enabled=True))
        legacy_calls: list[tuple[Any, str]] = []

        async def _mock_maybe(*args: Any, **kwargs: Any) -> bool:
            return False  # LangGraph declines

        async def _mock_legacy_advance(self_inner: Any, _app: Any, mid: str) -> None:
            legacy_calls.append((_app, mid))

        with (
            patch(
                "orchestrator.langgraph_lifecycle.maybe_advance_mission_lifecycle",
                new=_mock_maybe,
            ),
            patch.object(LegacyV1Engine, "advance", new=_mock_legacy_advance),
        ):
            await engine.advance(app, "mission-xyz")

        assert len(legacy_calls) == 1
        assert legacy_calls[0][1] == "mission-xyz"

    @pytest.mark.asyncio
    async def test_does_not_call_legacy_when_langgraph_handles(self):
        engine = LangGraphEngine()
        app = _make_app(_settings(mission_flow_v2_enabled=False, langgraph_enabled=True))
        legacy_calls: list[str] = []

        async def _mock_maybe(*args: Any, **kwargs: Any) -> bool:
            return True  # LangGraph handled it

        async def _mock_legacy_advance(self_inner: Any, _app: Any, mid: str) -> None:  # pragma: no cover
            legacy_calls.append(mid)

        with (
            patch(
                "orchestrator.langgraph_lifecycle.maybe_advance_mission_lifecycle",
                new=_mock_maybe,
            ),
            patch.object(LegacyV1Engine, "advance", new=_mock_legacy_advance),
        ):
            await engine.advance(app, "mission-handled")

        assert legacy_calls == []


# ---------------------------------------------------------------------------
# LegacyV1Engine: event-type strings match the original inline code
# ---------------------------------------------------------------------------

LEGACY_EVENT_TYPES = {"MISSION_RUNNING", "MISSION_VERIFIED", "MISSION_COMPLETE"}
LEGACY_COMPLETION_BLOCK_TYPE = "MISSION_COMPLETION_BLOCKED"


class TestLegacyV1Engine:
    """Verify that the extracted LegacyV1Engine uses the same event-type
    strings as the original inline code in runtime.py (regression guard)."""

    def test_transition_event_types_are_canonical(self):
        import ast
        import inspect
        import textwrap

        src = textwrap.dedent(inspect.getsource(LegacyV1Engine.advance))
        tree = ast.parse(src)
        string_constants: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                string_constants.add(node.value)

        for event_type in LEGACY_EVENT_TYPES:
            assert event_type in string_constants, (
                f"LegacyV1Engine.advance is missing event type {event_type!r}"
            )
        assert LEGACY_COMPLETION_BLOCK_TYPE in string_constants

    @pytest.mark.asyncio
    async def test_returns_early_when_prepare_chain_fails(self):
        """If _prepare_mission_chain_for_running returns False, advance returns."""
        engine = LegacyV1Engine()
        app = _make_app(_settings(mission_flow_v2_enabled=False, langgraph_enabled=False))

        transition_calls: list[str] = []

        async def _prepare(*args: Any, **kwargs: Any) -> bool:
            return False

        async def _mock_thread(fn: Any, *a: Any, **kw: Any) -> Any:
            # Record any storage.transition_mission_state calls
            if hasattr(fn, "__name__") and fn.__name__ == "transition_mission_state":
                transition_calls.append("called")
            return None

        import orchestrator.runtime as _rt

        with (
            patch.object(_rt, "_prepare_mission_chain_for_running", new=_prepare),
            patch("asyncio.to_thread", new=_mock_thread),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            await engine.advance(app, "mission-noprepare")

        # transition_mission_state must NOT be called if prepare fails
        assert transition_calls == []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_app(settings: Settings) -> Any:
    """Minimal FastAPI-like app namespace used by lifecycle adapters."""
    from orchestrator.protocol import EnvelopeValidator

    validator = MagicMock(spec=EnvelopeValidator)
    state = SimpleNamespace(
        settings=settings,
        envelope_validator=validator,
        redis_ready=False,
        redis=None,
    )
    app = SimpleNamespace(state=state)
    return app
