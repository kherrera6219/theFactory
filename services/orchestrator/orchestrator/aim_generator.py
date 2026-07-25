"""Application Intelligence Map generation for source-bearing missions."""
from __future__ import annotations

import hashlib
import json
import logging
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)

AIM_REQUIRING_MISSION_TYPES = frozenset(
    {
        "IMPORT_MODERNIZE",
        "PORT",
        "DEBUG_REPAIR",
        "SECURITY_HARDEN",
        "REDUCE_DEPENDENCIES",
        "ANALYZE_ONLY",
    }
)

MAX_AIM_FILES = 100
MAX_FILE_CHARS = 200_000
MAX_SOURCE_CHARS = 2_000_000
MAX_DETECTED_IMPORTS = 1_000

_SOURCE_BUNDLE_FILE_PATTERN = re.compile(r"^## FILE (.+)$", re.MULTILINE)
_LANGUAGE_BY_SUFFIX = {
    # Pod A — Dynamic
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".rb": "ruby",
    ".php": "php",
    # Pod B — Systems (desktop / game critical)
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".hpp": "cpp",
    ".hxx": "cpp",
    ".rs": "rust",
    ".go": "go",
    ".zig": "zig",
    # Pod C — Enterprise
    ".java": "java",
    ".cs": "csharp",
    ".scala": "scala",
    ".kt": "kotlin",
    ".kts": "kotlin",
    # Pod D — Mathematical
    ".r": "r",
    ".R": "r",
    ".jl": "julia",
    ".m": "matlab",
    ".wl": "mathematica",
    ".nb": "mathematica",
    ".hs": "haskell",
    ".ml": "ocaml",
    ".mli": "ocaml",
    # Platform-native (desktop / game)
    ".swift": "swift",
    ".mm": "objc",
    ".lua": "lua",
    ".glsl": "glsl",
    ".hlsl": "hlsl",
    ".wgsl": "wgsl",
    ".shader": "glsl",
}
_SUPPORTED_EXTRACTOR_LANGUAGES = frozenset({
    "python", "javascript", "typescript", "java",
    "c", "cpp", "rust", "go", "zig",
    "csharp", "scala", "kotlin",
    "ruby", "php",
    "r", "julia", "matlab", "mathematica", "haskell", "ocaml",
})


def mission_requires_aim(mission_type: str | None) -> bool:
    return str(mission_type or "").strip().upper() in AIM_REQUIRING_MISSION_TYPES


async def generate_aim(
    *,
    mission_id: str,
    source_code: str,
    prompt: str,
    mission_type: str,
    requested_target_language: str | None,
    feature_contract: dict[str, Any],
    settings: Any,
) -> dict[str, Any]:
    """Generate a bounded, source-safe Application Intelligence Map."""
    del settings
    from .llm_delegation import (
        _call_with_recommendation,
        _ceo_recommendation,
        _clean_text,
        check_user_input,
    )

    generated_at = datetime.now(UTC).isoformat()
    extraction_summary = _extract_all_languages(
        source_code=source_code,
        primary_language=requested_target_language,
    )
    recommendation = _ceo_recommendation()
    provider = str(recommendation.get("provider", "gemini")).strip().lower()
    model = str(recommendation.get("model", "gemini-3.6-flash")).strip()

    bounded_feature_contract = _bounded_feature_contract(feature_contract)

    prompt_text = (
        "You are AGENT-02-CEO producing an Application Intelligence Map.\n"
        "Use only the bounded source extraction summary below. "
        "Do not ask for or infer from raw source.\n"
        "Return only JSON. No markdown.\n\n"
        f"Recommended model: {provider}/{model}\n"
        f"Mission type: {_clean_text(mission_type, max_length=64)}\n"
        f"Operator request: {_clean_text(prompt, max_length=300)}\n"
        f"Target language: {_clean_text(requested_target_language or 'auto', max_length=64)}\n"
        f"Feature contract: {json.dumps(bounded_feature_contract, sort_keys=True)}\n"
        f"Extraction summary: {json.dumps(extraction_summary, sort_keys=True)}\n\n"
        "Required JSON keys:\n"
        "{\n"
        '  "repository_summary": "1-2 sentence source inventory",\n'
        '  "detected_languages": ["python"],\n'
        '  "primary_language": "python",\n'
        '  "domain_distribution": {"domain": 1},\n'
        '  "complexity_assessment": "low | medium | high | very_high",\n'
        '  "key_patterns": ["patterns observed"],\n'
        '  "detected_dependencies": ["dependency names"],\n'
        '  "risks": ["risks"],\n'
        '  "risk_flags": ["security | migration | dependency | data | approval"],\n'
        '  "human_approval_recommended": false,\n'
        '  "recommended_approach": "mission strategy",\n'
        '  "recommended_mission_type": "ANALYZE_ONLY"\n'
        "}\n"
    )

    # OWASP LLM01 — block injected operator free-text before it reaches the LLM.
    operator_input_safe = check_user_input(
        f"{prompt}\n{mission_type}",
        "application intelligence map generation",
    )
    if not operator_input_safe:
        parsed, resolved_provider, resolved_model, llm_route = (
            None,
            provider,
            model,
            "blocked_injection",
        )
    else:
        parsed, resolved_provider, resolved_model, llm_route = await _call_with_recommendation(
            recommendation=recommendation,
            prompt=prompt_text,
            call_context="application intelligence map generation",
        )

    return _normalize_aim(
        parsed=parsed if isinstance(parsed, dict) else None,
        mission_id=mission_id,
        mission_type=mission_type,
        requested_target_language=requested_target_language,
        generated_at=generated_at,
        extraction_summary=extraction_summary,
        feature_contract=bounded_feature_contract,
        source="llm" if isinstance(parsed, dict) else "fallback",
        llm_route=llm_route,
        model_provider=resolved_provider,
        model=resolved_model,
    )


