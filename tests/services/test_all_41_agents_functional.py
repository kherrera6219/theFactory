"""
test_all_41_agents_functional.py

Functional verification test for all 41 agents in theFactory registry:
- Executive (CEO: AGENT-02-CEO)
- Interface (PM: AGENT-01-PM)
- Pod Managers (Pod A, B, C, D)
- Pod Audit / QC (Pod A, B, C, D)
- Support Ring (Broker, Accountant, Security, IS, VC, Compliance, HW, Tester, Deploy, DepAbs, TestData, RQCA)
- Language Specialists (19 specialists covering all 20 languages)
"""
from __future__ import annotations

import pytest
from orchestrator.agent_base import (
    BaseAgent,
    make_agent,
)
from orchestrator.agent_registry import AGENT_REGISTRY

_AGENT_PARAMS = [
    pytest.param(defn, id=defn.agent_id) for defn in AGENT_REGISTRY
]

@pytest.mark.parametrize("defn", _AGENT_PARAMS)
def test_agent_functional_lifecycle(defn) -> None:
    agent_id = defn.agent_id
    cat = defn.category
    agent = make_agent(agent_id)

    assert isinstance(agent, BaseAgent)
    assert agent.agent_id == agent_id
    assert agent.category == cat
    assert agent.tier == defn.tier

    mission_id = f"m-ci-{agent_id.lower()}"

    if cat == "executive":
        payload = {
            "task": "orchestrate",
            "pod_manager_agent_id": "AGENT-12-PODA-MGR",
            "specialist_agent_id": "AGENT-14-PYTHON",
            "rationale": "CEO delegation test",
        }
    elif cat == "interface":
        payload = {
            "mission_id": mission_id,
            "prompt": "Build calculator",
            "target_language": "python",
        }
    elif cat == "pod_manager":
        payload = {
            "task": "fuse_pod_output",
            "specialist_agent_id": "AGENT-14-PYTHON",
            "requested_target_language": "python",
        }
    elif cat == "pod_audit":
        payload = {
            "task": "audit_logicnodes",
            "logicnodes": [{"node_id": "ln-001", "name": "core", "purity": "PURE"}],
        }
    elif cat == "support":
        payload = {
            "task": f"support_action_{defn.short_code.lower()}",
            "verdict": "PASS",
        }
    elif cat == "specialist":
        payload = {
            "code": "def solve(x: int) -> int:\n    return x * 2\n",
            "language": getattr(agent, "language", "generic"),
        }
    else:
        payload = {"task": "generic_action"}

    # 1. Execute
    exec_result = agent.execute(mission_id, payload)
    assert exec_result.status == "ok"

    # 2. Validate
    artifacts_to_validate = exec_result.artifacts
    if cat == "interface":
        artifacts_to_validate = [{"mission_id": mission_id, "type": "intake_contract", "payload": payload}]
    elif cat == "specialist":
        artifacts_to_validate = [{"path": "solution.py", "content": payload["code"], "language": "python"}]

    val_result = agent.validate(mission_id, artifacts_to_validate)
    assert val_result.passed is True, f"Validation failed for {agent_id}: {val_result.findings}"

    # 3. Report
    report = agent.report(mission_id, exec_result, val_result)
    assert report.verdict == "PASS"
    assert report.agent_id == agent_id
    assert len(report.summary) > 0
