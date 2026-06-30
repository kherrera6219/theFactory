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
get_lifecycle_engine_name = lifecycle_interface.get_lifecycle_engine_name
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

    def test_engine_name_matches_selected_engine(self):
        assert get_lifecycle_engine_name(
            _settings(mission_flow_v2_enabled=True, langgraph_enabled=True)
        ) == "mission_flow_v2"
        assert get_lifecycle_engine_name(
            _settings(mission_flow_v2_enabled=False, langgraph_enabled=True)
        ) == "langgraph"
        assert get_lifecycle_engine_name(
            _settings(mission_flow_v2_enabled=False, langgraph_enabled=False)
        ) == "legacy_v1"


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

        async def _mock_legacy_advance(
            self_inner: Any, _app: Any, mid: str
        ) -> None:  # pragma: no cover
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
# Event schema equivalence — item 13
# ---------------------------------------------------------------------------


class TestEventSchemaEquivalence:
    """Assert that all three engine adapters emit events with identical schema.

    Strategy:
      1. Verify each engine routes emissions through the canonical
         ``runtime.emit_state_event`` function (structurally, via AST).
      2. Lock down ``emit_state_event``'s own kwarg signature so a future
         refactor cannot silently change the envelope contract.
      3. Verify that the event-type strings directly present in
         LegacyV1Engine.advance (the only engine that embeds them inline)
         are members of the canonical ``models.EventType`` literal.
    """

    def test_legacy_engine_calls_emit_state_event_directly(self) -> None:
        """LegacyV1Engine.advance must call emit_state_event in its body."""
        import ast as _ast
        import inspect
        import textwrap

        src = textwrap.dedent(inspect.getsource(LegacyV1Engine.advance))
        tree = _ast.parse(src)
        emit_calls = sum(
            1
            for node in _ast.walk(tree)
            if isinstance(node, _ast.Call)
            and isinstance(node.func, _ast.Attribute)
            and node.func.attr == "emit_state_event"
        )
        assert emit_calls > 0, (
            "LegacyV1Engine.advance must call emit_state_event directly; found 0 calls"
        )

    def test_v2_engine_delegates_via_emit_state_event_fn_callback(self) -> None:
        """MissionFlowV2Engine must pass emit_state_event as a callback (kwarg)."""
        import ast as _ast
        import inspect
        import textwrap

        src = textwrap.dedent(inspect.getsource(MissionFlowV2Engine.advance))
        tree = _ast.parse(src)
        # The engine passes emit_state_event as a kwarg named emit_state_event_fn
        emit_fn_kwargs = [
            kw.arg
            for node in _ast.walk(tree)
            if isinstance(node, _ast.Call)
            for kw in node.keywords
            if kw.arg == "emit_state_event_fn"
        ]
        assert len(emit_fn_kwargs) >= 1, (
            "MissionFlowV2Engine.advance must pass emit_state_event_fn= kwarg "
            "to delegate event emission through the canonical function"
        )

    def test_langgraph_engine_delegates_via_emit_state_event_fn_callback(self) -> None:
        """LangGraphEngine must pass emit_state_event as a callback (kwarg)."""
        import ast as _ast
        import inspect
        import textwrap

        src = textwrap.dedent(inspect.getsource(LangGraphEngine.advance))
        tree = _ast.parse(src)
        emit_fn_kwargs = [
            kw.arg
            for node in _ast.walk(tree)
            if isinstance(node, _ast.Call)
            for kw in node.keywords
            if kw.arg == "emit_state_event_fn"
        ]
        assert len(emit_fn_kwargs) >= 1, (
            "LangGraphEngine.advance must pass emit_state_event_fn= kwarg "
            "to delegate event emission through the canonical function"
        )

    def test_emit_state_event_signature_is_canonical(self) -> None:
        """emit_state_event must have the locked-down kwarg schema all engines rely on.

        If this signature changes, all engine adapters must be reviewed.
        """
        import inspect

        import orchestrator.runtime as _rt

        sig = inspect.signature(_rt.emit_state_event)
        params = set(sig.parameters.keys())
        expected = {"settings", "validator", "redis_client", "mission", "event_type"}
        assert params == expected, (
            f"emit_state_event signature changed — engine event schema may diverge. "
            f"Got params={params!r}, expected={expected!r}. "
            "Update all three engine adapters before changing this signature."
        )

    def test_legacy_inline_event_types_are_in_canonical_event_type_set(self) -> None:
        """Event-type string literals in LegacyV1Engine.advance must be valid EventType values."""
        import ast as _ast
        import inspect
        import textwrap
        import typing

        orchestrator_models = importlib.import_module("orchestrator.models")
        valid_event_types: frozenset[str] = frozenset(
            typing.get_args(orchestrator_models.EventType)
        )

        src = textwrap.dedent(inspect.getsource(LegacyV1Engine.advance))
        tree = _ast.parse(src)
        # Collect string constants that look like MISSION_* or AGENT_* event types
        inline_event_types = {
            node.value
            for node in _ast.walk(tree)
            if isinstance(node, _ast.Constant)
            and isinstance(node.value, str)
            and (node.value.startswith("MISSION_") or node.value.startswith("AGENT_"))
        }
        assert inline_event_types, (
            "LegacyV1Engine.advance has no MISSION_*/AGENT_* string literals — "
            "cannot verify event-type schema."
        )
        unknown = inline_event_types - valid_event_types
        assert not unknown, (
            f"LegacyV1Engine.advance uses event types not in models.EventType: {unknown!r}. "
            "Add them to EventType or correct the engine."
        )


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
