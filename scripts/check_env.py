"""Validate the local `.env` before starting the stack.

Beyond the original `CHANGE_ME` check, this catches the class of `.env` mistake
that silently corrupts a value rather than failing loudly.

**Inline comments are not supported.** Docker Compose's `env_file` parser treats
everything after `=` as the value, so:

    ENVIRONMENT=development# Dev bypass - removes the admin key gate

sets `ENVIRONMENT` to the whole string `"development# Dev bypass - removes the
admin key gate"`, not `"development"`. Nothing errors. Every
`ENVIRONMENT == "development"` branch silently stops matching, and the only
symptom is behaviour that quietly differs from what the file appears to say.

That exact line shipped in a working `.env` and was found only by reading the
resolved value out of a running container (2026-08-03). This check makes it fail
at `make up` instead.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Value types where a "#" is legitimate rather than a stray comment — secrets
# and URLs can legally contain one.
_HASH_ALLOWED_SUFFIXES = (
    "_KEY",
    "_SECRET",
    "_PASSWORD",
    "_TOKEN",
    "_DSN",
    "_URL",
    "_URI",
)

# Keys whose value must be a single bare token, because code compares them by
# equality. A stray comment or space silently breaks the match.
_SINGLE_TOKEN_KEYS = {
    "ENVIRONMENT",
    "LLM_PROVIDER",
    "AUTH_MODE",
    "GATEWAY_AUTH_MODE",
    "TOPOLOGY_MODE",
    "LANGGRAPH_CHECKPOINTER",
}

# An explicit empty assignment overrides Compose `${VAR:-default}` and mounts
# an empty host directory. Delete the line instead of leaving KEY=.
_EMPTY_UNSAFE_KEYS = {
    "SANDBOX_WORKSPACE_HOST_ROOT",
}

_ASSIGNMENT = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$")


def _assignments(text: str):
    """Yield ``(lineno, key, value)`` for each assignment line."""
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = _ASSIGNMENT.match(line)
        if match:
            yield lineno, match.group(1), match.group(2)


def _inline_comment_errors(path: Path, text: str) -> list[str]:
    errors: list[str] = []
    for lineno, key, value in _assignments(text):
        if "#" not in value or key.endswith(_HASH_ALLOWED_SUFFIXES):
            continue
        preview = value[:70] + ("..." if len(value) > 70 else "")
        errors.append(
            f"{path.name}:{lineno}: {key} contains '#' in its value — .env has no "
            f"inline-comment support, so the comment becomes part of the value.\n"
            f"      got: {key}={preview}\n"
            f"      fix: move the comment to its own line above."
        )
    return errors


def _single_token_errors(path: Path, text: str) -> list[str]:
    errors: list[str] = []
    for lineno, key, value in _assignments(text):
        if key not in _SINGLE_TOKEN_KEYS:
            continue
        stripped = value.strip().strip("\"'")
        if stripped and " " in stripped:
            errors.append(
                f"{path.name}:{lineno}: {key} must be a single bare token; code "
                f"compares it by equality.\n      got: {key}={value[:70]}"
            )
    return errors


def _empty_override_errors(path: Path, text: str) -> list[str]:
    errors: list[str] = []
    for lineno, key, value in _assignments(text):
        if key not in _EMPTY_UNSAFE_KEYS:
            continue
        if value.strip().strip("\"'") == "":
            errors.append(
                f"{path.name}:{lineno}: {key} is set empty. Compose treats "
                f"KEY= as set, so the default host sandbox path is not used "
                f"and the daemon mounts an empty directory.\n"
                f"      fix: delete the line, or set an absolute host path."
            )
    return errors


def _legacy_auth_mode_warnings(path: Path, text: str) -> list[str]:
    keys = {key for _, key, _ in _assignments(text)}
    if "GATEWAY_AUTH_MODE" in keys:
        return [
            f"{path.name}: GATEWAY_AUTH_MODE is not read by the gateway; "
            "use AUTH_MODE."
        ]
    return []


def _rqca_override_warnings(path: Path, text: str) -> list[str]:
    for _lineno, key, value in _assignments(text):
        if key != "RQCA_ENFORCEMENT_ENABLED":
            continue
        if value.strip().strip("\"'").lower() in {"0", "false", "no", "off"}:
            return [
                f"{path.name}: RQCA_ENFORCEMENT_ENABLED={value.strip()} overrides "
                "the product default (true). FAIL will not block COMPLETE."
            ]
    return []


def _env_files(repo_root: Path) -> list[Path]:
    candidates = [repo_root / ".env", repo_root / "deploy" / ".env", Path(".env")]
    resolved: list[Path] = []
    seen: set[Path] = set()
    for path in candidates:
        if path.exists() and path.resolve() not in seen:
            seen.add(path.resolve())
            resolved.append(path)
    return resolved


def check_env() -> int:
    """Return 0 when the environment is usable, 1 otherwise."""
    repo_root = Path(__file__).resolve().parent.parent
    paths = _env_files(repo_root)

    if not paths:
        print("WARNING: No .env file found in repo root or deploy/. Proceeding with defaults.")
        return 0

    errors: list[str] = []
    warnings: list[str] = []
    for path in paths:
        text = path.read_text(encoding="utf-8", errors="replace")
        if "CHANGE_ME" in text:
            errors.append(f"{path.name}: unset CHANGE_ME values")
        errors.extend(_inline_comment_errors(path, text))
        errors.extend(_single_token_errors(path, text))
        errors.extend(_empty_override_errors(path, text))
        warnings.extend(_legacy_auth_mode_warnings(path, text))
        warnings.extend(_rqca_override_warnings(path, text))

    for warning in warnings:
        print(f"WARNING: {warning}")

    if errors:
        print("ERROR: .env validation failed:\n")
        for error in errors:
            print(f"  - {error}\n")
        return 1

    print(f"env OK ({', '.join(p.name for p in paths)})")
    return 0


if __name__ == "__main__":
    sys.exit(check_env())
