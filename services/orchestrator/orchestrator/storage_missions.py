"""storage_missions.py — Mission CRUD, state-event log, and partition-result recording."""
from __future__ import annotations

import json
from typing import Any

from .agent_scaling import (
    PartitionResult as ScalingPartitionResult,
)
from .agent_scaling import (
    all_partitions_complete,
    merge_partition_results,
)
from .agent_scaling import (
    record_partition_result as embed_partition_result,
)
from .models import (
    DataClassification,
    DepthMode,
    MissionEvent,
    MissionRecord,
    MissionState,
    MissionType,
    OutputMode,
)
from .project_identity import resolve_project_id, with_project_identity
from .settings import Settings
from .storage_core import _json_to_dict, _to_iso, get_connection, psycopg

FETCH_MISSION_SQL = """
    SELECT
        mission_id,
        prompt,
        requested_target_language,
        metadata_json,
        project_id,
        state,
        created_at
    FROM missions
    WHERE mission_id = %s
"""

UPDATE_MISSION_METADATA_SQL = """
    UPDATE missions
    SET metadata_json = %s::jsonb, project_id = %s, updated_at = NOW()
    WHERE mission_id = %s
    RETURNING
        mission_id,
        prompt,
        requested_target_language,
        metadata_json,
        project_id,
        state,
        created_at
"""

LIST_MISSIONS_SQL = """
    SELECT
        mission_id,
        prompt,
        requested_target_language,
        metadata_json,
        project_id,
        state,
        created_at
    FROM missions
    ORDER BY created_at DESC
    LIMIT %s
"""

LIST_MISSIONS_IN_STATES_SQL = """
    SELECT
        mission_id,
        prompt,
        requested_target_language,
        metadata_json,
        project_id,
        state,
        created_at
    FROM missions
    WHERE state = ANY(%s)
    ORDER BY created_at ASC
    LIMIT %s
"""

TRANSITION_MISSION_STATE_SQL = """
    UPDATE missions
    SET state = %s, updated_at = NOW()
    WHERE mission_id = %s
    RETURNING
        mission_id,
        prompt,
        requested_target_language,
        metadata_json,
        project_id,
        state,
        created_at
"""

TRANSITION_MISSION_STATE_IF_MATCH_SQL = """
    UPDATE missions
    SET state = %s, updated_at = NOW()
    WHERE mission_id = %s AND state = %s
    RETURNING
        mission_id,
        prompt,
        requested_target_language,
        metadata_json,
        project_id,
        state,
        created_at
"""

LOCKED_FETCH_MISSION_SQL = """
    SELECT
        mission_id,
        prompt,
        requested_target_language,
        metadata_json,
        project_id,
        state,
        created_at
    FROM missions
    WHERE mission_id = %s
    FOR UPDATE
"""

LOCKED_UPDATE_MISSION_METADATA_SQL = """
    UPDATE missions
    SET metadata_json = %s::jsonb, project_id = %s, updated_at = NOW()
    WHERE mission_id = %s
    RETURNING
        mission_id,
        prompt,
        requested_target_language,
        metadata_json,
        project_id,
        state,
        created_at
"""


def _charter_fields_from_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """Extract Phase 1 charter enum fields stored in metadata_json."""
    out: dict[str, Any] = {}
    raw_type = metadata.get("__mission_type__")
    raw_depth = metadata.get("__depth_mode__")
    raw_output = metadata.get("__output_mode__")
    raw_class = metadata.get("__data_classification__")
    try:
        out["mission_type"] = MissionType(raw_type) if raw_type else None
    except ValueError:
        out["mission_type"] = None
    try:
        out["depth_mode"] = DepthMode(raw_depth) if raw_depth else None
    except ValueError:
        out["depth_mode"] = None
    try:
        out["output_mode"] = OutputMode(raw_output) if raw_output else None
    except ValueError:
        out["output_mode"] = None
    try:
        out["data_classification"] = DataClassification(raw_class) if raw_class else None
    except ValueError:
        out["data_classification"] = None
    return out


