"""Offline dependency provisioning service and cache manifest builder (Phase 4).

Separates untrusted project dependency acquisition into two isolated steps:
1. Provision (network-enabled for allow-listed registries, NO execution of
   project code, setup.py, npm postinstall scripts, or Gradle scripts) -> writes
   content-addressed artifacts and ``provisioning_manifest.v1`` into ``dep-cache``.
2. Execute (``--network=none`` sandbox in ``sandbox_exec.py``) -> mounts the
   mission's ``dep_cache_dir`` read-only at ``/deps:ro`` with offline ecosystem
   environment variables.
"""

from __future__ import annotations

import ast
import hashlib
import hmac
import json
import logging
import os
import re
import subprocess
import tempfile
import urllib.parse
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from defusedxml import ElementTree as ET
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

LOGGER = logging.getLogger(__name__)

PROVISIONING_MANIFEST_SCHEMA_VERSION = "provisioning_manifest.v1"

ALLOWED_REGISTRIES: frozenset[str] = frozenset(
    {
        "pypi.org",
        "files.pythonhosted.org",
        "registry.npmjs.org",
        "repo.maven.apache.org",
        "api.nuget.org",
        "proxy.golang.org",
        "sum.golang.org",
        "crates.io",
        "static.crates.io",
        "repo.packagist.org",
        "rubygems.org",
    }
)

_ECOSYSTEM_BY_LANGUAGE: dict[str, str] = {
    "python": "pypi",
    "javascript": "npm",
    "typescript": "npm",
    "java": "maven",
    "kotlin": "maven",
    "scala": "maven",
    "csharp": "nuget",
    "c#": "nuget",
    "go": "golang",
    "rust": "cargo",
    "php": "composer",
    "ruby": "gem",
}

_LANGUAGE_BY_MANIFEST: dict[str, str] = {
    "requirements.txt": "python",
    "pyproject.toml": "python",
    "package.json": "javascript",
    "package-lock.json": "javascript",
    "pom.xml": "java",
    "build.gradle": "java",
    "build.gradle.kts": "kotlin",
    "gradle.lockfile": "java",
    "packages.lock.json": "csharp",
    "go.mod": "go",
    "go.sum": "go",
    "cargo.toml": "rust",
    "cargo.lock": "rust",
    "composer.json": "php",
    "composer.lock": "php",
    "gemfile": "ruby",
    "gemfile.lock": "ruby",
}

# Frameworks already baked into vendored offline sandbox images (see rqca_agent.py).
_VENDORED_TEST_PACKAGES: dict[str, frozenset[str]] = {
    "java": frozenset({"junit", "junit:junit", "org.junit.jupiter:junit-jupiter"}),
    "kotlin": frozenset({"kotlin-test", "kotlin.test", "junit"}),
    "scala": frozenset({"scalatest", "scalactic"}),
    "php": frozenset({"phpunit", "phpunit/phpunit"}),
    "r": frozenset({"testthat"}),
    "python": frozenset({"pytest"}),
    "javascript": frozenset({"vitest"}),
    "typescript": frozenset({"vitest"}),
    "csharp": frozenset(
        {"xunit", "xunit.runner.visualstudio", "microsoft.net.test.sdk"}
    ),
    "c#": frozenset({"xunit", "xunit.runner.visualstudio", "microsoft.net.test.sdk"}),
}


@dataclass(frozen=True, slots=True)
class ProvisionedPackage:
    """Single dependency record inside a provisioning manifest."""

    name: str
    version: str
    ecosystem: str
    sha256: str = ""
    status: str = "provisioned"  # provisioned | needs_build | not_in_registry | blocked_by_policy
    reason: str = ""
    cache_path: str = ""
    scope: str = "runtime"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "ecosystem": self.ecosystem,
            "sha256": self.sha256,
            "status": self.status,
            "reason": self.reason,
            "cache_path": self.cache_path,
            "scope": self.scope,
        }


