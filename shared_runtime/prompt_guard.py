"""prompt_guard.py — Prompt injection detection for theFactory.

2026 standard: OWASP LLM01 (Prompt Injection) is the #1 LLM vulnerability.
This module provides detection of common prompt injection patterns including:
  - Role-override attacks ("You are now X")
  - Delimiter smuggling (</system>, [INST], <<SYS>>)
  - Human-turn injection (\n\nHuman:, \n\nAssistant:)
  - Instruction-leakage attempts ("ignore previous instructions")
  - Jailbreak markers ("DAN mode", "developer mode")

Usage:
    from shared_runtime.prompt_guard import check_prompt, InjectionResult

    result = check_prompt(user_input)
    if result.is_suspicious:
        log_warning(result)
        # sanitize or reject based on policy
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class InjectionMatch:
    attack_type: str
    pattern: str
    matched_text: str


@dataclass
class InjectionResult:
    is_suspicious: bool
    risk_level: str  # "low", "medium", "high", "critical"
    matches: list[InjectionMatch] = field(default_factory=list)

    @property
    def summary(self) -> str:
        """Return a compact status string for logging and metadata."""
        if not self.is_suspicious:
            return "clean"
        types = {m.attack_type for m in self.matches}
        return f"suspicious:{self.risk_level}:{','.join(sorted(types))}"


# ---------------------------------------------------------------------------
# Pattern registry (ordered by severity)
# ---------------------------------------------------------------------------

_INJECTION_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    # (attack_type, compiled_pattern, risk_level)

    # Critical: system prompt delimiter smuggling
    ("DELIMITER_SYSTEM_TAG",
     re.compile(r"</?\s*system\s*>", re.IGNORECASE),
     "critical"),
    ("DELIMITER_INST_TAG",
     re.compile(r"\[INST\]|\[/INST\]|<<SYS>>|<</SYS>>", re.IGNORECASE),
     "critical"),
    ("DELIMITER_HUMAN_TURN",
     re.compile(r"(\n\n|^)(Human|Assistant|User|System)\s*:\s*", re.IGNORECASE | re.MULTILINE),
     "critical"),
    ("DELIMITER_SEPARATOR",
     re.compile(r"(---+|===+|###\s*SYSTEM\s*###)", re.IGNORECASE),
     "medium"),

    # High: role-override attempts
    ("ROLE_OVERRIDE",
     re.compile(
         r"\b(you are now|act as|pretend (?:you are|to be)|your new role is|"
         r"ignore (?:all )?(?:previous |above )?instructions?|"
         r"disregard (?:all )?(?:previous |above )?instructions?|"
         r"forget (?:all )?(?:previous |above )?instructions?)\b",
         re.IGNORECASE,
     ),
     "high"),

    # High: jailbreak keywords
    ("JAILBREAK_KEYWORD",
     re.compile(
         r"\b(DAN mode|developer mode|jailbreak|no restrictions|"
         r"unrestricted mode|bypass (?:safety|filter|guardrail|restriction)s?)\b",
         re.IGNORECASE,
     ),
     "high"),

    # Medium: agent ID injection attempts
    ("AGENT_ID_INJECT",
     re.compile(r"\bAGENT-\d{2}-[A-Z0-9\-]+\b"),
     "medium"),

    # Medium: prompt extraction attempts
    ("PROMPT_EXTRACTION",
     re.compile(
         r"\b(repeat (?:your|the) (system )?prompt|"
         r"show (?:me )?(?:your|the) (system )?prompt|"
         r"what (?:is|are) (?:your|the) (?:instructions?|prompt|rules?))\b",
         re.IGNORECASE,
     ),
     "medium"),

    # Low: encoded content that might hide injections
    ("BASE64_CONTENT",
     re.compile(r"\b[A-Za-z0-9+/]{50,}={0,2}\b"),
     "low"),
]

_RISK_PRIORITY = {"critical": 4, "high": 3, "medium": 2, "low": 1}


def check_prompt(text: str) -> InjectionResult:
    """Analyze *text* for prompt injection patterns.

    Returns an InjectionResult with is_suspicious=False if the text is clean.
    """
    if not text or not text.strip():
        return InjectionResult(is_suspicious=False, risk_level="low")

    matches: list[InjectionMatch] = []
    max_risk_level = "low"

    for attack_type, pattern, risk_level in _INJECTION_PATTERNS:
        for m in pattern.finditer(text):
            matches.append(InjectionMatch(
                attack_type=attack_type,
                pattern=pattern.pattern,
                matched_text=m.group(0)[:200],  # cap evidence length
            ))
            if _RISK_PRIORITY.get(risk_level, 0) > _RISK_PRIORITY.get(max_risk_level, 0):
                max_risk_level = risk_level

    return InjectionResult(
        is_suspicious=bool(matches),
        risk_level=max_risk_level if matches else "low",
        matches=matches,
    )


def sanitize_prompt(text: str) -> str:
    """Best-effort sanitization: strip known delimiter patterns.

    This is NOT a complete defense — use check_prompt() first and
    log/reject high-confidence attacks rather than relying on sanitization alone.
    """
    sanitized = text
    # Strip system tag delimiters
    sanitized = re.sub(r"</?\s*system\s*>", "", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"\[/?INST\]|<</?SYS>>", "", sanitized, flags=re.IGNORECASE)
    # Strip turn markers at line boundaries
    sanitized = re.sub(
        r"^(Human|Assistant|User|System)\s*:\s*",
        "",
        sanitized,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    return sanitized.strip()