def _embed_charter_fields(metadata: dict[str, Any], record: MissionRecord) -> dict[str, Any]:
    """Write Phase 1 charter enum fields into metadata_json for persistence."""
    if record.mission_type is not None:
        metadata["__mission_type__"] = record.mission_type.value
    if record.depth_mode is not None:
        metadata["__depth_mode__"] = record.depth_mode.value
    if record.output_mode is not None:
        metadata["__output_mode__"] = record.output_mode.value
    if record.data_classification is not None:
        metadata["__data_classification__"] = record.data_classification.value
    return metadata


def row_to_mission(row: Any) -> MissionRecord:
    """Convert a database row into a MissionRecord."""
    metadata = _json_to_dict(row[3])
    has_project_id = len(row) >= 7
    project_id_index = 4 if has_project_id else None
    state_index = 5 if has_project_id else 4
    created_at_index = 6 if has_project_id else 5
    charter = _charter_fields_from_metadata(metadata)
    return MissionRecord(
        mission_id=row[0],
        prompt=row[1],
        requested_target_language=row[2],
        mission_type=charter["mission_type"],
        depth_mode=charter["depth_mode"],
        output_mode=charter["output_mode"],
        data_classification=charter["data_classification"],
        metadata=metadata,
        project_id=str(
            (row[project_id_index] if project_id_index is not None else None)
            or resolve_project_id(metadata, mission_id=row[0])
        ),
        state=MissionState(row[state_index]),
        created_at=_to_iso(row[created_at_index]),
    )


def upsert_mission(settings: Settings, record: MissionRecord, source_stream_id: str | None) -> None:
    """Insert or update a mission record and its source stream pointer."""
    metadata = with_project_identity(record.metadata, mission_id=record.mission_id)
    metadata = _embed_charter_fields(metadata, record)
    project_id = str(
        record.project_id or resolve_project_id(metadata, mission_id=record.mission_id)
    )
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO missions (
                    mission_id,
                    prompt,
                    requested_target_language,
                    metadata_json,
                    project_id,
                    state,
                    created_at,
                    updated_at,
                    source_stream_id
                )
                VALUES (%s, %s, %s, %s::jsonb, %s, %s, %s::timestamptz, NOW(), %s)
                ON CONFLICT (mission_id) DO UPDATE SET
                    prompt = EXCLUDED.prompt,
                    requested_target_language = EXCLUDED.requested_target_language,
                    metadata_json = EXCLUDED.metadata_json,
                    project_id = EXCLUDED.project_id,
                    state = EXCLUDED.state,
                    updated_at = NOW(),
                    source_stream_id = EXCLUDED.source_stream_id;
                """,
                (
                    record.mission_id,
                    record.prompt,
                    record.requested_target_language,
                    json.dumps(metadata),
                    project_id,
                    record.state.value,
                    record.created_at,
                    source_stream_id,
                ),
            )


def fetch_mission(settings: Settings, mission_id: str) -> MissionRecord | None:
    """Fetch one mission by id."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(FETCH_MISSION_SQL, (mission_id,))
            row = cur.fetchone()

    if not row:
        return None
    return row_to_mission(row)


def update_mission_metadata(
    settings: Settings,
    mission_id: str,
    metadata: dict[str, Any],
) -> MissionRecord | None:
    """Replace persisted mission metadata while preserving project identity."""
    normalized_metadata = with_project_identity(metadata, mission_id=mission_id)
    project_id = resolve_project_id(normalized_metadata, mission_id=mission_id)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                UPDATE_MISSION_METADATA_SQL,
                (json.dumps(normalized_metadata), project_id, mission_id),
            )
            row = cur.fetchone()

    if not row:
        return None
    return row_to_mission(row)


