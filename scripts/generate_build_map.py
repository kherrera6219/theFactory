"""Generate a complete markdown repository build map for theFactory."""

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

EXCLUDED_DIR_NAMES = {
    ".claude",
    ".git",
    ".pytest_cache",
    ".pytest-tmp",
    ".ruff_cache",
    ".next",
    ".venv",
    "node_modules",
    "playwright-report",
    "test-results",
    "__pycache__",
    "dist",
    "out",
    "output_extracted",
}


@dataclass(frozen=True)
class BuildMapStats:
    directories: int = 0
    files: int = 0


def _iter_entries(path: Path) -> list[Path]:
    entries: list[Path] = []
    for entry in sorted(path.iterdir(), key=lambda item: (item.is_file(), item.name.lower())):
        if entry.name in EXCLUDED_DIR_NAMES and entry.is_dir():
            continue
        entries.append(entry)
    return entries


def _build_tree(path: Path, prefix: str = "") -> tuple[list[str], BuildMapStats]:
    lines: list[str] = []
    directories = 0
    files = 0

    entries = _iter_entries(path)
    for index, entry in enumerate(entries):
        connector = "└── " if index == len(entries) - 1 else "├── "
        lines.append(f"{prefix}{connector}{entry.name}")

        if entry.is_dir():
            directories += 1
            child_prefix = f"{prefix}{'    ' if index == len(entries) - 1 else '│   '}"
            child_lines, child_stats = _build_tree(entry, child_prefix)
            lines.extend(child_lines)
            directories += child_stats.directories
            files += child_stats.files
        else:
            files += 1

    return lines, BuildMapStats(directories=directories, files=files)


def generate_build_map(repo_root: Path, output_path: Path) -> None:
    repo_root = repo_root.resolve()
    lines, stats = _build_tree(repo_root)
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat()

    markdown = "\n".join(
        [
            "# Repository Build Map",
            "",
            "Document version: 2026.03.29",
            f"Generated at: {generated_at}",
            f"Repository root: `{repo_root}`",
            "",
            (
                "This map is generated from the current filesystem so it can be reproduced "
                "and reviewed as code."
            ),
            "",
            "## Inclusion Rules",
            "",
            (
                "- Includes all files and folders under the repository root except cache/vendor "
                "directories that are not part of the maintained application source tree."
            ),
            (
                "- Excludes `.claude`, `.git`, `.pytest_cache`, `.pytest-tmp`, `.ruff_cache`, "
                "`.next`, `.venv`, `node_modules`, `playwright-report`, `test-results`, "
                "`__pycache__`, `dist`, `out`, and `output_extracted` directories."
            ),
            "- Paths are shown exactly as present at generation time.",
            "",
            "## Summary",
            "",
            f"- Directories included: `{stats.directories}`",
            f"- Files included: `{stats.files}`",
            "",
            "## Tree",
            "",
            "```text",
            repo_root.name,
            *lines,
            "```",
            "",
        ]
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")


if __name__ == "__main__":
    repository_root = Path(__file__).resolve().parents[1]
    target_path = repository_root / "docs" / "REPOSITORY_BUILD_MAP_2026-06-13.md"
    generate_build_map(repository_root, target_path)
