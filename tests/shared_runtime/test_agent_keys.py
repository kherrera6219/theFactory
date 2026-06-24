"""Unit coverage for shared agent service-key resolution."""
from __future__ import annotations

import json

import pytest

from shared_runtime.agent_keys import service_api_key_for_agent


def test_file_backed_agent_key_rotates_without_restart(tmp_path) -> None:
    key_file = tmp_path / "agent-keys.json"
    env = {"AGENT_SERVICE_KEY_FILE": str(key_file)}
    key_file.write_text(
        json.dumps({"AGENT-14-PYTHON": "first-rotating-agent-key-123"}),
        encoding="utf-8",
    )

    first = service_api_key_for_agent(
        "AGENT-14-PYTHON",
        fallback_key="fallback-key-value-123456",
        env=env,
    )
    key_file.write_text(
        json.dumps({"AGENT-14-PYTHON": "second-rotating-agent-key-456"}),
        encoding="utf-8",
    )
    second = service_api_key_for_agent(
        "AGENT-14-PYTHON",
        fallback_key="fallback-key-value-123456",
        env=env,
    )

    assert first == "first-rotating-agent-key-123"
    assert second == "second-rotating-agent-key-456"


def test_direct_agent_env_key_overrides_rotating_file(tmp_path) -> None:
    key_file = tmp_path / "agent-keys.json"
    key_file.write_text(
        json.dumps({"AGENT-14-PYTHON": "file-agent-key-value-123"}),
        encoding="utf-8",
    )
    env = {
        "AGENT_SERVICE_KEY_FILE": str(key_file),
        "AGENT_14_PYTHON_SERVICE_API_KEY": "direct-agent-key-value-456",
    }

    resolved = service_api_key_for_agent(
        "AGENT-14-PYTHON",
        fallback_key="fallback-key-value-123456",
        env=env,
    )

    assert resolved == "direct-agent-key-value-456"


def test_invalid_configured_key_file_fails_closed(tmp_path) -> None:
    key_file = tmp_path / "agent-keys.json"
    key_file.write_text("not-json", encoding="utf-8")

    with pytest.raises(RuntimeError, match="failed to load agent service key file"):
        service_api_key_for_agent(
            "AGENT-14-PYTHON",
            fallback_key="fallback-key-value-123456",
            env={"AGENT_SERVICE_KEY_FILE": str(key_file)},
        )