def list_missions(settings: Settings, limit: int) -> list[MissionRecord]:
    """List recent missions ordered by creation time."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(LIST_MISSIONS_SQL, (limit,))
            rows = cur.fetchall()

    return [row_to_mission(row) for row in rows]


def list_missions_in_states(
    settings: Settings,
    states: list[MissionState] | tuple[MissionState, ...],
    limit: int,
) -> list[MissionRecord]:
    """List recent missions whose state is in the provided state set."""
    normalized_states = [state.value for state in states if isinstance(state, MissionState)]
    if not normalized_states:
        return []

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(LIST_MISSIONS_IN_STATES_SQL, (normalized_states, max(1, int(limit))))
            rows = cur.fetchall()

    return [row_to_mission(row) for row in rows]


def _resolve_engine_label(settings: Settings) -> str:
    """Map the active lifecycle engine to a Prometheus label value."""
    if getattr(settings, "mission_flow_v2_enabled", True):
        return "v2"
    if getattr(settings, "langgraph_enabled", False):
        return "langgraph"
    return "legacy"


def insert_mission_event(
    settings: Settings,
    mission_id: str,
    previous_state: MissionState | None,
    new_state: MissionState,
    event_type: str,
) -> None:
    """Persist a mission lifecycle event and record transition metrics."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO mission_state_events (mission_id, previous_state, new_state, event_type)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    mission_id,
                    previous_state.value if previous_state else None,
                    new_state.value,
                    event_type,
                ),
            )

    # Observability: record the transition for Prometheus. A self-loop
    # (previous == new) is a checkpoint event, not a real transition, so skip it
    # to avoid double-counting the active gauge and outcomes.
    if previous_state == new_state:
        return
    from .orchestrator_metrics import record_mission_transition

    started_at_epoch: float | None = None
    if new_state in {MissionState.complete, MissionState.failed}:
        try:
            mission = fetch_mission(settings, mission_id)
            if mission is not None and mission.created_at is not None:
                started_at_epoch = mission.created_at.timestamp()
        except Exception:  # noqa: BLE001
            started_at_epoch = None

    record_mission_transition(
        from_state=previous_state.value if previous_state else None,
        to_state=new_state.value,
        engine=_resolve_engine_label(settings),
        started_at_epoch=started_at_epoch,
    )


def list_mission_events(settings: Settings, mission_id: str, limit: int) -> list[MissionEvent]:
    """List recent lifecycle events for one mission."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT mission_id, previous_state, new_state, event_type, ts
                FROM mission_state_events
                WHERE mission_id = %s
                ORDER BY ts DESC
                LIMIT %s
                """,
                (mission_id, limit),
            )
            rows = cur.fetchall()

    events: list[MissionEvent] = []
    for row in rows:
        previous_state = MissionState(row[1]) if row[1] else None
        events.append(
            MissionEvent(
                mission_id=row[0],
                previous_state=previous_state,
                new_state=MissionState(row[2]),
                event_type=row[3],
                ts=_to_iso(row[4]),
            )
        )
    return events


def list_recent_mission_events(settings: Settings, limit: int) -> list[MissionEvent]:
    """List recent lifecycle events across missions."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT mission_id, previous_state, new_state, event_type, ts
                FROM mission_state_events
                ORDER BY ts DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()

    events: list[MissionEvent] = []
    for row in rows:
        previous_state = MissionState(row[1]) if row[1] else None
        events.append(
            MissionEvent(
                mission_id=row[0],
                previous_state=previous_state,
                new_state=MissionState(row[2]),
                event_type=row[3],
                ts=_to_iso(row[4]),
            )
        )
    return events


def transition_mission_state(
    settings: Settings,
    mission_id: str,
    expected_state: MissionState | None,
    new_state: MissionState,
    event_type: str,
) -> MissionRecord | None:
    """Transition a mission state and append the matching lifecycle event."""
    with get_connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                if expected_state is None:
                    cur.execute(TRANSITION_MISSION_STATE_SQL, (new_state.value, mission_id))
                else:
                    cur.execute(
                        TRANSITION_MISSION_STATE_IF_MATCH_SQL,
                        (new_state.value, mission_id, expected_state.value),
                    )
                row = cur.fetchone()
                if not row:
                    return None
                cur.execute(
                    """
                    INSERT INTO mission_state_events
                        (mission_id, previous_state, new_state, event_type)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (
                        mission_id,
                        expected_state.value if expected_state else None,
                        new_state.value,
                        event_type,
                    ),
                )

    return row_to_mission(row)


