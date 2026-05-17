from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ORCHESTRATOR_ROOT = ROOT / "services" / "orchestrator"
if str(ORCHESTRATOR_ROOT) not in sys.path:
    sys.path.insert(0, str(ORCHESTRATOR_ROOT))

from orchestrator.llm_delegation import generate_ceo_delegation  # noqa: E402


async def _main() -> int:
    has_provider_key = any(
        os.getenv(name, "").strip()
        for name in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY")
    )
    result = await generate_ceo_delegation(
        mission_context={
            "mission_id": "phase1-smoke",
            "requested_target_language": "python",
            "routing_version": "phase1-smoke",
            "routing_enforced": True,
        },
        requested_target_language="python",
    )
    source = str(result.get("source", "")).strip()
    provider = str(result.get("model_provider", "")).strip()
    model = str(result.get("model", "")).strip()
    pod_manager = str(result.get("pod_manager_agent_id", "")).strip()
    specialist = str(result.get("specialist_agent_id", "")).strip()

    print(f"source={source}")
    print(f"provider={provider}")
    print(f"model={model}")
    print(f"pod_manager_agent_id={pod_manager}")
    print(f"specialist_agent_id={specialist}")

    if has_provider_key and source != "llm":
        print("FAIL: provider key detected but CEO delegation used fallback", file=sys.stderr)
        return 1
    if not pod_manager or not specialist:
        print("FAIL: delegation did not return agent IDs", file=sys.stderr)
        return 1
    if not has_provider_key and source == "fallback":
        print("PASS: no provider keys detected; deterministic fallback is healthy")
        return 0
    print("PASS: CEO delegation smoke succeeded")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
