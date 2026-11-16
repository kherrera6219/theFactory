"""Opt-in GitHub Pull Request delivery exporter using vaulted credentials.

Pull request creation is disabled unless ``metadata["github_pr_export"]["enabled"]``
is explicitly True. Fine-grained ``github_token`` secrets must reside in
``shared_runtime.mission_vault`` and are strictly forbidden in Postgres
``missions.metadata_json``.
"""
from __future__ import annotations

import inspect
import logging
from datetime import UTC, datetime
from typing import Any

import httpx

from shared_runtime.mission_vault import load_vault

LOGGER = logging.getLogger(__name__)

_FORBIDDEN_TOKEN_KEYS: frozenset[str] = frozenset(
    {
        "github_token",
        "gh_token",
        "personal_access_token",
        "access_token",
        "token",
    }
)


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _contains_token_key(mapping: dict[str, Any]) -> str | None:
    for key, value in mapping.items():
        if str(key).lower() in _FORBIDDEN_TOKEN_KEYS and value:
            return str(key)
    return None


def validate_no_plaintext_github_token(metadata: dict[str, Any]) -> None:
    """Reject metadata containing plaintext GitHub tokens outside mission_vault."""
    top_hit = _contains_token_key(metadata)
    if top_hit is not None:
        raise ValueError(
            f"Plaintext GitHub credential '{top_hit}' in metadata is forbidden; "
            "store github_token in mission_vault instead."
        )
    export_cfg = metadata.get("github_pr_export")
    if isinstance(export_cfg, dict):
        nested_hit = _contains_token_key(export_cfg)
        if nested_hit is not None:
            raise ValueError(
                f"Plaintext GitHub credential '{nested_hit}' in github_pr_export is forbidden; "
                "store github_token in mission_vault instead."
            )


