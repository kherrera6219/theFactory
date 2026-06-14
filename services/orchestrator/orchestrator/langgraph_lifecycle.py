from __future__ import annotations

import asyncio
import logging
from typing import Any, TypedDict

from fastapi import FastAPI

from . import build_artifacts as build_artifact_support
from . import storage
from .llm_delegation import (
    generate_ceo_delegation,
    generate_pod_manager_delegation,
    generate_specialist_plan,
)
from .mission_flow import (
    CEO_AGENT_ID,
    PM_AGENT_ID,
    append_chain_event,
    completion_policy_exempt,
    resolve_pod_manager_agent_id,
    resolve_specialist_agent_id,
    with_chain_defaults,
)
from .mission_flow_v2 import V2_TRANSITIONS
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


def _select_transitions(
    settings: Any,
) -> tuple[tuple[MissionState, MissionState, str], ...]:
    """Return v2 or v1.1 transition table based on feature flag."""
    if getattr(settings, "mission_flow_v2_enabled", False):
        return V2_TRANSITIONS
    return TRANSITIONS

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
    # Thread ID is intentionally stable across calls for the same mission_id so
    # LangGraph can resume from the last checkpoint when `maybe_advance_mission_lifecycle`
    # is called multiple times during a mission's lifecycle. Replay safety relies on
    # mission IDs being UUID-v4 values that are never reused — enforced by the
    # `missions` table PRIMARY KEY constraint.
    thread_id = f"{prefix}:{mission_id}"
    LOGGER.debug("LangGraph thread_id=%s for mission %s", thread_id, mission_id)
    configurable: dict[str, Any] = {"thread_id": thread_id}
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
        default_specialist_agent_id = str(
            delegation.get("specialist_agent_id")
            or resolve_specialist_agent_id(mission.requested_target_language)
        ).strip().upper()
        mission_context = {
            "mission_id": mission.mission_id,
            "prompt": mission.prompt,
            "requested_target_language": mission.requested_target_language,
            "source": metadata.get("source"),
            "ceo_delegation": delegation,
        }
        pod_manager_delegation = await generate_pod_manager_delegation(
            mission_context=mission_context,
            requested_target_language=mission.requested_target_language,
            pod_manager_agent_id=pod_manager_agent_id,
            default_specialist_agent_id=default_specialist_agent_id,
        )
        specialist_agent_id = str(
            pod_manager_delegation.get("specialist_agent_id")
            or default_specialist_agent_id
            or resolve_specialist_agent_id(mission.requested_target_language)
        ).strip().upper()

        metadata["assigned_pod_manager_agent_id"] = pod_manager_agent_id
        metadata["assigned_specialist_agent_id"] = specialist_agent_id
        metadata["pod_manager_delegation"] = pod_manager_delegation
        metadata["selected_agent_id"] = pod_manager_agent_id
        metadata["agent_id"] = pod_manager_agent_id
        append_chain_event(
            metadata,
            event_type="MISSION_POD_MANAGER_ASSIGNED",
            agent_id=pod_manager_agent_id,
            details={
                "specialist_agent_id": specialist_agent_id,
                "source": pod_manager_delegation.get("source"),
                "model_provider": pod_manager_delegation.get("model_provider"),
                "model": pod_manager_delegation.get("model"),
            },
        )
        append_chain_event(
            metadata,
            event_type="MISSION_SPECIALIST_ASSIGNED",
            agent_id=specialist_agent_id,
            details={
                "pod_manager_agent_id": pod_manager_agent_id,
                "source": pod_manager_delegation.get("source"),
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
            event_type="MISSION_POD_MANAGER_ASSIGNED",
        )
        await _emit_chain_event(
            mission_id=state["mission_id"],
            mission=updated,
            event_type="MISSION_SPECIALIST_ASSIGNED",
        )
        merged_delegation = dict(delegation) if isinstance(delegation, dict) else {}
        merged_delegation.update(
            {
                "pod_manager_agent_id": pod_manager_agent_id,
                "specialist_agent_id": specialist_agent_id,
                "source": pod_manager_delegation.get("source", merged_delegation.get("source")),
                "model_provider": pod_manager_delegation.get("model_provider"),
                "model": pod_manager_delegation.get("model"),
                "pod_manager_delegation": pod_manager_delegation,
            }
        )
        return {
            "mission_id": state["mission_id"],
            "halted": False,
            "delegation": merged_delegation,
        }

    async def _specialist_plan(state: MissionLifecycleState) -> MissionLifecycleState:
        mission = await asyncio.to_thread(storage.fetch_mission, settings, state["mission_id"])
        if mission is None:
            return {"mission_id": state["mission_id"], "halted": True, "delegation": {}}

        metadata = with_chain_defaults(mission.metadata, mission.requested_target_language)
        delegation = state.get("delegation") or {}
        pod_manager_agent_id = str(
            delegation.get("pod_manager_agent_id")
            or metadata.get("assigned_pod_manager_agent_id")
            or resolve_pod_manager_agent_id(mission.requested_target_language)
        ).strip().upper()
        specialist_agent_id = str(
            delegation.get("specialist_agent_id")
            or metadata.get("assigned_specialist_agent_id")
            or resolve_specialist_agent_id(mission.requested_target_language)
        ).strip().upper()

        mission_context = {
            "mission_id": mission.mission_id,
            "prompt": mission.prompt,
            "requested_target_language": mission.requested_target_language,
            "source": metadata.get("source"),
            "ceo_delegation": metadata.get("ceo_delegation"),
            "pod_manager_delegation": metadata.get("pod_manager_delegation"),
        }
        specialist_plan = await generate_specialist_plan(
            mission_context=mission_context,
            requested_target_language=mission.requested_target_language,
            specialist_agent_id=specialist_agent_id,
            pod_manager_agent_id=pod_manager_agent_id,
        )

        metadata["specialist_plan"] = specialist_plan
        append_chain_event(
            metadata,
            event_type="MISSION_SPECIALIST_PLANNED",
            agent_id=specialist_agent_id,
            details={
                "pod_manager_agent_id": pod_manager_agent_id,
                "source": specialist_plan.get("source"),
                "model_provider": specialist_plan.get("model_provider"),
                "model": specialist_plan.get("model"),
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
            event_type="MISSION_SPECIALIST_PLANNED",
        )

        merged_delegation = dict(delegation) if isinstance(delegation, dict) else {}
        merged_delegation["specialist_plan"] = specialist_plan
        return {
            "mission_id": state["mission_id"],
            "halted": False,
            "delegation": merged_delegation,
        }

    async def _ensure_verified_build_artifact(mission: Any) -> Any:
        if not build_artifact_support.mission_requires_build_artifact(mission.metadata):
            return mission

        artifact_record = build_artifact_support.build_source_bundle_artifact(
            mission_id=mission.mission_id,
            requested_target_language=mission.requested_target_language,
            metadata=mission.metadata if isinstance(mission.metadata, dict) else {},
        )
        await asyncio.to_thread(
            storage.upsert_build_artifact,
            settings,
            mission.mission_id,
            artifact_record["artifact_id"],
            artifact_record["artifact_type"],
            artifact_record["stage"],
            artifact_record["status"],
            artifact_record["storage_backend"],
            artifact_record["storage_ref"],
            artifact_record["digest_sha256"],
            artifact_record["size_bytes"],
            artifact_record["manifest"],
            artifact_record["verification"],
            artifact_record["build_log"],
            artifact_record["artifact_text"],
            artifact_record["created_at"],
        )

        metadata = with_chain_defaults(mission.metadata, mission.requested_target_language)
        selected_agent_id = str(
            metadata.get("selected_agent_id")
            or metadata.get("assigned_specialist_agent_id")
            or CEO_AGENT_ID
        ).strip()
        build_artifact_support.record_build_artifact_metadata(
            metadata,
            agent_id=selected_agent_id or CEO_AGENT_ID,
            artifact_record=artifact_record,
        )
        updated = await asyncio.to_thread(
            storage.update_mission_metadata,
            settings,
            mission.mission_id,
            metadata,
        )
        return updated or mission

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
                build_artifact_required = build_artifact_support.mission_requires_build_artifact(
                    mission.metadata
                )
                build_records = (
                    await asyncio.to_thread(
                        storage.list_build_artifacts,
                        settings,
                        state["mission_id"],
                        10,
                    )
                    if build_artifact_required
                    else []
                )
                has_successful_build = build_artifact_support.has_successful_build_artifact(
                    build_records
                )
                artifacts_ready = (
                    has_successful_build and (bool(assignment) or bool(logicnodes))
                    if build_artifact_required
                    else bool(assignment) or bool(logicnodes)
                )
                artifact_details = {
                    "policy_exempt": False,
                    "build_artifact_required": build_artifact_required,
                    "build_artifact_count": len(build_records),
                    "build_artifact_status": build_artifact_support.latest_build_artifact_status(
                        build_records
                    ),
                    "has_successful_build_artifact": has_successful_build,
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

        if new_state == MissionState.verified:
            try:
                record = await _ensure_verified_build_artifact(record)
            except Exception as exc:
                LOGGER.warning(
                    "failed to package verified build artifact for mission %s: %s",
                    state["mission_id"],
                    exc,
                )

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

    active_transitions = _select_transitions(settings)

    workflow = StateGraph(MissionLifecycleState)
    workflow.add_node("ceo_delegate", _ceo_delegate)
    workflow.add_node("pod_manager_delegate", _pod_manager_delegate)
    workflow.add_node("specialist_plan", _specialist_plan)

    # Build transition nodes dynamically from selected table
    transition_node_names: list[str] = []
    for idx, (expected, new, _evt) in enumerate(active_transitions):
        node_name = f"{expected.value.lower()}_to_{new.value.lower()}"
        transition_node_names.append(node_name)

        def _make_node(
            _idx: int = idx,
            _transitions: Any = active_transitions,
        ):
            async def _node(
                state: MissionLifecycleState,
            ) -> MissionLifecycleState:
                es, ns, et = _transitions[_idx]
                return await _run_transition(state, es, ns, et)
            return _node

        workflow.add_node(node_name, _make_node())

    # Wire edges: start → delegation chain → transitions → end
    workflow.add_edge(START, "ceo_delegate")
    workflow.add_conditional_edges(
        "ceo_delegate", _route_next("pod_manager_delegate")
    )
    workflow.add_conditional_edges(
        "pod_manager_delegate", _route_next("specialist_plan")
    )
    workflow.add_conditional_edges(
        "specialist_plan", _route_next(transition_node_names[0])
    )
    for i, name in enumerate(transition_node_names[:-1]):
        workflow.add_conditional_edges(
            name, _route_next(transition_node_names[i + 1])
        )
    workflow.add_edge(transition_node_names[-1], END)

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
            checkpoint_url = settings.langgraph_checkpointer_postgres_url
            if not checkpoint_url:
                # Falling back to settings.postgres_url would use PgBouncer in
                # transaction-pool mode, which drops session-level advisory locks
                # between statements — silently corrupting checkpoint state.
                # Require an explicit direct-to-Postgres URL instead.
                LOGGER.error(
                    "LANGGRAPH_CHECKPOINTER=postgres requires LANGGRAPH_CHECKPOINTER_POSTGRES_URL "
                    "to be set to a direct Postgres connection string (not PgBouncer). "
                    "Skipping LangGraph lifecycle to avoid silent checkpoint corruption."
                )
                return False
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
