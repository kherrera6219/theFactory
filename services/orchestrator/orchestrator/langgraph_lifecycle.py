from __future__ import annotations

import asyncio
import logging
from typing import Any, TypedDict

from fastapi import FastAPI

from . import storage
from .models import MissionState
from .settings import Settings

LOGGER = logging.getLogger(__name__)

try:
    from langgraph.checkpoint.memory import InMemorySaver
except ModuleNotFoundError:
    InMemorySaver = None

try:
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
except ModuleNotFoundError:
    AsyncPostgresSaver = None

try:
    from langgraph.graph import END, START, StateGraph
except ModuleNotFoundError:
    END = "__langgraph_end__"
    START = "__langgraph_start__"
    StateGraph = None


TRANSITIONS: tuple[tuple[MissionState, MissionState, str], ...] = (
    (MissionState.queued, MissionState.running, "MISSION_RUNNING"),
    (MissionState.running, MissionState.verified, "MISSION_VERIFIED"),
    (MissionState.verified, MissionState.complete, "MISSION_COMPLETE"),
)

_MEMORY_CHECKPOINTER: Any | None = None


class MissionLifecycleState(TypedDict):
    mission_id: str
    halted: bool


def _langgraph_available() -> bool:
    return StateGraph is not None


def _resolve_checkpointer(settings: Settings) -> Any | None:
    global _MEMORY_CHECKPOINTER

    mode = settings.langgraph_checkpointer.strip().lower()
    if mode == "none":
        return None
    if mode == "memory":
        if InMemorySaver is None:
            LOGGER.warning(
                "LANGGRAPH_CHECKPOINTER=memory requested, "
                "but langgraph checkpoint dependency is unavailable"
            )
            return None
        if _MEMORY_CHECKPOINTER is None:
            _MEMORY_CHECKPOINTER = InMemorySaver()
        return _MEMORY_CHECKPOINTER

    LOGGER.warning(
        "Unsupported LANGGRAPH_CHECKPOINTER value '%s'; defaulting to no checkpointer",
        settings.langgraph_checkpointer,
    )
    return None


def _build_graph_config(settings: Settings, mission_id: str) -> dict[str, Any]:
    prefix = settings.langgraph_thread_prefix.strip() or "mission"
    configurable: dict[str, Any] = {"thread_id": f"{prefix}:{mission_id}"}
    if settings.langgraph_checkpoint_namespace:
        configurable["checkpoint_ns"] = settings.langgraph_checkpoint_namespace
    return {"configurable": configurable}


async def maybe_advance_mission_lifecycle(
    *,
    app: FastAPI,
    mission_id: str,
    settings: Settings,
    validator: Any,
    emit_state_event_fn: Any,
) -> bool:
    if not settings.langgraph_enabled:
        return False
    if not _langgraph_available():
        LOGGER.warning("LANGGRAPH_ENABLED=true but langgraph dependency is not installed")
        return False

    async def _run_transition(
        state: MissionLifecycleState,
        expected_state: MissionState,
        new_state: MissionState,
        event_type: str,
    ) -> MissionLifecycleState:
        await asyncio.sleep(settings.transition_step_seconds)
        record = await asyncio.to_thread(
            storage.transition_mission_state,
            settings,
            state["mission_id"],
            expected_state,
            new_state,
            event_type,
        )
        if record is None:
            return {"mission_id": state["mission_id"], "halted": True}

        redis_ready = bool(getattr(app.state, "redis_ready", False))
        redis_client = getattr(app.state, "redis", None)
        if not redis_ready or redis_client is None or validator is None:
            return {"mission_id": state["mission_id"], "halted": False}

        try:
            await emit_state_event_fn(
                settings=settings,
                validator=validator,
                redis_client=redis_client,
                mission=record,
                event_type=event_type,
            )
        except Exception as exc:
            LOGGER.warning(
                "failed to emit transition event %s for mission %s: %s",
                event_type,
                state["mission_id"],
                exc,
            )
        return {"mission_id": state["mission_id"], "halted": False}

    def _route_next(next_node: str):
        def _route(state: MissionLifecycleState) -> str:
            return END if state["halted"] else next_node

        return _route

    def _build_transition_node(index: int):
        expected_state, new_state, event_type = TRANSITIONS[index]

        async def _node(state: MissionLifecycleState) -> MissionLifecycleState:
            return await _run_transition(state, expected_state, new_state, event_type)

        return _node

    workflow = StateGraph(MissionLifecycleState)
    workflow.add_node("queued_to_running", _build_transition_node(0))
    workflow.add_node("running_to_verified", _build_transition_node(1))
    workflow.add_node("verified_to_complete", _build_transition_node(2))
    workflow.add_edge(START, "queued_to_running")
    workflow.add_conditional_edges("queued_to_running", _route_next("running_to_verified"))
    workflow.add_conditional_edges("running_to_verified", _route_next("verified_to_complete"))
    workflow.add_edge("verified_to_complete", END)

    mode = settings.langgraph_checkpointer.strip().lower()

    try:
        initial_state = {"mission_id": mission_id, "halted": False}
        config = _build_graph_config(settings, mission_id)

        if mode == "postgres":
            if AsyncPostgresSaver is None:
                LOGGER.warning(
                    "LANGGRAPH_CHECKPOINTER=postgres requested, "
                    "but langgraph-checkpoint-postgres is not installed"
                )
                return False
            checkpoint_url = settings.langgraph_checkpointer_postgres_url or settings.postgres_url
            async with AsyncPostgresSaver.from_conn_string(checkpoint_url) as checkpointer:
                setup_done = bool(
                    getattr(app.state, "langgraph_postgres_checkpointer_setup_done", False)
                )
                if settings.langgraph_checkpointer_setup and not setup_done:
                    await checkpointer.setup()
                    app.state.langgraph_postgres_checkpointer_setup_done = True
                graph = workflow.compile(checkpointer=checkpointer)
                await graph.ainvoke(initial_state, config=config)
        else:
            graph = workflow.compile(checkpointer=_resolve_checkpointer(settings))
            await graph.ainvoke(initial_state, config=config)

        return True
    except Exception:
        if settings.langgraph_fail_open:
            LOGGER.exception(
                "LangGraph mission lifecycle failed for mission %s; falling back to legacy engine",
                mission_id,
            )
            return False
        raise
