"""HTTP helper layer for Git-backed workspace import, review, and inspection."""

from __future__ import annotations

import base64
import hashlib
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from .file_tree import parse_file_tree
from .workspace import (
    DEFAULT_SUBDIRECTORY,
    MissionWorkspace,
    WorkspaceError,
    WorkspaceSecurityError,
    validate_workspace_rel_path,
    workspace_from_mission_metadata,
)

_MAX_REVIEW_FILES = 120
_SOURCE_CODE_LIMIT = 480_000
_INCLUDE_SOFT_LIMIT = 80_000
_REFERENCE_SOFT_LIMIT = 12_000
_EXCERPT_CHAR_LIMIT = 1_500
_EXCERPT_LINE_LIMIT = 20

_REQUESTED_LANGUAGE_MAP: dict[str, str] = {
    ".py": "python",
    ".pyw": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".mts": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".cs": "csharp",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".hpp": "cpp",
    ".php": "php",
    ".rb": "ruby",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".scala": "scala",
    ".hs": "haskell",
    ".ml": "ocaml",
    ".mli": "ocaml",
    ".jl": "julia",
    ".r": "r",
    ".zig": "zig",
}


def _normalize_subdirectory(raw: Any) -> str:
    cleaned = "/" + "/".join(part for part in str(raw or "/").strip().split("/") if part)
    if ".." in cleaned.split("/"):
        raise HTTPException(status_code=400, detail="subdirectory cannot contain traversal.")
    if len(cleaned) > 250:
        raise HTTPException(status_code=400, detail="subdirectory path is too long.")
    return cleaned or "/"


def _clamp_max_files(raw: Any, default: int = 500) -> int:
    try:
        parsed = int(raw) if raw is not None else default
    except (TypeError, ValueError):
        return default
    return max(1, min(5000, parsed))


def _requested_language_from_path(path: str) -> str | None:
    return _REQUESTED_LANGUAGE_MAP.get(Path(path).suffix.lower())


def _is_likely_binary_text(text: str) -> bool:
    if not text:
        return False
    control = sum(1 for ch in text if ord(ch) == 0 or (ord(ch) < 32 and ch not in "\t\n\r"))
    return control / max(1, len(text)) > 0.03


def _content_excerpt(text: str) -> str:
    lines = text.splitlines()[:_EXCERPT_LINE_LIMIT]
    joined = "\n".join(lines)
    if len(joined) > _EXCERPT_CHAR_LIMIT:
        return joined[:_EXCERPT_CHAR_LIMIT] + "\n...[truncated]"
    return joined


