import ast
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS_ROOT = REPO_ROOT / "docs"
SKIP_DIR_NAMES = {"archive", "evidence", "openapi", "phases"}
SKIP_NAME_PREFIXES = ("ADR_", "REPOSITORY_BUILD_MAP_")
REQUIRED_METADATA = (
    "Document version:",
    "Last updated:",
    "Status:",
    "Audience:",
)
LINK_PATTERN = re.compile(r"(?<!\!)\[[^\]]+\]\(([^)]+)\)")


def current_source_docs() -> list[Path]:
    docs: list[Path] = []
    for path in DOCS_ROOT.rglob("*.md"):
        if any(part in SKIP_DIR_NAMES for part in path.relative_to(DOCS_ROOT).parts):
            continue
        if path.name.startswith(SKIP_NAME_PREFIXES):
            continue
        docs.append(path)
    return sorted(docs)


def markdown_files_for_link_check() -> list[Path]:
    paths = [REPO_ROOT / "README.md"]
    for path in DOCS_ROOT.rglob("*.md"):
        if any(part in {"archive", "phases"} for part in path.relative_to(DOCS_ROOT).parts):
            continue
        paths.append(path)
    return sorted(paths)


def validate_metadata(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()[:10]
    errors: list[str] = []
    if not lines or not lines[0].startswith("# "):
        errors.append("missing top-level title")
        return errors
    for item in REQUIRED_METADATA:
        if not any(item in line for line in lines):
            errors.append(f"missing metadata field `{item}`")
    return errors


def validate_links(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    errors: list[str] = []
    for match in LINK_PATTERN.finditer(text):
        target = match.group(1).strip()
        if not target or target.startswith("#"):
            continue
        if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", target):
            continue
        if target.startswith("mailto:"):
            continue
        clean_target = target.split("#", 1)[0]
        resolved = (path.parent / clean_target).resolve()
        if not resolved.exists():
            errors.append(f"broken link `{target}`")
    return errors


def public_docstring_targets() -> list[Path]:
    """Return Python files covered by the Phase 12 public-docstring check."""
    targets = sorted((REPO_ROOT / "shared_runtime").glob("*.py"))
    targets.extend(
        sorted((REPO_ROOT / "services" / "orchestrator" / "orchestrator").glob("storage_*.py"))
    )
    return targets


def validate_public_docstrings(path: Path) -> list[str]:
    """Return missing public function or method docstrings for one Python file."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    errors: list[str] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_") and ast.get_docstring(node) is None:
                errors.append(f"missing docstring for `{node.name}`")
            continue
        if isinstance(node, ast.ClassDef):
            if node.name.startswith("_"):
                continue
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if not item.name.startswith("_") and ast.get_docstring(item) is None:
                        errors.append(f"missing docstring for `{node.name}.{item.name}`")
    return errors


def main() -> int:
    failures: list[str] = []

    for path in current_source_docs():
        for error in validate_metadata(path):
            failures.append(f"{path.relative_to(REPO_ROOT)}: {error}")

    build_maps = sorted(DOCS_ROOT.glob("REPOSITORY_BUILD_MAP_*.md"))
    if not build_maps:
        failures.append("docs: missing generated repository build map")

    for path in markdown_files_for_link_check():
        for error in validate_links(path):
            failures.append(f"{path.relative_to(REPO_ROOT)}: {error}")

    for path in public_docstring_targets():
        for error in validate_public_docstrings(path):
            failures.append(f"{path.relative_to(REPO_ROOT)}: {error}")

    if failures:
        print("documentation validation failed:")
        for failure in failures:
            print(f" - {failure}")
        return 1

    print("documentation validation passed")
    print(f"validated_metadata_files={len(current_source_docs())}")
    print(f"validated_link_files={len(markdown_files_for_link_check())}")
    print(f"validated_docstring_files={len(public_docstring_targets())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
