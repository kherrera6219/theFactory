from __future__ import annotations

import asyncio
import logging
from typing import Any, TypedDict

from fastapi import FastAPI

from . import storage
from .llm_delegation import generate_ceo_delegation
from .mission_flow import (
    CEO_AGENT_ID,
    PM_AGENT_ID,
    append_chain_event,
    completion_policy_exempt,
    resolve_pod_manager_agent_id,
    resolve_specialist_agent_id,
    with_chain_defaults,
)
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
RUNNING_PHASE_CHECKPOINT_EVENTS: tuple[str, ...] = (
    "MISSION_GATING",
    "MISSION_FUSION",
)

_MEMORY_CHECKPOINTER: Any | None = None


class MissionLifecycleState(TypedDict):
    mission_id: str
    halted: bool
    delegation: dict[str, Any]


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

    async def _emit_chain_event(
        *,
        mission_id: str,
        mission: Any,
        event_type: str,
        previous_state: MissionState = MissionState.queued,
        new_state: MissionState = MissionState.queued,
    ) -> None:
        await asyncio.to_thread(
            storage.insert_mission_event,
            settings,
            mission_id,
            previous_state,
            new_state,
            event_type,
        )
        redis_ready = bool(getattr(app.state, "redis_ready", False))
        redis_client = getattr(app.state, "redis", None)
        if not redis_ready or redis_client is None or validator is None:
            return
        try:
            await emit_state_event_fn(
                settings=settings,
                validator=validator,
                redis_client=redis_client,
                mission=mission,
                event_type=event_type,
            )
        except Exception as exc:
            LOGGER.warning(
                "failed to emit chain event %s for mission %s: %s",
                event_type,
                mission_id,
                exc,
            )

    async def _ceo_delegate(state: MissionLifecycleState) -> MissionLifecycleState:
        mission = await asyncio.to_thread(storage.fetch_mission, settings, state["mission_id"])
        if mission is None:
            return {"mission_id": state["mission_id"], "halted": True, "delegation": {}}

        metadata = with_chain_defaults(mission.metadata, mission.requested_target_language)
        chain_trace = metadata.get("chain_trace", [])
        existing_types = {
            str(entry.get("event_type", ""))
            for entry in chain_trace
            if isinstance(entry, dict)
        }
        if "MISSION_PM_INTAKE" not in existing_types:
            append_chain_event(
                metadata,
                event_type="MISSION_PM_INTAKE",
                agent_id=PM_AGENT_ID,
                details={"source": "langgraph-normalization"},
            )

        mission_context = {
            "mission_id": mission.mission_id,
            "prompt": mission.prompt,
            "requested_target_language": mission.requested_target_language,
            "source": metadata.get("source"),
        }
        delegation = await generate_ceo_delegation(
            mission_context=mission_context,
            requested_target_language=mission.requested_target_language,
        )
        metadata["ceo_delegation"] = delegation
        append_chain_event(
            metadata,
            event_type="MISSION_CEO_DELEGATED",
            agent_id=CEO_AGENT_ID,
            details={
                "target_agent_id": delegation.get("pod_manager_agent_id"),
                "specialist_agent_id": delegation.get("specialist_agent_id"),
                "source": delegation.get("source"),
                "model_provider": delegation.get("model_provider"),
                "model": delegation.get("model"),
            },
        )
        updated = await asyncio.to_thread(
            storage.update_mission_metadata,
            settings,
            state["mission_id"],
            metadata,
        )
        if updated is None:
            return {"mission_id": state["mission_id"], "halted": True, "delegation": {}}
        await _emit_chain_event(
            mission_id=state["mission_id"],
            mission=updated,
            event_type="MISSION_CEO_DELEGATED",
        )
        return {
            "mission_id": state["mission_id"],
            "halted": False,
            "delegation": delegation,
        }

    async def _pod_manager_delegate(state: MissionLifecycleState) -> MissionLifecycleState:
        mission = await asyncio.to_thread(storage.fetch_mission, settings, state["mission_id"])
        if mission is None:
            return {"mission_id": state["mission_id"], "halted": True, "delegation": {}}

        metadata = with_chain_defaults(mission.metadata, mission.requested_target_language)
        delegation = state.get("delegation") or metadata.get("ceo_delegation") or {}
        pod_manager_agent_id = str(
            delegation.get("pod_manager_agent_id")
            or resolve_pod_manager_agent_id(mission.requested_target_language)
        ).strip().upper()
        specialist_agent_id = str(
            delegation.get("specialist_agent_id")
            or resolve_specialist_agent_id(mission.requested_target_language)
        ).strip().upper()

        metadata["assigned_pod_manager_agent_id"] = pod_manager_agent_id
        metadata["assigned_specialist_agent_id"] = specialist_agent_id
        metadata["selected_agent_id"] = pod_manager_agent_id
        metadata["agent_id"] = pod_manager_agent_id
        append_chain_event(
            metadata,
            event_type="MISSION_POD_MANAGER_ASSIGNED",
            agent_id=pod_manager_agent_id,
            details={"specialist_agent_id": specialist_agent_id},
        )
        append_chain_event(
            metadata,
            event_type="MISSION_SPECIALIST_ASSIGNED",
            agent_id=specialist_agent_id,
            details={"pod_manager_agent_id": pod_manager_agent_id},
        )
        updated = await asyncio.to_thread(
            storage.update_mission_metadata,
            settings,
            state["mission_id"],
            metadata,
        )
        if updated is None:
            return {"mission_id": state["mission_id"], "halted": True, "delegation": {}}
        await _emit_chain_event(
            mission_id=state["mission_id"],
            mission=updated,
            event_type="MISSION_POD_MANAGER_ASSIGNED",
        )
        await _emit_chain_event(
            mission_id=state["mission_id"],
            mission=updated,
            event_type="MISSION_SPECIALIST_ASSIGNED",
        )
        return {
            "mission_id": state["mission_id"],
            "halted": False,
            "delegation": {
                "pod_manager_agent_id": pod_manager_agent_id,
                "specialist_agent_id": specialist_agent_id,
                "source": delegation.get("source", "fallback"),
                "model_provider": delegation.get("model_provider"),
                "model": delegation.get("model"),
            },
        }

    async def _run_transition(
        state: MissionLifecycleState,
        expected_state: MissionState,
        new_state: MissionState,
        event_type: str,
    ) -> MissionLifecycleState:
        if expected_state == MissionState.verified and new_state == MissionState.complete:
            mission = await asyncio.to_thread(storage.fetch_mission, settings, state["mission_id"])
            if mission is None:
                return {"mission_id": state["mission_id"], "halted": True, "delegation": {}}

            if completion_policy_exempt(mission.metadata):
                artifacts_ready = True
                artifact_details: dict[str, Any] = {"policy_exempt": True}
            else:
                assignment = await asyncio.to_thread(
                    storage.get_pod_assignment, settings, state["mission_id"]
                )
                logicnodes = await asyncio.to_thread(
                    storage.list_logicnodes, settings, state["mission_id"], 1
                )
                artifacts_ready = bool(assignment) or bool(logicnodes)
                artifact_details = {
                    "policy_exempt": False,
                    "has_pod_assignment": bool(assignment),
                    "logicnode_count": len(logicnodes),
                }

            if not artifacts_ready:
                metadata = with_chain_defaults(mission.metadata, mission.requested_target_language)
                append_chain_event(
                    metadata,
                    event_type="MISSION_COMPLETION_BLOCKED",
                    agent_id=CEO_AGENT_ID,
                    details=artifact_details,
                )
                updated = await asyncio.to_thread(
                    storage.update_mission_metadata,
                    settings,
                    state["mission_id"],
                    metadata,
                )
                if updated is not None:
                    mission = updated
                await asyncio.to_thread(
                    storage.insert_mission_event,
                    settings,
                    state["mission_id"],
                    MissionState.verified,
                    MissionState.verified,
                    "MISSION_COMPLETION_BLOCKED",
                )
                redis_ready = bool(getattr(app.state, "redis_ready", False))
                redis_client = getattr(app.state, "redis", None)
                if redis_ready and redis_client is not None and validator is not None:
                    try:
                        await emit_state_event_fn(
                            settings=settings,
                            validator=validator,
                            redis_client=redis_client,
                            mission=mission,
                            event_type="MISSION_COMPLETION_BLOCKED",
                        )
                    except Exception as exc:
                        LOGGER.warning(
                            "failed to emit completion block event for mission %s: %s",
                            state["mission_id"],
                            exc,
                        )
                return {
                    "mission_id": state["mission_id"],
                    "halted": True,
                    "delegation": state.get("delegation", {}),
                }

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
            return {
                "mission_id": state["mission_id"],
                "halted": True,
                "delegation": state.get("delegation", {}),
            }

        async def _emit_running_phase_checkpoints() -> None:
            for checkpoint_event_type in RUNNING_PHASE_CHECKPOINT_EVENTS:
                try:
                    await asyncio.to_thread(
                        storage.insert_mission_event,
                        settings,
                        state["mission_id"],
                        MissionState.running,
                        MissionState.running,
                        checkpoint_event_type,
                    )
                except Exception as exc:
                    LOGGER.warning(
                        "failed to persist running checkpoint %s for mission %s: %s",
                        checkpoint_event_type,
                        state["mission_id"],
                        exc,
                    )
                    continue

                redis_ready = bool(getattr(app.state, "redis_ready", False))
                redis_client = getattr(app.state, "redis", None)
                if not redis_ready or redis_client is None or validator is None:
                    continue

                try:
                    await emit_state_event_fn(
                        settings=settings,
                        validator=validator,
                        redis_client=redis_client,
                        mission=record,
                        event_type=checkpoint_event_type,
                    )
                except Exception as exc:
                    LOGGER.warning(
                        "failed to emit running checkpoint %s for mission %s: %s",
                        checkpoint_event_type,
                        state["mission_id"],
                        exc,
                    )

        redis_ready = bool(getattr(app.state, "redis_ready", False))
        redis_client = getattr(app.state, "redis", None)
        if redis_ready and redis_client is not None and validator is not None:
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

        if event_type == "MISSION_RUNNING":
            await _emit_running_phase_checkpoints()
        return {
            "mission_id": state["mission_id"],
            "halted": False,
            "delegation": state.get("delegation", {}),
        }

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
    workflow.add_node("ceo_delegate", _ceo_delegate)
    workflow.add_node("pod_manager_delegate", _pod_manager_delegate)
    workflow.add_node("queued_to_running", _build_transition_node(0))
    workflow.add_node("running_to_verified", _build_transition_node(1))
    workflow.add_node("verified_to_complete", _build_transition_node(2))
    workflow.add_edge(START, "ceo_delegate")
    workflow.add_conditional_edges("ceo_delegate", _route_next("pod_manager_delegate"))
    workflow.add_conditional_edges("pod_manager_delegate", _route_next("queued_to_running"))
    workflow.add_conditional_edges("queued_to_running", _route_next("running_to_verified"))
    workflow.add_conditional_edges("running_to_verified", _route_next("verified_to_complete"))
    workflow.add_edge("verified_to_complete", END)

    mode = settings.langgraph_checkpointer.strip().lower()

    try:
        initial_state = {"mission_id": mission_id, "halted": False, "delegation": {}}
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
