"""Git-backed per-mission workspace management for brownfield and greenfield work.

Replaces single-string ``metadata["source_code"]`` storage with an isolated Git
repository per workspace under ``WORKSPACE_ROOT``:
- Imports from ZIP archives, local folders, or Git URLs onto a ``baseline`` commit.
- Branches ``thefactory/mission-<mission_id>`` for each mission.
- Commits generated/repaired files incrementally without deleting untouched repo files.
- Produces real ``git diff baseline..HEAD`` patches and full-tree ``git archive`` ZIPs.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shutil
import stat
import subprocess
import uuid
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

MAX_WORKSPACE_ENTRIES = 10_000
MAX_WORKSPACE_UNCOMPRESSED_BYTES = 250_000_000
WORKSPACE_META_FILENAME = ".thefactory_workspace.json"
WORKSPACE_INTERNAL_DIR = ".thefactory"
DEFAULT_SUBDIRECTORY = "/"

_SKIP_DIR_NAMES = frozenset({".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".venv", "venv"})
_DRIVE_PREFIX_RE = re.compile(r"^[A-Za-z]:")
_WORKSPACE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_SAFE_GIT_SCHEMES = frozenset({"http", "https", "git", "ssh", "file"})

_EXT_LANGUAGE_MAP: dict[str, str] = {
    ".py": "Python",
    ".pyw": "Python",
    ".js": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".mts": "TypeScript",
    ".go": "Go",
    ".rs": "Rust",
    ".c": "C",
    ".h": "C",
    ".cpp": "C++",
    ".cc": "C++",
    ".cxx": "C++",
    ".hpp": "C++",
    ".java": "Java",
    ".cs": "C#",
    ".csproj": "XML",
    ".php": "PHP",
    ".rb": "Ruby",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".scala": "Scala",
    ".hs": "Haskell",
    ".ml": "OCaml",
    ".mli": "OCaml",
    ".r": "R",
    ".jl": "Julia",
    ".zig": "Zig",
    ".json": "JSON",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".toml": "TOML",
    ".xml": "XML",
    ".html": "HTML",
    ".css": "CSS",
    ".md": "Markdown",
    ".sh": "Shell",
    ".sql": "SQL",
}


class WorkspaceError(ValueError):
    """Base error for workspace creation, lookup, or file operations."""


class WorkspaceSecurityError(WorkspaceError):
    """Raised when a path, archive entry, symlink, or Git remote violates safety bounds."""


def resolve_workspace_root(settings: Any = None, *, create: bool = True) -> Path:
    """Resolve the base directory storing git-backed workspaces."""
    raw_root = getattr(settings, "workspace_root", None) if settings is not None else None
    if isinstance(raw_root, (str, Path)) and str(raw_root).strip():
        root = Path(raw_root)
    else:
        env_root = os.getenv("WORKSPACE_ROOT", "").strip()
        root = Path(env_root) if env_root else Path("workspaces")
    if create:
        root.mkdir(parents=True, exist_ok=True)
    return root


def validate_workspace_id(workspace_id: str) -> str:
    """Validate and return a safe workspace identifier (single path segment)."""
    cleaned = str(workspace_id or "").strip()
    if not _WORKSPACE_ID_RE.match(cleaned) or ".." in cleaned:
        raise WorkspaceSecurityError(f"Invalid workspace_id: {workspace_id!r}")
    return cleaned


def validate_workspace_rel_path(rel_path: str) -> str:
    """Validate and normalize a repository-relative POSIX path, rejecting traversals."""
    raw = str(rel_path or "").strip()
    if not raw or "\x00" in raw:
        raise WorkspaceSecurityError("Workspace file path cannot be empty or contain NUL bytes.")
    if "\\" in raw:
        raise WorkspaceSecurityError(f"Backslashes are not allowed in workspace path: {raw!r}")
    if _DRIVE_PREFIX_RE.match(raw):
        raise WorkspaceSecurityError(f"Windows drive prefix is not allowed: {raw!r}")
    if raw.startswith("/"):
        raise WorkspaceSecurityError(f"Absolute paths are not allowed in workspace: {raw!r}")
    parts = raw.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise WorkspaceSecurityError(f"Unsafe path segment in workspace path: {raw!r}")
    cleaned = "/".join(parts)
    if cleaned == ".git" or cleaned.startswith(".git/") or cleaned == WORKSPACE_META_FILENAME:
        raise WorkspaceSecurityError(f"Reserved metadata path is forbidden: {raw!r}")
    return cleaned


def _ensure_contained_path(workspace_dir: Path, rel_posix: str) -> Path:
    """Resolve ``workspace_dir / rel_posix`` and verify strict containment without symlink escape."""
    resolved_root = workspace_dir.resolve()
    candidate = workspace_dir.joinpath(*rel_posix.split("/"))
    # Reject symlinks along any existing prefix inside the workspace before reading/writing.
    probe = workspace_dir
    for segment in rel_posix.split("/"):
        probe = probe / segment
        if probe.is_symlink():
            raise WorkspaceSecurityError(f"Symlink path is forbidden in workspace: {rel_posix!r}")
    resolved_target = candidate.resolve()
    if resolved_target == resolved_root or resolved_root not in resolved_target.parents:
        raise WorkspaceSecurityError(f"Resolved path escapes workspace root: {rel_posix!r}")
    return candidate


def _detect_language(rel_path: str) -> str:
    name = Path(rel_path).name.lower()
    if name in {"makefile", "gnumakefile"}:
        return "Makefile"
    if name == "dockerfile":
        return "Dockerfile"
    return _EXT_LANGUAGE_MAP.get(Path(rel_path).suffix.lower(), "Text")


def _mission_branch_name(mission_id: str) -> str:
    safe_mission = re.sub(r"[^A-Za-z0-9._-]+", "-", str(mission_id or "").strip()).strip("-")
    if not safe_mission:
        raise WorkspaceError("mission_id must not be empty")
    return f"thefactory/mission-{safe_mission}"


def _git_env() -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_ASKPASS": "/bin/echo",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "theFactory",
            "GIT_AUTHOR_EMAIL": "factory@local",
            "GIT_COMMITTER_NAME": "theFactory",
            "GIT_COMMITTER_EMAIL": "factory@local",
        }
    )
    return env


def _run_git(
    cwd: Path,
    args: list[str],
    *,
    check: bool = True,
    text: bool = True,
) -> subprocess.CompletedProcess[Any]:
    cmd = [
        "git",
        "-c",
        "core.hooksPath=/dev/null",
        "-c",
        "core.autocrlf=false",
        "-c",
        "protocol.file.allow=user",
        "-c",
        "commit.gpgsign=false",
        *args,
    ]
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        env=_git_env(),
        check=check,
        capture_output=True,
        text=text,
    )


def _validate_zip_entry_name(raw_name: str) -> str:
    """Validate an entry name inside a ZIP archive before prefix stripping."""
    if not raw_name or "\x00" in raw_name:
        raise WorkspaceSecurityError("ZIP entry name is empty or contains NUL bytes.")
    if "\\" in raw_name or _DRIVE_PREFIX_RE.match(raw_name) or raw_name.startswith("/"):
        raise WorkspaceSecurityError(f"Unsafe ZIP entry path: {raw_name!r}")
    stripped = raw_name.rstrip("/")
    if not stripped:
        raise WorkspaceSecurityError(f"Empty ZIP directory entry: {raw_name!r}")
    parts = stripped.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise WorkspaceSecurityError(f"Traversal segment in ZIP entry: {raw_name!r}")
    if parts[0] == ".git" or WORKSPACE_META_FILENAME in parts:
        raise WorkspaceSecurityError(f"Reserved entry path forbidden in ZIP: {raw_name!r}")
    return "/".join(parts)


def _detect_common_root_prefix(file_paths: list[str]) -> str:
    """Strip single shared top-level folder prefix (matching Mission Control archive.ts)."""
    if not file_paths:
        return ""
    first_segments = {path.split("/", 1)[0] for path in file_paths if "/" in path}
    if len(first_segments) == 1 and all("/" in path for path in file_paths):
        return f"{next(iter(first_segments))}/"
    return ""


def _validate_git_source(url_or_path: str) -> tuple[str, bool]:
    """Validate a git source (local directory or remote URL). Returns (source, is_local_dir)."""
    raw = str(url_or_path or "").strip()
    if not raw or "\x00" in raw:
        raise WorkspaceSecurityError("Git source URL or local path cannot be empty.")
    if raw.startswith("-"):
        raise WorkspaceSecurityError(f"Unsafe git source starting with '-': {raw!r}")
    lower = raw.lower()
    if lower.startswith("ext::"):
        raise WorkspaceSecurityError("Git ext:: transport is forbidden.")

    local_candidate = Path(raw)
    if local_candidate.exists():
        if not local_candidate.is_dir():
            raise WorkspaceError(f"Local workspace source is not a directory: {raw!r}")
        return str(local_candidate.resolve()), True

    parsed = urlparse(raw)
    if parsed.scheme:
        if parsed.scheme.lower() not in _SAFE_GIT_SCHEMES:
            raise WorkspaceSecurityError(f"Unsupported git scheme: {parsed.scheme!r}")
        if parsed.scheme.lower() == "file":
            file_path = Path(url_to_path_compat(parsed.path))
            if not file_path.is_dir():
                raise WorkspaceError(f"Local file:// repository not found: {raw!r}")
            return str(file_path.resolve()), True
        return raw, False

    # scp-style SSH remote e.g. git@github.com:org/repo.git
    if ":" in raw and "@" in raw.split(":", 1)[0] and not _DRIVE_PREFIX_RE.match(raw):
        return raw, False

    raise WorkspaceError(f"Workspace source path or URL does not exist: {raw!r}")


def url_to_path_compat(raw_path: str) -> str:
    """Convert file:// URI path on Windows (`/C:/foo`) or POSIX (`/tmp/foo`) to OS path."""
    if os.name == "nt" and len(raw_path) >= 3 and raw_path[0] == "/" and raw_path[2] == ":":
        return raw_path[1:]
    return raw_path


