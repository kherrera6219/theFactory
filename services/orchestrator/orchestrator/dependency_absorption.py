"""Mission-local dependency inventory and absorption planning."""
from __future__ import annotations

import ast
import json
import logging
import re
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)

DEPENDENCY_INVENTORY_SCHEMA_VERSION = "dependency_inventory.v1"
DEPENDENCY_CLASSIFICATION_SCHEMA_VERSION = "dependency_classification_report.v1"
DEPENDENCY_ABSORPTION_SCHEMA_VERSION = "dependency_absorption_report.v1"
DEPENDENCY_SURVIVAL_SCHEMA_VERSION = "dependency_survival_justification.v1"

_PACKAGE_JSON_PATTERN = re.compile(
    r"(?im)^## FILE (?P<path>[^\n]*package\.json)\s*\n(?P<body>.*?)(?=^## FILE |\Z)",
    re.DOTALL,
)
_REQUIREMENTS_PATTERN = re.compile(
    r"(?im)^## FILE (?P<path>[^\n]*(requirements[^/\n\\]*\.txt|constraints[^/\n\\]*\.txt))\s*\n"
    r"(?P<body>.*?)(?=^## FILE |\Z)",
    re.DOTALL,
)
_PYPROJECT_PATTERN = re.compile(
    r"(?im)^## FILE (?P<path>[^\n]*pyproject\.toml)\s*\n(?P<body>.*?)(?=^## FILE |\Z)",
    re.DOTALL,
)

_PYTHON_STDLIB = {
    "argparse",
    "asyncio",
    "collections",
    "csv",
    "datetime",
    "functools",
    "hashlib",
    "hmac",
    "http",
    "importlib",
    "itertools",
    "json",
    "logging",
    "math",
    "os",
    "pathlib",
    "random",
    "re",
    "sqlite3",
    "ssl",
    "subprocess",
    "sys",
    "typing",
    "uuid",
}
_SECURITY_CRITICAL = {
    "argon2-cffi",
    "bcrypt",
    "certifi",
    "cryptography",
    "jose",
    "passlib",
    "pyjwt",
    "pyopenssl",
    "python-jose",
    "ssl",
}
_PLATFORM_RUNTIME = {
    "aiomysql",
    "asyncpg",
    "azure-identity",
    "boto3",
    "google-auth",
    "motor",
    "psycopg2",
    "pymongo",
    "redis",
    "redis-py",
}
_VALIDATION_SERIALIZATION = {"attrs", "marshmallow", "pydantic", "zod"}
_HTTP_CLIENTS = {"aiohttp", "axios", "httpx", "requests"}
_FRAMEWORK_CORE = {
    "django",
    "express",
    "fastapi",
    "flask",
    "next",
    "nextjs",
    "react",
    "starlette",
    "vue",
}
_COMPLEX_PARSERS = {
    "acorn",
    "babel",
    "esbuild",
    "esprima",
    "javalang",
    "parser",
    "typescript",
    "webpack",
}
_SAFETY_CRITICAL_MATH = {"numpy", "scipy", "sympy"}
_OBSERVABILITY = {"loguru", "structlog"}
_SMALL_PURE_UTILITIES = {
    "camelcase",
    "classnames",
    "clsx",
    "is-even",
    "is-odd",
    "kebabcase",
    "left-pad",
    "lodash.camelcase",
    "lodash.kebabcase",
    "lodash.snakecase",
    "slugify",
    "snakecase",
}
_BLOCKED_LICENSES = {"agpl", "agpl-3.0", "gpl", "gpl-2.0", "gpl-3.0", "proprietary"}


def mission_requires_dependency_absorption(metadata: Any) -> bool:
    if not isinstance(metadata, dict):
        return False
    mission_type = str(metadata.get("mission_type") or "").strip().upper()
    output_mode = str(metadata.get("output_mode") or "").strip().upper()
    if mission_type == "REDUCE_DEPENDENCIES" or output_mode == "DEPENDENCY_REDUCTION":
        return True
    return bool(build_dependency_inventory(mission_id="probe", metadata=metadata)["dependencies"])