def scrub_github_token_from_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of ``metadata`` with any plaintext GitHub token keys removed."""
    cleaned = {
        k: v
        for k, v in metadata.items()
        if str(k).lower() not in _FORBIDDEN_TOKEN_KEYS
    }
    export_cfg = cleaned.get("github_pr_export")
    if isinstance(export_cfg, dict):
        cleaned["github_pr_export"] = {
            k: v
            for k, v in export_cfg.items()
            if str(k).lower() not in _FORBIDDEN_TOKEN_KEYS
        }
    return cleaned


def build_github_pr_payload(
    mission_id: str,
    metadata: dict[str, Any],
    *,
    head_branch: str,
    base_branch: str = "main",
) -> dict[str, Any]:
    """Construct the GitHub REST API pull request payload from mission evidence."""
    export_cfg = metadata.get("github_pr_export")
    cfg = export_cfg if isinstance(export_cfg, dict) else {}
    contract = metadata.get("mission_contract")
    contract_dict = contract if isinstance(contract, dict) else {}

    title = str(
        cfg.get("title")
        or contract_dict.get("title")
        or f"theFactory delivery for mission {mission_id}"
    )
    objective = str(
        contract_dict.get("objective") or "Automated software change delivered by theFactory."
    )

    body_lines = [
        f"## Mission `{mission_id}`",
        "",
        objective,
        "",
    ]

    completed_slices = [
        item for item in (metadata.get("slices_completed") or []) if isinstance(item, dict)
    ]
    if completed_slices:
        body_lines.extend(
            [
                "### Verified Slices",
                "",
                "| Slice ID | Title | Commit SHA | Verdict |",
                "|---|---|---|---|",
            ]
        )
        for sl in completed_slices:
            sha = str(sl.get("commit_sha") or "-")[:12] or "-"
            body_lines.append(
                f"| `{sl.get('id')}` | {sl.get('title') or '-'} | `{sha}` | "
                f"`{sl.get('verdict') or 'PRESERVED'}` |"
            )
        body_lines.append("")

    baseline = metadata.get("baseline")
    runtime_qc = metadata.get("runtime_qc_report")
    preservation = runtime_qc.get("preservation_gate") if isinstance(runtime_qc, dict) else None
    body_lines.append("### Verification Summary")
    body_lines.append("")
    if isinstance(baseline, dict) and baseline.get("test_command"):
        body_lines.append(
            f"- **Baseline Tests**: command=`{baseline.get('test_command')}`, "
            f"passed={baseline.get('passed_count', 0)}, failed={baseline.get('failed_count', 0)}"
        )
    if isinstance(preservation, dict) and preservation:
        body_lines.append(f"- **Preservation Gate**: `{preservation.get('verdict', 'UNKNOWN')}`")

    eq_report = metadata.get("equivalence_report")
    if isinstance(eq_report, dict) and eq_report.get("status"):
        body_lines.append(f"- **Equivalence Report**: `{eq_report.get('status')}`")

    sec_report = metadata.get("security_compliance_report")
    if isinstance(sec_report, dict) and sec_report.get("status"):
        body_lines.append(f"- **Security Compliance**: `{sec_report.get('status')}`")

    body_lines.extend(
        [
            "",
            "_Generated by theFactory (Holy Grail Refinery). See `MIGRATION_NOTES.md` for details._",
        ]
    )

    return {
        "title": title,
        "head": head_branch,
        "base": base_branch,
        "body": "\n".join(body_lines),
        "draft": bool(cfg.get("draft", False)),
    }


async def export_mission_as_github_pr(
    mission_id: str,
    metadata: dict[str, Any],
    *,
    redis_client: Any = None,
    vault_loader: Any = None,
    http_client: Any = None,
    api_base_url: str = "https://api.github.com",
) -> dict[str, Any]:
    """Create a GitHub PR when explicitly opted in, loading ``github_token`` from vault only."""
    cfg = metadata.get("github_pr_export")
    if not isinstance(cfg, dict) or not cfg.get("enabled"):
        return {
            "exported": False,
            "skipped": True,
            "reason": "github_pr_export not enabled",
        }

    validate_no_plaintext_github_token(metadata)

    repo = str(cfg.get("repo") or "").strip()
    if not repo or "/" not in repo:
        result = {
            "exported": False,
            "skipped": False,
            "status": "error",
            "reason": "invalid or missing target repo (expected owner/repo)",
        }
        metadata["github_pr_result"] = result
        return result

    loader = vault_loader or load_vault
    vault = await _maybe_await(loader(redis_client, mission_id))
    vault_dict = vault if isinstance(vault, dict) else {}
    token = str(
        vault_dict.get("github_token")
        or vault_dict.get("GITHUB_TOKEN")
        or vault_dict.get("gh_token")
        or ""
    ).strip()
    if not token:
        result = {
            "exported": False,
            "skipped": False,
            "status": "error",
            "reason": "github_token missing from mission vault",
        }
        metadata["github_pr_result"] = result
        return result

    head_branch = str(
        cfg.get("head_branch")
        or metadata.get("workspace_branch")
        or f"thefactory/mission-{mission_id[:16]}"
    )
    base_branch = str(cfg.get("base_branch") or "main")
    payload = build_github_pr_payload(
        mission_id,
        metadata,
        head_branch=head_branch,
        base_branch=base_branch,
    )

    url = f"{api_base_url.rstrip('/')}/repos/{repo}/pulls"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    try:
        if http_client is not None:
            response = await _maybe_await(http_client.post(url, json=payload, headers=headers))
        else:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(url, json=payload, headers=headers)
    except Exception as exc:  # noqa: BLE001 - never include auth token in logs or metadata
        LOGGER.warning("GitHub PR creation failed for %s: %s", mission_id, type(exc).__name__)
        result = {
            "exported": False,
            "skipped": False,
            "status": "error",
            "repo": repo,
            "head_branch": head_branch,
            "base_branch": base_branch,
            "reason": f"http_error:{type(exc).__name__}",
        }
        metadata["github_pr_result"] = result
        return result

    status_code = int(getattr(response, "status_code", 0) or 0)
    try:
        body = response.json()
    except Exception:  # noqa: BLE001
        body = {}

    if status_code not in (200, 201) or not isinstance(body, dict):
        result = {
            "exported": False,
            "skipped": False,
            "status": "error",
            "http_status": status_code,
            "repo": repo,
            "head_branch": head_branch,
            "base_branch": base_branch,
            "reason": str(body.get("message") or f"github_api_status_{status_code}")
            if isinstance(body, dict)
            else f"github_api_status_{status_code}",
        }
        metadata["github_pr_result"] = result
        return result

    result = {
        "exported": True,
        "skipped": False,
        "status": "created",
        "repo": repo,
        "head_branch": head_branch,
        "base_branch": base_branch,
        "pr_number": body.get("number"),
        "pr_url": str(body.get("html_url") or ""),
        "created_at": datetime.now(UTC).isoformat(),
    }
    metadata["github_pr_result"] = result
    return result