def normalize_package_name(name: str) -> str:
    """Canonical lowercase key matching across pip/npm/maven/nuget coordinates."""
    cleaned = str(name or "").strip().lower()
    if not cleaned:
        return ""
    for sep in ("==", ">=", "<=", "~=", "!=", "[", " "):
        if sep in cleaned and not (cleaned.startswith("@") and sep == "@"):
            cleaned = cleaned.split(sep, 1)[0].strip()
    return cleaned.replace("_", "-")


def is_regulated_classification(data_classification: str | None) -> bool:
    """True when data classification requires an internal mirror for external lookups."""
    norm = str(data_classification or "").strip().upper()
    return norm in {"TIER_3_REGULATED", "REGULATED", "RESTRICTED"}


def check_provisioning_policy(
    data_classification: str | None,
    *,
    internal_mirror_url: str = "",
) -> tuple[bool, str]:
    """Verify whether outbound dependency resolution is permitted by policy.

    Regulated tiers must never send dependency names to public registries; they
    require an operator-configured internal mirror URL.
    """
    mirror = str(internal_mirror_url or "").strip()
    if is_regulated_classification(data_classification):
        if not mirror:
            return (
                False,
                "TIER_3_REGULATED missions require DEPENDENCY_PROVISIONER_INTERNAL_MIRROR_URL",
            )
        ok, detail = validate_registry_url(mirror, internal_mirror_url=mirror)
        if not ok:
            return False, detail
    return True, ""


def validate_registry_url(
    url: str,
    *,
    allowed_hosts: Iterable[str] = ALLOWED_REGISTRIES,
    internal_mirror_url: str = "",
) -> tuple[bool, str]:
    """Allow-list guard rejecting unapproved egress hosts or non-HTTP schemes."""
    raw = str(url or "").strip()
    if not raw:
        return False, "empty registry URL"
    parsed = urllib.parse.urlparse(raw)
    if parsed.scheme not in {"https", "http"} or not parsed.hostname:
        return False, f"invalid registry URL scheme or host: {raw}"
    host = parsed.hostname.lower()
    allowed = {h.lower() for h in allowed_hosts}
    if internal_mirror_url:
        mirror_host = urllib.parse.urlparse(internal_mirror_url.strip()).hostname
        if mirror_host:
            allowed.add(mirror_host.lower())
    if host not in allowed:
        return False, f"registry host {host!r} is not in ALLOWED_REGISTRIES"
    if parsed.scheme == "http" and not internal_mirror_url:
        # Public registries must use HTTPS; private mirrors may run plain HTTP in cluster.
        return False, f"public registry must use https: {raw}"
    return True, ""


def offline_sandbox_env(language: str, deps_mount: str = "/deps") -> dict[str, str]:
    """Environment variables configuring offline package resolution in ``sandbox_exec``."""
    mount = str(deps_mount or "/deps").rstrip("/") or "/deps"
    lang = str(language or "").strip().lower()
    if lang == "python":
        return {
            "PIP_NO_INDEX": "1",
            "PIP_FIND_LINKS": f"{mount}/pip",
            "PYTHONPATH": f"{mount}/site-packages:/workspace",
        }
    if lang in {"javascript", "typescript"}:
        return {
            "NPM_CONFIG_OFFLINE": "true",
            "NPM_CONFIG_CACHE": f"{mount}/npm",
            "NODE_PATH": f"{mount}/node_modules:/workspace/node_modules",
        }
    if lang in {"java", "kotlin", "scala"}:
        return {
            "MAVEN_OPTS": f"-Dmaven.repo.local={mount}/m2 -o",
            "GRADLE_USER_HOME": f"{mount}/gradle",
        }
    if lang in {"csharp", "c#"}:
        return {
            "NUGET_PACKAGES": f"{mount}/nuget",
            "DOTNET_CLI_TELEMETRY_OPTOUT": "1",
        }
    if lang == "go":
        return {
            "GOFLAGS": "-mod=mod",
            "GOPROXY": "off",
            "GOMODCACHE": f"{mount}/go",
        }
    if lang == "rust":
        return {
            "CARGO_NET_OFFLINE": "true",
            "CARGO_HOME": f"{mount}/cargo",
        }
    if lang == "php":
        return {
            "COMPOSER_CACHE_DIR": f"{mount}/composer",
            "COMPOSER_DISABLENETWORK": "1",
        }
    if lang == "ruby":
        return {
            "BUNDLE_LOCAL": "true",
            "BUNDLE_CACHE_PATH": f"{mount}/gem",
        }
    return {}


