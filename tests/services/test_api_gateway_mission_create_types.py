"""P0: mission_type survives the gateway and aliases map to official enums."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api-gateway"))
sys.path.insert(0, str(ROOT))

from shared_runtime.mission_types import (  # noqa: E402
    UnknownMissionTypeError,
    normalize_mission_type,
)

api_gateway_main = importlib.import_module("api_gateway.main")


def test_unofficial_repo_aliases_normalize_to_official_enum() -> None:
    assert normalize_mission_type("update") == "IMPORT_MODERNIZE"
    assert normalize_mission_type("add_feature") == "IMPORT_MODERNIZE"
    assert normalize_mission_type("refactor") == "IMPORT_MODERNIZE"
    assert normalize_mission_type("analyze") == "ANALYZE_ONLY"
    assert normalize_mission_type("port") == "PORT"
    assert normalize_mission_type("") == "BUILD_NEW"
    assert normalize_mission_type(None) == "BUILD_NEW"


def test_unknown_mission_type_fails_closed_not_build_new() -> None:
    with pytest.raises(UnknownMissionTypeError):
        normalize_mission_type("not-a-real-type")


def test_gateway_persists_mission_type_on_record_and_metadata() -> None:
    payload = api_gateway_main.MissionCreate(
        prompt="Build a cli",
        mission_type="port",
        metadata={},
    )
    metadata = api_gateway_main._apply_mission_classification(payload, dict(payload.metadata))
    assert metadata["mission_type"] == "PORT"
    assert metadata["output_mode"] == "FULL_TRANSFORMATION"
    persist = {
        "mission_type": metadata.get("mission_type"),
        "depth_mode": metadata.get("depth_mode"),
        "output_mode": metadata.get("output_mode"),
        "data_classification": metadata.get("data_classification"),
        "metadata": metadata,
    }
    assert persist["mission_type"] == "PORT"
    assert persist["metadata"]["mission_type"] == "PORT"


def test_gateway_persists_output_mode_depth_and_classification() -> None:
    payload = api_gateway_main.MissionCreate(
        prompt="Build a cli",
        mission_type="BUILD_NEW",
        output_mode="PLAN_ONLY",
        depth_mode="REGULATED",
        data_classification="TIER_3_REGULATED",
        metadata={},
    )
    metadata = api_gateway_main._apply_mission_classification(payload, {})
    assert metadata["output_mode"] == "PLAN_ONLY"
    assert metadata["depth_mode"] == "REGULATED"
    assert metadata["data_classification"] == "TIER_3_REGULATED"


def test_unknown_type_on_gateway_is_422() -> None:
    payload = api_gateway_main.MissionCreate(
        prompt="Build a cli",
        mission_type="spaceship",
        metadata={},
    )
    with pytest.raises(HTTPException) as exc:
        api_gateway_main._apply_mission_classification(payload, {})
    assert exc.value.status_code == 422


def test_metadata_only_type_is_normalized() -> None:
    payload = api_gateway_main.MissionCreate(prompt="update the app", metadata={"mission_type": "update"})
    metadata = api_gateway_main._apply_mission_classification(payload, dict(payload.metadata))
    assert metadata["mission_type"] == "IMPORT_MODERNIZE"


def test_intake_passes_source_code_into_pm_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    import inspect

    from orchestrator.mission_flow_v2 import phases_intake

    source = inspect.getsource(phases_intake._prepare_pm_intake)
    assert "source_code=source_code" in source
    assert 'metadata.get("source_code")' in source


def test_persist_body_includes_classification_fields() -> None:
    src = Path(api_gateway_main.__file__).read_text(encoding="utf-8")
    assert '"mission_type": metadata.get("mission_type")' in src
    assert '"output_mode": metadata.get("output_mode")' in src
