"""Persist approved SOW snapshots outside the 4096-byte launch metadata bag."""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .sow_estimator import estimate_change_order, estimate_mission_cost


def _sow_root(settings: Any) -> Path:
    root = Path(getattr(settings, "delivery_dir", None) or "output") / ".sow"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_sow_path(settings: Any, sow_id: str) -> Path | None:
    """Return a SOW path only when it stays inside the SOW root.

    ``sow_id`` is caller-supplied. Allow only ``[A-Za-z0-9_-]``, then
    normalize and require the resolved path to be a child of the root.
    """
    raw = str(sow_id)
    safe = "".join(ch for ch in raw if ch.isalnum() or ch in {"-", "_"})
    if not safe or safe != raw:
        return None
    root = os.path.abspath(str(_sow_root(settings)))
    fullpath = os.path.normpath(os.path.join(root, f"{safe}.json"))
    if not fullpath.startswith(root + os.sep):
        return None
    return Path(fullpath)


def sow_digest(document: dict[str, Any]) -> str:
    payload = json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def validate_sow_for_accept(
    feature_contract: dict[str, Any],
    *,
    unpriced_ack: bool = False,
) -> list[str]:
    """Return error strings. Empty list means the SOW may be accepted."""
    errors: list[str] = []
    out_of_scope = feature_contract.get("out_of_scope") or []
    if not any(str(item).strip() for item in out_of_scope):
        errors.append("out_of_scope is required")
    deliverables = feature_contract.get("deliverables") or []
    if not any(str(item).strip() if not isinstance(item, dict) else str(item.get("name") or "").strip() for item in deliverables):
        errors.append("at least one deliverable is required")
    estimate = feature_contract.get("cost_estimate") if isinstance(feature_contract.get("cost_estimate"), dict) else {}
    if not estimate.get("pricing_known") and not unpriced_ack:
        errors.append("cost_estimate is missing or unpriced; pass unpriced_ack to proceed anyway")
    return errors


def attach_cost_estimate(
    feature_contract: dict[str, Any],
    *,
    mission_type: str,
    provider: str | None = None,
    model: str | None = None,
    change_order: bool = False,
    prior_cost: dict[str, Any] | None = None,
) -> dict[str, Any]:
    contract = dict(feature_contract)
    resolved_type = mission_type or str(contract.get("engagement_type") or "BUILD_NEW")
    complexity = str(contract.get("estimated_complexity") or "medium")
    resolved_provider = str(provider or contract.get("model_provider") or "gemini")
    resolved_model = str(model or contract.get("model") or "gemini-3.7-flash")
    if change_order:
        estimate = estimate_change_order(
            prior=prior_cost,
            mission_type=resolved_type,
            complexity=complexity,
            provider=resolved_provider,
            model=resolved_model,
        )
    else:
        estimate = estimate_mission_cost(
            mission_type=resolved_type,
            complexity=complexity,
            provider=resolved_provider,
            model=resolved_model,
        )
    contract["engagement_type"] = str(resolved_type)
    contract["cost_estimate"] = estimate
    contract["timeline"] = {
        "estimated_minutes_low": estimate["estimated_minutes_low"],
        "estimated_minutes_high": estimate["estimated_minutes_high"],
    }
    return contract


def save_approved_sow(
    settings: Any,
    feature_contract: dict[str, Any],
    *,
    approved_by: str = "operator",
    unpriced_ack: bool = False,
) -> dict[str, Any]:
    errors = validate_sow_for_accept(feature_contract, unpriced_ack=unpriced_ack)
    if errors:
        raise ValueError("; ".join(errors))
    sow_id = f"sow-{uuid.uuid4()}"
    document = {
        "sow_id": sow_id,
        "feature_contract": feature_contract,
        "approved_at": datetime.now(UTC).isoformat(),
        "approved_by": approved_by,
        "digest": "",
    }
    document["digest"] = sow_digest(document["feature_contract"])
    path = _safe_sow_path(settings, sow_id)
    if path is None:
        raise ValueError("refusing to write sow outside the sow root")
    path.write_text(json.dumps(document, indent=2), encoding="utf-8")
    return document


def check_mission_spend_cap(
    *,
    actual_usd: float | None,
    cap_usd: float | None,
    warn_ratio: float = 0.8,
) -> str:
    """Return ``ok``, ``warn``, or ``pause``. Pure."""
    if cap_usd is None or actual_usd is None:
        return "ok"
    if actual_usd >= cap_usd:
        return "pause"
    if actual_usd >= cap_usd * warn_ratio:
        return "warn"
    return "ok"


def load_approved_sow(settings: Any, sow_id: str) -> dict[str, Any] | None:
    path = _safe_sow_path(settings, sow_id)
    if path is None or not path.is_file():
        return None
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return loaded if isinstance(loaded, dict) else None
