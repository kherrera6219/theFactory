from __future__ import annotations

import importlib
import json
import re
from typing import Any

from ..agent_personas import get_language_guidance, get_language_tooling
from .config import _PROMPT_CONTEXT_MAX_BYTES, _VALID_AGENT_IDS


def _prompt_context_max_bytes() -> int:
    """Resolve the prompt-context byte cap through the package namespace.

    Tests ``monkeypatch.setattr(llm_delegation, "_PROMPT_CONTEXT_MAX_BYTES", N)``
    on the package; reading it at call time keeps that contract working after
    the monolith was split into this package (issue #186).
    """
    pkg = importlib.import_module(__package__)
    return getattr(pkg, "_PROMPT_CONTEXT_MAX_BYTES", _PROMPT_CONTEXT_MAX_BYTES)

JSON_OBJECT_PATTERN = re.compile(r"\{.*\}", re.DOTALL)
_CONTROL_CHAR_PATTERN = re.compile(r"[\u0000-\u001F\u007F]")
_LANGUAGE_PATTERN = re.compile(r"^[a-z0-9#+-]{1,32}$")
_ROUTING_VERSION_PATTERN = re.compile(r"^[a-z0-9._-]{1,32}$")
_EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
_SECRET_LIKE_PATTERN = re.compile(
    r"(sk-[A-Za-z0-9_-]{8,}|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})"
)


# Hard cap on the string length fed to the redaction regexes. Inputs are
# uncontrolled (LLM output, mission context) and the email pattern can backtrack
# super-linearly, so we bound the scan length before any regex runs (ReDoS guard).
_MAX_CLEAN_INPUT_CHARS = 50000


def _clean_text(value: Any, *, max_length: int = 160) -> str:
    text = str(value)[:_MAX_CLEAN_INPUT_CHARS]
    text = _CONTROL_CHAR_PATTERN.sub(" ", text).strip()
    text = _EMAIL_PATTERN.sub("[redacted-email]", text)
    text = _SECRET_LIKE_PATTERN.sub("[redacted-secret]", text)
    return text[:max_length]


# Everything _CONTROL_CHAR_PATTERN covers except tab, newline and carriage
# return. Built from ranges rather than written as a literal class so the source
# of this file never contains a control character itself.
_CODE_CONTROL_CHARS = "".join(
    chr(code) for code in list(range(0x00, 0x20)) + [0x7F] if code not in (0x09, 0x0A, 0x0D)
)
_CODE_CONTROL_CHAR_PATTERN = re.compile(f"[{re.escape(_CODE_CONTROL_CHARS)}]")


def _clean_code(value: Any, *, max_length: int = 10000) -> str:
    """Sanitize a generated *source code* field without destroying its layout.

    ``_clean_text`` collapses every control character to a space. That is right
    for a label and catastrophic for code, because the newline is the statement
    separator. Generated unit tests were stored through it, so every test file
    began ``import inspect import pytest from sum_integers import sum_integers``
    on one line and no generated test could be imported. The mission still
    reported COMPLETE, because a test that cannot load looks much like a test
    that failed on its own merits.

    Tab, newline and carriage return are preserved; every other control
    character is still removed, and the same email/secret redaction and ReDoS
    input cap apply. Per-line trailing whitespace is trimmed so the length cap
    is not spent on padding.
    """
    text = str(value)[:_MAX_CLEAN_INPUT_CHARS]
    text = _CODE_CONTROL_CHAR_PATTERN.sub(" ", text)
    text = _EMAIL_PATTERN.sub("[redacted-email]", text)
    text = _SECRET_LIKE_PATTERN.sub("[redacted-secret]", text)
    normalized = text.replace("\r\n", "\n")
    return "\n".join(line.rstrip() for line in normalized.split("\n")).strip("\n")[:max_length]


def _sanitize_context_value(key: str, value: Any) -> Any:
    if key == "routing_enforced":
        return bool(value)
    if key == "requested_target_language":
        language = _clean_text(value, max_length=32).lower()
        return language if _LANGUAGE_PATTERN.fullmatch(language) else "general"
    if key == "routing_version":
        version = _clean_text(value, max_length=32).lower()
        return version if _ROUTING_VERSION_PATTERN.fullmatch(version) else "unknown"
    if key in {
        "intake_agent_id",
        "executive_agent_id",
        "expected_pod_manager_agent_id",
        "expected_specialist_agent_id",
        "selected_agent_id",
        "agent_id",
    }:
        candidate = _clean_text(value, max_length=32).upper()
        return candidate if candidate in _VALID_AGENT_IDS else None
    return _clean_text(value, max_length=96)