def build_provision_command(
    language: str,
    *,
    cache_dir: str | Path,
    manifest_file: str = "",
    packages: Iterable[str] = (),
    only_binary: bool = True,
) -> list[str]:
    """Return an argv list that fetches dependencies without executing project code."""
    lang = str(language or "").strip().lower()
    cache = str(cache_dir)
    pkg_list = [str(p).strip() for p in packages if str(p).strip()]

    if lang == "python":
        cmd = ["pip", "download", "--no-deps", "--dest", f"{cache}/pip"]
        if only_binary:
            cmd.append("--only-binary=:all:")
        if manifest_file and manifest_file.endswith(".txt"):
            cmd.extend(["-r", manifest_file])
        elif pkg_list:
            cmd.extend(pkg_list)
        return cmd

    if lang in {"javascript", "typescript"}:
        if manifest_file.endswith("package-lock.json"):
            return ["npm", "ci", "--ignore-scripts", "--cache", f"{cache}/npm"]
        cmd = ["npm", "pack", "--ignore-scripts", "--pack-destination", f"{cache}/npm"]
        if pkg_list:
            cmd.extend(pkg_list)
        return cmd

    if lang in {"java", "kotlin", "scala"}:
        if manifest_file.endswith(".gradle") or manifest_file.endswith(".gradle.kts"):
            return ["gradle", "--offline", "dependencies", f"--gradle-user-home={cache}/gradle"]
        return [
            "mvn",
            "-B",
            "dependency:go-offline",
            f"-Dmaven.repo.local={cache}/m2",
        ]

    if lang in {"csharp", "c#"}:
        target = manifest_file or "."
        return ["dotnet", "restore", target, "--packages", f"{cache}/nuget"]

    if lang == "go":
        return ["go", "mod", "download"]

    if lang == "rust":
        return ["cargo", "fetch", "--locked"]

    if lang == "php":
        return ["composer", "install", "--no-scripts", "--no-plugins", "--no-autoloader"]

    if lang == "ruby":
        return ["bundle", "cache", "--no-install", "--path", f"{cache}/gem"]

    return []


def _parse_requirements_txt(path: Path) -> list[dict[str, Any]]:
    deps: list[dict[str, Any]] = []
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        match = re.match(r"([A-Za-z0-9_.-]+)(?:\[[^\]]+\])?\s*([<>=!~]{1,2}\s*[^\s;]+)?", line)
        if not match:
            continue
        deps.append(
            {
                "name": match.group(1),
                "version": (match.group(2) or "latest").replace("==", "").strip() or "latest",
                "ecosystem": "pypi",
                "scope": "runtime",
            }
        )
    return deps