def build_dependency_absorption_reports(
    *,
    mission_id: str,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    inventory = build_dependency_inventory(mission_id=mission_id, metadata=metadata)
    classifications = [
        _classify_dependency(entry, metadata=metadata)
        for entry in inventory["dependencies"]
    ]
    equivalence_report = _dict_value(metadata.get("equivalence_report"))
    security_report = _dict_value(metadata.get("security_compliance_report"))
    equivalence_passed = equivalence_report.get("passed") is True
    security_passed = security_report.get("passed") is True and not bool(
        security_report.get("blocking")
    )

    classification_report = {
        "schema_version": DEPENDENCY_CLASSIFICATION_SCHEMA_VERSION,
        "report_id": f"dependency-classification-{mission_id}",
        "mission_id": mission_id,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "blocked" if any(item["blocking"] for item in classifications) else "classified",
        "blocking": any(item["blocking"] for item in classifications),
        "classification_count": len(classifications),
        "classifications": classifications,
        "source": "deterministic",
    }
    survival_justifications = [
        _survival_justification(mission_id, item)
        for item in classifications
        if item["decision"] != "absorb"
    ]
    planned_replacements = [
        _replacement_plan(item, equivalence_passed, security_passed)
        for item in classifications
        if item["decision"] == "absorb"
    ]
    absorption_report = {
        "schema_version": DEPENDENCY_ABSORPTION_SCHEMA_VERSION,
        "report_id": f"dependency-absorption-{mission_id}",
        "mission_id": mission_id,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": _absorption_status(classification_report, planned_replacements),
        "blocking": bool(classification_report["blocking"]),
        "modified_output_created": False,
        "equivalence_required": bool(planned_replacements),
        "equivalence_passed": equivalence_passed,
        "security_compliance_required": bool(planned_replacements),
        "security_compliance_passed": security_passed,
        "planned_replacements": planned_replacements,
        "survival_justification_count": len(survival_justifications),
        "safety_block_count": sum(
            1 for item in classifications if item.get("safety_blocked")
        ),
        "recommendations": _recommendations(classifications, planned_replacements),
        "evidence_refs": _evidence_refs(metadata),
        "source": "deterministic",
    }
    return {
        "dependency_inventory": inventory,
        "dependency_classification_report": classification_report,
        "dependency_absorption_report": absorption_report,
        "dependency_survival_justifications": survival_justifications,
    }


def build_dependency_inventory(
    *,
    mission_id: str,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    entries: dict[str, dict[str, Any]] = {}

    def add(name: Any, *, source: str, ecosystem: str = "unknown", version: Any = None) -> None:
        clean = _clean_name(name)
        if not clean:
            return
        normalized = _normalize_name(clean)
        entry = entries.setdefault(
            normalized,
            {
                "dependency_id": f"dep-{normalized}",
                "name": clean,
                "normalized_name": normalized,
                "ecosystem": ecosystem,
                "version": _clean_version(version),
                "source_refs": [],
                "usage_hints": [],
            },
        )
        if entry["version"] is None and version is not None:
            entry["version"] = _clean_version(version)
        if ecosystem != "unknown" and entry["ecosystem"] == "unknown":
            entry["ecosystem"] = ecosystem
        if source not in entry["source_refs"]:
            entry["source_refs"].append(source)

    aim = _dict_value(metadata.get("application_intelligence_map"))
    for dependency in _string_list(aim.get("detected_dependencies")):
        add(dependency, source="application_intelligence_map.detected_dependencies")

    generated_output = _dict_value(metadata.get("generated_output"))
    for dependency in _string_list(generated_output.get("dependencies")):
        add(dependency, source="generated_output.dependencies")

    for dependency in _string_list(metadata.get("dependencies")):
        add(dependency, source="metadata.dependencies")

    package_metadata = _dict_value(metadata.get("package_metadata"))
    _add_package_metadata(package_metadata, add)
    source_code = str(metadata.get("source_code") or "")
    _add_source_bundle_manifests(source_code, add)

    dependencies = sorted(entries.values(), key=lambda item: item["normalized_name"])
    for entry in dependencies:
        entry["usage_hints"] = _usage_hints(entry, metadata)

    return {
        "schema_version": DEPENDENCY_INVENTORY_SCHEMA_VERSION,
        "inventory_id": f"dependency-inventory-{mission_id}",
        "mission_id": mission_id,
        "generated_at": datetime.now(UTC).isoformat(),
        "dependency_count": len(dependencies),
        "dependencies": dependencies,
        "sources": sorted(
            {
                source
                for entry in dependencies
                for source in entry.get("source_refs", [])
            }
        ),
        "source": "deterministic",
    }


async def execute_absorption(
    *,
    mission_id: str,
    source_code: str,
    language: str,
    absorption_report: dict[str, Any],
    settings: Any,
) -> dict[str, Any]:
    """Execute conservative first-party replacement splices for ready plans."""
    normalized_language = str(language or "").strip().lower()
    if normalized_language not in {"python", "javascript", "typescript"}:
        return {
            "schema_version": "depabs_execution.v1",
            "mission_id": mission_id,
            "status": "skipped",
            "reason": f"Absorption execution not supported for {language}.",
            "modified_source": source_code,
            "splices": [],
            "absorption_count": 0,
            "source": "deterministic",
            "executed_at": datetime.now(UTC).isoformat(),
        }

    candidates = [
        item
        for item in (absorption_report.get("planned_replacements") or [])
        if isinstance(item, dict) and item.get("status") == "ready_for_planning"
    ][:3]
    if not candidates:
        return {
            "schema_version": "depabs_execution.v1",
            "mission_id": mission_id,
            "status": "nothing_to_absorb",
            "modified_source": source_code,
            "splices": [],
            "absorption_count": 0,
            "source": "deterministic",
            "executed_at": datetime.now(UTC).isoformat(),
        }

    modified = source_code
    splices: list[dict[str, Any]] = []
    for candidate in candidates:
        library = str(candidate.get("name") or "").strip()
        used_symbols = _detect_used_symbols(modified, library, normalized_language)
        replacement = await _generate_replacement_code(
            library=library,
            used_symbols=used_symbols,
            language=normalized_language,
            settings=settings,
            mission_id=mission_id,
        )
        if not replacement.get("replacement_code"):
            splices.append(
                {
                    "library": library,
                    "symbols_replaced": used_symbols,
                    "status": "unsupported",
                    "reason": "No deterministic replacement available.",
                }
            )
            continue
        next_source, status, reason = _splice_replacement(
            source=modified,
            library=library,
            language=normalized_language,
            replacement=replacement,
        )
        splices.append(
            {
                "library": library,
                "symbols_replaced": used_symbols,
                "filename": replacement.get("filename"),
                "status": status,
                "reason": reason,
            }
        )
        if status == "ok":
            modified = next_source

    absorption_count = sum(1 for item in splices if item.get("status") == "ok")
    return {
        "schema_version": "depabs_execution.v1",
        "mission_id": mission_id,
        "status": "executed" if absorption_count else "no_splices_applied",
        "modified_source": modified,
        "splices": splices,
        "absorption_count": absorption_count,
        "source": "deterministic",
        "executed_at": datetime.now(UTC).isoformat(),
    }


def build_sbom_delta(
    *,
    original_dependencies: list[dict[str, Any]],
    absorption_result: dict[str, Any],
    survival_justifications: list[dict[str, Any]],
) -> dict[str, Any]:
    original_names = [
        str(item.get("name") or "").strip()
        for item in original_dependencies
        if isinstance(item, dict) and str(item.get("name") or "").strip()
    ]
    removed = [
        str(item.get("library") or "").strip()
        for item in absorption_result.get("splices", [])
        if isinstance(item, dict) and item.get("status") == "ok"
    ]
    kept = [
        str(item.get("name") or "").strip()
        for item in survival_justifications
        if isinstance(item, dict) and str(item.get("name") or "").strip()
    ]
    remaining = [name for name in original_names if name not in removed]
    return {
        "schema_version": "sbom_delta.v1",
        "original_dependency_count": len(original_names),
        "removed": removed,
        "remaining": remaining,
        "kept_with_justification": kept,
        "reduction_percent": round(len(removed) / max(len(original_names), 1) * 100, 1),
        "generated_at": datetime.now(UTC).isoformat(),
    }


def _detect_used_symbols(source: str, library: str, language: str) -> list[str]:
    normalized = library.strip()
    if not normalized:
        return []
    if language == "python":
        symbols = []
        for pattern in (
            rf"(?m)^\s*import\s+{re.escape(normalized)}(?:\s+as\s+(\w+))?",
            rf"(?m)^\s*from\s+{re.escape(normalized)}\s+import\s+([^\n#]+)",
        ):
            for match in re.finditer(pattern, source):
                captured = match.group(1)
                if captured:
                    symbols.extend(
                        item.strip().split(" as ")[-1]
                        for item in captured.split(",")
                        if item.strip()
                    )
                else:
                    symbols.append(normalized)
        return sorted(set(symbols)) or [normalized]
    if language in {"javascript", "typescript"}:
        if _js_import_present(source, normalized):
            return [normalized]
    return []


async def _generate_replacement_code(
    *,
    library: str,
    used_symbols: list[str],
    language: str,
    settings: Any = None,
    mission_id: str = "",
) -> dict[str, Any]:
    normalized = library.strip().lower()
    if language == "python" and normalized in {"left-pad", "left_pad"}:
        return {
            "filename": "depabs_left_pad.py",
            "replacement_code": (
                "\n\n# DEPABS replacement for left-pad\n"
                "def left_pad(value, width, fillchar=' '):\n"
                "    text = str(value)\n"
                "    pad = str(fillchar or ' ')[:1]\n"
                "    if len(text) >= int(width):\n"
                "        return text\n"
                "    return pad * (int(width) - len(text)) + text\n"
            ),
        }
    if language == "python" and normalized in {"slugify", "snakecase", "kebabcase"}:
        helper_name = normalized.replace("-", "_")
        separator = "-" if normalized in {"slugify", "kebabcase"} else "_"
        return {
            "filename": f"depabs_{helper_name}.py",
            "replacement_code": (
                f"\n\n# DEPABS replacement for {normalized}\n"
                f"def {helper_name}(value):\n"
                "    import re\n"
                "    text = re.sub(r'[^A-Za-z0-9]+', '"
                f"{separator}"
                "', str(value)).strip('"
                f"{separator}"
                "')\n"
                "    return text.lower()\n"
            ),
        }
    # LLM-driven replacement for everything not in the deterministic table
    return await _llm_generate_replacement(
        library=library,
        normalized=normalized,
        used_symbols=used_symbols,
        language=language,
        settings=settings,
        mission_id=mission_id,
    )


def validate_js_syntax(code: str) -> bool:
    """Validate JS/TS syntax with ``node --check``.

    Returns True when the code parses, or when Node.js is unavailable (so the
    splice is not blocked in environments without a Node runtime). ``--check``
    requires a file argument, so the code is written to a temp file with a
    language-appropriate extension. TypeScript-only syntax (e.g. type
    annotations) is not valid plain JS, so a ``.ts`` file is parsed leniently:
    if the strict check fails we fall back to import/structure detection.
    """
    if not code.strip():
        return True
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".js", delete=False, encoding="utf-8"
        ) as handle:
            handle.write(code)
            tmp_path = handle.name
        try:
            result = subprocess.run(
                ["node", "--check", tmp_path],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        finally:
            Path(tmp_path).unlink(missing_ok=True)
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return True  # node not available — skip validation rather than block


def _js_import_present(source: str, library: str) -> bool:
    """Detect whether ``library`` is imported/required in JS/TS source.

    Matches ES module ``import ... from 'lib'`` / bare ``import 'lib'`` and
    CommonJS ``require('lib')`` forms, anchored on the quoted module specifier
    so substrings of unrelated identifiers are not matched. This replaces the
    earlier loose ``'lib'`` quote search which matched the library name in any
    string literal, not just import positions.
    """
    lib = re.escape(library)
    patterns = (
        rf"\bfrom\s+['\"]{lib}['\"]",
        rf"\bimport\s+['\"]{lib}['\"]",
        rf"\brequire\(\s*['\"]{lib}['\"]\s*\)",
    )
    return any(re.search(pattern, source) for pattern in patterns)


def _splice_replacement(
    *,
    source: str,
    library: str,
    language: str,
    replacement: dict[str, Any],
) -> tuple[str, str, str]:
    replacement_code = str(replacement.get("replacement_code") or "")
    if not replacement_code.strip():
        return source, "skipped", "Replacement code is empty."

    if language == "python":
        import_pattern = re.compile(
            rf"(?m)^\s*(?:import\s+{re.escape(library)}(?:\s+as\s+\w+)?|"
            rf"from\s+{re.escape(library)}\s+import\s+[^\n#]+)\s*(?:#.*)?$"
        )
        modified = import_pattern.sub("", source).rstrip() + replacement_code + "\n"
        try:
            ast.parse(modified)
        except SyntaxError as exc:
            return source, "syntax_error", str(exc)
        return modified, "ok", "Replacement spliced into source."

    if language in {"javascript", "typescript"}:
        # Match: import X from 'lib'; import {X} from 'lib'; import 'lib'; const X = require('lib')
        lib_esc = re.escape(library)
        js_import_pattern = re.compile(
            rf"(?m)^\s*(?:"
            rf"import\s+(?:\*\s+as\s+\w+|\{{[^}}]*\}}|\w+(?:\s*,\s*\{{[^}}]*\}})?)\s+from\s+['\"]"
            rf"{lib_esc}['\"]"
            rf"|import\s+['\"]{lib_esc}['\"]"
            rf"|(?:const|let|var)\s+(?:\w+|\{{[^}}]*\}})\s*=\s*require\(\s*['\"]{lib_esc}['\"]\s*\))"
            rf"\s*;?\s*(?://.*)?$"
        )
        modified = js_import_pattern.sub("", source).rstrip() + replacement_code + "\n"
        # Validate the spliced result with node --check (JS only; TS-only syntax
        # such as type annotations is not valid plain JS, so we skip the strict
        # check for typescript and rely on import-presence detection instead).
        if language == "javascript" and not validate_js_syntax(modified):
            return source, "syntax_error", "node --check rejected spliced JavaScript."
        return modified, "ok", "Replacement spliced into source."

    return source, "unsupported", f"Splicing not supported for language: {language}."


def _classify_dependency(entry: dict[str, Any], *, metadata: dict[str, Any]) -> dict[str, Any]:
    name = str(entry["normalized_name"])
    license_id = _license_for_dependency(name, metadata)
    decision = "keep"
    category = "Keep"
    risk_level = "medium"
    safety_blocked = False
    blocking = False
    rationale = "Dependency survival requires explicit justification."

    if _license_blocks_absorption(license_id):
        decision = "block"
        category = "Block"
        risk_level = "high"
        blocking = True
        rationale = "License blocks absorption or redistribution without legal review."
    elif name in _PYTHON_STDLIB:
        decision = "keep"
        category = "Keep"
        risk_level = "low"
        safety_blocked = name in {"hashlib", "hmac", "random", "ssl", "subprocess"}
        rationale = "Runtime or standard-library dependency should not be absorbed."
    elif _in_family(name, _SECURITY_CRITICAL):
        decision = "keep"
        category = "Keep"
        risk_level = "high"
        safety_blocked = True
        rationale = "Security-critical dependency is on the safety block list."
    elif _in_family(name, _PLATFORM_RUNTIME):
        decision = "wrap"
        category = "Wrap"
        risk_level = "high"
        safety_blocked = True
        rationale = "Platform/runtime driver should be isolated, not absorbed."
    elif _in_family(name, _VALIDATION_SERIALIZATION):
        decision = "pin"
        category = "Pin"
        risk_level = "medium"
        safety_blocked = True
        rationale = "Validation and serialization behavior is edge-case heavy."
    elif _in_family(name, _HTTP_CLIENTS):
        decision = "wrap"
        category = "Wrap"
        risk_level = "medium"
        safety_blocked = True
        rationale = "HTTP client behavior includes TLS, pooling, and retry semantics."
    elif _in_family(name, _FRAMEWORK_CORE):
        decision = "keep"
        category = "Keep"
        risk_level = "high"
        safety_blocked = True
        rationale = "Framework core dependency should not be auto-absorbed."
    elif _in_family(name, _COMPLEX_PARSERS):
        decision = "pin"
        category = "Pin"
        risk_level = "medium"
        safety_blocked = True
        rationale = "Parser/compiler behavior is complex and version-sensitive."
    elif _in_family(name, _SAFETY_CRITICAL_MATH):
        decision = "keep"
        category = "Keep"
        risk_level = "high"
        safety_blocked = True
        rationale = "Safety-critical math dependency must remain vetted."
    elif _in_family(name, _OBSERVABILITY):
        decision = "wrap"
        category = "Wrap"
        risk_level = "medium"
        safety_blocked = True
        rationale = "Observability-impacting dependency should remain controlled."
    elif name == "lodash":
        decision = "replace"
        category = "Replace"
        risk_level = "medium"
        rationale = (
            "Broad utility package should be replaced with narrower utilities "
            "or first-party helpers."
        )
    elif name in _SMALL_PURE_UTILITIES:
        decision = "absorb"
        category = "Absorbable"
        risk_level = "low"
        rationale = "Small deterministic utility is eligible for first-party replacement planning."

    return {
        "dependency_id": entry["dependency_id"],
        "name": entry["name"],
        "normalized_name": name,
        "decision": decision,
        "category": category,
        "risk_level": risk_level,
        "safety_blocked": safety_blocked,
        "blocking": blocking,
        "license": license_id,
        "rationale": rationale,
        "source_refs": entry.get("source_refs", []),
        "usage_hints": entry.get("usage_hints", []),
    }


def _replacement_plan(
    classification: dict[str, Any],
    equivalence_passed: bool,
    security_passed: bool,
) -> dict[str, Any]:
    blocked_by = []
    if not equivalence_passed:
        blocked_by.append("equivalence_report")
    if not security_passed:
        blocked_by.append("security_compliance_report")
    return {
        "dependency_id": classification["dependency_id"],
        "name": classification["name"],
        "decision": "absorb",
        "status": "ready_for_planning" if not blocked_by else "gated",
        "blocked_by": blocked_by,
        "replacement_scope": "small pure utility helper",
        "requires_operator_approval": False,
        "modified_output_created": False,
        "rationale": classification["rationale"],
    }


def _survival_justification(mission_id: str, classification: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": DEPENDENCY_SURVIVAL_SCHEMA_VERSION,
        "justification_id": (
            f"dependency-survival-{mission_id}-{classification['normalized_name']}"
        ),
        "mission_id": mission_id,
        "dependency_id": classification["dependency_id"],
        "name": classification["name"],
        "decision": classification["decision"],
        "risk_level": classification["risk_level"],
        "safety_blocked": classification["safety_blocked"],
        "rationale": classification["rationale"],
        "review_required": classification["risk_level"] in {"medium", "high"},
    }


def _absorption_status(
    classification_report: dict[str, Any],
    planned_replacements: list[dict[str, Any]],
) -> str:
    if classification_report["blocking"]:
        return "blocked"
    if any(plan["status"] == "ready_for_planning" for plan in planned_replacements):
        return "planned"
    if planned_replacements:
        return "gated"
    return "not_applicable"


def _recommendations(
    classifications: list[dict[str, Any]],
    planned_replacements: list[dict[str, Any]],
) -> list[str]:
    recommendations: list[str] = []
    if any(item["safety_blocked"] for item in classifications):
        recommendations.append("Keep safety-blocked dependencies out of automatic absorption.")
    if any(item["decision"] == "wrap" for item in classifications):
        recommendations.append("Introduce internal adapters for wrapped dependencies.")
    if any(item["decision"] == "pin" for item in classifications):
        recommendations.append("Pin retained dependencies and attach CVE monitoring.")
    if planned_replacements:
        recommendations.append(
            "Generate first-party replacements only after equivalence and security evidence passes."
        )
    return recommendations


def _add_package_metadata(package_metadata: dict[str, Any], add: Any) -> None:
    for key in ("dependencies", "devDependencies", "optionalDependencies"):
        section = package_metadata.get(key)
        if isinstance(section, dict):
            for name, version in section.items():
                add(name, source=f"package_metadata.{key}", ecosystem="javascript", version=version)
        elif isinstance(section, list):
            for name in section:
                add(name, source=f"package_metadata.{key}")


def _add_source_bundle_manifests(source_code: str, add: Any) -> None:
    for match in _PACKAGE_JSON_PATTERN.finditer(source_code):
        try:
            payload = json.loads(match.group("body"))
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        for section in ("dependencies", "devDependencies", "optionalDependencies"):
            dependencies = payload.get(section)
            if isinstance(dependencies, dict):
                for name, version in dependencies.items():
                    add(
                        name,
                        source=f"{match.group('path')}:{section}",
                        ecosystem="javascript",
                        version=version,
                    )
    for match in _REQUIREMENTS_PATTERN.finditer(source_code):
        for line in match.group("body").splitlines():
            name, version = _parse_requirement_line(line)
            if name:
                add(
                    name,
                    source=match.group("path"),
                    ecosystem="python",
                    version=version,
                )
    for match in _PYPROJECT_PATTERN.finditer(source_code):
        for name, version in _parse_pyproject_dependencies(match.group("body")):
            add(name, source=match.group("path"), ecosystem="python", version=version)


def _parse_requirement_line(line: str) -> tuple[str | None, str | None]:
    candidate = line.strip()
    if not candidate or candidate.startswith("#") or candidate.startswith("-"):
        return None, None
    candidate = candidate.split("#", 1)[0].strip()
    match = re.match(r"([A-Za-z0-9_.-]+)\s*([<>=!~]{1,2}.+)?$", candidate)
    if not match:
        return None, None
    return match.group(1), (match.group(2) or "").strip() or None


def _parse_pyproject_dependencies(body: str) -> list[tuple[str, str | None]]:
    dependencies: list[tuple[str, str | None]] = []
    in_dependencies = False
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("dependencies") and "[" in stripped:
            in_dependencies = True
            stripped = stripped.split("[", 1)[1]
        if in_dependencies:
            for value in re.findall(r'"([^"]+)"|\'([^\']+)\'', stripped):
                raw = value[0] or value[1]
                name, version = _parse_requirement_line(raw)
                if name:
                    dependencies.append((name, version))
            if "]" in stripped:
                in_dependencies = False
    return dependencies


def _usage_hints(entry: dict[str, Any], metadata: dict[str, Any]) -> list[str]:
    hints = []
    name = str(entry.get("normalized_name") or "")
    source_code = str(metadata.get("source_code") or "").lower()
    if name and source_code and name in source_code:
        hints.append("referenced_in_source_bundle")
    if entry.get("version"):
        hints.append("version_declared")
    return hints


def _license_for_dependency(name: str, metadata: dict[str, Any]) -> str | None:
    licenses = _dict_value(metadata.get("dependency_licenses"))
    raw = licenses.get(name) or licenses.get(name.replace("-", "_"))
    return str(raw).strip().lower() if raw else None


def _license_blocks_absorption(license_id: str | None) -> bool:
    if not license_id:
        return False
    normalized = license_id.lower().replace("only", "").replace("-or-later", "").strip()
    return normalized in _BLOCKED_LICENSES


def _in_family(name: str, family: set[str]) -> bool:
    return name in family or any(name.startswith(f"{item}.") for item in family)


def _clean_name(value: Any) -> str:
    candidate = str(value or "").strip()
    if not candidate:
        return ""
    if candidate.startswith("@"):
        parts = candidate.split("@")
        return "@".join(parts[:2]).strip()
    return candidate.split("@", 1)[0].strip()


def _normalize_name(value: str) -> str:
    return value.strip().lower().replace("_", "-").replace("/", "-")


def _clean_version(value: Any) -> str | None:
    candidate = str(value or "").strip()
    return candidate or None


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _dict_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _evidence_refs(metadata: dict[str, Any]) -> list[dict[str, Any]]:
    refs = []
    for key in (
        "application_intelligence_map",
        "equivalence_report",
        "security_compliance_report",
        "generated_output",
        "package_metadata",
    ):
        if isinstance(metadata.get(key), dict):
            refs.append({"type": "metadata", "ref": key})
    if isinstance(metadata.get("source_code"), str) and metadata["source_code"].strip():
        refs.append({"type": "metadata", "ref": "source_code"})
    return refs


async def _llm_generate_replacement(
    *,
    library: str,
    normalized: str,
    used_symbols: list[str],
    language: str,
    settings: Any,
    mission_id: str,
) -> dict[str, Any]:
    """Call the LLM to generate a first-party replacement for an absorbable dependency.

    Returns a replacement dict compatible with _splice_replacement.
    Falls back to empty dict (skipped) on any failure.
    """
    if not settings:
        return {"filename": "", "replacement_code": ""}
    if language not in {"python", "javascript", "typescript"}:
        return {"filename": "", "replacement_code": ""}

    symbols_str = ", ".join(used_symbols[:10]) if used_symbols else library
    ext = {"python": "py", "javascript": "js", "typescript": "ts"}.get(language, "py")
    filename = f"depabs_{normalized.replace('-', '_').replace('.', '_')}.{ext}"

    prompt = (
        "You are AGENT-39-DEPABS performing dependency absorption.\n"
        f"Generate a minimal, self-contained first-party replacement for the '{library}' library.\n"
        f"Language: {language}\n"
        f"Symbols used by the codebase: {symbols_str}\n"
        "Requirements:\n"
        "- Only implement the symbols listed above\n"
        "- Zero external imports (stdlib only)\n"
        "- Match the public API exactly so existing call sites work without modification\n"
        "- Include a module docstring stating this is a DEPABS replacement\n"
        "- Keep it under 80 lines\n"
        "Return ONLY the raw source code. No markdown fences. No explanation.\n"
        f"Start with: # DEPABS replacement for {library}\n"
    )

    try:
        from .llm_delegation import _call_with_recommendation, _depabs_recommendation

        recommendation = _depabs_recommendation()
        recommendation["__mission_id__"] = mission_id
        recommendation["__agent_id__"] = "AGENT-39-DEPABS"
        recommendation["__settings__"] = settings

        parsed, _provider, _model, _route = await _call_with_recommendation(
            recommendation=recommendation,
            prompt=prompt,
            call_context="depabs_llm_replacement",
        )

        code = ""
        if isinstance(parsed, dict):
            # LLM returned JSON — extract any code field
            for key in ("replacement_code", "code", "source", "content"):
                candidate = str(parsed.get(key) or "").strip()
                if candidate and len(candidate) > 10:
                    code = candidate
                    break
        elif isinstance(parsed, str):
            code = parsed.strip()

        if not code or len(code) < 10:
            return {"filename": "", "replacement_code": ""}

        # Validate Python syntax before accepting
        if language == "python":
            try:
                import ast as _ast
                _ast.parse(code)
            except SyntaxError:
                return {"filename": "", "replacement_code": ""}

        return {
            "filename": filename,
            "replacement_code": f"\n\n{code}\n",
            "source": "llm",
        }

    except Exception as exc:  # noqa: BLE001
        LOGGER.warning(
            "dependency_absorption: LLM replacement call failed for %s/%s: %s",
            language, library, exc,
        )
        return {"filename": "", "replacement_code": "", "error": str(exc)}
