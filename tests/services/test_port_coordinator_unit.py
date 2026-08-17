"""PORT two-phase helpers — language detect, setup, extraction."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))
sys.path.insert(0, str(ROOT))

from orchestrator import port_coordinator  # noqa: E402


def test_detect_source_language_from_file_extensions() -> None:
    bundle = "## FILE src/main.go\npackage main\n\n## FILE util.go\npackage util\n"
    assert port_coordinator._detect_source_language_from_bundle(bundle, "") == "go"


def test_detect_source_language_from_prompt_when_no_bundle() -> None:
    assert port_coordinator._detect_source_language_from_bundle(None, "port this rust cli") == "rust"
    assert port_coordinator._detect_source_language_from_bundle("   ", "build something") == "python"


def test_setup_port_two_phase_uses_cluster_extraction_ids() -> None:
    metadata: dict = {"source_code": "## FILE app.py\nprint(1)\n"}
    mission = SimpleNamespace(prompt="port this to go", requested_target_language="go")
    port_coordinator._setup_port_two_phase(
        metadata,
        mission,
        [
            {"domain": "ui", "pod_manager_agent_id": "AGENT-12-PODA-MGR"},
            {
                "domain": "source_extraction",
                "pod_manager_agent_id": "AGENT-18-PODB-MGR",
                "specialist_agent_id": "AGENT-36-GO",
            },
        ],
    )
    assert metadata["port_source_language"] == "python"
    assert metadata["port_target_language"] == "go"
    assert metadata["port_phase"] == "extraction"
    assert metadata["port_source_pod_manager_agent_id"] == "AGENT-18-PODB-MGR"
    assert metadata["port_source_specialist_agent_id"] == "AGENT-36-GO"


def test_setup_port_two_phase_defaults_when_clusters_unusable() -> None:
    metadata: dict = {}
    mission = SimpleNamespace(prompt="port java to kotlin", requested_target_language=None)
    port_coordinator._setup_port_two_phase(metadata, mission, ["not-a-dict"])
    assert metadata["port_source_language"] == "java"
    assert metadata["port_target_language"] == "python"
    assert metadata["port_source_specialist_agent_id"] == "AGENT-26-JAVA"


def test_run_port_extraction_phase_collects_aim_nodes(monkeypatch) -> None:
    async def _aim(**_kwargs):
        return {
            "source": "llm",
            "files": [
                {
                    "extracted_concepts": [
                        {"domain": "io", "concept": "read", "intent": "read file", "confidence": 0.9}
                    ]
                },
                "skip",
            ],
        }

    async def _plan(**_kwargs):
        return {"source": "llm", "summary": "extract"}

    monkeypatch.setattr("orchestrator.aim_generator.generate_aim", _aim)
    monkeypatch.setattr("orchestrator.llm_delegation.generate_specialist_plan", _plan)
    metadata = {
        "port_source_language": "python",
        "port_source_specialist_agent_id": "AGENT-14-PYTHON",
        "port_source_pod_manager_agent_id": "AGENT-12-PODA-MGR",
        "source_code": "## FILE app.py\nprint(1)\n",
        "chain_trace": [],
    }
    result = asyncio.run(
        port_coordinator.run_port_extraction_phase(
            mission_id="mission-port",
            mission=SimpleNamespace(prompt="port to go"),
            metadata=metadata,
            settings=SimpleNamespace(),
        )
    )
    assert result["port_phase"] == "generation"
    assert result["extraction_degraded"] is False
    assert result["port_source_logicnodes"][0]["concept"] == "read"
    assert metadata["chain_trace"][-1]["event_type"] == "MISSION_PORT_EXTRACTION_COMPLETE"


def test_run_port_extraction_phase_degrades_when_aim_and_plan_fail(monkeypatch) -> None:
    async def _aim(**_kwargs):
        raise RuntimeError("aim down")

    async def _plan(**_kwargs):
        raise RuntimeError("plan down")

    monkeypatch.setattr("orchestrator.aim_generator.generate_aim", _aim)
    monkeypatch.setattr("orchestrator.llm_delegation.generate_specialist_plan", _plan)
    metadata = {
        "source_code": "## FILE app.py\nprint(1)\n",
        "chain_events": [],
    }
    result = asyncio.run(
        port_coordinator.run_port_extraction_phase(
            mission_id="mission-port-fail",
            mission=SimpleNamespace(prompt="port"),
            metadata=metadata,
            settings=SimpleNamespace(),
        )
    )
    assert result["extraction_degraded"] is True
    assert result["port_source_aim"]["source"] == "error"
    assert result["port_source_plan"]["source"] == "fallback"