def _safe_context_json(mission_context: dict[str, Any]) -> str:
    """Serialize mission_context for prompt embedding with a hard size cap.

    Only the fields needed for routing are kept; all others are dropped before
    serialisation so that user-controlled content (e.g. ``prompt``,
    ``source_code``) cannot inject instructions into the LLM prompt.
    """
    safe_fields = {
        "mission_id",
        "requested_target_language",
        "routing_version",
        "routing_enforced",
        "intake_agent_id",
        "executive_agent_id",
        "expected_pod_manager_agent_id",
        "expected_specialist_agent_id",
        "selected_agent_id",
        "agent_id",
    }
    filtered: dict[str, Any] = {}
    for key in safe_fields:
        if key not in mission_context:
            continue
        sanitized = _sanitize_context_value(key, mission_context.get(key))
        if sanitized is not None:
            filtered[key] = sanitized
    serialized = json.dumps(filtered, sort_keys=True)
    max_bytes = _prompt_context_max_bytes()
    if len(serialized.encode("utf-8")) > max_bytes:
        # Truncate to safe length rather than embedding unbounded data.
        serialized = serialized.encode("utf-8")[:max_bytes].decode(
            "utf-8", errors="replace"
        ) + "...[truncated]"
    return serialized


def _extract_openai_text(payload: dict[str, Any]) -> str | None:
    output_text = payload.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()
    choices = payload.get("choices")
    if isinstance(choices, list):
        for choice in choices:
            if not isinstance(choice, dict):
                continue
            message = choice.get("message")
            if isinstance(message, dict):
                content = message.get("content")
                if isinstance(content, str) and content.strip():
                    return content.strip()
    output = payload.get("output")
    if isinstance(output, list):
        text_chunks: list[str] = []
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict):
                    continue
                text = block.get("text")
                if isinstance(text, str) and text.strip():
                    text_chunks.append(text.strip())
        if text_chunks:
            return "\n".join(text_chunks)
    return None


def _extract_anthropic_text(payload: dict[str, Any]) -> str | None:
    content = payload.get("content")
    if not isinstance(content, list):
        return None
    parts: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") != "text":
            continue
        text = block.get("text")
        if isinstance(text, str) and text.strip():
            parts.append(text.strip())
    if not parts:
        return None
    return "\n".join(parts)


def _extract_gemini_text(payload: dict[str, Any]) -> str | None:
    candidates = payload.get("candidates")
    if not isinstance(candidates, list):
        return None
    lines: list[str] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        content = candidate.get("content")
        if not isinstance(content, dict):
            continue
        parts = content.get("parts")
        if not isinstance(parts, list):
            continue
        for part in parts:
            if not isinstance(part, dict):
                continue
            text = part.get("text")
            if isinstance(text, str) and text.strip():
                lines.append(text.strip())
    if not lines:
        return None
    return "\n".join(lines)


def _find_balanced_json_objects(text: str) -> list[str]:
    """Return every top-level balanced ``{...}`` span in ``text``, in order,
    honoring string literals and escapes so braces inside quoted values don't
    prematurely close a span.

    A naive greedy regex (``\\{.*\\}``) spans from the very first ``{`` to the
    very last ``}`` in the whole text, so any second JSON-like block or brace
    inside prose (an example, an aside, a code snippet) merges into one
    unparseable candidate and discards an otherwise valid object.
    """
    spans: list[str] = []
    depth = 0
    in_string = False
    escaped = False
    start = -1
    for index, char in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start != -1:
                    spans.append(text[start : index + 1])
                    start = -1
    return spans


