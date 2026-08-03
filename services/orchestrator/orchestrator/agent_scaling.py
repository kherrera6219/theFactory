"""Dynamic agent scaling — pod managers spawn N specialist instances.

Feature-flagged via ``AGENT_SCALING_ENABLED`` (default ``False``).
When enabled, the pod-manager stage of the Mission Flow v2 pipeline
evaluates the workload manifest and records a scaling decision in
mission metadata.  Pod-worker replicas then claim individual
partitions and execute in parallel.  Results are merged before the
QC / audit gate.
"""

from __future__ import annotations

import math
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any, Final

SCALING_VERSION: Final[str] = "v1"

# Hard ceiling — never spawn more than this regardless of config.
ABSOLUTE_MAX_INSTANCES: Final[int] = 8

# Specialist agent IDs that support scaling (all 19 coding agents).
SCALABLE_AGENT_IDS: Final[frozenset[str]] = frozenset(
    {
        # Pod A — dynamic languages
        "AGENT-14-PYTHON",
        "AGENT-15-JAVASCRIPT",
        "AGENT-16-RUBY",
        "AGENT-17-PHP",
        # Pod B — systems languages
        "AGENT-20-C",
        "AGENT-21-CPP",
        "AGENT-22-RUST",
        "AGENT-23-ZIG",
        "AGENT-36-GO",
        # Pod C — enterprise languages
        "AGENT-26-JAVA",
        "AGENT-27-CSHARP",
        "AGENT-28-SCALA",
        "AGENT-29-KOTLIN",
        # Pod D — mathematical & functional languages
        "AGENT-32-MATLAB",
        "AGENT-33-R",
        "AGENT-34-JULIA",
        "AGENT-35-MATHEMATICA",
        "AGENT-37-HASKELL",
        "AGENT-38-OCAML",
    }
)


# ------------------------------------------------------------------
# Data models
# ------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class WorkPartition:
    """A slice of work assigned to a single specialist instance."""

    partition_id: str
    instance_index: int
    total_instances: int
    assigned_items: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ScalingDecision:
    """The pod-manager's decision on how many instances to spawn."""

    agent_id: str
    instance_count: int
    partitions: tuple[WorkPartition, ...]
    reason: str
    scaling_version: str = SCALING_VERSION
    decided_at: str = ""

    def __post_init__(self) -> None:
        if not self.decided_at:
            object.__setattr__(
                self, "decided_at", datetime.now(UTC).isoformat()
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "instance_count": self.instance_count,
            "partitions": [p.to_dict() for p in self.partitions],
            "reason": self.reason,
            "scaling_version": self.scaling_version,
            "decided_at": self.decided_at,
        }


@dataclass(slots=True)
class PartitionResult:
    """Result from a single partition execution."""

    partition_id: str
    instance_index: int
    agent_id: str
    logicnodes: list[dict[str, Any]] = field(default_factory=list)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    report: dict[str, Any] = field(default_factory=dict)
    completed_at: str = ""

    def __post_init__(self) -> None:
        if not self.completed_at:
            self.completed_at = datetime.now(UTC).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "partition_id": self.partition_id,
            "instance_index": self.instance_index,
            "agent_id": self.agent_id,
            "logicnodes": self.logicnodes,
            "artifacts": self.artifacts,
            "report": self.report,
            "completed_at": self.completed_at,
        }


@dataclass(frozen=True, slots=True)
class MergedResult:
    """Fused output from all partitions."""

    logicnodes: tuple[dict[str, Any], ...]
    artifacts: tuple[dict[str, Any], ...]
    partition_count: int
    merge_strategy: str
    merged_at: str = ""

    def __post_init__(self) -> None:
        if not self.merged_at:
            object.__setattr__(
                self, "merged_at", datetime.now(UTC).isoformat()
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "logicnodes": list(self.logicnodes),
            "artifacts": list(self.artifacts),
            "partition_count": self.partition_count,
            "merge_strategy": self.merge_strategy,
            "merged_at": self.merged_at,
        }


# ------------------------------------------------------------------
# Scaling decision
# ------------------------------------------------------------------


def is_scalable_agent(agent_id: str) -> bool:
    """Return ``True`` if the agent supports dynamic scaling."""
    return str(agent_id or "").strip().upper() in SCALABLE_AGENT_IDS


def compute_scaling_decision(
    *,
    agent_id: str,
    workload_items: list[str],
    max_instances: int = 4,
    items_per_instance: int = 3,
) -> ScalingDecision:
    """Decide how many specialist instances to spawn.

    Parameters
    ----------
    agent_id:
        The specialist agent ID (must be in ``SCALABLE_AGENT_IDS``).
    workload_items:
        List of work item identifiers (file paths, module names, etc.).
    max_instances:
        Upper bound on instance count (capped at ``ABSOLUTE_MAX_INSTANCES``).
    items_per_instance:
        Minimum items per instance before scaling up.

    Returns
    -------
    ScalingDecision
        Contains the partitions and reasoning.
    """
    normalized_agent_id = str(agent_id or "").strip().upper()
    effective_max = min(max(1, max_instances), ABSOLUTE_MAX_INSTANCES)
    effective_items_per = max(1, items_per_instance)
    item_count = len(workload_items)

    if item_count <= effective_items_per or not is_scalable_agent(normalized_agent_id):
        # Single instance — no scaling needed.
        partitions = partition_workload(workload_items, 1)
        return ScalingDecision(
            agent_id=normalized_agent_id,
            instance_count=1,
            partitions=partitions,
            reason=f"single_instance:item_count={item_count}",
        )

    desired = min(effective_max, math.ceil(item_count / effective_items_per))
    desired = max(1, desired)
    partitions = partition_workload(workload_items, desired)

    return ScalingDecision(
        agent_id=normalized_agent_id,
        instance_count=desired,
        partitions=partitions,
        reason=(
            f"scaled:{desired}_instances:"
            f"item_count={item_count}:"
            f"items_per_instance={effective_items_per}"
        ),
    )