def count_missions(settings: Settings) -> int:
    """Return the total number of persisted missions."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM missions")
            row = cur.fetchone()
    return int(row[0] if row else 0)


def mission_state_counts(settings: Settings) -> dict[str, int]:
    """Return mission counts grouped by state."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT state, COUNT(*)
                FROM missions
                GROUP BY state
                """
            )
            rows = cur.fetchall()

    return {str(row[0]): int(row[1]) for row in rows}


def _locked_mission_metadata_update(
    settings: Settings,
    mission_id: str,
    updater: Any,
) -> MissionRecord | None:
    if psycopg is None:
        raise RuntimeError("psycopg dependency is not installed")

    # prepare_threshold=None keeps this connection PgBouncer-safe (transaction
    # pooling mode does not support server-side prepared statements).
    conn = psycopg.connect(settings.postgres_url, autocommit=False, prepare_threshold=None)
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(LOCKED_FETCH_MISSION_SQL, (mission_id,))
                row = cur.fetchone()
                if row is None:
                    return None

                mission = row_to_mission(row)
                metadata = dict(mission.metadata) if isinstance(mission.metadata, dict) else {}
                updated_metadata = updater(metadata, mission)
                if not isinstance(updated_metadata, dict):
                    updated_metadata = metadata

                cur.execute(
                    LOCKED_UPDATE_MISSION_METADATA_SQL,
                    (
                        json.dumps(with_project_identity(updated_metadata, mission_id=mission_id)),
                        resolve_project_id(updated_metadata, mission_id=mission_id),
                        mission_id,
                    ),
                )
                updated_row = cur.fetchone()
                if updated_row is None:
                    return None
        return row_to_mission(updated_row)
    finally:
        conn.close()


def record_partition_result(
    settings: Settings,
    mission_id: str,
    result: dict[str, Any],
) -> MissionRecord | None:
    """Record one scaling partition result and merge when all partitions complete."""
    partition_result = ScalingPartitionResult(
        partition_id=str(result.get("partition_id", "")),
        instance_index=int(result.get("instance_index", 0)),
        agent_id=str(result.get("agent_id", "")),
        logicnodes=[node for node in result.get("logicnodes", []) if isinstance(node, dict)],
        artifacts=[
            artifact for artifact in result.get("artifacts", []) if isinstance(artifact, dict)
        ],
        report=result.get("report") if isinstance(result.get("report"), dict) else {},
        completed_at=str(result.get("completed_at", "")),
    )

    def _update(metadata: dict[str, Any], _mission: MissionRecord) -> dict[str, Any]:
        embed_partition_result(metadata, partition_result)
        metadata["last_partition_result_at"] = partition_result.completed_at
        partition_results = metadata.get("partition_results")
        if isinstance(partition_results, dict):
            metadata["partition_result_count"] = len(partition_results)

        if all_partitions_complete(metadata):
            results: list[ScalingPartitionResult] = []
            for raw in (metadata.get("partition_results") or {}).values():
                if not isinstance(raw, dict):
                    continue
                results.append(
                    ScalingPartitionResult(
                        partition_id=str(raw.get("partition_id", "")),
                        instance_index=int(raw.get("instance_index", 0)),
                        agent_id=str(raw.get("agent_id", "")),
                        logicnodes=[
                            node for node in raw.get("logicnodes", []) if isinstance(node, dict)
                        ],
                        artifacts=[
                            artifact
                            for artifact in raw.get("artifacts", [])
                            if isinstance(artifact, dict)
                        ],
                        report=raw.get("report") if isinstance(raw.get("report"), dict) else {},
                        completed_at=str(raw.get("completed_at", "")),
                    )
                )
            merged = merge_partition_results(results)
            metadata["merged_partition_result"] = merged.to_dict()
            metadata["scaling_merge_complete"] = True
            metadata["scaling_completed_at"] = merged.merged_at
        else:
            metadata["scaling_merge_complete"] = False

        return metadata

    return _locked_mission_metadata_update(settings, mission_id, _update)
