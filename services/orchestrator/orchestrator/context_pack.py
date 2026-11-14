"""Focused specialist retrieval context pack builder without 12 KB file truncation (Phase 5)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .workspace import MissionWorkspace

_FILE_BLOCK_RE = re.compile(r"^## FILE (.+)$", re.MULTILINE)


def parse_file_bundle(source_code: str) -> list[dict[str, str]]:
    """Parse ``## FILE <path>`` blocks into ordered ``{path, content}`` entries."""
    raw = str(source_code or "")
    if not raw.strip():
        return []
    matches = list(_FILE_BLOCK_RE.finditer(raw))
    if not matches:
        return [{"path": "inline_source.txt", "content": raw}]
    items: list[dict[str, str]] = []
    for idx, match in enumerate(matches):
        path = str(match.group(1) or "").strip() or f"file-{idx + 1}.txt"
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(raw)
        content = raw[start:end].lstrip("\r\n")
        items.append({"path": path, "content": content})
    return items


def _normalize_slice_paths(slice_spec: dict[str, Any] | None) -> list[str]:
    if not isinstance(slice_spec, dict):
        return []
    raw_files = slice_spec.get("files")
    if not isinstance(raw_files, list):
        return []
    cleaned: list[str] = []
    for item in raw_files:
        text = str(item or "").strip().replace("\\", "/").lstrip("./")
        if text and text not in cleaned:
            cleaned.append(text)
    return cleaned


def build_specialist_context_pack(
    *,
    ws: MissionWorkspace | None = None,
    source_code: str = "",
    slice_spec: dict[str, Any] | None = None,
    aim: dict[str, Any] | None = None,
    index_data: dict[str, Any] | None = None,
    query: str = "",
    max_neighbors: int = 24,
) -> dict[str, Any]:
    """Assemble full-content target files plus 1-hop symbol/import neighbors for a specialist.

    Target/slice files are NEVER truncated at 12 KB — specialists always receive
    complete file bodies alongside symbol signatures of callers and imports.
    """
    bundle_entries = parse_file_bundle(source_code)
    bundle_by_path = {entry["path"]: entry["content"] for entry in bundle_entries}

    slice_paths = _normalize_slice_paths(slice_spec)
    target_files: list[dict[str, str]] = []

    if ws is not None:
        ws_paths = [str(item["path"]) for item in ws.list_files()]
        chosen_paths = slice_paths if slice_paths else ws_paths
        for rel in chosen_paths:
            if rel in ws_paths:
                try:
                    content = ws.read_file(rel)
                except OSError:
                    content = bundle_by_path.get(rel, "")
                if "\x00" not in content:
                    target_files.append({"path": rel, "content": content})
            elif rel in bundle_by_path:
                target_files.append({"path": rel, "content": bundle_by_path[rel]})
    else:
        if slice_paths:
            for rel in slice_paths:
                if rel in bundle_by_path:
                    target_files.append({"path": rel, "content": bundle_by_path[rel]})
        if not target_files:
            target_files = list(bundle_entries)

    target_path_set = {item["path"] for item in target_files}

    # Resolve 1-hop imported and caller files + symbol signatures from workspace index.
    resolved_index = index_data
    if resolved_index is None and ws is not None:
        from .workspace_indexer import index_workspace, load_workspace_index

        resolved_index = load_workspace_index(ws) or index_workspace(ws)

    neighbor_paths: set[str] = set()
    neighbor_signatures: list[dict[str, Any]] = []
    if isinstance(resolved_index, dict):
        graph = resolved_index.get("symbol_graph") or {}
        imports_by_path = graph.get("imports_by_path") or {}
        importers_by_path = graph.get("importers_by_path") or {}
        callers_by_path = graph.get("callers_by_path") or {}
        for t_path in target_path_set:
            for dep in imports_by_path.get(t_path) or []:
                if dep not in target_path_set:
                    neighbor_paths.add(str(dep))
            for caller in importers_by_path.get(t_path) or []:
                if caller not in target_path_set:
                    neighbor_paths.add(str(caller))
            for caller in callers_by_path.get(t_path) or []:
                if caller not in target_path_set:
                    neighbor_paths.add(str(caller))

        if query and ws is not None:
            from .workspace_indexer import search_workspace_chunks

            for hit in search_workspace_chunks(ws, query, top_k=6, index_data=resolved_index):
                h_path = str(hit.get("path") or "")
                if h_path and h_path not in target_path_set:
                    neighbor_paths.add(h_path)

        symbols = graph.get("symbols") or []
        for sym in symbols:
            if not isinstance(sym, dict):
                continue
            s_path = str(sym.get("path") or "")
            if s_path in neighbor_paths:
                neighbor_signatures.append(
                    {
                        "path": s_path,
                        "line": int(sym.get("line") or 1),
                        "kind": str(sym.get("kind") or "symbol"),
                        "name": str(sym.get("name") or ""),
                        "signature": str(sym.get("signature") or sym.get("name") or "")[:200],
                    }
                )
            if len(neighbor_signatures) >= max_neighbors:
                break

    aim_excerpt: dict[str, Any] = {}
    if isinstance(aim, dict) and aim:
        for key in (
            "workspace_id",
            "primary_language",
            "detected_languages",
            "frameworks",
            "source_framework",
            "entrypoints",
            "test_discovery",
            "repository_summary",
        ):
            if aim.get(key) is not None:
                aim_excerpt[key] = aim.get(key)
        test_disc = aim.get("test_discovery") if isinstance(aim.get("test_discovery"), dict) else {}
        for tf in test_disc.get("test_files") or []:
            tf_str = str(tf)
            if tf_str and tf_str not in target_path_set:
                neighbor_paths.add(tf_str)

    return {
        "schema_version": "specialist_context_pack.v1",
        "slice": slice_spec if isinstance(slice_spec, dict) else None,
        "target_files": target_files,
        "target_file_paths": [item["path"] for item in target_files],
        "neighbor_paths": sorted(neighbor_paths),
        "neighbor_signatures": neighbor_signatures,
        "aim_excerpt": aim_excerpt,
        "total_target_chars": sum(len(item["content"]) for item in target_files),
    }


