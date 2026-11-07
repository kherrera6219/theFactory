"""Surgical file-level self-repair and multi-turn Runtime QC helpers."""

from __future__ import annotations

import hashlib
import os
import re
from typing import Any

from .file_tree import parse_file_tree, sanitize_rel_path, serialize_file_tree

_HEX_ADDR_RE = re.compile(r"0x[0-9a-fA-F]+")
_TEMP_PATH_RE = re.compile(r"/(?:tmp|var/folders)/[A-Za-z0-9_./-]+")
_MAX_SURGICAL_CODE_CHARS = 32_000


def extract_failing_files(
    stderr: str,
    stdout: str,
    files: list[dict[str, str]],
) -> list[str]:
    """Identify which files in a multi-file bundle are referenced in stderr/stdout."""
    if not files:
        return []
    combined = f"{stderr or ''}\n{stdout or ''}"
    if not combined.strip():
        return [item["path"] for item in files]

    matched: list[str] = []
    for item in files:
        path = str(item.get("path") or "").strip()
        if not path:
            continue
        basename = os.path.basename(path)
        if path in combined or (basename and basename in combined):
            if path not in matched:
                matched.append(path)

    return matched or [item["path"] for item in files]


def compute_error_signature(stderr: str, stdout: str, exit_code: Any = None) -> str:
    """Compute a stable hash signature for a runtime/compiler error output."""
    raw = (stderr or "").strip() or (stdout or "").strip()
    normalized = _HEX_ADDR_RE.sub("0xADDR", raw)
    normalized = _TEMP_PATH_RE.sub("<TMP_WORKSPACE>", normalized)
    lines = [line.strip() for line in normalized.splitlines() if line.strip()]
    tail = "\n".join(lines[-12:])[:1500]
    payload = f"exit={exit_code}|{tail}"
    return hashlib.sha256(payload.encode("utf-8", errors="replace")).hexdigest()[:16]


def is_duplicate_error_signature(
    stderr: str,
    stdout: str,
    previous_signatures: list[str],
    exit_code: Any = None,
) -> tuple[bool, str]:
    """Return (is_duplicate, signature) to detect stalled repair loops."""
    sig = compute_error_signature(stderr, stdout, exit_code=exit_code)
    return (sig in previous_signatures, sig)


def build_surgical_repair_context(
    *,
    execution: dict[str, Any],
    generated_code: str,
    attempt: int = 1,
    max_attempts: int = 2,
    previous_errors: list[str] | None = None,
) -> dict[str, Any]:
    """Construct a surgical repair context preserving full failing files up to 32k chars."""
    stderr = str(execution.get("stderr_preview") or "")[:4000]
    stdout = str(execution.get("stdout_preview") or "")[:2000]
    files = parse_file_tree(generated_code)
    all_paths = [item["path"] for item in files]
    failing_paths = extract_failing_files(stderr, stdout, files)

    if files:
        prioritized: list[dict[str, str]] = []
        failing_set = set(failing_paths)
        for item in files:
            if item["path"] in failing_set:
                prioritized.append(item)
        for item in files:
            if item["path"] not in failing_set:
                prioritized.append(item)
        previous_code = serialize_file_tree(prioritized)[:_MAX_SURGICAL_CODE_CHARS]
    else:
        previous_code = str(generated_code or "")[:_MAX_SURGICAL_CODE_CHARS]

    return {
        "attempt": attempt,
        "max_attempts": max_attempts,
        "exit_code": execution.get("exit_code"),
        "stderr_preview": stderr,
        "stdout_preview": stdout,
        "command": execution.get("command"),
        "previous_code": previous_code,
        "file_tree_manifest": all_paths,
        "failing_files": failing_paths,
        "previous_errors": list(previous_errors or [])[-4:],
    }


def merge_repaired_files(original_code: str, repaired_code: str) -> str:
    """Merge a partial or full multi-file repair bundle back into the original file tree."""
    orig_files = parse_file_tree(original_code)
    rep_files = parse_file_tree(repaired_code)
    if not orig_files or not rep_files:
        return repaired_code

    rep_by_path = {sanitize_rel_path(item["path"]): item["content"] for item in rep_files}
    merged: list[dict[str, str]] = []
    seen: set[str] = set()

    for item in orig_files:
        norm_path = sanitize_rel_path(item["path"])
        seen.add(norm_path)
        if norm_path in rep_by_path:
            merged.append({"path": norm_path, "content": rep_by_path[norm_path]})
        else:
            merged.append({"path": norm_path, "content": item["content"]})

    for item in rep_files:
        norm_path = sanitize_rel_path(item["path"])
        if norm_path not in seen:
            seen.add(norm_path)
            merged.append({"path": norm_path, "content": item["content"]})

    return serialize_file_tree(merged)
