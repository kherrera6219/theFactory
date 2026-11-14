"""Tests for Phase 5: full-repo workspace indexer, AIM at import, maturity matrix, and sliced SOW."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
ORCH_ROOT = REPO_ROOT / "services" / "orchestrator"
if str(ORCH_ROOT) not in sys.path:
    sys.path.insert(0, str(ORCH_ROOT))

from orchestrator.aim_generator import generate_aim, generate_workspace_aim, load_workspace_aim
from orchestrator.context_pack import (
    build_specialist_context_pack,
    parse_file_bundle,
    render_context_pack_for_prompt,
)
from orchestrator.language_maturity import (
    format_language_maturity_markdown,
    format_language_maturity_summary,
    get_language_maturity_table,
    recommend_port_target_languages,
    write_language_maturity_doc,
)
from orchestrator.llm_delegation.prompts import (
    _build_codegen_prompt,
    _build_pm_feature_contract_prompt,
)
from orchestrator.mission_flow_v2.base import build_mission_charter, validate_mission_charter_schema
from orchestrator.workspace import MissionWorkspace
from orchestrator.workspace_api import import_workspace_from_payload
from orchestrator.workspace_indexer import (
    chunk_workspace_file,
    index_workspace,
    load_workspace_index,
    search_workspace_chunks,
)

BENCHMARK_ROOT = REPO_ROOT / "tests" / "benchmark" / "brownfield"

EXPECTED_BENCHMARK_DISCOVERY: dict[str, dict[str, str]] = {
    "csharp_net_console": {
        "language": "csharp",
        "source_framework": "dotnet-console",
        "test_command": "dotnet test LegacyCsv.csproj --nologo",
    },
    "c_buffer_lib": {
        "language": "c",
        "source_framework": "c99-make",
        "test_command": "make test",
    },
    "express_cjs_node": {
        "language": "javascript",
        "source_framework": "express-commonjs",
        "test_command": "node test/router.test.js",
    },
    "flask_legacy_py": {
        "language": "python",
        "source_framework": "flask",
        "test_command": "python -m pytest -q test_app.py",
    },
    "maven_legacy_java8": {
        "language": "java",
        "source_framework": "maven-java8",
        "test_command": "mvn -q test",
    },
    "php7_legacy_app": {
        "language": "php",
        "source_framework": "composer-php7",
        "test_command": "vendor/bin/phpunit tests",
    },
    "port_cli_py_to_go": {
        "language": "python",
        "source_framework": "python-argparse",
        "test_command": "python -m pytest -q test_app.py && cd reference_go && go test ./...",
    },
}


def test_specialist_prompt_preserves_files_over_12kb_without_truncation(tmp_path: Path) -> None:
    """Specialist codegen prompt for a slice must contain full >12 KB file contents."""
    large_body = "\n".join(
        [
            "def process_record(record_id: int) -> str:",
            *[f"    step_{i} = record_id + {i}" for i in range(520)],
            "    return f'SENTINEL_END_OF_FILE_{record_id}'",
        ]
    )
    assert len(large_body) > 14_000

    ws = MissionWorkspace.create_from_files(
        {
            "src/large_service.py": large_body,
            "src/helpers.py": "def helper_fn() -> int:\n    return 42\n",
            "tests/test_service.py": "from src.large_service import process_record\n",
        },
        workspace_id="ws-large-file",
        root=tmp_path,
    )
    idx = index_workspace(ws)
    aim = generate_workspace_aim(ws, index_data=idx)
    pack = build_specialist_context_pack(
        ws=ws,
        slice_spec={
            "id": "slice-1",
            "title": "Modernize large service",
            "files": ["src/large_service.py"],
        },
        aim=aim,
        index_data=idx,
        query="process_record",
    )
    prompt = _build_codegen_prompt(
        mission_context={
            "mission_id": "mission-large",
            "imported_source_code": render_context_pack_for_prompt(pack),
            "context_pack": pack,
            "feature_contract": {"title": "Large file slice"},
        },
        mission_contract={
            "contract_summary": "Update process_record without losing tail logic",
            "acceptance_criteria": ["SENTINEL_END_OF_FILE marker remains implemented"],
            "deliverables": [{"name": "src/large_service.py", "artifact_hint": "src/large_service.py"}],
        },
        logicnodes=[],
        target_language="python",
        specialist_agent_id="AGENT-08-PYTHON",
        recommended_provider="gemini",
        recommended_model="gemini-4-argon",
    )
    assert "SENTINEL_END_OF_FILE_{record_id}" in prompt
    assert len(pack["target_files"]) == 1
    assert pack["target_files"][0]["content"] == large_body


def test_reimporting_unchanged_workspace_reembeds_zero_chunks(tmp_path: Path) -> None:
    """Incremental SHA-256 deduplication skips embedding on unchanged chunks."""
    ws = MissionWorkspace.create_from_files(
        {
            "app/calc.py": (
                "from app.tax import tax_rate\n\n"
                "def total_price(amount: float) -> float:\n"
                "    return amount * (1.0 + tax_rate())\n"
            ),
            "app/tax.py": "def tax_rate() -> float:\n    return 0.08\n",
        },
        workspace_id="ws-dedup",
        root=tmp_path,
    )
    embed_calls: list[str] = []

    def _fake_embed(text: str) -> list[float]:
        embed_calls.append(text)
        return [0.1, 0.2, 0.3]

    first = index_workspace(ws, embed_fn=_fake_embed)
    assert first["index_stats"]["total_chunks"] >= 2
    assert first["index_stats"]["chunks_reembedded"] == first["index_stats"]["total_chunks"]
    assert len(embed_calls) == first["index_stats"]["total_chunks"]

    embed_calls.clear()
    second = index_workspace(ws, embed_fn=_fake_embed)
    assert second["index_stats"]["chunks_reembedded"] == 0
    assert second["index_stats"]["reused_chunks"] == second["index_stats"]["total_chunks"]
    assert embed_calls == []
    assert load_workspace_index(ws) is not None


@pytest.mark.parametrize("project_name,expected", list(EXPECTED_BENCHMARK_DISCOVERY.items()))
def test_benchmark_corpus_indexing_and_aim_discovery(
    tmp_path: Path,
    project_name: str,
    expected: dict[str, str],
) -> None:
    """Index + AIM at import accurately detects language, framework, and test_command."""
    project_dir = BENCHMARK_ROOT / project_name
    settings = SimpleNamespace(workspace_root=str(tmp_path))
    result = import_workspace_from_payload(
        {
            "source_type": "local",
            "local_path": str(project_dir),
            "display_name": project_name,
        },
        settings=settings,
    )
    aim = result["aim"]
    td = aim["test_discovery"]
    assert aim["workspace_id"] == result["repository"]["workspace_id"]
    assert aim["primary_language"] == expected["language"]
    assert expected["source_framework"] in (aim.get("frameworks") or [])
    assert td["test_command"] == expected["test_command"]
    assert td["has_tests"] is True
    assert len(td["test_files"]) >= 1

    # Persisted AIM + index exist in .thefactory/ and stay excluded from git status/diff.
    ws = MissionWorkspace.open(aim["workspace_id"], settings=settings)
    assert load_workspace_aim(ws) is not None
    assert ws.modified_files() == []
    assert not any(f["path"].startswith(".thefactory") for f in ws.list_files())


def test_symbol_graph_projection_methods_and_search(tmp_path: Path) -> None:
    """Symbol graph records projection_method per file and answers targeted queries."""
    ws = MissionWorkspace.create_from_files(
        {
            "core/engine.py": "def compute_invoice(x: int) -> int:\n    return x * 2\n",
            "api/handler.py": (
                "from core.engine import compute_invoice\n\n"
                "def handle(val: int) -> int:\n"
                "    return compute_invoice(val)\n"
            ),
            "web/client.ts": "export function renderInvoice(total: number): string { return String(total); }\n",
            "README.md": "# Legacy Billing App\nHandles invoice calculation.\n",
        },
        workspace_id="ws-graph",
        root=tmp_path,
    )
    idx = index_workspace(ws)
    graph = idx["symbol_graph"]
    assert graph["projection_methods"]["core/engine.py"] == "ast"
    assert graph["projection_methods"]["web/client.ts"] in {"tree-sitter", "structural_ast", "regex"}
    assert "api/handler.py" in graph["importers_by_path"].get("core/engine.py", [])
    assert "api/handler.py" in graph["callers_by_path"].get("core/engine.py", [])

    hits = search_workspace_chunks(ws, "compute_invoice", index_data=idx)
    assert hits and any(h["path"] == "core/engine.py" for h in hits)

    # Syntax-error Python falls back to sliding window safely.
    bad_py = chunk_workspace_file("broken.py", "def broken(:\n    pass\n")
    assert bad_py["projection_method"] == "sliding_window"


def test_language_maturity_matrix_and_port_recommendations() -> None:
    """Maturity table reflects live tables and ranks Tier 1 PORT targets first."""
    table = get_language_maturity_table()
    by_lang = {row["language"]: row for row in table}
    assert by_lang["python"]["maturity_tier"] == "Tier 1 — Full Production"
    assert by_lang["go"]["maturity_tier"] == "Tier 1 — Full Production"
    assert by_lang["matlab"]["maturity_tier"].startswith("Tier 3")

    recs = recommend_port_target_languages(source_language="php", limit=3)
    assert len(recs) == 3
    assert all(r["language"] != "php" for r in recs)

    md_path = REPO_ROOT / "docs" / "LANGUAGE_MATURITY.md"
    assert md_path.read_text(encoding="utf-8") == format_language_maturity_markdown()


@pytest.mark.asyncio
async def test_pm_prompt_and_mission_charter_with_slices_and_baseline_policy(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """PM contract + charter validate with slices[], baseline_policy, and target recommendation."""
    ws = MissionWorkspace.create_from_files(
        {
            "app.py": "import argparse\ndef main():\n    return 0\n",
            "test_app.py": "def test_ok():\n    assert True\n",
        },
        workspace_id="ws-sow",
        root=tmp_path,
    )
    idx = index_workspace(ws)
    aim = generate_workspace_aim(ws, index_data=idx)

    pm_prompt = _build_pm_feature_contract_prompt(
        prompt="Port CLI to Go preserving outputs",
        mission_type="PORT",
        depth_mode="STANDARD",
        output_mode="FULL_BUILD",
        requested_target_language="go",
        recommended_provider="gemini",
        recommended_model="gemini-4-argon",
        workspace_aim=aim,
        workspace_chunks=idx["chunks"],
        language_maturity_summary=format_language_maturity_summary(),
    )
    assert "Workspace Application Intelligence Map" in pm_prompt
    assert "Factory Language Maturity Matrix" in pm_prompt
    assert "baseline_policy" in pm_prompt
    assert '"slices"' in pm_prompt

    from orchestrator import llm_delegation

    async def _fake_pm_call(**kwargs: Any) -> tuple[dict[str, Any], str, str, str]:
        return (
            {
                "title": "Port Python CLI to Go",
                "summary": "Port CLI behaviour to Go slice by slice.",
                "intake_status": "ready",
                "functional_requirements": ["Match CLI exit codes and stdout"],
                "non_functional_requirements": ["Zero new runtime deps"],
                "acceptance_criteria": ["go test ./... passes"],
                "assumptions": ["Go 1.22 toolchain"],
                "target_languages": ["go"],
                "estimated_complexity": "medium",
                "human_approval_required": True,
                "out_of_scope": ["GUI frontend"],
                "deliverables": [{"name": "cmd/main.go", "artifact_hint": "cmd/main.go"}],
                "engagement_type": "PORT",
                "baseline_policy": "preserve_existing_behaviour",
                "target_versions": {"go": "1.22"},
                "slices": [
                    {
                        "id": "slice-1",
                        "title": "CLI argument parsing & core output",
                        "files": ["app.py", "test_app.py"],
                        "acceptance_criteria": ["Matches Python stdout"],
                        "depends_on": [],
                    }
                ],
                "recommended_target_language": {
                    "language": "go",
                    "rationale": "Tier 1 sandbox + test support",
                    "maturity_tier": "Tier 1 — Full Production",
                },
            },
            "gemini",
            "gemini-4-argon",
            "primary",
        )

    monkeypatch.setattr(
        "orchestrator.llm_delegation.generators._call_with_agent_system",
        _fake_pm_call,
    )
    contract = await llm_delegation.generate_pm_feature_contract(
        prompt="Port CLI to Go preserving outputs",
        mission_type="PORT",
        depth_mode="STANDARD",
        output_mode="FULL_BUILD",
        requested_target_language="go",
        workspace_aim=aim,
        workspace_chunks=idx["chunks"],
        language_maturity_summary=format_language_maturity_summary(),
    )
    assert contract["baseline_policy"] == "preserve_existing_behaviour"
    assert len(contract["slices"]) == 1
    assert contract["target_versions"] == {"go": "1.22"}
    assert contract["recommended_target_language"]["language"] == "go"

    charter = build_mission_charter(
        mission_id="mission-slice-charter",
        prompt="Port CLI to Go",
        requested_target_language="go",
        feature_contract=contract,
        mission_type="PORT",
        depth_mode="STANDARD",
        output_mode="FULL_BUILD",
    )
    assert charter["baseline_policy"] == "preserve_existing_behaviour"
    assert len(charter["slices"]) == 1

    # Validate runtime charter schema and verify strict Draft202012 schema declares Phase 5 fields.
    import jsonschema

    validate_mission_charter_schema(charter)
    strict_schema = json.loads(
        (REPO_ROOT / "schemas" / "mission_charter.v1.schema.json").read_text(encoding="utf-8")
    )
    jsonschema.Draft202012Validator.check_schema(strict_schema)
    for prop in ("slices", "baseline_policy", "target_versions", "recommended_target_language"):
        assert prop in strict_schema["properties"]

    # Test generate_aim workspace reuse path with monkeypatched LLM call.
    async def _fake_aim_call(**kwargs: Any) -> tuple[dict[str, Any], str, str, str]:
        return (
            {"repository_summary": "Workspace summary", "complexity_assessment": "low"},
            "gemini",
            "gemini-4-argon",
            "primary",
        )

    monkeypatch.setattr(llm_delegation, "_call_with_recommendation", _fake_aim_call)
    merged_aim = await generate_aim(
        mission_id="mission-aim-ws",
        source_code="",
        prompt="Analyze workspace",
        mission_type="PORT",
        requested_target_language="go",
        feature_contract=contract,
        settings=SimpleNamespace(workspace_root=str(tmp_path)),
        workspace_id="ws-sow",
    )
    assert merged_aim["workspace_id"] == "ws-sow"
    assert merged_aim["test_discovery"]["test_command"] == "python -m pytest -q test_app.py"


def test_context_pack_aim_and_maturity_edge_cases(tmp_path: Path) -> None:
    """Cover non-workspace bundle parsing, empty/unknown inputs, and AIM/maturity helpers."""
    assert parse_file_bundle("") == []
    inline = parse_file_bundle("print('inline')\n")
    assert inline == [{"path": "inline_source.txt", "content": "print('inline')\n"}]

    bundled = (
        "## FILE src/a.py\n"
        "def alpha():\n    return 1\n"
        "## FILE src/b.py\n"
        "def beta():\n    return 2\n"
    )
    pack_bundle = build_specialist_context_pack(
        ws=None,
        source_code=bundled,
        slice_spec={
            "id": "s1",
            "title": "Alpha slice",
            "description": "Migrate alpha module.",
            "files": ["./src/a.py"],
            "acceptance_criteria": ["alpha returns 1"],
        },
        aim={
            "primary_language": "python",
            "frameworks": ["flask"],
            "entrypoints": ["src/a.py"],
            "test_discovery": {"test_command": "pytest -q", "test_files": ["tests/test_a.py"]},
        },
        query="alpha",
    )
    assert pack_bundle["target_file_paths"] == ["src/a.py"]
    assert "tests/test_a.py" in pack_bundle["neighbor_paths"]
    rendered = render_context_pack_for_prompt(pack_bundle)
    assert "Active Execution Slice: s1" in rendered
    assert "Slice scope: Migrate alpha module." in rendered
    assert "Slice acceptance criteria:" in rendered
    assert "Discovered test command: pytest -q" in rendered
    assert "Neighbor files: tests/test_a.py" in rendered
    assert "## FILE src/a.py" in rendered
    assert render_context_pack_for_prompt("not-a-dict") == ""  # type: ignore[arg-type]

    # Empty workspace AIM/index helpers + query miss branch.
    ws_empty = MissionWorkspace.create_from_files(
        {"notes.txt": "plain text note\n", "main.go": "package main\nfunc main() {}\n"},
        workspace_id="ws-edge",
        root=tmp_path,
    )
    assert load_workspace_aim(ws_empty) is None
    assert load_workspace_index(ws_empty) is None
    generated_aim = generate_workspace_aim(ws_empty)
    assert generated_aim["workspace_id"] == "ws-edge"
    assert load_workspace_aim(ws_empty) is not None
    assert len(search_workspace_chunks(ws_empty, "")) >= 1
    assert search_workspace_chunks(ws_empty, "xyznonexistenttoken999") == []

    # Language maturity edge cases.
    unknown_recs = recommend_port_target_languages(source_language="brainfuck", limit=3)
    assert len(unknown_recs) == 3
    java_recs = recommend_port_target_languages(source_language="java", limit=5)
    assert len(java_recs) >= 1
    assert all(r["language"] != "java" for r in java_recs)
    markdown = format_language_maturity_markdown()
    assert "Tier 1" in markdown
    assert "| `python` |" in markdown
    written_doc = write_language_maturity_doc(tmp_path / "MATURITY.md")
    assert written_doc.exists()
