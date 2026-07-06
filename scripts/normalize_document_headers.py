import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from shared_runtime.atomic_io import atomic_write_text  # noqa: E402

DOCS_ROOT = REPO_ROOT / "docs"
DOCUMENT_VERSION = "2026.03.29"
LAST_UPDATED = "2026-03-29"
DEFAULT_STATUS = "Canonical"
DEFAULT_AUDIENCE = "Operators, developers, maintainers, and auditors"

STATUS_OVERRIDES = {
    "ACCESSIBILITY_STATEMENT.md": "Draft; accessibility review required",
    "AGENT_LLM_PROVIDER_MODEL_MATRIX_2026-03-02.md": "Reference",
    "AGENT_PERSONA_STANDARDS_EVIDENCE_2026-03-02.md": "Reference",
    "AGENT_PROTOCOL_BUS_DATA_SYSTEMS_PLAN.md": "Reference",
    "LEGACY_PROFILE_ID_MAPPING_INDEX.md": "Reference",
    "PRIVACY_POLICY.md": "Draft; legal review required",
    "ROADMAP.md": "Historical reference",
    "SMELT_CYCLE_RUNTIME_MAPPING_2026-03-04.md": "Reference",
    "TERMS_OF_SERVICE.md": "Draft; legal review required",
}

AUDIENCE_OVERRIDES = {
    "ACCESSIBILITY_STATEMENT.md": "Operators, users, accessibility reviewers, and legal reviewers",
    "AGENT_SERVICE_KEY_ISOLATION.md": "Maintainers, operators, and security reviewers",
    "API_INTEGRATION_GUIDE.md": "Integrators, developers, and operators",
    "COMPLIANCE_EVIDENCE_MAPPING.md": "Maintainers, auditors, and compliance reviewers",
    "COMPOSE_ENVIRONMENT_PROFILES.md": "Operators, developers, and maintainers",
    "DATA_CLASSIFICATION_POLICY.md": "Operators, developers, maintainers, and security reviewers",
    "DEPLOYMENT_DR_PLAYBOOK.md": "Operators, maintainers, incident responders, and release owners",
    "DEVELOPER_GUIDE.md": "Engineers and maintainers",
    "DEVELOPER_ONBOARDING_GUIDE.md": "Contributors, maintainers, and new developers",
    "DIAGRAM_STANDARDS.md": "Developers, maintainers, and technical writers",
    "GETTING_STARTED.md": "Operators and developers",
    "MODEL_PROMOTION_GOVERNANCE.md": "Maintainers, AI operators, and release reviewers",
    "OBSERVABILITY_STACK.md": "Operators, maintainers, and SRE/DevOps reviewers",
    "OPERATOR_GUIDE.md": "Operators, reviewers, and technical users",
    "OPERATIONS_RUNBOOK.md": "Operators, maintainers, and on-call responders",
    "PRIVACY_POLICY.md": "Operators, maintainers, legal reviewers, and compliance reviewers",
    "PRODUCTION_STANDARDS_REFERENCES.md": (
        "Maintainers, auditors, security reviewers, and technical leads"
    ),
    "RELEASE_COMPLETION_PLAN.md": "Maintainers, technical leads, release owners, and auditors",
    "RELEASE_TRUST_PROMOTION_GATE.md": "Maintainers, release owners, and auditors",
    "TERMS_OF_SERVICE.md": "Operators, maintainers, and legal reviewers",
    "README.md": "Integrators, developers, operators, and auditors",
}

SKIP_DIR_NAMES = {"archive", "evidence", "openapi"}
SKIP_NAME_PREFIXES = ("ADR_", "REPOSITORY_BUILD_MAP_")
METADATA_PREFIXES = (
    "Document version:",
    "Last updated:",
    "Status:",
    "Audience:",
    "**Last updated:**",
    "**Status:**",
    "**Audience:**",
    "**Goal:**",
    "**Owner:**",
    "**Review Cycle:**",
    "**Standards:**",
    "**RTO Target:**",
    "**Current results:**",
    "**Stack:**",
)
METADATA_PATTERNS = (
    re.compile(r"^\*\*Last updated:\*\*"),
    re.compile(r"^\*\*Status:\*\*"),
    re.compile(r"^\*\*Audience:\*\*"),
    re.compile(r"^\*\*Goal:\*\*"),
    re.compile(r"^\*\*Owner:\*\*"),
    re.compile(r"^\*\*Review Cycle:\*\*"),
    re.compile(r"^\*\*Standards:\*\*"),
    re.compile(r"^\*\*RTO Target:\*\*"),
    re.compile(r"^\*\*Current results:\*\*"),
    re.compile(r"^\*\*Stack:\*\*"),
)


def iter_target_docs() -> list[Path]:
    result: list[Path] = []
    for path in DOCS_ROOT.rglob("*.md"):
        if any(part in SKIP_DIR_NAMES for part in path.relative_to(DOCS_ROOT).parts):
            continue
        if path.name.startswith(SKIP_NAME_PREFIXES):
            continue
        result.append(path)
    return sorted(result)


def is_metadata_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    if stripped == "---":
        return True
    if stripped.startswith(METADATA_PREFIXES):
        return True
    return any(pattern.match(stripped) for pattern in METADATA_PATTERNS)


def audience_for(path: Path) -> str:
    return AUDIENCE_OVERRIDES.get(path.name, DEFAULT_AUDIENCE)


def status_for(path: Path) -> str:
    return STATUS_OVERRIDES.get(path.name, DEFAULT_STATUS)


def compute_normalized(path: Path) -> tuple[str, str] | None:
    """Return (original, normalized) if the file's header needs a rewrite, else None."""
    original = path.read_text(encoding="utf-8")
    lines = original.splitlines()
    if not lines or not lines[0].startswith("# "):
        raise ValueError(f"{path} is missing a top-level markdown title")

    title = lines[0].rstrip()
    index = 1
    while index < len(lines) and is_metadata_line(lines[index]):
        index += 1

    remaining = "\n".join(lines[index:]).lstrip("\n")
    normalized = (
        f"{title}\n\n"
        f"Document version: {DOCUMENT_VERSION}  \n"
        f"Last updated: {LAST_UPDATED}  \n"
        f"Status: {status_for(path)}  \n"
        f"Audience: {audience_for(path)}\n"
    )
    if remaining:
        normalized += f"\n{remaining}\n"
    else:
        normalized += "\n"

    if normalized == original:
        return None
    return original, normalized


def normalize(path: Path, *, execute: bool) -> bool:
    """Return True if path needs (dry-run) or received (execute) a header rewrite."""
    result = compute_normalized(path)
    if result is None:
        return False
    if execute:
        _, normalized = result
        atomic_write_text(path, normalized)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Normalize the version/date/status/audience header block on docs/*.md."
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually rewrite files. Without this flag (the default), only reports "
        "which files' headers would change and writes nothing.",
    )
    args = parser.parse_args()

    changed = 0
    for path in iter_target_docs():
        if normalize(path, execute=args.execute):
            changed += 1
            verb = "normalized" if args.execute else "would normalize"
            print(f"{verb} {path.relative_to(REPO_ROOT)}")

    if not args.execute:
        print(f"DRY-RUN: {changed} file(s) would be normalized. Pass --execute to write them.")
    else:
        print(f"normalized_files={changed}")


if __name__ == "__main__":
    main()
