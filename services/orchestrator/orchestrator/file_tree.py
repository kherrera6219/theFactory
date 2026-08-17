"""Serialize and parse multi-file delivery trees.

Used by specialist codegen and disk delivery so an imported or SOW-promised
tree is written as many files, not one invented blob. Paths are relative;
callers must still apply containment checks before writing to disk.
"""

from __future__ import annotations

import os
import re
from typing import Any

FILE_MARKER = re.compile(r"^## FILE (.+)$", re.MULTILINE)
_MAX_FILES = 80
_MAX_PATH = 240
_MAX_CONTENT_CHARS = 200_000


def sanitize_rel_path(path: Any) -> str:
    """Return a relative path fragment with traversal and drive prefixes removed."""
    raw = str(path or "").strip().replace("\\", "/")
    raw = re.sub(r"^[A-Za-z]:", "", raw)
    raw = raw.lstrip("/")
    parts = [part for part in raw.split("/") if part and part not in {".", ".."}]
    cleaned = "/".join(parts)[:_MAX_PATH]
    return cleaned or "generated.txt"


def parse_file_tree(text: str) -> list[dict[str, str]]:
    """Parse a ``## FILE path`` bundle into ``[{path, content}, ...]``."""
    source = str(text or "")
    matches = list(FILE_MARKER.finditer(source))
    if not matches:
        return []
    files: list[dict[str, str]] = []
    for index, match in enumerate(matches[:_MAX_FILES]):
        path = sanitize_rel_path(match.group(1))
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(source)
        content = source[start:end].lstrip("\r\n")[:_MAX_CONTENT_CHARS]
        files.append({"path": path, "content": content})
    return files


def serialize_file_tree(files: list[dict[str, str]]) -> str:
    """Render files as a ``## FILE`` bundle for storage and disk splitting."""
    chunks: list[str] = []
    for item in files[:_MAX_FILES]:
        path = sanitize_rel_path(item.get("path"))
        content = str(item.get("content") or "")[:_MAX_CONTENT_CHARS]
        chunks.append(f"## FILE {path}\n{content.rstrip()}\n")
    return "\n".join(chunks).rstrip() + ("\n" if chunks else "")


def normalize_codegen_files(raw_files: Any) -> list[dict[str, str]]:
    """Accept LLM ``files`` arrays; drop empty or unreadable entries."""
    if not isinstance(raw_files, list):
        return []
    files: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in raw_files[:_MAX_FILES]:
        if not isinstance(item, dict):
            continue
        path = sanitize_rel_path(item.get("path") or item.get("filename") or item.get("name"))
        content = str(item.get("content") or item.get("code") or item.get("generated_code") or "")
        if len(content.strip()) < 1:
            continue
        if path in seen:
            continue
        seen.add(path)
        files.append({"path": path, "content": content[:_MAX_CONTENT_CHARS]})
    return files


def codegen_bundle_from_result(raw: dict[str, Any], generated_code: str) -> tuple[str, list[dict[str, str]]]:
    """Prefer an explicit files array; otherwise parse a ``## FILE`` bundle."""
    files = normalize_codegen_files(raw.get("files"))
    if not files:
        files = parse_file_tree(generated_code)
    if files:
        return serialize_file_tree(files), files
    return generated_code, []


def first_filename(files: list[dict[str, str]], fallback: str) -> str:
    if not files:
        return os.path.basename(fallback) or "generated.txt"
    return os.path.basename(files[0]["path"]) or fallback
