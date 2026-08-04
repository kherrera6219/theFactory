"""Regression test: Phase 4's Refined-IR must reach Phase 5's gate.

pod-worker built the RIR module in memory and, when `REFINED_IR_STORE_PATH` was
configured, wrote it to *its own container's* filesystem. The orchestrator never
received it, so behavioural equivalence reported, on every mission:

    "status": "skipped",
    "reason": "no Refined-IR module in mission metadata"

Phase 4 produced the equivalence vectors and Phase 5 had no way to reach them —
two shipped phases that never connected. Found by running a real mission
(2026-08-04), not by any test, because each phase was correct in isolation.

Only the executable vectors are handed over. Persisting the whole module would
put unbounded extractor output into mission metadata, which is exactly the
mistake that made chat launches fail against the gateway's size limit.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))
sys.path.insert(0, str(ROOT / "services" / "pod-worker"))

import pod_worker.main as pod_worker_main  # noqa: E402
from pod_worker.refined_ir import build_refined_ir_module  # noqa: E402


def _module_with_vectors():
    """A module shaped like a real ast_v1 projection."""
    node = {
        "node_id": "podA.add.m1.abc.10",
        "concept": "add",
        "domain": "arithmetic",
        "node": {
            "node_id": "podA.add.m1.abc.10",
            "cmd": "add",
            "payload": {
                "concept": "add",
                "domain": "arithmetic",
                "types_source": "ast_signature:add",
                "confidence": 0.9,
            },
            "priority": "NORMAL",
            "intent": "add two numbers",
            "types": {"in": ["int", "int"], "out": ["int"]},
            "purity": "PURE",
            "provenance": {
                "source_ref": "demo.py",
                "snippet_hash": "0" * 64,
                "miner_agent": "AGENT-14-PYTHON",
                "timestamp": "2026-08-04T00:00:00+00:00",
            },
        },
    }
    return build_refined_ir_module(
        mission_id="m1",
        agent_id="AGENT-14-PYTHON",
        source_language="python",
        target_language="python",
        logicnodes=[node],
        source_ref="demo.py",
    )


def test_handoff_posts_the_projection_to_the_orchestrator(monkeypatch) -> None:
    captured: dict[str, object] = {}

    async def _fake_request(method, path, json_body=None, **_kwargs):
        captured["method"] = method
        captured["path"] = path
        captured["body"] = json_body
        return {}

    monkeypatch.setattr(pod_worker_main, "_request", _fake_request)
    asyncio.run(pod_worker_main._handoff_refined_ir("m1", _module_with_vectors()))

    assert captured["method"] == "POST"
    assert captured["path"] == "/internal/missions/m1/refined-ir"
    body = captured["body"]
    assert isinstance(body, dict)
    assert body["projection_method"] in {"ast_v1", "templated_v1", "mixed_v1"}
    assert isinstance(body["fns"], list) and body["fns"]


def test_handed_over_functions_carry_executable_vectors() -> None:
    """What Phase 5 needs is the vectors; without them the gate has nothing."""
    module = _module_with_vectors()
    payload = module.model_dump(by_alias=True)
    ast_fns = [fn for fn in payload["fns"] if fn.get("projection_method") == "ast_v1"]
    assert ast_fns, "the fixture should produce an ast_v1 projection"
    vectors = ast_fns[0]["tests"]["equivalence_vectors"]
    assert any(v["out"].get("executable") for v in vectors)


def test_handoff_failure_never_propagates(monkeypatch) -> None:
    """Extraction has already succeeded; an unreachable gate must not fail it.

    The gate degrades to a recorded "skipped", which is the honest outcome.
    """
    async def _boom(*_args, **_kwargs):
        raise RuntimeError("orchestrator unreachable")

    monkeypatch.setattr(pod_worker_main, "_request", _boom)
    asyncio.run(pod_worker_main._handoff_refined_ir("m1", _module_with_vectors()))


def test_handoff_is_called_from_every_rir_build_site() -> None:
    """Both the running-mission and partition-ready handlers build a module.

    If one forgets the handoff, missions on that path silently lose behavioural
    verification — the exact class of gap this test exists to prevent.
    """
    source = Path(pod_worker_main.__file__).read_text(encoding="utf-8")
    build_sites = source.count("refined_ir_module = build_refined_ir_module(")
    handoffs = source.count("await _handoff_refined_ir(")
    assert build_sites >= 2, "expected both RIR build sites"
    assert handoffs == build_sites, (
        f"{build_sites} RIR build sites but {handoffs} handoffs — a build site "
        "without a handoff loses behavioural verification silently"
    )