# ------------------------------------------------------------------
# Work partitioning
# ------------------------------------------------------------------


def partition_workload(
    items: list[str],
    instance_count: int,
) -> tuple[WorkPartition, ...]:
    """Split work items into balanced partitions via round-robin.

    Parameters
    ----------
    items:
        List of work item identifiers.
    instance_count:
        Number of partitions to create (must be >= 1).

    Returns
    -------
    tuple[WorkPartition, ...]
        One ``WorkPartition`` per instance.
    """
    effective_count = max(1, min(instance_count, len(items) if items else 1))
    buckets: list[list[str]] = [[] for _ in range(effective_count)]

    for idx, item in enumerate(items):
        buckets[idx % effective_count].append(item)

    return tuple(
        WorkPartition(
            partition_id=f"p{i}-{uuid.uuid4().hex[:8]}",
            instance_index=i,
            total_instances=effective_count,
            assigned_items=tuple(bucket),
        )
        for i, bucket in enumerate(buckets)
    )


# ------------------------------------------------------------------
# Result merging
# ------------------------------------------------------------------


def merge_partition_results(
    results: list[PartitionResult],
) -> MergedResult:
    """Fuse outputs from N parallel specialist instances.

    LogicNodes and artifacts are concatenated in partition order.
    Deduplication (if needed) is left to the QC/audit agent.

    Parameters
    ----------
    results:
        Completed results from each partition, in any order.

    Returns
    -------
    MergedResult
        Combined output ready for the gating/audit phase.
    """
    sorted_results = sorted(results, key=lambda r: r.instance_index)

    all_logicnodes: list[dict[str, Any]] = []
    all_artifacts: list[dict[str, Any]] = []
    for result in sorted_results:
        all_logicnodes.extend(result.logicnodes)
        all_artifacts.extend(result.artifacts)

    return MergedResult(
        logicnodes=tuple(all_logicnodes),
        artifacts=tuple(all_artifacts),
        partition_count=len(sorted_results),
        merge_strategy="concatenate_by_partition_order",
    )


# ------------------------------------------------------------------
# Metadata helpers
# ------------------------------------------------------------------


def scaling_decision_from_metadata(
    metadata: dict[str, Any],
) -> ScalingDecision | None:
    """Reconstruct a ``ScalingDecision`` from mission metadata."""
    raw = metadata.get("scaling_decision")
    if not isinstance(raw, dict):
        return None
    partitions_raw = raw.get("partitions")
    if not isinstance(partitions_raw, list):
        return None

    partitions = tuple(
        WorkPartition(
            partition_id=str(p.get("partition_id", "")),
            instance_index=int(p.get("instance_index", 0)),
            total_instances=int(p.get("total_instances", 1)),
            assigned_items=tuple(p.get("assigned_items", ())),
        )
        for p in partitions_raw
        if isinstance(p, dict)
    )

    return ScalingDecision(
        agent_id=str(raw.get("agent_id", "")),
        instance_count=int(raw.get("instance_count", 1)),
        partitions=partitions,
        reason=str(raw.get("reason", "")),
        scaling_version=str(raw.get("scaling_version", SCALING_VERSION)),
        decided_at=str(raw.get("decided_at", "")),
    )


def embed_scaling_decision(
    metadata: dict[str, Any],
    decision: ScalingDecision,
) -> None:
    """Write a scaling decision into mission metadata (mutates in-place)."""
    metadata["scaling_decision"] = decision.to_dict()
    metadata["scaling_active"] = decision.instance_count > 1
    metadata["scaling_version"] = decision.scaling_version


def all_partitions_complete(
    metadata: dict[str, Any],
) -> bool:
    """Check whether all partition results have been received."""
    decision = scaling_decision_from_metadata(metadata)
    if decision is None:
        return True  # no scaling → always "complete"
    if decision.instance_count <= 1:
        return True

    partition_results = metadata.get("partition_results")
    if not isinstance(partition_results, dict):
        return False

    expected_ids = {p.partition_id for p in decision.partitions}
    received_ids = set(partition_results.keys())
    return expected_ids <= received_ids


def record_partition_result(
    metadata: dict[str, Any],
    result: PartitionResult,
) -> None:
    """Store a partition result in mission metadata (mutates in-place)."""
    partition_results = metadata.get("partition_results")
    if not isinstance(partition_results, dict):
        partition_results = {}
    partition_results[result.partition_id] = result.to_dict()
    metadata["partition_results"] = partition_results
