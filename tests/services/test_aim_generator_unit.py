from __future__ import annotations

import asyncio
import importlib
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

aim_generator = importlib.import_module("orchestrator.aim_generator")
llm_delegation = importlib.import_module("orchestrator.llm_delegation")


def test_mission_requires_aim_only_for_source_analysis_types() -> None:
    assert aim_generator.mission_requires_aim("ANALYZE_ONLY") is True
    assert aim_generator.mission_requires_aim("import_modernize") is True
    assert aim_generator.mission_requires_aim("BUILD_NEW") is False
    assert aim_generator.mission_requires_aim(None) is False


def test_extract_all_languages_parses_multifile_bundle_without_raw_content_in_manifest() -> None:
    source_code = (
        "## FILE app.py\n"
        "import csv\n\n"
        "class Reader:\n"
        "    def rows(self):\n"
        "        return []\n\n"
        "## FILE web.ts\n"
        "import React from 'react';\n"
        "export function App() { return null; }\n"
    )

    summary = aim_generator._extract_all_languages(
        source_code=source_code,
        primary_language="python",
    )

    assert summary["files_seen"] == 2
    assert summary["files_analyzed"] == 2
    assert "python" in summary["detected_languages"]
    assert "typescript" in summary["detected_languages"]
    assert summary["total_functions"] >= 1
    assert summary["total_classes"] >= 1
    assert all("content" not in item for item in summary["file_manifest"])


def test_generate_aim_uses_bounded_extraction_summary(monkeypatch) -> None:
    captured: dict[str, str] = {}

    async def _fake_call(*, recommendation: dict[str, Any], prompt: str, call_context: str):
        captured["prompt"] = prompt
        return (
            {
                "repository_summary": "A small CSV reader.",
                "detected_languages": ["python"],
                "primary_language": "python",
                "complexity_assessment": "low",
                "detected_dependencies": ["csv"],
                "risks": ["Validate file input"],
                "risk_flags": ["data"],
                "human_approval_recommended": False,
                "recommended_approach": "Review parser behavior before changes.",
                "recommended_mission_type": "ANALYZE_ONLY",
            },
            "openai",
            "gpt-5.5",
            "primary",
        )

    monkeypatch.setattr(llm_delegation, "_call_with_recommendation", _fake_call)

    aim = asyncio.run(
        aim_generator.generate_aim(
            mission_id="mission-1",
            source_code="## FILE app.py\nSECRET_RAW_SENTINEL = 'do-not-forward'\n",
            prompt="Analyze this repo",
            mission_type="ANALYZE_ONLY",
            requested_target_language="python",
            feature_contract={"title": "CSV review", "summary": "Review CSV reader"},
            settings=object(),
        )
    )

    assert aim["schema_version"] == "aim.v1"
    assert aim["source"] == "llm"
    assert aim["repository_summary"] == "A small CSV reader."
    assert "SECRET_RAW_SENTINEL" not in captured["prompt"]
    assert "source_digest_sha256" in captured["prompt"]
