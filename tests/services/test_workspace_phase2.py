"""Phase 2 tests: Git-backed mission workspace, security containment, and HTTP routes."""

from __future__ import annotations

import importlib
import io
import os
import stat
import subprocess
import sys
import zipfile
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "shared_runtime"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))
sys.path.insert(0, str(ROOT / "services" / "api-gateway"))

api_gateway_main = importlib.import_module("api_gateway.main")
orchestrator_auth = importlib.import_module("orchestrator.auth")
orchestrator_main = importlib.import_module("orchestrator.main")
orchestrator_missions = importlib.import_module("orchestrator.routes.missions")
orchestrator_models = importlib.import_module("orchestrator.models")
workspace_mod = importlib.import_module("orchestrator.workspace")

MissionRecord = orchestrator_models.MissionRecord
MissionState = orchestrator_models.MissionState
MissionWorkspace = workspace_mod.MissionWorkspace
WorkspaceSecurityError = workspace_mod.WorkspaceSecurityError


def _zip_from_dir(src_dir: Path) -> bytes:
    skip_dirs = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".venv", "venv"}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in sorted(src_dir.rglob("*")):
            if not file_path.is_file():
                continue
            rel_parts = file_path.relative_to(src_dir).parts
            if any(part in skip_dirs for part in rel_parts):
                continue
            zf.write(file_path, arcname=f"{src_dir.name}/{'/'.join(rel_parts)}")
    return buf.getvalue()


def _create_ten_file_repo(base_dir: Path) -> Path:
    repo = base_dir / "sample-10file"
    repo.mkdir(parents=True, exist_ok=True)
    for idx in range(1, 11):
        (repo / f"file_{idx:02d}.py").write_bytes(
            f"VALUE_{idx} = {idx}\n".encode("utf-8")
        )
    return repo


def test_benchmark_apps_import_local_and_zip_clean_baseline(tmp_path: Path) -> None:
    """All 7 MIT brownfield benchmark apps import cleanly via local and ZIP paths."""
    bench_root = ROOT / "tests" / "benchmark" / "brownfield"
    bench_dirs = sorted(p for p in bench_root.iterdir() if p.is_dir())
    assert len(bench_dirs) == 7

    for idx, app_dir in enumerate(bench_dirs):
        ws_local = MissionWorkspace.create_from_local(
            app_dir,
            workspace_id=f"bench-local-{idx}",
            root=tmp_path / "local",
        )
        status_local = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=ws_local.workspace_dir,
            check=True,
            capture_output=True,
            text=True,
        )
        assert status_local.stdout.strip() == ""
        head_local = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ws_local.workspace_dir,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        assert head_local == ws_local.base_commit

        ws_zip = MissionWorkspace.create_from_zip(
            _zip_from_dir(app_dir),
            workspace_id=f"bench-zip-{idx}",
            root=tmp_path / "zip",
        )
        status_zip = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=ws_zip.workspace_dir,
            check=True,
            capture_output=True,
            text=True,
        )
        assert status_zip.stdout.strip() == ""
        head_zip = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ws_zip.workspace_dir,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        assert head_zip == ws_zip.base_commit
        assert len(ws_local.list_files()) >= 1
        assert len(ws_zip.list_files()) == len(ws_local.list_files())


