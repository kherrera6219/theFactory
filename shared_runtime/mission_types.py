"""Official mission-type vocabulary and alias normalization.

Unknown strings must not become BUILD_NEW. An omitted or empty value is the
only case that defaults to BUILD_NEW.
"""

from __future__ import annotations

from typing import Any

OFFICIAL_MISSION_TYPES = frozenset(
    {
        "BUILD_NEW",
        "IMPORT_MODERNIZE",
        "PORT",
        "DEBUG_REPAIR",
        "SECURITY_HARDEN",
        "REDUCE_DEPENDENCIES",
        "RUN_QC",
        "ARCHITECTURE_DOCS",
        "ANALYZE_ONLY",
        "SELF_ANALYZE",
    }
)

# Keys are already uppercased, hyphen/space folded to underscore.
MISSION_TYPE_ALIASES: dict[str, str] = {
    "": "BUILD_NEW",
    "BUILD": "BUILD_NEW",
    "BUILD_NEW": "BUILD_NEW",
    "CREATE": "BUILD_NEW",
    "FEATURE": "BUILD_NEW",
    "FULL_BUILD": "BUILD_NEW",
    "IMPLEMENTATION": "BUILD_NEW",
    "NEW": "BUILD_NEW",
    "IMPORT_MODERNIZE": "IMPORT_MODERNIZE",
    "MODERNIZE": "IMPORT_MODERNIZE",
    "UPDATE": "IMPORT_MODERNIZE",
    "ADD_FEATURE": "IMPORT_MODERNIZE",
    "REFACTOR": "IMPORT_MODERNIZE",
    "PORT": "PORT",
    "DEBUG": "DEBUG_REPAIR",
    "DEBUG_REPAIR": "DEBUG_REPAIR",
    "REPAIR": "DEBUG_REPAIR",
    "SECURITY": "SECURITY_HARDEN",
    "SECURITY_HARDEN": "SECURITY_HARDEN",
    "REDUCE_DEPENDENCIES": "REDUCE_DEPENDENCIES",
    "DEPENDENCY_REDUCTION": "REDUCE_DEPENDENCIES",
    "RUN_QC": "RUN_QC",
    "QC": "RUN_QC",
    "ARCHITECTURE": "ARCHITECTURE_DOCS",
    "ARCHITECTURE_DOCS": "ARCHITECTURE_DOCS",
    "ANALYZE": "ANALYZE_ONLY",
    "ANALYZE_ONLY": "ANALYZE_ONLY",
    "ANALYSIS": "ANALYZE_ONLY",
    "SELF_ANALYZE": "SELF_ANALYZE",
}

OFFICIAL_OUTPUT_MODES = frozenset(
    {
        "ANALYZE_ONLY",
        "PLAN_ONLY",
        "PATCH_PROPOSAL",
        "APPLY_PATCH",
        "FULL_BUILD",
        "DEPENDENCY_REDUCTION",
        "RUN_QC",
        "FULL_TRANSFORMATION",
    }
)

OFFICIAL_DEPTH_MODES = frozenset(
    {
        "SPRINT",
        "STANDARD",
        "PRODUCTION",
        "REGULATED",
        "AUTONOMOUS_LONG_RUN",
    }
)

OFFICIAL_DATA_CLASSIFICATIONS = frozenset(
    {
        "TIER_0_PUBLIC",
        "TIER_1_INTERNAL",
        "TIER_2_SENSITIVE",
        "TIER_3_REGULATED",
    }
)


class UnknownMissionTypeError(ValueError):
    """Raised when a mission type is neither official nor a known alias."""


def _fold_token(value: Any) -> str:
    return str(value or "").strip().upper().replace("-", "_").replace(" ", "_")


def normalize_mission_type(value: Any, *, default_if_empty: str = "BUILD_NEW") -> str:
    """Return an official mission type or raise ``UnknownMissionTypeError``.

    Empty / omitted values become ``default_if_empty`` (BUILD_NEW). A non-empty
    unknown string is a client error, not a silent BUILD_NEW.
    """
    folded = _fold_token(value)
    if not folded:
        return default_if_empty
    mapped = MISSION_TYPE_ALIASES.get(folded)
    if mapped is None:
        raise UnknownMissionTypeError(
            f"unknown mission_type {value!r}; expected an official type or alias"
        )
    return mapped


def normalize_output_mode(value: Any, *, default_if_empty: str = "FULL_BUILD") -> str:
    """Return an official output mode or raise ``UnknownMissionTypeError``.

    Empty / omitted values become ``default_if_empty`` (FULL_BUILD). Unlike
    mission types these have no alias table, so any non-empty unrecognised
    value is a client error.
    """
    folded = _fold_token(value)
    if not folded:
        return default_if_empty
    if folded not in OFFICIAL_OUTPUT_MODES:
        raise UnknownMissionTypeError(f"unknown output_mode {value!r}")
    return folded


def normalize_depth_mode(value: Any, *, default_if_empty: str = "STANDARD") -> str:
    """Return an official depth mode or raise ``UnknownMissionTypeError``.

    Empty / omitted values become ``default_if_empty`` (STANDARD).
    """
    folded = _fold_token(value)
    if not folded:
        return default_if_empty
    if folded not in OFFICIAL_DEPTH_MODES:
        raise UnknownMissionTypeError(f"unknown depth_mode {value!r}")
    return folded


def normalize_data_classification(
    value: Any, *, default_if_empty: str = "TIER_1_INTERNAL"
) -> str:
    """Return an official data classification or raise ``UnknownMissionTypeError``.

    Empty / omitted values become ``default_if_empty`` (TIER_1_INTERNAL). An
    unrecognised classification must never be silently downgraded to the
    default -- it decides how the mission's data may be handled.
    """
    folded = _fold_token(value)
    if not folded:
        return default_if_empty
    if folded not in OFFICIAL_DATA_CLASSIFICATIONS:
        raise UnknownMissionTypeError(f"unknown data_classification {value!r}")
    return folded