def _extract_decision_payload(raw_text: str | None) -> dict[str, Any] | None:
    if not isinstance(raw_text, str) or not raw_text.strip():
        return None
    candidate = raw_text.strip()
    spans = _find_balanced_json_objects(candidate)
    # LLMs typically emit reasoning/preamble (which may itself contain example
    # JSON or braces) before the actual decision object, so the answer is most
    # often the LAST top-level object, not the first. Try from the end,
    # falling back through earlier spans, then the raw text itself.
    candidates = list(reversed(spans)) or [candidate]
    for text_candidate in candidates:
        try:
            parsed = json.loads(text_candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def _normalize_text_list(value: Any, *, limit: int = 5) -> list[str]:
    items: list[str] = []
    if isinstance(value, str) and value.strip():
        items = [_clean_text(value)]
    elif isinstance(value, list):
        items = [_clean_text(item) for item in value if _clean_text(item)]
    return items[:limit]


def _language_context(language: str | None) -> str:
    language_key = _clean_text(language or "", max_length=32).lower()
    guidance = get_language_guidance(language_key)
    tooling = get_language_tooling(language_key)
    if not guidance and not tooling:
        return ""
    lines = ["Language discipline:"]
    if guidance:
        lines.append(f"  - {guidance}")
    if tooling:
        lines.append(f"  - Tooling references: {tooling}")
    return "\n" + "\n".join(lines) + "\n"


def _string_list(value: Any, *, limit: int, max_length: int = 120) -> list[str]:
    if not isinstance(value, list):
        return []
    return [
        cleaned
        for item in value[:limit]
        if (cleaned := _clean_text(item, max_length=max_length))
    ]


_MAX_KNOWLEDGE_CONTEXT_CHARS = 8_000


def _format_knowledge_context(knowledge: Any) -> str:
    """Render Knowledge Lake documentation for injection into a codegen prompt.

    Accepts either the merged string returned by
    ``knowledge_lake.get_language_context`` or the list of records returned by
    ``knowledge_lake.query_documentation``. Returns an empty string when there
    is nothing to inject.
    """
    if isinstance(knowledge, str):
        text = knowledge.strip()
    elif isinstance(knowledge, list):
        parts: list[str] = []
        for item in knowledge:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            snippet = ""
            if isinstance(content, dict):
                snippet = str(content.get("combined_text") or "").strip()
            elif isinstance(content, str):
                snippet = content.strip()
            if snippet:
                parts.append(snippet)
        text = "\n\n".join(parts)
    else:
        return ""

    if not text:
        return ""
    if len(text) > _MAX_KNOWLEDGE_CONTEXT_CHARS:
        text = text[:_MAX_KNOWLEDGE_CONTEXT_CHARS] + "\n...[truncated]"
    return "\nRelevant documentation from the Knowledge Lake:\n" + text + "\n"


def _format_upstream_risks(metadata: dict[str, Any]) -> str:
    """Summarize upstream PM/CEO risk signals for downstream prompts."""
    lines: list[str] = []
    feature_contract = metadata.get("feature_contract")
    if isinstance(feature_contract, dict):
        risks = _string_list(feature_contract.get("risk_notes"), limit=3)
        questions = _string_list(feature_contract.get("clarifying_questions"), limit=3)
        if risks:
            lines.append("PM risk notes: " + "; ".join(risks))
        if questions:
            lines.append("PM open questions: " + "; ".join(questions))
    mission_contract = metadata.get("mission_contract")
    if isinstance(mission_contract, dict):
        risks = _string_list(mission_contract.get("risk_notes"), limit=3)
        if risks:
            lines.append("CEO risk notes: " + "; ".join(risks))
    if not lines:
        return ""
    return "\nUpstream risk context:\n" + "\n".join(f"  - {line}" for line in lines) + "\n"


def _format_upstream_style(metadata: dict[str, Any]) -> str:
    """Summarize user style directives for downstream prompts."""
    directives = metadata.get("global_style_directives") or []
    if not directives:
        return ""
    return "\nGlobal Team Style Directives (MANDATORY):\n" + "\n".join(f"  - {d}" for d in directives) + "\n"


def _pm_ambiguity_score(contract: dict[str, Any], prompt: str) -> float:
    """Score feature-contract ambiguity from 0.0 to 1.0."""
    score = 0.0
    intake_status = str(contract.get("intake_status") or "").strip().lower()
    if intake_status == "needs_clarification":
        score += 0.55
    questions = contract.get("clarifying_questions")
    if isinstance(questions, list):
        score += min(len(questions) * 0.15, 0.45)
    risks = contract.get("risk_notes")
    if isinstance(risks, list):
        score += min(len(risks) * 0.10, 0.20)
    if len(str(prompt or "").strip()) < 60:
        score += 0.20
    complexity = str(contract.get("estimated_complexity") or "medium").strip().lower()
    requirements = contract.get("functional_requirements")
    if complexity in {"high", "very_high"} and isinstance(requirements, list):
        if len(requirements) <= 2:
            score += 0.20
    if bool(contract.get("human_approval_required")):
        score += 0.10
    return round(min(score, 1.0), 3)


def _pm_product_clarifying_questions(
    *,
    prompt: str,
    contract: dict[str, Any],
    requested_target_language: str | None = None,
) -> list[str]:
    """Return product-level clarification questions for underspecified UI/app work."""
    text = " ".join(
        [
            str(prompt or ""),
            str(contract.get("summary") or ""),
            " ".join(str(item) for item in contract.get("functional_requirements") or []),
            " ".join(str(item) for item in contract.get("assumptions") or []),
        ]
    ).lower()
    target_language = str(requested_target_language or "").strip().lower()
    target_languages = " ".join(str(item).lower() for item in contract.get("target_languages") or [])
    language_text = f"{target_language} {target_languages}"
    def has_token(*tokens: str) -> bool:
        return any(re.search(rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])", text) for token in tokens)

    is_game = has_token("game", "snake", "pong", "tetris", "rpg", "platformer")
    is_interactive_app = is_game or has_token(
        "app",
        "application",
        "dashboard",
        "frontend",
        "ui",
        "user interface",
        "angular",
        "react",
        "next.js",
        "vue",
    )
    if not is_interactive_app:
        return []

    # Specified stdlib/CLI/single-file requests are ready; do not add arcade prompts.
    specified_stdlib = has_token(
        "standard library",
        "stdlib",
        "no pygame",
        "no pip",
        "no pyqt",
        "zero-dependency",
        "zero dependency",
        "no third-party",
    )
    specified_single_file = has_token("single file", "single python file") or bool(
        re.search(r"\b\w+\.(py|js|ts|go|rs)\b", text)
    )
    specified_controls = has_token("wasd", "arrow", "arrows", "keyboard")
    specified_loop = has_token("score", "collision", "wall", "game over", "quit")
    specified_terminal = has_token(
        "terminal", "curses", "msvcrt", "console", "no curses", "windows without curses"
    )
    fully_specified_cli_game = (
        is_game and specified_stdlib and specified_single_file and specified_controls
    )
    if fully_specified_cli_game:
        return []

    existing_questions = {
        str(question).strip().lower()
        for question in contract.get("clarifying_questions") or []
        if str(question).strip()
    }
    questions: list[str] = []

    def add(question: str) -> None:
        normalized = question.strip().lower()
        if normalized not in existing_questions and question not in questions:
            questions.append(question)

    style_tokens = (
        "theme",
        "visual",
        "style",
        "brand",
        "neon",
        "minimal",
        "retro",
        "dark mode",
        "light mode",
        "pixel",
    )
    if not specified_terminal and not specified_stdlib and not has_token(*style_tokens):
        add("What visual direction should the UI use? Recommended default: polished dark arcade style with clear contrast and responsive layout.")

    if is_game and not specified_controls and not specified_loop:
        gameplay_tokens = (
            "power",
            "level",
            "difficulty",
            "speed",
            "leaderboard",
            "save",
            "pause",
            "mobile",
            "touch",
            "keyboard",
        )
        if not has_token(*gameplay_tokens):
            add("What gameplay scope should be included beyond the core loop? Recommended default: keyboard controls, score, pause/resume, restart, and increasing speed.")

    packaging_tokens = (
        "start.bat",
        "docker",
        "electron",
        "installer",
        "zip",
        "readme",
        "dev server",
        "production build",
    )
    if not specified_single_file and not specified_stdlib and not has_token(*packaging_tokens):
        framework_default = "Angular CLI" if "angular" in text or "typescript" in language_text else "the framework default"
        add(f"How should the project be packaged for handoff? Recommended default: complete {framework_default} project with install/start script and run instructions.")

    # "build" deliberately excluded: it appears in almost every prompt on this
    # code-generation platform ("build a game/app") and is not itself a signal
    # that the user specified acceptance criteria.
    acceptance_tokens = ("test", "acceptance", "done", "verify", "lint", "playtest")
    if not specified_loop and not has_token(*acceptance_tokens):
        add("What should count as done for acceptance? Recommended default: app builds, starts locally, and the main user flow can be manually verified.")

    return questions[:3]


def _apply_pm_product_clarification_policy(
    *,
    contract: dict[str, Any],
    prompt: str,
    requested_target_language: str | None = None,
) -> dict[str, Any]:
    questions = _pm_product_clarifying_questions(
        prompt=prompt,
        contract=contract,
        requested_target_language=requested_target_language,
    )
    if not questions:
        return contract

    existing = [
        str(question).strip()
        for question in contract.get("clarifying_questions") or []
        if str(question).strip()
    ]
    contract["clarifying_questions"] = [*existing, *questions][:5]
    contract["intake_status"] = "needs_clarification"
    assumptions = [
        str(item).strip()
        for item in contract.get("assumptions") or []
        if str(item).strip()
    ]
    assumptions.append(
        "If the operator says to proceed with assumptions, use the recommended defaults from the clarifying questions."
    )
    contract["assumptions"] = assumptions[:6]
    contract["ambiguity_score"] = _pm_ambiguity_score(contract, prompt)
    return contract


def _normalize_agent_choice(raw_value: Any, *, allowed_ids: set[str], fallback: str) -> str:
    candidate = _clean_text(raw_value, max_length=32).upper()
    return candidate if candidate in allowed_ids else fallback


def _strip_code_fences(value: str) -> str:
    text = value.strip()
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _safe_filename(value: Any, fallback: str) -> str:
    filename = _clean_text(value or fallback, max_length=96)
    filename = filename.replace("\\", "_").replace("/", "_").replace("..", "_").strip()
    return filename or fallback


def _priority(value: Any) -> str:
    priority = _clean_text(value or "MEDIUM", max_length=16).upper()
    if priority not in {"HIGH", "MEDIUM", "LOW"}:
        return "MEDIUM"
    return priority


def _cluster_id(index: int, domain: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", domain.strip().lower()).strip("-")
    return f"cluster-{index:02d}-{slug or 'general'}"


def _logicnode_payload(record: Any) -> dict[str, Any]:
    if not isinstance(record, dict):
        return {}
    nested = record.get("node")
    if isinstance(nested, dict):
        return nested
    return record


def _logicnode_text(value: Any, *keys: str, fallback: str = "") -> str:
    if not isinstance(value, dict):
        return fallback
    for key in keys:
        raw_candidate = value.get(key)
        if raw_candidate is None:
            continue
        candidate = _clean_text(raw_candidate, max_length=120)
        if candidate:
            return candidate
    nested = value.get("payload")
    if isinstance(nested, dict):
        for key in keys:
            raw_candidate = nested.get(key)
            if raw_candidate is None:
                continue
            candidate = _clean_text(raw_candidate, max_length=120)
            if candidate:
                return candidate
    return fallback


def _logicnode_sources(record: Any, payload: dict[str, Any]) -> list[str]:
    sources: list[str] = []
    for container in (record, payload):
        if not isinstance(container, dict):
            continue
        for key in ("node_id", "id", "logicnode_id"):
            raw_candidate = container.get(key)
            if raw_candidate is None:
                continue
            candidate = _clean_text(raw_candidate, max_length=96)
            if candidate and candidate not in sources:
                sources.append(candidate)
    return sources or ["unidentified-logicnode"]


def _logicnode_languages(record: Any, payload: dict[str, Any]) -> list[str]:
    languages: list[str] = []
    for container in (record, payload):
        if not isinstance(container, dict):
            continue
        for key in ("language", "target_language", "requested_target_language", "source_language"):
            raw_candidate = container.get(key)
            if raw_candidate is None:
                continue
            candidate = _clean_text(raw_candidate, max_length=32).lower()
            if candidate and candidate not in languages:
                languages.append(candidate)
    return languages[:6]


def _standard_node_id(index: int, domain: str, concept: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", f"{domain}-{concept}".strip().lower()).strip("-")
    return f"standard-node-{index:02d}-{slug or 'general'}"


def _pod_standard_coverage_verdict(
    *,
    logicnodes: list[dict[str, Any]],
    canonical_logicnodes: list[dict[str, Any]],
    source_code: str | None = None,
) -> dict[str, Any]:
    raw_count = len([node for node in logicnodes if isinstance(node, dict)])
    canonical_count = len(canonical_logicnodes)
    source_line_count = len([line for line in str(source_code or "").splitlines() if line.strip()])
    expected_minimum = max(1, min(20, source_line_count // 25)) if source_line_count else 1
    coverage_thin = canonical_count < expected_minimum or (raw_count > 0 and canonical_count == 0)
    duplicate_ratio = (
        round((max(0, raw_count - canonical_count) / raw_count), 4) if raw_count else 0.0
    )
    findings: list[str] = []
    if coverage_thin:
        findings.append(
            "Canonical LogicNode coverage is thin for the available source and pod evidence."
        )
    if raw_count > 0 and duplicate_ratio >= 0.85:
        findings.append("High duplicate-elimination ratio requires pod-manager review.")
    if not findings:
        findings.append("Canonical LogicNode coverage meets deterministic pod standard checks.")
    return {
        "schema_version": "pod_standard_coverage.v1",
        "raw_logicnode_count": raw_count,
        "canonical_logicnode_count": canonical_count,
        "source_line_count": source_line_count,
        "expected_minimum_canonical_logicnodes": expected_minimum,
        "duplicate_ratio": duplicate_ratio,
        "coverage_thin": coverage_thin,
        "findings": findings,
    }