def _extract_all_languages(*, source_code: str, primary_language: str | None) -> dict[str, Any]:
    files = _parse_source_bundle(source_code[:MAX_SOURCE_CHARS])
    domain_counts: dict[str, int] = {}
    detected_imports: list[str] = []
    detected_languages: set[str] = set()
    analyzed_files: list[dict[str, Any]] = []
    total_functions = 0
    total_classes = 0
    total_concepts = 0

    for file_item in files[:MAX_AIM_FILES]:
        path = str(file_item.get("path", "inline_source.txt"))
        language = _infer_language(path, primary_language)
        manifest_entry = {
            "path": path,
            "language": language or "unknown",
            "size_bytes": file_item["size_bytes"],
            "sha256": file_item["sha256"],
        }
        if language not in _SUPPORTED_EXTRACTOR_LANGUAGES:
            analyzed_files.append({**manifest_entry, "analyzed": False})
            continue
        detected_languages.add(language)
        result = _extract_file(language, str(file_item.get("content", ""))[:MAX_FILE_CHARS])
        total_functions += result["function_count"]
        total_classes += result["class_count"]
        total_concepts += result["concept_count"]
        for domain, count in result["domain_counts"].items():
            domain_counts[domain] = domain_counts.get(domain, 0) + count
        detected_imports.extend(result["detected_imports"])
        analyzed_files.append({**manifest_entry, "analyzed": True})

    unique_imports = sorted({item for item in detected_imports if item})
    # Cap generously — this is a cheap list of import-name strings, not full
    # file content. The prior cap of 50 systematically dropped every
    # alphabetically-later dependency (e.g. "requests", "sqlalchemy",
    # "uvicorn") for any codebase with 50+ distinct imports, and those
    # dropped names silently vanished from detected_dependencies (this AIM's
    # fallback source of truth for dependency_absorption's inventory) with
    # no signal that anything was cut.
    imports_truncated = len(unique_imports) > MAX_DETECTED_IMPORTS

    return {
        "schema_version": "aim_extraction.v1",
        "files_seen": len(files),
        "files_analyzed": sum(1 for item in analyzed_files if item.get("analyzed")),
        "truncated": (
            len(files) > MAX_AIM_FILES
            or len(source_code) > MAX_SOURCE_CHARS
            or imports_truncated
        ),
        "source_digest_sha256": hashlib.sha256(source_code.encode("utf-8")).hexdigest(),
        "file_manifest": [
            {key: value for key, value in item.items() if key != "content"}
            for item in analyzed_files[:MAX_AIM_FILES]
        ],
        "detected_languages": sorted(detected_languages),
        "primary_language": _choose_primary_language(detected_languages, primary_language),
        "total_functions": total_functions,
        "total_classes": total_classes,
        "total_concepts": total_concepts,
        "domain_counts": domain_counts,
        "detected_imports": unique_imports[:MAX_DETECTED_IMPORTS],
    }