class MissionWorkspace:
    """Per-workspace Git repository with baseline tracking and mission branching."""

    def __init__(
        self,
        *,
        workspace_id: str,
        root: Path,
        workspace_dir: Path,
        base_commit: str,
        branch_name: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.workspace_id = validate_workspace_id(workspace_id)
        self.root = root
        self.workspace_dir = workspace_dir
        self.base_commit = base_commit
        self.branch_name = branch_name
        self.metadata = metadata or {}

    @classmethod
    def create_from_zip(
        cls,
        archive: bytes | Path,
        *,
        workspace_id: str | None = None,
        root: Path | None = None,
        display_name: str | None = None,
        source_ref: str = "main",
        subdirectory: str = DEFAULT_SUBDIRECTORY,
        settings: Any = None,
    ) -> MissionWorkspace:
        """Unpack a ZIP safely into a fresh workspace and commit a ``baseline`` branch."""
        ws_root = root if root is not None else resolve_workspace_root(settings)
        ws_root.mkdir(parents=True, exist_ok=True)
        ws_id = validate_workspace_id(workspace_id or f"ws-{uuid.uuid4().hex[:12]}")
        ws_dir = ws_root / ws_id
        if ws_dir.exists():
            shutil.rmtree(ws_dir)
        ws_dir.mkdir(parents=True, exist_ok=True)

        source_obj: Any = io.BytesIO(archive) if isinstance(archive, (bytes, bytearray)) else Path(archive)
        if not zipfile.is_zipfile(source_obj):
            raise WorkspaceError("Input is not a valid ZIP archive.")
        if isinstance(source_obj, io.BytesIO):
            source_obj.seek(0)

        total_entries = 0
        total_bytes = 0
        extracted_items: list[tuple[str, bytes]] = []

        with zipfile.ZipFile(source_obj, "r") as zf:
            infos = zf.infolist()
            if len(infos) > MAX_WORKSPACE_ENTRIES:
                raise WorkspaceSecurityError(
                    f"ZIP archive exceeds entry limit ({len(infos)} > {MAX_WORKSPACE_ENTRIES})."
                )
            for info in infos:
                total_entries += 1
                unix_mode = (info.external_attr >> 16) & 0o170000
                if unix_mode == stat.S_IFLNK:
                    raise WorkspaceSecurityError(
                        f"Symlink entry forbidden in ZIP archive: {info.filename!r}"
                    )
                if info.is_dir():
                    # Validate directory entry name against traversal too.
                    _validate_zip_entry_name(info.filename)
                    continue
                clean_name = _validate_zip_entry_name(info.filename)
                if info.file_size > MAX_WORKSPACE_UNCOMPRESSED_BYTES:
                    raise WorkspaceSecurityError(
                        f"ZIP entry exceeds uncompressed byte limit: {info.filename!r}"
                    )
                with zf.open(info, "r") as member:
                    data = member.read(MAX_WORKSPACE_UNCOMPRESSED_BYTES - total_bytes + 1)
                total_bytes += len(data)
                if total_bytes > MAX_WORKSPACE_UNCOMPRESSED_BYTES:
                    raise WorkspaceSecurityError(
                        "ZIP archive exceeds maximum uncompressed workspace limit."
                    )
                extracted_items.append((clean_name, data))

        prefix = _detect_common_root_prefix([name for name, _ in extracted_items])
        for raw_rel, data in extracted_items:
            stripped_rel = raw_rel[len(prefix) :] if prefix and raw_rel.startswith(prefix) else raw_rel
            if not stripped_rel:
                continue
            rel_posix = validate_workspace_rel_path(stripped_rel)
            target = _ensure_contained_path(ws_dir, rel_posix)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)

        meta = {
            "workspace_id": ws_id,
            "source_type": "zip",
            "display_name": display_name or ws_id,
            "source_ref": source_ref or "main",
            "selected_subdirectory": subdirectory or "/",
            "root_prefix": prefix,
            "created_at": datetime.now(UTC).isoformat(),
        }
        return cls._init_baseline_repo(ws_root=ws_root, ws_id=ws_id, ws_dir=ws_dir, meta=meta)

    @classmethod
    def create_from_local(
        cls,
        local_dir: str | Path,
        *,
        workspace_id: str | None = None,
        root: Path | None = None,
        display_name: str | None = None,
        source_ref: str = "main",
        subdirectory: str = DEFAULT_SUBDIRECTORY,
        settings: Any = None,
    ) -> MissionWorkspace:
        """Create a baseline git workspace from a local folder (git or plain directory)."""
        src = Path(local_dir).resolve()
        if not src.exists() or not src.is_dir():
            raise WorkspaceError(f"Local workspace directory does not exist: {local_dir!r}")
        return cls.create_from_git(
            str(src),
            ref=source_ref if (src / ".git").exists() and source_ref else None,
            workspace_id=workspace_id,
            root=root,
            display_name=display_name or src.name,
            subdirectory=subdirectory,
            settings=settings,
        )

    @classmethod
    def create_from_files(
        cls,
        files: dict[str, str | bytes],
        *,
        workspace_id: str | None = None,
        root: Path | None = None,
        display_name: str | None = None,
        source_ref: str = "baseline",
        subdirectory: str = DEFAULT_SUBDIRECTORY,
        settings: Any = None,
    ) -> MissionWorkspace:
        """Create a baseline git workspace directly from an in-memory path->content mapping."""
        ws_root = root if root is not None else resolve_workspace_root(settings)
        ws_root.mkdir(parents=True, exist_ok=True)
        ws_id = validate_workspace_id(workspace_id or f"ws-{uuid.uuid4().hex[:12]}")
        ws_dir = ws_root / ws_id
        if ws_dir.exists():
            shutil.rmtree(ws_dir)
        ws_dir.mkdir(parents=True, exist_ok=True)

        for raw_rel, content in files.items():
            rel_posix = validate_workspace_rel_path(raw_rel)
            target = _ensure_contained_path(ws_dir, rel_posix)
            target.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(content, (bytes, bytearray)):
                target.write_bytes(bytes(content))
            else:
                target.write_bytes(str(content).encode("utf-8"))

        meta = {
            "workspace_id": ws_id,
            "source_type": "bundle",
            "display_name": display_name or ws_id,
            "source_ref": source_ref,
            "selected_subdirectory": subdirectory or "/",
            "root_prefix": "",
            "created_at": datetime.now(UTC).isoformat(),
        }
        return cls._init_baseline_repo(ws_root=ws_root, ws_id=ws_id, ws_dir=ws_dir, meta=meta)

    @classmethod
    def create_from_git(
        cls,
        url_or_path: str,
        *,
        ref: str | None = None,
        workspace_id: str | None = None,
        root: Path | None = None,
        display_name: str | None = None,
        subdirectory: str = DEFAULT_SUBDIRECTORY,
        settings: Any = None,
    ) -> MissionWorkspace:
        """Clone a Git repo (with hooks disabled) or snapshot a plain local dir onto ``baseline``."""
        source_str, is_local = _validate_git_source(url_or_path)
        if ref and str(ref).strip().startswith("-"):
            raise WorkspaceSecurityError(f"Unsafe git ref starting with '-': {ref!r}")

        ws_root = root if root is not None else resolve_workspace_root(settings)
        ws_root.mkdir(parents=True, exist_ok=True)
        ws_id = validate_workspace_id(workspace_id or f"ws-{uuid.uuid4().hex[:12]}")
        ws_dir = ws_root / ws_id
        if ws_dir.exists():
            shutil.rmtree(ws_dir)

        source_path = Path(source_str) if is_local else None
        if is_local and source_path is not None and not (source_path / ".git").exists():
            ws_dir.mkdir(parents=True, exist_ok=True)
            cls._copy_plain_directory(source_path, ws_dir)
            meta = {
                "workspace_id": ws_id,
                "source_type": "local",
                "display_name": display_name or source_path.name,
                "source_ref": ref or "local",
                "selected_subdirectory": subdirectory or "/",
                "root_prefix": "",
                "source_origin": str(source_path),
                "created_at": datetime.now(UTC).isoformat(),
            }
            return cls._init_baseline_repo(ws_root=ws_root, ws_id=ws_id, ws_dir=ws_dir, meta=meta)

        clone_args = ["clone", "--no-checkout"]
        if is_local:
            clone_args.append("--no-local")
        else:
            clone_args.extend(["--depth", "1"])
        clone_args.extend([source_str, str(ws_dir)])
        try:
            _run_git(ws_root, clone_args)
        except subprocess.CalledProcessError as exc:
            raise WorkspaceError(
                f"Failed to clone repository: {exc.stderr.strip() or exc.stdout.strip() or exc}"
            ) from exc

        # Ensure cloned hooks are never executed even if repository config had custom settings.
        _run_git(ws_dir, ["config", "core.hooksPath", "/dev/null"])

        if ref and str(ref).strip():
            target_ref = str(ref).strip()
            try:
                _run_git(ws_dir, ["checkout", target_ref])
            except subprocess.CalledProcessError:
                if not is_local:
                    _run_git(ws_dir, ["fetch", "--depth", "1", "origin", target_ref], check=False)
                _run_git(ws_dir, ["checkout", target_ref])
        else:
            _run_git(ws_dir, ["checkout", "HEAD"])

        cls._verify_no_escaping_symlinks(ws_dir)
        _run_git(ws_dir, ["checkout", "-B", "baseline"])
        head_proc = _run_git(ws_dir, ["rev-parse", "HEAD"])
        base_commit = head_proc.stdout.strip()
        cls._write_git_exclude(ws_dir)

        derived_name = (
            source_path.name
            if source_path is not None
            else (Path(urlparse(source_str).path).stem or ws_id)
        )
        meta = {
            "workspace_id": ws_id,
            "source_type": "local" if is_local else "git",
            "display_name": display_name or derived_name,
            "source_ref": str(ref or base_commit[:12]),
            "selected_subdirectory": subdirectory or "/",
            "root_prefix": "",
            "source_origin": source_str,
            "base_commit": base_commit,
            "branch": "baseline",
            "created_at": datetime.now(UTC).isoformat(),
        }
        cls._write_meta_file(ws_dir, meta)
        return cls(
            workspace_id=ws_id,
            root=ws_root,
            workspace_dir=ws_dir,
            base_commit=base_commit,
            branch_name="baseline",
            metadata=meta,
        )

    @classmethod
    def open(
        cls,
        workspace_id: str,
        *,
        root: Path | None = None,
        settings: Any = None,
    ) -> MissionWorkspace:
        """Open an existing workspace directory under ``WORKSPACE_ROOT``."""
        ws_root = root if root is not None else resolve_workspace_root(settings, create=False)
        ws_id = validate_workspace_id(workspace_id)
        ws_dir = ws_root / ws_id
        if not ws_dir.exists() or not (ws_dir / ".git").exists():
            raise WorkspaceError(f"Workspace not found: {ws_id!r}")
        meta = cls._read_meta_file(ws_dir)
        base_commit = str(meta.get("base_commit") or "").strip()
        if not base_commit:
            base_commit = _run_git(ws_dir, ["rev-parse", "baseline"]).stdout.strip()
        branch_name = _run_git(ws_dir, ["rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip()
        return cls(
            workspace_id=ws_id,
            root=ws_root,
            workspace_dir=ws_dir,
            base_commit=base_commit,
            branch_name=branch_name,
            metadata=meta,
        )

    @classmethod
    def _init_baseline_repo(
        cls,
        *,
        ws_root: Path,
        ws_id: str,
        ws_dir: Path,
        meta: dict[str, Any],
    ) -> MissionWorkspace:
        try:
            _run_git(ws_dir, ["init", "-b", "baseline"])
        except subprocess.CalledProcessError:
            _run_git(ws_dir, ["init"])
            _run_git(ws_dir, ["checkout", "-B", "baseline"])
        _run_git(ws_dir, ["config", "core.hooksPath", "/dev/null"])
        cls._write_git_exclude(ws_dir)
        cls._write_meta_file(ws_dir, meta)
        _run_git(ws_dir, ["add", "-A"])
        _run_git(ws_dir, ["commit", "--allow-empty", "-m", "baseline"])
        base_commit = _run_git(ws_dir, ["rev-parse", "HEAD"]).stdout.strip()
        meta["base_commit"] = base_commit
        meta["branch"] = "baseline"
        cls._write_meta_file(ws_dir, meta)
        return cls(
            workspace_id=ws_id,
            root=ws_root,
            workspace_dir=ws_dir,
            base_commit=base_commit,
            branch_name="baseline",
            metadata=meta,
        )

    @staticmethod
    def _copy_plain_directory(src_dir: Path, dst_dir: Path) -> None:
        src_resolved = src_dir.resolve()
        dst_resolved = dst_dir.resolve()
        entry_count = 0
        total_bytes = 0
        for root_str, dirs, files in os.walk(src_resolved, followlinks=False):
            dirs[:] = sorted(
                d
                for d in dirs
                if d not in _SKIP_DIR_NAMES
                and d != WORKSPACE_INTERNAL_DIR
                and not (Path(root_str) / d).is_symlink()
            )
            rel_dir = Path(root_str).relative_to(src_resolved)
            for filename in sorted(files):
                if filename == WORKSPACE_META_FILENAME:
                    continue
                src_file = Path(root_str) / filename
                if src_file.is_symlink():
                    raise WorkspaceSecurityError(
                        f"Symlink file forbidden in local directory import: {src_file}"
                    )
                entry_count += 1
                if entry_count > MAX_WORKSPACE_ENTRIES:
                    raise WorkspaceSecurityError("Local directory exceeds workspace entry limit.")
                data = src_file.read_bytes()
                total_bytes += len(data)
                if total_bytes > MAX_WORKSPACE_UNCOMPRESSED_BYTES:
                    raise WorkspaceSecurityError("Local directory exceeds workspace byte limit.")
                rel_posix = (rel_dir / filename).as_posix()
                validate_workspace_rel_path(rel_posix)
                target = dst_dir.joinpath(*rel_posix.split("/"))
                target_resolved = target.resolve()
                if dst_resolved not in target_resolved.parents:
                    raise WorkspaceSecurityError(f"Escaping path rejected: {rel_posix!r}")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)

    @staticmethod
    def _verify_no_escaping_symlinks(ws_dir: Path) -> None:
        ws_resolved = ws_dir.resolve()
        for root_str, dirs, files in os.walk(ws_dir, followlinks=False):
            if ".git" in dirs:
                dirs.remove(".git")
            for name in list(dirs) + list(files):
                candidate = Path(root_str) / name
                if candidate.is_symlink():
                    resolved = candidate.resolve()
                    if ws_resolved != resolved and ws_resolved not in resolved.parents:
                        raise WorkspaceSecurityError(
                            f"Symlink escaping workspace root forbidden: {candidate}"
                        )

    @staticmethod
    def _write_git_exclude(ws_dir: Path) -> None:
        exclude_path = ws_dir / ".git" / "info" / "exclude"
        exclude_path.parent.mkdir(parents=True, exist_ok=True)
        existing = exclude_path.read_text(encoding="utf-8") if exclude_path.exists() else ""
        lines = existing.splitlines()
        missing = [
            entry
            for entry in (WORKSPACE_META_FILENAME, f"{WORKSPACE_INTERNAL_DIR}/")
            if entry not in lines
        ]
        if missing:
            suffix = "\n" if existing and not existing.endswith("\n") else ""
            exclude_path.write_text(
                f"{existing}{suffix}" + "\n".join(missing) + "\n",
                encoding="utf-8",
            )

    @staticmethod
    def _write_meta_file(ws_dir: Path, meta: dict[str, Any]) -> None:
        (ws_dir / WORKSPACE_META_FILENAME).write_text(
            json.dumps(meta, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    @staticmethod
    def _read_meta_file(ws_dir: Path) -> dict[str, Any]:
        meta_path = ws_dir / WORKSPACE_META_FILENAME
        if not meta_path.exists():
            return {}
        try:
            loaded = json.loads(meta_path.read_text(encoding="utf-8"))
            return loaded if isinstance(loaded, dict) else {}
        except Exception:
            return {}

    def current_head(self) -> str:
        """Return the current HEAD commit SHA."""
        return _run_git(self.workspace_dir, ["rev-parse", "HEAD"]).stdout.strip()

    def branch(self, mission_id: str) -> str:
        """Create/checkout ``thefactory/mission-<mission_id>`` from ``baseline``."""
        target_branch = _mission_branch_name(mission_id)
        existing = _run_git(
            self.workspace_dir,
            ["rev-parse", "--verify", "--quiet", target_branch],
            check=False,
        )
        if existing.returncode == 0:
            _run_git(self.workspace_dir, ["checkout", target_branch])
        else:
            _run_git(self.workspace_dir, ["checkout", "-b", target_branch, "baseline"])
        self.branch_name = target_branch
        self.metadata["branch"] = target_branch
        self.metadata["mission_id"] = mission_id
        self._write_meta_file(self.workspace_dir, self.metadata)
        return target_branch

    def read_file(self, rel_path: str, *, revision: str | None = None) -> str:
        """Read UTF-8 file text from the workspace working tree or a git revision."""
        clean_path = validate_workspace_rel_path(rel_path)
        if revision:
            if revision.startswith("-"):
                raise WorkspaceSecurityError(f"Unsafe revision name: {revision!r}")
            proc = _run_git(
                self.workspace_dir,
                ["show", f"{revision}:{clean_path}"],
                check=False,
                text=False,
            )
            if proc.returncode != 0:
                raise FileNotFoundError(f"{clean_path} not found at revision {revision}")
            return bytes(proc.stdout).decode("utf-8", errors="replace")

        target = _ensure_contained_path(self.workspace_dir, clean_path)
        if not target.exists() or not target.is_file():
            raise FileNotFoundError(clean_path)
        return target.read_bytes().decode("utf-8", errors="replace")

    def list_files(self, *, subdirectory: str = DEFAULT_SUBDIRECTORY) -> list[dict[str, Any]]:
        """List files currently tracked/present in the workspace tree."""
        ws_resolved = self.workspace_dir.resolve()
        sub_prefix = subdirectory.strip("/")
        proc = _run_git(self.workspace_dir, ["ls-files", "-z"], text=False)
        raw_paths = [p.decode("utf-8", errors="replace") for p in proc.stdout.split(b"\x00") if p]
        if not raw_paths:
            # Fallback walk in case repo has untracked working tree files before commit
            for root_str, dirs, files in os.walk(ws_resolved, followlinks=False):
                dirs[:] = sorted(d for d in dirs if d != ".git")
                for fname in sorted(files):
                    if fname == WORKSPACE_META_FILENAME:
                        continue
                    rel = (Path(root_str).relative_to(ws_resolved) / fname).as_posix()
                    raw_paths.append(rel)

        records: list[dict[str, Any]] = []
        for rel_posix in sorted(set(raw_paths)):
            if (
                rel_posix == WORKSPACE_META_FILENAME
                or rel_posix.startswith(".git/")
                or rel_posix == WORKSPACE_INTERNAL_DIR
                or rel_posix.startswith(f"{WORKSPACE_INTERNAL_DIR}/")
            ):
                continue
            if sub_prefix and not (
                rel_posix == sub_prefix or rel_posix.startswith(f"{sub_prefix}/")
            ):
                continue
            target = _ensure_contained_path(self.workspace_dir, rel_posix)
            if not target.exists() or not target.is_file():
                continue
            raw_bytes = target.read_bytes()
            text = raw_bytes.decode("utf-8", errors="replace")
            line_count = len(text.splitlines()) if raw_bytes else 0
            records.append(
                {
                    "path": rel_posix,
                    "language": _detect_language(rel_posix),
                    "size_bytes": len(raw_bytes),
                    "bytes": len(raw_bytes),
                    "estimated_lines": line_count,
                    "sha256": hashlib.sha256(raw_bytes).hexdigest(),
                }
            )
        return records

    def write_files(
        self,
        files: dict[str, str | bytes],
        message: str = "mission update",
    ) -> str:
        """Write and commit the given files onto the active branch without deleting other files."""
        if not files:
            return self.current_head()
        written_paths: list[str] = []
        for raw_rel, content in files.items():
            clean_path = validate_workspace_rel_path(raw_rel)
            target = _ensure_contained_path(self.workspace_dir, clean_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(content, (bytes, bytearray)):
                target.write_bytes(bytes(content))
            else:
                target.write_bytes(str(content).encode("utf-8"))
            written_paths.append(clean_path)

        _run_git(self.workspace_dir, ["add", "--", *written_paths])
        _run_git(self.workspace_dir, ["commit", "--allow-empty", "-m", message])
        return self.current_head()

    def diff(self, base: str = "baseline") -> str:
        """Return unified ``git diff <base>..HEAD`` for the workspace."""
        if str(base).startswith("-"):
            raise WorkspaceSecurityError(f"Unsafe git base ref: {base!r}")
        proc = _run_git(self.workspace_dir, ["diff", f"{base}..HEAD"], check=False)
        return str(proc.stdout or "")

    def modified_files(self, base: str = "baseline") -> list[str]:
        """Return relative file paths changed between ``base`` and ``HEAD``."""
        if str(base).startswith("-"):
            raise WorkspaceSecurityError(f"Unsafe git base ref: {base!r}")
        proc = _run_git(self.workspace_dir, ["diff", "--name-only", f"{base}..HEAD"], check=False)
        return [line.strip() for line in str(proc.stdout or "").splitlines() if line.strip()]

    def export_zip_bytes(self) -> bytes:
        """Export the full repository tree at branch ``HEAD`` as a ZIP archive."""
        files_proc = _run_git(self.workspace_dir, ["ls-tree", "-r", "--name-only", "HEAD"], check=False)
        has_tree_entries = bool(str(files_proc.stdout or "").strip())
        if has_tree_entries:
            proc = _run_git(self.workspace_dir, ["archive", "--format=zip", "HEAD"], text=False)
            return bytes(proc.stdout)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED):
            pass
        return buf.getvalue()

    def build_source_bundle_excerpt(
        self,
        *,
        max_chars: int = 80_000,
        selected_paths: list[str] | None = None,
    ) -> str:
        """Build a bounded ``## FILE <path>`` text bundle from workspace files for LLM prompts."""
        entries = self.list_files()
        allowed = set(selected_paths) if selected_paths else None
        chunks: list[str] = []
        used = 0
        for entry in entries:
            rel_path = entry["path"]
            if allowed is not None and rel_path not in allowed:
                continue
            try:
                content = self.read_file(rel_path)
            except (OSError, WorkspaceError):
                continue
            if "\x00" in content:
                continue
            block = f"## FILE {rel_path}\n{content.rstrip()}\n\n"
            if used + len(block) > max_chars:
                remaining = max(0, max_chars - used)
                if remaining > 64:
                    chunks.append(block[:remaining] + "\n...[truncated]\n")
                break
            chunks.append(block)
            used += len(block)
        return "".join(chunks)


def workspace_from_mission_metadata(
    metadata: dict[str, Any] | None,
    *,
    settings: Any = None,
) -> MissionWorkspace | None:
    """Open the MissionWorkspace referenced in mission metadata if it exists on disk."""
    if not isinstance(metadata, dict):
        return None
    ws_info = metadata.get("workspace")
    ws_id = ""
    if isinstance(ws_info, dict):
        ws_id = str(ws_info.get("workspace_id") or "").strip()
    if not ws_id:
        repo_import = metadata.get("repo_import")
        if isinstance(repo_import, dict):
            ws_id = str(repo_import.get("workspace_id") or "").strip()
    if not ws_id:
        return None
    try:
        return MissionWorkspace.open(ws_id, settings=settings)
    except WorkspaceError:
        return None


def _has_configured_workspace_root(settings: Any) -> bool:
    raw_root = getattr(settings, "workspace_root", None) if settings is not None else None
    if isinstance(raw_root, (str, Path)) and str(raw_root).strip():
        return True
    return bool(os.getenv("WORKSPACE_ROOT", "").strip())


def bind_mission_workspace(
    mission_id: str,
    metadata: dict[str, Any],
    *,
    settings: Any = None,
) -> MissionWorkspace | None:
    """Attach an imported workspace or materialize one from source_code, on a mission branch."""
    if not _has_configured_workspace_root(settings):
        return None

    ws = workspace_from_mission_metadata(metadata, settings=settings)
    if ws is None:
        safe_mission = re.sub(r"[^A-Za-z0-9._-]+", "-", str(mission_id or "").strip()).strip("-")
        default_ws_id = f"ws-{safe_mission}"[:120] if safe_mission else None
        if default_ws_id:
            try:
                ws = MissionWorkspace.open(default_ws_id, settings=settings)
            except WorkspaceError:
                ws = None

        if ws is None:
            raw_source = metadata.get("source_code")
            if isinstance(raw_source, str) and raw_source.strip():
                from .file_tree import parse_file_tree

                parsed = parse_file_tree(raw_source, max_files=MAX_WORKSPACE_ENTRIES)
                if parsed:
                    files_map: dict[str, str | bytes] = {}
                    for entry in parsed:
                        rel_path = entry.get("path", "")
                        try:
                            clean = validate_workspace_rel_path(rel_path)
                        except WorkspaceSecurityError:
                            continue
                        files_map[clean] = entry.get("content", "")
                    if files_map:
                        ws = MissionWorkspace.create_from_files(
                            files_map,
                            workspace_id=default_ws_id,
                            display_name=str(metadata.get("project_name") or mission_id),
                            settings=settings,
                        )

    if ws is None:
        return None

    branch_name = ws.branch(mission_id)
    existing_meta = metadata.get("workspace")
    ws_meta = dict(existing_meta) if isinstance(existing_meta, dict) else {}
    ws_meta.update(
        {
            "workspace_id": ws.workspace_id,
            "base_commit": ws.base_commit,
            "head_commit": ws.current_head(),
            "branch": branch_name,
        }
    )
    metadata["workspace"] = ws_meta
    return ws


def sync_generated_output_to_workspace(
    mission_id: str,
    metadata: dict[str, Any],
    generated_output: dict[str, Any] | None,
    *,
    commit_message: str | None = None,
    settings: Any = None,
) -> MissionWorkspace | None:
    """Write specialist generated/repaired files into the mission workspace and commit."""
    if not isinstance(generated_output, dict):
        return None
    ws = bind_mission_workspace(mission_id, metadata, settings=settings)
    if ws is None:
        # Also allow creating a workspace directly from generated output when a
        # greenfield mission configures a workspace root and emits a multi-file tree.
        if not _has_configured_workspace_root(settings):
            return None
        from .file_tree import parse_file_tree

        raw_code = str(generated_output.get("generated_code") or generated_output.get("code") or "")
        raw_files = generated_output.get("files")
        if not isinstance(raw_files, list) and not parse_file_tree(
            raw_code, max_files=MAX_WORKSPACE_ENTRIES
        ):
            return None
        safe_mission = re.sub(r"[^A-Za-z0-9._-]+", "-", str(mission_id or "").strip()).strip("-")
        ws_id = f"ws-{safe_mission}"[:120] if safe_mission else None
        ws = MissionWorkspace.create_from_files(
            {},
            workspace_id=ws_id,
            display_name=str(metadata.get("project_name") or mission_id),
            settings=settings,
        )
        ws.branch(mission_id)

    from .file_tree import parse_file_tree

    files_to_write: dict[str, str | bytes] = {}
    raw_files = generated_output.get("files")
    if isinstance(raw_files, list):
        for item in raw_files[:MAX_WORKSPACE_ENTRIES]:
            if not isinstance(item, dict):
                continue
            raw_path = str(item.get("path") or item.get("filename") or "").strip()
            raw_content = item.get("content") or item.get("code") or item.get("generated_code")
            if not raw_path or raw_content is None:
                continue
            try:
                clean = validate_workspace_rel_path(raw_path)
            except WorkspaceSecurityError:
                continue
            files_to_write[clean] = str(raw_content)

    raw_code = str(generated_output.get("generated_code") or generated_output.get("code") or "")
    if not files_to_write and raw_code.strip():
        parsed = parse_file_tree(raw_code, max_files=MAX_WORKSPACE_ENTRIES)
        if parsed:
            for item in parsed:
                try:
                    clean = validate_workspace_rel_path(item.get("path", ""))
                except WorkspaceSecurityError:
                    continue
                files_to_write[clean] = str(item.get("content") or "")
        else:
            fallback_name = str(generated_output.get("filename") or "").strip()
            if fallback_name:
                try:
                    clean = validate_workspace_rel_path(fallback_name)
                    files_to_write[clean] = raw_code
                except WorkspaceSecurityError:
                    pass

    if not files_to_write:
        return ws

    head_sha = ws.write_files(
        files_to_write,
        message=commit_message or f"mission {mission_id}: specialist codegen",
    )
    existing_meta = metadata.get("workspace")
    ws_meta = dict(existing_meta) if isinstance(existing_meta, dict) else {}
    ws_meta.update(
        {
            "workspace_id": ws.workspace_id,
            "base_commit": ws.base_commit,
            "head_commit": head_sha,
            "branch": ws.branch_name,
            "modified_files": ws.modified_files("baseline"),
        }
    )
    metadata["workspace"] = ws_meta
    return ws