def render_context_pack_for_prompt(context_pack: dict[str, Any]) -> str:
    """Format a specialist context pack preserving complete target/slice file bodies."""
    if not isinstance(context_pack, dict):
        return ""
    sections: list[str] = []

    slice_spec = context_pack.get("slice")
    if isinstance(slice_spec, dict) and slice_spec:
        slice_id = str(slice_spec.get("id") or "slice")
        slice_title = str(slice_spec.get("title") or slice_id)
        slice_desc = str(slice_spec.get("description") or "").strip()
        lines = [f"Active Execution Slice: {slice_id} — {slice_title}"]
        if slice_desc:
            lines.append(f"Slice scope: {slice_desc}")
        slice_files = slice_spec.get("files") or []
        if isinstance(slice_files, list) and slice_files:
            lines.append("Slice files: " + ", ".join(str(f) for f in slice_files))
        slice_ac = slice_spec.get("acceptance_criteria") or []
        if isinstance(slice_ac, list) and slice_ac:
            lines.append("Slice acceptance criteria:")
            lines.extend(f"- {c}" for c in slice_ac)
        sections.append("\n".join(lines))

    aim = context_pack.get("aim_excerpt")
    if isinstance(aim, dict) and aim:
        aim_lines = ["Workspace Application Intelligence Map (AIM):"]
        if aim.get("primary_language"):
            aim_lines.append(f"- Primary language: {aim['primary_language']}")
        if aim.get("frameworks"):
            aim_lines.append("- Frameworks: " + ", ".join(str(f) for f in aim["frameworks"]))
        if aim.get("entrypoints"):
            aim_lines.append("- Entrypoints: " + ", ".join(str(e) for e in aim["entrypoints"]))
        td = aim.get("test_discovery")
        if isinstance(td, dict) and td.get("test_command"):
            aim_lines.append(f"- Discovered test command: {td['test_command']}")
        sections.append("\n".join(aim_lines))

    neighbors = context_pack.get("neighbor_signatures") or []
    neighbor_paths = context_pack.get("neighbor_paths") or []
    if neighbors or neighbor_paths:
        n_lines = ["Related 1-hop imports/callers (signatures only):"]
        if neighbor_paths:
            n_lines.append("- Neighbor files: " + ", ".join(str(p) for p in neighbor_paths[:20]))
        for sig in neighbors[:24]:
            if isinstance(sig, dict):
                n_lines.append(
                    f"- {sig.get('path')}:{sig.get('line', 1)} [{sig.get('kind', 'symbol')}] "
                    f"{sig.get('signature') or sig.get('name')}"
                )
        sections.append("\n".join(n_lines))

    target_files = context_pack.get("target_files") or []
    if target_files:
        file_blocks = [
            "Imported project source (complete file contents; rewrite or extend these files in place):"
        ]
        for entry in target_files:
            if not isinstance(entry, dict):
                continue
            path = str(entry.get("path") or Path("inline_source.txt"))
            body = str(entry.get("content") or "")
            file_blocks.append(f"## FILE {path}\n{body.rstrip()}\n")
        sections.append("\n".join(file_blocks))

    return "\n\n".join(part for part in sections if part.strip()) + ("\n" if sections else "")