def _pod_worker_import_root() -> Path | None:
    """Locate the directory containing the importable ``pod_worker`` package.

    Local dev: ``services/pod-worker`` is a sibling of ``services/orchestrator``,
    so ``parents[2]`` from this file lands on ``services/``. Inside the built
    orchestrator container, only ``services/orchestrator``'s *contents* are
    copied to ``/app`` (see the Dockerfile) — there is no ``services/``
    ancestor at all, so that same arithmetic silently resolved to the
    filesystem root and never found anything (every extraction silently used
    the empty-result fallback in production). The Dockerfile instead copies
    the ``pod_worker`` package directly alongside ``orchestrator`` at
    ``/app/pod_worker``, so try both layouts and use whichever exists.
    """
    here = Path(__file__).resolve()
    candidates = (
        here.parents[2] / "pod-worker",  # local dev: services/pod-worker
        here.parents[1],  # container: /app (pod_worker copied alongside orchestrator)
    )
    for candidate in candidates:
        if (candidate / "pod_worker" / "language_extractor.py").is_file():
            return candidate
    return None


def _extract_file(language: str, content: str) -> dict[str, Any]:
    try:
        pod_worker_root = _pod_worker_import_root()
        if pod_worker_root is None:
            raise ModuleNotFoundError("pod_worker package not found in any known location")
        if str(pod_worker_root) not in sys.path:
            sys.path.insert(0, str(pod_worker_root))
        from pod_worker.language_extractor import get_extractor

        result = get_extractor(language).extract(content)
        concepts = list(getattr(result, "concepts", []) or [])
        domain_counts: dict[str, int] = {}
        for concept in concepts:
            domain = str(getattr(concept, "domain", "generic") or "generic")
            domain_counts[domain] = domain_counts.get(domain, 0) + 1
        # ExtractionResult has its own dedicated, well-populated `imports`
        # field (every language extractor subclass fills it via regex/AST
        # import detection). This used to instead filter `concepts` for
        # domain == "import" — a domain value the concept catalog never
        # actually produces (real import-like concepts are tagged
        # "module_patterns" alongside unrelated module declarations), so
        # detected_imports was always empty regardless of real source
        # content, silently starving dependency_absorption's AIM-based
        # detected_dependencies fallback of any real data.
        detected_imports = [str(item) for item in (getattr(result, "imports", []) or []) if item]
        return {
            "function_count": len(getattr(result, "functions", []) or []),
            "class_count": len(getattr(result, "classes", []) or []),
            "concept_count": len(concepts),
            "domain_counts": domain_counts,
            "detected_imports": detected_imports,
        }
    except Exception as exc:
        LOGGER.warning("AIM extraction failed for %s: %s", language, exc)
        return {
            "function_count": 0,
            "class_count": 0,
            "concept_count": 0,
            "domain_counts": {},
            "detected_imports": [],
        }


def _parse_source_bundle(source_code: str) -> list[dict[str, Any]]:
    matches = list(_SOURCE_BUNDLE_FILE_PATTERN.finditer(source_code))
    if not matches:
        return [_source_file_entry("inline_source.txt", source_code)]

    files: list[dict[str, Any]] = []
    for index, match in enumerate(matches):
        path = str(match.group(1)).strip() or f"file-{index + 1}.txt"
        content_start = match.end()
        content_end = matches[index + 1].start() if index + 1 < len(matches) else len(source_code)
        content = source_code[content_start:content_end].lstrip("\r\n")
        files.append(_source_file_entry(path, content))
    return files


