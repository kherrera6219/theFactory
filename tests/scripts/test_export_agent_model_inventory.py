import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "export_agent_model_inventory.py"

spec = importlib.util.spec_from_file_location("export_agent_model_inventory", MODULE_PATH)
assert spec is not None and spec.loader is not None
inventory = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = inventory
spec.loader.exec_module(inventory)


def test_build_inventory_classifies_preview_and_stable_routes(monkeypatch) -> None:
    monkeypatch.setattr(
        inventory,
        "build_agent_integrations_snapshot",
        lambda: {
            "agents": [
                {
                    "agent_id": "AGENT-01-PM",
                    "llm_recommendation": {
                        "provider": "openai",
                        "model": "gpt-5.5",
                    },
                },
                {
                    "agent_id": "AGENT-30-PODD-MGR",
                    "llm_recommendation": {
                        "provider": "gemini",
                        "model": "gemini-3.5-flash",
                        "fallback_provider": "openai",
                        "fallback_model": "gpt-5.5",
                    },
                },
            ]
        },
    )

    payload = inventory.build_inventory()
    assert payload["summary"]["total_agents"] == 2
    assert payload["summary"]["blocked_agent_count"] == 1
    assert payload["summary"]["lifecycle_counts"]["preview"] == 1
