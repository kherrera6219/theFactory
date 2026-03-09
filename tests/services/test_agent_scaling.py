"""Tests for agent_scaling.py — dynamic agent scaling engine."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))
agent_scaling = importlib.import_module("orchestrator.agent_scaling")

ScalingDecision = agent_scaling.ScalingDecision
WorkPartition = agent_scaling.WorkPartition
PartitionResult = agent_scaling.PartitionResult
MergedResult = agent_scaling.MergedResult
SCALABLE_AGENT_IDS = agent_scaling.SCALABLE_AGENT_IDS
ABSOLUTE_MAX_INSTANCES = agent_scaling.ABSOLUTE_MAX_INSTANCES

is_scalable_agent = agent_scaling.is_scalable_agent
compute_scaling_decision = agent_scaling.compute_scaling_decision
partition_workload = agent_scaling.partition_workload
merge_partition_results = agent_scaling.merge_partition_results
scaling_decision_from_metadata = agent_scaling.scaling_decision_from_metadata
embed_scaling_decision = agent_scaling.embed_scaling_decision
all_partitions_complete = agent_scaling.all_partitions_complete
record_partition_result = agent_scaling.record_partition_result


# ------------------------------------------------------------------
# Scalable agent identification
# ------------------------------------------------------------------


class TestIsScalableAgent:
    def test_all_16_specialists_are_scalable(self) -> None:
        assert len(SCALABLE_AGENT_IDS) == 16

    @pytest.mark.parametrize(
        "agent_id",
        [
            "AGENT-14-PYTHON",
            "AGENT-15-JAVASCRIPT",
            "AGENT-16-RUBY",
            "AGENT-17-PHP",
            "AGENT-20-C",
            "AGENT-21-CPP",
            "AGENT-22-RUST",
            "AGENT-23-ZIG",
            "AGENT-26-JAVA",
            "AGENT-27-CSHARP",
            "AGENT-28-SCALA",
            "AGENT-29-KOTLIN",
            "AGENT-32-MATLAB",
            "AGENT-33-R",
            "AGENT-34-JULIA",
            "AGENT-35-MATHEMATICA",
        ],
    )
    def test_specialist_is_scalable(self, agent_id: str) -> None:
        assert is_scalable_agent(agent_id)

    @pytest.mark.parametrize(
        "agent_id",
        [
            "AGENT-01-PM",
            "AGENT-02-CEO",
            "AGENT-03-BROKER",
            "AGENT-12-PODA-MGR",
            "AGENT-13-PODA-AUDIT",
        ],
    )
    def test_non_specialist_is_not_scalable(self, agent_id: str) -> None:
        assert not is_scalable_agent(agent_id)

    def test_empty_and_none(self) -> None:
        assert not is_scalable_agent("")
        assert not is_scalable_agent(None)  # type: ignore[arg-type]

    def test_case_insensitive(self) -> None:
        assert is_scalable_agent("agent-14-python")
        assert is_scalable_agent("Agent-14-Python")


# ------------------------------------------------------------------
# Workload partitioning
# ------------------------------------------------------------------


class TestPartitionWorkload:
    def test_single_instance(self) -> None:
        items = ["a", "b", "c"]
        result = partition_workload(items, 1)
        assert len(result) == 1
        assert result[0].assigned_items == ("a", "b", "c")
        assert result[0].instance_index == 0
        assert result[0].total_instances == 1

    def test_even_split(self) -> None:
        items = ["a", "b", "c", "d"]
        result = partition_workload(items, 2)
        assert len(result) == 2
        assert result[0].assigned_items == ("a", "c")
        assert result[1].assigned_items == ("b", "d")

    def test_uneven_split(self) -> None:
        items = ["a", "b", "c", "d", "e"]
        result = partition_workload(items, 3)
        assert len(result) == 3
        assert result[0].assigned_items == ("a", "d")
        assert result[1].assigned_items == ("b", "e")
        assert result[2].assigned_items == ("c",)

    def test_more_instances_than_items(self) -> None:
        items = ["a", "b"]
        result = partition_workload(items, 5)
        # Can only create as many partitions as items
        assert len(result) == 2
        assert result[0].assigned_items == ("a",)
        assert result[1].assigned_items == ("b",)

    def test_empty_items(self) -> None:
        result = partition_workload([], 4)
        assert len(result) == 1
        assert result[0].assigned_items == ()

    def test_partition_ids_are_unique(self) -> None:
        items = [f"item-{i}" for i in range(12)]
        result = partition_workload(items, 4)
        ids = [p.partition_id for p in result]
        assert len(set(ids)) == 4

    def test_all_items_assigned(self) -> None:
        items = [f"mod-{i}" for i in range(15)]
        result = partition_workload(items, 4)
        all_assigned = []
        for p in result:
            all_assigned.extend(p.assigned_items)
        assert sorted(all_assigned) == sorted(items)


# ------------------------------------------------------------------
# Scaling decision computation
# ------------------------------------------------------------------


class TestComputeScalingDecision:
    def test_single_instance_for_small_workload(self) -> None:
        decision = compute_scaling_decision(
            agent_id="AGENT-14-PYTHON",
            workload_items=["a", "b"],
            max_instances=4,
            items_per_instance=3,
        )
        assert decision.instance_count == 1
        assert len(decision.partitions) == 1
        assert "single_instance" in decision.reason

    def test_scales_up_for_large_workload(self) -> None:
        decision = compute_scaling_decision(
            agent_id="AGENT-14-PYTHON",
            workload_items=[f"mod-{i}" for i in range(12)],
            max_instances=4,
            items_per_instance=3,
        )
        assert decision.instance_count == 4
        assert len(decision.partitions) == 4
        assert "scaled" in decision.reason

    def test_respects_max_instances(self) -> None:
        decision = compute_scaling_decision(
            agent_id="AGENT-14-PYTHON",
            workload_items=[f"mod-{i}" for i in range(100)],
            max_instances=3,
            items_per_instance=2,
        )
        assert decision.instance_count == 3

    def test_absolute_cap(self) -> None:
        decision = compute_scaling_decision(
            agent_id="AGENT-14-PYTHON",
            workload_items=[f"mod-{i}" for i in range(100)],
            max_instances=20,
            items_per_instance=1,
        )
        assert decision.instance_count <= ABSOLUTE_MAX_INSTANCES

    def test_non_scalable_agent_always_single(self) -> None:
        decision = compute_scaling_decision(
            agent_id="AGENT-02-CEO",
            workload_items=[f"mod-{i}" for i in range(50)],
            max_instances=4,
            items_per_instance=3,
        )
        assert decision.instance_count == 1

    def test_empty_workload(self) -> None:
        decision = compute_scaling_decision(
            agent_id="AGENT-14-PYTHON",
            workload_items=[],
            max_instances=4,
            items_per_instance=3,
        )
        assert decision.instance_count == 1

    @pytest.mark.parametrize(
        "agent_id",
        [
            "AGENT-14-PYTHON",
            "AGENT-15-JAVASCRIPT",
            "AGENT-20-C",
            "AGENT-26-JAVA",
            "AGENT-32-MATLAB",
        ],
    )
    def test_each_pod_specialist_scales(self, agent_id: str) -> None:
        decision = compute_scaling_decision(
            agent_id=agent_id,
            workload_items=[f"mod-{i}" for i in range(9)],
            max_instances=4,
            items_per_instance=3,
        )
        assert decision.instance_count == 3
        assert decision.agent_id == agent_id

    def test_decision_serialization(self) -> None:
        decision = compute_scaling_decision(
            agent_id="AGENT-14-PYTHON",
            workload_items=["a", "b", "c", "d", "e", "f"],
            max_instances=2,
            items_per_instance=3,
        )
        d = decision.to_dict()
        assert d["agent_id"] == "AGENT-14-PYTHON"
        assert d["instance_count"] == 2
        assert len(d["partitions"]) == 2
        assert "decided_at" in d


# ------------------------------------------------------------------
# Result merging
# ------------------------------------------------------------------


class TestMergePartitionResults:
    def test_merge_two_partitions(self) -> None:
        r0 = PartitionResult(
            partition_id="p0",
            instance_index=0,
            agent_id="AGENT-14-PYTHON",
            logicnodes=[{"node_id": "ln-1"}],
            artifacts=[{"type": "logicnode_set"}],
        )
        r1 = PartitionResult(
            partition_id="p1",
            instance_index=1,
            agent_id="AGENT-14-PYTHON",
            logicnodes=[{"node_id": "ln-2"}, {"node_id": "ln-3"}],
            artifacts=[{"type": "logicnode_set"}],
        )
        merged = merge_partition_results([r1, r0])  # out of order
        assert len(merged.logicnodes) == 3
        # Should be sorted by instance_index
        assert merged.logicnodes[0]["node_id"] == "ln-1"
        assert merged.partition_count == 2
        assert merged.merge_strategy == "concatenate_by_partition_order"

    def test_merge_empty(self) -> None:
        merged = merge_partition_results([])
        assert len(merged.logicnodes) == 0
        assert merged.partition_count == 0

    def test_merge_single(self) -> None:
        r = PartitionResult(
            partition_id="p0",
            instance_index=0,
            agent_id="AGENT-14-PYTHON",
            logicnodes=[{"node_id": "x"}],
        )
        merged = merge_partition_results([r])
        assert len(merged.logicnodes) == 1
        assert merged.partition_count == 1


# ------------------------------------------------------------------
# Metadata helpers
# ------------------------------------------------------------------


class TestMetadataHelpers:
    def test_embed_and_read_back(self) -> None:
        decision = compute_scaling_decision(
            agent_id="AGENT-14-PYTHON",
            workload_items=["a", "b", "c", "d", "e", "f"],
            max_instances=2,
            items_per_instance=3,
        )
        metadata: dict[str, Any] = {}
        embed_scaling_decision(metadata, decision)

        assert metadata["scaling_active"] is True
        assert metadata["scaling_version"] == "v1"

        reconstituted = scaling_decision_from_metadata(metadata)
        assert reconstituted is not None
        assert reconstituted.instance_count == 2
        assert reconstituted.agent_id == "AGENT-14-PYTHON"
        assert len(reconstituted.partitions) == 2

    def test_no_scaling_in_metadata(self) -> None:
        assert scaling_decision_from_metadata({}) is None
        assert scaling_decision_from_metadata({"scaling_decision": "bad"}) is None

    def test_all_partitions_complete_no_scaling(self) -> None:
        assert all_partitions_complete({}) is True

    def test_all_partitions_complete_single_instance(self) -> None:
        decision = compute_scaling_decision(
            agent_id="AGENT-14-PYTHON",
            workload_items=["a"],
            max_instances=4,
            items_per_instance=3,
        )
        metadata: dict[str, Any] = {}
        embed_scaling_decision(metadata, decision)
        assert all_partitions_complete(metadata) is True

    def test_all_partitions_complete_multi_instance(self) -> None:
        decision = compute_scaling_decision(
            agent_id="AGENT-14-PYTHON",
            workload_items=["a", "b", "c", "d", "e", "f"],
            max_instances=2,
            items_per_instance=3,
        )
        metadata: dict[str, Any] = {}
        embed_scaling_decision(metadata, decision)

        # Not yet complete
        assert all_partitions_complete(metadata) is False

        # Record one partition
        r0 = PartitionResult(
            partition_id=decision.partitions[0].partition_id,
            instance_index=0,
            agent_id="AGENT-14-PYTHON",
        )
        record_partition_result(metadata, r0)
        assert all_partitions_complete(metadata) is False

        # Record second partition
        r1 = PartitionResult(
            partition_id=decision.partitions[1].partition_id,
            instance_index=1,
            agent_id="AGENT-14-PYTHON",
        )
        record_partition_result(metadata, r1)
        assert all_partitions_complete(metadata) is True

    def test_record_partition_result(self) -> None:
        metadata: dict[str, Any] = {}
        r = PartitionResult(
            partition_id="p0-abc",
            instance_index=0,
            agent_id="AGENT-14-PYTHON",
            logicnodes=[{"node_id": "ln-1"}],
        )
        record_partition_result(metadata, r)
        assert "p0-abc" in metadata["partition_results"]
        assert metadata["partition_results"]["p0-abc"]["agent_id"] == "AGENT-14-PYTHON"


# ------------------------------------------------------------------
# Data model serialization
# ------------------------------------------------------------------


class TestDataModels:
    def test_work_partition_to_dict(self) -> None:
        p = WorkPartition(
            partition_id="p0-test",
            instance_index=0,
            total_instances=2,
            assigned_items=("a", "b"),
        )
        d = p.to_dict()
        assert d["partition_id"] == "p0-test"
        assert d["assigned_items"] == ("a", "b")

    def test_partition_result_to_dict(self) -> None:
        r = PartitionResult(
            partition_id="p0-test",
            instance_index=0,
            agent_id="AGENT-14-PYTHON",
            logicnodes=[{"x": 1}],
        )
        d = r.to_dict()
        assert d["partition_id"] == "p0-test"
        assert "completed_at" in d

    def test_merged_result_to_dict(self) -> None:
        m = MergedResult(
            logicnodes=({"a": 1},),
            artifacts=(),
            partition_count=1,
            merge_strategy="test",
        )
        d = m.to_dict()
        assert d["logicnodes"] == [{"a": 1}]
        assert d["merge_strategy"] == "test"

    def test_scaling_decision_has_timestamp(self) -> None:
        decision = ScalingDecision(
            agent_id="AGENT-14-PYTHON",
            instance_count=1,
            partitions=(),
            reason="test",
        )
        assert decision.decided_at != ""