def _source_file_entry(path: str, content: str) -> dict[str, Any]:
    payload = content.encode("utf-8")
    return {
        "path": path,
        "content": content,
        "size_bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def _infer_language(path: str, primary_language: str | None) -> str | None:
    suffix = Path(path.lower()).suffix
    if suffix in _LANGUAGE_BY_SUFFIX:
        return _LANGUAGE_BY_SUFFIX[suffix]
    normalized = str(primary_language or "").strip().lower()
    if normalized in _SUPPORTED_EXTRACTOR_LANGUAGES:
        return normalized
    return None


def _choose_primary_language(
    detected_languages: set[str],
    primary_language: str | None,
) -> str | None:
    normalized = str(primary_language or "").strip().lower()
    if normalized in detected_languages:
        return normalized
    if not detected_languages:
        return normalized or None
    return sorted(detected_languages)[0]


def _bounded_feature_contract(feature_contract: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": str(feature_contract.get("title") or "")[:160],
        "summary": str(feature_contract.get("summary") or "")[:360],
        "functional_requirements": _string_list(
            feature_contract.get("functional_requirements"), limit=8
        ),
        "acceptance_criteria": _string_list(feature_contract.get("acceptance_criteria"), limit=6),
        "risk_notes": _string_list(feature_contract.get("risk_notes"), limit=6),
    }


def _normalize_aim(
    *,
    parsed: dict[str, Any] | None,
    mission_id: str,
    mission_type: str,
    requested_target_language: str | None,
    generated_at: str,
    extraction_summary: dict[str, Any],
    feature_contract: dict[str, Any],
    source: str,
    llm_route: str,
    model_provider: str,
    model: str,
) -> dict[str, Any]:
    candidate = parsed or {}
    detected_languages = _string_list(candidate.get("detected_languages"), limit=12)
    if not detected_languages:
        detected_languages = list(extraction_summary.get("detected_languages") or [])
    repository_summary = str(candidate.get("repository_summary") or "").strip()
    if not repository_summary:
        repository_summary = _fallback_repository_summary(
            mission_type=mission_type,
            extraction_summary=extraction_summary,
            feature_contract=feature_contract,
        )

    return {
        "schema_version": "aim.v1",
        "aim_id": f"aim-{mission_id}",
        "mission_id": mission_id,
        "mission_type": str(mission_type or "ANALYZE_ONLY").strip().upper(),
        "generated_at": generated_at,
        "source": source,
        "llm_route": llm_route,
        "model_provider": model_provider,
        "model": model,
        "repository_summary": repository_summary[:500],
        "detected_languages": detected_languages,
        "primary_language": str(
            candidate.get("primary_language")
            or extraction_summary.get("primary_language")
            or requested_target_language
            or ""
        ),
        "total_functions": _int_value(
            candidate.get("total_functions"), extraction_summary.get("total_functions", 0)
        ),
        "total_classes": _int_value(
            candidate.get("total_classes"), extraction_summary.get("total_classes", 0)
        ),
        "total_concepts": int(extraction_summary.get("total_concepts", 0) or 0),
        "domain_distribution": _dict_value(
            candidate.get("domain_distribution"), extraction_summary.get("domain_counts", {})
        ),
        "complexity_assessment": _complexity(candidate.get("complexity_assessment")),
        "key_patterns": _string_list(candidate.get("key_patterns"), limit=10),
        "detected_dependencies": _string_list(
            candidate.get("detected_dependencies") or extraction_summary.get("detected_imports"),
            limit=50,
        ),
        "risks": _string_list(candidate.get("risks"), limit=10),
        "risk_flags": _string_list(candidate.get("risk_flags"), limit=10),
        "human_approval_recommended": bool(candidate.get("human_approval_recommended", False)),
        "recommended_approach": str(candidate.get("recommended_approach") or "")[:500],
        "recommended_mission_type": str(
            candidate.get("recommended_mission_type") or mission_type or "ANALYZE_ONLY"
        ).strip().upper(),
        "extraction_summary": extraction_summary,
    }


def _fallback_repository_summary(
    *,
    mission_type: str,
    extraction_summary: dict[str, Any],
    feature_contract: dict[str, Any],
) -> str:
    title = str(feature_contract.get("title") or "Source bundle").strip()
    files = int(extraction_summary.get("files_seen", 0) or 0)
    languages = ", ".join(extraction_summary.get("detected_languages") or []) or "unknown language"
    return (
        f"{title} contains {files} file(s) for a {mission_type} mission, "
        f"with detected {languages} code."
    )


def _string_list(value: Any, *, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip()[:160] for item in value if str(item).strip()][:limit]


def _dict_value(value: Any, fallback: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(fallback, dict):
        return fallback
    return {}


def _int_value(value: Any, fallback: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(fallback)
        except (TypeError, ValueError):
            return 0


def _complexity(value: Any) -> str:
    candidate = str(value or "").strip().lower()
    if candidate in {"low", "medium", "high", "very_high"}:
        return candidate
    return "medium"