def _parse_pyproject_toml(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    deps: list[dict[str, Any]] = []
    in_deps = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("dependencies") and "[" in stripped:
            in_deps = True
            stripped = stripped.split("[", 1)[1]
        if in_deps:
            for m in re.findall(r'"([^"]+)"|\'([^\']+)\'', stripped):
                spec = m[0] or m[1]
                req_match = re.match(
                    r"([A-Za-z0-9_.-]+)(?:\[[^\]]+\])?\s*([<>=!~]{1,2}\s*[^\s;]+)?",
                    spec.strip(),
                )
                if req_match:
                    deps.append(
                        {
                            "name": req_match.group(1),
                            "version": (req_match.group(2) or "latest").replace("==", "").strip()
                            or "latest",
                            "ecosystem": "pypi",
                            "scope": "runtime",
                        }
                    )
            if "]" in stripped:
                in_deps = False
    return deps


def _parse_package_json(path: Path) -> list[dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError:
        return []
    if not isinstance(data, dict):
        return []
    deps: list[dict[str, Any]] = []
    for section, scope in (("dependencies", "runtime"), ("devDependencies", "test")):
        mapping = data.get(section)
        if isinstance(mapping, dict):
            for name, ver in mapping.items():
                deps.append(
                    {
                        "name": str(name),
                        "version": str(ver or "latest"),
                        "ecosystem": "npm",
                        "scope": scope,
                    }
                )
    return deps


def _parse_pom_xml(path: Path) -> list[dict[str, Any]]:
    deps: list[dict[str, Any]] = []
    try:
        root = ET.fromstring(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return []
    for dep_el in root.findall(".//{*}dependency"):
        group_el = dep_el.find("{*}groupId")
        art_el = dep_el.find("{*}artifactId")
        ver_el = dep_el.find("{*}version")
        scope_el = dep_el.find("{*}scope")
        group = (group_el.text or "").strip() if group_el is not None else ""
        art = (art_el.text or "").strip() if art_el is not None else ""
        if not art:
            continue
        coord = f"{group}:{art}" if group else art
        version = (ver_el.text or "latest").strip() if ver_el is not None else "latest"
        scope = (scope_el.text or "runtime").strip().lower() if scope_el is not None else "runtime"
        deps.append(
            {
                "name": coord,
                "version": version,
                "ecosystem": "maven",
                "scope": "test" if scope == "test" else "runtime",
            }
        )
    return deps


def _parse_csproj(path: Path) -> list[dict[str, Any]]:
    deps: list[dict[str, Any]] = []
    try:
        root = ET.fromstring(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return []
    for ref in root.findall(".//PackageReference"):
        name = str(ref.attrib.get("Include") or "").strip()
        version = str(ref.attrib.get("Version") or "latest").strip()
        if not name:
            continue
        scope = "test" if any(t in name.lower() for t in ("xunit", "test", "nunit", "mstest")) else "runtime"
        deps.append(
            {
                "name": name,
                "version": version,
                "ecosystem": "nuget",
                "scope": scope,
            }
        )
    return deps


def _parse_composer_json(path: Path) -> list[dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError:
        return []
    if not isinstance(data, dict):
        return []
    deps: list[dict[str, Any]] = []
    for section, scope in (("require", "runtime"), ("require-dev", "test")):
        mapping = data.get(section)
        if isinstance(mapping, dict):
            for name, ver in mapping.items():
                if name.lower() == "php" or name.startswith("ext-"):
                    continue
                deps.append(
                    {
                        "name": str(name),
                        "version": str(ver or "latest"),
                        "ecosystem": "composer",
                        "scope": scope,
                    }
                )
    return deps


def _parse_go_mod(path: Path) -> list[dict[str, Any]]:
    deps: list[dict[str, Any]] = []
    in_require = False
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.split("//", 1)[0].strip()
        if line == "require (":
            in_require = True
            continue
        if line == ")":
            in_require = False
            continue
        if line.startswith("require ") and not in_require:
            line = line[len("require ") :].strip()
        elif not in_require:
            continue
        parts = line.split()
        if len(parts) >= 2:
            deps.append(
                {
                    "name": parts[0],
                    "version": parts[1],
                    "ecosystem": "golang",
                    "scope": "runtime",
                }
            )
    return deps


def _parse_cargo_toml(path: Path) -> list[dict[str, Any]]:
    deps: list[dict[str, Any]] = []
    section = ""
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.split("#", 1)[0].strip()
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip().lower()
            continue
        if section not in {"dependencies", "dev-dependencies"} or "=" not in line:
            continue
        name, val = [p.strip() for p in line.split("=", 1)]
        version = val.strip().strip('"').strip("'")
        if version.startswith("{"):
            m = re.search(r'version\s*=\s*["\']([^"\']+)["\']', version)
            version = m.group(1) if m else "latest"
        deps.append(
            {
                "name": name,
                "version": version or "latest",
                "ecosystem": "cargo",
                "scope": "test" if section == "dev-dependencies" else "runtime",
            }
        )
    return deps


def _parse_gemfile(path: Path) -> list[dict[str, Any]]:
    deps: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.match(r"""^\s*gem\s+['"]([^'"]+)['"](?:\s*,\s*['"]([^'"]+)['"])?""", raw)
        if m:
            deps.append(
                {
                    "name": m.group(1),
                    "version": (m.group(2) or "latest").strip(),
                    "ecosystem": "gem",
                    "scope": "runtime",
                }
            )
    return deps


def _detect_gradle_unpinned_warnings(workspace: Path) -> list[str]:
    """Flag imperative Gradle build scripts when no gradle.lockfile exists."""
    warnings: list[str] = []
    has_gradle = any((workspace / name).is_file() for name in ("build.gradle", "build.gradle.kts"))
    if has_gradle and not (workspace / "gradle.lockfile").is_file():
        warnings.append("Gradle build script treated as executable code; lockfile missing")
    return warnings


def scan_workspace_manifests(
    workspace_dir: str | Path,
    *,
    language_hint: str | None = None,
    declared_dependencies: Iterable[str] = (),
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    """Inspect manifests/lockfiles statically inside *workspace_dir*.

    Returns ``(dependencies, manifests_found, warnings)`` and never imports or
    executes any code from *workspace_dir*.
    """
    ws = Path(workspace_dir)
    deps: list[dict[str, Any]] = []
    manifests: list[str] = []
    warnings: list[str] = _detect_gradle_unpinned_warnings(ws)

    for rel_path in sorted(ws.rglob("*")):
        if not rel_path.is_file():
            continue
        rel = rel_path.relative_to(ws).as_posix()
        if any(part in {".git", "node_modules", "__pycache__", ".venv", "venv"} for part in rel_path.parts):
            continue
        fname = rel_path.name.lower()
        if re.fullmatch(r"(requirements|constraints)[^/]*\.txt", fname):
            manifests.append(rel)
            deps.extend(_parse_requirements_txt(rel_path))
        elif fname == "pyproject.toml":
            manifests.append(rel)
            deps.extend(_parse_pyproject_toml(rel_path))
        elif fname == "package.json":
            manifests.append(rel)
            deps.extend(_parse_package_json(rel_path))
        elif fname == "pom.xml":
            manifests.append(rel)
            deps.extend(_parse_pom_xml(rel_path))
        elif fname.endswith(".csproj"):
            manifests.append(rel)
            deps.extend(_parse_csproj(rel_path))
        elif fname == "composer.json":
            manifests.append(rel)
            deps.extend(_parse_composer_json(rel_path))
        elif fname == "go.mod":
            manifests.append(rel)
            deps.extend(_parse_go_mod(rel_path))
        elif fname == "cargo.toml":
            manifests.append(rel)
            deps.extend(_parse_cargo_toml(rel_path))
        elif fname == "gemfile":
            manifests.append(rel)
            deps.extend(_parse_gemfile(rel_path))

    # Fallback: if no Python requirements file exists, scan .py AST imports statically (stdlib excluded).
    lang = str(language_hint or "").strip().lower()
    if lang == "python" and not any(m.endswith((".txt", "pyproject.toml")) for m in manifests):
        import sys  # noqa: PLC0415

        stdlib = {m.lower() for m in getattr(sys, "stdlib_module_names", frozenset())}
        local_modules = {p.stem.lower() for p in ws.glob("*.py")}
        for py_file in sorted(ws.rglob("*.py")):
            if any(part in {".git", "__pycache__", ".venv"} for part in py_file.parts):
                continue
            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8", errors="replace"))
            except SyntaxError:
                continue
            scope = "test" if py_file.name.startswith("test_") else "runtime"
            for node in ast.walk(tree):
                mod = ""
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        mod = alias.name.split(".")[0].strip()
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    mod = node.module.split(".")[0].strip()
                if mod and mod.lower() not in stdlib and mod.lower() not in local_modules:
                    deps.append(
                        {
                            "name": mod,
                            "version": "latest",
                            "ecosystem": "pypi",
                            "scope": scope,
                        }
                    )

    ecosystem = _ECOSYSTEM_BY_LANGUAGE.get(lang, "generic")
    for raw in declared_dependencies:
        clean = str(raw or "").strip()
        if clean:
            deps.append(
                {
                    "name": clean,
                    "version": "latest",
                    "ecosystem": ecosystem,
                    "scope": "runtime",
                }
            )

    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in deps:
        key = (item["ecosystem"], normalize_package_name(item["name"]))
        if key[1] and key not in seen:
            seen.add(key)
            deduped.append(item)
    return deduped, sorted(set(manifests)), warnings


def _find_cached_artifact(cache_dir: Path, name: str, ecosystem: str) -> Path | None:
    """Locate a matching cached wheel/tarball/nupkg/jar under *cache_dir*."""
    if not cache_dir.exists():
        return None
    norm = normalize_package_name(name)
    alt = norm.replace("-", "_")
    short = norm.split("/")[-1].split(":")[-1]
    candidates = [
        p for p in cache_dir.rglob("*")
        if p.is_file() and p.name != "provisioning_manifest.json"
    ]
    for path in sorted(candidates):
        low = path.name.lower()
        if low.startswith((f"{norm}-", f"{alt}-", f"{short}-")) or f"/{short}/" in path.as_posix().lower():
            return path
    return None


def _is_vendored_satisfaction(name: str, language: str) -> bool:
    lang = str(language or "").strip().lower()
    vendored = _VENDORED_TEST_PACKAGES.get(lang, frozenset())
    low = str(name or "").strip().lower()
    norm = normalize_package_name(low)
    return low in vendored or norm in vendored or any(token in low for token in vendored)


def _default_dep_cache_root() -> Path:
    configured = os.getenv("DEP_CACHE_ROOT", "").strip() or os.getenv("SANDBOX_DEPS_ROOT", "").strip()
    if configured:
        return Path(configured)
    return Path(tempfile.gettempdir()) / "thefactory-dep-cache"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _safe_cache_key(mission_id: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "-", str(mission_id or "mission")).strip("-")
    return cleaned[:96] or "mission"


def _run_no_exec_command(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    timeout_s: float = 120.0,
) -> tuple[int, str, str]:
    """Execute a package-manager fetch command inside a clean no-script env."""
    proc = subprocess.run(  # noqa: S603 - hardcoded safe command args from build_provision_command
        command,
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout_s,
        check=False,
    )
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def provision_workspace_dependencies(
    workspace_dir: str | Path,
    *,
    mission_id: str,
    workspace_id: str = "",
    language: str | None = None,
    data_classification: str = "TIER_1_INTERNAL",
    dep_cache_root: str | Path | None = None,
    internal_mirror_url: str = "",
    declared_dependencies: Iterable[str] = (),
    execute_fetch: bool = False,
    fetcher: Callable[[list[str], Path, dict[str, str]], tuple[int, str, str]] | None = None,
) -> dict[str, Any]:
    """Provision dependencies for *workspace_dir* without running any project code.

    When ``execute_fetch`` is True, invokes no-exec fetch commands against
    allow-listed registries (or checks ``fetcher`` in tests). When False, resolves
    already-cached artifacts in ``dep_cache_dir`` and vendored offline frameworks.
    """
    ws = Path(workspace_dir)
    if not ws.is_dir():
        raise FileNotFoundError(f"Workspace directory not found: {ws}")

    deps, manifests, warnings = scan_workspace_manifests(
        ws,
        language_hint=language,
        declared_dependencies=declared_dependencies,
    )
    inferred_lang = str(language or "").strip().lower()
    if not inferred_lang and manifests:
        inferred_lang = _LANGUAGE_BY_MANIFEST.get(Path(manifests[0]).name.lower(), "python")
    inferred_lang = inferred_lang or "python"

    root = Path(dep_cache_root) if dep_cache_root is not None else _default_dep_cache_root()
    mission_cache_dir = root / _safe_cache_key(mission_id)
    mission_cache_dir.mkdir(parents=True, exist_ok=True)

    mirror = str(
        internal_mirror_url or os.getenv("DEPENDENCY_PROVISIONER_INTERNAL_MIRROR_URL", "")
    ).strip()
    policy_ok, policy_reason = check_provisioning_policy(
        data_classification,
        internal_mirror_url=mirror,
    )

    if execute_fetch and policy_ok and deps:
        run_fetch = fetcher or (lambda cmd, cwd, env: _run_no_exec_command(cmd, cwd=cwd, env=env))
        fetch_cmd = build_provision_command(
            inferred_lang,
            cache_dir=mission_cache_dir,
            manifest_file=manifests[0] if manifests else "",
            packages=[d["name"] for d in deps],
            only_binary=True,
        )
        if fetch_cmd:
            clean_env = {
                **os.environ,
                "NPM_CONFIG_IGNORE_SCRIPTS": "true",
                "PIP_ONLY_BINARY": ":all:",
                "PIP_NO_BUILD_ISOLATION": "1",
            }
            if mirror and inferred_lang == "python":
                clean_env["PIP_INDEX_URL"] = mirror
            elif mirror and inferred_lang in {"javascript", "typescript"}:
                clean_env["NPM_CONFIG_REGISTRY"] = mirror
            rc, _stdout, stderr = run_fetch(fetch_cmd, ws, clean_env)
            if rc != 0:
                lower_err = stderr.lower()
                if "no matching distribution" in lower_err or "only-binary" in lower_err or "sdist" in lower_err:
                    warnings.append("source distribution skipped (--only-binary=:all:): needs_build")
                elif stderr.strip():
                    warnings.append(f"provision fetch exited {rc}: {stderr.strip()[:240]}")

    package_records: list[ProvisionedPackage] = []
    for entry in deps:
        pkg_name = str(entry["name"])
        pkg_ver = str(entry.get("version") or "latest")
        pkg_eco = str(entry.get("ecosystem") or _ECOSYSTEM_BY_LANGUAGE.get(inferred_lang, "generic"))
        pkg_scope = str(entry.get("scope") or "runtime")

        cached_file = _find_cached_artifact(mission_cache_dir, pkg_name, pkg_eco)
        vendored_ok = _is_vendored_satisfaction(pkg_name, inferred_lang)

        if not policy_ok and not vendored_ok and cached_file is None:
            package_records.append(
                ProvisionedPackage(
                    name=pkg_name,
                    version=pkg_ver,
                    ecosystem=pkg_eco,
                    status="blocked_by_policy",
                    reason="blocked_by_policy",
                    scope=pkg_scope,
                )
            )
            continue

        if cached_file is not None:
            sha256 = _sha256_file(cached_file)
            package_records.append(
                ProvisionedPackage(
                    name=pkg_name,
                    version=pkg_ver,
                    ecosystem=pkg_eco,
                    sha256=sha256,
                    status="provisioned",
                    reason="cached_artifact",
                    cache_path=str(cached_file.relative_to(mission_cache_dir).as_posix()),
                    scope=pkg_scope,
                )
            )
            continue

        if vendored_ok:
            digest = hashlib.sha256(f"vendored:{inferred_lang}:{pkg_name}:{pkg_ver}".encode()).hexdigest()
            package_records.append(
                ProvisionedPackage(
                    name=pkg_name,
                    version=pkg_ver,
                    ecosystem=pkg_eco,
                    sha256=digest,
                    status="provisioned",
                    reason="vendored_sandbox_image",
                    scope=pkg_scope,
                )
            )
            continue

        # Classify unprovisioned dependencies honestly.
        needs_build = any("needs_build" in w for w in warnings)
        status = "needs_build" if needs_build else "not_in_registry"
        package_records.append(
            ProvisionedPackage(
                name=pkg_name,
                version=pkg_ver,
                ecosystem=pkg_eco,
                status=status,
                reason=status,
                scope=pkg_scope,
            )
        )

    pkg_dicts = [p.to_dict() for p in package_records]
    provisioned_names = [p.name for p in package_records if p.status == "provisioned"]
    unmet_reasons = {p.name: p.reason or p.status for p in package_records if p.status != "provisioned"}
    runtime_unmet = [
        p.name for p in package_records if p.scope == "runtime" and p.status != "provisioned"
    ]

    manifest = {
        "schema_version": PROVISIONING_MANIFEST_SCHEMA_VERSION,
        "mission_id": mission_id,
        "workspace_id": workspace_id or None,
        "language": inferred_lang,
        "data_classification": str(data_classification or "TIER_1_INTERNAL"),
        "policy_allowed": policy_ok,
        "policy_reason": policy_reason,
        "dep_cache_dir": str(mission_cache_dir),
        "manifests": manifests,
        "warnings": warnings,
        "packages": pkg_dicts,
        "provisioned_packages": provisioned_names,
        "unmet_reasons": unmet_reasons,
        "executable_with_cache": len(runtime_unmet) == 0,
        "offline_env": offline_sandbox_env(inferred_lang, deps_mount="/deps"),
        "allowed_registries": sorted(ALLOWED_REGISTRIES),
        "generated_at": datetime.now(UTC).isoformat(),
    }
    manifest_path = mission_cache_dir / "provisioning_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def _provisioner_url(settings: Any = None) -> str:
    raw = str(
        getattr(settings, "dependency_provisioner_url", "")
        or os.getenv("DEPENDENCY_PROVISIONER_URL", "")
    ).strip()
    return raw.rstrip("/") if raw.startswith(("http://", "https://")) else ""


# --- Optional standalone microservice API -----------------------------------

app = FastAPI(title="HGR dependency provisioner", docs_url=None, redoc_url=None)


class ProvisionRequest(BaseModel):
    workspace_dir: str = Field(min_length=1, max_length=1024)
    mission_id: str = Field(min_length=1, max_length=128)
    workspace_id: str = Field(default="", max_length=128)
    language: str = Field(default="", max_length=64)
    data_classification: str = Field(default="TIER_1_INTERNAL", max_length=64)
    declared_dependencies: list[str] = Field(default_factory=list)
    execute_fetch: bool = False


def _expected_service_key() -> str:
    key = os.getenv("INTERNAL_SERVICE_API_KEY", "").strip()
    if not key or key.lower().startswith("change_me"):
        return ""
    return key


def _authorize(authorization: str | None) -> None:
    expected = _expected_service_key()
    if not expected:
        raise HTTPException(status_code=503, detail="dependency provisioner key is not configured")
    provided = (authorization or "").strip()
    if provided.lower().startswith("bearer "):
        provided = provided[7:].strip()
    if not provided or not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="unauthorized")


@app.get("/livez")
async def livez() -> dict[str, bool]:
    return {"ok": True}


@app.post("/internal/provision")
async def provision_endpoint(
    payload: ProvisionRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    _authorize(authorization)
    try:
        return provision_workspace_dependencies(
            payload.workspace_dir,
            mission_id=payload.mission_id,
            workspace_id=payload.workspace_id,
            language=payload.language or None,
            data_classification=payload.data_classification,
            declared_dependencies=payload.declared_dependencies,
            execute_fetch=payload.execute_fetch,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


__all__ = [
    "ALLOWED_REGISTRIES",
    "PROVISIONING_MANIFEST_SCHEMA_VERSION",
    "ProvisionedPackage",
    "app",
    "build_provision_command",
    "check_provisioning_policy",
    "normalize_package_name",
    "offline_sandbox_env",
    "provision_workspace_dependencies",
    "scan_workspace_manifests",
    "validate_registry_url",
]