def test_ten_file_workspace_one_edit_full_zip_and_clean_git_apply(tmp_path: Path) -> None:
    """Editing 1 file preserves all 10 files in ZIP export and produces a valid git patch."""
    repo_src = _create_ten_file_repo(tmp_path / "src")
    ws = MissionWorkspace.create_from_local(
        repo_src,
        workspace_id="ws-10file",
        root=tmp_path / "ws_root",
    )
    branch_name = ws.branch("mission-10file")
    assert branch_name == "thefactory/mission-mission-10file"

    ws.write_files(
        {"file_03.py": "VALUE_3 = 999\n"},
        message="update file_03",
    )
    assert ws.modified_files("baseline") == ["file_03.py"]

    zip_bytes = ws.export_zip_bytes()
    with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
        names = set(zf.namelist())
        for idx in range(1, 11):
            assert f"file_{idx:02d}.py" in names
        assert zf.read("file_03.py").decode("utf-8") == "VALUE_3 = 999\n"
        assert zf.read("file_07.py").decode("utf-8") == "VALUE_7 = 7\n"

    patch_text = ws.diff("baseline")
    assert "diff --git a/file_03.py b/file_03.py" in patch_text
    assert "+VALUE_3 = 999" in patch_text

    # Apply the exported unified patch onto a fresh clone checked out at baseline.
    verify_dir = tmp_path / "apply_verify"
    subprocess.run(
        [
            "git",
            "-c",
            "core.hooksPath=/dev/null",
            "-c",
            "core.autocrlf=false",
            "clone",
            str(ws.workspace_dir),
            str(verify_dir),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        [
            "git",
            "-c",
            "core.hooksPath=/dev/null",
            "-c",
            "core.autocrlf=false",
            "checkout",
            ws.base_commit,
        ],
        cwd=verify_dir,
        check=True,
        capture_output=True,
        text=True,
    )
    patch_file = tmp_path / "mission.patch"
    patch_file.write_bytes(patch_text.encode("utf-8"))
    apply_proc = subprocess.run(
        ["git", "-c", "core.autocrlf=false", "apply", str(patch_file)],
        cwd=verify_dir,
        capture_output=True,
        text=True,
    )
    assert apply_proc.returncode == 0, apply_proc.stderr
    assert (verify_dir / "file_03.py").read_text(encoding="utf-8") == "VALUE_3 = 999\n"
    assert (verify_dir / "file_07.py").read_text(encoding="utf-8") == "VALUE_7 = 7\n"


def test_workspace_security_containment_and_hooks_disabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reject traversal, symlinks in ZIP/worktree, and never execute .git/hooks."""
    # 1. ZIP entry path traversal
    buf_traversal = io.BytesIO()
    with zipfile.ZipFile(buf_traversal, "w") as zf:
        zf.writestr("../../etc/passwd", "root:x:0:0::/:/bin/sh\n")
    with pytest.raises(WorkspaceSecurityError):
        MissionWorkspace.create_from_zip(
            buf_traversal.getvalue(),
            workspace_id="ws-bad-zip-trav",
            root=tmp_path / "sec",
        )

    # 2. ZIP symlink entry (external_attr 0o120777 << 16)
    buf_symlink = io.BytesIO()
    with zipfile.ZipFile(buf_symlink, "w") as zf:
        info = zipfile.ZipInfo("link.txt")
        info.create_system = 3
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        zf.writestr(info, "/etc/passwd")
    with pytest.raises(WorkspaceSecurityError):
        MissionWorkspace.create_from_zip(
            buf_symlink.getvalue(),
            workspace_id="ws-bad-zip-sym",
            root=tmp_path / "sec",
        )

    # 3. Escaping symlink in directory / worktree containment
    outside_target = tmp_path / "outside.txt"
    outside_target.write_text("secret", encoding="utf-8")
    sym_dir = tmp_path / "sym_repo"
    sym_dir.mkdir(parents=True, exist_ok=True)
    (sym_dir / "ok.py").write_text("x = 1\n", encoding="utf-8")
    sym_path = sym_dir / "escape_link"
    created_os_symlink = False
    try:
        os.symlink(outside_target, sym_path)
        created_os_symlink = True
    except OSError:
        # Windows without Developer Mode / SeCreateSymbolicLinkPrivilege: test directly via mock
        sym_path.write_text("placeholder", encoding="utf-8")
        orig_is_symlink = Path.is_symlink
        orig_readlink = os.readlink
        monkeypatch.setattr(
            Path,
            "is_symlink",
            lambda self: True if self.name == "escape_link" else orig_is_symlink(self),
        )
        monkeypatch.setattr(
            os,
            "readlink",
            lambda p: str(outside_target) if Path(p).name == "escape_link" else orig_readlink(p),
        )
    with pytest.raises(WorkspaceSecurityError):
        MissionWorkspace._verify_no_escaping_symlinks(sym_dir)
    if created_os_symlink:
        sym_path.unlink()
    monkeypatch.undo()

    # 4. read_file / write_files traversal
    safe_src = _create_ten_file_repo(tmp_path / "safe_src")
    ws = MissionWorkspace.create_from_local(
        safe_src,
        workspace_id="ws-safe-check",
        root=tmp_path / "sec",
    )
    with pytest.raises(WorkspaceSecurityError):
        ws.read_file("../../etc/passwd")
    with pytest.raises(WorkspaceSecurityError):
        ws.write_files({"../escape.py": "print(1)\n"})

    # 5. Git hooks disabled during create_from_git, branch, and write_files
    git_origin = tmp_path / "git_origin"
    git_origin.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-b", "main"], cwd=git_origin, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.name", "Tester"], cwd=git_origin, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.email", "tester@example.com"],
        cwd=git_origin,
        check=True,
        capture_output=True,
    )
    (git_origin / "app.py").write_text("print('ok')\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=git_origin, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init"], cwd=git_origin, check=True, capture_output=True
    )

    marker = tmp_path / "hook_executed.marker"
    origin_hook = git_origin / ".git" / "hooks" / "post-checkout"
    origin_hook.parent.mkdir(parents=True, exist_ok=True)
    origin_hook.write_text(f"#!/bin/sh\necho ran > {marker.as_posix()}\n", encoding="utf-8")
    origin_hook.chmod(0o755)

    cloned_ws = MissionWorkspace.create_from_git(
        git_origin.as_uri(),
        workspace_id="ws-git-hook-test",
        root=tmp_path / "sec",
    )
    ws_hook = cloned_ws.workspace_dir / ".git" / "hooks" / "post-checkout"
    ws_hook.parent.mkdir(parents=True, exist_ok=True)
    ws_hook.write_text(f"#!/bin/sh\necho ran > {marker.as_posix()}\n", encoding="utf-8")
    ws_hook.chmod(0o755)

    cloned_ws.branch("mission-hooks")
    cloned_ws.write_files({"app.py": "print('updated')\n"}, message="update")
    assert marker.exists() is False


def test_orchestrator_and_gateway_workspace_routes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Orchestrator /internal/workspaces* and mission workspace/export routes work end to end."""
    app = orchestrator_main.app
    app.dependency_overrides.clear()
    ws_root = tmp_path / "orchestrator_ws"
    monkeypatch.setattr(app.state, "settings", replace(app.state.settings, workspace_root=ws_root))

    src_repo = _create_ten_file_repo(tmp_path / "http_repo")

    auth_ctx = orchestrator_auth.AuthContext(
        api_key="test-internal-key",
        roles={"internal", "read"},
    )
    app.dependency_overrides[orchestrator_main.INTERNAL_AUTH] = lambda: auth_ctx

    mission_store: dict[str, MissionRecord] = {}

    async def _db_ready(_app: object) -> tuple[bool, bool]:
        return True, True

    async def _fetch_existing(_app: object, mission_id: str) -> MissionRecord:
        return mission_store[mission_id]

    monkeypatch.setattr(orchestrator_main, "_ensure_db_ready", _db_ready)
    monkeypatch.setattr(orchestrator_main, "_fetch_existing_mission", _fetch_existing)
    monkeypatch.setattr(orchestrator_missions.storage, "list_build_artifacts", lambda *_args: [])

    client = TestClient(app)
    try:
        # 1. Create workspace from local path
        imp_res = client.post(
            "/internal/workspaces",
            json={"local_path": str(src_repo), "display_name": "ten-file-app"},
        )
        assert imp_res.status_code == 200
        imp_body = imp_res.json()
        ws_id = imp_body["repository"]["workspace_id"]
        base_commit = imp_body["repository"]["base_commit"]
        assert ws_id
        assert len(imp_body["files"]) == 10

        # 2. Review workspace
        rev_res = client.post(
            f"/internal/workspaces/{ws_id}/review",
            json={
                "mission_type": "update",
                "description": "Update constant in file_03",
                "selected_files": [{"path": "file_03.py", "overlay_action": "include"}],
            },
        )
        assert rev_res.status_code == 200
        rev_body = rev_res.json()
        assert rev_body["repository"]["workspace_id"] == ws_id
        assert "VALUE_3 = 3" in rev_body["source_code"]

        # 3. Apply a mission edit on the workspace branch
        ws = MissionWorkspace.open(ws_id, root=ws_root)
        ws.branch("mission-http-1")
        ws.write_files({"file_03.py": "VALUE_3 = 999\n"}, message="mission edit")

        mission_store["mission-http-1"] = MissionRecord(
            mission_id="mission-http-1",
            prompt="Update file_03",
            requested_target_language="python",
            metadata={
                "workspace": {"workspace_id": ws_id, "base_commit": base_commit},
                "generated_output": {
                    "filename": "file_03.py",
                    "language": "python",
                    "code": "## FILE file_03.py\nVALUE_3 = 999\n",
                },
            },
            state=MissionState.complete,
            created_at="2026-11-13T00:00:00+00:00",
        )

        # 4. Workspace tree/file/diff endpoints
        tree_res = client.get("/internal/missions/mission-http-1/workspace/tree")
        assert tree_res.status_code == 200
        tree_body = tree_res.json()
        assert len(tree_body["files"]) == 10
        assert tree_body["modified_files"] == ["file_03.py"]

        file_res = client.get("/internal/missions/mission-http-1/workspace/file?path=file_03.py")
        assert file_res.status_code == 200
        file_body = file_res.json()
        assert file_body["content"] == "VALUE_3 = 999\n"
        assert file_body["baseline_content"] == "VALUE_3 = 3\n"
        assert file_body["modified"] is True

        bad_file_res = client.get(
            "/internal/missions/mission-http-1/workspace/file?path=../../secret.txt"
        )
        assert bad_file_res.status_code == 400

        diff_res = client.get("/internal/missions/mission-http-1/workspace/diff")
        assert diff_res.status_code == 200
        assert "+VALUE_3 = 999" in diff_res.json()["diff"]

        # 5. Full-tree ZIP artifact download and git unified patch export
        zip_res = client.get("/missions/mission-http-1/artifact?format=zip")
        assert zip_res.status_code == 200
        with zipfile.ZipFile(io.BytesIO(zip_res.content), "r") as zf:
            assert len(zf.namelist()) == 10
            assert zf.read("file_03.py").decode("utf-8") == "VALUE_3 = 999\n"

        patch_res = client.get("/missions/mission-http-1/export/patch")
        assert patch_res.status_code == 200
        assert "diff --git a/file_03.py b/file_03.py" in patch_res.text
        assert "+VALUE_3 = 999" in patch_res.text
    finally:
        app.dependency_overrides.clear()


def test_api_gateway_workspace_proxy_routes_and_path_traversal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """API Gateway exposes /v1/missions/{id}/workspace/* and rejects path traversal early."""
    proxied_calls: list[tuple[str, dict[str, Any] | None]] = []

    monkeypatch.setattr(api_gateway_main, "_require_reader_access", lambda **_kw: "reader")

    async def _fake_proxy(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        proxied_calls.append((path, params))
        return {"ok": True, "path": path, "params": params}

    monkeypatch.setattr(api_gateway_main, "_proxy_get_internal", _fake_proxy)
    client = TestClient(api_gateway_main.app)

    r_tree = client.get("/v1/missions/m1/workspace/tree")
    assert r_tree.status_code == 200
    assert r_tree.json()["path"] == "/missions/m1/workspace/tree"

    r_file = client.get("/v1/missions/m1/workspace/file?path=src/app.py")
    assert r_file.status_code == 200
    assert r_file.json()["params"] == {"path": "src/app.py"}

    r_diff = client.get("/v1/missions/m1/workspace/diff")
    assert r_diff.status_code == 200
    assert r_diff.json()["path"] == "/missions/m1/workspace/diff"

    r_bad = client.get("/v1/missions/m1/workspace/file?path=../../etc/passwd")
    assert r_bad.status_code == 400
    assert len(proxied_calls) == 3
