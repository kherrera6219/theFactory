"""Sliced brownfield execution, crash-resumable checkpoints, and MIGRATION_NOTES.md generation.

Coordinates ordered per-slice coding, workspace commits, preservation gating,
PM checkpoint pauses/change orders, and migration note summaries without altering
greenfield single-shot mission execution when ``slices`` is absent or empty.
"""
from __future__ import annotations

import asyncio
import heapq
import inspect
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from .baseline_verification import evaluate_preservation_gate
from .context_pack import build_specialist_context_pack

LOGGER = logging.getLogger(__name__)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def extract_mission_slices(metadata: dict[str, Any]) -> list[dict[str, Any]]:
    """Return ordered raw slice dicts from charter, feature contract, or metadata."""
    candidates: list[Any] = []
    charter = metadata.get("mission_charter")
    if isinstance(charter, dict):
        candidates.append(charter.get("slices"))
    feature_contract = metadata.get("feature_contract")
    if isinstance(feature_contract, dict):
        candidates.append(feature_contract.get("slices"))
    candidates.append(metadata.get("slices"))
    for raw in candidates:
        if isinstance(raw, list) and any(isinstance(item, dict) for item in raw):
            return [dict(item) for item in raw if isinstance(item, dict)]
    return []


def topological_sort_slices(slices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort slices topologically by ``depends_on`` with deterministic tie-breaking.

    Unknown dependency IDs are ignored, and any cyclic remainder falls back to its
    original relative order instead of raising.
    """
    normalized: list[dict[str, Any]] = []
    id_to_index: dict[str, int] = {}
    for idx, item in enumerate(slices):
        if not isinstance(item, dict):
            continue
        copy_item = dict(item)
        slice_id = str(copy_item.get("id") or f"slice-{idx + 1}").strip()
        copy_item["id"] = slice_id
        normalized.append(copy_item)
        id_to_index.setdefault(slice_id, len(normalized) - 1)

    n = len(normalized)
    if n <= 1:
        return normalized

    in_degree = [0] * n
    dependents: list[list[int]] = [[] for _ in range(n)]
    for idx, item in enumerate(normalized):
        deps = item.get("depends_on") or []
        if not isinstance(deps, list):
            continue
        seen_deps: set[int] = set()
        for raw_dep in deps:
            dep_id = str(raw_dep or "").strip()
            dep_idx = id_to_index.get(dep_id)
            if dep_idx is None or dep_idx == idx or dep_idx in seen_deps:
                continue
            seen_deps.add(dep_idx)
            dependents[dep_idx].append(idx)
            in_degree[idx] += 1

    ready: list[int] = [i for i in range(n) if in_degree[i] == 0]
    heapq.heapify(ready)
    ordered_indices: list[int] = []
    visited = [False] * n

    while ready:
        current = heapq.heappop(ready)
        visited[current] = True
        ordered_indices.append(current)
        for nxt in dependents[current]:
            in_degree[nxt] -= 1
            if in_degree[nxt] == 0:
                heapq.heappush(ready, nxt)

    if len(ordered_indices) < n:
        LOGGER.warning("Cycle detected in slice dependencies; preserving remaining input order.")
        for idx in range(n):
            if not visited[idx]:
                ordered_indices.append(idx)

    return [normalized[idx] for idx in ordered_indices]


def _append_slice_event(
    metadata: dict[str, Any],
    *,
    event_type: str,
    agent_id: str,
    slice_id: str,
    details: dict[str, Any],
) -> None:
    events = metadata.setdefault("chain_events", [])
    if isinstance(events, list):
        events.append(
            {
                "event_type": event_type,
                "agent_id": agent_id,
                "timestamp": _utc_now(),
                "details": {"slice_id": slice_id, **details},
            }
        )


def _persist_metadata_sync(storage_module: Any, settings: Any, mission_id: str, meta: dict[str, Any]) -> None:
    if storage_module is None or settings is None:
        return
    updater = getattr(storage_module, "update_mission_metadata", None)
    if callable(updater):
        updater(settings, mission_id, meta)


def _extract_files_and_cost(result: Any) -> tuple[dict[str, str], float]:
    if not isinstance(result, dict):
        return {}, 0.0
    cost = float(result.get("cost_usd") or 0.0)
    raw_files = result.get("files")
    if isinstance(raw_files, dict):
        return {str(k): str(v) for k, v in raw_files.items()}, cost
    if isinstance(raw_files, list):
        extracted: dict[str, str] = {}
        for item in raw_files:
            if not isinstance(item, dict):
                continue
            path = str(item.get("path") or "").strip()
            content = item.get("content")
            if path and content is not None:
                extracted[path] = str(content)
        if extracted:
            return extracted, cost
    if all(isinstance(k, str) and isinstance(v, str) for k, v in result.items()):
        excluded = {"status", "output", "summary", "verdict"}
        return {k: v for k, v in result.items() if k not in excluded}, cost
    return {}, cost


def _compute_diff_stat(ws: Any) -> dict[str, Any]:
    if ws is None:
        return {"files_changed": 0}
    try:
        modified = ws.modified_files("baseline")
    except Exception:  # noqa: BLE001
        modified = []
    return {"files_changed": len(modified), "modified_files": list(modified)}


async def _run_preservation_check(
    *,
    preservation_fn: Callable[..., Any] | None,
    slice_spec: dict[str, Any],
    ws: Any,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    if preservation_fn is not None:
        res = await _maybe_await(preservation_fn(slice_spec=slice_spec, ws=ws, metadata=metadata))
        return res if isinstance(res, dict) else {"verdict": "PRESERVED"}
    if ws is not None and isinstance(metadata.get("baseline"), dict):
        allowed = metadata.get("behaviour_change_allowed")
        if not isinstance(allowed, list):
            allowed = []
        return await evaluate_preservation_gate(
            ws,
            baseline=metadata["baseline"],
            baseline_policy=str(metadata.get("baseline_policy") or "preserve"),
            behaviour_change_allowed=allowed,
        )
    return {"verdict": "PRESERVED", "reason": "no baseline attached"}


async def execute_mission_slices(
    *,
    mission_id: str,
    metadata: dict[str, Any],
    ws: Any = None,
    settings: Any = None,
    storage_module: Any = None,
    codegen_fn: Callable[..., Any] | None = None,
    harness_fn: Callable[..., Any] | None = None,
    preservation_fn: Callable[..., Any] | None = None,
    audit_fn: Callable[..., Any] | None = None,
    repair_fn: Callable[..., Any] | None = None,
    event_emitter: Callable[..., Any] | None = None,
    agent_id: str = "AGENT-PM",
    max_repair_attempts: int = 2,
) -> dict[str, Any]:
    """Execute brownfield mission slices in topological order with crash-safe checkpoints."""
    raw_slices = extract_mission_slices(metadata)
    if not raw_slices:
        return {"sliced": False, "slices_completed": [], "paused": False, "regressed": False}

    ordered_slices = topological_sort_slices(raw_slices)
    completed_list = metadata.setdefault("slices_completed", [])
    if not isinstance(completed_list, list):
        completed_list = []
        metadata["slices_completed"] = completed_list

    completed_ids = {
        str(item.get("id"))
        for item in completed_list
        if isinstance(item, dict) and item.get("id")
    }
    last_completed_id = (
        str(completed_list[-1].get("id"))
        if completed_list and isinstance(completed_list[-1], dict) and completed_list[-1].get("id")
        else None
    )

    charter = metadata.setdefault("mission_charter", {})
    if not isinstance(charter, dict):
        charter = {}
        metadata["mission_charter"] = charter

    for slice_spec in ordered_slices:
        slice_id = str(slice_spec.get("id") or "")
        slice_title = str(slice_spec.get("title") or slice_id)
        if slice_id in completed_ids:
            continue

        metadata["active_slice"] = dict(slice_spec)
        charter["checkpoint"] = {
            "last_completed_slice_id": last_completed_id,
            "active_slice_id": slice_id,
            "updated_at": _utc_now(),
        }
        start_details = {"title": slice_title, "files": list(slice_spec.get("files") or [])}
        _append_slice_event(
            metadata,
            event_type="MISSION_SLICE_STARTED",
            agent_id=agent_id,
            slice_id=slice_id,
            details=start_details,
        )
        if event_emitter is not None:
            await _maybe_await(event_emitter("MISSION_SLICE_STARTED", slice_id, start_details))

        aim = metadata.get("application_intelligence_map")
        context_pack = await asyncio.to_thread(
            build_specialist_context_pack,
            ws=ws,
            source_code=str(metadata.get("source_code") or ""),
            slice_spec=slice_spec,
            aim=aim if isinstance(aim, dict) else None,
            query=str(slice_spec.get("description") or slice_title),
        )

        generated_files: dict[str, str] = {}
        total_cost = 0.0
        if codegen_fn is not None:
            codegen_res = await _maybe_await(
                codegen_fn(
                    slice_spec=slice_spec,
                    context_pack=context_pack,
                    ws=ws,
                    metadata=metadata,
                )
            )
            generated_files, cost = _extract_files_and_cost(codegen_res)
            total_cost += cost

        if harness_fn is not None:
            harness_res = await _maybe_await(
                harness_fn(
                    slice_spec=slice_spec,
                    context_pack=context_pack,
                    ws=ws,
                    metadata=metadata,
                )
            )
            h_files, h_cost = _extract_files_and_cost(harness_res)
            generated_files.update(h_files)
            total_cost += h_cost

        commit_sha = ""
        committed_files = list(generated_files.keys()) or list(slice_spec.get("files") or [])
        if ws is not None and generated_files:
            commit_sha = await asyncio.to_thread(
                ws.write_files,
                generated_files,
                message=f"mission {mission_id}: slice {slice_id}",
            )
        elif ws is not None:
            commit_sha = str(getattr(ws, "current_head", lambda: "")() or "")

        gate = await _run_preservation_check(
            preservation_fn=preservation_fn,
            slice_spec=slice_spec,
            ws=ws,
            metadata=metadata,
        )
        verdict = str(gate.get("verdict") or "PRESERVED").upper()

        attempts = 0
        while verdict == "REGRESSED" and attempts < max_repair_attempts and repair_fn is not None:
            attempts += 1
            repair_res = await _maybe_await(
                repair_fn(
                    slice_spec=slice_spec,
                    gate_result=gate,
                    attempt=attempts,
                    ws=ws,
                    metadata=metadata,
                )
            )
            r_files, r_cost = _extract_files_and_cost(repair_res)
            total_cost += r_cost
            if r_files:
                generated_files.update(r_files)
                committed_files = list(dict.fromkeys([*committed_files, *r_files.keys()]))
                if ws is not None:
                    commit_sha = await asyncio.to_thread(
                        ws.write_files,
                        r_files,
                        message=f"mission {mission_id}: slice {slice_id} repair-{attempts}",
                    )
            gate = await _run_preservation_check(
                preservation_fn=preservation_fn,
                slice_spec=slice_spec,
                ws=ws,
                metadata=metadata,
            )
            verdict = str(gate.get("verdict") or "PRESERVED").upper()

        if audit_fn is not None and verdict != "REGRESSED":
            audit_res = await _maybe_await(
                audit_fn(
                    slice_spec=slice_spec,
                    gate_result=gate,
                    ws=ws,
                    metadata=metadata,
                )
            )
            if isinstance(audit_res, dict) and str(audit_res.get("verdict") or "").upper() == "FAIL":
                verdict = "REGRESSED"
                gate = {**gate, "audit": audit_res, "verdict": "REGRESSED"}

        if verdict == "REGRESSED":
            regress_details = {"title": slice_title, "verdict": verdict, "commit_sha": commit_sha, "gate": gate}
            _append_slice_event(
                metadata,
                event_type="MISSION_SLICE_REGRESSED",
                agent_id=agent_id,
                slice_id=slice_id,
                details=regress_details,
            )
            if event_emitter is not None:
                await _maybe_await(event_emitter("MISSION_SLICE_REGRESSED", slice_id, regress_details))
            await asyncio.to_thread(_persist_metadata_sync, storage_module, settings, mission_id, metadata)
            return {
                "sliced": True,
                "slices_completed": list(completed_list),
                "paused": False,
                "regressed": True,
                "failed_slice_id": slice_id,
                "verdict": verdict,
                "gate": gate,
            }

        diff_stat = await asyncio.to_thread(_compute_diff_stat, ws)
        record = {
            "id": slice_id,
            "title": slice_title,
            "files": committed_files,
            "commit_sha": commit_sha,
            "diff_stat": diff_stat,
            "verdict": verdict,
            "verified_at": _utc_now(),
            "cost_usd": round(total_cost, 6),
        }
        completed_list.append(record)
        completed_ids.add(slice_id)
        last_completed_id = slice_id
        charter["checkpoint"] = {
            "last_completed_slice_id": slice_id,
            "active_slice_id": None,
            "workspace_commit_sha": commit_sha,
            "updated_at": _utc_now(),
        }
        verify_details = {
            "title": slice_title,
            "verdict": verdict,
            "commit_sha": commit_sha,
            "files": committed_files,
        }
        _append_slice_event(
            metadata,
            event_type="MISSION_SLICE_VERIFIED",
            agent_id=agent_id,
            slice_id=slice_id,
            details=verify_details,
        )
        if event_emitter is not None:
            await _maybe_await(event_emitter("MISSION_SLICE_VERIFIED", slice_id, verify_details))
        await asyncio.to_thread(_persist_metadata_sync, storage_module, settings, mission_id, metadata)

        should_pause = bool(
            slice_spec.get("pause_after_slice")
            or metadata.get("pause_after_slice") == slice_id
            or metadata.get("pause_requested") is True
        )
        if should_pause:
            metadata["slice_paused"] = True
            pause_details = {"paused_after_slice_id": slice_id, "commit_sha": commit_sha}
            _append_slice_event(
                metadata,
                event_type="MISSION_SLICE_PAUSED",
                agent_id=agent_id,
                slice_id=slice_id,
                details=pause_details,
            )
            if event_emitter is not None:
                await _maybe_await(event_emitter("MISSION_SLICE_PAUSED", slice_id, pause_details))
            await asyncio.to_thread(_persist_metadata_sync, storage_module, settings, mission_id, metadata)
            return {
                "sliced": True,
                "slices_completed": list(completed_list),
                "paused": True,
                "paused_after_slice_id": slice_id,
                "regressed": False,
            }

    metadata.pop("active_slice", None)
    metadata["slice_paused"] = False
    await asyncio.to_thread(_persist_metadata_sync, storage_module, settings, mission_id, metadata)
    return {
        "sliced": True,
        "slices_completed": list(completed_list),
        "paused": False,
        "regressed": False,
    }


def apply_slice_change_order(
    metadata: dict[str, Any],
    updated_slices: list[dict[str, Any]],
    *,
    reason: str = "",
) -> dict[str, Any]:
    """Replace uncompleted slices while preserving already-completed slice history and commits."""
    completed_list = [
        item for item in (metadata.get("slices_completed") or []) if isinstance(item, dict)
    ]
    completed_ids = {str(item.get("id")) for item in completed_list if item.get("id")}
    existing_by_id = {
        str(item.get("id")): dict(item)
        for item in extract_mission_slices(metadata)
        if item.get("id")
    }

    preserved_completed: list[dict[str, Any]] = []
    for rec in completed_list:
        sid = str(rec.get("id") or "")
        if not sid:
            continue
        if sid in existing_by_id:
            preserved_completed.append(existing_by_id[sid])
        else:
            preserved_completed.append(
                {
                    "id": sid,
                    "title": rec.get("title") or sid,
                    "files": list(rec.get("files") or []),
                }
            )

    new_remaining = [
        dict(item)
        for item in updated_slices
        if isinstance(item, dict) and str(item.get("id") or "") not in completed_ids
    ]
    merged_slices = [*preserved_completed, *new_remaining]

    metadata["slices"] = merged_slices
    if isinstance(metadata.get("mission_charter"), dict):
        metadata["mission_charter"]["slices"] = [dict(s) for s in merged_slices]
    if isinstance(metadata.get("feature_contract"), dict):
        metadata["feature_contract"]["slices"] = [dict(s) for s in merged_slices]

    metadata["slice_paused"] = False
    metadata.pop("pause_requested", None)
    metadata.pop("pause_after_slice", None)

    change_orders = metadata.setdefault("slice_change_orders", [])
    if isinstance(change_orders, list):
        change_orders.append(
            {
                "applied_at": _utc_now(),
                "reason": reason,
                "preserved_slice_ids": [str(item.get("id")) for item in preserved_completed],
                "updated_remaining_ids": [str(item.get("id")) for item in new_remaining],
            }
        )
    return {
        "preserved_slice_ids": [str(item.get("id")) for item in preserved_completed],
        "updated_remaining_ids": [str(item.get("id")) for item in new_remaining],
        "total_slices": len(merged_slices),
    }


def generate_migration_notes(mission_id: str, metadata: dict[str, Any]) -> str:
    """Render structured ``MIGRATION_NOTES.md`` from mission SOW, slices, and gate reports."""
    mission_contract = metadata.get("mission_contract")
    contract = mission_contract if isinstance(mission_contract, dict) else {}
    charter = metadata.get("mission_charter")
    charter_dict = charter if isinstance(charter, dict) else {}

    title = str(contract.get("title") or charter_dict.get("title") or mission_id)
    objective = str(
        contract.get("objective")
        or charter_dict.get("objective")
        or "Automated software modification delivered by theFactory."
    )
    mission_type = str(metadata.get("mission_type") or charter_dict.get("mission_type") or "BUILD_NEW")
    target_language = str(
        metadata.get("port_target_language")
        or metadata.get("requested_target_language")
        or contract.get("target_language")
        or "python"
    )

    lines = [
        f"# Migration Notes — {title}",
        "",
        f"- **Mission ID**: `{mission_id}`",
        f"- **Mission Type**: `{mission_type}`",
        f"- **Target Language**: `{target_language}`",
        f"- **Generated At**: `{_utc_now()}`",
        "",
        "## Objective",
        "",
        objective,
        "",
    ]

    completed_slices = [
        item for item in (metadata.get("slices_completed") or []) if isinstance(item, dict)
    ]
    lines.append("## Executed Slices")
    lines.append("")
    if completed_slices:
        lines.extend(
            [
                "| Slice ID | Title | Verdict | Commit SHA | Files |",
                "|---|---|---|---|---|",
            ]
        )
        for sl in completed_slices:
            files_str = ", ".join(str(f) for f in (sl.get("files") or [])) or "-"
            sha = str(sl.get("commit_sha") or "-")[:12] or "-"
            lines.append(
                f"| `{sl.get('id')}` | {sl.get('title') or '-'} | "
                f"`{sl.get('verdict') or 'PRESERVED'}` | `{sha}` | {files_str} |"
            )
    else:
        lines.append("Executed as a single-shot delivery (no explicit slice breakdown).")
    lines.append("")

    runtime_qc = metadata.get("runtime_qc_report")
    preservation = runtime_qc.get("preservation_gate") if isinstance(runtime_qc, dict) else None
    lines.append("## Behaviour Preservation & Verification")
    lines.append("")
    if isinstance(preservation, dict) and preservation:
        lines.append(f"- **Preservation Verdict**: `{preservation.get('verdict', 'UNKNOWN')}`")
        lines.append(f"- **Baseline Regressions**: `{len(preservation.get('regressions') or [])}`")
        if preservation.get("reason"):
            lines.append(f"- **Notes**: {preservation.get('reason')}")
    else:
        lines.append("- **Preservation Verdict**: Not applicable or no brownfield baseline attached.")

    eq_report = metadata.get("equivalence_report")
    if isinstance(eq_report, dict) and eq_report:
        lines.append(f"- **Equivalence Status**: `{eq_report.get('status', 'unknown')}`")

    lines.append("")
    lines.append("## Dependencies & Supply Chain")
    lines.append("")
    sbom_delta = metadata.get("sbom_delta")
    if isinstance(sbom_delta, dict) and sbom_delta:
        lines.append(
            f"- **SBOM Delta**: added={len(sbom_delta.get('added') or [])}, "
            f"removed={len(sbom_delta.get('removed') or [])}"
        )
    else:
        lines.append("- **SBOM Delta**: No dependency manifest changes recorded.")

    pr_res = metadata.get("github_pr_result")
    if isinstance(pr_res, dict) and pr_res.get("pr_url"):
        lines.extend(
            [
                "",
                "## Pull Request Delivery",
                "",
                f"- **Pull Request**: {pr_res.get('pr_url')}",
            ]
        )

    lines.append("")
    return "\n".join(lines)