def import_workspace_from_payload(payload: dict[str, Any], *, settings: Any) -> dict[str, Any]:
    """Create a Git-backed baseline workspace from ZIP base64, local path, or Git URL."""
    archive_b64 = str(payload.get("archive_base64") or "").strip()
    local_path = str(payload.get("local_path") or "").strip()
    git_url = str(payload.get("git_url") or "").strip()
    source_type = str(payload.get("source_type") or "").strip().lower()
    subdirectory = _normalize_subdirectory(payload.get("subdirectory") or DEFAULT_SUBDIRECTORY)
    max_files = _clamp_max_files(payload.get("max_files"), default=500)
    explicit_id = str(payload.get("workspace_id") or "").strip() or None
    display_name = str(payload.get("display_name") or "").strip() or None
    source_ref = str(payload.get("ref") or payload.get("source_ref") or "").strip() or None

    try:
        if archive_b64 or source_type == "zip":
            if not archive_b64:
                raise HTTPException(status_code=400, detail="archive_base64 is required for zip import")
            try:
                raw_bytes = base64.b64decode(archive_b64, validate=True)
            except Exception as exc:
                raise HTTPException(status_code=400, detail="Invalid base64 ZIP payload") from exc
            archive_sha256 = hashlib.sha256(raw_bytes).hexdigest()
            ws = MissionWorkspace.create_from_zip(
                raw_bytes,
                workspace_id=explicit_id,
                display_name=display_name,
                source_ref=source_ref or "main",
                subdirectory=subdirectory,
                settings=settings,
            )
            source_kind = "zip"
            archive_id = f"repozip-{archive_sha256[:12]}"
            html_url = None
        elif local_path or source_type == "local":
            if not local_path:
                raise HTTPException(status_code=400, detail="local_path is required for local import")
            ws = MissionWorkspace.create_from_local(
                local_path,
                workspace_id=explicit_id,
                display_name=display_name,
                source_ref=source_ref or "",
                subdirectory=subdirectory,
                settings=settings,
            )
            source_kind = "local"
            archive_sha256 = hashlib.sha256(ws.base_commit.encode("utf-8")).hexdigest()
            archive_id = f"ws-{ws.workspace_id}"
            html_url = None
        elif git_url or source_type == "git":
            if not git_url:
                raise HTTPException(status_code=400, detail="git_url is required for git import")
            ws = MissionWorkspace.create_from_git(
                git_url,
                ref=source_ref,
                workspace_id=explicit_id,
                display_name=display_name,
                subdirectory=subdirectory,
                settings=settings,
            )
            source_kind = "git"
            archive_sha256 = hashlib.sha256(ws.base_commit.encode("utf-8")).hexdigest()
            archive_id = f"ws-{ws.workspace_id}"
            html_url = git_url
        else:
            raise HTTPException(
                status_code=422,
                detail="One of archive_base64, local_path, or git_url must be supplied.",
            )
    except HTTPException:
        raise
    except (WorkspaceSecurityError, WorkspaceError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    all_entries = ws.list_files(subdirectory=subdirectory)
    truncated = len(all_entries) > max_files
    entries = all_entries[:max_files]
    total_lines = sum(int(item.get("estimated_lines") or 0) for item in entries)
    total_bytes = sum(int(item.get("size_bytes") or 0) for item in entries)
    effective_display = str(ws.metadata.get("display_name") or ws.workspace_id)
    effective_ref = str(ws.metadata.get("source_ref") or source_ref or "baseline")

    from .aim_generator import generate_workspace_aim
    from .workspace_indexer import index_workspace

    index_data = index_workspace(ws, settings=settings)
    workspace_aim = generate_workspace_aim(
        ws,
        index_data=index_data,
        settings=settings,
    )

    return {
        "repository": {
            "source": source_kind,
            "owner": "local",
            "repo": effective_display,
            "branch": effective_ref,
            "default_branch": effective_ref,
            "private": True,
            "html_url": html_url,
            "display_name": effective_display,
            "archive_id": archive_id,
            "archive_sha256": archive_sha256,
            "source_ref": effective_ref,
            "root_prefix": str(ws.metadata.get("root_prefix") or ""),
            "workspace_id": ws.workspace_id,
            "base_commit": ws.base_commit,
        },
        "files": [
            {
                "path": item["path"],
                "language": item["language"],
                "bytes": item["bytes"],
                "estimated_lines": item["estimated_lines"],
            }
            for item in entries
        ],
        "stats": {
            "total_files": len(entries),
            "estimated_total_lines": total_lines,
            "selected_subdirectory": subdirectory,
            "truncated": truncated,
            "skipped_large_files": 0,
            "skipped_unsafe_entries": 0,
            "skipped_directory_entries": 0,
            "skipped_unreadable_entries": 0,
            "entry_limit_reached": False,
            "byte_limit_reached": False,
            "total_entries": len(all_entries),
            "total_uncompressed_bytes": total_bytes,
        },
        "index_stats": index_data.get("index_stats") or {},
        "aim": workspace_aim,
        "logs": [
            f"Initialized git workspace {ws.workspace_id} at baseline {ws.base_commit[:12]}.",
            f"Indexed {len(entries)} files from {subdirectory}.",
            (
                f"Built workspace index ({(index_data.get('index_stats') or {}).get('total_chunks', 0)} "
                f"chunks, primary={workspace_aim.get('primary_language', 'unknown')}) and AIM at baseline."
            ),
        ],
    }


def review_workspace_from_payload(
    workspace_id: str,
    payload: dict[str, Any],
    *,
    settings: Any,
) -> dict[str, Any]:
    """Build a RepoReviewResponse directly from an existing Git workspace."""
    try:
        ws = MissionWorkspace.open(workspace_id, settings=settings)
    except WorkspaceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    subdirectory = _normalize_subdirectory(
        payload.get("subdirectory") or ws.metadata.get("selected_subdirectory") or "/"
    )
    mission_type = str(payload.get("mission_type") or "analyze").strip().lower()
    if mission_type not in {"analyze", "update", "add_feature", "refactor", "port"}:
        raise HTTPException(
            status_code=400,
            detail="mission_type must be one of analyze, update, add_feature, refactor, or port.",
        )
    description = str(payload.get("description") or "").strip()[:2000]
    if mission_type in {"update", "add_feature"} and len(description) < 3:
        raise HTTPException(
            status_code=400,
            detail="description must be provided for update and add_feature reviews.",
        )

    ws_files_by_path = {entry["path"]: entry for entry in ws.list_files(subdirectory=subdirectory)}
    raw_selected = payload.get("selected_files")
    if isinstance(raw_selected, list) and raw_selected:
        selected_specs: list[tuple[str, str]] = []
        for item in raw_selected[:_MAX_REVIEW_FILES]:
            if not isinstance(item, dict):
                continue
            rel = str(item.get("path") or "").strip()
            action = str(item.get("overlay_action") or "include").strip().lower()
            if action not in {"include", "reference"}:
                continue
            if rel in ws_files_by_path:
                selected_specs.append((rel, action))
    else:
        selected_specs = [(p, "include") for p in sorted(ws_files_by_path)[:_MAX_REVIEW_FILES]]

    if not selected_specs:
        raise HTTPException(
            status_code=400,
            detail="selected_files must include 1-120 valid files from the workspace.",
        )

    fetched_files: list[dict[str, Any]] = []
    bundled_parts: list[str] = []
    used_chars = 0
    bundled_paths: set[str] = set()
    truncated_paths: set[str] = set()
    unavailable_paths: set[str] = set()
    lang_counts: Counter[str] = Counter()

    for rel_path, overlay_action in selected_specs:
        meta = ws_files_by_path[rel_path]
        raw_bytes = (ws.workspace_dir / rel_path).read_bytes()
        raw_text = raw_bytes.decode("utf-8", errors="replace")
        text_available = not _is_likely_binary_text(raw_text)
        req_lang = _requested_language_from_path(rel_path)
        if overlay_action == "include" and req_lang:
            lang_counts[req_lang] += 1
        sha = hashlib.sha256(raw_bytes).hexdigest() if text_available else None

        if not text_available:
            unavailable_paths.add(rel_path)
        else:
            limit = _INCLUDE_SOFT_LIMIT if overlay_action == "include" else _REFERENCE_SOFT_LIMIT
            excerpt_text = raw_text[:limit]
            block = f"## FILE {rel_path}\n{excerpt_text.rstrip()}\n\n"
            if used_chars + len(block) <= _SOURCE_CODE_LIMIT:
                bundled_parts.append(block)
                used_chars += len(block)
                bundled_paths.add(rel_path)
                if len(raw_text) > limit:
                    truncated_paths.add(rel_path)
            else:
                truncated_paths.add(rel_path)

        fetched_files.append(
            {
                "path": rel_path,
                "overlay_action": overlay_action,
                "language": meta["language"],
                "requested_language": req_lang,
                "bytes": meta["bytes"],
                "estimated_lines": meta["estimated_lines"],
                "summary": (
                    f"{meta['language']} file ({meta['estimated_lines']} lines)"
                    if text_available
                    else f"Binary {meta['language']} asset retained as metadata only."
                ),
                "content_excerpt": _content_excerpt(raw_text) if text_available else "",
                "text_available": text_available,
                "included_in_source": rel_path in bundled_paths,
                "truncated_in_source": rel_path in truncated_paths,
                "sha": sha,
            }
        )

    if not lang_counts:
        for f in fetched_files:
            if f["requested_language"]:
                lang_counts[f["requested_language"]] += 1

    target_language = lang_counts.most_common(1)[0][0] if lang_counts else None
    source_code = "".join(bundled_parts)
    archive_sha256 = hashlib.sha256(ws.base_commit.encode("utf-8")).hexdigest()
    display_name = str(
        payload.get("display_name") or ws.metadata.get("display_name") or ws.workspace_id
    )
    source_ref = str(
        payload.get("source_ref") or ws.metadata.get("source_ref") or ws.base_commit[:12]
    )
    fp_seed = json.dumps(
        {
            "workspace_id": ws.workspace_id,
            "base_commit": ws.base_commit,
            "subdirectory": subdirectory,
            "mission_type": mission_type,
            "description": description,
            "files": [{"path": f["path"], "action": f["overlay_action"], "sha": f["sha"]} for f in fetched_files],
        },
        sort_keys=True,
    )
    fingerprint = hashlib.sha256(fp_seed.encode("utf-8")).hexdigest()
    include_count = sum(1 for f in fetched_files if f["overlay_action"] == "include")
    reference_count = len(fetched_files) - include_count
    source_kind = str(ws.metadata.get("source_type") or "local")
    if source_kind not in {"zip", "local", "git"}:
        source_kind = "local"

    return {
        "request_id": f"repo-review-{fingerprint[:12]}",
        "review_fingerprint": fingerprint,
        "source": "repo-review",
        "generated_at": datetime.now(UTC).isoformat(),
        "repository": {
            "source": source_kind,
            "owner": "local",
            "repo": display_name,
            "branch": source_ref,
            "html_url": ws.metadata.get("source_origin") if source_kind == "git" else None,
            "selected_subdirectory": subdirectory,
            "archive_id": f"ws-{ws.workspace_id}",
            "archive_sha256": archive_sha256,
            "display_name": display_name,
            "source_ref": source_ref,
            "root_prefix": str(ws.metadata.get("root_prefix") or ""),
            "workspace_id": ws.workspace_id,
            "base_commit": ws.base_commit,
        },
        "mission_type": mission_type,
        "requested_target_language": target_language,
        "source_code": source_code,
        "source_stats": {
            "selected_files": len(fetched_files),
            "include_files": include_count,
            "reference_files": reference_count,
            "source_characters": len(source_code),
            "bundled_files": len(bundled_paths),
            "truncated_files": len(truncated_paths),
            "unavailable_files": len(unavailable_paths),
        },
        "plan": [
            {
                "title": "Workspace baseline verification",
                "description": f"Inspect baseline commit {ws.base_commit[:12]} across {len(fetched_files)} selected files.",
            },
            {
                "title": "Isolated branch execution",
                "description": "Execute specialist changes on dedicated mission branch and verify tests.",
            },
        ],
        "diff_summary": [
            f"Reviewed {len(fetched_files)} selected files from git workspace {display_name}@{source_ref}.",
            f"Direct-edit scope covers {include_count} file(s); {reference_count} reference-only.",
        ],
        "risk_notes": [],
        "test_plan": [
            "Run existing repository tests inside isolated verification sandbox after edits.",
        ],
        "files": fetched_files,
        "notice": None,
    }


def _fallback_artifact_files(artifact_text: str) -> list[dict[str, Any]]:
    parsed = parse_file_tree(artifact_text or "")
    entries: list[dict[str, Any]] = []
    for item in parsed:
        content = item.get("content") or ""
        raw = content.encode("utf-8", errors="replace")
        entries.append(
            {
                "path": item["path"],
                "language": "Text",
                "size_bytes": len(raw),
                "bytes": len(raw),
                "estimated_lines": len(content.splitlines()) if content else 0,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "modified": True,
            }
        )
    return entries


def build_mission_workspace_tree(
    mission: Any,
    *,
    settings: Any,
    artifact_records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return full file tree and git metadata for a mission's workspace."""
    metadata = getattr(mission, "metadata", None)
    if not isinstance(metadata, dict):
        metadata = {}
    mission_id = str(getattr(mission, "mission_id", "") or "")
    ws = workspace_from_mission_metadata(metadata, settings=settings)
    if ws is not None:
        changed = set(ws.modified_files("baseline"))
        files = []
        for entry in ws.list_files():
            files.append({**entry, "modified": entry["path"] in changed})
        return {
            "mission_id": mission_id,
            "workspace_id": ws.workspace_id,
            "base_commit": ws.base_commit,
            "head_commit": ws.current_head(),
            "branch": ws.branch_name,
            "modified_files": sorted(changed),
            "files": files,
        }

    records = artifact_records or []
    primary = next(
        (
            r
            for r in records
            if str(r.get("artifact_type") or "").strip().lower() == "generated_code"
            and r.get("artifact_text")
        ),
        records[0] if records else None,
    )
    files = _fallback_artifact_files(str(primary.get("artifact_text") or "")) if primary else []
    return {
        "mission_id": mission_id,
        "workspace_id": None,
        "base_commit": None,
        "head_commit": None,
        "branch": None,
        "modified_files": [f["path"] for f in files],
        "files": files,
    }


def read_mission_workspace_file(
    mission: Any,
    rel_path: str,
    *,
    settings: Any,
    artifact_records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Read a single file (and its baseline revision if any) from a mission workspace."""
    try:
        clean_path = validate_workspace_rel_path(rel_path)
    except WorkspaceSecurityError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    metadata = getattr(mission, "metadata", None)
    if not isinstance(metadata, dict):
        metadata = {}
    mission_id = str(getattr(mission, "mission_id", "") or "")
    ws = workspace_from_mission_metadata(metadata, settings=settings)
    if ws is not None:
        try:
            content = ws.read_file(clean_path)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=f"File not found: {clean_path}") from exc
        except WorkspaceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        try:
            baseline_content = ws.read_file(clean_path, revision=ws.base_commit)
        except FileNotFoundError:
            baseline_content = None
        return {
            "mission_id": mission_id,
            "workspace_id": ws.workspace_id,
            "path": clean_path,
            "content": content,
            "baseline_content": baseline_content,
            "size_bytes": len(content.encode("utf-8", errors="replace")),
            "modified": baseline_content is None or baseline_content != content,
        }

    for record in artifact_records or []:
        text = str(record.get("artifact_text") or "")
        for entry in parse_file_tree(text):
            if entry["path"] == clean_path:
                content = entry["content"]
                return {
                    "mission_id": mission_id,
                    "workspace_id": None,
                    "path": clean_path,
                    "content": content,
                    "baseline_content": None,
                    "size_bytes": len(content.encode("utf-8", errors="replace")),
                    "modified": True,
                }
    raise HTTPException(status_code=404, detail=f"File not found: {clean_path}")
