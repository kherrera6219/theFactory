"""Phase 7 tests: sliced execution, crash recovery, PM change orders, MIGRATION_NOTES, and PR export."""
from __future__ import annotations

import io
import zipfile
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from orchestrator.github_pr_exporter import (
    build_github_pr_payload,
    export_mission_as_github_pr,
    scrub_github_token_from_metadata,
    validate_no_plaintext_github_token,
)
from orchestrator.mission_flow_v2.transitions import V2_EVENT_TO_PHASE
from orchestrator.models import MissionState
from orchestrator.sliced_execution import (
    apply_slice_change_order,
    execute_mission_slices,
    extract_mission_slices,
    generate_migration_notes,
    topological_sort_slices,
)
from orchestrator.workspace import MissionWorkspace


def _zip_bytes(files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path, content in files.items():
            zf.writestr(path, content)
    return buf.getvalue()


def _make_workspace(tmp_path, files: dict[str, str] | None = None) -> MissionWorkspace:
    initial = files or {"app.py": "def greet():\n    return 'hello'\n"}
    return MissionWorkspace.create_from_zip(
        _zip_bytes(initial),
        root=tmp_path,
        workspace_id="ws-phase7-test",
    )


def test_transition_slice_events_registered():
    for event_type in (
        "MISSION_SLICE_STARTED",
        "MISSION_SLICE_VERIFIED",
        "MISSION_SLICE_REGRESSED",
        "MISSION_SLICE_PAUSED",
    ):
        assert V2_EVENT_TO_PHASE[event_type] == MissionState.running


def test_topological_sort_slices_orders_dependencies_and_handles_cycles():
    slices = [
        {"id": "slice-c", "title": "API", "depends_on": ["slice-b"]},
        {"id": "slice-a", "title": "Model", "depends_on": []},
        {"id": "slice-b", "title": "Service", "depends_on": ["slice-a", "unknown-id"]},
    ]
    ordered = topological_sort_slices(slices)
    assert [s["id"] for s in ordered] == ["slice-a", "slice-b", "slice-c"]

    cyclic = [
        {"id": "s1", "depends_on": ["s2"]},
        {"id": "s2", "depends_on": ["s1"]},
    ]
    cyclic_ordered = topological_sort_slices(cyclic)
    assert [s["id"] for s in cyclic_ordered] == ["s1", "s2"]


@pytest.mark.asyncio
async def test_execute_mission_slices_sequential_commits_and_empty_noop(tmp_path):
    empty_res = await execute_mission_slices(mission_id="m-empty", metadata={})
    assert empty_res["sliced"] is False

    ws = _make_workspace(tmp_path)
    events: list[tuple[str, str]] = []
    persisted: list[int] = []

    class _FakeStorage:
        @staticmethod
        def update_mission_metadata(_settings, _mission_id, meta):
            persisted.append(len(meta.get("slices_completed") or []))
            return meta

    metadata: dict[str, object] = {
        "mission_charter": {
            "title": "Refactor module",
            "slices": [
                {"id": "slice-2", "title": "Wire endpoint", "files": ["api.py"], "depends_on": ["slice-1"]},
                {"id": "slice-1", "title": "Core logic", "files": ["app.py"], "depends_on": []},
            ],
        },
        "application_intelligence_map": {"primary_language": "python", "files": []},
    }

    async def _codegen(*, slice_spec, context_pack, ws, metadata):
        sid = slice_spec["id"]
        if sid == "slice-1":
            return {"files": {"app.py": "def greet():\n    return 'hi v2'\n"}, "cost_usd": 0.01}
        return {"files": {"api.py": "from app import greet\n"}, "cost_usd": 0.02}

    async def _harness(*, slice_spec, context_pack, ws, metadata):
        return {"files": {}}

    async def _emit(event_type, slice_id, _details):
        events.append((event_type, slice_id))

    result = await execute_mission_slices(
        mission_id="m-slice-1",
        metadata=metadata,
        ws=ws,
        settings=SimpleNamespace(),
        storage_module=_FakeStorage,
        codegen_fn=_codegen,
        harness_fn=_harness,
        preservation_fn=lambda **_kw: {"verdict": "PRESERVED"},
        event_emitter=_emit,
    )

    assert result["sliced"] is True
    assert result["paused"] is False
    assert result["regressed"] is False
    completed = metadata["slices_completed"]
    assert isinstance(completed, list)
    assert [item["id"] for item in completed] == ["slice-1", "slice-2"]
    assert all(item["commit_sha"] for item in completed)
    assert persisted == [1, 2, 2]
    assert events == [
        ("MISSION_SLICE_STARTED", "slice-1"),
        ("MISSION_SLICE_VERIFIED", "slice-1"),
        ("MISSION_SLICE_STARTED", "slice-2"),
        ("MISSION_SLICE_VERIFIED", "slice-2"),
    ]


@pytest.mark.asyncio
async def test_execute_slices_crash_recovery_skips_completed_and_pause_checkpoint(tmp_path):
    ws = _make_workspace(tmp_path)
    executed_ids: list[str] = []

    metadata: dict[str, object] = {
        "slices": [
            {"id": "slice-1", "title": "Done before crash", "files": ["app.py"]},
            {"id": "slice-2", "title": "Middle pause", "files": ["mid.py"], "pause_after_slice": True},
            {"id": "slice-3", "title": "Final", "files": ["end.py"]},
        ],
        "slices_completed": [
            {"id": "slice-1", "title": "Done before crash", "files": ["app.py"], "commit_sha": "deadbeef"},
        ],
    }

    async def _codegen(*, slice_spec, **_kw):
        executed_ids.append(slice_spec["id"])
        return {"files": {slice_spec["files"][0]: "# generated\n"}}

    paused_res = await execute_mission_slices(
        mission_id="m-resume",
        metadata=metadata,
        ws=ws,
        codegen_fn=_codegen,
        preservation_fn=lambda **_kw: {"verdict": "PRESERVED"},
    )
    assert paused_res["paused"] is True
    assert paused_res["paused_after_slice_id"] == "slice-2"
    assert metadata["slice_paused"] is True
    # slice-1 was skipped on recovery, slice-3 stopped at PM pause checkpoint
    assert executed_ids == ["slice-2"]

    change_res = apply_slice_change_order(
        metadata,
        [
            {"id": "slice-1", "title": "Tampered", "files": ["evil.py"]},
            {"id": "slice-3", "title": "Revised Final", "files": ["revised.py"]},
            {"id": "slice-4", "title": "New Extra", "files": ["extra.py"]},
        ],
        reason="PM updated remaining scope",
    )
    assert change_res["preserved_slice_ids"] == ["slice-1", "slice-2"]
    assert change_res["updated_remaining_ids"] == ["slice-3", "slice-4"]
    assert metadata["slice_paused"] is False
    # Completed slice commits remain untouched
    assert metadata["slices_completed"][0]["commit_sha"] == "deadbeef"
    assert extract_mission_slices(metadata)[-1]["id"] == "slice-4"


@pytest.mark.asyncio
async def test_execute_slices_self_repair_and_regression_stop(tmp_path):
    ws = _make_workspace(tmp_path)
    calls = {"preserve": 0}

    def _preserv(**_kw):
        calls["preserve"] += 1
        return {"verdict": "REGRESSED"} if calls["preserve"] == 1 else {"verdict": "PRESERVED"}

    metadata: dict[str, object] = {"slices": [{"id": "s1", "title": "Repairable", "files": ["app.py"]}]}
    repaired = await execute_mission_slices(
        mission_id="m-repair",
        metadata=metadata,
        ws=ws,
        codegen_fn=lambda **_kw: {"files": {"app.py": "broken = 1\n"}},
        preservation_fn=_preserv,
        repair_fn=lambda **_kw: {"files": {"app.py": "def greet():\n    return 'fixed'\n"}},
    )
    assert repaired["regressed"] is False
    assert calls["preserve"] == 2

    # Persistent regression fails closed cleanly
    fail_meta: dict[str, object] = {"slices": [{"id": "s1", "title": "Broken", "files": ["app.py"]}]}
    failed = await execute_mission_slices(
        mission_id="m-fail",
        metadata=fail_meta,
        ws=ws,
        codegen_fn=lambda **_kw: {"files": {"app.py": "bad\n"}},
        preservation_fn=lambda **_kw: {"verdict": "REGRESSED"},
        repair_fn=lambda **_kw: {"files": {"app.py": "still bad\n"}},
        max_repair_attempts=1,
    )
    assert failed["regressed"] is True
    assert failed["failed_slice_id"] == "s1"


def test_generate_migration_notes_and_github_pr_exporter_security_negative():
    meta: dict[str, object] = {
        "mission_type": "PORT",
        "port_target_language": "python",
        "mission_contract": {"title": "Legacy Service Port", "objective": "Port service cleanly."},
        "slices_completed": [
            {"id": "s1", "title": "Core", "files": ["core.py"], "commit_sha": "abcdef123456789", "verdict": "PRESERVED"}
        ],
        "runtime_qc_report": {"preservation_gate": {"verdict": "PRESERVED", "regressions": []}},
        "equivalence_report": {"status": "passed"},
        "sbom_delta": {"added": ["pydantic"], "removed": ["flask"]},
        "github_pr_result": {"pr_url": "https://github.com/org/repo/pull/7"},
    }
    notes = generate_migration_notes("m-notes", meta)
    assert "# Migration Notes — Legacy Service Port" in notes
    assert "| `s1` | Core | `PRESERVED` | `abcdef123456` | core.py |" in notes
    assert "Preservation Verdict" in notes
    assert "https://github.com/org/repo/pull/7" in notes

    # Security negative test: plaintext GitHub tokens in metadata MUST be rejected and scrubbed
    unsafe_meta = {
        "github_token": "ghp_secret_leak_123",
        "github_pr_export": {"enabled": True, "repo": "org/repo", "github_token": "ghp_nested"},
    }
    with pytest.raises(ValueError, match="mission_vault"):
        validate_no_plaintext_github_token(unsafe_meta)
    scrubbed = scrub_github_token_from_metadata(unsafe_meta)
    assert "github_token" not in scrubbed
    assert "github_token" not in scrubbed["github_pr_export"]

    payload = build_github_pr_payload("m-notes", meta, head_branch="thefactory/mission-m-notes")
    assert payload["title"] == "Legacy Service Port"
    assert "| `s1` | Core | `abcdef123456` | `PRESERVED` |" in payload["body"]


@pytest.mark.asyncio
async def test_export_mission_as_github_pr_uses_vault_and_never_leaks_token():
    skipped = await export_mission_as_github_pr("m-skip", {"github_pr_export": {"enabled": False}})
    assert skipped["skipped"] is True

    # Plaintext token in metadata is rejected even when enabled
    with pytest.raises(ValueError, match="mission_vault"):
        await export_mission_as_github_pr(
            "m-unsafe",
            {"github_pr_export": {"enabled": True, "repo": "org/repo", "github_token": "ghp_abc"}},
        )

    missing_vault = await export_mission_as_github_pr(
        "m-no-token",
        {"github_pr_export": {"enabled": True, "repo": "org/repo"}},
        vault_loader=lambda _r, _mid: {},
    )
    assert missing_vault["exported"] is False
    assert "missing" in missing_vault["reason"]

    fake_response = SimpleNamespace(
        status_code=201,
        json=lambda: {"number": 88, "html_url": "https://github.com/org/repo/pull/88"},
    )
    fake_client = MagicMock()

    async def _post(url, json, headers):
        assert url == "https://api.github.com/repos/org/repo/pulls"
        assert headers["Authorization"] == "Bearer vaulted-gh-pat-xyz"
        assert json["base"] == "main"
        return fake_response

    fake_client.post = _post
    meta: dict[str, object] = {
        "mission_contract": {"title": "Brownfield Fix", "objective": "Fix bug safely."},
        "github_pr_export": {"enabled": True, "repo": "org/repo", "base_branch": "main"},
        "slices_completed": [
            {"id": "s1", "title": "Fix", "commit_sha": "1234567890ab", "verdict": "PRESERVED"}
        ],
    }
    res = await export_mission_as_github_pr(
        "m-pr-ok",
        meta,
        vault_loader=lambda _r, _mid: {"github_token": "vaulted-gh-pat-xyz"},
        http_client=fake_client,
    )
    assert res["exported"] is True
    assert res["pr_number"] == 88
    assert res["pr_url"] == "https://github.com/org/repo/pull/88"
    assert "vaulted-gh-pat-xyz" not in str(meta)


@pytest.mark.asyncio
async def test_phase7_build_and_delivery_wiring_with_zip_export(tmp_path):
    from datetime import UTC, datetime

    from orchestrator.mission_flow_v2 import phases_build, phases_delivery
    from orchestrator.models import DataClassification, MissionRecord

    ws = _make_workspace(tmp_path)
    meta = {
        "workspace": {"workspace_id": ws.workspace_id, "workspace_dir": str(ws.workspace_dir)},
        "workspace_id": ws.workspace_id,
        "workspace_root": str(tmp_path),
        "mission_type": "BROWNFIELD_ENHANCE",
        "mission_contract": {
            "title": "Sliced Enhancement",
            "objective": "Add health endpoint safely.",
            "target_language": "python",
        },
        "mission_charter": {
            "slices": [{"id": "s1", "title": "Health route", "files": ["app.py"]}],
        },
        "runtime_qc_report": {"preservation_gate": {"verdict": "PRESERVED", "regressions": []}},
    }
    mission = MissionRecord(
        mission_id="m-wire-7",
        prompt="Add health endpoint",
        requested_target_language="python",
        data_classification=DataClassification.tier_1_internal,
        state=MissionState.verified,
        metadata=meta,
        created_at=datetime.now(UTC),
    )

    from orchestrator.sliced_execution import generate_migration_notes

    notes = generate_migration_notes(mission.mission_id, meta)
    assert "# Migration Notes" in notes

    # Confirm invalid repo handling and HTTP error handling never leak tokens
    bad_repo_res = await export_mission_as_github_pr(
        mission.mission_id,
        {"github_pr_export": {"enabled": True, "repo": "invalid-repo"}},
    )
    assert bad_repo_res["status"] == "error"

    class _ErrClient:
        async def post(self, url, json, headers):
            return SimpleNamespace(status_code=422, json=lambda: {"message": "Validation Failed"})

    err_res = await export_mission_as_github_pr(
        mission.mission_id,
        {"github_pr_export": {"enabled": True, "repo": "org/repo"}},
        vault_loader=lambda _r, _m: {"github_token": "secret-tok"},
        http_client=_ErrClient(),
    )
    assert err_res["status"] == "error"
    assert err_res["http_status"] == 422
    assert "secret-tok" not in str(err_res)
    assert phases_build is not None
    assert phases_delivery is not None


def test_workspace_bind_sync_and_bundle_excerpt(tmp_path):
    from orchestrator.workspace import (
        MissionWorkspace,
        bind_mission_workspace,
        sync_generated_output_to_workspace,
        workspace_from_mission_metadata,
    )

    settings = SimpleNamespace(workspace_root=str(tmp_path))

    # 1. Create from files + build_source_bundle_excerpt with selected_paths & truncation
    ws = MissionWorkspace.create_from_files(
        {
            "a.py": "def alpha():\n    return '" + ("a" * 80) + "'\n",
            "b.py": "def beta():\n    return '" + ("b" * 80) + "'\n",
            "bin.dat": b"nul\x00byte",
        },
        workspace_id="ws-files-7",
        settings=settings,
    )
    excerpt_selected = ws.build_source_bundle_excerpt(selected_paths=["a.py"])
    assert "## FILE a.py" in excerpt_selected
    assert "## FILE b.py" not in excerpt_selected
    excerpt_trunc = ws.build_source_bundle_excerpt(max_chars=120)
    assert "...[truncated]" in excerpt_trunc

    # 2. workspace_from_mission_metadata via repo_import & missing-workspace fallback
    assert workspace_from_mission_metadata(None, settings=settings) is None
    assert (
        workspace_from_mission_metadata(
            {"repo_import": {"workspace_id": "ws-files-7"}}, settings=settings
        ).workspace_id
        == "ws-files-7"
    )
    assert (
        workspace_from_mission_metadata(
            {"workspace": {"workspace_id": "nonexistent-ws"}}, settings=settings
        )
        is None
    )

    # 3. bind_mission_workspace from ## FILE bundle in source_code + existing workspace_id
    meta_bundle: dict[str, object] = {
        "project_name": "Demo",
        "source_code": "## FILE src/mod.py\ndef fn():\n    return 1\n\n## FILE ../bad.py\nx=1\n",
    }
    bound = bind_mission_workspace("mission-bind-7", meta_bundle, settings=settings)
    assert bound is not None
    assert bound.read_file("src/mod.py").strip().startswith("def fn")
    # Re-opening existing default ws-<mission_id>
    meta_reopen: dict[str, object] = {}
    reopened = bind_mission_workspace("mission-bind-7", meta_reopen, settings=settings)
    assert reopened is not None and reopened.workspace_id == bound.workspace_id

    # 4. sync_generated_output_to_workspace across files[], generated_code ## FILE, and single file
    sync_meta: dict[str, object] = {"project_name": "SyncApp"}
    synced1 = sync_generated_output_to_workspace(
        "mission-sync-files",
        sync_meta,
        {"files": [{"path": "pkg/app.py", "content": "print(1)\n"}, {"path": "../esc.py", "content": "x"}]},
        settings=settings,
    )
    assert synced1 is not None and synced1.read_file("pkg/app.py") == "print(1)\n"

    synced2 = sync_generated_output_to_workspace(
        "mission-sync-files",
        sync_meta,
        {"generated_code": "## FILE pkg/next.py\nprint(2)\n"},
        commit_message="slice next",
        settings=settings,
    )
    assert synced2 is not None and synced2.read_file("pkg/next.py") == "print(2)\n"

    synced3 = sync_generated_output_to_workspace(
        "mission-sync-files",
        sync_meta,
        {"filename": "main.py", "code": "print(3)\n"},
        settings=settings,
    )
    assert synced3 is not None and synced3.read_file("main.py") == "print(3)\n"
    assert sync_generated_output_to_workspace("m", {}, None, settings=settings) is None


@pytest.mark.asyncio
async def test_sliced_execution_awaits_async_preservation_gate_and_handles_list_files(
    tmp_path, monkeypatch
):
    import orchestrator.sliced_execution as sliced_exec

    ws = _make_workspace(tmp_path)
    called: list[str] = []

    async def _fake_gate(_ws, **_kwargs):
        called.append("awaited")
        return {"verdict": "PRESERVED"}

    monkeypatch.setattr(sliced_exec, "evaluate_preservation_gate", _fake_gate)

    metadata: dict[str, object] = {
        "slices": [{"id": "s1", "title": "List files", "files": ["app.py"]}],
        "baseline": {"suite": "pytest", "passed": 1, "failed": 0},
    }
    res = await execute_mission_slices(
        mission_id="m-async-preserv",
        metadata=metadata,
        ws=ws,
        codegen_fn=lambda **_kw: {
            "files": [{"path": "app.py", "content": "def greet():\n    return 'list-ok'\n"}],
        },
    )
    assert called == ["awaited"]
    assert res["regressed"] is False
    assert ws.read_file("app.py").strip().endswith("'list-ok'")




@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("target_lang", "expected_file"),
    [("go", "main.go"), ("java", "Main.java"), ("rust", "main.rs"), ("python", "main.py")],
)
async def test_sliced_codegen_unbundled_output_uses_language_entry_file_and_grounding(
    monkeypatch, target_lang, expected_file
):
    """Un-bundled slice output is named for the target language, and slice
    prompts get the same Knowledge Lake + AIM grounding as single-shot codegen."""
    import orchestrator.mission_flow_v2 as mf2
    import orchestrator.sliced_execution as sliced_mod
    import orchestrator.workspace as workspace_mod
    from orchestrator.mission_flow_v2 import phases_build

    seen_contexts: list[dict] = []

    async def _fake_codegen(*, mission_context, **_kwargs):
        seen_contexts.append(mission_context)
        return {"code": "plain source without a FILE header", "source": "llm"}

    captured: dict = {}

    async def _fake_execute_mission_slices(*, codegen_fn, metadata, **_kwargs):
        captured["result"] = await codegen_fn(
            slice_spec={"id": "s1", "title": "No files listed"},
            context_pack={"files": []},
            ws=None,
            metadata=metadata,
        )
        return {"slices_completed": ["s1"]}

    lake_calls: list[dict] = []

    def _fake_language_context(**kwargs):
        lake_calls.append(kwargs)
        return "KB docs"

    monkeypatch.setattr(mf2, "generate_code_from_contract", _fake_codegen)
    monkeypatch.setattr(sliced_mod, "execute_mission_slices", _fake_execute_mission_slices)
    monkeypatch.setattr(workspace_mod, "workspace_from_mission_metadata", lambda *_a, **_k: None)
    monkeypatch.setattr(phases_build.knowledge_lake, "get_language_context", _fake_language_context)

    metadata = {
        "application_intelligence_map": {"primary_language": target_lang, "secret_field": "x"},
    }
    from datetime import UTC, datetime

    from orchestrator.models import DataClassification, MissionRecord

    mission = MissionRecord(
        mission_id="m-slice-lang",
        prompt="Slice it",
        requested_target_language=target_lang,
        data_classification=DataClassification.tier_1_internal,
        state=MissionState.specialist_assigned,
        metadata={},
        created_at=datetime.now(UTC),
    )
    generated, paused = await phases_build._execute_sliced_specialist_codegen(
        mission=mission,
        mission_id="m-slice-lang",
        metadata=metadata,
        settings=SimpleNamespace(),
        mission_contract={"title": "t"},
        normalized_plan={},
        specialist_agent_id="AGENT-X",
        target_lang=target_lang,
        port_source_logicnodes=None,
    )

    assert paused is False
    assert generated is not None
    assert list(captured["result"]["files"]) == [expected_file]
    assert len(lake_calls) == 1  # looked up once, not per slice
    ctx = seen_contexts[0]
    assert ctx["knowledge_context"] == "KB docs"
    assert ctx["application_intelligence_map"] == {"primary_language": target_lang}
    assert "imported_source_code" not in ctx  # slices scope source via context_pack


def test_default_entry_filename_covers_every_routed_language():
    from orchestrator.mission_flow import POD_MANAGER_BY_LANGUAGE
    from orchestrator.mission_flow_v2 import phases_build

    routed = {lang for lang in POD_MANAGER_BY_LANGUAGE if lang.isalpha()}
    missing = sorted(
        lang for lang in routed if phases_build._default_entry_filename(lang) == "main.txt"
    )
    assert missing == []
